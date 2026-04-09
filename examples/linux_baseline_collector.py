"""
Linux Baseline Collector (Python / Server-side)
=================================================
Runs on: SERVER  (set "Execution" to "Run on Satellite" in the Script Editor)

Connects to the target Linux device via SSH using paramiko and runs the same
commands as the bash collector, producing identical ---ISOTOPEIQ---[section]
delimited output so the existing linux_baseline_parser.py works unchanged.

The `device` variable is provided by the Satellite execution context.
"""

import base64
import io

import paramiko

# ── Credentials ───────────────────────────────────────────────────────────────

cred = device.credential  # noqa: F821
if cred:
    _username    = cred.username or ''
    _password    = cred.password or ''
    _private_key = cred.private_key or ''
    _elevate     = 'sudo_pass' if cred.credential_type == 'password' else 'sudo' if cred.credential_type == 'private_key' else 'none'
    _elevate_pass = cred.password or ''
else:
    _username    = device.username or ''
    _password    = device.password or ''
    _private_key = device.ssh_private_key or ''
    _elevate     = 'sudo_pass' if _password else 'none'
    _elevate_pass = _password


# ── SSH connection ────────────────────────────────────────────────────────────

def _load_key(pem):
    for cls in (paramiko.Ed25519Key, paramiko.ECDSAKey, paramiko.RSAKey):
        try:
            return cls.from_private_key(io.StringIO(pem))
        except paramiko.SSHException:
            continue
    raise paramiko.SSHException('Unsupported or invalid private key.')


class _PinnedPolicy(paramiko.MissingHostKeyPolicy):
    def __init__(self, expected_b64):
        self._expected = expected_b64

    def missing_host_key(self, client, hostname, key):
        actual = base64.b64encode(key.asbytes()).decode()
        if actual != self._expected:
            raise paramiko.SSHException(f'Host key mismatch for {hostname}.')


client = paramiko.SSHClient()
if device.host_key:
    client.set_missing_host_key_policy(_PinnedPolicy(device.host_key))
else:
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

connect_kwargs = dict(
    hostname=device.hostname,
    port=device.port or 22,
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


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run(cmd):
    """Run a shell command over SSH and return stdout (stderr suppressed)."""
    _, stdout, _ = client.exec_command(cmd, timeout=60)
    return stdout.read().decode('utf-8', errors='replace').rstrip()


def _priv(cmd):
    """Run a command with privilege elevation based on the credential type."""
    if _elevate == 'sudo':
        return _run(f'sudo {cmd}')
    elif _elevate == 'sudo_pass':
        return _run(f'echo {_elevate_pass!r} | sudo -S {cmd} 2>/dev/null')
    else:
        return _run(cmd)


SEP = '---ISOTOPEIQ---'

sections = []


def section(name, content):
    sections.append(f'{SEP}[{name}]')
    sections.append(content)


# ── Device ────────────────────────────────────────────────────────────────────

section('device', '\n'.join([
    _run('hostname'),
    _run('hostname -f 2>/dev/null || echo ""'),
    'server',
    _priv('cat /sys/class/dmi/id/sys_vendor 2>/dev/null || echo ""'),
    _priv('cat /sys/class/dmi/id/product_name 2>/dev/null || echo ""'),
]))

# ── Hardware ──────────────────────────────────────────────────────────────────

section('hardware', '\n'.join([
    _run('grep -m1 "model name" /proc/cpuinfo 2>/dev/null | cut -d: -f2 | xargs || echo ""'),
    _run('nproc --all 2>/dev/null || grep -c "^processor" /proc/cpuinfo 2>/dev/null || echo ""'),
    _run('awk \'/MemTotal/ {printf "%.2f\\n", $2/1024/1024}\' /proc/meminfo'),
    _priv('cat /sys/class/dmi/id/bios_version 2>/dev/null || echo ""'),
    _priv('cat /sys/class/dmi/id/product_serial 2>/dev/null || echo ""'),
    _run('uname -m'),
    _run('systemd-detect-virt 2>/dev/null || (grep -qm1 "hypervisor" /proc/cpuinfo && echo "other" || echo "bare-metal")'),
]))

# ── OS ────────────────────────────────────────────────────────────────────────

section('os', '\n'.join([
    _run(r'''
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        echo "${NAME:-}"; echo "${VERSION_ID:-}"; echo "${BUILD_ID:-${VERSION:-}}"
    elif [ -f /etc/alpine-release ]; then
        echo "Alpine Linux"; cat /etc/alpine-release; echo ""
    else
        echo ""; echo ""; echo ""
    fi
    '''.strip()),
    _run('uname -r'),
    _run('cat /etc/timezone 2>/dev/null || timedatectl show -p Timezone --value 2>/dev/null || echo ""'),
    _run(r"grep -E '^NTP=' /etc/systemd/timesyncd.conf 2>/dev/null | cut -d= -f2 || grep '^server ' /etc/chrony.conf 2>/dev/null | awk '{print $2}' | tr '\n' ' ' || grep '^server ' /etc/ntp.conf 2>/dev/null | awk '{print $2}' | tr '\n' ' ' || echo ''"),
    _run("timedatectl show -p NTPSynchronized --value 2>/dev/null || echo 'unknown'"),
]))

# ── Network ───────────────────────────────────────────────────────────────────

section('network',        _run('ip -j addr show 2>/dev/null || ip addr show 2>/dev/null || ifconfig -a 2>/dev/null || echo ""'))
section('network_routes', _run('ip -j route show 2>/dev/null || ip route show 2>/dev/null || echo ""'))
section('network_dns',    _run("grep '^nameserver' /etc/resolv.conf | awk '{print $2}' || echo ''"))
section('network_hosts',  _run("grep -v '^#' /etc/hosts | grep -v '^$' || echo ''"))

# ── Users ─────────────────────────────────────────────────────────────────────

section('users', _run(r"""
awk -F: '{print $1"|"$3"|"$6"|"$7}' /etc/passwd | while IFS='|' read -r uname uid home shell; do
    groups=$(id -Gn "$uname" 2>/dev/null | tr ' ' ',')
    echo "${uname}|${uid}|${home}|${shell}|${groups}||"
done
""".strip()))

# ── Groups ────────────────────────────────────────────────────────────────────

section('groups', _run("awk -F: '{print $1\"|\"$3\"|\"$4}' /etc/group"))

# ── Packages ──────────────────────────────────────────────────────────────────

section('packages', _run(r"""
if command -v dpkg-query &>/dev/null; then
    dpkg-query -W -f='${Package}|${Version}|${Maintainer}|\n' 2>/dev/null || true
elif command -v rpm &>/dev/null; then
    rpm -qa --queryformat '%{NAME}|%{VERSION}-%{RELEASE}|%{VENDOR}|%{INSTALLTIME:date}\n' 2>/dev/null || true
elif command -v apk &>/dev/null; then
    apk info -v 2>/dev/null | sed 's/-[0-9].*//' | awk '{print $1"|||"}' || true
elif command -v pacman &>/dev/null; then
    pacman -Q 2>/dev/null | awk '{print $1"|"$2"||"}' || true
fi
""".strip()))

# ── Services ──────────────────────────────────────────────────────────────────

section('services', _run(r"""
if command -v systemctl &>/dev/null; then
    systemctl list-units --type=service --all --no-pager --no-legend --output=json 2>/dev/null \
    || systemctl list-units --type=service --all --no-pager --no-legend 2>/dev/null
fi
""".strip()))

# ── Filesystem ────────────────────────────────────────────────────────────────

section('filesystem',        _run('df -P -T 2>/dev/null | tail -n +2 || df -P 2>/dev/null | tail -n +2 || true'))
section('filesystem_mounts', _run('cat /proc/mounts 2>/dev/null || mount'))
section('filesystem_suid',   _priv('find / -xdev \\( -perm -4000 -o -perm -2000 \\) -type f 2>/dev/null | sort || true'))

# ── Security ──────────────────────────────────────────────────────────────────

section('security', _run(r"""
getenforce 2>/dev/null || echo "disabled"
command -v apparmor_status &>/dev/null && (apparmor_status --enabled 2>/dev/null && echo "enabled" || echo "disabled") || echo "disabled"
command -v ufw &>/dev/null && (ufw status | head -1) || command -v firewall-cmd &>/dev/null && firewall-cmd --state 2>/dev/null || echo "inactive"
[ -f /etc/ssh/sshd_config ] && grep -E "^PasswordAuthentication|^PermitRootLogin|^Protocol" /etc/ssh/sshd_config 2>/dev/null || true
""".strip()))

# ── Scheduled tasks ───────────────────────────────────────────────────────────

section('scheduled_tasks', _run(r"""
for f in /etc/cron.d/* /etc/cron.daily/* /etc/cron.hourly/* /etc/cron.weekly/* /etc/cron.monthly/*; do
    [ -f "$f" ] && echo "=== $f ===" && cat "$f" 2>/dev/null; done
crontab -l 2>/dev/null || true
""".strip()))

# ── SSH keys ──────────────────────────────────────────────────────────────────

section('ssh_keys', _priv(r"find /home /root -name authorized_keys 2>/dev/null -exec echo '=== {} ===' \; -exec cat {} \; || true"))

# ── SSH config ────────────────────────────────────────────────────────────────

section('ssh_config', _run("grep -v '^#' /etc/ssh/sshd_config 2>/dev/null | grep -v '^$' || echo ''"))

# ── Kernel modules ────────────────────────────────────────────────────────────

section('kernel_modules', _run('lsmod 2>/dev/null || true'))

# ── PCI devices ───────────────────────────────────────────────────────────────

section('pci_devices', _run('lspci 2>/dev/null || true'))

# ── Storage devices ───────────────────────────────────────────────────────────

section('storage_devices', _priv('lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,MODEL 2>/dev/null || fdisk -l 2>/dev/null || true'))

# ── USB devices ───────────────────────────────────────────────────────────────

section('usb_devices', _run('lsusb 2>/dev/null || true'))

# ── Listening services ────────────────────────────────────────────────────────

section('listening_services', _run('ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null || true'))

# ── Firewall rules ────────────────────────────────────────────────────────────

section('firewall_rules', _priv('iptables -L -n -v 2>/dev/null || nft list ruleset 2>/dev/null || true'))

# ── Sysctl ────────────────────────────────────────────────────────────────────

section('sysctl', _run('sysctl -a 2>/dev/null || true'))

# ── Logging targets ───────────────────────────────────────────────────────────

section('logging_targets', _run(r"""
[ -f /etc/rsyslog.conf ] && cat /etc/rsyslog.conf 2>/dev/null || true
[ -d /etc/rsyslog.d ] && cat /etc/rsyslog.d/*.conf 2>/dev/null || true
""".strip()))

# ── Done ─────────────────────────────────────────────────────────────────────

sections.append(f'{SEP}[END]')
client.close()

output = '\n'.join(sections)
