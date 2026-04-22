# DEC Terminal Server (DECServer) Baseline Parser
# Parses output from decserver_baseline_collector.py into the canonical schema.
#
# `result` — raw string output from the collector
# `output` — canonical dict to populate (pre-filled with empty structure)
#
# Supported DECServer product lines:
#   90L / 90L+ / 90M / 90TL / 200 / 300 / 700 / 900 / 5000 series
#
# --- Output mapping ---
#   server        → device, hardware, os, network (IP config)
#   ports         → network (interfaces / serial ports)
#   services      → services
#   users         → users
#   authentication→ security (auth method, RADIUS/TACACS servers)
#   logging       → logging_targets
#   snmp          → security (SNMP community / trap config)
#   ip_config     → network (supplements server section)
#   ip_routes     → not mapped (no equivalent canonical field)
#   protocol      → not mapped (LAT/Telnet protocol tuning is not in schema)

import re

SEP = '---ISOTOPEIQ---'

# ── Split raw output into named sections ──────────────────────────────────────

sections: dict[str, str] = {}
current = None
buf: list[str] = []

for _line in result.splitlines():
    if _line.startswith(SEP + '[') and _line.endswith(']'):
        if current is not None:
            sections[current] = '\n'.join(buf).strip()
        current = _line[len(SEP) + 1:-1]
        buf = []
    elif current is not None:
        buf.append(_line)

if current and current != 'END':
    sections[current] = '\n'.join(buf).strip()


def lines(section: str) -> list[str]:
    return [l for l in sections.get(section, '').splitlines() if l.strip()]


# ── Key: value helper ─────────────────────────────────────────────────────────
# DECServer SHOW commands use fixed-width "Key:   Value" formatting.
# Build a flat dict of all key→value pairs from a text block.

def _kv(text: str) -> dict[str, str]:
    """Return a dict of all  'Key:  Value'  pairs in ``text``."""
    d: dict[str, str] = {}
    for ln in text.splitlines():
        m = re.match(r'^\s*([A-Za-z][A-Za-z0-9 /]+?):\s*(.*)', ln)
        if m:
            key = re.sub(r'\s+', '_', m.group(1).strip().lower())
            val = m.group(2).strip()
            d[key] = val
    return d


def _find(pattern: str, text: str, default: str = '', flags: int = 0) -> str:
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else default


# ── device / hardware / os — from SHOW SERVER ─────────────────────────────────
#
# Typical SHOW SERVER header line (varies by model):
#   "DECserver 90L+ SERVER V3.1 BL44-10 ROM V2.0 BL44-03"
# or
#   "DEC server 700 V1.0"

server_raw = sections.get('server', '')
kv = _kv(server_raw)

# --- First line carries model + firmware version ---
first_line = server_raw.splitlines()[0].strip() if server_raw else ''

# Model: everything before the first "V<digit>" version token
model_m = re.match(r'^(DECserver\s+\S+|DEC\s+server\s+\S+)', first_line, re.IGNORECASE)
model = model_m.group(1).strip() if model_m else 'DECserver'

# Firmware version: first "V<x>.<y>[...]" token  e.g. V3.1, V1.0
fw_ver = _find(r'\bV(\d+\.\d+\S*)', first_line)

# Server / hostname
srv_name = kv.get('server_name', kv.get('name', ''))

# Hardware (MAC) address: "AA-00-04-00-1C-2A"
hw_addr  = kv.get('hardware_address', kv.get('hardware_addr', ''))

# IP address (may also appear later in ip_config section)
ip_addr  = kv.get('ip_address', '')
ip_mask  = kv.get('ip_subnet_mask', kv.get('subnet_mask', ''))
ip_gw    = kv.get('ip_gateway_address', kv.get('gateway_address', kv.get('ip_gateway', '')))

# NTP
ntp_raw  = kv.get('ntp_servers', kv.get('ntp_server', ''))
ntp_list = [s.strip() for s in re.split(r'[,\s]+', ntp_raw) if s.strip() and s.strip() != '(None)']

# Timezone offset: "Timezone:  0" (minutes offset from UTC)
tz_val   = kv.get('server_timezone', kv.get('timezone', ''))
tz_str   = 'UTC' if tz_val in ('0', '00', '') else f'UTC{tz_val}'

# Uptime
uptime = kv.get('uptime', '')

output['device']['hostname']    = srv_name or _hostname if '_hostname' in dir() else srv_name
output['device']['fqdn']        = srv_name
output['device']['device_type'] = 'network'
output['device']['vendor']      = 'Digital Equipment Corporation'
output['device']['model']       = model

output['hardware']['serial_number']       = kv.get('serial_number', kv.get('serial', ''))
output['hardware']['architecture']        = 'mips'    # all DECServer models used MIPS-family cores
output['hardware']['virtualization_type'] = 'bare-metal'

output['os']['name']        = model
output['os']['version']     = fw_ver
output['os']['build']       = _find(r'\bBL(\S+)', first_line)  # build label e.g. BL44-10
output['os']['kernel']      = fw_ver
output['os']['ntp_servers'] = ntp_list
output['os']['timezone']    = tz_str
output['os']['ntp_synced']  = None   # DECServer reports NTP state only via SHOW NTP (not universal)

# ── network — management IP from SHOW SERVER / SHOW IP ───────────────────────

ip_raw = sections.get('ip_config', '')
if ip_raw:
    ip_kv   = _kv(ip_raw)
    ip_addr = ip_kv.get('ip_address', ip_addr)
    ip_mask = ip_kv.get('subnet_mask', ip_kv.get('ip_subnet_mask', ip_mask))
    ip_gw   = ip_kv.get('gateway', ip_kv.get('ip_gateway_address', ip_gw))

if ip_addr:
    # Express as CIDR if mask is available, otherwise plain address
    cidr = ip_addr
    if ip_mask:
        try:
            import ipaddress
            iface = ipaddress.IPv4Interface(f'{ip_addr}/{ip_mask}')
            cidr  = str(iface.with_prefixlen)
        except ValueError:
            pass

    output['network']['interfaces'].append({
        'name':          'mgmt',
        'description':   'Management interface',
        'admin_status':  'up',
        'oper_status':   'up',
        'mac_address':   hw_addr,
        'mtu':           None,
        'speed':         None,
        'duplex':        'unknown',
        'port_mode':     'routed',
        'ipv4':          [cidr],
        'ipv6':          [],
    })

if ip_gw:
    output['network']['default_gateway'] = ip_gw

# ── network — serial / AUX ports from SHOW PORT ALL CHARACTERISTICS ───────────
#
# Each port block starts with "Port N Characteristics:" and uses "Key: Value"
# format.  We represent each port as a network interface with the port type
# as the description.
#
# Example block:
#   Port 1 Characteristics:
#     Access:       Local
#     Baud Rate:    9600
#     Type:         VT100
#     Port Name:    PRINTER
#     ...

ports_raw = sections.get('ports', '')

# Split into per-port blocks on "Port N Characteristics:"
port_blocks = re.split(r'(?=^\s*Port\s+\d+\s+Characteristics:)', ports_raw, flags=re.MULTILINE)

for block in port_blocks:
    if not block.strip():
        continue
    port_hdr = re.match(r'\s*Port\s+(\d+)\s+Characteristics:', block)
    if not port_hdr:
        continue
    pnum   = port_hdr.group(1)
    pkv    = _kv(block)
    pname  = pkv.get('port_name', f'port{pnum}')
    if pname in ('(No Name)', '(None)', ''):
        pname = f'port{pnum}'
    baud   = pkv.get('baud_rate', '')
    access = pkv.get('access', '')
    ptype  = pkv.get('type', '')

    output['network']['interfaces'].append({
        'name':          pname,
        'description':   f'Serial port {pnum} — access={access} type={ptype}',
        'admin_status':  'up',
        'oper_status':   'unknown',
        'mac_address':   None,
        'mtu':           None,
        'speed':         baud,
        'duplex':        'unknown',
        'port_mode':     'access',
        'ipv4':          [],
        'ipv6':          [],
    })

# ── services — from SHOW SERVICE ALL ─────────────────────────────────────────
#
# Each service block starts with "Service Name: <name>" and may have
# Status, Type, Identification, Ports fields.
#
# Example:
#   Service Name:     MYSERVER
#     Status:         Available
#     Type:           Terminal
#     Identification: My DECServer
#     Ports:          1-8

services_raw = sections.get('services', '')

svc_blocks = re.split(r'(?=^\s*Service Name:)', services_raw, flags=re.MULTILINE | re.IGNORECASE)
for block in svc_blocks:
    if not block.strip():
        continue
    skv    = _kv(block)
    sname  = skv.get('service_name', '')
    if not sname or sname == '(None)':
        continue
    sstatus = skv.get('status', 'unknown').lower()
    startup = 'enabled' if sstatus in ('available', 'enabled') else 'disabled'
    output['services'].append({'name': sname, 'startup': startup})

# ── users — from SHOW USER ALL ────────────────────────────────────────────────
#
# Example:
#   Username:     ADMIN
#     Access:     All
#     Privilege:  Privileged
#   Username:     OPERATOR
#     Privilege:  Non-privileged

users_raw = sections.get('users', '')

user_blocks = re.split(r'(?=^\s*Username:)', users_raw, flags=re.MULTILINE | re.IGNORECASE)
for block in user_blocks:
    if not block.strip():
        continue
    ukv      = _kv(block)
    uname    = ukv.get('username', '')
    if not uname or uname == '(None)':
        continue
    priv     = ukv.get('privilege', '').lower()
    groups   = 'privileged' if 'privileged' in priv and 'non' not in priv else 'user'
    output['users'].append({
        'username':             uname,
        'uid':                  None,
        'home':                 '',
        'shell':                '',
        'groups':               groups,
        'password_last_changed': '',
        'last_login':           '',
        'sudo_access':          1 if groups == 'privileged' else 0,
    })

# ── security — from SHOW AUTHENTICATION + SHOW SNMP ──────────────────────────
#
# SHOW AUTHENTICATION example:
#   Authentication:     RADIUS
#   RADIUS Server 1 Address: 192.168.1.200
#   RADIUS Server 1 Port:    1812
#   RADIUS Server 2 Address: (None)
#
# SHOW SNMP example:
#   SNMP:           Enabled
#   Community:      public (Read-Only)
#   Traps:          Enabled
#   Trap Host:      192.168.1.50

auth_raw = sections.get('authentication', '')
auth_kv  = _kv(auth_raw)

snmp_raw = sections.get('snmp', '')
snmp_kv  = _kv(snmp_raw)

# Authentication method (RADIUS / KERBEROS / LOCAL)
auth_method = auth_kv.get('authentication', 'local').upper()
if auth_method == '(NONE)' or not auth_method:
    auth_method = 'local'

# RADIUS servers — keys like "radius_server_1_address", "radius_server_2_address"
radius_servers = [v for k, v in auth_kv.items()
                  if 'radius' in k and 'address' in k and v and v != '(None)']

output['security']['selinux']   = 'disabled'   # not applicable
output['security']['apparmor']  = 'disabled'   # not applicable
output['security']['firewall']  = 'unknown'    # not applicable at OS level

# Encode auth info via audit/password policy fields available in schema
if radius_servers:
    output['security']['password_policy'] = (
        f'auth={auth_method} radius={",".join(radius_servers)}'
    )
else:
    output['security']['password_policy'] = f'auth={auth_method}'

# SNMP
snmp_enabled   = snmp_kv.get('snmp', '').lower() == 'enabled'
snmp_community = snmp_kv.get('community', '')
snmp_trap_host = snmp_kv.get('trap_host', snmp_kv.get('trap_destination', ''))

# Aggregate SNMP info into security field (real schema has no SNMP sub-section)
snmp_summary = []
if snmp_enabled:
    snmp_summary.append(f'snmp=enabled community={snmp_community}')
    if snmp_trap_host and snmp_trap_host != '(None)':
        snmp_summary.append(f'trap_host={snmp_trap_host}')
else:
    snmp_summary.append('snmp=disabled')

if snmp_summary:
    existing = output['security'].get('password_policy', '')
    output['security']['password_policy'] = (
        (existing + ' ' if existing else '') + ' '.join(snmp_summary)
    ).strip()

# ── logging_targets — from SHOW LOGGING ───────────────────────────────────────
#
# Example:
#   Logging:         Enabled
#   Log Server:      192.168.1.50
#   Log Protocol:    UDP
#   Log Port:        514

log_raw = sections.get('logging', '')
log_kv  = _kv(log_raw)

log_enabled = log_kv.get('logging', '').lower() == 'enabled'
log_server  = log_kv.get('log_server', log_kv.get('syslog_host', log_kv.get('server', '')))
log_proto   = log_kv.get('log_protocol', 'UDP').upper()
log_port    = log_kv.get('log_port', '514')

if log_enabled and log_server and log_server != '(None)':
    output['logging_targets'].append(
        f'{log_proto.lower()}://{log_server}:{log_port}'
    )
