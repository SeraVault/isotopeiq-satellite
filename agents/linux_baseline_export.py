#!/usr/bin/env python3
"""Standalone Linux baseline exporter.

Collects a system baseline and writes it as JSON in the schema-1.2.0
format produced by the ansible-baseline collector (see vmcfgmgmt.json).
No network transport -- output is a local JSON file only.

Usage:
    sudo python3 linux_baseline_export.py [--identifier NAME] [-o FILE]

Run as root for complete results (shadow, dmidecode, sshd -T, user
crontabs). Unprivileged runs still produce a valid file; the
"collection.privileged" security setting records which mode was used.
"""

import argparse
import glob
import hashlib
import json
import os
import pwd
import re
import socket
import subprocess
import sys
from datetime import datetime, timezone

SCHEMA_VERSION = '1.2.0'
COLLECTOR_VERSION = '1.0.0'


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def run(cmd, timeout=60):
    """Run a shell command, return stdout ('' on any failure).

    Python 3.6 compatible (the amd64 binary is built on centos:7).
    """
    try:
        p = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE,
                           universal_newlines=True, timeout=timeout)
        return p.stdout
    except Exception:
        return ''


def run_lines(cmd, timeout=60):
    return [ln for ln in run(cmd, timeout).splitlines() if ln.strip()]


def which(cmd):
    for d in os.environ.get('PATH', '/usr/sbin:/usr/bin:/sbin:/bin').split(':'):
        if d and os.path.isfile(os.path.join(d, cmd)):
            return os.path.join(d, cmd)
    for d in ('/usr/sbin', '/usr/bin', '/sbin', '/bin'):
        if os.path.isfile(os.path.join(d, cmd)):
            return os.path.join(d, cmd)
    return None


def read_file(path):
    try:
        with open(path, 'r', errors='replace') as f:
            return f.read()
    except Exception:
        return ''


def read_lines(path):
    return [ln.rstrip('\n') for ln in read_file(path).splitlines()]


def is_root():
    return os.geteuid() == 0


def os_release():
    info = {}
    for line in read_lines('/etc/os-release'):
        if '=' in line:
            k, v = line.split('=', 1)
            info[k.strip()] = v.strip().strip('"').strip("'")
    return info


def sha256_file(path):
    try:
        h = hashlib.sha256()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# host / os / hardware
# ---------------------------------------------------------------------------

def collect_host(identifier):
    hostname = socket.gethostname().split('.')[0]
    try:
        fqdn = socket.getfqdn()
    except Exception:
        fqdn = hostname

    osr = os_release()
    ids = (osr.get('ID', '') + ' ' + osr.get('ID_LIKE', '')).lower()
    if any(t in ids for t in ('rhel', 'fedora', 'centos', 'almalinux', 'rocky')):
        family = 'redhat'
    elif any(t in ids for t in ('debian', 'ubuntu')):
        family = 'debian'
    elif 'suse' in ids:
        family = 'suse'
    elif 'arch' in ids:
        family = 'archlinux'
    elif 'alpine' in ids:
        family = 'alpine'
    else:
        family = osr.get('ID', 'linux') or 'linux'

    return {
        'fqdn': fqdn,
        'hostname': hostname,
        'identifier': identifier or hostname,
        'os_family': family,
        'platform': 'linux',
    }


def collect_os():
    osr = os_release()
    version = osr.get('VERSION', '')
    m = re.search(r'\(([^)]+)\)', version)
    build = m.group(1) if m else osr.get('VERSION_CODENAME', '')
    return {
        'architecture': run('uname -m').strip(),
        'build': build,
        'kernel': run('uname -r').strip(),
        'name': osr.get('NAME', 'Linux'),
        'service_pack': '',
        'version': osr.get('VERSION_ID', ''),
    }


def collect_hardware():
    cpu = ''
    for line in read_lines('/proc/cpuinfo'):
        if line.startswith(('model name', 'cpu model', 'Processor', 'Hardware')):
            cpu = line.split(':', 1)[-1].strip()
            break

    memory_mb = None
    for line in read_lines('/proc/meminfo'):
        if line.startswith('MemTotal:'):
            try:
                memory_mb = int(line.split()[1]) // 1024
            except (IndexError, ValueError):
                pass
            break

    manufacturer = read_file('/sys/class/dmi/id/sys_vendor').strip()
    model = read_file('/sys/class/dmi/id/product_name').strip()
    serial = read_file('/sys/class/dmi/id/product_serial').strip()
    if is_root() and which('dmidecode'):
        manufacturer = manufacturer or run('dmidecode -s system-manufacturer 2>/dev/null').strip()
        model = model or run('dmidecode -s system-product-name 2>/dev/null').strip()
        serial = serial or run('dmidecode -s system-serial-number 2>/dev/null').strip()

    disks = []
    for dev in sorted(glob.glob('/sys/block/*')):
        name = os.path.basename(dev)
        if re.match(r'^(loop|ram|zram|fd|sr|dm-|md)', name):
            continue
        try:
            sectors = int(read_file(os.path.join(dev, 'size')).strip() or 0)
        except ValueError:
            sectors = 0
        if sectors == 0:
            continue
        rotational = read_file(os.path.join(dev, 'queue/rotational')).strip()
        disks.append({
            'model': read_file(os.path.join(dev, 'device/model')).strip(),
            'name': name,
            'serial_number': read_file(os.path.join(dev, 'device/serial')).strip(),
            'size_gb': round(sectors * 512 / (1024 ** 3), 2),
            'type': 'hdd' if rotational == '1' else 'ssd',
        })

    return {
        'cpu': cpu,
        'cpu_cores': os.cpu_count(),
        'disks': disks,
        'manufacturer': manufacturer,
        'memory_mb': memory_mb,
        'model': model,
        'serial_number': serial,
    }


# ---------------------------------------------------------------------------
# network
# ---------------------------------------------------------------------------

def collect_network():
    interfaces = []
    for dev in sorted(glob.glob('/sys/class/net/*')):
        name = os.path.basename(dev)
        mac = read_file(os.path.join(dev, 'address')).strip()

        if name == 'lo' or read_file(os.path.join(dev, 'type')).strip() == '772':
            iface_type = 'loopback'
        else:
            devtype = ''
            for line in read_lines(os.path.join(dev, 'uevent')):
                if line.startswith('DEVTYPE='):
                    devtype = line.split('=', 1)[1]
                    break
            if os.path.isdir(os.path.join(dev, 'wireless')):
                iface_type = 'wifi'
            else:
                iface_type = devtype or 'ether'

        ipv4, ipv6 = [], []
        for line in run_lines('ip -o addr show dev %s 2>/dev/null' % name):
            parts = line.split()
            if 'inet' in parts:
                addr = parts[parts.index('inet') + 1].split('/')[0]
                ipv4.append(addr)
            elif 'inet6' in parts:
                addr = parts[parts.index('inet6') + 1].split('/')[0]
                if not addr.lower().startswith('fe80'):
                    ipv6.append(addr)

        interfaces.append({
            'dhcp': None,
            'ipv4_addresses': ipv4,
            'ipv6_addresses': ipv6,
            'mac': mac,
            'name': name,
            'type': iface_type,
        })

    dns = []
    for line in read_lines('/etc/resolv.conf'):
        if line.strip().startswith('nameserver'):
            parts = line.split()
            if len(parts) >= 2 and parts[1] not in dns:
                dns.append(parts[1])
    if dns and all(d.startswith('127.') for d in dns) and which('resolvectl'):
        real = []
        for line in run_lines('resolvectl dns 2>/dev/null'):
            if ':' not in line:
                continue
            for tok in line.split(':', 1)[1].split():
                if (re.match(r'^\d+\.\d+\.\d+\.\d+$', tok) or
                        re.match(r'^[0-9a-fA-F:]+$', tok) and ':' in tok):
                    if tok not in real and not tok.startswith('127.'):
                        real.append(tok)
        if real:
            dns = real

    return {'dns_servers': dns, 'interfaces': interfaces}


# ---------------------------------------------------------------------------
# users / groups
# ---------------------------------------------------------------------------

def _database_lines(database, path):
    """Entries from getent (includes systemd dynamic users), else the file."""
    lines = run_lines('getent %s 2>/dev/null' % database)
    return lines if lines else read_lines(path)


def _admin_info():
    """Names and gids of the sudo-granting groups (wheel/sudo/admin)."""
    admins = set()
    admin_gids = set()
    for line in _database_lines('group', '/etc/group'):
        parts = line.split(':')
        if len(parts) >= 4 and parts[0] in ('wheel', 'sudo', 'admin'):
            admin_gids.add(parts[2])
            admins.update(m for m in parts[3].split(',') if m)
    return admins, admin_gids


def collect_users():
    locked = {}
    for line in read_lines('/etc/shadow'):
        parts = line.split(':')
        if len(parts) >= 2:
            locked[parts[0]] = parts[1].startswith('!')

    admins, admin_gids = _admin_info()
    users = []
    for line in _database_lines('passwd', '/etc/passwd'):
        parts = line.split(':')
        if len(parts) < 7:
            continue
        name, passwd, uid, gid, gecos, home, shell = parts[:7]
        if passwd == 'x' and locked:
            # shadow database readable: locked entries and accounts with no
            # shadow entry at all (systemd dynamic users) count as disabled
            enabled = name in locked and not locked[name]
        elif passwd == 'x':
            enabled = True  # shadow unreadable (not root); assume enabled
        else:
            # inline field -- locked when it can never match a password
            enabled = passwd not in ('*', '!', '!!', '!*')
        users.append({
            'admin': uid == '0' or name in admins or gid in admin_gids,
            'description': gecos.split(',')[0],
            'enabled': enabled,
            'home': home,
            'id': uid,
            'name': name,
            'shell': shell,
        })
    return sorted(users, key=lambda u: u['name'])


def collect_groups():
    groups = []
    for line in _database_lines('group', '/etc/group'):
        parts = line.split(':')
        if len(parts) < 4:
            continue
        groups.append({
            'id': parts[2],
            'members': sorted(m for m in parts[3].split(',') if m),
            'name': parts[0],
        })
    return sorted(groups, key=lambda g: g['name'])


# ---------------------------------------------------------------------------
# applications / patches
# ---------------------------------------------------------------------------

def collect_applications():
    apps = []
    if which('rpm'):
        for line in run_lines(r"rpm -qa --qf '%{NAME}\t%{VERSION}\t%{ARCH}\n'", 120):
            parts = line.split('\t')
            if len(parts) == 3:
                apps.append({
                    'architecture': '' if parts[2] == '(none)' else parts[2],
                    'name': parts[0],
                    'source': 'rpm',
                    'vendor': '',
                    'version': parts[1],
                })
    elif which('dpkg-query'):
        for line in run_lines(r"dpkg-query -W -f '${Package}\t${Version}\t${Architecture}\n'", 120):
            parts = line.split('\t')
            if len(parts) == 3:
                apps.append({
                    'architecture': parts[2],
                    'name': parts[0],
                    'source': 'dpkg',
                    'vendor': '',
                    'version': parts[1],
                })
    elif which('apk'):
        # entries look like 'name-1.2.3-r0': version is the last two
        # dash-separated fields
        for line in run_lines('apk info -v 2>/dev/null', 120):
            parts = line.rsplit('-', 2)
            if len(parts) == 3 and parts[2].startswith('r'):
                apps.append({
                    'architecture': '',
                    'name': parts[0],
                    'source': 'apk',
                    'vendor': '',
                    'version': parts[1] + '-' + parts[2],
                })
    return sorted(apps, key=lambda a: (a['name'], a['version']))


def collect_patches():
    # Parity with the ansible-baseline collector, which reports no discrete
    # patch entries for Linux (updates surface through package versions).
    return []


# ---------------------------------------------------------------------------
# services
# ---------------------------------------------------------------------------

def collect_services():
    services = {}
    state_map = {'enabled': 'auto', 'enabled-runtime': 'auto'}

    for line in run_lines('systemctl list-unit-files --type=service '
                          '--no-legend --no-pager --plain 2>/dev/null'):
        parts = line.split()
        if len(parts) >= 2 and parts[0].endswith('.service'):
            services[parts[0]] = state_map.get(parts[1], parts[1])

    for line in run_lines('systemctl list-units --type=service --all '
                          '--no-legend --no-pager --plain 2>/dev/null'):
        parts = line.split()
        if len(parts) >= 4 and parts[0].endswith('.service'):
            name, load, active = parts[0], parts[1], parts[2]
            if name not in services:
                services[name] = 'not-found' if load == 'not-found' else active

    if not services:  # non-systemd fallback
        for line in run_lines('service --status-all 2>/dev/null'):
            m = re.match(r'^\s*\[\s*([+-?])\s*\]\s+(\S+)', line)
            if m:
                services[m.group(2)] = 'auto' if m.group(1) == '+' else 'disabled'

    return [{
        'display_name': '',
        'name': name,
        'path': '',
        'run_as': '',
        'source': 'systemd' if which('systemctl') else 'sysvinit',
        'startup': startup,
    } for name, startup in sorted(services.items())]


# ---------------------------------------------------------------------------
# startup items (cron + systemd timers)
# ---------------------------------------------------------------------------

_TIMER_KEYS = ('OnCalendar=', 'OnBootSec=', 'OnStartupSec=', 'Persistent=')


def collect_startup_items():
    items = []

    cron_files = ['/etc/crontab'] + sorted(glob.glob('/etc/cron.d/*'))
    for path in cron_files:
        for line in read_lines(path):
            line = line.strip()
            if not line or line.startswith('#') or re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', line):
                continue
            fields = line.split()
            scope = fields[5] if len(fields) >= 7 else 'root'
            items.append({
                'command': line,
                'location': 'cron:%s' % path,
                'name': line,
                'scope': scope,
            })

    if is_root():
        for spool in ('/var/spool/cron', '/var/spool/cron/crontabs'):
            if not os.path.isdir(spool):
                continue
            for path in sorted(glob.glob(os.path.join(spool, '*'))):
                if not os.path.isfile(path):
                    continue
                user = os.path.basename(path)
                for line in read_lines(path):
                    line = line.strip()
                    if not line or line.startswith('#') or re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', line):
                        continue
                    items.append({
                        'command': line,
                        'location': 'cron:crontab',
                        'name': line,
                        'scope': user,
                    })

    for line in run_lines('systemctl list-unit-files --type=timer '
                          '--no-legend --no-pager --plain 2>/dev/null'):
        parts = line.split()
        if len(parts) < 2 or not parts[0].endswith('.timer'):
            continue
        name, state = parts[0], parts[1]
        if state not in ('enabled', 'enabled-runtime'):
            continue
        schedule = ''
        for cl in run_lines('systemctl cat %s 2>/dev/null' % name):
            cl = cl.strip()
            if cl.startswith(_TIMER_KEYS):
                schedule += cl + ';'
        items.append({
            'command': schedule,
            'location': 'systemd-timer',
            'name': name,
            'scope': 'system',
        })

    return sorted(items, key=lambda i: (i['location'], i['name']))


# ---------------------------------------------------------------------------
# firewall rules
# ---------------------------------------------------------------------------

def _fw_rule(name, raw, source):
    return {
        'action': '',
        'application': '',
        'direction': '',
        'enabled': True,
        'id': raw,
        'local_ports': [],
        'name': name,
        'profiles': [],
        'protocol': '',
        'raw': raw,
        'remote_ports': [],
        'service': '',
        'source': source,
    }


def collect_firewall_rules():
    rules = []

    if which('firewall-cmd') and 'running' in run('firewall-cmd --state 2>/dev/null'):
        zone = None
        # permanent config (matches the ansible-baseline collector; runtime
        # listing would add transient interface/source bindings). --permanent
        # needs root, so fall back to the runtime listing without it.
        listing = run('firewall-cmd --permanent --list-all-zones 2>/dev/null')
        if not listing.strip():
            listing = run('firewall-cmd --list-all-zones 2>/dev/null')
        for line in listing.splitlines():
            if not line.strip():
                zone = None
                continue
            if not line[0].isspace():
                zone = line.split()[0].strip()
                continue
            if zone:
                rules.append(_fw_rule(zone, '%s: %s' % (zone, line.strip()), 'firewalld'))
    elif which('nft') and is_root():
        chain = ''
        for line in run_lines('nft list ruleset 2>/dev/null'):
            stripped = line.strip()
            m = re.match(r'^chain\s+(\S+)', stripped)
            if m:
                chain = m.group(1)
            if stripped and not stripped.startswith(('table', '}', '{')):
                rules.append(_fw_rule(chain or stripped.split()[0], stripped, 'nftables'))
    elif which('iptables-save') and is_root():
        chain = ''
        for line in run_lines('iptables-save 2>/dev/null'):
            if line.startswith(':'):
                chain = line[1:].split()[0]
            if line.startswith('-A'):
                chain = line.split()[1]
                rules.append(_fw_rule(chain, line, 'iptables'))

    return sorted(rules, key=lambda r: r['id'])


# ---------------------------------------------------------------------------
# security settings + file integrity
# ---------------------------------------------------------------------------

_LOGIN_DEFS = {
    'ENCRYPT_METHOD': 'login.encrypt_method',
    'PASS_MAX_DAYS': 'login.pass_max_days',
    'PASS_MIN_DAYS': 'login.pass_min_days',
    'PASS_MIN_LEN': 'login.pass_min_len',
    'PASS_WARN_AGE': 'login.pass_warn_age',
    'UMASK': 'login.umask',
}

_SSHD_KEYS = ('allowtcpforwarding', 'kbdinteractiveauthentication', 'maxauthtries',
              'passwordauthentication', 'permitemptypasswords', 'permitrootlogin',
              'port', 'pubkeyauthentication', 'usepam', 'x11forwarding')

_SYSCTL_KEYS = ('fs.protected_hardlinks', 'fs.protected_symlinks',
                'kernel.kptr_restrict', 'kernel.randomize_va_space',
                'net.ipv4.conf.all.accept_redirects', 'net.ipv4.conf.all.rp_filter',
                'net.ipv4.ip_forward')


def _unit_enable_state(unit):
    out = run('systemctl is-enabled %s 2>&1' % unit).strip()
    first = out.splitlines()[0].strip() if out else ''
    if first in ('enabled', 'enabled-runtime'):
        return 'enabled'
    if first in ('disabled', 'masked', 'static', 'indirect', 'alias'):
        return 'disabled' if first in ('disabled', 'masked') else first
    return 'not-found'


def collect_security():
    settings = {'collection.privileged': 'true' if is_root() else 'false'}

    for unit in ('firewalld', 'iptables', 'nftables', 'ufw'):
        if unit == 'ufw' and not which('ufw'):
            continue
        settings['firewall.%s' % unit] = _unit_enable_state(unit)

    for line in read_lines('/etc/login.defs'):
        parts = line.split()
        if len(parts) >= 2 and parts[0] in _LOGIN_DEFS:
            settings[_LOGIN_DEFS[parts[0]]] = parts[1]

    if which('getenforce'):
        mode = run('getenforce 2>/dev/null').strip().lower()
        if mode:
            settings['selinux.mode'] = mode
            settings['selinux.status'] = 'disabled' if mode == 'disabled' else 'enabled'
    if which('aa-status'):
        settings['apparmor.status'] = (
            'enabled' if run('aa-status --enabled 2>/dev/null; echo $?').strip().endswith('0')
            else 'disabled')

    sshd_conf = {}
    if is_root():
        for line in run_lines('sshd -T 2>/dev/null'):
            parts = line.split(None, 1)
            if len(parts) == 2:
                sshd_conf[parts[0].lower()] = parts[1]
    if not sshd_conf:
        for line in read_lines('/etc/ssh/sshd_config'):
            line = line.strip()
            if line and not line.startswith('#'):
                parts = line.split(None, 1)
                if len(parts) == 2:
                    sshd_conf.setdefault(parts[0].lower(), parts[1].lower())
    for key in _SSHD_KEYS:
        if key in sshd_conf:
            settings['ssh.%s' % key] = sshd_conf[key]

    for key in _SYSCTL_KEYS:
        val = read_file('/proc/sys/%s' % key.replace('.', '/')).strip()
        if val:
            settings['sysctl.%s' % key] = val

    ntp = []
    for conf in ('/etc/chrony.conf', '/etc/chrony/chrony.conf', '/etc/ntp.conf',
                 '/etc/systemd/timesyncd.conf'):
        for line in read_lines(conf):
            line = line.strip()
            m = re.match(r'^(?:server|pool|NTP=)\s*(\S+)', line, re.IGNORECASE)
            if m and not line.startswith('#'):
                ntp.append(m.group(1))
    if ntp:
        settings['time.ntp_servers'] = ','.join(dict.fromkeys(ntp))

    tz = ''
    if os.path.islink('/etc/localtime'):
        target = os.path.realpath('/etc/localtime')
        m = re.search(r'zoneinfo/(.+)$', target)
        tz = m.group(1) if m else ''
    if not tz:
        tz = read_file('/etc/timezone').strip()
    if tz:
        settings['time.timezone'] = tz

    integrity_paths = ['/etc/fstab', '/etc/hosts', '/etc/login.defs',
                       '/etc/ssh/sshd_config', '/etc/sudoers']
    integrity_paths += glob.glob('/etc/modprobe.d/*.conf')
    integrity_paths += glob.glob('/etc/sudoers.d/*')
    try:
        for u in pwd.getpwall():
            if u.pw_uid >= 1000 and u.pw_dir.startswith('/home'):
                integrity_paths.append(os.path.join(u.pw_dir, '.ssh/authorized_keys'))
    except Exception:
        pass

    file_integrity = []
    for path in sorted(set(integrity_paths)):
        if os.path.isfile(path):
            digest = sha256_file(path)
            if digest:
                file_integrity.append({'path': path, 'sha256': digest})

    return {
        'file_integrity': file_integrity,
        'settings': [{'key': k, 'value': v} for k, v in sorted(settings.items())],
    }


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def collect(identifier, collector, method):
    return {
        'applications': collect_applications(),
        'collection': {
            'collected_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'collector': collector,
            'collector_version': COLLECTOR_VERSION,
            'method': method,
        },
        'firewall_rules': collect_firewall_rules(),
        'groups': collect_groups(),
        'hardware': collect_hardware(),
        'host': collect_host(identifier),
        'network': collect_network(),
        'os': collect_os(),
        'patches': collect_patches(),
        'schema_version': SCHEMA_VERSION,
        'security': collect_security(),
        'services': collect_services(),
        'startup_items': collect_startup_items(),
        'users': collect_users(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--identifier', default='',
                        help='device identifier (default: hostname)')
    parser.add_argument('-o', '--output', default='',
                        help='output file (default: <identifier>.json in CWD)')
    parser.add_argument('--collector', default='baseline-export',
                        help='collection.collector value (default: baseline-export)')
    parser.add_argument('--method', default='local',
                        help='collection.method value (default: local)')
    args = parser.parse_args()

    if not is_root():
        print('warning: not running as root -- shadow, dmidecode, sshd -T and '
              'user crontabs will be incomplete', file=sys.stderr)

    data = collect(args.identifier, args.collector, args.method)
    out_path = args.output or '%s.json' % data['host']['identifier']
    with open(out_path, 'w') as f:
        f.write(json.dumps(data, indent=4, sort_keys=True) + '\n')
    print('wrote %s' % os.path.abspath(out_path))


if __name__ == '__main__':
    main()
