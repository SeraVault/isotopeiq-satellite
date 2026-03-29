# Cisco IOS / IOS-XE Baseline Parser
# Parses output from cisco_ios_baseline_collector.sh into the canonical schema.
#
# `result` — raw string output from the collector
# `output` — canonical dict to populate (pre-filled with empty structure)

import re

SEP = "---ISOTOPEIQ---"

# ── Split raw output into named sections ──────────────────────────────────────

sections = {}
current = None
buf = []

for line in result.splitlines():
    if line.startswith(SEP + "[") and line.endswith("]"):
        if current is not None:
            sections[current] = "\n".join(buf).strip()
        current = line[len(SEP) + 1:-1]
        buf = []
    elif current is not None:
        buf.append(line)

if current and current != "END":
    sections[current] = "\n".join(buf).strip()


def lines(section):
    return [l for l in sections.get(section, "").splitlines() if l.strip()]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _find(pattern, text, default="", flags=0):
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else default


def _findall(pattern, text, flags=0):
    return re.findall(pattern, text, flags)


# ── device + hardware + os (from show version) ────────────────────────────────

ver_raw = sections.get("version", "")

# Hostname appears on the first non-blank line as "<hostname> uptime is ..."
hostname_match = re.search(r"^(\S+)\s+uptime\s+is", ver_raw, re.MULTILINE)
hostname = hostname_match.group(1) if hostname_match else ""

output["device"]["hostname"]    = hostname
output["device"]["fqdn"]        = hostname
output["device"]["device_type"] = "network"
output["device"]["vendor"]      = "Cisco"

# Model: "Cisco IOS Software ... Cisco 4321 ..." / "Model Number: ..."
model = _find(r"(?:^|\s)(?:cisco\s+)?([A-Z]{1,4}\d[\w/-]+)\s+\(?revision", ver_raw, flags=re.IGNORECASE | re.MULTILINE)
if not model:
    model = _find(r"Model\s+[Nn]umber\s*:\s*(\S+)", ver_raw)
if not model:
    model = _find(r"^[Cc]isco\s+(\S+)\s+.*\(revision", ver_raw, flags=re.MULTILINE)
output["device"]["model"] = model

# IOS version string: "Cisco IOS Software, Version 15.7(3)M4, ..."
ios_version = _find(r"[Cc]isco IOS.*?[Vv]ersion\s+([\d().a-zA-Z]+)", ver_raw)
ios_name    = "Cisco IOS"
if "IOS-XE" in ver_raw or "IOS XE" in ver_raw:
    ios_name = "Cisco IOS XE"
elif "IOS-XR" in ver_raw or "IOS XR" in ver_raw:
    ios_name = "Cisco IOS XR"
elif "NX-OS" in ver_raw:
    ios_name = "Cisco NX-OS"

output["os"]["name"]    = ios_name
output["os"]["version"] = ios_version
output["os"]["build"]   = _find(r"(?:RELEASE SOFTWARE|Release).*?\(([^)]+)\)", ver_raw)
output["os"]["kernel"]  = ios_version   # IOS has no separate kernel version

# Serial number from show version
serial = _find(r"[Pp]rocessor board ID\s+(\S+)", ver_raw)
output["hardware"]["serial_number"] = serial

# CPU: "Cisco ... processor ..."
cpu = _find(r"^[Cc]isco\s+\S+.*?with\s+([\d]+[KMG]?)\s+bytes", ver_raw, flags=re.MULTILINE)
cpu_model = _find(r"(\S+ CPU at \S+)", ver_raw)
if not cpu_model:
    cpu_model = _find(r"(?:Cisco|cisco)\s+([\w/]+)\s+processor", ver_raw)
output["hardware"]["cpu_model"] = cpu_model

# RAM: "... with 4194304K bytes of physical memory"
ram_match = re.search(r"with\s+([\d]+)K\s+bytes of physical memory", ver_raw, re.IGNORECASE)
if ram_match:
    output["hardware"]["memory_gb"] = round(int(ram_match.group(1)) / 1024 / 1024, 2)

output["hardware"]["bios_version"]        = _find(r"System image file.*?\"([^\"]+)\"", ver_raw)
output["hardware"]["architecture"]        = "mips" if "MIPS" in ver_raw else "x86_64"
output["hardware"]["virtualization_type"] = "other" if "Virtual" in ver_raw or "CSR" in ver_raw else "bare-metal"

# ── os — NTP ──────────────────────────────────────────────────────────────────

ntp_raw = sections.get("ntp_status", "")
ntp_assoc_raw = sections.get("ntp_assoc", "")

# Configured NTP servers from running-config
running = sections.get("running_config", "")
ntp_servers = _findall(r"^ntp server\s+(\S+)", running, re.MULTILINE)
output["os"]["ntp_servers"] = ntp_servers

# NTP sync status: "Clock is synchronized, ..." or "Clock is unsynchronized"
if re.search(r"[Cc]lock is synchronized", ntp_raw):
    output["os"]["ntp_synced"] = True
elif re.search(r"[Cc]lock is unsynchronized", ntp_raw):
    output["os"]["ntp_synced"] = False
else:
    output["os"]["ntp_synced"] = None

# Timezone from "show clock detail"
clock_raw = sections.get("clock", "")
tz = _find(r"Time source is.*\nTime zone is (\S+)", clock_raw)
if not tz:
    tz = _find(r"^clock timezone\s+(\S+)", running, flags=re.MULTILINE)
if not tz:
    tz = _find(r"(\w+)\s+time$", clock_raw, flags=re.MULTILINE)
output["os"]["timezone"] = tz


# ── network — interfaces ──────────────────────────────────────────────────────

int_raw     = sections.get("interfaces", "")
ip_int_raw  = sections.get("ip_int_detail", "")
ip_brief    = sections.get("ip_interfaces", "")

def _parse_interfaces(int_raw, ip_int_raw, ip_brief_raw):
    ifaces = []
    # Split on interface header lines: "GigabitEthernet0/0 is ..."
    blocks = re.split(r"(?=^\S\S+\s+is\s+(?:up|down|administratively down))", int_raw, flags=re.MULTILINE)
    for block in blocks:
        if not block.strip():
            continue
        hdr = re.match(r"^(\S+)\s+is\s+(up|down|administratively down),\s+line protocol is\s+(up|down)", block, re.IGNORECASE)
        if not hdr:
            continue
        name        = hdr.group(1)
        admin_str   = hdr.group(2).lower()
        oper_str    = hdr.group(3).lower()
        admin_st    = "down" if "administratively" in admin_str else admin_str
        oper_st     = oper_str

        mac   = _find(r"[Aa]ddress is\s+([0-9a-fA-F.]{14})", block)
        mtu   = _find(r"MTU\s+(\d+)\s+bytes", block)
        desc  = _find(r"Description:\s*(.+)", block)
        speed_raw = _find(r"BW\s+(\d+)\s+Kbit", block)
        speed = ""
        if speed_raw:
            bw_kbit = int(speed_raw)
            if bw_kbit >= 1_000_000:
                speed = "{}G".format(bw_kbit // 1_000_000)
            elif bw_kbit >= 1_000:
                speed = "{}M".format(bw_kbit // 1_000)
            else:
                speed = "{}K".format(bw_kbit)

        duplex_raw = _find(r"(Full|Half|Auto)-duplex", block, flags=re.IGNORECASE).lower()
        duplex = duplex_raw if duplex_raw in ("full", "half", "auto") else "unknown"

        # IPv4 addresses from "show ip interface detail"
        ipv4 = []
        ip_block_match = re.search(
            r"^" + re.escape(name) + r"\s+is.*?(?=^\S|\Z)",
            ip_int_raw, re.MULTILINE | re.DOTALL
        )
        if ip_block_match:
            ipv4 = re.findall(r"Internet address is\s+(\d+\.\d+\.\d+\.\d+/\d+)", ip_block_match.group())
            secondaries = re.findall(r"Secondary address\s+(\d+\.\d+\.\d+\.\d+/\d+)", ip_block_match.group())
            ipv4.extend(secondaries)

        # Port mode (access/trunk/routed)
        port_mode = "routed"
        access_vlan = None
        trunk_vlans = ""
        if ipv4:
            port_mode = "routed"
        else:
            # Check switchport mode from running-config
            sw_match = re.search(
                r"interface\s+" + re.escape(name) + r".*?(?=\ninterface\s|\Z)",
                running, re.DOTALL | re.IGNORECASE
            )
            if sw_match:
                sw_block = sw_match.group()
                if re.search(r"switchport mode trunk", sw_block, re.IGNORECASE):
                    port_mode = "trunk"
                    m = re.search(r"switchport trunk allowed vlan\s+(.+)", sw_block, re.IGNORECASE)
                    trunk_vlans = m.group(1).strip() if m else ""
                elif re.search(r"switchport mode access", sw_block, re.IGNORECASE):
                    port_mode = "access"
                    m = re.search(r"switchport access vlan\s+(\d+)", sw_block, re.IGNORECASE)
                    access_vlan = int(m.group(1)) if m else 1

        iface = {
            "name":         name,
            "description":  desc,
            "mac":          mac.lower().replace(".", ""),
            "ipv4":         ipv4,
            "ipv6":         [],
            "admin_status": admin_st,
            "oper_status":  oper_st,
            "speed":        speed,
            "duplex":       duplex,
            "mtu":          int(mtu) if mtu else None,
            "port_mode":    port_mode,
        }
        if port_mode == "access":
            iface["access_vlan"] = access_vlan
        if port_mode == "trunk":
            iface["trunk_vlans"] = trunk_vlans
        ifaces.append(iface)
    return ifaces

output["network"]["interfaces"] = _parse_interfaces(int_raw, ip_int_raw, ip_brief)


# ── network — DNS servers (from running-config) ───────────────────────────────

dns_servers = _findall(r"^ip name-server\s+(\S+)", running, re.MULTILINE)
output["network"]["dns_servers"] = dns_servers


# ── network — routes ──────────────────────────────────────────────────────────

route_raw = sections.get("ip_routes", "")

def _parse_routes(raw):
    routes = []
    # IOS route format:
    # S* 0.0.0.0/0 [1/0] via 192.0.2.1
    # C  10.0.0.0/8 is directly connected, GigabitEthernet0/0
    # O  172.16.0.0/12 [110/20] via 10.1.1.1, 00:01:02, GigabitEthernet0/1
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("Codes:") or line.startswith("Gateway"):
            continue
        # Multi-line "via" continuation lines start with spaces
        m = re.match(
            r"^[A-Z*i\s]{1,5}\s+(\d+\.\d+\.\d+\.\d+/?\d*|::/\d+|0\.0\.0\.0/0)\s+"
            r"(?:\[[\d/]+\]\s+)?(?:via\s+(\S+?),?.*?,\s*(\S+))?",
            line
        )
        if not m:
            m = re.match(
                r"^[A-Z*i\s]{1,5}\s+(\d+\.\d+\.\d+\.\d+/?\d*)\s+is directly connected,\s+(\S+)",
                line
            )
            if m:
                routes.append({
                    "destination": m.group(1),
                    "gateway":     "",
                    "interface":   m.group(2).rstrip(","),
                    "metric":      None,
                })
            continue
        dst = m.group(1)
        gw  = m.group(2) or ""
        dev = m.group(3) or ""
        routes.append({
            "destination": dst,
            "gateway":     gw.rstrip(","),
            "interface":   dev.rstrip(","),
            "metric":      None,
        })
    return routes

output["network"]["routes"] = _parse_routes(route_raw)

# Default gateway
for r in output["network"]["routes"]:
    if r.get("destination") in ("0.0.0.0/0", "0.0.0.0"):
        output["network"]["default_gateway"] = r.get("gateway", "")
        break


# ── users (from show users + running-config local users) ─────────────────────

# Local users defined in running-config: "username admin privilege 15 ..."
for m in re.finditer(
    r"^username\s+(\S+)\s+(.*?)$", running, re.MULTILINE
):
    uname = m.group(1)
    rest  = m.group(2)
    priv  = _find(r"privilege\s+(\d+)", rest) or "1"
    disabled = bool(re.search(r"\bnoenable\b", rest, re.IGNORECASE))
    output["users"].append({
        "username":          uname,
        "uid":               priv,       # privilege level as uid proxy
        "groups":            [],
        "home":              "",
        "shell":             "",
        "disabled":          disabled,
        "password_last_set": "",
        "last_login":        "",
        "sudo_privileges":   "enable" if int(priv) >= 15 else "",
    })


# ── groups (privilege levels used as groups) ──────────────────────────────────

# IOS uses privilege levels 0-15; represent used levels as pseudo-groups
priv_levels = set()
for u in output["users"]:
    if u.get("uid"):
        priv_levels.add(u["uid"])
for level in sorted(priv_levels, key=lambda x: int(x) if x.isdigit() else 0):
    output["groups"].append({
        "group_name": "privilege-{}".format(level),
        "gid":        level,
        "members":    [u["username"] for u in output["users"] if u.get("uid") == level],
    })


# ── packages (IOS images / feature sets from show version) ───────────────────

# System image file: "flash:packages.conf" or "flash:isr4300-universalk9.SPA.03.16..."
image = _find(r'System image file is\s+"([^"]+)"', ver_raw)
ios_pkg = {
    "name":         image or ios_name,
    "version":      ios_version,
    "vendor":       "Cisco",
    "install_date": "",
    "source":       "other",
}
output["packages"].append(ios_pkg)

# Feature licenses / technology packages from show version
for lic in re.finditer(r"^([\w-]+)\s+\S+\s+(?:Permanent|Evaluation|RTU|In Use)", ver_raw, re.MULTILINE):
    output["packages"].append({
        "name":         lic.group(1),
        "version":      "",
        "vendor":       "Cisco",
        "install_date": "",
        "source":       "other",
    })


# ── services (IOS processes from running-config — enabled/disabled features) ──

IOS_SERVICES = [
    ("ip http server",          "http"),
    ("ip http secure-server",   "https"),
    ("snmp-server",             "snmp"),
    ("telnet",                  "telnet"),
    ("ip ftp server",           "ftp"),
    ("ip tftp server",          "tftp"),
    ("ip scp server",           "scp"),
    ("cdp run",                 "cdp"),
    ("lldp run",                "lldp"),
    ("ip dhcp pool",            "dhcp"),
    ("ip nat ",                 "nat"),
    ("crypto isakmp",           "ipsec-isakmp"),
    ("ip ospf",                 "ospf"),
    ("router bgp",              "bgp"),
    ("router eigrp",            "eigrp"),
    ("router rip",              "rip"),
    ("spanning-tree mode",      "spanning-tree"),
    ("service password-encryption", "password-encryption"),
    ("aaa new-model",           "aaa"),
    ("ip ssh",                  "ssh"),
]

for pattern, svc_name in IOS_SERVICES:
    enabled = bool(re.search(r"^" + re.escape(pattern), running, re.MULTILINE))
    # "no <service>" means disabled
    disabled = bool(re.search(r"^no\s+" + re.escape(pattern.strip()), running, re.MULTILINE))
    status  = "running" if (enabled and not disabled) else "stopped"
    startup = "enabled" if (enabled and not disabled) else "disabled"
    output["services"].append({
        "name":    svc_name,
        "status":  status,
        "startup": startup,
    })


# ── filesystem (flash from show flash) ───────────────────────────────────────

flash_raw = sections.get("flash", "")
# "16777216 bytes total (10485760 bytes free)"
flash_total = _find(r"([\d]+)\s+bytes total", flash_raw)
flash_free  = _find(r"([\d]+)\s+bytes free", flash_raw)
if flash_total:
    size_gb = round(int(flash_total) / 1024**3, 2)
    free_gb = round(int(flash_free) / 1024**3, 2) if flash_free else None
    output["filesystem"].append({
        "mount":         "flash:",
        "type":          "flash",
        "size_gb":       size_gb,
        "free_gb":       free_gb,
        "mount_options": [],
        "suid_files":    [],
    })


# ── security ──────────────────────────────────────────────────────────────────

# Firewall: "ip inspect" or ZBF "zone-pair security" present
fw_enabled = bool(
    re.search(r"^ip inspect", running, re.MULTILINE) or
    re.search(r"^zone-pair security", running, re.MULTILINE) or
    re.search(r"^ip access-group", running, re.MULTILINE)
)
output["security"]["firewall_enabled"] = fw_enabled

# SSH enabled and version
ssh_raw = sections.get("ip_ssh", "")
ssh_ver = _find(r"SSH [Vv]ersion\s+:\s+([\d.]+)", ssh_raw) or _find(r"version (\d+\.\d+)", ssh_raw)

# Secure boot
boot_raw = sections.get("boot", "")
output["security"]["secure_boot"] = bool(re.search(r"secure-boot-image", boot_raw, re.IGNORECASE))

# Password encryption
output["security"]["audit_logging_enabled"] = bool(
    re.search(r"^logging \S+", running, re.MULTILINE)
)

# Password policy
policy = {}
min_len = _find(r"security passwords min-length\s+(\d+)", running)
if min_len:
    policy["min_length"] = int(min_len)
max_age = _find(r"security authentication failure rate\s+(\d+)", running)
if max_age:
    policy["lockout_threshold"] = int(max_age)
if policy:
    output["security"]["password_policy"] = policy


# ── snmp ──────────────────────────────────────────────────────────────────────

snmp_community_raw = sections.get("snmp_community", "")
snmp_users_raw     = sections.get("snmp_users", "")
snmp_groups_raw    = sections.get("snmp_groups", "")

snmp_enabled = bool(re.search(r"^snmp-server", running, re.MULTILINE))

versions = set()
if re.search(r"^snmp-server community", running, re.MULTILINE):
    versions.update(["v2c"])
if re.search(r"^snmp-server group\s+\S+\s+v3", running, re.MULTILINE):
    versions.add("v3")
if re.search(r"^snmp-server group\s+\S+\s+v1\b", running, re.MULTILINE):
    versions.add("v1")

# Community strings (read/write)
communities = _findall(r"^snmp-server community\s+(\S+)", running, re.MULTILINE)

# Trap targets
trap_targets = _findall(r"^snmp-server host\s+(\S+)", running, re.MULTILINE)

# SNMPv3 users from "show snmp user"
v3_users = []
for m in re.finditer(
    r"^User name:\s+(\S+).*?Authentication Protocol:\s+(\S+).*?Privacy Protocol:\s+(\S+)",
    snmp_users_raw, re.DOTALL | re.MULTILINE
):
    auth_proto = m.group(2).upper()
    priv_proto = m.group(3).upper()
    if auth_proto == "NONE" and priv_proto == "NONE":
        sec_level = "noAuthNoPriv"
    elif priv_proto == "NONE":
        sec_level = "authNoPriv"
    else:
        sec_level = "authPriv"
    v3_users.append({
        "username":       m.group(1),
        "auth_protocol":  auth_proto,
        "priv_protocol":  priv_proto,
        "security_level": sec_level,
    })

location = _find(r"^snmp-server location\s+(.+)", running, flags=re.MULTILINE)
contact  = _find(r"^snmp-server contact\s+(.+)", running, flags=re.MULTILINE)

output["snmp"] = {
    "enabled":      snmp_enabled,
    "versions":     sorted(versions),
    "communities":  communities,
    "v3_users":     v3_users,
    "trap_targets": trap_targets,
    "location":     location,
    "contact":      contact,
}


# ── vlans ─────────────────────────────────────────────────────────────────────

vlan_raw = sections.get("vlans", "")
vlans = []
for line in vlan_raw.splitlines():
    # "1    default                          active    Gi0/0, Gi0/1"
    m = re.match(r"^\s*(\d+)\s+(\S+)\s+(active|act|suspended|unsup)", line, re.IGNORECASE)
    if m:
        state_raw = m.group(3).lower()
        state = "active" if state_raw in ("active", "act") else "suspended"
        vlans.append({
            "id":    int(m.group(1)),
            "name":  m.group(2),
            "state": state,
        })
output["vlans"] = vlans


# ── acls ──────────────────────────────────────────────────────────────────────

acl_raw = sections.get("access_lists", "")

def _parse_acls(raw):
    acls = {}
    current_acl = None
    for line in raw.splitlines():
        line = line.rstrip()
        # Named/numbered ACL header
        m_named = re.match(r"^(Extended|Standard) IP access list\s+(\S+)", line)
        m_num   = re.match(r"^(IP|Extended|Standard) access list\s+(\S+)", line)
        header  = m_named or m_num
        if header:
            acl_type_raw = header.group(1).lower()
            acl_type = "extended" if "extend" in acl_type_raw else "standard"
            name = header.group(2)
            current_acl = name
            acls[name] = {"name": name, "type": acl_type, "entries": []}
            continue
        if current_acl is None:
            continue
        line = line.strip()
        if not line:
            continue
        # ACE line: "10 permit tcp 10.0.0.0 0.255.255.255 any eq 80"
        m_ace = re.match(
            r"^(\d+)?\s*(permit|deny|remark)\s+(.*)",
            line, re.IGNORECASE
        )
        if not m_ace:
            continue
        seq    = int(m_ace.group(1)) if m_ace.group(1) else None
        action = m_ace.group(2).lower()
        rest   = m_ace.group(3).strip()
        # Protocol
        proto_m = re.match(r"^(\w+)\s+(.*)", rest)
        proto  = proto_m.group(1) if proto_m else "ip"
        remain = proto_m.group(2) if proto_m else rest
        # Source/destination (simplified — first two address tokens)
        addr_tokens = remain.split()
        src, dst = "any", "any"
        if addr_tokens:
            src = addr_tokens[0]
            if len(addr_tokens) > 1 and not addr_tokens[1].startswith("eq"):
                dst = addr_tokens[1]
        acls[current_acl]["entries"].append({
            "sequence":    seq,
            "action":      action,
            "protocol":    proto,
            "source":      src,
            "destination": dst,
            "description": "",
        })
    return list(acls.values())

output["acls"] = _parse_acls(acl_raw)


# ── routing_protocols ─────────────────────────────────────────────────────────

routing_protocols = []

# BGP
bgp_sum = sections.get("ip_bgp_sum", "")
bgp_asn = _find(r"local AS number\s+(\d+)", bgp_sum)
if bgp_asn or re.search(r"^router bgp", running, re.MULTILINE):
    if not bgp_asn:
        bgp_asn = _find(r"^router bgp\s+(\d+)", running, flags=re.MULTILINE)
    router_id = _find(r"BGP router identifier\s+([\d.]+)", bgp_sum)
    neighbors = []
    for m in re.finditer(
        r"^([\d.]+)\s+\d+\s+(\d+)\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+\s+\S+\s+(\w+)",
        bgp_sum, re.MULTILINE
    ):
        neighbors.append({
            "address":     m.group(1),
            "remote_asn":  int(m.group(2)),
            "state":       m.group(3),
            "description": "",
        })
    routing_protocols.append({
        "protocol":  "bgp",
        "instance":  bgp_asn,
        "router_id": router_id,
        "networks":  _findall(r"^network\s+(\S+)", running, re.MULTILINE),
        "neighbors": neighbors,
    })

# OSPF
ospf_raw  = sections.get("ip_ospf", "")
ospf_neigh = sections.get("ip_ospf_neigh", "")
ospf_pid  = _find(r"Routing Process \"ospf\s+(\d+)\"", ospf_raw)
if ospf_pid or re.search(r"^router ospf", running, re.MULTILINE):
    ospf_rid = _find(r"Router ID\s+([\d.]+)", ospf_raw)
    neighbors = []
    for m in re.finditer(
        r"^([\d.]+)\s+\d+\s+(\S+)/\s*\S+\s+\S+\s+(\S+)",
        ospf_neigh, re.MULTILINE
    ):
        neighbors.append({
            "address":     m.group(1),
            "remote_asn":  None,
            "state":       m.group(2),
            "description": "",
        })
    routing_protocols.append({
        "protocol":  "ospf",
        "instance":  ospf_pid or _find(r"^router ospf\s+(\d+)", running, flags=re.MULTILINE),
        "router_id": ospf_rid,
        "networks":  [],
        "neighbors": neighbors,
    })

# EIGRP
eigrp_neigh = sections.get("ip_eigrp_neigh", "")
eigrp_asn   = _find(r"^router eigrp\s+(\d+)", running, flags=re.MULTILINE)
if eigrp_asn:
    neighbors = []
    for m in re.finditer(r"^([\d.]+)\s+(\S+)\s+\d+", eigrp_neigh, re.MULTILINE):
        neighbors.append({
            "address":     m.group(1),
            "remote_asn":  None,
            "state":       "Established",
            "description": "",
        })
    routing_protocols.append({
        "protocol":  "eigrp",
        "instance":  eigrp_asn,
        "router_id": "",
        "networks":  [],
        "neighbors": neighbors,
    })

# RIP
if re.search(r"^router rip", running, re.MULTILINE):
    routing_protocols.append({
        "protocol":  "rip",
        "instance":  "",
        "router_id": "",
        "networks":  _findall(r"^network\s+(\S+)", running, re.MULTILINE),
        "neighbors": [],
    })

output["routing_protocols"] = routing_protocols


# ── aaa ───────────────────────────────────────────────────────────────────────

tacacs_servers = _findall(r"^tacacs-server host\s+(\S+)", running, re.MULTILINE)
tacacs_servers += _findall(r"^\s+address ipv4\s+(\S+)", running, re.MULTILINE)  # IOS-XE group syntax
radius_servers = _findall(r"^radius-server host\s+(\S+)", running, re.MULTILINE)
radius_servers += _findall(r"^\s+address ipv4\s+(\S+).*auth-port", running, re.MULTILINE)

auth_lists = []
for m in re.finditer(r"^aaa authentication (\S+)\s+(\S+)\s+(.+)", running, re.MULTILINE):
    auth_lists.append({
        "name":    "{} {}".format(m.group(1), m.group(2)),
        "methods": m.group(3).strip().split(),
    })

authz_lists = []
for m in re.finditer(r"^aaa authorization (\S+)\s+(\S+)\s+(.+)", running, re.MULTILINE):
    authz_lists.append({
        "name":    "{} {}".format(m.group(1), m.group(2)),
        "methods": m.group(3).strip().split(),
    })

acct_lists = []
for m in re.finditer(r"^aaa accounting (\S+)\s+(\S+)\s+(.+)", running, re.MULTILINE):
    acct_lists.append({
        "name":    "{} {}".format(m.group(1), m.group(2)),
        "methods": m.group(3).strip().split(),
    })

output["aaa"] = {
    "tacacs_servers":       list(set(tacacs_servers)),
    "radius_servers":       list(set(radius_servers)),
    "authentication_lists": auth_lists,
    "authorization_lists":  authz_lists,
    "accounting_lists":     acct_lists,
}


# ── spanning_tree ─────────────────────────────────────────────────────────────

stp_raw = sections.get("spanning_tree", "")

stp_mode_raw = _find(r"^spanning-tree mode\s+(\S+)", running, flags=re.MULTILINE)
mode_map = {
    "pvst": "pvst", "rapid-pvst": "rapid-pvst",
    "mst": "mstp", "rstp": "rstp",
}
stp_mode = mode_map.get(stp_mode_raw.lower(), "pvst") if stp_mode_raw else "pvst"

# Root bridge detection: "This bridge is the root"
is_root = bool(re.search(r"This bridge is the root", stp_raw, re.IGNORECASE))
root_priority = None
root_address  = ""
m_root = re.search(r"Root ID\s+Priority\s+(\d+).*?Address\s+(\S+)", stp_raw, re.DOTALL)
if m_root:
    root_priority = int(m_root.group(1))
    root_address  = m_root.group(2)

# Per-port STP state
stp_ports = []
for m in re.finditer(
    r"^(\S+)\s+(Root|Desg|Altn|Back|Disc|BLK|FWD|LRN|LIS)\s+(FWD|BLK|LRN|LIS|DIS)\s",
    stp_raw, re.MULTILINE | re.IGNORECASE
):
    role_map  = {"root": "root", "desg": "designated", "altn": "alternate",
                 "back": "backup", "disc": "disabled"}
    state_map = {"fwd": "forwarding", "blk": "blocking", "lrn": "learning",
                 "lis": "listening", "dis": "disabled"}
    stp_ports.append({
        "interface":   m.group(1),
        "role":        role_map.get(m.group(2).lower(), "unknown"),
        "state":       state_map.get(m.group(3).lower(), "unknown"),
        "bpdu_guard":  None,
        "bpdu_filter": None,
        "root_guard":  None,
    })

# Enhance with BPDU guard/filter info from running-config
for port in stp_ports:
    iface_block_m = re.search(
        r"interface\s+" + re.escape(port["interface"]) + r".*?(?=\ninterface\s|\Z)",
        running, re.DOTALL | re.IGNORECASE
    )
    if iface_block_m:
        blk = iface_block_m.group()
        port["bpdu_guard"]  = bool(re.search(r"spanning-tree bpduguard enable", blk, re.IGNORECASE))
        port["bpdu_filter"] = bool(re.search(r"spanning-tree bpdufilter enable", blk, re.IGNORECASE))
        port["root_guard"]  = bool(re.search(r"spanning-tree guard root", blk, re.IGNORECASE))

output["spanning_tree"] = {
    "mode":          stp_mode,
    "root_bridge":   is_root,
    "root_priority": root_priority,
    "root_address":  root_address,
    "ports":         stp_ports,
}


# ── logging_targets (from running-config) ─────────────────────────────────────

output["logging_targets"] = []
for m in re.finditer(r"^logging\s+([\d.]+|[\w.-]+)\s*(?:transport\s+(\w+))?\s*(?:port\s+(\d+))?", running, re.MULTILINE):
    host    = m.group(1)
    proto   = (m.group(2) or "udp").lower()
    port    = m.group(3) or "514"
    if proto not in ("udp", "tcp", "tls"):
        proto = "udp"
    output["logging_targets"].append({
        "type":        "syslog",
        "destination": "{}:{}".format(host, port),
        "protocol":    proto,
        "enabled":     True,
    })


# ── vpn_tunnels (IPsec from show crypto ipsec sa) ────────────────────────────

ipsec_raw = sections.get("crypto_ipsec", "")
isakmp_raw = sections.get("crypto_isakmp", "")

output["vpn_tunnels"] = []
# ISAKMP SA: "dst             src             state          conn-id status"
for m in re.finditer(
    r"^([\d.]+)\s+([\d.]+)\s+(\S+)\s+\d+\s+(\S+)",
    isakmp_raw, re.MULTILINE
):
    dst, src, state, status = m.group(1), m.group(2), m.group(3), m.group(4)
    up = status.upper() == "ACTIVE" or state.upper() == "QM_IDLE"
    output["vpn_tunnels"].append({
        "name":           "ipsec-{}-{}".format(src, dst),
        "type":           "ipsec",
        "local_address":  src,
        "remote_address": dst,
        "status":         "up" if up else "down",
        "cipher_suite":   "",
        "auth_method":    "pre-shared-key",
    })


# ── firewall_rules (from ACLs applied to interfaces) ─────────────────────────

output["firewall_rules"] = []
for acl in output.get("acls", []):
    for entry in acl.get("entries", []):
        action = entry.get("action", "")
        if action == "remark":
            continue
        output["firewall_rules"].append({
            "chain":       acl["name"],
            "direction":   "in",
            "action":      action,
            "protocol":    entry.get("protocol", "ip"),
            "source":      entry.get("source", "any"),
            "destination": entry.get("destination", "any"),
            "port":        "",
            "enabled":     True,
            "description": entry.get("description", ""),
            "source_tool": "ios-acl",
        })
