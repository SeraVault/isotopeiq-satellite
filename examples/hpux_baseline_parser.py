# HP-UX Baseline Parser
# Parses output from hpux_baseline_collector.sh into the canonical schema.
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


# ── device ────────────────────────────────────────────────────────────────────

dev_lines = lines("device")
output["device"]["hostname"]    = dev_lines[0] if len(dev_lines) > 0 else ""
output["device"]["fqdn"]        = dev_lines[1] if len(dev_lines) > 1 else ""
output["device"]["device_type"] = dev_lines[2] if len(dev_lines) > 2 else "server"
output["device"]["vendor"]      = dev_lines[3] if len(dev_lines) > 3 else "HP"
output["device"]["model"]       = dev_lines[4] if len(dev_lines) > 4 else ""


# ── hardware ──────────────────────────────────────────────────────────────────

hw_lines = lines("hardware")
output["hardware"]["cpu_model"] = hw_lines[0] if len(hw_lines) > 0 else ""
try:
    output["hardware"]["cpu_cores"] = int(hw_lines[1]) if len(hw_lines) > 1 else None
except ValueError:
    output["hardware"]["cpu_cores"] = None
try:
    output["hardware"]["memory_gb"] = float(hw_lines[2]) if len(hw_lines) > 2 else None
except ValueError:
    output["hardware"]["memory_gb"] = None
output["hardware"]["bios_version"]  = hw_lines[3] if len(hw_lines) > 3 else ""
output["hardware"]["serial_number"] = hw_lines[4] if len(hw_lines) > 4 else ""
output["hardware"]["architecture"]  = hw_lines[5] if len(hw_lines) > 5 else ""

virt_raw = hw_lines[6].lower().strip() if len(hw_lines) > 6 else "bare-metal"
virt_map = {
    "bare-metal": "bare-metal",
    "none":       "bare-metal",
    "hpvm":       "other",       # HP Integrity Virtual Machine
    "vmware":     "vmware",
    "hyperv":     "hyperv",
    "kvm":        "kvm",
    "xen":        "xen",
    "other":      "other",
}
output["hardware"]["virtualization_type"] = virt_map.get(virt_raw, "other")


# ── os ────────────────────────────────────────────────────────────────────────

os_lines = lines("os")
output["os"]["name"]     = os_lines[0] if len(os_lines) > 0 else "HP-UX"
output["os"]["version"]  = os_lines[1] if len(os_lines) > 1 else ""
output["os"]["build"]    = os_lines[2] if len(os_lines) > 2 else ""
output["os"]["kernel"]   = os_lines[3] if len(os_lines) > 3 else ""
output["os"]["timezone"] = os_lines[4] if len(os_lines) > 4 else ""

ntp_raw = os_lines[5].strip() if len(os_lines) > 5 else ""
output["os"]["ntp_servers"] = [s for s in ntp_raw.split() if s] if ntp_raw else []

ntp_sync = os_lines[6].strip().lower() if len(os_lines) > 6 else "unknown"
output["os"]["ntp_synced"] = True if ntp_sync == "yes" else (False if ntp_sync == "no" else None)


# ── network — interfaces ──────────────────────────────────────────────────────
#
# HP-UX ifconfig -a output example:
#   lan0: flags=843<UP,BROADCAST,RUNNING,MULTICAST>
#          inet 10.0.0.5 netmask ffffff00 broadcast 10.0.0.255
#   lo0: flags=849<UP,LOOPBACK,RUNNING,MULTICAST>
#          inet 127.0.0.1 netmask ff000000

def _parse_hpux_ifconfig(raw):
    ifaces = []
    current_iface = None
    for line in raw.splitlines():
        # New interface block — starts at column 0 with "name: flags=..."
        m = re.match(r'^(\S+):\s+flags=\w+<([^>]*)>', line)
        if m:
            if current_iface:
                ifaces.append(current_iface)
            name = m.group(1)
            flag_str = m.group(2)
            flags = [f.strip() for f in flag_str.split(",")]
            admin = "up" if "UP" in flags else "down"
            oper  = "up" if "RUNNING" in flags else "down"
            current_iface = {
                "name":         name,
                "description":  "",
                "mac":          "",
                "ipv4":         [],
                "ipv6":         [],
                "admin_status": admin,
                "oper_status":  oper,
                "mtu":          None,
                "port_mode":    "routed",
                "duplex":       "unknown",
            }
            continue
        if current_iface is None:
            continue
        # inet line: inet <addr> netmask <mask>
        m_inet = re.match(r'^\s+inet\s+(\S+)\s+netmask\s+(\S+)', line)
        if m_inet:
            addr = m_inet.group(1)
            mask_hex = m_inet.group(2)
            # Convert hex netmask (e.g. ffffff00) to prefix length
            try:
                mask_int = int(mask_hex.replace("0x", ""), 16)
                prefix = bin(mask_int).count("1")
            except ValueError:
                prefix = 32
            current_iface["ipv4"].append(f"{addr}/{prefix}")
            continue
        # inet6 line: inet6 <addr>/<prefix>
        m_inet6 = re.match(r'^\s+inet6\s+(\S+)', line)
        if m_inet6:
            current_iface["ipv6"].append(m_inet6.group(1))
            continue
        # ether / link — MAC address
        m_ether = re.match(r'^\s+ether\s+(\S+)', line)
        if m_ether:
            current_iface["mac"] = m_ether.group(1)
            continue
        # MTU on some HP-UX versions appears inline with flags as "mtu <n>"
        m_mtu = re.search(r'\bmtu\s+(\d+)', line, re.IGNORECASE)
        if m_mtu:
            try:
                current_iface["mtu"] = int(m_mtu.group(1))
            except ValueError:
                pass
    if current_iface:
        ifaces.append(current_iface)
    return ifaces

output["network"]["interfaces"] = _parse_hpux_ifconfig(sections.get("network_interfaces", ""))


# ── network — routes ──────────────────────────────────────────────────────────
#
# HP-UX netstat -rn output:
# Routing tables
#                  Dest/Nexthop    Flags  Refs   Use    Interface  Pmtu
# ---------------------- ... -----
# 0.0.0.0            10.0.0.1       UG      0     ...    lan0       -

def _parse_hpux_routes(raw):
    routes = []
    for line in raw.splitlines():
        line = line.strip()
        # Skip headers and separator lines
        if not line or line.startswith("Routing") or line.startswith("---") \
                or line.startswith("Dest") or line.startswith("Net"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        dst = parts[0]
        gw  = parts[1]
        iface = parts[5] if len(parts) > 5 else ""
        # Skip purely local / loopback clutter where gateway == destination
        routes.append({
            "destination": dst,
            "gateway":     gw,
            "interface":   iface,
            "metric":      None,
        })
    return routes

output["network"]["routes"] = _parse_hpux_routes(sections.get("network_routes", ""))

# Default gateway
for r in output["network"]["routes"]:
    if r.get("destination") in ("default", "0.0.0.0"):
        output["network"]["default_gateway"] = r.get("gateway", "")
        break


# ── network — DNS ─────────────────────────────────────────────────────────────

output["network"]["dns_servers"] = lines("network_dns")


# ── network — hosts file ──────────────────────────────────────────────────────

hosts = []
for line in lines("network_hosts"):
    parts = line.split()
    if len(parts) >= 2:
        hosts.append({"ip": parts[0], "hostname": parts[1]})
output["network"]["hosts_file"] = hosts


# ── users ─────────────────────────────────────────────────────────────────────

for line in lines("users"):
    parts = line.split("|")
    if len(parts) < 4:
        continue
    uname, uid, home, shell = parts[0], parts[1], parts[2], parts[3]
    groups   = parts[4].split(",") if len(parts) > 4 and parts[4] else []
    pw_date  = parts[5].strip() if len(parts) > 5 else ""
    lastlog  = parts[6].strip() if len(parts) > 6 else ""
    sudo_cnt = parts[7].strip() if len(parts) > 7 else "0"
    try:
        disabled = int(uid) < 0
    except ValueError:
        disabled = None
    output["users"].append({
        "username":          uname,
        "uid":               uid,
        "groups":            [g for g in groups if g],
        "home":              home,
        "shell":             shell,
        "disabled":          disabled,
        "password_last_set": pw_date,
        "last_login":        lastlog,
        "sudo_privileges":   "sudo" if sudo_cnt.isdigit() and int(sudo_cnt) > 0 else "",
    })


# ── groups ────────────────────────────────────────────────────────────────────

for line in lines("groups"):
    parts = line.split("|")
    if len(parts) < 2:
        continue
    gname = parts[0]
    gid   = parts[1]
    members = [m for m in parts[2].split(",") if m] if len(parts) > 2 else []
    output["groups"].append({"group_name": gname, "gid": gid, "members": members})


# ── packages ──────────────────────────────────────────────────────────────────
#
# swlist -l product output (pipe-delimited by collector):
#   name|revision||install_date

for line in lines("packages"):
    parts = line.split("|")
    if not parts or not parts[0]:
        continue
    output["packages"].append({
        "name":         parts[0].strip(),
        "version":      parts[1].strip() if len(parts) > 1 else "",
        "vendor":       parts[2].strip() if len(parts) > 2 else "",
        "install_date": parts[3].strip() if len(parts) > 3 else "",
        "source":       "other",   # HP SD-UX — closest canonical value is "other"
    })


# ── services ──────────────────────────────────────────────────────────────────
#
# Collector emits: name|running|startup
# startup is one of: enabled | disabled | unknown

def _parse_hpux_services(raw):
    svcs = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("|")
        if len(parts) < 1:
            continue
        name    = parts[0].strip()
        status  = parts[1].strip().lower() if len(parts) > 1 else "unknown"
        startup = parts[2].strip().lower() if len(parts) > 2 else "unknown"
        if status not in ("running", "stopped"):
            status = "unknown"
        if startup not in ("enabled", "disabled", "manual"):
            startup = "unknown"
        svcs.append({"name": name, "status": status, "startup": startup})
    return svcs

output["services"] = _parse_hpux_services(sections.get("services", ""))


# ── filesystem ────────────────────────────────────────────────────────────────
#
# bdf output on HP-UX:
#   Filesystem          kbytes    used   avail %used Mounted on
#   /dev/vg00/lvol3     409600  198432  203168   49% /
# (Continuation lines may appear if the filesystem path is long.)

def _parse_bdf(raw):
    fs_list = []
    pending = None
    for line in raw.splitlines():
        line = line.rstrip()
        if not line:
            continue
        parts = line.split()
        # A line with only 1 token is a wrapped filesystem device name
        if len(parts) == 1:
            pending = parts[0]
            continue
        if pending:
            parts = [pending] + parts
            pending = None
        if len(parts) < 6:
            continue
        # parts: device kbytes used avail %used mountpoint
        device, kbytes_s, _used_s, avail_s, _pct, mountpoint = \
            parts[0], parts[1], parts[2], parts[3], parts[4], parts[5]
        try:
            size_gb = round(int(kbytes_s) / 1024 / 1024, 2)
            free_gb = round(int(avail_s)  / 1024 / 1024, 2)
        except ValueError:
            size_gb = free_gb = None
        fs_list.append({
            "mount":         mountpoint,
            "type":          "",         # bdf does not show fs type; filled from mnttab below
            "size_gb":       size_gb,
            "free_gb":       free_gb,
            "mount_options": [],
            "suid_files":    [],
        })
    return fs_list

output["filesystem"] = _parse_bdf(sections.get("filesystem", ""))

# Enrich from /etc/mnttab — format: device mountpoint fstype options freq passno
# HP-UX mnttab is whitespace-separated
mount_types   = {}   # mountpoint -> fstype
mount_options = {}   # mountpoint -> [options]
for line in lines("filesystem_mounts"):
    parts = line.split()
    if len(parts) >= 3:
        mountpoint = parts[1]
        fstype     = parts[2]
        options    = parts[3].split(",") if len(parts) > 3 else []
        mount_types[mountpoint]   = fstype
        mount_options[mountpoint] = options

for fs in output["filesystem"]:
    mp = fs["mount"]
    if mp in mount_types:
        fs["type"] = mount_types[mp]
    if mp in mount_options:
        fs["mount_options"] = mount_options[mp]

# SUID files — attach to the most specific matching mount point
suid_by_mount = {}
for path in lines("filesystem_suid"):
    best = ""
    for fs in output["filesystem"]:
        mp = fs["mount"]
        if path.startswith(mp) and len(mp) > len(best):
            best = mp
    if best:
        suid_by_mount.setdefault(best, []).append(path)

for fs in output["filesystem"]:
    fs["suid_files"] = suid_by_mount.get(fs["mount"], [])


# ── security ──────────────────────────────────────────────────────────────────
#
# Collector sections for security (in order):
#   1. getprdef -r output  (or "trusted_mode=enabled/disabled")
#   2. audsys -q output    (or "audit=unknown")
#   3. ipf -V / ipf presence line
#   4. swlist security patches (may span many lines)
#   5. getprdef password policy fields

sec_raw  = sections.get("security", "")
sec_lines_all = [l for l in sec_raw.splitlines() if l.strip()]

# --- Trusted mode (TCB / SELinux equivalent) ---
trusted_enabled = False
for sl in sec_lines_all:
    sl_l = sl.lower()
    # getprdef -r output includes "system_default" with "trusted" fields;
    # a simple heuristic: if "trusted" appears and not "not" before it
    if "trusted_mode=enabled" in sl_l:
        trusted_enabled = True
        break
    if re.search(r'\btrusted\b', sl_l) and "disabled" not in sl_l and "not" not in sl_l:
        trusted_enabled = True
        break

# Map TCB trusted mode → selinux_mode (closest canonical field)
output["security"]["selinux_mode"] = "enforcing" if trusted_enabled else "disabled"

# AppArmor is not applicable on HP-UX
output["security"]["apparmor_status"] = "disabled"

# --- Audit logging (audsys -q) ---
audit_enabled = False
for sl in sec_lines_all:
    sl_l = sl.lower()
    if "audit" in sl_l and ("running" in sl_l or "enabled" in sl_l or "on" in sl_l):
        audit_enabled = True
        break
    # audsys -q output may say "auditing is enabled"
    if re.search(r'auditing\s+is\s+on', sl_l):
        audit_enabled = True
        break
output["security"]["audit_logging_enabled"] = audit_enabled

# --- Firewall (IPFilter) ---
fw_enabled = False
for sl in sec_lines_all:
    sl_l = sl.lower()
    if "ipf=" in sl_l and "absent" not in sl_l:
        fw_enabled = True
        break
    if "ipfilter" in sl_l or "ip filter" in sl_l:
        fw_enabled = True
        break
output["security"]["firewall_enabled"] = fw_enabled

# Secure boot — not applicable on classic HP-UX hardware
output["security"]["secure_boot"] = None

# --- Password policy from getprdef fields ---
policy = {}
for sl in sec_lines_all:
    # getprdef output: one key=value per line or key = value
    m = re.search(r'minpwlen\s*[=:]\s*(\d+)', sl, re.IGNORECASE)
    if m:
        policy["min_length"] = int(m.group(1))
    m = re.search(r'u_exp\s*[=:]\s*(\d+)', sl, re.IGNORECASE)
    if m:
        policy["max_age_days"] = int(m.group(1))
    m = re.search(r'pw_expire\s*[=:]\s*(\d+)', sl, re.IGNORECASE)
    if m:
        policy.setdefault("max_age_days", int(m.group(1)))
    m = re.search(r'maxlogins\s*[=:]\s*(\d+)', sl, re.IGNORECASE)
    if m:
        policy["lockout_threshold"] = int(m.group(1))
    m = re.search(r'loginFailures\s*[=:]\s*(\d+)', sl, re.IGNORECASE)
    if m:
        policy.setdefault("lockout_threshold", int(m.group(1)))

if policy:
    output["security"]["password_policy"] = policy


# ── scheduled_tasks ───────────────────────────────────────────────────────────

output["scheduled_tasks"] = []
for line in lines("scheduled_tasks"):
    parts = line.split("|", 3)
    if len(parts) < 4:
        continue
    task_type, user, src, schedule_cmd = parts
    fields = schedule_cmd.split(None, 5)
    if len(fields) >= 6:
        schedule = " ".join(fields[:5])
        command  = fields[5]
    else:
        schedule = ""
        command  = schedule_cmd
    output["scheduled_tasks"].append({
        "name":     "{}:{}".format(src, command[:60]),
        "type":     task_type,
        "command":  command,
        "schedule": schedule,
        "user":     user,
        "enabled":  True,
    })


# ── ssh_keys ──────────────────────────────────────────────────────────────────

output["ssh_keys"] = []
for line in lines("ssh_keys"):
    if "|" not in line:
        continue
    idx = line.index("|")
    uname    = line[:idx]
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


# ── ssh_config ────────────────────────────────────────────────────────────────

ssh_cfg  = {}
bool_map = {"yes": True, "no": False}

for line in lines("ssh_config"):
    parts = line.split(None, 1)
    if len(parts) != 2:
        continue
    key, val = parts[0].lower(), parts[1].strip()
    if key == "port":
        try:
            ssh_cfg["port"] = int(val)
        except ValueError:
            pass
    elif key == "protocol":
        ssh_cfg["protocol"] = val
    elif key == "permitrootlogin":
        ssh_cfg["permit_root_login"] = val
    elif key == "passwordauthentication":
        ssh_cfg["password_authentication"] = bool_map.get(val.lower())
    elif key == "pubkeyauthentication":
        ssh_cfg["pubkey_authentication"] = bool_map.get(val.lower())
    elif key == "permitemptypasswords":
        ssh_cfg["permit_empty_passwords"] = bool_map.get(val.lower())
    elif key == "x11forwarding":
        ssh_cfg["x11_forwarding"] = bool_map.get(val.lower())
    elif key == "maxauthtries":
        try:
            ssh_cfg["max_auth_tries"] = int(val)
        except ValueError:
            pass
    elif key == "allowusers":
        ssh_cfg["allow_users"] = val.split()
    elif key == "denyusers":
        ssh_cfg["deny_users"] = val.split()
    elif key == "allowgroups":
        ssh_cfg["allow_groups"] = val.split()
    elif key == "denygroups":
        ssh_cfg["deny_groups"] = val.split()
    elif key == "usepam":
        ssh_cfg["use_pam"] = bool_map.get(val.lower())

if ssh_cfg:
    output["ssh_config"] = ssh_cfg


# ── kernel_modules ────────────────────────────────────────────────────────────
#
# kcmodule output (11.31):
#   Module              State      Unload  Description
#   -------             ------     ------  -----------
#   ccio               loaded          1  ... Hardware
#
# kmadmin -s output (older):
#   Module State  ...
#   inet   loaded
#
# We accept either format — capture the first token of each non-header line.

output["kernel_modules"] = []
for line in lines("kernel_modules"):
    if re.match(r'^[-=\s]+$', line):
        continue
    parts = line.split()
    if not parts:
        continue
    name = parts[0]
    # Skip header lines
    if name.lower() in ("module", "state", "name"):
        continue
    state = parts[1].lower() if len(parts) > 1 else ""
    desc  = " ".join(parts[3:]) if len(parts) > 3 else ""
    entry = {"name": name, "type": "kcmodule"}
    if desc:
        entry["description"] = desc
    output["kernel_modules"].append(entry)


# ── listening_services ────────────────────────────────────────────────────────
#
# netstat -an LISTEN lines on HP-UX:
#   tcp        0      0  0.0.0.0.22             0.0.0.0.0              LISTEN
# HP-UX uses dot notation: address.port (e.g. 0.0.0.0.22 → addr=0.0.0.0, port=22)
#
# lsof -i LISTEN lines:
#   sshd   1234 root   3u  IPv4  0xd...  0t0  TCP *:22 (LISTEN)

output["listening_services"] = []

def _dotaddr_to_ip_port(dotaddr):
    """Convert HP-UX dot-notation address (e.g. 0.0.0.0.22) to (ip, port)."""
    parts = dotaddr.rsplit(".", 1)
    if len(parts) == 2:
        try:
            return parts[0], int(parts[1])
        except ValueError:
            pass
    return dotaddr, None

for line in lines("listening_services"):
    line = line.strip()
    if not line:
        continue
    # lsof output: process pid user ... TCP addr:port (LISTEN)
    lsof_m = re.search(r'(\S+)\s+(\d+)\s+(\S+)\s+\S+\s+(IPv4|IPv6)\s+\S+\s+\S+\s+(TCP|UDP)\s+\S*:(\d+)\s+\(LISTEN\)', line)
    if lsof_m:
        proto_s = lsof_m.group(5).lower()
        port_s  = lsof_m.group(6)
        try:
            port = int(port_s)
        except ValueError:
            continue
        output["listening_services"].append({
            "protocol":      proto_s,
            "local_address": "",
            "port":          port,
            "process_name":  lsof_m.group(1),
            "pid":           int(lsof_m.group(2)),
            "user":          lsof_m.group(3),
        })
        output["network"]["open_ports"].append(port)
        continue
    # netstat -an LISTEN line
    parts = line.split()
    if len(parts) < 6:
        continue
    proto_raw = parts[0].lower()
    if proto_raw not in ("tcp", "tcp6", "udp", "udp6"):
        continue
    local_raw = parts[3]
    state     = parts[5].upper() if len(parts) > 5 else ""
    if state != "LISTEN":
        continue
    local_ip, port = _dotaddr_to_ip_port(local_raw)
    if port is None:
        continue
    output["listening_services"].append({
        "protocol":      proto_raw,
        "local_address": local_ip,
        "port":          port,
        "process_name":  "",
        "pid":           None,
        "user":          "",
    })
    output["network"]["open_ports"].append(port)


# ── firewall_rules ────────────────────────────────────────────────────────────
#
# ipfstat -io output (IPFilter):
#   Outgoing packet filtering rules:
#   pass out quick on lo0 all
#   pass out all
#   Incoming packet filtering rules:
#   block in all
#   pass in quick on lan0 proto tcp from any to any port = 22
#
# ipf.conf rules follow the same syntax.

output["firewall_rules"] = []

def _parse_ipf_rules(raw):
    rules = []
    direction = "both"
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        line_l = line.lower()
        # Section headers from ipfstat -io
        if "outgoing" in line_l and "filtering" in line_l:
            direction = "out"
            continue
        if "incoming" in line_l and "filtering" in line_l:
            direction = "in"
            continue
        # Rule lines start with "pass", "block", "log", "count", etc.
        parts = line_l.split()
        if not parts or parts[0] not in ("pass", "block", "log", "count", "skip", "return-rst"):
            continue
        action = parts[0]
        # Infer direction from rule keyword if present
        rule_dir = direction
        if "out" in parts[:3]:
            rule_dir = "out"
        elif "in" in parts[:3]:
            rule_dir = "in"
        # Protocol
        proto = "any"
        if "proto" in parts:
            idx = parts.index("proto")
            if idx + 1 < len(parts):
                proto = parts[idx + 1]
        # Source / destination
        src = "any"
        dst = "any"
        port_str = ""
        # "from X to Y port = P"
        m_src = re.search(r'\bfrom\s+(\S+)', line_l)
        m_dst = re.search(r'\bto\s+(\S+)', line_l)
        m_port = re.search(r'\bport\s*=\s*(\S+)', line_l)
        if m_src:
            src = m_src.group(1)
        if m_dst:
            dst = m_dst.group(1)
        if m_port:
            port_str = m_port.group(1)
        # Interface
        iface = ""
        if "on" in parts:
            idx = parts.index("on")
            if idx + 1 < len(parts):
                iface = parts[idx + 1]
        rules.append({
            "chain":       iface or "ipf",
            "direction":   rule_dir,
            "action":      "accept" if action == "pass" else ("drop" if action == "block" else action),
            "protocol":    proto,
            "source":      src,
            "destination": dst,
            "port":        port_str,
            "enabled":     True,
            "source_tool": "iptables",   # canonical value closest to IPFilter
        })
    return rules

fw_raw = sections.get("firewall_rules", "")
if fw_raw:
    output["firewall_rules"] = _parse_ipf_rules(fw_raw)


# ── sysctl (kctune / kmtune) ──────────────────────────────────────────────────
#
# kctune -v output (11.31):
#   Tunable                 Value      Expression  Dflags  Mflags  Description
#   executable_stack             0           0    ...
#
# kmtune output (older):
#   Parameter            Current  Dflags  Mflags  Description
#   maxuprc              512      ...
#
# We capture parameter name and value from the first two whitespace-separated
# tokens of each non-header, non-comment line.

output["sysctl"] = []
for line in lines("sysctl"):
    if re.match(r'^[-= \t]+$', line):
        continue
    parts = line.split()
    if len(parts) < 2:
        continue
    key = parts[0]
    # Skip header rows
    if key.lower() in ("tunable", "parameter", "name"):
        continue
    val = parts[1]
    output["sysctl"].append({"key": key, "value": val})


# ── logging_targets ───────────────────────────────────────────────────────────

output["logging_targets"] = []
for line in lines("logging_targets"):
    line = line.strip()
    if not line:
        continue
    # syslog.conf remote: facility.level  @host  or  @@host:port
    m = re.search(r'(@@?)([^\s:]+):?(\d+)?', line)
    if m:
        tcp  = m.group(1) == "@@"
        host = m.group(2)
        port = m.group(3) or "514"
        output["logging_targets"].append({
            "type":        "syslog",
            "destination": "{}:{}".format(host, port),
            "protocol":    "tcp" if tcp else "udp",
            "enabled":     True,
        })


# ── snmp ─────────────────────────────────────────────────────────────────────
#
# HP-UX SNMP agent config (snmpd.conf or SnmpAgent.d/snmpd.conf).
# Common directives:
#   community public  ro  0.0.0.0
#   community private rw  10.0.0.0/8
#   trap-dest 10.0.0.1
#   location "Server Room"
#   contact  "admin@example.com"
#   agentaddress udp:161

snmp_obj = {}
communities = []
trap_targets = []
versions_seen = set()

for line in lines("snmp"):
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    parts = line.split()
    key_l = parts[0].lower() if parts else ""

    if key_l == "community" and len(parts) >= 2:
        communities.append(parts[1])
        versions_seen.add("v2c")

    elif key_l in ("trap-dest", "trapdest", "trap_dest") and len(parts) >= 2:
        trap_targets.append(parts[1])

    elif key_l == "location":
        snmp_obj["location"] = " ".join(parts[1:]).strip('"')

    elif key_l == "contact":
        snmp_obj["contact"] = " ".join(parts[1:]).strip('"')

    elif key_l == "agentaddress" and len(parts) >= 2:
        # presence of agentaddress implies SNMP is enabled
        snmp_obj["enabled"] = True

    # SNMPv3 user lines in some HP configs:
    #   createUser authuser MD5 "passphrase" DES
    elif key_l == "createuser" and len(parts) >= 2:
        versions_seen.add("v3")
        v3_users = snmp_obj.setdefault("v3_users", [])
        v3_entry = {"username": parts[1]}
        if len(parts) > 2:
            v3_entry["auth_protocol"] = parts[2].upper()
        if len(parts) > 4:
            v3_entry["priv_protocol"] = parts[4].upper()
        v3_users.append(v3_entry)

if communities:
    snmp_obj["communities"] = communities
if trap_targets:
    snmp_obj["trap_targets"] = trap_targets
if versions_seen:
    snmp_obj["versions"] = sorted(versions_seen)
if "enabled" not in snmp_obj and (communities or trap_targets or versions_seen):
    snmp_obj["enabled"] = True

if snmp_obj:
    output["snmp"] = snmp_obj
