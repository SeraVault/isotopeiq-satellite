# OpenVMS Baseline Parser
# Parses output from openvms_baseline_collector.com into the canonical schema.
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
            out[k.strip().lower()] = v.strip()
    return out


def _find(pattern, text, default="", flags=0):
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else default


# ── device ────────────────────────────────────────────────────────────────────

d = kv("device")
output["device"]["hostname"]    = d.get("hostname", "")
output["device"]["fqdn"]        = d.get("fqdn", "")
output["device"]["device_type"] = d.get("device_type", "server")
output["device"]["vendor"]      = "HP" if "HP" in d.get("vendor", "").upper() else "DEC/HP/VSI"
output["device"]["model"]       = d.get("model", "")


# ── hardware ──────────────────────────────────────────────────────────────────

h = kv("hardware")
output["hardware"]["cpu_model"]  = h.get("cpu_model", "")
try:
    output["hardware"]["cpu_cores"] = int(h.get("cpu_cores", ""))
except (ValueError, TypeError):
    pass
try:
    output["hardware"]["memory_gb"] = float(h.get("memory_gb", ""))
except (ValueError, TypeError):
    pass
output["hardware"]["bios_version"]  = h.get("bios_version", "")
output["hardware"]["serial_number"] = h.get("serial_number", "")
output["hardware"]["architecture"]  = h.get("architecture", "")

virt_raw = h.get("virtualization_type", "bare-metal").lower()
output["hardware"]["virtualization_type"] = "other" if virt_raw != "bare-metal" else "bare-metal"


# ── os ────────────────────────────────────────────────────────────────────────

o = kv("os")
output["os"]["name"]    = o.get("name", "OpenVMS")
output["os"]["version"] = o.get("version", "")
output["os"]["build"]   = o.get("build", "")
output["os"]["kernel"]  = o.get("kernel", "")
output["os"]["timezone"] = o.get("timezone", "")

ntp_raw = o.get("ntp_servers", "")
output["os"]["ntp_servers"] = [s for s in ntp_raw.split("|") if s] if ntp_raw else []

ntp_sync = o.get("ntp_synced", "unknown").lower()
output["os"]["ntp_synced"] = True if ntp_sync == "yes" else (False if ntp_sync == "no" else None)


# ── network — interfaces ──────────────────────────────────────────────────────
#
# TCPIP SHOW INTERFACE output example:
#
# Interface    WE0:
#   IP=192.168.1.10  Mask=255.255.255.0  MTU=1500
#   Hardware address: 08-00-2B-1A-2C-3D
#   Line status: UP
#   ...

iface_raw = sections.get("network_interfaces", "")

def _parse_vms_interfaces(raw):
    ifaces = []
    current_if = None
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        # Interface header: "Interface    WE0:" or "WE0 - ..."
        m_hdr = re.match(r"^Interface\s+(\S+?):\s*$", line, re.IGNORECASE)
        if not m_hdr:
            m_hdr = re.match(r"^(\w+\d+)\s+-\s+", line)
        if m_hdr:
            if current_if:
                ifaces.append(current_if)
            current_if = {
                "name":         m_hdr.group(1).upper(),
                "description":  "",
                "mac":          "",
                "ipv4":         [],
                "ipv6":         [],
                "admin_status": "unknown",
                "oper_status":  "unknown",
                "speed":        "",
                "duplex":       "unknown",
                "mtu":          None,
                "port_mode":    "routed",
            }
            continue
        if current_if is None:
            continue
        # IP / mask
        m_ip = re.search(r"IP=(\d+\.\d+\.\d+\.\d+)\s+Mask=(\d+\.\d+\.\d+\.\d+)", line, re.IGNORECASE)
        if m_ip:
            ip   = m_ip.group(1)
            mask = m_ip.group(2)
            # Convert dotted mask to prefix length
            try:
                prefix = sum(bin(int(o)).count("1") for o in mask.split("."))
                current_if["ipv4"].append("{}/{}".format(ip, prefix))
            except ValueError:
                current_if["ipv4"].append(ip)
        # MAC
        m_mac = re.search(r"[Hh]ardware address[:\s]+([0-9A-Fa-f]{2}[-:][0-9A-Fa-f]{2}[-:][0-9A-Fa-f]{2}[-:][0-9A-Fa-f]{2}[-:][0-9A-Fa-f]{2}[-:][0-9A-Fa-f]{2})", line)
        if m_mac:
            current_if["mac"] = m_mac.group(1).replace("-", "").replace(":", "").lower()
        # MTU
        m_mtu = re.search(r"MTU=(\d+)", line, re.IGNORECASE)
        if m_mtu:
            current_if["mtu"] = int(m_mtu.group(1))
        # Line status / admin status
        if re.search(r"[Ll]ine status.*UP", line):
            current_if["oper_status"]  = "up"
            current_if["admin_status"] = "up"
        elif re.search(r"[Ll]ine status.*DOWN", line):
            current_if["oper_status"] = "down"
        # Description
        m_desc = re.search(r"[Dd]escription[:\s]+(.+)", line)
        if m_desc:
            current_if["description"] = m_desc.group(1).strip()
    if current_if:
        ifaces.append(current_if)
    return ifaces

output["network"]["interfaces"] = _parse_vms_interfaces(iface_raw)


# ── network — routes ──────────────────────────────────────────────────────────
#
# TCPIP SHOW ROUTE output example:
# Network         Mask            Gateway         Flags  Interface
# 0.0.0.0         0.0.0.0         192.168.1.1     UGS    WE0
# 192.168.1.0     255.255.255.0   192.168.1.10    U      WE0

route_raw = sections.get("network_routes", "")

def _parse_vms_routes(raw):
    routes = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or re.match(r"^[Nn]etwork|^-{3}", line):
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        # Skip header row
        if parts[0].lower() == "network":
            continue
        dst  = parts[0]
        mask = parts[1] if len(parts) > 1 else ""
        gw   = parts[2] if len(parts) > 2 else ""
        dev  = parts[4] if len(parts) > 4 else ""
        # Build CIDR notation
        if mask and mask != "0.0.0.0":
            try:
                prefix = sum(bin(int(o)).count("1") for o in mask.split("."))
                dst = "{}/{}".format(dst, prefix)
            except ValueError:
                pass
        elif dst == "0.0.0.0":
            dst = "0.0.0.0/0"
        routes.append({
            "destination": dst,
            "gateway":     gw,
            "interface":   dev,
            "metric":      None,
        })
    return routes

output["network"]["routes"] = _parse_vms_routes(route_raw)

for r in output["network"]["routes"]:
    if r.get("destination") in ("0.0.0.0/0", "0.0.0.0"):
        output["network"]["default_gateway"] = r.get("gateway", "")
        break


# ── network — DNS ─────────────────────────────────────────────────────────────
#
# TCPIP SHOW NAME_SERVICE output includes lines like:
#   Domain:     example.com
#   Nameserver: 192.168.1.53

dns_raw = sections.get("network_dns", "")
dns_servers = []
for line in dns_raw.splitlines():
    m = re.search(r"[Nn]ameserver[:\s]+(\d+\.\d+\.\d+\.\d+)", line)
    if m:
        dns_servers.append(m.group(1))
output["network"]["dns_servers"] = dns_servers


# ── users ─────────────────────────────────────────────────────────────────────
#
# AUTHORIZE SHOW * /FULL produces blocks like:
#
# Username: SMITH                          Owner:  John Smith
# Account:  STAFF                          UIC:    [STAFF,SMITH] ([300,012])
# CLI:      DCL                            Tables: DCLTABLES
# Default:  DUA1:[SMITH]
# Login Flags: Lockout
# Primary days: Mon Tue Wed Thu Fri
# Pwd minimum: 6                           Modified: 19-JAN-2024
# Login Failures: 0                        Max Failures: 3
# ...

users_raw = sections.get("users", "")

def _parse_vms_users(raw):
    users = []
    blocks = re.split(r"(?=^Username:)", raw, flags=re.MULTILINE)
    for block in blocks:
        if not block.strip():
            continue
        uname    = _find(r"^Username:\s+(\S+)", block, flags=re.MULTILINE).upper()
        if not uname:
            continue
        uic_m    = re.search(r"UIC:\s+\[([^\]]+)\]\s+\(\[([^\]]+)\]\)", block)
        uic_str  = uic_m.group(2) if uic_m else ""        # numeric [group,member]
        uic_name = uic_m.group(1) if uic_m else ""        # named   [STAFF,SMITH]
        # uid = numeric UIC as string e.g. "300,012"
        uid      = uic_str.strip("[]") if uic_str else uic_name.strip("[]")
        # group = first element of named UIC
        group    = uic_name.split(",")[0].strip("[]") if uic_name else ""
        home     = _find(r"^Default:\s+(\S+)", block, flags=re.MULTILINE)
        cli      = _find(r"^CLI:\s+(\S+)", block, flags=re.MULTILINE)
        account  = _find(r"^Account:\s+(\S+)", block, flags=re.MULTILINE)
        flags    = _find(r"^Login Flags:\s*(.*)", block, flags=re.MULTILINE).upper()
        disabled = "LOCKOUT" in flags or "DISUSER" in flags or "CAPTIVE" in flags
        pwd_mod  = _find(r"Modified:\s+(\d{2}-\w{3}-\d{4})", block)
        last_int = _find(r"Last Login:\s+(\d{2}-\w{3}-\d{4}\s+\d{2}:\d{2}:\d{2}\.\d+)", block)
        # Privileges — SYSPRV, BYPASS, TMPMBX, etc.
        privs    = ""
        priv_m   = re.search(r"Privileges?:\s*(.*?)(?=\n[A-Z]|\Z)", block, re.DOTALL)
        if priv_m:
            privs = " ".join(priv_m.group(1).split())
        users.append({
            "username":          uname,
            "uid":               uid,
            "groups":            [group] if group else [],
            "home":              home,
            "shell":             cli,
            "disabled":          disabled,
            "password_last_set": pwd_mod,
            "last_login":        last_int,
            "sudo_privileges":   privs,
        })
    return users

output["users"] = _parse_vms_users(users_raw)


# ── groups (rights identifiers) ───────────────────────────────────────────────
#
# AUTHORIZE SHOW/RIGHTS * produces lines like:
#   STAFF                    [000300,*] General
#   SMITH                    [000300,000012] General

rights_raw = sections.get("groups", "")

def _parse_vms_rights(raw):
    groups = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("Identifier") or line.startswith("-"):
            continue
        m = re.match(r"^(\S+)\s+\[([^\]]+)\]\s+(\w+)", line)
        if not m:
            continue
        ident = m.group(1)
        uic   = m.group(2)
        kind  = m.group(3)
        # Group identifiers have wildcard member: [GRP,*]
        if "," in uic:
            grp_part, mem_part = uic.split(",", 1)
            if mem_part.strip() == "*":
                # This is a group identifier
                if ident not in groups:
                    groups[ident] = {"group_name": ident, "gid": grp_part.strip(), "members": []}
    # Associate users with groups via their UIC group
    for user in output.get("users", []):
        for grp in user.get("groups", []):
            if grp in groups:
                groups[grp]["members"].append(user["username"])
    return list(groups.values())

output["groups"] = _parse_vms_rights(rights_raw)


# ── packages (PCSI products) ──────────────────────────────────────────────────
#
# PRODUCT SHOW PRODUCT */FULL produces blocks like:
#
# Product:    OPENVMS V8.4-2L3              Patch Level: None
# Producer:   DEC
# Release date: 28-SEP-2015
# Kit type:   Full Installation
# ...

packages_raw = sections.get("packages", "")

def _parse_vms_packages(raw):
    pkgs = []
    blocks = re.split(r"(?=^Product:)", raw, flags=re.MULTILINE)
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        name_ver = _find(r"^Product:\s+(.+?)(?:\s+Patch Level:.*)?$", block, flags=re.MULTILINE)
        if not name_ver:
            continue
        # Split name and version: "OPENVMS V8.4-2L3" -> name=OPENVMS, ver=V8.4-2L3
        parts = name_ver.split()
        name    = parts[0] if parts else name_ver
        version = parts[1] if len(parts) > 1 else ""
        vendor  = _find(r"^Producer:\s+(\S+)", block, flags=re.MULTILINE)
        date    = _find(r"^[Rr]elease date:\s+(\S+)", block, flags=re.MULTILINE)
        pkgs.append({
            "name":         name,
            "version":      version,
            "vendor":       vendor,
            "install_date": date,
            "source":       "other",
        })
    return pkgs

output["packages"] = _parse_vms_packages(packages_raw)


# ── services (detached processes from SHOW SYSTEM) ────────────────────────────
#
# SHOW SYSTEM /FULL output (simplified):
#  Pid    Process Name    State   Pri I/O   CPU        PC       PSW
# 00000201 SWAPPER         HIB      16  ...
# 00000204 ERRFMT          HIB      8   ...
# 00000209 JOB_CONTROL     HIB      10  ...

services_raw = sections.get("services", "")

def _parse_vms_services(raw):
    svcs = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        # Process table: pid(8hex) name state ...
        m = re.match(r"^([0-9A-Fa-f]{8})\s+(\S+)\s+(\w+)\s+\d+", line)
        if not m:
            continue
        pid   = m.group(1)
        pname = m.group(2)
        state = m.group(3).lower()
        # Deduplicate by name; keep first occurrence (lowest PID = original)
        if pname not in svcs:
            status  = "running" if state in ("cur", "com", "hib", "lef", "lef+") else "stopped"
            svcs[pname] = {
                "name":    pname,
                "status":  status,
                "startup": "enabled",
            }
    return list(svcs.values())

output["services"] = _parse_vms_services(services_raw)


# ── filesystem ────────────────────────────────────────────────────────────────
#
# SHOW DEVICE /MOUNTED /FULL output includes blocks per device.
# Relevant lines:
#   Device $1$DKA100: (ALPHA)
#     Volume label: SYSTEM
#     Total blocks: 8388608, Used: 3145728, Free: 5242880

fs_raw = sections.get("filesystem", "")

def _parse_vms_filesystem(raw):
    mounts = []
    current = None
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        # Device line: "Device $1$DKA100: (ALPHA)" or "DKA100:"
        m_dev = re.match(r"^(?:Device\s+)?(\$\d\$[\w]+:|[A-Z]{2,4}\d+:)\s*", line, re.IGNORECASE)
        if m_dev:
            if current and current.get("mount"):
                mounts.append(current)
            current = {
                "mount":         m_dev.group(1).rstrip(":"),
                "type":          "ODS-2",
                "size_gb":       None,
                "free_gb":       None,
                "mount_options": [],
                "suid_files":    [],
            }
            continue
        if current is None:
            continue
        # Volume label → use as mount name suffix
        m_lbl = re.search(r"[Vv]olume [Ll]abel[:\s]+(\S+)", line)
        if m_lbl:
            current["mount"] = m_lbl.group(1)
        # Filesystem type (ODS-2 or ODS-5)
        if "ODS-5" in line.upper():
            current["type"] = "ODS-5"
        elif "ODS-2" in line.upper():
            current["type"] = "ODS-2"
        # Blocks: 1 block = 512 bytes
        m_blocks = re.search(r"[Tt]otal [Bb]locks:\s+([\d,]+),\s*[Uu]sed:\s*([\d,]+),\s*[Ff]ree:\s*([\d,]+)", line)
        if m_blocks:
            def _blocks_to_gb(s):
                return round(int(s.replace(",", "")) * 512 / 1024**3, 2)
            current["size_gb"] = _blocks_to_gb(m_blocks.group(1))
            current["free_gb"] = _blocks_to_gb(m_blocks.group(3))
        # Mount options: "NOWRITE", "FOREIGN", etc.
        m_opts = re.search(r"[Mm]ount [Ff]lags:\s*(.*)", line)
        if m_opts:
            current["mount_options"] = [o.strip() for o in m_opts.group(1).split(",") if o.strip()]
    if current and current.get("mount"):
        mounts.append(current)
    return mounts

output["filesystem"] = _parse_vms_filesystem(fs_raw)


# ── security ──────────────────────────────────────────────────────────────────

security_raw = sections.get("security", "")

# Audit logging
audit_line = _find(r"audit_journal=(\w+)", security_raw, "disabled")
output["security"]["audit_logging_enabled"] = audit_line.lower() == "enabled"

# Firewall — VMS TCP/IP has a packet filter; check TCPIP SHOW FILTER or ipfilter
output["security"]["firewall_enabled"] = bool(
    re.search(r"[Pp]acket [Ff]ilter|ipfilter|IPFILTER", security_raw)
)

# Secure boot indicator (HPVM / integrity only)
output["security"]["secure_boot"] = bool(
    re.search(r"[Ss]ecure [Bb]oot|UEFI.*[Ss]ecure", security_raw)
)

# Password policy from AUTHORIZE SHOW DEFAULT block embedded in security section
uafdef_raw = security_raw

def _parse_vms_password_policy(raw):
    policy = {}
    m_min = re.search(r"[Pp]wd\s+[Mm]inimum[:\s]+(\d+)", raw)
    if m_min:
        policy["min_length"] = int(m_min.group(1))
    m_life = re.search(r"[Pp]wd\s+[Ll]ifetime[:\s]+([\d-]+\s+\S+)", raw)
    if m_life:
        # Convert VMS delta time (e.g. "90 00:00:00.00") to days
        d_m = re.match(r"(\d+)", m_life.group(1))
        if d_m:
            policy["max_age_days"] = int(d_m.group(1))
    m_fail = re.search(r"[Mm]ax\s+[Ff]ailures[:\s]+(\d+)", raw)
    if m_fail:
        policy["lockout_threshold"] = int(m_fail.group(1))
    return policy

policy = _parse_vms_password_policy(uafdef_raw)
if policy:
    output["security"]["password_policy"] = policy


# ── sysctl (SYSGEN parameters) ────────────────────────────────────────────────
#
# MCR SYSGEN SHOW/ALL output:
#   Parameter Name    Current     Default    Min        Max      Unit  Dynamic
#   ----------------  ----------  ---------  ---------  -------  ----  -------
#   GBLPAGES          200000      200000     ...

sysgen_raw = sections.get("sysctl", "")
output["sysctl"] = []
for line in sysgen_raw.splitlines():
    line = line.strip()
    if not line or re.match(r"^[-=\s]*$", line) or re.match(r"^Parameter", line, re.IGNORECASE):
        continue
    parts = line.split()
    if len(parts) < 2:
        continue
    output["sysctl"].append({"key": parts[0], "value": parts[1]})


# ── scheduled_tasks (batch queues) ───────────────────────────────────────────
#
# SHOW QUEUE /BATCH /FULL /ALL_JOBS output:
#   Batch queue SYS$BATCH, available, on ALPHA
#     /BASE_PRIORITY=4 /JOB_LIMIT=4 /WSDEFAULT=4096
#     Entry  Jobname          Username     Status
#     -----  ---------------  -----------  -------
#       201  BACKUP           SYSTEM       Holding
#            /AFTER=01-JAN-2024 00:00 /NOTIFY
#            File: SYS$MANAGER:BACKUP.COM

queues_raw = sections.get("scheduled_tasks", "")
output["scheduled_tasks"] = []

def _parse_vms_queues(raw):
    tasks = []
    current_queue = ""
    current_job   = None
    for line in raw.splitlines():
        line_strip = line.strip()
        if not line_strip:
            continue
        # Queue header
        m_q = re.match(r"^[Bb]atch queue\s+(\S+),", line_strip)
        if m_q:
            current_queue = m_q.group(1)
            continue
        # Job entry line: "  201  BACKUP  SYSTEM  Holding"
        m_job = re.match(r"^\s+(\d+)\s+(\S+)\s+(\S+)\s+(\w+)", line)
        if m_job:
            if current_job:
                tasks.append(current_job)
            current_job = {
                "name":     m_job.group(2),
                "type":     "other",
                "command":  "",
                "schedule": "",
                "user":     m_job.group(3),
                "enabled":  m_job.group(4).lower() not in ("held", "holding"),
            }
            continue
        if current_job is None:
            continue
        # Command file
        m_file = re.search(r"[Ff]ile:\s*(\S+)", line_strip)
        if m_file:
            current_job["command"] = m_file.group(1)
        # Schedule /AFTER= or /REPEAT=
        m_after = re.search(r"/AFTER=(\S+\s+\S+)", line_strip)
        if m_after:
            current_job["schedule"] = "after " + m_after.group(1)
        m_rep = re.search(r"/REPEAT=(\S+)", line_strip)
        if m_rep:
            current_job["schedule"] = "repeat " + m_rep.group(1)
    if current_job:
        tasks.append(current_job)
    return tasks

output["scheduled_tasks"] = _parse_vms_queues(queues_raw)


# ── listening_services (TCPIP SHOW SERVICE) ───────────────────────────────────
#
# TCPIP SHOW SERVICE output:
# Service         Port  Proto  Process           Address  State
# --------        ----  -----  -------           -------  -----
# FTP             21    TCP    TCPIP$FTP         0.0.0.0  Enabled
# SSH             22    TCP    TCPIP$SSH         0.0.0.0  Enabled
# TELNET          23    TCP    TCPIP$TELNET      0.0.0.0  Enabled

svc_raw = sections.get("listening_services", "")
output["listening_services"] = []
for line in svc_raw.splitlines():
    line = line.strip()
    if not line or re.match(r"^[Ss]ervice|^-{3}", line):
        continue
    parts = line.split()
    if len(parts) < 5:
        continue
    svc_name = parts[0]
    try:
        port = int(parts[1])
    except ValueError:
        continue
    proto_raw = parts[2].lower()
    proto = proto_raw if proto_raw in ("tcp", "udp") else "tcp"
    state = parts[4].lower() if len(parts) > 4 else ""
    output["listening_services"].append({
        "protocol":      proto,
        "local_address": "0.0.0.0",
        "port":          port,
        "process_name":  svc_name,
        "pid":           None,
        "user":          "",
    })
    if state == "enabled":
        output["network"]["open_ports"].append(port)


# ── logging_targets (syslog.conf) ─────────────────────────────────────────────
#
# TCPIP$ETC:SYSLOG.CONF lines like:
#   *.info    @192.168.1.100
#   kern.err  @syslog.example.com:514

syslog_raw = sections.get("logging_targets", "")
output["logging_targets"] = []
for line in syslog_raw.splitlines():
    line = line.strip()
    if not line or line.startswith("!") or line.startswith("#"):
        continue
    m = re.search(r"(@@?)([^\s:@]+):?(\d+)?", line)
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


# ── ssh_config ────────────────────────────────────────────────────────────────
#
# HP SSH / VSI SSH sshd config keys are similar to OpenSSH but may use
# VMS-style values (e.g. AllowUsers is comma-delimited)

ssh_cfg = {}
bool_map = {"yes": True, "no": False, "true": True, "false": False}

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
        ssh_cfg["allow_users"] = re.split(r"[,\s]+", val)
    elif key == "denyusers":
        ssh_cfg["deny_users"] = re.split(r"[,\s]+", val)

if ssh_cfg:
    output["ssh_config"] = ssh_cfg


# ── snmp ──────────────────────────────────────────────────────────────────────
#
# TCPIP SHOW SNMP output:
#   Community:  public      Access: Read-Only   Status: Enabled
#   Trap host:  192.168.1.5
#   Location:   Server Room
#   Contact:    admin@example.com

snmp_raw = sections.get("snmp", "")
snmp_enabled   = bool(snmp_raw.strip())
communities    = re.findall(r"[Cc]ommunity[:\s]+(\S+)", snmp_raw)
trap_targets   = re.findall(r"[Tt]rap [Hh]ost[:\s]+(\S+)", snmp_raw)
snmp_location  = _find(r"[Ll]ocation[:\s]+(.+)", snmp_raw)
snmp_contact   = _find(r"[Cc]ontact[:\s]+(.+)", snmp_raw)
snmp_versions  = ["v2c"] if communities else []

output["snmp"] = {
    "enabled":      snmp_enabled,
    "versions":     snmp_versions,
    "communities":  communities,
    "v3_users":     [],
    "trap_targets": trap_targets,
    "location":     snmp_location,
    "contact":      snmp_contact,
}


# ── shares (NFS exports) ──────────────────────────────────────────────────────
#
# TCPIP SHOW NFS/SERVER/EXPORT output:
#   Export Path     Client         Access  Options
#   DUA0:[EXPORT]   *              rw      root_squash

shares_raw = sections.get("shares", "")
output["shares"] = []
for line in shares_raw.splitlines():
    line = line.strip()
    if not line or re.match(r"^[Ee]xport|^-{3}", line):
        continue
    parts = line.split()
    if len(parts) < 3:
        continue
    path     = parts[0]
    access   = parts[2].lower() if len(parts) > 2 else "rw"
    read_only = access == "ro"
    output["shares"].append({
        "name":        path,
        "type":        "nfs",
        "path":        path,
        "comment":     "",
        "permissions": access,
        "read_only":   read_only,
        "enabled":     True,
    })


# ── certificates ─────────────────────────────────────────────────────────────
#
# CRYPTO SHOW CERTIFICATE /FULL output:
#   Certificate:
#     Subject:     CN=ALPHA.EXAMPLE.COM
#     Issuer:      CN=Example CA
#     Serial:      01:23:45:67
#     Valid from:  01-JAN-2024 00:00:00.00
#     Valid until: 01-JAN-2026 00:00:00.00

certs_raw = sections.get("certificates", "")
output["certificates"] = []

def _parse_vms_certs(raw):
    certs = []
    blocks = re.split(r"(?=^\s*[Cc]ertificate:)", raw, flags=re.MULTILINE)
    for block in blocks:
        if not block.strip():
            continue
        subject  = _find(r"[Ss]ubject[:\s]+(.+)", block)
        issuer   = _find(r"[Ii]ssuer[:\s]+(.+)", block)
        serial   = _find(r"[Ss]erial[:\s]+(.+)", block)
        thumb    = _find(r"(?:[Ff]ingerprint|[Tt]humbprint)[:\s]+(.+)", block)
        not_bef  = _find(r"[Vv]alid from[:\s]+(.+)", block)
        not_aft  = _find(r"[Vv]alid until[:\s]+(.+)", block)
        if not subject and not thumb:
            continue
        certs.append({
            "subject":    subject,
            "issuer":     issuer,
            "thumbprint": thumb or serial,
            "serial":     serial,
            "not_before": not_bef,
            "not_after":  not_aft,
            "store":      "system",
        })
    return certs

output["certificates"] = _parse_vms_certs(certs_raw)
