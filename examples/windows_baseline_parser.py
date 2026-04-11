# Windows Baseline Parser
# Parses output from windows_baseline_collector.ps1 into the canonical schema.
#
# `result` — raw string output from the collector
# `output` — canonical dict to populate (pre-filled with empty structure)

import re

SEP = "---ISOTOPEIQ---"

# ── Split raw output into named sections ─────────────────────────────────────

sections = {}
current = None
buf = []

for line in result.splitlines():
    line = line.rstrip("\r")
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


def kv(section):
    """Parse key=value lines from a section into a dict."""
    out = {}
    for line in lines(section):
        if "=" in line:
            k, _, v = line.partition("=")
            out[k.strip()] = v.strip()
    return out


# ── device ───────────────────────────────────────────────────────────────────

d = kv("device")
output["device"]["hostname"]    = d.get("hostname", "")
output["device"]["fqdn"]        = d.get("fqdn", "")
output["device"]["device_type"] = d.get("device_type", "server")
output["device"]["vendor"]      = d.get("vendor", "")
output["device"]["model"]       = d.get("model", "")


# ── hardware ─────────────────────────────────────────────────────────────────

h = kv("hardware")

output["hardware"]["cpu_model"]  = h.get("cpu_model", "")
try:
    output["hardware"]["cpu_cores"] = int(h.get("cpu_cores", ""))
except (ValueError, TypeError):
    output["hardware"]["cpu_cores"] = None
try:
    output["hardware"]["memory_gb"] = float(h.get("memory_gb", ""))
except (ValueError, TypeError):
    output["hardware"]["memory_gb"] = None
output["hardware"]["bios_version"]  = h.get("bios_version", "")
output["hardware"]["serial_number"] = h.get("serial_number", "")
output["hardware"]["architecture"]  = h.get("architecture", "")

virt_raw = h.get("virtualization_type", "none").lower()
virt_map = {
    "none": "bare-metal", "bare-metal": "bare-metal",
    "vmware": "vmware", "hyperv": "hyperv", "hyper-v": "hyperv",
    "virtualbox": "virtualbox", "kvm": "kvm", "xen": "xen",
    "virtual": "other",
}
output["hardware"]["virtualization_type"] = virt_map.get(virt_raw, "other")


# ── os ───────────────────────────────────────────────────────────────────────

o = kv("os")
output["os"]["name"]     = o.get("name", "")
output["os"]["version"]  = o.get("version", "")
output["os"]["build"]    = o.get("build", "")
output["os"]["kernel"]   = o.get("kernel", o.get("version", ""))
output["os"]["timezone"] = o.get("timezone", "")

ntp_raw = o.get("ntp_servers", "")
# Strip trailing ",0x..." flags from w32tm NTP server entries (e.g. "time.windows.com,0x9")
ntp_servers = [s.split(",")[0] for s in ntp_raw.split() if s] if ntp_raw else []
output["os"]["ntp_servers"] = ntp_servers

ntp_sync = o.get("ntp_synced", "").lower()
output["os"]["ntp_synced"] = True if ntp_sync == "true" else (False if ntp_sync == "false" else None)


# ── network — interfaces ─────────────────────────────────────────────────────

# Collector emits lines: ifAlias|IPAddress|PrefixLength|AddressFamily
# followed by ---MAC--- sentinel then: ifAlias|MACAddress[|InterfaceType[|Status]]
# Modern collectors (Windows 8+) emit the 4-field form with NDIS InterfaceType.

def _classify_iface_windows(name):
    nl = name.lower()
    if 'loopback' in nl:
        return 'loopback'
    if 'teredo' in nl or 'isatap' in nl or '6to4' in nl:
        return 'tunnel'
    if any(v in nl for v in ('vmware', 'virtualbox', 'hyper-v', 'virtual adapter')):
        return 'virtual'
    if 'wan miniport' in nl or 'kernel debug' in nl:
        return 'skip'
    return 'physical'

# NDIS InterfaceType enum  (NET_IF_TYPE from ifdef.h)
_WIN_IF_TYPE_MAP = {
    '6':   'physical',   # Ethernet
    '71':  'physical',   # IEEE 802.11 WiFi
    '24':  'loopback',   # Software Loopback
    '131': 'tunnel',     # Tunnel
    '53':  'tunnel',     # PPP
    '23':  'tunnel',     # PPP (alt)
    '157': 'virtual',    # NDIS virtual (802.3ad LAG)
}

_WIN_SKIP_TYPES = {'loopback', 'skip'}

iface_map = {}
mac_section = False

for line in lines("network"):
    if line.strip() == "---MAC---":
        mac_section = True
        continue
    parts = line.split("|")
    if not mac_section:
        if len(parts) < 4:
            continue
        alias    = parts[0].strip()
        ip_addr  = parts[1].strip()
        prefix   = parts[2].strip()
        family   = parts[3].strip().upper()
        if not alias or not ip_addr or ip_addr in ("", "::1", "127.0.0.1"):
            continue
        if alias not in iface_map:
            iface_map[alias] = {
                "name": alias, "mac": "", "description": "",
                "ipv4": [], "ipv6": [],
                "admin_status": "unknown", "oper_status": "unknown",
                "speed": "", "duplex": "unknown", "mtu": None,
                "port_mode": "routed", "access_vlan": None, "trunk_vlans": "",
                "interface_type": _classify_iface_windows(alias),
            }
        cidr = f"{ip_addr}/{prefix}" if prefix else ip_addr
        if family in ("IPV4", "INET", "2"):  # AddressFamily 2 = IPv4 in .NET
            iface_map[alias]["ipv4"].append(cidr)
        else:
            iface_map[alias]["ipv6"].append(cidr)
    else:
        if len(parts) < 2:
            continue
        alias      = parts[0].strip()
        mac        = parts[1].strip()
        # parts[2] = InterfaceType (numeric), parts[3] = Status — emitted by modern PS collector
        if_type_s  = parts[2].strip() if len(parts) > 2 else ''
        status_s   = parts[3].strip().lower() if len(parts) > 3 else ''

        # Resolve interface_type — NDIS enum beats name heuristic
        iface_type = _WIN_IF_TYPE_MAP.get(if_type_s) or _classify_iface_windows(alias)
        oper = 'up' if status_s in ('up', 'connected') else ('down' if status_s else 'unknown')

        if alias in iface_map:
            iface_map[alias]["mac"] = mac
            iface_map[alias]["interface_type"] = iface_type
            if oper != 'unknown':
                iface_map[alias]["admin_status"] = oper
                iface_map[alias]["oper_status"]  = oper
        else:
            iface_map[alias] = {
                "name": alias, "mac": mac, "description": "",
                "ipv4": [], "ipv6": [],
                "admin_status": oper, "oper_status": oper,
                "speed": "", "duplex": "unknown", "mtu": None,
                "port_mode": "routed", "access_vlan": None, "trunk_vlans": "",
                "interface_type": iface_type,
            }

output["network"]["interfaces"] = [
    i for i in iface_map.values()
    if i.get("interface_type") not in _WIN_SKIP_TYPES
]


# ── network — routes ─────────────────────────────────────────────────────────

def _parse_routes_windows(raw_lines):
    routes = []
    for line in raw_lines:
        parts = line.split("|")
        if len(parts) >= 3:
            # Pipe-delimited: DestinationPrefix|NextHop|InterfaceAlias|RouteMetric
            dest    = parts[0].strip()
            gw      = parts[1].strip()
            iface   = parts[2].strip()
            metric  = None
            if len(parts) > 3:
                try:
                    metric = int(parts[3].strip())
                except ValueError:
                    pass
            routes.append({"destination": dest, "gateway": gw, "interface": iface, "metric": metric})
        else:
            # Fallback: route print text — columns: Network Destination Netmask Gateway Interface Metric
            m = re.match(r"\s*(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\d+)", line)
            if m:
                dest_raw, mask, gw, iface, metric_s = m.groups()
                try:
                    prefix = sum(bin(int(o)).count("1") for o in mask.split("."))
                    dest = f"{dest_raw}/{prefix}"
                except Exception:
                    dest = dest_raw
                try:
                    metric = int(metric_s)
                except ValueError:
                    metric = None
                routes.append({"destination": dest, "gateway": gw, "interface": iface, "metric": metric})
    return routes

output["network"]["routes"] = _parse_routes_windows(lines("network_routes"))

# Default gateway
for r in output["network"]["routes"]:
    if r.get("destination") in ("0.0.0.0/0", "0.0.0.0", "default"):
        output["network"]["default_gateway"] = r.get("gateway", "")
        break


# ── network — DNS ────────────────────────────────────────────────────────────

output["network"]["dns_servers"] = lines("network_dns")


# ── network — hosts file ─────────────────────────────────────────────────────

hosts = []
for line in lines("network_hosts"):
    if line.startswith("#"):
        continue
    parts = line.split()
    if len(parts) >= 2:
        hosts.append({"ip": parts[0], "hostname": parts[1]})
output["network"]["hosts_file"] = hosts


# ── users ────────────────────────────────────────────────────────────────────

# Format: username|SID|homedir|shell|groups|password_last_set|last_logon|is_admin
for line in lines("users"):
    parts = line.split("|")
    if len(parts) < 2:
        continue
    uname    = parts[0].strip()
    sid      = parts[1].strip()
    homedir  = parts[2].strip() if len(parts) > 2 else ""
    shell    = parts[3].strip() if len(parts) > 3 else ""
    groups   = [g.strip() for g in parts[4].split(",") if g.strip()] if len(parts) > 4 else []
    pwd_last = parts[5].strip() if len(parts) > 5 else ""
    last_log = parts[6].strip() if len(parts) > 6 else ""
    is_admin = parts[7].strip().lower() if len(parts) > 7 else "false"
    output["users"].append({
        "username":          uname,
        "uid":               sid,
        "groups":            groups,
        "home":              homedir,
        "shell":             shell,
        "disabled":          None,
        "password_last_set": pwd_last,
        "last_login":        last_log,
        "sudo_privileges":   "Administrators" if is_admin == "true" else "",
    })


# ── groups ───────────────────────────────────────────────────────────────────

# Format: groupname|SID|members
for line in lines("groups"):
    parts = line.split("|")
    if len(parts) < 1 or not parts[0].strip():
        continue
    gname   = parts[0].strip()
    gid     = parts[1].strip() if len(parts) > 1 else ""
    members = [m.strip() for m in parts[2].split(",") if m.strip()] if len(parts) > 2 else []
    output["groups"].append({"group_name": gname, "gid": gid, "members": members})


# ── packages ─────────────────────────────────────────────────────────────────

# Format: name|version|publisher|install_date
for line in lines("packages"):
    parts = line.split("|")
    if not parts[0].strip():
        continue
    output["packages"].append({
        "name":         parts[0].strip(),
        "version":      parts[1].strip() if len(parts) > 1 else "",
        "vendor":       parts[2].strip() if len(parts) > 2 else "",
        "install_date": parts[3].strip() if len(parts) > 3 else "",
        "source":       "msi",
    })


# ── services ─────────────────────────────────────────────────────────────────

# Format: name|status|starttype
status_map  = {"running": "running", "stopped": "stopped"}
startup_map = {"auto": "enabled", "automatic": "enabled", "manual": "manual",
               "disabled": "disabled", "boot": "enabled", "system": "enabled"}

for line in lines("services"):
    parts = line.split("|")
    if not parts[0].strip():
        continue
    name       = parts[0].strip()
    status_raw = parts[1].strip().lower() if len(parts) > 1 else ""
    start_raw  = parts[2].strip().lower() if len(parts) > 2 else ""
    output["services"].append({
        "name":    name,
        "status":  status_map.get(status_raw, "unknown"),
        "startup": startup_map.get(start_raw, "unknown"),
    })


# ── filesystem ───────────────────────────────────────────────────────────────

# Format: drive|fstype|size_gb|free_gb
for line in lines("filesystem"):
    parts = line.split("|")
    if not parts[0].strip():
        continue
    drive   = parts[0].strip()
    fstype  = parts[1].strip() if len(parts) > 1 else ""
    try:
        size_gb = float(parts[2].strip()) if len(parts) > 2 else None
    except ValueError:
        size_gb = None
    try:
        free_gb = float(parts[3].strip()) if len(parts) > 3 else None
    except ValueError:
        free_gb = None
    output["filesystem"].append({
        "mount":         drive,
        "type":          fstype,
        "size_gb":       size_gb,
        "free_gb":       free_gb,
        "mount_options": [],
        "suid_files":    [],
    })


# ── security ─────────────────────────────────────────────────────────────────

sec = kv("security")

# UAC
uac_raw = sec.get("uac_enabled", "").lower()
output["security"]["uac_enabled"] = True if uac_raw == "true" else (False if uac_raw == "false" else None)

# Defender / AV
defender_raw = sec.get("defender_enabled", "").lower()
output["security"]["defender_enabled"] = True if defender_raw == "true" else (False if defender_raw == "false" else None)
output["security"]["antivirus"] = sec.get("antivirus", "")

# Firewall — any profile enabled counts
fw_raw = sec.get("firewall_enabled", "").lower()
output["security"]["firewall_enabled"] = True if fw_raw == "true" else (False if fw_raw == "false" else None)

# Secure boot
sb_raw = sec.get("secure_boot", "").lower()
output["security"]["secure_boot"] = True if sb_raw == "true" else (False if sb_raw == "false" else None)

# Audit logging — present if auditpol returned something
audit_raw = sec.get("audit_logging_enabled", "").lower()
output["security"]["audit_logging_enabled"] = True if audit_raw == "true" else False

# Password policy from net accounts
policy = {}
min_len = sec.get("password_min_length", "")
max_age = sec.get("password_max_age", "")
if min_len:
    try:
        policy["min_length"] = int(min_len)
    except ValueError:
        pass
if max_age and max_age.lower() not in ("unlimited", "never"):
    try:
        policy["max_age_days"] = int(max_age)
    except ValueError:
        pass
if policy:
    output["security"]["password_policy"] = policy


# ── scheduled_tasks ──────────────────────────────────────────────────────────

# Format: windows-task-scheduler|username|taskname|schedule|command|enabled
output["scheduled_tasks"] = []
for line in lines("scheduled_tasks"):
    parts = line.split("|", 5)
    if len(parts) < 3:
        continue
    task_type = parts[0].strip()
    user      = parts[1].strip()
    name      = parts[2].strip()
    schedule  = parts[3].strip() if len(parts) > 3 else ""
    command   = parts[4].strip() if len(parts) > 4 else ""
    enabled_s = parts[5].strip().lower() if len(parts) > 5 else "true"
    enabled   = enabled_s not in ("false", "0", "disabled")
    output["scheduled_tasks"].append({
        "name":     name,
        "type":     task_type,
        "command":  command,
        "schedule": schedule,
        "user":     user,
        "enabled":  enabled,
    })


# ── ssh_keys ─────────────────────────────────────────────────────────────────

output["ssh_keys"] = []
for line in lines("ssh_keys"):
    if "|" not in line:
        continue
    idx   = line.index("|")
    uname = line[:idx]
    key_line = line[idx + 1:]
    parts = key_line.split(None, 2)
    if len(parts) < 2:
        continue
    output["ssh_keys"].append({
        "username":   uname,
        "key_type":   parts[0],
        "public_key": parts[1],
        "comment":    parts[2] if len(parts) > 2 else "",
    })


# ── kernel_modules (Windows drivers) ─────────────────────────────────────────

# Format: name|state|startmode|pathname
output["kernel_modules"] = []
for line in lines("kernel_modules"):
    parts = line.split("|")
    if not parts[0].strip():
        continue
    output["kernel_modules"].append({
        "name":        parts[0].strip(),
        "type":        "driver",
        "description": "",
        "path":        parts[3].strip() if len(parts) > 3 else "",
        "hash":        "",
        "signed":      None,
    })


# ── listening_services ───────────────────────────────────────────────────────

# netstat -ano output:
#   Proto  Local Address     Foreign Address    State     PID
#   TCP    0.0.0.0:135       0.0.0.0:0          LISTENING 1234
#   UDP    0.0.0.0:500       *:*                           5678

output["listening_services"] = []
proto_map = {"tcp": "tcp", "tcp6": "tcp6", "udp": "udp", "udp6": "udp6"}

for line in lines("listening_services"):
    line = line.strip()
    if not line or line.lower().startswith("proto") or line.lower().startswith("active"):
        continue
    parts = line.split()
    if len(parts) < 3:
        continue
    proto_raw = parts[0].lower()
    if proto_raw not in proto_map:
        continue
    proto = proto_map[proto_raw]
    local = parts[1]
    state = parts[3].upper() if len(parts) > 3 else ""

    # TCP: only LISTENING; UDP: all entries are effectively listening
    if proto in ("tcp", "tcp6") and state != "LISTENING":
        continue

    # Extract address and port from local address (handles IPv6 [::]:port)
    if local.startswith("["):
        m = re.match(r"\[(.+)\]:(\d+)", local)
        if not m:
            continue
        local_addr, port_s = m.group(1), m.group(2)
    else:
        local_addr, _, port_s = local.rpartition(":")

    try:
        port = int(port_s)
    except ValueError:
        continue

    pid = None
    pid_s = parts[-1] if len(parts) >= 4 else ""
    try:
        pid = int(pid_s)
    except ValueError:
        pass

    output["listening_services"].append({
        "protocol":      proto,
        "local_address": local_addr,
        "port":          port,
        "process_name":  "",
        "pid":           pid,
        "user":          "",
    })
    output["network"]["open_ports"].append(port)


# ── firewall_rules ───────────────────────────────────────────────────────────

# Parse netsh advfirewall firewall show rule name=all verbose output.
# Rules are separated by lines of dashes. Each rule has key: value pairs.

output["firewall_rules"] = []

direction_map = {"in": "in", "inbound": "in", "out": "out", "outbound": "out"}
action_map    = {"allow": "allow", "block": "block", "bypass": "allow"}

rule_buf = {}
def _flush_fw(buf):
    # Rule name key differs by collection method:
    #   PS1 modern (Get-NetFirewallRule): "rulename" (from "RuleName:")
    #   netsh advfirewall verbose:        "rule_name" (from "Rule Name:")
    rule_name = buf.get("rulename") or buf.get("rule_name", "")
    if not rule_name:
        return
    direction_raw = buf.get("direction", "").lower()
    action_raw    = buf.get("action", "").lower()
    enabled_raw   = buf.get("enabled", "yes").lower()
    # source key also differs: "remoteaddress" (modern) vs "remoteip" (netsh)
    source = buf.get("remoteaddress") or buf.get("remoteip", "any")
    output["firewall_rules"].append({
        "chain":       rule_name,
        "direction":   direction_map.get(direction_raw, "unknown"),
        "action":      action_map.get(action_raw, action_raw),
        "protocol":    buf.get("protocol", "any"),
        "source":      source,
        "destination": buf.get("localip", "any"),
        "port":        buf.get("localport", ""),
        "enabled":     enabled_raw in ("yes", "true"),
        "description": buf.get("description", ""),
        "source_tool": "windows-firewall",
    })

for line in lines("firewall_rules"):
    line = line.strip()
    if re.match(r"^-{3,}$", line):
        _flush_fw(rule_buf)
        rule_buf = {}
        continue
    if ":" in line:
        k, _, v = line.partition(":")
        rule_buf[k.strip().lower().replace(" ", "_")] = v.strip()

_flush_fw(rule_buf)


# ── sysctl (Windows registry security settings) ──────────────────────────────

output["sysctl"] = []
for line in lines("sysctl"):
    if "=" not in line:
        continue
    k, _, v = line.partition("=")
    output["sysctl"].append({"key": k.strip(), "value": v.strip()})


# ── startup_items ────────────────────────────────────────────────────────────

# Format: name|type|command|location|user
output["startup_items"] = []
for line in lines("startup_items"):
    parts = line.split("|", 4)
    if not parts[0].strip():
        continue
    output["startup_items"].append({
        "name":    parts[0].strip(),
        "type":    parts[1].strip() if len(parts) > 1 else "other",
        "command": parts[2].strip() if len(parts) > 2 else "",
        "path":    parts[3].strip() if len(parts) > 3 else "",
        "enabled": True,
    })


# ── certificates ─────────────────────────────────────────────────────────────

# Format: subject|issuer|thumbprint|serial|not_before|not_after|store
output["certificates"] = []
for line in lines("certificates"):
    parts = line.split("|", 6)
    if len(parts) < 3 or not parts[2].strip():  # thumbprint required
        continue
    output["certificates"].append({
        "subject":    parts[0].strip(),
        "issuer":     parts[1].strip(),
        "thumbprint": parts[2].strip(),
        "serial":     parts[3].strip() if len(parts) > 3 else "",
        "not_before": parts[4].strip() if len(parts) > 4 else "",
        "not_after":  parts[5].strip() if len(parts) > 5 else "",
        "store":      parts[6].strip() if len(parts) > 6 else "",
    })


# ── logging_targets ──────────────────────────────────────────────────────────

output["logging_targets"] = []
for line in lines("logging_targets"):
    line = line.strip()
    if not line:
        continue
    # Determine protocol from URL scheme
    if re.match(r"https?://", line, re.IGNORECASE):
        proto = "tcp"
    else:
        proto = "unknown"
    output["logging_targets"].append({
        "type":        "windows-event-forwarding",
        "destination": line,
        "protocol":    proto,
        "enabled":     True,
    })


# ── pci_devices ──────────────────────────────────────────────────────────────
# Format: slot|class|vendor|device  (pipe-separated, from Win32_PnPEntity PCI\*)

output["pci_devices"] = []
for line in lines("pci_devices"):
    parts = [p.strip() for p in line.split("|")]
    slot = parts[0] if parts else ""
    if not slot:
        continue
    entry = {"slot": slot}
    if len(parts) > 1 and parts[1]: entry["class"]  = parts[1]
    if len(parts) > 2 and parts[2]: entry["vendor"] = parts[2]
    if len(parts) > 3 and parts[3]: entry["device"] = parts[3]
    output["pci_devices"].append(entry)


# ── storage_devices ──────────────────────────────────────────────────────────
# Format: type|name|model|vendor|size|serial|interface|removable

output["storage_devices"] = []
for line in lines("storage_devices"):
    parts = [p.strip() for p in line.split("|")]
    if len(parts) < 2 or not parts[1]:
        continue
    dev_type = parts[0] if parts[0] else "disk"
    name     = parts[1]
    entry = {"name": name, "type": dev_type}
    if len(parts) > 2 and parts[2]: entry["model"]     = parts[2]
    if len(parts) > 3 and parts[3]: entry["vendor"]    = parts[3]
    if len(parts) > 4 and parts[4]: entry["size"]      = parts[4]
    if len(parts) > 5 and parts[5]: entry["serial"]    = parts[5]
    if len(parts) > 6 and parts[6]: entry["interface"] = parts[6]
    if len(parts) > 7:              entry["removable"]  = parts[7] == "1"
    output["storage_devices"].append(entry)


# ── usb_devices ──────────────────────────────────────────────────────────────
# Format: bus_id|vendor_id|product_id|manufacturer|product

output["usb_devices"] = []
for line in lines("usb_devices"):
    parts = [p.strip() for p in line.split("|")]
    bus_id = parts[0] if parts else ""
    if not bus_id:
        continue
    entry = {"bus_id": bus_id}
    if len(parts) > 1 and parts[1]: entry["vendor_id"]    = parts[1]
    if len(parts) > 2 and parts[2]: entry["product_id"]   = parts[2]
    if len(parts) > 3 and parts[3]: entry["manufacturer"] = parts[3]
    if len(parts) > 4 and parts[4]: entry["product"]      = parts[4]
    output["usb_devices"].append(entry)
