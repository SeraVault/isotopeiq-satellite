# macOS Baseline Parser
# Parses output from macos_baseline_collector.sh into the canonical schema.
#
# `result` — raw string output from the collector
# `output` — canonical dict to populate (pre-filled with empty structure)

import re
import hashlib

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
output["device"]["vendor"]      = dev_lines[3] if len(dev_lines) > 3 else "Apple"
# Lines 4 and 5 come from the awk block that prints model then serial
output["device"]["model"]       = dev_lines[4] if len(dev_lines) > 4 else ""


# ── hardware ──────────────────────────────────────────────────────────────────

hw_lines = lines("hardware")
output["hardware"]["cpu_model"] = hw_lines[0] if len(hw_lines) > 0 else ""

# Core count — may include annotation like "8 (4 performance and 4 efficiency)"
core_raw = hw_lines[1] if len(hw_lines) > 1 else ""
core_match = re.search(r"(\d+)", core_raw)
try:
    output["hardware"]["cpu_cores"] = int(core_match.group(1)) if core_match else None
except (ValueError, AttributeError):
    pass

# Memory — reported as bare number of GB (awk strips " GB" suffix)
try:
    output["hardware"]["memory_gb"] = float(hw_lines[2]) if len(hw_lines) > 2 else None
except ValueError:
    pass

output["hardware"]["bios_version"]  = hw_lines[3] if len(hw_lines) > 3 else ""
output["hardware"]["serial_number"] = hw_lines[4] if len(hw_lines) > 4 else ""
output["hardware"]["architecture"]  = hw_lines[5] if len(hw_lines) > 5 else ""

virt_raw = hw_lines[6].strip().lower() if len(hw_lines) > 6 else "bare-metal"
virt_map = {
    "bare-metal": "bare-metal",
    "vmware":     "vmware",
    "virtualbox": "virtualbox",
    "other":      "other",
}
output["hardware"]["virtualization_type"] = virt_map.get(virt_raw, "other")


# ── os ────────────────────────────────────────────────────────────────────────

os_lines = lines("os")
output["os"]["name"]     = os_lines[0] if len(os_lines) > 0 else "macOS"
output["os"]["version"]  = os_lines[1] if len(os_lines) > 1 else ""
output["os"]["build"]    = os_lines[2] if len(os_lines) > 2 else ""
output["os"]["kernel"]   = os_lines[3] if len(os_lines) > 3 else ""
output["os"]["timezone"] = os_lines[4].strip() if len(os_lines) > 4 else ""

ntp_raw = os_lines[5].strip() if len(os_lines) > 5 else ""
output["os"]["ntp_servers"] = [s for s in ntp_raw.split() if s] if ntp_raw else []

ntp_sync = os_lines[6].strip().lower() if len(os_lines) > 6 else "unknown"
output["os"]["ntp_synced"] = True if ntp_sync == "yes" else (False if ntp_sync == "no" else None)


# ── network — interfaces (ifconfig -a) ───────────────────────────────────────

iface_raw = sections.get("network_interfaces", "")

def _parse_ifconfig(raw):
    """Parse BSD ifconfig -a output into canonical interface dicts."""
    ifaces = []
    current_iface = None

    for line in raw.splitlines():
        # New interface block: "en0: flags=8863<UP,...> mtu 1500"
        m = re.match(r'^(\S+):\s+flags=(\S+)\s+mtu\s+(\d+)', line)
        if m:
            if current_iface is not None:
                ifaces.append(current_iface)
            name = m.group(1)
            flags_str = m.group(2)
            mtu = int(m.group(3))
            # flags field is hex<FLAGNAMES>
            flag_names = re.search(r'<([^>]*)>', flags_str)
            flag_list = flag_names.group(1).split(",") if flag_names else []
            admin_status = "up"   if "UP"      in flag_list else "down"
            oper_status  = "up"   if "RUNNING" in flag_list else "down"
            current_iface = {
                "name":         name,
                "mac":          "",
                "ipv4":         [],
                "ipv6":         [],
                "admin_status": admin_status,
                "oper_status":  oper_status,
                "mtu":          mtu,
                "port_mode":    "routed",
                "duplex":       "unknown",
            }
            continue

        if current_iface is None:
            continue

        # MAC address: "ether aa:bb:cc:dd:ee:ff"
        m = re.match(r'^\s+ether\s+([0-9a-f:]+)', line)
        if m:
            current_iface["mac"] = m.group(1)
            continue

        # IPv4: "inet 192.168.1.1 netmask 0xffffff00 broadcast ..."
        m = re.match(r'^\s+inet\s+(\d+\.\d+\.\d+\.\d+)\s+netmask\s+(\S+)', line)
        if m:
            ip = m.group(1)
            mask_hex = m.group(2)
            # Convert hex netmask to prefix length
            try:
                mask_int = int(mask_hex, 16)
                prefix = bin(mask_int).count("1")
            except ValueError:
                prefix = 32
            current_iface["ipv4"].append(f"{ip}/{prefix}")
            continue

        # IPv6: "inet6 fe80::1%lo0 prefixlen 64"
        m = re.match(r'^\s+inet6\s+(\S+)\s+prefixlen\s+(\d+)', line)
        if m:
            addr = m.group(1).split("%")[0]   # strip zone ID
            prefix = m.group(2)
            current_iface["ipv6"].append(f"{addr}/{prefix}")
            continue

    if current_iface is not None:
        ifaces.append(current_iface)

    return ifaces

output["network"]["interfaces"] = _parse_ifconfig(iface_raw)


# ── network — routes (netstat -rn) ────────────────────────────────────────────

route_raw = sections.get("network_routes", "")

def _parse_netstat_routes(raw):
    """Parse netstat -rn output into canonical route dicts."""
    routes = []
    in_table = False
    for line in raw.splitlines():
        line = line.strip()
        # Header line signals start of table
        if re.match(r'^Destination\s+Gateway', line):
            in_table = True
            continue
        if not in_table or not line:
            continue
        # Skip section headers like "Internet:" or "Internet6:"
        if re.match(r'^Internet', line):
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        destination = parts[0]
        gateway     = parts[1]
        # Interface is usually the last column; flags in the middle
        iface = ""
        # Typical columns: Destination Gateway Flags Refs Use Mtu Netif Expire
        # or:              Destination Gateway Flags Netif Expire
        # Netif is reliably non-numeric and looks like an interface name
        for p in reversed(parts[2:]):
            if re.match(r'^[a-z][a-z0-9]+\d*$', p) and not re.match(r'^\d+$', p):
                iface = p
                break
        # Convert host-only entries ("link#N" gateway) to empty string
        if gateway.startswith("link#"):
            gateway = ""
        routes.append({
            "destination": destination,
            "gateway":     gateway,
            "interface":   iface,
            "metric":      None,
        })
    return routes

output["network"]["routes"] = _parse_netstat_routes(route_raw)


# ── network — DNS (scutil --dns) ──────────────────────────────────────────────

dns_raw = sections.get("network_dns", "")
dns_servers = []
seen_dns = set()
for line in dns_raw.splitlines():
    m = re.search(r'nameserver\[\d+\]\s*:\s*(\S+)', line)
    if m:
        ns = m.group(1)
        if ns not in seen_dns:
            seen_dns.add(ns)
            dns_servers.append(ns)
output["network"]["dns_servers"] = dns_servers

# Default gateway from routes
for r in output["network"]["routes"]:
    if r.get("destination") in ("default", "0.0.0.0/0", "::/0"):
        if r.get("gateway") and not r["gateway"].startswith("link#"):
            output["network"]["default_gateway"] = r["gateway"]
            break


# ── users ─────────────────────────────────────────────────────────────────────

for line in lines("users"):
    parts = line.split("|")
    if len(parts) < 4:
        continue
    uname, uid, home, shell = parts[0], parts[1], parts[2], parts[3]
    groups       = [g for g in parts[4].split(",") if g] if len(parts) > 4 and parts[4] else []
    pw_last_set  = parts[5].strip() if len(parts) > 5 else ""
    last_login   = parts[6].strip() if len(parts) > 6 else ""
    admin_cnt    = parts[7].strip() if len(parts) > 7 else "0"
    try:
        uid_int  = int(uid)
        disabled = uid_int < 0
    except ValueError:
        disabled = None
    output["users"].append({
        "username":          uname,
        "uid":               uid,
        "groups":            groups,
        "home":              home,
        "shell":             shell,
        "disabled":          disabled,
        "password_last_set": pw_last_set,
        "last_login":        last_login,
        "sudo_privileges":   "sudo" if admin_cnt.isdigit() and int(admin_cnt) > 0 else "",
    })


# ── groups ────────────────────────────────────────────────────────────────────

for line in lines("groups"):
    parts = line.split("|")
    if len(parts) < 2:
        continue
    gname   = parts[0]
    gid     = parts[1]
    members = [m for m in parts[2].split(",") if m] if len(parts) > 2 else []
    output["groups"].append({"group_name": gname, "gid": gid, "members": members})


# ── packages ──────────────────────────────────────────────────────────────────

# Packages section contains two sources interleaved:
#   1. system_profiler lines: name|version|vendor|
#   2. pkgutil lines:         com.example.pkg|version||install_date
#   3. brew lines:            name|version||
# All share the same pipe-delimited format; we deduplicate by name+version.

_pkg_seen = set()

for line in lines("packages"):
    parts = line.split("|")
    if len(parts) < 1 or not parts[0].strip():
        continue
    name    = parts[0].strip()
    version = parts[1].strip() if len(parts) > 1 else ""
    vendor  = parts[2].strip() if len(parts) > 2 else ""
    install_date = parts[3].strip() if len(parts) > 3 else ""

    # Detect source by name pattern
    if re.match(r'^[a-z][a-z0-9.]+\.[a-z]', name):
        # Reverse-domain pkgutil identifier
        source = "other"
    elif vendor.lower() in ("homebrew", ""):
        source = "brew" if not vendor else "other"
    else:
        source = "other"

    key = (name, version)
    if key in _pkg_seen:
        continue
    _pkg_seen.add(key)

    output["packages"].append({
        "name":         name,
        "version":      version,
        "vendor":       vendor,
        "install_date": install_date,
        "source":       source,
    })


# ── services (launchctl list) ─────────────────────────────────────────────────

# launchctl list columns: PID  LastExitStatus  Label
# PID is "-" when not running.

output["services"] = []
for line in lines("services"):
    line = line.strip()
    if not line or line.startswith("PID"):
        continue
    parts = line.split(None, 2)
    if len(parts) < 3:
        continue
    pid_field, exit_status, label = parts[0], parts[1], parts[2]
    running = pid_field != "-" and pid_field.isdigit()
    status  = "running" if running else "stopped"
    # Treat exit status 0 as clean stop; non-zero suggests failure (still "stopped")
    output["services"].append({
        "name":    label,
        "status":  status,
        "startup": "unknown",   # launchctl list does not expose this reliably
    })


# ── filesystem (df -P -k) ─────────────────────────────────────────────────────

# df -P -k columns: Filesystem  1024-blocks  Used  Available  Capacity  Mounted-on
# macOS df -P does NOT include a Type column (unlike Linux df -P -T).
# We infer type from filesystem name prefix (devfs, /dev/diskXsY → apfs, etc.)

def _infer_fs_type(device):
    dev = device.lower()
    if dev.startswith("devfs"):
        return "devfs"
    if dev.startswith("map "):
        return "autofs"
    if dev.startswith("/dev/disk"):
        return "apfs"   # default assumption on modern macOS
    if dev.startswith("//") or dev.startswith("smb://"):
        return "smbfs"
    if dev.startswith("nfs:") or ":" in dev:
        return "nfs"
    return "other"

for line in lines("filesystem"):
    parts = line.split()
    if len(parts) < 6:
        continue
    device, blocks, used, avail, _cap, mount = (
        parts[0], parts[1], parts[2], parts[3], parts[4],
        parts[5] if len(parts) > 5 else parts[-1],
    )
    # For lines where mount path has spaces (rare but possible), rejoin
    if len(parts) > 6:
        mount = " ".join(parts[5:])
    fs_type = _infer_fs_type(device)
    try:
        size_gb = round(int(blocks) / 1024 / 1024, 2)
        free_gb = round(int(avail)  / 1024 / 1024, 2)
    except ValueError:
        size_gb = free_gb = None
    output["filesystem"].append({
        "mount":         mount,
        "type":          fs_type,
        "size_gb":       size_gb,
        "free_gb":       free_gb,
        "mount_options": [],
        "suid_files":    [],
    })

# SUID files — attach to the matching (deepest) mount point
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

# Collector emits these lines in order:
#   0: csrutil status     → SIP state
#   1: fdesetup status    → FileVault state
#   2: spctl --status     → Gatekeeper state
#   3: socketfilterfw ... → Application Firewall state
#   4: autologin user     → "disabled" or a username
#   5: MDM profile count
#   6: secure boot line

sec_lines = lines("security")

# SIP → selinux_mode field ("enforcing" = SIP enabled, "disabled" = SIP off)
sip_raw = sec_lines[0].lower() if len(sec_lines) > 0 else "unknown"
if "enabled" in sip_raw:
    output["security"]["selinux_mode"] = "enforcing"
elif "disabled" in sip_raw:
    output["security"]["selinux_mode"] = "disabled"
else:
    output["security"]["selinux_mode"] = "unknown"

# FileVault → secure_boot field (repurposed as per spec)
fv_raw = sec_lines[1].lower() if len(sec_lines) > 1 else "unknown"
if "on" in fv_raw or "enabled" in fv_raw:
    output["security"]["secure_boot"] = True
elif "off" in fv_raw or "disabled" in fv_raw or "not enabled" in fv_raw:
    output["security"]["secure_boot"] = False
else:
    output["security"]["secure_boot"] = None

# Gatekeeper → firewall_enabled (first pass; overridden by socket firewall below)
spctl_raw = sec_lines[2].lower() if len(sec_lines) > 2 else "unknown"
gatekeeper_enabled = "enabled" in spctl_raw or "assessments enabled" in spctl_raw

# Application Firewall socket state → firewall_enabled (takes precedence)
fw_sock_raw = sec_lines[3].lower() if len(sec_lines) > 3 else "unknown"
if "enabled" in fw_sock_raw or "is enabled" in fw_sock_raw:
    output["security"]["firewall_enabled"] = True
elif "disabled" in fw_sock_raw or "is disabled" in fw_sock_raw:
    output["security"]["firewall_enabled"] = False
else:
    # Fall back to Gatekeeper state as a proxy
    output["security"]["firewall_enabled"] = gatekeeper_enabled if gatekeeper_enabled else None

# AppArmor is a Linux concept; report as disabled on macOS
output["security"]["apparmor_status"] = "disabled"

# Audit logging — macOS uses the BSM audit framework; assume active if running
output["security"]["audit_logging_enabled"] = None


# ── scheduled_tasks ───────────────────────────────────────────────────────────

output["scheduled_tasks"] = []
for line in lines("scheduled_tasks"):
    parts = line.split("|", 3)
    if len(parts) < 3:
        continue
    source_dir = parts[0]
    label      = parts[1]
    program    = parts[2].strip() if len(parts) > 2 else ""
    disabled   = parts[3].strip() if len(parts) > 3 else "0"
    enabled    = disabled != "1"
    output["scheduled_tasks"].append({
        "name":     label,
        "type":     "launchd",
        "command":  program,
        "schedule": "",
        "user":     "root" if "/LaunchDaemons" in source_dir else "",
        "enabled":  enabled,
    })


# ── ssh_keys ──────────────────────────────────────────────────────────────────

output["ssh_keys"] = []
for line in lines("ssh_keys"):
    if "|" not in line:
        continue
    idx = line.index("|")
    uname    = line[:idx]
    key_line = line[idx + 1:]
    parts    = key_line.split(None, 2)
    if len(parts) < 2:
        continue
    key_type   = parts[0]
    public_key = parts[1]
    comment    = parts[2] if len(parts) > 2 else ""
    output["ssh_keys"].append({
        "username":   uname,
        "key_type":   key_type,
        "public_key": public_key,
        "comment":    comment,
    })


# ── ssh_config ────────────────────────────────────────────────────────────────

ssh_cfg = {}
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


# ── listening_services (lsof -nP -iTCP -iUDP -sTCP:LISTEN) ──────────────────

# lsof columns: COMMAND PID USER FD TYPE DEVICE SIZE/OFF NODE NAME
# NAME for TCP LISTEN looks like: *:22 (LISTEN)  or  127.0.0.1:631 (LISTEN)

output["listening_services"] = []
for line in lines("listening_services"):
    line = line.strip()
    if not line or line.startswith("COMMAND"):
        continue
    parts = line.split()
    if len(parts) < 9:
        continue
    cmd     = parts[0]
    pid_str = parts[1]
    user    = parts[2]
    # TYPE column (parts[4]) is "IPv4" or "IPv6"
    type_field = parts[4] if len(parts) > 4 else ""
    name_field = parts[-1] if parts else ""

    # Strip "(LISTEN)" suffix
    name_field = re.sub(r'\s*\(LISTEN\)', '', name_field)

    # Split host:port — handle IPv6 addresses in brackets
    m_v6 = re.match(r'^\[(.+)\]:(\d+)$', name_field)
    m_v4 = re.match(r'^(.+):(\d+)$', name_field)
    if m_v6:
        local_addr = m_v6.group(1)
        port_str   = m_v6.group(2)
    elif m_v4:
        local_addr = m_v4.group(1)
        port_str   = m_v4.group(2)
    else:
        continue

    try:
        port = int(port_str)
    except ValueError:
        continue

    proto = "tcp6" if "6" in type_field else "tcp"
    try:
        pid = int(pid_str)
    except ValueError:
        pid = None

    output["listening_services"].append({
        "protocol":      proto,
        "local_address": local_addr,
        "port":          port,
        "process_name":  cmd,
        "pid":           pid,
        "user":          user,
    })
    if port not in output["network"]["open_ports"]:
        output["network"]["open_ports"].append(port)


# ── firewall_rules (socketfilterfw --listapps) ────────────────────────────────

# Output format:
#   ALF: total number of applications: N
#   <blank line or app name line>
#   /path/to/app ( Allow/Deny incoming connections)
#   ...

fw_raw = sections.get("firewall_rules", "")
output["firewall_rules"] = []

for line in fw_raw.splitlines():
    line = line.strip()
    if not line or line.startswith("ALF"):
        continue
    m = re.match(r'^(.+?)\s*\(\s*(Allow|Block|Deny)\s+incoming connections\s*\)', line, re.IGNORECASE)
    if m:
        app_path = m.group(1).strip()
        action   = "allow" if m.group(2).lower() == "allow" else "block"
        output["firewall_rules"].append({
            "chain":       "APPLICATION",
            "direction":   "in",
            "action":      action,
            "protocol":    "tcp",
            "source":      "any",
            "destination": "any",
            "port":        "",
            "enabled":     True,
            "description": app_path,
            "source_tool": "pf",
        })


# ── sysctl ────────────────────────────────────────────────────────────────────

output["sysctl"] = []
for line in lines("sysctl"):
    # macOS sysctl uses ": " as separator (not "=")
    if ": " in line:
        key, _, val = line.partition(": ")
    elif "=" in line:
        key, _, val = line.partition("=")
    else:
        continue
    output["sysctl"].append({"key": key.strip(), "value": val.strip()})


# ── logging_targets ───────────────────────────────────────────────────────────

output["logging_targets"] = []
for line in lines("logging_targets"):
    line = line.strip()
    if not line:
        continue
    # ASL remote target: "> /path/to/log" or "> syslog://host:port"
    # syslog.conf: "*.* @host:514"
    m = re.search(r"(@@?)([^\s:@>]+):?(\d+)?", line)
    if m:
        tcp  = m.group(1) == "@@"
        host = m.group(2)
        port = m.group(3) or "514"
        output["logging_targets"].append({
            "type":        "syslog",
            "destination": f"{host}:{port}",
            "protocol":    "tcp" if tcp else "udp",
            "enabled":     True,
        })
    elif "remote" in line.lower():
        # Unified log remote target — store as-is
        output["logging_targets"].append({
            "type":        "syslog",
            "destination": line,
            "protocol":    "unknown",
            "enabled":     True,
        })


# ── certificates ─────────────────────────────────────────────────────────────
#
# The collector outputs PEM blocks from the System keychain, each terminated
# with a "##CERTBOUNDARY##" sentinel line.  We pipe each PEM block through
# a regex-based parser (no cryptography library required).
#
# If the collector was also able to pipe through `openssl x509 -text`, the
# text header appears before the PEM block and contains Subject/Issuer/dates.
# We handle both cases: text-annotated PEM and raw PEM only.

output["certificates"] = []

cert_section_raw = sections.get("certificates", "")

# Split on our sentinel
raw_cert_blocks = cert_section_raw.split("##CERTBOUNDARY##")

def _pem_thumbprint(pem_block):
    """SHA-1 thumbprint of the DER bytes encoded in a PEM block (hex)."""
    import base64
    lines_b64 = [
        l for l in pem_block.splitlines()
        if l.strip() and not l.strip().startswith("-----")
    ]
    if not lines_b64:
        return ""
    try:
        der = base64.b64decode("".join(lines_b64))
        return hashlib.sha1(der).hexdigest().upper()
    except Exception:
        return ""

def _parse_openssl_text(text):
    """Extract Subject, Issuer, notBefore, notAfter from openssl x509 -text output."""
    cert = {}
    m = re.search(r'Subject:\s*(.+)', text)
    if m:
        cert["subject"] = m.group(1).strip()
    m = re.search(r'Issuer:\s*(.+)', text)
    if m:
        cert["issuer"] = m.group(1).strip()
    m = re.search(r'Not Before\s*:\s*(.+)', text)
    if m:
        cert["not_before"] = m.group(1).strip()
    m = re.search(r'Not After\s*:\s*(.+)', text)
    if m:
        cert["not_after"] = m.group(1).strip()
    m = re.search(r'Serial Number.*\n\s*([0-9a-f:]+)', text, re.IGNORECASE)
    if m:
        cert["serial"] = m.group(1).strip().replace(":", "").upper()
    return cert

for block in raw_cert_blocks:
    block = block.strip()
    if not block:
        continue

    # Extract PEM portion
    pem_match = re.search(
        r'(-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----)',
        block, re.DOTALL
    )
    if not pem_match:
        continue
    pem = pem_match.group(1)
    thumbprint = _pem_thumbprint(pem)
    if not thumbprint:
        continue

    # Try to get text metadata from openssl annotation before the PEM block
    pre_pem = block[:pem_match.start()]
    cert_meta = _parse_openssl_text(pre_pem) if pre_pem.strip() else {}

    output["certificates"].append({
        "subject":    cert_meta.get("subject", ""),
        "issuer":     cert_meta.get("issuer", ""),
        "thumbprint": thumbprint,
        "serial":     cert_meta.get("serial", ""),
        "not_before": cert_meta.get("not_before", ""),
        "not_after":  cert_meta.get("not_after", ""),
        "store":      "system",
    })
