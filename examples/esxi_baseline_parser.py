# ESXi Baseline Parser
# Parses output from esxi_baseline_collector.sh into the canonical schema.
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

def subsection(raw, header):
    """Extract text between two === headers inside a raw section string."""
    pattern = r"^=== " + re.escape(header) + r" ===$"
    sec_lines = raw.splitlines()
    capturing = False
    buf = []
    for line in sec_lines:
        if re.match(pattern, line.strip()):
            capturing = True
            continue
        if capturing and re.match(r"^=== .+ ===$", line.strip()):
            break
        if capturing:
            buf.append(line)
    return "\n".join(buf).strip()


# ── Generic esxcli Key: Value record parser ───────────────────────────────────

def _parse_esxcli_records(raw):
    """
    Parse esxcli "Key: Value" block output into a list of dicts.
    Records are separated by blank lines; each non-blank line is "Key: Value".
    """
    records = []
    current_rec = {}
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            if current_rec:
                records.append(current_rec)
                current_rec = {}
            continue
        if ":" in stripped:
            key, _, val = stripped.partition(":")
            current_rec[key.strip()] = val.strip()
        else:
            # Continuation or non-KV line — attach to last key if present
            if current_rec:
                last_key = list(current_rec.keys())[-1]
                current_rec[last_key] = (current_rec[last_key] + " " + stripped).strip()
    if current_rec:
        records.append(current_rec)
    return records


def _esxcli_single(raw):
    """Parse a single esxcli Key: Value block into one dict (first record)."""
    recs = _parse_esxcli_records(raw)
    return recs[0] if recs else {}


# ── device ────────────────────────────────────────────────────────────────────

dev_lines = lines("device")
output["device"]["hostname"]    = dev_lines[0] if len(dev_lines) > 0 else ""
output["device"]["fqdn"]        = dev_lines[1] if len(dev_lines) > 1 else ""
output["device"]["device_type"] = dev_lines[2] if len(dev_lines) > 2 else "server"
output["device"]["vendor"]      = dev_lines[3] if len(dev_lines) > 3 else "VMware"
output["device"]["model"]       = dev_lines[4] if len(dev_lines) > 4 else ""


# ── hardware ──────────────────────────────────────────────────────────────────

hw_lines = lines("hardware")
output["hardware"]["cpu_model"] = hw_lines[0] if len(hw_lines) > 0 else ""
try:
    output["hardware"]["cpu_cores"] = int(hw_lines[1]) if len(hw_lines) > 1 else None
except ValueError:
    pass
try:
    output["hardware"]["memory_gb"] = float(hw_lines[2]) if len(hw_lines) > 2 else None
except ValueError:
    pass
output["hardware"]["bios_version"]  = hw_lines[3] if len(hw_lines) > 3 else ""
output["hardware"]["serial_number"] = hw_lines[4] if len(hw_lines) > 4 else ""
output["hardware"]["architecture"]  = hw_lines[5] if len(hw_lines) > 5 else ""
# ESXi is always the bare-metal hypervisor from its own perspective
output["hardware"]["virtualization_type"] = "bare-metal"


# ── os ────────────────────────────────────────────────────────────────────────

os_lines = lines("os")
output["os"]["name"]     = os_lines[0] if len(os_lines) > 0 else "VMware ESXi"
output["os"]["version"]  = os_lines[1] if len(os_lines) > 1 else ""
output["os"]["build"]    = os_lines[2] if len(os_lines) > 2 else ""
output["os"]["kernel"]   = os_lines[3] if len(os_lines) > 3 else ""
output["os"]["timezone"] = os_lines[4] if len(os_lines) > 4 else "UTC"

ntp_raw = os_lines[5].strip() if len(os_lines) > 5 else ""
output["os"]["ntp_servers"] = [s for s in ntp_raw.split() if s] if ntp_raw else []

ntp_sync = os_lines[6].strip().lower() if len(os_lines) > 6 else "unknown"
output["os"]["ntp_synced"] = True if ntp_sync == "yes" else (False if ntp_sync == "no" else None)


# ── network — interfaces ──────────────────────────────────────────────────────

def _parse_network_interfaces(raw):
    """
    Parse the network_interfaces section.
    Combines esxcli network ip interface list, ipv4 get, and nic list.
    Returns list of canonical network interface dicts.
    """
    vmk_raw    = subsection(raw, "VMkernel Interfaces")
    ipv4_raw   = subsection(raw, "VMkernel IPv4")
    phys_raw   = subsection(raw, "Physical NICs")

    # Build IPv4 map: vmknic name -> {ipv4_address, subnet_mask}
    ipv4_map = {}
    for rec in _parse_esxcli_records(ipv4_raw):
        name = rec.get("Name", rec.get("Interface", ""))
        if name:
            addr = rec.get("IPv4 Address", rec.get("Address", ""))
            mask = rec.get("IPv4 Netmask", rec.get("Netmask", ""))
            # Convert mask to prefix length for CIDR notation
            if addr and mask:
                # Count bits in dotted-decimal mask
                try:
                    prefix = sum(bin(int(o)).count("1") for o in mask.split("."))
                    ipv4_map[name] = f"{addr}/{prefix}"
                except (ValueError, AttributeError):
                    ipv4_map[name] = addr

    ifaces = []
    # VMkernel (vmk*) interfaces
    for rec in _parse_esxcli_records(vmk_raw):
        name = rec.get("Name", "")
        if not name:
            continue
        mac     = rec.get("MAC Address", rec.get("MAC", ""))
        mtu_str = rec.get("MTU", "")
        try:
            mtu = int(mtu_str)
        except (ValueError, TypeError):
            mtu = None
        enabled = rec.get("Enabled", "").lower()
        admin   = "up" if enabled == "true" else ("down" if enabled == "false" else "unknown")
        # Oper status comes from link state if present
        link    = rec.get("Portgroup", rec.get("Netstack", ""))
        ipv4_cidr = ipv4_map.get(name, "")
        ifaces.append({
            "name":         name,
            "mac":          mac,
            "ipv4":         [ipv4_cidr] if ipv4_cidr else [],
            "ipv6":         [],
            "admin_status": admin,
            "oper_status":  "unknown",
            "mtu":          mtu,
            "port_mode":    "routed",
            "duplex":       "unknown",
        })

    # Physical NICs — tab/space separated table
    # Columns vary by ESXi version but typically:
    # Name  PCI Device  Driver  Admin Status  Link Status  Speed  Duplex  MAC Address  MTU  Description
    phys_lines = [l for l in phys_raw.splitlines() if l.strip()]
    if len(phys_lines) > 1:
        header_line = phys_lines[0]
        # Identify column start positions from header
        col_names = re.split(r"\s{2,}", header_line.strip())
        for data_line in phys_lines[1:]:
            cols = re.split(r"\s{2,}", data_line.strip())
            rec  = dict(zip(col_names, cols)) if len(cols) >= len(col_names) else {}
            if not rec and cols:
                # Fallback: positional by index
                rec = {col_names[i]: cols[i] for i in range(min(len(col_names), len(cols)))}
            name = cols[0] if cols else ""
            if not name or name.lower() == col_names[0].lower():
                continue
            mac     = rec.get("MAC Address", rec.get("MAC", ""))
            speed_r = rec.get("Speed", "")
            speed   = speed_r.replace("Mb/s", "M").replace("Gb/s", "G").replace("Mbps", "M").replace("Gbps", "G") if speed_r else ""
            duplex_r = rec.get("Duplex", "").lower()
            duplex  = "full" if "full" in duplex_r else ("half" if "half" in duplex_r else "unknown")
            admin_r  = rec.get("Admin Status", rec.get("Link Status", "")).lower()
            admin    = "up" if "up" in admin_r else "down"
            link_r   = rec.get("Link Status", "").lower()
            oper     = "up" if "up" in link_r else ("down" if "down" in link_r else "unknown")
            mtu_str  = rec.get("MTU", "")
            try:
                mtu = int(mtu_str)
            except (ValueError, TypeError):
                mtu = None
            ifaces.append({
                "name":         name,
                "mac":          mac,
                "ipv4":         [],
                "ipv6":         [],
                "admin_status": admin,
                "oper_status":  oper,
                "speed":        speed,
                "duplex":       duplex,
                "mtu":          mtu,
                "port_mode":    "routed",
            })

    return ifaces

output["network"]["interfaces"] = _parse_network_interfaces(sections.get("network_interfaces", ""))


# ── network — routes ─────────────────────────────────────────────────────────

def _parse_esxcli_routes(raw):
    """
    Parse esxcli network ip route ipv4 list columnar output.
    Columns: Network  Netmask  Gateway  Interface  Source
    """
    route_lines = [l for l in raw.splitlines() if l.strip()]
    if not route_lines:
        return []
    routes = []
    # Find header line
    header_idx = 0
    for i, l in enumerate(route_lines):
        if re.match(r"\s*Network\s+Netmask", l, re.IGNORECASE):
            header_idx = i
            break
    data_lines = route_lines[header_idx + 2:]   # skip header + separator dashes
    for line in data_lines:
        parts = line.split()
        if len(parts) < 3:
            continue
        network  = parts[0]
        netmask  = parts[1]
        gateway  = parts[2]
        iface    = parts[3] if len(parts) > 3 else ""
        # Build destination CIDR from network + netmask
        try:
            prefix = sum(bin(int(o)).count("1") for o in netmask.split("."))
            dst = f"{network}/{prefix}" if network not in ("0.0.0.0", "default") else "default"
        except (ValueError, AttributeError):
            dst = network
        routes.append({
            "destination": dst,
            "gateway":     gateway,
            "interface":   iface,
            "metric":      None,
        })
    return routes

output["network"]["routes"] = _parse_esxcli_routes(sections.get("network_routes", ""))

# Default gateway from routes
for r in output["network"]["routes"]:
    if r.get("destination") in ("default", "0.0.0.0/0"):
        output["network"]["default_gateway"] = r.get("gateway", "")
        break


# ── network — DNS ─────────────────────────────────────────────────────────────

def _parse_esxcli_dns(raw):
    servers = []
    srv_raw = subsection(raw, "DNS Servers")
    for line in srv_raw.splitlines():
        line = line.strip()
        # esxcli output: "   DNSConfig(servers=['10.0.0.1', ...])" or plain IPs
        for ip in re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", line):
            if ip not in servers:
                servers.append(ip)
    return servers

output["network"]["dns_servers"] = _parse_esxcli_dns(sections.get("network_dns", ""))


# ── users ─────────────────────────────────────────────────────────────────────

def _parse_esxcli_users(raw):
    """
    esxcli system account list — columnar: UserID  Description  SuspendedAccount  ShellAccessEnabled
    """
    users = []
    raw_lines = [l for l in raw.splitlines() if l.strip()]
    if not raw_lines:
        return users
    # Skip header and separator lines
    data_start = 0
    for i, l in enumerate(raw_lines):
        if re.match(r"[-]+", l.strip()):
            data_start = i + 1
            break
    for line in raw_lines[data_start:]:
        parts = re.split(r"\s{2,}", line.strip())
        if not parts or not parts[0]:
            continue
        uid_name   = parts[0]
        desc       = parts[1] if len(parts) > 1 else ""
        suspended  = parts[2].lower() if len(parts) > 2 else "false"
        shell_acc  = parts[3].lower() if len(parts) > 3 else "false"
        disabled   = suspended in ("true", "yes", "1")
        users.append({
            "username":          uid_name,
            "uid":               uid_name,   # ESXi has no numeric UID
            "groups":            [],
            "home":              "",
            "shell":             "/bin/sh" if shell_acc in ("true", "yes", "1") else "",
            "disabled":          disabled,
            "password_last_set": "",
            "last_login":        "",
            "sudo_privileges":   "",
        })
    return users

output["users"] = _parse_esxcli_users(sections.get("users", ""))


# ── groups (ESXi permissions/roles) ──────────────────────────────────────────

def _parse_esxcli_permissions(raw):
    """
    esxcli system permission list — columnar: Principal  IsGroup  Role  RoleId  Propagate
    Groups these by Role to produce canonical groups.
    """
    role_members = {}
    raw_lines = [l for l in raw.splitlines() if l.strip()]
    data_start = 0
    for i, l in enumerate(raw_lines):
        if re.match(r"[-]+", l.strip()):
            data_start = i + 1
            break
    for line in raw_lines[data_start:]:
        parts = re.split(r"\s{2,}", line.strip())
        if not parts or not parts[0]:
            continue
        principal = parts[0]
        is_group  = parts[1].lower() if len(parts) > 1 else "false"
        role      = parts[2] if len(parts) > 2 else "Unknown"
        role_members.setdefault(role, []).append(principal)
    groups = []
    for role, members in role_members.items():
        groups.append({
            "group_name": role,
            "gid":        role,
            "members":    members,
        })
    return groups

output["groups"] = _parse_esxcli_permissions(sections.get("groups", ""))


# ── packages (VIBs) ───────────────────────────────────────────────────────────

def _parse_esxcli_vibs(raw):
    """
    esxcli software vib list — columnar table:
    Name  Version  Vendor  Acceptance Level  Install Date
    """
    packages = []
    raw_lines = [l for l in raw.splitlines() if l.strip()]
    data_start = 0
    for i, l in enumerate(raw_lines):
        if re.match(r"[-]+", l.strip()):
            data_start = i + 1
            break
    for line in raw_lines[data_start:]:
        # Split on 2+ spaces to handle version strings with hyphens
        parts = re.split(r"\s{2,}", line.strip())
        if len(parts) < 2 or not parts[0]:
            continue
        name     = parts[0]
        version  = parts[1] if len(parts) > 1 else ""
        vendor   = parts[2] if len(parts) > 2 else ""
        # parts[3] = AcceptanceLevel, parts[4] = InstallDate
        install_date = parts[4] if len(parts) > 4 else (parts[3] if len(parts) > 3 else "")
        # Heuristic: if parts[3] looks like a date, no acceptance level column present
        if len(parts) == 4 and re.match(r"\d{4}-\d{2}-\d{2}", parts[3]):
            install_date = parts[3]
        packages.append({
            "name":         name,
            "version":      version,
            "vendor":       vendor,
            "install_date": install_date,
            "source":       "other",   # VIBs don't map to a standard canonical source
        })
    return packages

output["packages"] = _parse_esxcli_vibs(sections.get("packages", ""))


# ── services ──────────────────────────────────────────────────────────────────

def _parse_esxcli_services(raw):
    """
    esxcli system service list — Key: Value records per service.
    Known keys: Label, Key, Policy, Running, Required
    """
    svc_raw = subsection(raw, "Service List")
    if not svc_raw:
        svc_raw = raw   # no subsection headers
    services = []
    for rec in _parse_esxcli_records(svc_raw):
        name    = rec.get("Label", rec.get("Key", ""))
        if not name:
            continue
        running = rec.get("Running", "").lower()
        policy  = rec.get("Policy", "").lower()
        status  = "running" if running in ("true", "yes", "1") else "stopped"
        # Policy: "on"=enabled, "off"=disabled, "automatic"=manual
        if policy in ("on", "enabled"):
            startup = "enabled"
        elif policy in ("off", "disabled"):
            startup = "disabled"
        elif policy == "automatic":
            startup = "manual"
        else:
            startup = "unknown"
        services.append({"name": name, "status": status, "startup": startup})
    # Also parse chkconfig --list fallback (name    0:off 1:off ... 5:on 6:off)
    if not services:
        for line in [l for l in svc_raw.splitlines() if l.strip()]:
            parts = line.split()
            if not parts:
                continue
            name = parts[0]
            if ":" not in line:
                continue
            # Check if any runlevel has "on"
            enabled = any(":on" in p for p in parts[1:])
            services.append({
                "name":    name,
                "status":  "unknown",
                "startup": "enabled" if enabled else "disabled",
            })
    return services

output["services"] = _parse_esxcli_services(sections.get("services", ""))


# ── filesystem ────────────────────────────────────────────────────────────────

def _parse_esxcli_filesystem(raw):
    """
    Combine df -k output and esxcli storage filesystem list.
    """
    df_raw = subsection(raw, "df")
    storage_raw = subsection(raw, "Storage Filesystems")

    fs_map = {}

    # df -k: Filesystem  1K-blocks  Used  Available  Use%  Mounted on
    for line in [l for l in df_raw.splitlines() if l.strip()]:
        parts = line.split()
        # Skip header
        if not parts or parts[0].lower() in ("filesystem",):
            continue
        if len(parts) < 6:
            continue
        device = parts[0]
        try:
            blocks = int(parts[1])
            avail  = int(parts[3])
            size_gb = round(blocks / 1024 / 1024, 2)
            free_gb = round(avail  / 1024 / 1024, 2)
        except (ValueError, IndexError):
            size_gb = free_gb = None
        mount = parts[5]
        fs_map[mount] = {
            "mount":         mount,
            "type":          "vmfs",
            "size_gb":       size_gb,
            "free_gb":       free_gb,
            "mount_options": [],
            "suid_files":    [],
        }

    # esxcli storage filesystem list — enrich type info
    # Columns: Mount Point  Volume Name  UUID  Mounted  Type  Size  Free
    stor_lines = [l for l in storage_raw.splitlines() if l.strip()]
    data_start = 0
    for i, l in enumerate(stor_lines):
        if re.match(r"[-]+", l.strip()):
            data_start = i + 1
            break
    for line in stor_lines[data_start:]:
        parts = re.split(r"\s{2,}", line.strip())
        if len(parts) < 5 or not parts[0]:
            continue
        mount_pt = parts[0]
        fs_type  = parts[4] if len(parts) > 4 else "vmfs"
        if mount_pt in fs_map:
            fs_map[mount_pt]["type"] = fs_type
        else:
            try:
                size_gb = round(int(parts[5]) / 1024 / 1024 / 1024, 2) if len(parts) > 5 else None
                free_gb = round(int(parts[6]) / 1024 / 1024 / 1024, 2) if len(parts) > 6 else None
            except (ValueError, IndexError):
                size_gb = free_gb = None
            fs_map[mount_pt] = {
                "mount":         mount_pt,
                "type":          fs_type,
                "size_gb":       size_gb,
                "free_gb":       free_gb,
                "mount_options": [],
                "suid_files":    [],
            }

    return list(fs_map.values())

output["filesystem"] = _parse_esxcli_filesystem(sections.get("filesystem", ""))


# ── security ──────────────────────────────────────────────────────────────────

sec_raw = sections.get("security", "")

# Lockdown mode → selinux_mode equivalent
lockdown_raw = subsection(sec_raw, "Lockdown Mode").lower()
if "enabled" in lockdown_raw or "strict" in lockdown_raw or "normal" in lockdown_raw:
    output["security"]["selinux_mode"] = "enforcing"
elif "disabled" in lockdown_raw:
    output["security"]["selinux_mode"] = "disabled"
else:
    output["security"]["selinux_mode"] = "unknown"

# ESXi has no AppArmor
output["security"]["apparmor_status"] = "disabled"

# Firewall status
fw_status_raw = subsection(sec_raw, "Firewall Status")
fw_rec = _esxcli_single(fw_status_raw)
fw_enabled_val = fw_rec.get("Enabled", fw_rec.get("Default Action", "")).lower()
if fw_enabled_val in ("true", "yes", "1", "drop"):
    output["security"]["firewall_enabled"] = True
elif fw_enabled_val in ("false", "no", "0", "pass"):
    output["security"]["firewall_enabled"] = False
else:
    output["security"]["firewall_enabled"] = None

# ESXi has no Secure Boot reporting via CLI in most versions
output["security"]["secure_boot"] = None

# Audit logging — if syslog is configured to a remote host, treat as enabled
syslog_raw = subsection(sec_raw, "Syslog Config")
syslog_rec = _esxcli_single(syslog_raw)
remote_host = syslog_rec.get("Remote Host", syslog_rec.get("Loghost", ""))
output["security"]["audit_logging_enabled"] = bool(remote_host)

# Password complexity policy
pw_raw = subsection(sec_raw, "Password Complexity")
pw_rec = _esxcli_single(pw_raw)
policy = {}
min_len = pw_rec.get("Minimum Length", pw_rec.get("MinLength", ""))
if min_len:
    try:
        policy["min_length"] = int(min_len)
    except ValueError:
        pass
max_days = pw_rec.get("Maximum Days", pw_rec.get("MaxDays", ""))
if max_days:
    try:
        policy["max_age_days"] = int(max_days)
    except ValueError:
        pass
# "Complexity required" from ESXi password complexity setting
complexity = pw_rec.get("Complexity", pw_rec.get("Required", "")).lower()
if complexity:
    policy["complexity_required"] = complexity not in ("false", "no", "0", "disabled", "")
lockout_str = pw_rec.get("Lockout Attempts", pw_rec.get("MaxAttempts", ""))
if lockout_str:
    try:
        policy["lockout_threshold"] = int(lockout_str)
    except ValueError:
        pass
if policy:
    output["security"]["password_policy"] = policy


# ── scheduled_tasks ───────────────────────────────────────────────────────────

output["scheduled_tasks"] = []
tasks_raw = sections.get("scheduled_tasks", "")
cron_raw = subsection(tasks_raw, "Root Crontab")

for line in [l for l in cron_raw.splitlines() if l.strip()]:
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
        "name":     f"{src}:{command[:60]}",
        "type":     "cron",
        "command":  command,
        "schedule": schedule,
        "user":     user,
        "enabled":  True,
    })


# ── listening_services ────────────────────────────────────────────────────────

output["listening_services"] = []

# esxcli network ip connection list | grep LISTEN
# Columns: Proto  Recv-Q  Send-Q  LocalAddress  ForeignAddress  State  CC  World  Name
for line in lines("listening_services"):
    line = line.strip()
    if not line or line.lower().startswith("proto"):
        continue
    parts = line.split()
    if len(parts) < 6:
        continue
    proto_raw   = parts[0].lower()
    proto_map   = {"tcp": "tcp", "tcp6": "tcp6", "udp": "udp", "udp6": "udp6"}
    proto       = proto_map.get(proto_raw, "unknown")
    local       = parts[3] if len(parts) > 3 else ""
    port_str    = local.rsplit(":", 1)[-1] if ":" in local else ""
    try:
        port = int(port_str)
    except ValueError:
        continue
    local_addr = local.rsplit(":", 1)[0]
    proc_name  = parts[8] if len(parts) > 8 else ""
    output["listening_services"].append({
        "protocol":      proto,
        "local_address": local_addr,
        "port":          port,
        "process_name":  proc_name,
        "pid":           None,
        "user":          "",
    })
    output["network"]["open_ports"].append(port)


# ── firewall_rules ────────────────────────────────────────────────────────────

def _parse_esxcli_firewall_rulesets(raw):
    """
    esxcli network firewall ruleset list — columnar:
    Name  Enabled  AllowedAll  ...
    Produces canonical firewall_rules entries.
    """
    rules = []
    raw_lines = [l for l in raw.splitlines() if l.strip()]
    data_start = 0
    for i, l in enumerate(raw_lines):
        if re.match(r"[-]+", l.strip()):
            data_start = i + 1
            break
    for line in raw_lines[data_start:]:
        parts = re.split(r"\s{2,}", line.strip())
        if not parts or not parts[0]:
            continue
        name    = parts[0]
        enabled_str = parts[1].lower() if len(parts) > 1 else "false"
        enabled = enabled_str in ("true", "yes", "1")
        rules.append({
            "chain":       name,
            "direction":   "both",
            "action":      "accept" if enabled else "drop",
            "protocol":    "any",
            "source":      "any",
            "destination": "any",
            "port":        "",
            "enabled":     enabled,
            "description": name,
            "source_tool": "esxcli",
        })
    return rules

output["firewall_rules"] = _parse_esxcli_firewall_rulesets(sections.get("firewall_rules", ""))


# ── sysctl (ESXi advanced settings) ──────────────────────────────────────────

def _parse_esxcli_advanced_settings(raw):
    """
    esxcli system settings advanced list — Key: Value records.
    Relevant keys: Path, Type, Int Value, String Value, Default Int Value, etc.
    """
    sysctl = []
    for rec in _parse_esxcli_records(raw):
        path = rec.get("Path", "")
        if not path:
            continue
        int_val = rec.get("Int Value", "")
        str_val = rec.get("String Value", "")
        val = str_val if str_val else int_val
        sysctl.append({"key": path, "value": val})
    return sysctl

output["sysctl"] = _parse_esxcli_advanced_settings(sections.get("sysctl", ""))


# ── logging_targets ───────────────────────────────────────────────────────────

def _parse_esxcli_syslog(raw):
    """
    Parse syslog config and loggers into canonical logging_targets.
    """
    targets = []
    cfg_raw     = subsection(raw, "Syslog Config")
    loggers_raw = subsection(raw, "Syslog Loggers")

    cfg_rec = _esxcli_single(cfg_raw)
    # Remote host field names vary by ESXi version
    for field in ("Remote Host", "Loghost", "Default Rotation Size", "Loghost URI"):
        remote = cfg_rec.get(field, "")
        if remote and (":" in remote or re.match(r"\d{1,3}\.\d{1,3}", remote) or remote.startswith("udp://") or remote.startswith("tcp://")):
            # Parse protocol prefix if present
            proto = "udp"
            dest  = remote
            if remote.startswith("tcp://"):
                proto = "tcp"
                dest  = remote[6:]
            elif remote.startswith("tls://"):
                proto = "tls"
                dest  = remote[6:]
            elif remote.startswith("udp://"):
                dest = remote[6:]
            targets.append({
                "type":        "syslog",
                "destination": dest,
                "protocol":    proto,
                "enabled":     True,
            })
            break

    # Per-logger entries from loggers list
    for rec in _parse_esxcli_records(loggers_raw):
        logger_id  = rec.get("Logger", rec.get("ID", ""))
        logger_dst = rec.get("Remote Host", rec.get("Loghost", ""))
        if logger_dst and logger_id:
            targets.append({
                "type":        "syslog",
                "destination": logger_dst,
                "protocol":    "udp",
                "facility":    logger_id,
                "enabled":     True,
            })

    return targets

output["logging_targets"] = _parse_esxcli_syslog(sections.get("logging_targets", ""))


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

# Annotate SSH service state from security section
ssh_svc_raw = subsection(sections.get("security", ""), "SSH Service").lower()
if ssh_svc_raw:
    ssh_running = "running" in ssh_svc_raw or "true" in ssh_svc_raw
    if "permit_root_login" not in ssh_cfg:
        # ESXi SSH always allows root; note it if service is up
        ssh_cfg["permit_root_login"] = "yes" if ssh_running else "no"

if ssh_cfg:
    output["ssh_config"] = ssh_cfg


# ── snmp ──────────────────────────────────────────────────────────────────────

def _parse_esxcli_snmp(raw):
    """
    esxcli system snmp get — Key: Value output.
    """
    rec = _esxcli_single(raw)
    if not rec:
        return {}

    enabled_str = rec.get("Enable", rec.get("Enabled", "false")).lower()
    enabled = enabled_str in ("true", "yes", "1")

    communities_raw = rec.get("Communities", "")
    communities = [c.strip() for c in communities_raw.split(",") if c.strip()] if communities_raw else []

    targets_raw = rec.get("Targets", rec.get("Trap Targets", ""))
    trap_targets = [t.strip() for t in targets_raw.split(",") if t.strip()] if targets_raw else []

    # V3 users (ESXi format: "username/authproto/privproto/securitylevel,...")
    v3_users = []
    v3_raw = rec.get("V3users", rec.get("Users", ""))
    if v3_raw:
        for entry in v3_raw.split(","):
            entry = entry.strip()
            if not entry:
                continue
            parts = entry.split("/")
            v3_users.append({
                "username":       parts[0] if len(parts) > 0 else entry,
                "auth_protocol":  parts[1].upper() if len(parts) > 1 else "none",
                "priv_protocol":  parts[2].upper() if len(parts) > 2 else "none",
                "security_level": parts[3] if len(parts) > 3 else "noAuthNoPriv",
            })

    # Determine versions in use
    versions = []
    if communities:
        versions.append("v2c")
    if v3_users:
        versions.append("v3")
    if not versions and enabled:
        versions.append("v2c")

    snmp = {
        "enabled":      enabled,
        "versions":     versions,
        "communities":  communities,
        "v3_users":     v3_users,
        "trap_targets": trap_targets,
    }
    location = rec.get("Syscontact", rec.get("Location", ""))
    contact  = rec.get("Syslocation", rec.get("Contact", ""))
    if location:
        snmp["location"] = location
    if contact:
        snmp["contact"] = contact
    return snmp

_snmp = _parse_esxcli_snmp(sections.get("snmp", ""))
if _snmp:
    output["snmp"] = _snmp


# ── certificates ──────────────────────────────────────────────────────────────

def _parse_esxi_certificates(raw):
    """
    Parse the certificates section.
    Extracts PEM content from /etc/vmware/ssl/rui.crt and TLS rule entries.
    """
    certs = []
    cert_raw = subsection(raw, "Host Certificate")

    # Find PEM blocks
    pem_pattern = re.compile(
        r"(-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----)",
        re.DOTALL
    )
    for pem_match in pem_pattern.finditer(cert_raw):
        pem = pem_match.group(1)
        # Extract CN from Subject line if present (non-crypto text parsing)
        subject = ""
        for line in cert_raw.splitlines():
            cn_match = re.search(r"Subject:.*CN\s*=\s*([^,/\n]+)", line, re.IGNORECASE)
            if cn_match:
                subject = cn_match.group(1).strip()
                break
        if not subject:
            # Try to derive from hostname
            subject = output["device"].get("hostname", "")

        # Thumbprint: we cannot compute without crypto libs in ESXi parser context;
        # use a deterministic placeholder derived from the PEM length + first chars
        thumb_seed = str(len(pem)) + pem[28:36] if len(pem) > 36 else str(len(pem))
        thumbprint = "sha256:" + thumb_seed[:32].replace("\n", "").replace(" ", "")

        certs.append({
            "subject":    subject,
            "issuer":     subject,   # self-signed by default on ESXi
            "thumbprint": thumbprint,
            "serial":     "",
            "not_before": "",
            "not_after":  "",
            "store":      "system",
        })

    return certs

output["certificates"] = _parse_esxi_certificates(sections.get("certificates", ""))


# ── vlans ─────────────────────────────────────────────────────────────────────

def _parse_esxi_vlans(raw):
    """
    Parse esxcli network vswitch standard list for port groups with VLAN IDs.
    The output contains nested port group blocks with VLAN ID fields.
    """
    vlans = []
    seen_ids = set()

    std_raw = subsection(raw, "Standard vSwitches")
    dvs_raw = subsection(raw, "DVS vSwitches")

    # Standard vSwitch output — port groups appear as:
    #    Portgroups: <name> (VLAN ID: <n>)   or in KV record blocks
    # Parse all records and look for VLAN-related keys
    for section_raw in (std_raw, dvs_raw):
        # Scan for VLAN ID mentions anywhere in the output
        for line in section_raw.splitlines():
            # Pattern: "VLAN ID: 100" or "VLAN: 100" or "VlanID: 100"
            vlan_match = re.search(r"VLAN\s*(?:ID)?\s*[:\s]+(\d+)", line, re.IGNORECASE)
            if vlan_match:
                vlan_id = int(vlan_match.group(1))
                if vlan_id in seen_ids:
                    continue
                seen_ids.add(vlan_id)
                # Try to extract port group name from nearby text
                name_match = re.search(r"Name\s*:\s*(.+)", line, re.IGNORECASE)
                if not name_match:
                    # Check the line itself for a name before VLAN
                    name_match = re.match(r"^\s*([^\s:][^:]+?)\s+VLAN", line, re.IGNORECASE)
                name = name_match.group(1).strip() if name_match else f"VLAN{vlan_id}"
                state = "active" if vlan_id != 0 else "active"
                vlans.append({"id": vlan_id, "name": name, "state": state})

        # Also parse structured records
        for rec in _parse_esxcli_records(section_raw):
            vlan_id_str = rec.get("VLAN ID", rec.get("VLanID", rec.get("VLAN", "")))
            if not vlan_id_str:
                continue
            try:
                vlan_id = int(vlan_id_str)
            except ValueError:
                continue
            if vlan_id in seen_ids:
                continue
            seen_ids.add(vlan_id)
            name = rec.get("Name", rec.get("Portgroup", f"VLAN{vlan_id}"))
            vlans.append({"id": vlan_id, "name": name, "state": "active"})

    # Sort by VLAN ID for stable output
    vlans.sort(key=lambda v: v["id"])
    return vlans

output["vlans"] = _parse_esxi_vlans(sections.get("vlans", ""))
