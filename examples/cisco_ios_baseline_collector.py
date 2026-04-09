"""
Cisco IOS / IOS-XE Baseline Collector
======================================
Runs on: SERVER  (set "Runs On" to Server in the Script Editor)

This script runs on the Satellite server and connects outbound to the device
via SSH using paramiko. It is NOT pushed to the device.

The `device` variable is provided by the Satellite execution context and gives
access to the device record and its linked credential — no placeholders needed.

Collected sections (delimited by ---ISOTOPEIQ---[name] for the parser):
    version, running_config, interfaces, ip_interfaces, ip_int_detail,
    ip_routes, ip_bgp_sum, ip_ospf, ip_ospf_neigh, ip_eigrp_neigh,
    vlans, spanning_tree, cdp_neighbors, users_detail, aaa_servers,
    aaa_radius, snmp_groups, snmp_users, snmp_community, access_lists,
    ip_nat, crypto_isakmp, crypto_ipsec, ntp_status, ntp_assoc, clock,
    logging, processes_cpu, memory, flash, environment, inventory, boot,
    ip_ssh, ip_scp, line_config, tcp_intercept, ip_access_int
"""

import base64
import io
import time

import paramiko

# ── Resolve credentials from the device record ────────────────────────────────

cred = device.credential  # noqa: F821 — `device` injected by Satellite
if cred:
    _username    = cred.username or ''
    _password    = cred.password or ''
    _private_key = cred.private_key or ''
    _enable_pass = cred.password or ''   # same credential; named separately for clarity
else:
    _username    = device.username or ''
    _password    = device.password or ''
    _private_key = device.ssh_private_key or ''
    _enable_pass = device.password or ''

_hostname = device.hostname
_port     = device.port or 22

# ── Helper: load a private key from a PEM string ─────────────────────────────

def _load_key(pem: str):
    for cls in (paramiko.Ed25519Key, paramiko.ECDSAKey, paramiko.RSAKey):
        try:
            return cls.from_private_key(io.StringIO(pem))
        except paramiko.SSHException:
            continue
    raise paramiko.SSHException('Unsupported or invalid private key.')


# ── Helper: host key policy ───────────────────────────────────────────────────

class _PinnedPolicy(paramiko.MissingHostKeyPolicy):
    def __init__(self, expected_b64: str):
        self._expected = expected_b64

    def missing_host_key(self, client, hostname, key):
        actual = base64.b64encode(key.asbytes()).decode()
        if actual != self._expected:
            raise paramiko.SSHException(
                f'Host key mismatch for {hostname}. '
                'Update the device host_key field to correct this.'
            )


# ── Establish SSH connection ───────────────────────────────────────────────────

client = paramiko.SSHClient()
if device.host_key:
    client.set_missing_host_key_policy(_PinnedPolicy(device.host_key))
else:
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

connect_kwargs = dict(
    hostname=_hostname,
    port=_port,
    username=_username,
    timeout=30,
    allow_agent=False,
    look_for_keys=False,
)
if _private_key:
    connect_kwargs['pkey'] = _load_key(_private_key)
else:
    connect_kwargs['password'] = _password

client.connect(**connect_kwargs)

# ── Open an interactive shell channel ─────────────────────────────────────────
# exec_command() is one-shot; IOS requires an interactive session so that
# context (enable mode, terminal settings) is preserved across commands.

chan = client.invoke_shell(width=512, height=100)
chan.settimeout(30)

SEP = '---ISOTOPEIQ---'

def _read_until_prompt(timeout: float = 30.0) -> str:
    """Read from the channel until a Cisco prompt (# or >) is seen."""
    buf = ''
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if chan.recv_ready():
            chunk = chan.recv(4096).decode('utf-8', errors='replace')
            buf += chunk
            stripped = buf.rstrip()
            if stripped.endswith('#') or stripped.endswith('>'):
                break
        else:
            time.sleep(0.05)
    return buf


def _send(cmd: str, timeout: float = 30.0) -> str:
    chan.send(cmd + '\n')
    return _read_until_prompt(timeout)


# Flush the login banner / initial prompt
_read_until_prompt()

# ── Enter enable mode if needed ───────────────────────────────────────────────

_send('terminal length 0')
_send('terminal width 0')

# Check whether we landed in user EXEC (>) or privileged EXEC (#)
probe = _send('')
if probe.rstrip().endswith('>'):
    chan.send('enable\n')
    # May prompt for a password
    resp = ''
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if chan.recv_ready():
            resp += chan.recv(4096).decode('utf-8', errors='replace')
            if 'assword' in resp:
                chan.send(_enable_pass + '\n')
            if resp.rstrip().endswith('#'):
                break
        else:
            time.sleep(0.05)

# ── Collect sections ──────────────────────────────────────────────────────────

COMMANDS = [
    ('version',        'show version'),
    ('running_config', 'show running-config'),
    ('interfaces',     'show interfaces'),
    ('ip_interfaces',  'show ip interface brief'),
    ('ip_int_detail',  'show ip interface'),
    ('ip_routes',      'show ip route'),
    ('ip_bgp_sum',     'show ip bgp summary'),
    ('ip_ospf',        'show ip ospf'),
    ('ip_ospf_neigh',  'show ip ospf neighbor'),
    ('ip_eigrp_neigh', 'show ip eigrp neighbors'),
    ('vlans',          'show vlan brief'),
    ('spanning_tree',  'show spanning-tree'),
    ('cdp_neighbors',  'show cdp neighbors detail'),
    ('users_detail',   'show users'),
    ('aaa_servers',    'show tacacs'),
    ('aaa_radius',     'show radius server-group all'),
    ('snmp_groups',    'show snmp group'),
    ('snmp_users',     'show snmp user'),
    ('snmp_community', 'show snmp community'),
    ('access_lists',   'show access-lists'),
    ('ip_nat',         'show ip nat translations'),
    ('crypto_isakmp',  'show crypto isakmp sa'),
    ('crypto_ipsec',   'show crypto ipsec sa'),
    ('ntp_status',     'show ntp status'),
    ('ntp_assoc',      'show ntp associations'),
    ('clock',          'show clock detail'),
    ('logging',        'show logging'),
    ('processes_cpu',  'show processes cpu sorted'),
    ('memory',         'show memory statistics'),
    ('flash',          'show flash:'),
    ('environment',    'show environment all'),
    ('inventory',      'show inventory'),
    ('boot',           'show boot'),
    ('ip_ssh',         'show ip ssh'),
    ('ip_scp',         'show ip scp server'),
    ('line_config',    'show line'),
    ('tcp_intercept',  'show ip inspect sessions brief'),
    ('ip_access_int',  'show ip interface | include line|access list'),
]

collected = []
for section, cmd in COMMANDS:
    raw = _send(cmd, timeout=60)
    # Strip the echoed command (first line) and the trailing prompt (last line)
    lines = raw.splitlines()
    if lines and cmd in lines[0]:
        lines = lines[1:]
    if lines:
        lines = lines[:-1]
    collected.append(f'{SEP}[{section}]')
    collected.append('\n'.join(lines))

collected.append(f'{SEP}[END]')

chan.send('exit\n')
chan.close()
client.close()

# `output` is the variable Satellite reads as this script's result
output = '\n'.join(collected)
