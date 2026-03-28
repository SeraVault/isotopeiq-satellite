# Linux Baseline Parser
# Parses output from linux_baseline_collector.sh into the canonical schema.
#
# `result` — raw string output from the collector
# `output` — canonical dict to populate (pre-filled with empty structure)

import json
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
output["device"]["vendor"]      = dev_lines[3] if len(dev_lines) > 3 else ""
output["device"]["model"]       = dev_lines[4] if len(dev_lines) > 4 else ""


# ── hardware ──────────────────────────────────────────────────────────────────

hw_lines = lines("hardware")
output["hardware"]["cpu_model"]   = hw_lines[0] if len(hw_lines) > 0 else ""
try:
    output["hardware"]["cpu_cores"] = int(hw_lines[1]) if len(hw_lines) > 1 else None
except ValueError:
    pass
try:
    output["hardware"]["memory_gb"] = float(hw_lines[2]) if len(hw_lines) > 2 else None
except ValueError:
    pass
output["hardware"]["bios_version"]        = hw_lines[3] if len(hw_lines) > 3 else ""
output["hardware"]["serial_number"]       = hw_lines[4] if len(hw_lines) > 4 else ""
output["hardware"]["architecture"]        = hw_lines[5] if len(hw_lines) > 5 else ""
virt_raw = hw_lines[6].lower() if len(hw_lines) > 6 else "bare-metal"
virt_map = {
    "none": "bare-metal", "bare-metal": "bare-metal",
    "vmware": "vmware", "microsoft": "hyperv", "hyperv": "hyperv",
    "kvm": "kvm", "xen": "xen", "oracle": "virtualbox", "wsl": "wsl",
}
output["hardware"]["virtualization_type"] = virt_map.get(virt_raw, "other")


# ── os ────────────────────────────────────────────────────────────────────────

os_lines = lines("os")
output["os"]["name"]     = os_lines[0] if len(os_lines) > 0 else ""
output["os"]["version"]  = os_lines[1] if len(os_lines) > 1 else ""
output["os"]["build"]    = os_lines[2] if len(os_lines) > 2 else ""
output["os"]["kernel"]   = os_lines[3] if len(os_lines) > 3 else ""
output["os"]["timezone"] = os_lines[4] if len(os_lines) > 4 else ""

ntp_raw = os_lines[5].strip() if len(os_lines) > 5 else ""
output["os"]["ntp_servers"] = [s for s in ntp_raw.split() if s] if ntp_raw else []

ntp_sync = os_lines[6].strip().lower() if len(os_lines) > 6 else "unknown"
output["os"]["ntp_synced"] = True if ntp_sync == "yes" else (False if ntp_sync == "no" else None)


# ── network — interfaces ──────────────────────────────────────────────────────

iface_raw = sections.get("network", "")

def _parse_ip_json(raw):
    """Parse `ip -j addr show` JSON output."""
    try:
        ifaces = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return []
    result_ifaces = []
    for iface in ifaces:
        name = iface.get("ifname", "")
        flags = iface.get("flags", [])
        link_info = iface.get("link_type", "")
        oper = "up" if iface.get("operstate", "").lower() == "up" else "down"
        admin = "up" if "UP" in flags else "down"
        mac = iface.get("address", "")
        mtu = iface.get("mtu")
        ipv4, ipv6 = [], []
        for addr in iface.get("addr_info", []):
            cidr = f"{addr['local']}/{addr['prefixlen']}"
            if addr.get("family") == "inet":
                ipv4.append(cidr)
            elif addr.get("family") == "inet6":
                ipv6.append(cidr)
        result_ifaces.append({
            "name": name,
            "mac": mac,
            "ipv4": ipv4,
            "ipv6": ipv6,
            "admin_status": admin,
            "oper_status": oper,
            "mtu": mtu,
            "port_mode": "routed",
            "duplex": "unknown",
        })
    return result_ifaces

output["network"]["interfaces"] = _parse_ip_json(iface_raw)


# ── network — routes ─────────────────────────────────────────────────────────

route_raw = sections.get("network_routes", "")

def _parse_routes(raw):
    try:
        routes_json = json.loads(raw)
        result_routes = []
        for r in routes_json:
            dst = r.get("dst", "")
            gw  = r.get("gateway", "")
            dev = r.get("dev", "")
            metric = r.get("metric")
            result_routes.append({"destination": dst, "gateway": gw, "interface": dev, "metric": metric})
        return result_routes
    except (json.JSONDecodeError, ValueError):
        pass
    # fallback: plain text `ip route`
    result_routes = []
    for line in raw.splitlines():
        parts = line.split()
        if not parts:
            continue
        dst = parts[0]
        gw, dev, metric = "", "", None
        for i, p in enumerate(parts):
            if p == "via" and i + 1 < len(parts):
                gw = parts[i + 1]
            if p == "dev" and i + 1 < len(parts):
                dev = parts[i + 1]
            if p == "metric" and i + 1 < len(parts):
                try:
                    metric = int(parts[i + 1])
                except ValueError:
                    pass
        result_routes.append({"destination": dst, "gateway": gw, "interface": dev, "metric": metric})
    return result_routes

output["network"]["routes"] = _parse_routes(route_raw)


# ── network — DNS / gateway ───────────────────────────────────────────────────

output["network"]["dns_servers"] = lines("network_dns")

# Default gateway from routes
for r in output["network"]["routes"]:
    if r.get("destination") in ("default", "0.0.0.0/0"):
        output["network"]["default_gateway"] = r.get("gateway", "")
        break


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
    chage    = parts[5].strip() if len(parts) > 5 else ""
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
        "password_last_set": chage,
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

def _guess_pkg_source():
    """Detect package manager from known tools in the environment."""
    import shutil
    if shutil.which("dpkg-query"):
        return "apt"
    if shutil.which("rpm"):
        return "rpm"
    return "other"

pkg_source = _guess_pkg_source()

for line in lines("packages"):
    parts = line.split("|")
    if len(parts) < 1 or not parts[0]:
        continue
    pkg = {
        "name":         parts[0],
        "version":      parts[1] if len(parts) > 1 else "",
        "vendor":       parts[2] if len(parts) > 2 else "",
        "install_date": parts[3] if len(parts) > 3 else "",
        "source":       pkg_source,
    }
    output["packages"].append(pkg)


# ── services ──────────────────────────────────────────────────────────────────

svc_raw = sections.get("services", "")

def _parse_services(raw):
    # Try JSON first (systemctl --output=json)
    try:
        units = json.loads(raw)
        result_svcs = []
        for u in units:
            name = u.get("unit", "").removesuffix(".service")
            active = u.get("active", "").lower()
            sub    = u.get("sub", "").lower()
            load   = u.get("load", "").lower()
            status = "running" if sub == "running" else ("stopped" if active in ("inactive", "failed") else "unknown")
            startup = "enabled" if load == "loaded" else "disabled"
            result_svcs.append({"name": name, "status": status, "startup": startup})
        return result_svcs
    except (json.JSONDecodeError, ValueError, AttributeError):
        pass
    # Fallback: plain-text `systemctl list-units` output
    result_svcs = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("UNIT"):
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        name = parts[0].removesuffix(".service")
        sub  = parts[3].lower() if len(parts) > 3 else ""
        status = "running" if sub == "running" else "stopped"
        result_svcs.append({"name": name, "status": status, "startup": "unknown"})
    return result_svcs

output["services"] = _parse_services(svc_raw)


# ── filesystem ────────────────────────────────────────────────────────────────

# df -P -T output: Filesystem Type 1024-blocks Used Available Use% Mounted-on
for line in lines("filesystem"):
    parts = line.split()
    if len(parts) < 7:
        continue
    _, fs_type, blocks, _, avail, _, mount = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5], parts[6]
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

# Mount options from /proc/mounts
mount_options = {}
for line in lines("filesystem_mounts"):
    parts = line.split()
    if len(parts) >= 4:
        mount_options[parts[1]] = parts[3].split(",")

for fs in output["filesystem"]:
    if fs["mount"] in mount_options:
        fs["mount_options"] = mount_options[fs["mount"]]

# SUID files — attach to the matching mount point
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

sec_lines = lines("security")

selinux_raw = sec_lines[0].lower() if len(sec_lines) > 0 else "unknown"
selinux_map = {"enforcing": "enforcing", "permissive": "permissive", "disabled": "disabled"}
output["security"]["selinux_mode"] = selinux_map.get(selinux_raw, "unknown")

aa_raw = sec_lines[1].lower() if len(sec_lines) > 1 else "disabled"
output["security"]["apparmor_status"] = "enabled" if "enabled" in aa_raw else "disabled"

fw_raw = sec_lines[2].lower() if len(sec_lines) > 2 else ""
output["security"]["firewall_enabled"] = ("active" in fw_raw or "running" in fw_raw
                                           or "policy" in fw_raw)

sb_raw = sec_lines[3].lower() if len(sec_lines) > 3 else ""
output["security"]["secure_boot"] = True if "enabled" in sb_raw else (False if "disabled" in sb_raw else None)

audit_raw = sec_lines[4].lower() if len(sec_lines) > 4 else ""
output["security"]["audit_logging_enabled"] = "active" in audit_raw

# Password policy from login.defs lines
policy = {}
for line in sec_lines[5:]:
    m = re.match(r"(PASS_MIN_LEN|PASS_MAX_DAYS)\s+(\d+)", line)
    if m:
        key, val = m.group(1), int(m.group(2))
        if key == "PASS_MIN_LEN":
            policy["min_length"] = val
        elif key == "PASS_MAX_DAYS":
            policy["max_age_days"] = val
if policy:
    output["security"]["password_policy"] = policy


# ── scheduled_tasks ───────────────────────────────────────────────────────────

output["scheduled_tasks"] = []
for line in lines("scheduled_tasks"):
    parts = line.split("|", 3)
    if len(parts) < 4:
        continue
    task_type, user, src, schedule_cmd = parts
    # Split schedule (5 cron fields) from command
    fields = schedule_cmd.split(None, 5)
    if len(fields) >= 6:
        schedule = " ".join(fields[:5])
        command  = fields[5]
    else:
        schedule = ""
        command  = schedule_cmd
    output["scheduled_tasks"].append({
        "name":     f"{src}:{command[:60]}",
        "type":     task_type,
        "command":  command,
        "schedule": schedule,
        "user":     user,
        "enabled":  True,
    })


# ── ssh_keys ──────────────────────────────────────────────────────────────────

output["ssh_keys"] = []
for line in lines("ssh_keys"):
    idx = line.index("|")
    uname = line[:idx]
    key_line = line[idx + 1:]
    parts = key_line.split(None, 2)
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


# ── kernel_modules ────────────────────────────────────────────────────────────

output["kernel_modules"] = []
for line in lines("kernel_modules"):
    parts = line.split()
    if not parts:
        continue
    output["kernel_modules"].append({"name": parts[0], "type": "lsmod"})


# ── listening_services ────────────────────────────────────────────────────────

output["listening_services"] = []
# ss -tlunp output columns: Netid State Recv-Q Send-Q Local-Address:Port Peer-Address:Port Process
for line in lines("listening_services"):
    line = line.strip()
    if not line or line.startswith("Netid") or line.startswith("Proto"):
        continue
    parts = line.split()
    if len(parts) < 5:
        continue
    proto_raw = parts[0].lower()
    proto_map = {"tcp": "tcp", "tcp6": "tcp6", "udp": "udp", "udp6": "udp6"}
    proto = proto_map.get(proto_raw, "unknown")
    local = parts[4] if len(parts) > 4 else ""
    # Extract port from last colon
    port_str = local.rsplit(":", 1)[-1].strip("[]")
    try:
        port = int(port_str)
    except ValueError:
        continue
    local_addr = local.rsplit(":", 1)[0]
    # Process info: users:(("sshd",pid=1234,fd=3))
    proc_raw = " ".join(parts[6:]) if len(parts) > 6 else ""
    proc_match = re.search(r'"([^"]+)"', proc_raw)
    pid_match  = re.search(r"pid=(\d+)", proc_raw)
    output["listening_services"].append({
        "protocol":      proto,
        "local_address": local_addr,
        "port":          port,
        "process_name":  proc_match.group(1) if proc_match else "",
        "pid":           int(pid_match.group(1)) if pid_match else None,
        "user":          "",
    })
    output["network"]["open_ports"].append(port)


# ── firewall_rules ────────────────────────────────────────────────────────────

fw_raw = sections.get("firewall_rules", "")
output["firewall_rules"] = []

def _parse_iptables_save(raw):
    rules = []
    current_table = ""
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("*"):
            current_table = line[1:]
            continue
        if not line.startswith("-A"):
            continue
        parts = line.split()
        chain = parts[1] if len(parts) > 1 else "unknown"
        action = ""
        proto  = "any"
        src    = "any"
        dst    = "any"
        port   = ""
        for i, p in enumerate(parts):
            if p == "-j" and i + 1 < len(parts):
                action = parts[i + 1].lower()
            if p == "-p" and i + 1 < len(parts):
                proto = parts[i + 1]
            if p == "-s" and i + 1 < len(parts):
                src = parts[i + 1]
            if p == "-d" and i + 1 < len(parts):
                dst = parts[i + 1]
            if p in ("--dport", "--sport") and i + 1 < len(parts):
                port = parts[i + 1]
        rules.append({
            "chain":       chain,
            "direction":   "in" if chain == "INPUT" else ("out" if chain == "OUTPUT" else "both"),
            "action":      action,
            "protocol":    proto,
            "source":      src,
            "destination": dst,
            "port":        port,
            "enabled":     True,
            "source_tool": "iptables",
        })
    return rules

if fw_raw:
    output["firewall_rules"] = _parse_iptables_save(fw_raw)


# ── sysctl ────────────────────────────────────────────────────────────────────

output["sysctl"] = []
for line in lines("sysctl"):
    if "=" not in line:
        continue
    key, _, val = line.partition("=")
    output["sysctl"].append({"key": key.strip(), "value": val.strip()})


# ── logging_targets ───────────────────────────────────────────────────────────

output["logging_targets"] = []
for line in lines("logging_targets"):
    line = line.strip()
    if not line:
        continue
    # rsyslog remote: *.* @host:514 (UDP) or @@host:514 (TCP)
    m = re.search(r"(@@?)([^\s:]+):?(\d+)?", line)
    if m:
        tcp = m.group(1) == "@@"
        host = m.group(2)
        port = m.group(3) or ("514")
        output["logging_targets"].append({
            "type":        "syslog",
            "destination": f"{host}:{port}",
            "protocol":    "tcp" if tcp else "udp",
            "enabled":     True,
        })
