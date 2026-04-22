"""
DEC Terminal Server (DECServer) Baseline Collector
====================================================
Runs on: SERVER  (set "Runs On" to Server in the Script Editor)

Connects outbound to the DECServer management interface via Telnet (port 23).
DECServers do not support SSH; Telnet is the standard management protocol
across all DECServer product lines (90L/90M/200/300/700/900/5000 series).

Privilege escalation:
    DECServers have two privilege levels: unprivileged and privileged.
    Privileged mode is entered with 'SET PRIVILEGED [password]'.  The
    credential password is used as the privileged password.  If no privileged
    password is configured on the server the command is accepted silently
    without a password prompt.

    Commands that REQUIRE privilege on most models:
        SHOW USER ALL
        SHOW AUTHENTICATION
        SHOW LOGGING
        SHOW SNMP
        SHOW IP (some models)

    Commands that do NOT require privilege:
        SHOW SERVER
        SHOW PORT ALL CHARACTERISTICS
        SHOW SERVICE ALL
        SHOW PROTOCOL ALL

Credential mapping:
    username  — used if the server has a login prompt (optional on many models)
    password  — used for login AND for SET PRIVILEGED

Collected sections (delimited by ---ISOTOPEIQ---[name]):
    server, ports, services, protocol, users, authentication, logging, snmp,
    ip_config, ip_routes
"""

import re
import socket
import time

# ── Resolve credentials from the device record ────────────────────────────────

cred = device.credential  # noqa: F821 — `device` injected by Satellite
if cred:
    _username  = cred.username or ''
    _password  = cred.password or ''
    _priv_pass = cred.password or ''   # same credential used for SET PRIVILEGED
else:
    _username  = ''
    _password  = getattr(device, 'password', '') or ''
    _priv_pass = _password

_hostname = device.hostname
_port     = device.port or 23

SEP = '---ISOTOPEIQ---'

# ── Telnet transport (raw socket) ─────────────────────────────────────────────
# telnetlib is deprecated in Python 3.11+; use raw sockets with inline IAC
# negotiation stripping instead.

_TIMEOUT  = 20.0
_RECV_BUF = 4096

# DECServer prompt: server-name followed by > (unprivileged) or * / # (privileged)
# Examples:  "MYSERVER> "   "MYSERVER*> "   "MYSERVER# "   "Local> "
_PROMPT_RE = re.compile(r'\S+\s*[>*#]\s*$')


def _strip_iac(data: bytes) -> bytes:
    """Strip Telnet IAC option-negotiation sequences from raw bytes.

    DECServers send standard Telnet IAC (0xFF) negotiation on connect.
    We refuse all requests by doing nothing (not responding), and strip
    the bytes from the stream so the text decoder stays clean.
    """
    out = bytearray()
    i = 0
    while i < len(data):
        b = data[i]
        if b == 0xFF and i + 1 < len(data):
            cmd = data[i + 1]
            if cmd in (0xFB, 0xFC, 0xFD, 0xFE):   # WILL / WONT / DO / DONT (3-byte)
                i += 3
            elif cmd == 0xFA:                        # SB subneg (variable length → find IAC SE)
                end = data.find(b'\xFF\xF0', i + 2)
                i = (end + 2) if end != -1 else len(data)
            else:                                    # 2-byte (IAC IAC etc.)
                i += 2
        else:
            out.append(b)
            i += 1
    return bytes(out)


class _Telnet:
    """Minimal synchronous Telnet connection."""

    def __init__(self, host: str, port: int, timeout: float = _TIMEOUT):
        self._sock = socket.create_connection((host, port), timeout=timeout)
        self._sock.settimeout(timeout)

    def read_until_prompt(self, timeout: float = _TIMEOUT) -> str:
        buf = ''
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                raw = self._sock.recv(_RECV_BUF)
            except socket.timeout:
                break
            if raw:
                buf += _strip_iac(raw).decode('ascii', errors='replace')
                if _PROMPT_RE.search(buf.rstrip()):
                    break
            else:
                time.sleep(0.05)
        return buf

    def send(self, cmd: str, timeout: float = _TIMEOUT) -> str:
        """Send a command line and return all text received until the next prompt."""
        self._sock.sendall((cmd + '\r\n').encode('ascii'))
        return self.read_until_prompt(timeout)

    def close(self):
        self._sock.close()


# ── Connect ───────────────────────────────────────────────────────────────────

conn = _Telnet(_hostname, _port)

# Flush initial banner and any Telnet negotiation traffic.
banner = conn.read_until_prompt()

# ── Login sequence ────────────────────────────────────────────────────────────
# Some models prompt for a username and/or password; others present the
# management prompt immediately.  Handle both cases gracefully.

if re.search(r'[Uu]sername[:\s]|[Ll]ogin[:\s]', banner) and _username:
    banner = conn.send(_username)

if re.search(r'[Pp]assword[:\s]', banner) and _password:
    banner = conn.send(_password)

# ── Privilege escalation — SET PRIVILEGED ─────────────────────────────────────
# Most SHOW commands work unprivileged, but SHOW USER, SHOW AUTHENTICATION,
# SHOW LOGGING and SHOW SNMP require privilege on most DECServer models.

_resp = conn.send('SET PRIVILEGED')
if re.search(r'[Pp]assword[:\s]', _resp) and _priv_pass:
    conn.send(_priv_pass)

# ── Collect sections ──────────────────────────────────────────────────────────

COMMANDS = [
    ('server',         'SHOW SERVER'),
    ('ports',          'SHOW PORT ALL CHARACTERISTICS'),
    ('services',       'SHOW SERVICE ALL'),
    ('protocol',       'SHOW PROTOCOL ALL'),
    ('users',          'SHOW USER ALL'),          # requires privilege
    ('authentication', 'SHOW AUTHENTICATION'),    # requires privilege
    ('logging',        'SHOW LOGGING'),           # requires privilege on some models
    ('snmp',           'SHOW SNMP'),              # requires privilege on some models
    ('ip_config',      'SHOW IP'),                # requires privilege on some models
    ('ip_routes',      'SHOW IP ROUTE'),          # requires privilege on some models
]

collected = []

for section_name, cmd in COMMANDS:
    raw = conn.send(cmd, timeout=30)
    # Strip echoed command (first line) and trailing prompt (last line)
    lines = raw.splitlines()
    if lines and cmd.lower() in lines[0].lower():
        lines = lines[1:]
    if lines:
        lines = lines[:-1]
    collected.append(f'{SEP}[{section_name}]')
    collected.append('\n'.join(lines))

collected.append(f'{SEP}[END]')

conn.close()

# `output` is the variable Satellite reads as this script's result
output = '\n'.join(collected)
