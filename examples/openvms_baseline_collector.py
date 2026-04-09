"""
OpenVMS Baseline Collector
===========================
Runs on: SERVER  (set "Runs On" to Server in the Script Editor)

This script runs on the Satellite server and connects outbound to the device
via Telnet. It is NOT pushed to the device — OpenVMS DCL cannot be uploaded
and executed remotely without a third-party agent.

The `device` variable is provided by the Satellite execution context and gives
access to the device record and its linked credential — no placeholders needed.

Compatibility: OpenVMS VAX 6.x+, Alpha 7.x+, Integrity (IA-64) 8.x+

Privilege requirements:
    Most sections run as any user. The following produce richer output with
    SYSPRV, BYPASS, or when logged in as SYSTEM:
        users, groups, security, scheduled_tasks, sysctl
"""

import re
import telnetlib
import time

# ── Resolve credentials from the device record ────────────────────────────────

cred = device.credential  # noqa: F821 — `device` injected by Satellite
if cred:
    _username = cred.username or ''
    _password = cred.password or ''
else:
    _username = device.username or ''
    _password = device.password or ''

_hostname = device.hostname
_port     = device.port or 23

CONNECT_TIMEOUT = 30   # seconds for initial TCP connection
LOGIN_TIMEOUT   = 15   # seconds to wait for login prompts
CMD_TIMEOUT     = 60   # seconds to wait for each command to complete

SEP = '---ISOTOPEIQ---'

# OpenVMS DCL prompt: "$ " possibly preceded by the username or node name
_PROMPT_RE = re.compile(rb'\$\s*$', re.MULTILINE)
_LOGIN_RE  = re.compile(rb'[Uu]sername:', re.IGNORECASE)
_PASS_RE   = re.compile(rb'[Pp]assword:', re.IGNORECASE)

# ── Connect and authenticate ──────────────────────────────────────────────────

tn = telnetlib.Telnet(_hostname, _port, timeout=CONNECT_TIMEOUT)

def _read_until_any(patterns, timeout):
    """Wait for any of the compiled regex patterns; return accumulated bytes."""
    index, _, data = tn.expect(patterns, timeout=timeout)
    return index, data

# Wait for username prompt or DCL prompt (already logged in)
idx, buf = _read_until_any([_LOGIN_RE, _PASS_RE, _PROMPT_RE], LOGIN_TIMEOUT)

if idx == 0:
    # Username prompt
    tn.write((_username + '\r\n').encode())
    idx2, data = _read_until_any([_PASS_RE, _PROMPT_RE], LOGIN_TIMEOUT)
    buf += data
    if idx2 == 0:
        tn.write((_password + '\r\n').encode())
        _, data = _read_until_any([_PROMPT_RE], LOGIN_TIMEOUT)
        buf += data
elif idx == 1:
    # Password-only prompt
    tn.write((_password + '\r\n').encode())
    _, data = _read_until_any([_PROMPT_RE], LOGIN_TIMEOUT)
    buf += data
# idx == 2: already at DCL prompt

# ── Send a DCL command and return its output ──────────────────────────────────

def _send(cmd: str, timeout: float = CMD_TIMEOUT) -> str:
    """Send a DCL command and return everything up to the next $ prompt."""
    tn.write((cmd + '\r\n').encode())
    _, data = _read_until_any([_PROMPT_RE], timeout)
    text = data.decode('utf-8', errors='replace')
    # Strip the echoed command (first line) and trailing prompt (last line)
    lines = text.splitlines()
    if lines and cmd.strip() in lines[0]:
        lines = lines[1:]
    if lines and _PROMPT_RE.search(lines[-1].encode()):
        lines = lines[:-1]
    return '\n'.join(lines)

# Suppress DCL error formatting so stdout stays clean
_send('SET MESSAGE/NOFACILITY/NOIDENTIFICATION/NOSEVERITY/NOTEXT')
_send('ON ERROR THEN CONTINUE')
_send('ON WARNING THEN CONTINUE')

# ── Collect sections ──────────────────────────────────────────────────────────
# Each entry is (section_name, list_of_dcl_commands).
# Multiple commands per section have their output concatenated under one header.

SECTIONS = [
    ('device', [
        'WRITE SYS$OUTPUT "hostname=" + F$GETSYI("NODENAME")',
        'WRITE SYS$OUTPUT "fqdn=" + F$GETSYI("NODENAME")',
        'WRITE SYS$OUTPUT "device_type=server"',
        'WRITE SYS$OUTPUT "vendor=" + F$GETSYI("NODE_SWVERS")',
        'WRITE SYS$OUTPUT "model=" + F$GETSYI("HW_NAME")',
    ]),
    ('hardware', [
        'WRITE SYS$OUTPUT "cpu_model=" + F$GETSYI("HW_NAME")',
        'WRITE SYS$OUTPUT "cpu_cores=" + F$STRING(F$GETSYI("ACTIVECPU_CNT"))',
        'WRITE SYS$OUTPUT "memory_gb=" + F$STRING(F$INTEGER(F$GETSYI("MEMSIZE") * 512 / 1048576) / 1024)',
        'WRITE SYS$OUTPUT "bios_version=" + F$GETSYI("SID")',
        'WRITE SYS$OUTPUT "serial_number=" + F$GETSYI("SER_NUM")',
        'WRITE SYS$OUTPUT "architecture=" + F$GETSYI("ARCH_NAME")',
    ]),
    ('os', [
        'WRITE SYS$OUTPUT "name=OpenVMS"',
        'WRITE SYS$OUTPUT "version=" + F$GETSYI("VERSION")',
        'WRITE SYS$OUTPUT "build=" + F$GETSYI("BOOTTIME")',
        'WRITE SYS$OUTPUT "kernel=" + F$GETSYI("VERSION")',
        'WRITE SYS$OUTPUT "timezone=" + F$LOGICAL("SYS$TIMEZONE_NAME")',
    ]),
    ('network_interfaces', [
        'TCPIP SHOW INTERFACE',
    ]),
    ('network_routes', [
        'TCPIP SHOW ROUTE',
    ]),
    ('network_dns', [
        'TCPIP SHOW NAME_SERVICE',
    ]),
    ('users', [
        'MCR AUTHORIZE SHOW */FULL',
    ]),
    ('groups', [
        'MCR AUTHORIZE SHOW/RIGHTS *',
    ]),
    ('packages', [
        'PRODUCT SHOW PRODUCT */FULL',
    ]),
    ('services', [
        'SHOW SYSTEM /FULL',
    ]),
    ('filesystem', [
        'SHOW DEVICE /MOUNTED /FULL',
    ]),
    ('security', [
        'SHOW INTRUSION/FULL',
        'MCR SYSGEN SHOW UAFALTERNATE',
        'MCR SYSGEN SHOW SECURITY_POLICY',
        'MCR AUTHORIZE SHOW DEFAULT',
    ]),
    ('scheduled_tasks', [
        'SHOW QUEUE /BATCH /FULL /ALL_JOBS',
    ]),
    ('sysctl', [
        'MCR SYSGEN SHOW/ALL',
    ]),
    ('listening_services', [
        'TCPIP SHOW SERVICE',
    ]),
    ('logging_targets', [
        'TYPE TCPIP$ETC:SYSLOG.CONF',
    ]),
    ('ssh_config', [
        'TYPE TCPIP$SSH_DEVICE:[TCPIP$SSH]SSH2_CONFIG.DAT',
        'TYPE SYS$SPECIFIC:[SSH2]SSHD2_CONFIG',
    ]),
    ('snmp', [
        'TCPIP SHOW SNMP',
    ]),
    ('shares', [
        'TCPIP SHOW NFS/SERVER/EXPORT',
    ]),
    ('certificates', [
        'CRYPTO SHOW CERTIFICATE/FULL',
    ]),
]

collected = []
for section_name, commands in SECTIONS:
    collected.append(f'{SEP}[{section_name}]')
    for cmd in commands:
        collected.append(_send(cmd))

collected.append(f'{SEP}[END]')

_send('LOGOUT')
tn.close()

# `output` is the variable Satellite reads as this script's result
output = '\n'.join(collected)
