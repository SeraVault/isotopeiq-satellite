"""
IsotopeIQ Linux Agent
Collects system baseline data and outputs the canonical object as JSON to stdout.

Compatible with Python 2.6+ and Python 3.x.
No third-party dependencies — stdlib only.

Compile with PyInstaller (produces a single self-contained ELF):
    pyinstaller --onefile linux_collector.py

The resulting binary can be copied to any Linux host (matching arch) and run
as any user.  Most privileged data (shadow, suid scan, firewall rules) is
collected automatically when running as root; non-root runs silently skip
commands that require elevation.
"""
from __future__ import print_function

import json
import os
import re
import socket
import subprocess
import sys

try:
    from http.server import BaseHTTPRequestHandler, HTTPServer  # Python 3
except ImportError:
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer  # Python 2

try:
    import argparse
    HAS_ARGPARSE = True
except ImportError:
    HAS_ARGPARSE = False  # Python 2.6 — manual fallback below


# ---------------------------------------------------------------------------
# Config file
# The agent reads token (and optionally port) from isotopeiq-agent.conf.
# Checked in order: next to the binary, then /etc/isotopeiq-agent.conf.
# Format (key=value, one per line, # comments ignored):
#   token=<hex>
#   port=9322
# ---------------------------------------------------------------------------

def _read_config():
    paths = []
    try:
        paths.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'isotopeiq-agent.conf'))
    except Exception:
        pass
    paths.append('/etc/isotopeiq-agent.conf')
    for path in paths:
        try:
            cfg = {}
            with open(path, 'r') as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith('#') or '=' not in line:
                        continue
                    key, _, val = line.partition('=')
                    cfg[key.strip()] = val.strip()
            if cfg:
                return cfg
        except Exception:
            pass
    return {}

PY2 = sys.version_info[0] == 2

if PY2:
    string_types = (str, unicode)  # noqa: F821
else:
    string_types = (str,)

# Default listener port.  9322 is unassigned in the IANA Service Name registry,
# outside the Prometheus exporter range (9100-9299), and clear of all IANA
# well-known / registered ports commonly deployed in enterprise environments.
DEFAULT_AGENT_PORT = 9322


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(cmd, shell=True):
    """Run a shell command, return stdout as a unicode string. Never raises."""
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=shell,
        )
        stdout, _ = proc.communicate()
        if isinstance(stdout, bytes):
            return stdout.decode('utf-8', errors='replace').strip()
        return stdout.strip()
    except Exception:
        return ''


def run_lines(cmd):
    """Run a command and return non-empty stripped lines."""
    return [ln for ln in run(cmd).splitlines() if ln.strip()]


def which(cmd):
    """Return True if cmd is available on PATH."""
    return run('command -v {0} 2>/dev/null'.format(cmd)) != ''


def is_root():
    try:
        return os.getuid() == 0
    except AttributeError:
        return False


def read_file(path):
    """Read a file, return contents as str. Returns '' on any error."""
    try:
        with open(path, 'r') as fh:
            return fh.read()
    except Exception:
        return ''


def read_lines(path):
    """Read a file, return non-empty stripped lines."""
    return [ln.rstrip('\n') for ln in read_file(path).splitlines() if ln.strip()]


# ---------------------------------------------------------------------------
# Elevation helper
# The binary is typically run as root via sudo from the Satellite server.
# When not root, privileged commands are silently skipped.
# ---------------------------------------------------------------------------

def priv(cmd):
    """Run cmd with privilege; returns output or '' if insufficient privilege."""
    if is_root():
        return run(cmd)
    # Try sudo without password (NOPASSWD sudoers entry)
    out = run('sudo -n {0} 2>/dev/null'.format(cmd))
    return out


# ---------------------------------------------------------------------------
# Canonical skeleton
# ---------------------------------------------------------------------------

def empty_canonical():
    return {
        'device': {
            'hostname': '', 'fqdn': '', 'device_type': 'server',
            'vendor': '', 'model': '',
        },
        'hardware': {
            'cpu_model': '', 'cpu_cores': None, 'memory_gb': None,
            'bios_version': '', 'serial_number': '', 'architecture': '',
            'virtualization_type': 'bare-metal',
        },
        'os': {
            'name': '', 'version': '', 'build': '', 'kernel': '',
            'timezone': '', 'ntp_servers': [], 'ntp_synced': None,
        },
        'network': {
            'interfaces': [], 'dns_servers': [], 'default_gateway': '',
            'routes': [], 'hosts_file': [], 'open_ports': [],
        },
        'users': [],
        'groups': [],
        'packages': [],
        'services': [],
        'filesystem': [],
        'security': {
            'firewall_enabled': None, 'antivirus': '',
            'secure_boot': None, 'selinux_mode': '', 'apparmor_status': '',
            'audit_logging_enabled': None, 'uac_enabled': None,
            'defender_enabled': None,
        },
        'scheduled_tasks': [],
        'startup_items': [],
        'ssh_keys': [],
        'kernel_modules': [],
        'pci_devices': [],
        'storage_devices': [],
        'usb_devices': [],
        'listening_services': [],
        'firewall_rules': [],
        'sysctl': [],
        'certificates': [],
        'logging_targets': [],
        'custom': {},
    }


# ---------------------------------------------------------------------------
# device
# ---------------------------------------------------------------------------

def collect_device(output):
    hostname = run('hostname').strip() or socket.gethostname()
    try:
        fqdn = socket.getfqdn()
    except Exception:
        fqdn = hostname

    vendor = (
        read_file('/sys/class/dmi/id/sys_vendor').strip() or
        priv('dmidecode -s system-manufacturer 2>/dev/null').strip()
    )
    model = (
        read_file('/sys/class/dmi/id/product_name').strip() or
        priv('dmidecode -s system-product-name 2>/dev/null').strip()
    )

    output['device']['hostname']    = hostname
    output['device']['fqdn']        = fqdn
    output['device']['device_type'] = 'server'
    output['device']['vendor']      = vendor
    output['device']['model']       = model


# ---------------------------------------------------------------------------
# hardware
# ---------------------------------------------------------------------------

def collect_hardware(output):
    # CPU model — /proc/cpuinfo works back to kernel 2.0
    cpu_model = ''
    for line in read_lines('/proc/cpuinfo'):
        if line.startswith('model name') or line.startswith('cpu model'):
            cpu_model = line.split(':', 1)[-1].strip()
            break
    if not cpu_model:
        # Some ARM boards use 'Processor' or 'Hardware'
        for line in read_lines('/proc/cpuinfo'):
            if line.startswith('Processor') or line.startswith('Hardware'):
                cpu_model = line.split(':', 1)[-1].strip()
                break

    # Core count
    cpu_cores = None
    nproc_out = run('nproc --all 2>/dev/null || nproc 2>/dev/null')
    if nproc_out.isdigit():
        cpu_cores = int(nproc_out)
    else:
        count = len([l for l in read_lines('/proc/cpuinfo') if l.startswith('processor')])
        if count:
            cpu_cores = count

    # Memory from /proc/meminfo
    mem_gb = None
    for line in read_lines('/proc/meminfo'):
        if line.startswith('MemTotal'):
            m = re.search(r'(\d+)', line)
            if m:
                try:
                    mem_gb = round(int(m.group(1)) / 1048576.0, 2)
                except (ValueError, TypeError):
                    pass
            break

    # BIOS / firmware
    bios_ver = (
        read_file('/sys/class/dmi/id/bios_version').strip() or
        priv('dmidecode -s bios-version 2>/dev/null').strip()
    )

    # Serial number — world-readable on some hypervisors, needs root on physical
    serial = (
        read_file('/sys/class/dmi/id/product_serial').strip() or
        priv('dmidecode -s system-serial-number 2>/dev/null').strip()
    )

    arch = run('uname -m').strip()

    # Virtualization detection — prefer systemd-detect-virt, fall back to heuristics
    virt = 'bare-metal'
    virt_raw = run('systemd-detect-virt 2>/dev/null').strip().lower()
    if virt_raw and virt_raw not in ('none', 'chroot', ''):
        virt_map = {
            'kvm': 'kvm', 'qemu': 'kvm',
            'vmware': 'vmware',
            'oracle': 'virtualbox', 'virtualbox': 'virtualbox',
            'microsoft': 'hyperv', 'hyperv': 'hyperv',
            'xen': 'xen',
            'docker': 'other', 'lxc': 'other', 'openvz': 'other',
            'systemd-nspawn': 'other', 'container-other': 'other',
        }
        virt = virt_map.get(virt_raw, 'other')
    else:
        # Fallback: check cpuinfo flags and kernel params
        cpuinfo = read_file('/proc/cpuinfo').lower()
        if 'hypervisor' in cpuinfo:
            virt = 'other'
        dmi_vendor = read_file('/sys/class/dmi/id/sys_vendor').strip().lower()
        if 'vmware' in dmi_vendor:
            virt = 'vmware'
        elif 'virtualbox' in dmi_vendor:
            virt = 'virtualbox'
        elif 'microsoft' in dmi_vendor:
            virt = 'hyperv'
        elif 'xen' in dmi_vendor:
            virt = 'xen'
        elif 'qemu' in dmi_vendor or 'kvm' in dmi_vendor:
            virt = 'kvm'

    output['hardware']['cpu_model']           = cpu_model
    output['hardware']['cpu_cores']           = cpu_cores
    output['hardware']['memory_gb']           = mem_gb
    output['hardware']['bios_version']        = bios_ver
    output['hardware']['serial_number']       = serial
    output['hardware']['architecture']        = arch
    output['hardware']['virtualization_type'] = virt


# ---------------------------------------------------------------------------
# os
# ---------------------------------------------------------------------------

def collect_os(output):
    name = version = build = ''

    # /etc/os-release is the standard on systemd distros (Debian 7+, RHEL 7+,
    # SUSE 12+, Arch, Alpine 3.x, etc.)
    if os.path.isfile('/etc/os-release'):
        for line in read_lines('/etc/os-release'):
            if '=' not in line or line.startswith('#'):
                continue
            k, _, v = line.partition('=')
            v = v.strip().strip('"\'')
            if k == 'NAME' and not name:
                name = v
            elif k == 'VERSION_ID' and not version:
                version = v
            elif k == 'BUILD_ID' and not build:
                build = v
            elif k == 'VERSION' and not build:
                build = v
    elif os.path.isfile('/etc/alpine-release'):
        name = 'Alpine Linux'
        version = read_file('/etc/alpine-release').strip()
    elif os.path.isfile('/etc/redhat-release'):
        line = read_lines('/etc/redhat-release')[0] if read_lines('/etc/redhat-release') else ''
        name = line
        m = re.search(r'[\d.]+', line)
        version = m.group(0) if m else ''
    elif os.path.isfile('/etc/debian_version'):
        name = 'Debian'
        version = read_file('/etc/debian_version').strip()
    elif os.path.isfile('/etc/SuSE-release'):
        lines_s = read_lines('/etc/SuSE-release')
        name = lines_s[0] if lines_s else 'SUSE'
        for l in lines_s:
            if l.startswith('VERSION'):
                version = l.split('=', 1)[-1].strip()

    kernel = run('uname -r').strip()

    # Timezone — multiple fallback paths for old distros
    tz = ''
    if os.path.isfile('/etc/timezone'):
        tz = read_file('/etc/timezone').strip()
    if not tz and which('timedatectl'):
        tz = run('timedatectl show -p Timezone --value 2>/dev/null').strip()
    if not tz and os.path.islink('/etc/localtime'):
        link = os.readlink('/etc/localtime')
        m = re.search(r'zoneinfo/(.+)', link)
        if m:
            tz = m.group(1)
    if not tz and os.path.isfile('/etc/sysconfig/clock'):
        for line in read_lines('/etc/sysconfig/clock'):
            if line.startswith('ZONE=') or line.startswith('TIMEZONE='):
                tz = line.split('=', 1)[-1].strip().strip('"\'')
                break

    # NTP servers — check all common config locations
    ntp_servers = []
    for path in ['/etc/systemd/timesyncd.conf', '/etc/chrony.conf',
                 '/etc/chrony/chrony.conf', '/etc/ntp.conf']:
        if not os.path.isfile(path):
            continue
        for line in read_lines(path):
            line = line.strip()
            if line.startswith('#'):
                continue
            # timesyncd: NTP=a b c
            if line.startswith('NTP='):
                ntp_servers = line.split('=', 1)[-1].strip().split()
                break
            # chrony / ntp: server hostname [options]
            if line.startswith('server ') or line.startswith('pool '):
                parts = line.split()
                if len(parts) >= 2 and parts[1] not in ('local', '127.127.1.0'):
                    ntp_servers.append(parts[1])
        if ntp_servers:
            break

    # NTP sync state
    ntp_synced = None
    if which('timedatectl'):
        ts_out = run('timedatectl show -p NTPSynchronized --value 2>/dev/null').strip().lower()
        if ts_out == 'yes':
            ntp_synced = True
        elif ts_out == 'no':
            ntp_synced = False
    elif which('ntpstat'):
        ntp_synced = (run('ntpstat >/dev/null 2>&1; echo $?').strip() == '0')
    elif which('chronyc'):
        tracking = run('chronyc -n tracking 2>/dev/null')
        ntp_synced = 'Reference ID' in tracking and '0.0.0.0' not in tracking

    output['os']['name']        = name
    output['os']['version']     = version
    output['os']['build']       = build
    output['os']['kernel']      = kernel
    output['os']['timezone']    = tz
    output['os']['ntp_servers'] = ntp_servers
    output['os']['ntp_synced']  = ntp_synced


# ---------------------------------------------------------------------------
# network
# ---------------------------------------------------------------------------

def _empty_iface(name):
    return {
        'name': name, 'mac': '', 'description': '',
        'ipv4': [], 'ipv6': [],
        'admin_status': 'unknown', 'oper_status': 'unknown',
        'speed': '', 'duplex': 'unknown', 'mtu': None,
        'port_mode': 'routed', 'access_vlan': None, 'trunk_vlans': '',
    }


def _prefix_from_mask(mask):
    try:
        return sum(bin(int(o)).count('1') for o in mask.split('.'))
    except Exception:
        return 24


def collect_network(output):
    iface_map = {}

    # ── ip addr (iproute2, available since ~2.1.x kernel era) ────────────────
    ip_out = run('ip addr show 2>/dev/null')
    if ip_out:
        current = None
        for line in ip_out.splitlines():
            # New interface block: "2: eth0: <FLAGS> mtu ..."
            m = re.match(r'^\d+:\s+(\S+?)[@:]?\s', line)
            if m:
                current = m.group(1).rstrip(':')
                if current not in iface_map:
                    iface_map[current] = _empty_iface(current)
                # State from flags
                if 'UP' in line:
                    iface_map[current]['oper_status'] = 'up'
                    iface_map[current]['admin_status'] = 'up'
                elif 'DOWN' in line:
                    iface_map[current]['oper_status']  = 'down'
                    iface_map[current]['admin_status'] = 'down'
                # MTU
                mtu_m = re.search(r'mtu\s+(\d+)', line)
                if mtu_m:
                    iface_map[current]['mtu'] = int(mtu_m.group(1))
                continue
            if not current:
                continue
            # MAC
            mac_m = re.match(r'\s+link/\S+\s+([0-9a-f:]{17})', line)
            if mac_m:
                iface_map[current]['mac'] = mac_m.group(1)
                continue
            # IPv4 — "inet 192.168.1.1/24 ..."
            v4_m = re.match(r'\s+inet\s+(\d+\.\d+\.\d+\.\d+(?:/\d+)?)', line)
            if v4_m:
                addr = v4_m.group(1)
                if not addr.startswith('127.'):
                    iface_map[current]['ipv4'].append(addr)
                continue
            # IPv6 — "inet6 fe80::1/64 ..."
            v6_m = re.match(r'\s+inet6\s+([0-9a-f:]+(?:/\d+)?)', line)
            if v6_m:
                addr = v6_m.group(1)
                if not addr.startswith('::1'):
                    iface_map[current]['ipv6'].append(addr)

    else:
        # ── ifconfig fallback (BSD-style or net-tools on very old distros) ────
        current = None
        for line in run('ifconfig -a 2>/dev/null').splitlines():
            # Interface name — may appear as "eth0:" or "eth0 Link ..."
            m = re.match(r'^(\S+?)(?::\s|\s+Link|\s+flags)', line)
            if m and not line.startswith(' '):
                current = m.group(1).rstrip(':')
                if current not in iface_map:
                    iface_map[current] = _empty_iface(current)
                continue
            if not current:
                continue
            # MAC
            mac_m = re.search(r'(?:HWaddr|ether)\s+([0-9a-fA-F:]{17})', line)
            if mac_m:
                iface_map[current]['mac'] = mac_m.group(1).lower()
            # IPv4
            v4_m = re.search(r'inet\s+(?:addr:)?(\d+\.\d+\.\d+\.\d+)', line)
            mask_m = re.search(r'[Mm]ask:?(\d+\.\d+\.\d+\.\d+)', line)
            if v4_m:
                ip = v4_m.group(1)
                if not ip.startswith('127.'):
                    if mask_m:
                        prefix = _prefix_from_mask(mask_m.group(1))
                        iface_map[current]['ipv4'].append('{0}/{1}'.format(ip, prefix))
                    else:
                        iface_map[current]['ipv4'].append(ip)
            # IPv6
            v6_m = re.search(r'inet6\s+(?:addr:)?\s*([0-9a-f:]+(?:/\d+)?)', line)
            if v6_m:
                addr = v6_m.group(1).strip()
                if not addr.startswith('::1'):
                    iface_map[current]['ipv6'].append(addr)

    output['network']['interfaces'] = list(iface_map.values())

    # ── DNS servers from /etc/resolv.conf ─────────────────────────────────────
    dns = []
    for line in read_lines('/etc/resolv.conf'):
        if line.startswith('nameserver'):
            parts = line.split()
            if len(parts) >= 2:
                dns.append(parts[1])
    output['network']['dns_servers'] = dns

    # ── Default gateway ───────────────────────────────────────────────────────
    gw = ''
    # ip route show default
    gw_out = run('ip route show default 2>/dev/null') or run('ip route 2>/dev/null')
    m = re.search(r'default\s+via\s+(\S+)', gw_out)
    if m:
        gw = m.group(1)
    else:
        # netstat -rn / route -n fallback
        route_out = run('netstat -rn 2>/dev/null') or run('route -n 2>/dev/null')
        for line in route_out.splitlines():
            if re.match(r'^(0\.0\.0\.0|default)\s', line):
                parts = line.split()
                if len(parts) >= 2:
                    gw = parts[1] if parts[1] != '0.0.0.0' else (parts[2] if len(parts) > 2 else '')
                    break
    output['network']['default_gateway'] = gw

    # ── Routes ────────────────────────────────────────────────────────────────
    routes = []
    ip_route = run('ip route show 2>/dev/null')
    if ip_route:
        for line in ip_route.splitlines():
            line = line.strip()
            if not line:
                continue
            # "192.168.1.0/24 via 10.0.0.1 dev eth0"  or  "default via 10.0.0.1 dev eth0"
            dest = line.split()[0]
            if dest == 'default':
                dest = '0.0.0.0/0'
            via_m  = re.search(r'via\s+(\S+)', line)
            dev_m  = re.search(r'dev\s+(\S+)', line)
            met_m  = re.search(r'metric\s+(\d+)', line)
            routes.append({
                'destination': dest,
                'gateway':     via_m.group(1)  if via_m  else '',
                'interface':   dev_m.group(1)  if dev_m  else '',
                'metric':      int(met_m.group(1)) if met_m else None,
            })
    else:
        # netstat -rn fallback
        for line in run('netstat -rn 2>/dev/null').splitlines():
            m = re.match(r'^(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+\d+\s+\d+\s+\d+\s+(\S+)', line)
            if m:
                dest_raw, gw_raw, mask, _flags, iface = m.groups()
                if dest_raw in ('Destination', 'destination'):
                    continue
                if dest_raw == '0.0.0.0' and mask == '0.0.0.0':
                    dest_raw = '0.0.0.0/0'
                elif '/' not in dest_raw:
                    try:
                        prefix = _prefix_from_mask(mask)
                        dest_raw = '{0}/{1}'.format(dest_raw, prefix)
                    except Exception:
                        pass
                routes.append({
                    'destination': dest_raw,
                    'gateway':     gw_raw if gw_raw != '0.0.0.0' else '',
                    'interface':   iface,
                    'metric':      None,
                })
    output['network']['routes'] = routes

    # ── Hosts file ────────────────────────────────────────────────────────────
    hosts = []
    for line in read_lines('/etc/hosts'):
        if line.startswith('#'):
            continue
        parts = line.split()
        if len(parts) >= 2:
            hosts.append({'ip': parts[0], 'hostname': parts[1]})
    output['network']['hosts_file'] = hosts


# ---------------------------------------------------------------------------
# users
# ---------------------------------------------------------------------------

def collect_users(output):
    # Build sudo/admin set — check sudo group and wheel group members
    priv_set = set()
    for grp_line in read_lines('/etc/group'):
        parts = grp_line.split(':')
        if len(parts) < 4:
            continue
        gname   = parts[0]
        members = [m.strip() for m in parts[3].split(',') if m.strip()]
        if gname in ('sudo', 'wheel', 'admin'):
            priv_set.update(members)

    # /etc/shadow for disabled status (root only)
    shadow = {}
    for line in priv('cat /etc/shadow 2>/dev/null').splitlines():
        parts = line.split(':')
        if len(parts) < 2:
            continue
        uname  = parts[0]
        passwd = parts[1]
        # Account is disabled if password hash is '!' or '*' (locked)
        shadow[uname] = passwd.startswith('!') or passwd == '*'

    for line in read_lines('/etc/passwd'):
        parts = line.split(':')
        if len(parts) < 7:
            continue
        uname  = parts[0]
        uid    = parts[2]
        gid    = parts[3]
        home   = parts[5]
        shell  = parts[6]

        # UID filter — include all accounts (system and human alike) for full baseline
        try:
            uid_i = int(uid)
        except ValueError:
            uid_i = -1

        # Groups via id command (works on all distros)
        groups_out = run('id -Gn {0} 2>/dev/null'.format(uname))
        groups = groups_out.split() if groups_out else []

        disabled = shadow.get(uname)  # None if shadow not readable

        # Sudo privileges
        sudo_priv = ''
        if uname in priv_set:
            sudo_priv = 'ALL'
        else:
            # Check sudoers for explicit entry (needs root)
            sudo_check = priv('sudo -l -U {0} 2>/dev/null'.format(uname))
            if sudo_check and 'ALL' in sudo_check:
                sudo_priv = 'ALL'

        # Password last changed from shadow field 3 (days since epoch)
        pwd_last = ''
        pwd_last_raw = ''
        shadow_line = priv('getent shadow {0} 2>/dev/null'.format(uname))
        if shadow_line:
            sp = shadow_line.split(':')
            if len(sp) > 2 and sp[2].isdigit():
                try:
                    import datetime
                    epoch = datetime.date(1970, 1, 1)
                    d = epoch + datetime.timedelta(days=int(sp[2]))
                    pwd_last = d.isoformat()
                except Exception:
                    pwd_last = sp[2]

        # Last login from lastlog
        last_login = ''
        lastlog_out = run('lastlog -u {0} 2>/dev/null'.format(uname))
        if lastlog_out:
            lines_ll = lastlog_out.splitlines()
            if len(lines_ll) >= 2:
                entry = lines_ll[-1].strip()
                if 'Never logged in' not in entry and entry:
                    last_login = entry

        output['users'].append({
            'username':          uname,
            'uid':               uid,
            'groups':            groups,
            'home':              home,
            'shell':             shell,
            'disabled':          disabled,
            'password_last_set': pwd_last,
            'last_login':        last_login,
            'sudo_privileges':   sudo_priv,
        })


# ---------------------------------------------------------------------------
# groups
# ---------------------------------------------------------------------------

def collect_groups(output):
    for line in read_lines('/etc/group'):
        parts = line.split(':')
        if len(parts) < 3 or not parts[0]:
            continue
        gname   = parts[0]
        gid     = parts[2]
        members = [m.strip() for m in parts[3].split(',') if m.strip()] if len(parts) > 3 else []
        output['groups'].append({
            'group_name': gname,
            'gid':        gid,
            'members':    members,
        })


# ---------------------------------------------------------------------------
# packages
# ---------------------------------------------------------------------------

def collect_packages(output):
    collected = False

    # dpkg (Debian / Ubuntu / Raspbian / etc.)
    if which('dpkg-query'):
        out = run("dpkg-query -W -f='${Package}|${Version}|${Maintainer}|\\n' 2>/dev/null")
        if not out:
            out = run("dpkg-query -W -f='${Package}|${Version}||\\n' 2>/dev/null")
        for line in out.splitlines():
            parts = line.rstrip('|').split('|')
            if not parts[0].strip():
                continue
            output['packages'].append({
                'name':         parts[0].strip(),
                'version':      parts[1].strip() if len(parts) > 1 else '',
                'vendor':       parts[2].strip() if len(parts) > 2 else '',
                'install_date': '',
                'source':       'deb',
            })
        if output['packages']:
            collected = True

    # rpm (RHEL / CentOS / Fedora / SUSE / Amazon Linux)
    if which('rpm') and not collected:
        out = run("rpm -qa --queryformat '%{NAME}|%{VERSION}-%{RELEASE}|%{VENDOR}|%{INSTALLTIME:date}\\n' 2>/dev/null")
        _before = len(output['packages'])
        for line in out.splitlines():
            parts = line.split('|')
            if not parts[0].strip():
                continue
            output['packages'].append({
                'name':         parts[0].strip(),
                'version':      parts[1].strip() if len(parts) > 1 else '',
                'vendor':       parts[2].strip() if len(parts) > 2 else '',
                'install_date': parts[3].strip() if len(parts) > 3 else '',
                'source':       'rpm',
            })
        if len(output['packages']) > _before:
            collected = True

    # apk (Alpine Linux)
    if which('apk') and not collected:
        out = run('apk info -v 2>/dev/null')
        _before = len(output['packages'])
        for line in out.splitlines():
            # e.g. "busybox-1.36.1-r0"
            m = re.match(r'^(.+)-(\d[^-]*-r\d+)$', line.strip())
            if m:
                output['packages'].append({
                    'name':         m.group(1),
                    'version':      m.group(2),
                    'vendor':       '',
                    'install_date': '',
                    'source':       'apk',
                })
        if len(output['packages']) > _before:
            collected = True

    # pacman (Arch / Manjaro)
    if which('pacman') and not collected:
        _before = len(output['packages'])
        for line in run_lines('pacman -Q 2>/dev/null'):
            parts = line.split(None, 1)
            output['packages'].append({
                'name':         parts[0],
                'version':      parts[1] if len(parts) > 1 else '',
                'vendor':       '',
                'install_date': '',
                'source':       'pacman',
            })
        if len(output['packages']) > _before:
            collected = True

    # zypper (SUSE / openSUSE)
    if which('zypper') and not collected:
        out = run('zypper --no-color packages --installed-only 2>/dev/null')
        _before = len(output['packages'])
        for line in out.splitlines():
            parts = [p.strip() for p in line.split('|')]
            # Format: S | Repository | Name | Version | Arch
            if len(parts) >= 4 and parts[0].strip().lower() in ('i', 'i+'):
                output['packages'].append({
                    'name':         parts[2],
                    'version':      parts[3],
                    'vendor':       '',
                    'install_date': '',
                    'source':       'rpm',
                })
        if len(output['packages']) > _before:
            collected = True

    # snap (any distro)
    if which('snap'):
        out = run('snap list 2>/dev/null')
        for line in out.splitlines()[1:]:
            parts = line.split()
            if parts:
                output['packages'].append({
                    'name':         parts[0],
                    'version':      parts[1] if len(parts) > 1 else '',
                    'vendor':       '',
                    'install_date': '',
                    'source':       'snap',
                })

    # flatpak (any distro)
    if which('flatpak'):
        out = run('flatpak list --app --columns=application,version 2>/dev/null')
        for line in out.splitlines():
            parts = line.split('\t')
            if parts:
                output['packages'].append({
                    'name':         parts[0].strip(),
                    'version':      parts[1].strip() if len(parts) > 1 else '',
                    'vendor':       '',
                    'install_date': '',
                    'source':       'flatpak',
                })


# ---------------------------------------------------------------------------
# services
# ---------------------------------------------------------------------------

def _detect_init():
    if which('systemctl') and run('systemctl --version 2>/dev/null'):
        return 'systemd'
    if os.path.isfile('/sbin/openrc') or which('rc-service'):
        return 'openrc'
    if os.path.isfile('/sbin/initctl') and 'upstart' in run('/sbin/initctl --version 2>/dev/null'):
        return 'upstart'
    return 'sysvinit'


def collect_services(output):
    init = _detect_init()
    status_map  = {'active': 'running', 'running': 'running',
                   'inactive': 'stopped', 'stopped': 'stopped', 'failed': 'stopped'}
    startup_map = {'enabled': 'enabled', 'disabled': 'disabled',
                   'static': 'manual', 'manual': 'manual', 'masked': 'disabled'}

    if init == 'systemd':
        # list-unit-files gives only units with a persistent file on disk —
        # this excludes transient, runtime-generated, and session units that
        # would otherwise change every boot/login.
        enabled_out = run('systemctl list-unit-files --type=service --no-pager --no-legend 2>/dev/null')
        enabled_map = {}
        for line in enabled_out.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                sname = parts[0].replace('.service', '')
                enabled_map[sname] = parts[1].lower()

        # Get current running state only for units that have a unit file.
        active_map = {}
        units_out = run('systemctl list-units --type=service --all --no-pager --no-legend 2>/dev/null')
        for line in units_out.splitlines():
            parts = line.split(None, 4)
            if len(parts) < 3:
                continue
            unit = parts[0].replace('.service', '')
            if unit.startswith('●'):
                unit = unit[1:]
            active_map[unit] = parts[2].lower()

        for unit, startup_raw in sorted(enabled_map.items()):
            if startup_raw == 'masked':
                continue
            active = active_map.get(unit, 'inactive')
            output['services'].append({
                'name':    unit,
                'status':  status_map.get(active, 'unknown'),
                'startup': startup_map.get(startup_raw, startup_raw),
            })

    elif init == 'openrc':
        for line in run_lines('rc-status --all --nocolor 2>/dev/null'):
            m = re.match(r'\s+(\S+)\s+\[\s*(\S+)\s*\]', line)
            if m:
                output['services'].append({
                    'name':    m.group(1),
                    'status':  'running' if m.group(2).lower() == 'started' else 'stopped',
                    'startup': 'unknown',
                })

    elif init == 'upstart':
        for line in run_lines('initctl list 2>/dev/null'):
            parts = line.split(None, 2)
            if len(parts) >= 2:
                output['services'].append({
                    'name':    parts[0],
                    'status':  'running' if 'running' in parts[1] else 'stopped',
                    'startup': 'unknown',
                })

    else:
        # SysVinit — iterate /etc/init.d scripts
        if os.path.isdir('/etc/init.d'):
            for svc in sorted(os.listdir('/etc/init.d')):
                path = os.path.join('/etc/init.d', svc)
                if not os.path.isfile(path):
                    continue
                status_out = run('{0} status 2>/dev/null'.format(path))
                running = bool(re.search(r'running|started|active', status_out, re.IGNORECASE))
                output['services'].append({
                    'name':    svc,
                    'status':  'running' if running else 'stopped',
                    'startup': 'unknown',
                })


# ---------------------------------------------------------------------------
# filesystem
# ---------------------------------------------------------------------------

def collect_filesystem(output):
    # Mount options from /proc/mounts (present since kernel 2.4)
    mount_opts = {}
    for line in read_lines('/proc/mounts'):
        parts = line.split()
        if len(parts) >= 4:
            mount_opts[parts[1]] = parts[3].split(',')

    # SUID files per mount point (root only, skip network and pseudo FSes)
    suid_files = {}
    if is_root():
        suid_out = run('find / -xdev \\( -perm -4000 -o -perm -2000 \\) -type f 2>/dev/null | sort')
        for path in suid_out.splitlines():
            path = path.strip()
            if not path:
                continue
            # Associate with longest matching mount point
            best = '/'
            for mp in mount_opts:
                if path.startswith(mp) and len(mp) > len(best):
                    best = mp
            suid_files.setdefault(best, []).append(path)

    # df -P -T gives: Filesystem Type 1K-blocks Used Available Use% Mounted
    # -T may not exist on old BusyBox df; fall back to -P only
    df_out = run('df -P -T 2>/dev/null') or run('df -P 2>/dev/null')
    for line in df_out.splitlines():
        parts = line.split()
        # Skip header
        if parts and parts[0] in ('Filesystem',):
            continue

        # With -T:  device type   blocks used avail pct mount
        # Without:  device        blocks used avail pct mount
        if len(parts) >= 7 and not parts[0].startswith('/') and parts[1].startswith('/'):
            # Wrapped line from df — skip (rare)
            continue

        if len(parts) == 7:
            # With type column
            device, fstype, blocks, used, avail, _pct, mount = parts
        elif len(parts) == 6:
            # Without type column
            device, blocks, used, avail, _pct, mount = parts
            fstype = ''
        else:
            continue

        # Skip pseudo/virtual FSes
        if fstype in ('tmpfs', 'devtmpfs', 'sysfs', 'proc', 'cgroup',
                      'cgroup2', 'devpts', 'securityfs', 'pstore',
                      'hugetlbfs', 'mqueue', 'debugfs', 'tracefs',
                      'configfs', 'fusectl', 'overlay') or device in ('none', 'tmpfs'):
            continue
        if not device.startswith('/') and not device.startswith('//'):
            continue

        try:
            size_gb = round(int(blocks) * 1024 / (1024 ** 3), 2)
        except (ValueError, TypeError):
            size_gb = None
        try:
            free_gb = round(int(avail) * 1024 / (1024 ** 3), 2)
        except (ValueError, TypeError):
            free_gb = None

        output['filesystem'].append({
            'mount':         mount,
            'type':          fstype,
            'size_gb':       size_gb,
            'free_gb':       free_gb,
            'mount_options': mount_opts.get(mount, []),
            'suid_files':    suid_files.get(mount, []),
        })


# ---------------------------------------------------------------------------
# security
# ---------------------------------------------------------------------------

def collect_security(output):
    # SELinux
    selinux = run('getenforce 2>/dev/null').strip().lower()
    output['security']['selinux_mode'] = selinux if selinux else 'disabled'

    # AppArmor
    aa_status = ''
    if which('apparmor_status'):
        aa_out = priv('apparmor_status 2>/dev/null')
        aa_status = 'enabled' if '0 processes' not in aa_out and aa_out else 'disabled'
    elif os.path.isdir('/sys/kernel/security/apparmor'):
        aa_status = 'enabled'
    output['security']['apparmor_status'] = aa_status

    # Firewall state
    fw_enabled = None
    if which('ufw'):
        ufw_out = run('ufw status 2>/dev/null')
        if 'active' in ufw_out.lower():
            fw_enabled = True
        elif 'inactive' in ufw_out.lower():
            fw_enabled = False
    elif which('firewall-cmd'):
        fw_out = run('firewall-cmd --state 2>/dev/null')
        fw_enabled = fw_out.strip().lower() == 'running'
    elif which('iptables'):
        ipt_out = priv('iptables -L INPUT -n 2>/dev/null')
        # If there are any non-default rules, consider it enabled
        rule_lines = [l for l in ipt_out.splitlines() if l and not l.startswith('Chain') and not l.startswith('target')]
        fw_enabled = len(rule_lines) > 0 if ipt_out else None
    output['security']['firewall_enabled'] = fw_enabled

    # Secure boot
    sb_out = priv('mokutil --sb-state 2>/dev/null').strip().lower()
    if 'enabled' in sb_out:
        output['security']['secure_boot'] = True
    elif 'disabled' in sb_out:
        output['security']['secure_boot'] = False

    # Audit daemon
    audit_enabled = None
    if which('systemctl'):
        audit_status = run('systemctl is-active auditd 2>/dev/null').strip().lower()
        audit_enabled = audit_status == 'active'
    elif which('service'):
        audit_status = run('service auditd status 2>/dev/null')
        audit_enabled = bool(re.search(r'running|active', audit_status, re.IGNORECASE))
    output['security']['audit_logging_enabled'] = audit_enabled

    # Password policy from /etc/login.defs
    policy = {}
    for line in priv('grep -E "^(PASS_MIN_LEN|PASS_MAX_DAYS|PASS_WARN_AGE)" /etc/login.defs 2>/dev/null').splitlines():
        parts = line.split()
        if len(parts) >= 2:
            key  = parts[0].strip().lower()
            val  = parts[1].strip()
            try:
                ival = int(val)
                if key == 'pass_min_len':
                    policy['min_length'] = ival
                elif key == 'pass_max_days' and ival > 0:
                    policy['max_age_days'] = ival
                elif key == 'pass_warn_age':
                    policy['warn_age_days'] = ival
            except ValueError:
                pass
    if policy:
        output['security']['password_policy'] = policy


# ---------------------------------------------------------------------------
# scheduled tasks / cron
# ---------------------------------------------------------------------------

def collect_scheduled_tasks(output):
    # System crontabs
    cron_files = []
    if os.path.isfile('/etc/crontab'):
        cron_files.append(('/etc/crontab', 'system'))
    cron_d = '/etc/cron.d'
    if os.path.isdir(cron_d):
        for f in sorted(os.listdir(cron_d)):
            cron_files.append((os.path.join(cron_d, f), 'system'))

    for path, user_label in cron_files:
        for line in read_lines(path):
            if line.startswith('#') or not line.strip():
                continue
            # Determine user field presence (system crontab has user column)
            parts = line.split(None, 6)
            if len(parts) >= 6:
                output['scheduled_tasks'].append({
                    'name':     path,
                    'type':     'cron',
                    'command':  line,
                    'schedule': '',
                    'user':     user_label,
                    'enabled':  True,
                })

    # Per-user crontabs via crontab -l
    for line in read_lines('/etc/passwd'):
        uname = line.split(':')[0] if ':' in line else ''
        if not uname:
            continue
        ctab = run('crontab -l -u {0} 2>/dev/null'.format(uname))
        for cl in ctab.splitlines():
            if cl.startswith('#') or not cl.strip():
                continue
            output['scheduled_tasks'].append({
                'name':     'crontab:{0}'.format(uname),
                'type':     'cron',
                'command':  cl,
                'schedule': '',
                'user':     uname,
                'enabled':  True,
            })

    # Systemd timers
    # NOTE: do NOT use 'systemctl list-timers' - its NEXT/LAST columns are
    # volatile timestamps that change on every timer activation.  Instead,
    # read OnCalendar= (or OnBootSec= / OnUnitActiveSec=) directly from the
    # unit file on disk.  Only /etc/systemd/system and /usr/lib/systemd/system
    # are searched, so transient /run/systemd/transient/ timers are excluded.
    if _detect_init() == 'systemd' and which('systemctl'):
        timer_files_out = run('systemctl list-unit-files --type=timer --no-pager --no-legend 2>/dev/null')
        for tline in timer_files_out.splitlines():
            tparts = tline.split(None, 2)
            if len(tparts) < 2:
                continue
            unit_name, state = tparts[0], tparts[1]
            if state == 'masked':
                continue
            unit_file = None
            for d in ('/etc/systemd/system', '/usr/lib/systemd/system', '/lib/systemd/system'):
                candidate = os.path.join(d, unit_name)
                if os.path.isfile(candidate):
                    unit_file = candidate
                    break
            if not unit_file:
                continue
            schedule = ''
            for kw in ('OnCalendar=', 'OnBootSec=', 'OnUnitActiveSec='):
                for fline in read_lines(unit_file):
                    if fline.startswith(kw):
                        schedule = fline[len(kw):].strip()
                        break
                if schedule:
                    break
            output['scheduled_tasks'].append({
                'name':     unit_name,
                'type':     'systemd-timer',
                'command':  '',
                'schedule': schedule or 'unknown',
                'user':     'system',
                'enabled':  True,
            })


# ---------------------------------------------------------------------------
# ssh keys
# ---------------------------------------------------------------------------

def collect_ssh_keys(output):
    for line in read_lines('/etc/passwd'):
        parts = line.split(':')
        if len(parts) < 6:
            continue
        uname = parts[0]
        home  = parts[5]
        if not home:
            continue
        auth_keys = os.path.join(home, '.ssh', 'authorized_keys')
        try:
            for key_line in read_lines(auth_keys):
                key_line = key_line.strip()
                if not key_line or key_line.startswith('#'):
                    continue
                kparts = key_line.split(None, 2)
                if len(kparts) < 2:
                    continue
                output['ssh_keys'].append({
                    'username':   uname,
                    'key_type':   kparts[0],
                    'public_key': kparts[1],
                    'comment':    kparts[2] if len(kparts) > 2 else '',
                })
        except Exception:
            pass

    # Global authorized_keys for root / sshd AuthorizedKeysFile directive
    for extra in ['/etc/ssh/authorized_keys', '/root/.ssh/authorized_keys']:
        if not os.path.isfile(extra) or extra == '/root/.ssh/authorized_keys':
            continue  # /root is already covered above via passwd
        for key_line in read_lines(extra):
            key_line = key_line.strip()
            if not key_line or key_line.startswith('#'):
                continue
            kparts = key_line.split(None, 2)
            if len(kparts) < 2:
                continue
            output['ssh_keys'].append({
                'username':   'root',
                'key_type':   kparts[0],
                'public_key': kparts[1],
                'comment':    kparts[2] if len(kparts) > 2 else '',
            })


# ---------------------------------------------------------------------------
# ssh config (sshd_config)
# ---------------------------------------------------------------------------

def collect_ssh_config(output):
    settings = {}
    for line in priv('grep -v "^#" /etc/ssh/sshd_config 2>/dev/null').splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) == 2:
            settings[parts[0]] = parts[1]
    if settings:
        output['custom']['sshd_config'] = settings


# ---------------------------------------------------------------------------
# kernel modules
# ---------------------------------------------------------------------------

def collect_kernel_modules(output):
    lsmod_out = run('lsmod 2>/dev/null')
    for line in lsmod_out.splitlines()[1:]:
        parts = line.split()
        if not parts:
            continue
        name = parts[0]
        # Module path from /sys/module/<name>/filename (kernel 2.6+)
        mod_path = read_file('/sys/module/{0}/filename'.format(name)).strip()
        output['kernel_modules'].append({
            'name':        name,
            'type':        'module',
            'description': '',
            'path':        mod_path,
            'hash':        '',
            'signed':      None,
        })


# ---------------------------------------------------------------------------
# PCI devices
# ---------------------------------------------------------------------------

def collect_pci_devices(output):
    """Parse lspci -vmm output into pci_devices list."""
    if not which('lspci'):
        return
    out = run('lspci -vmm 2>/dev/null')
    if not out:
        return
    current = {}
    field_map = {
        'Slot':    'slot',
        'Class':   'class',
        'Vendor':  'vendor',
        'Device':  'device',
        'SVendor': 'subsystem_vendor',
        'SDevice': 'subsystem_device',
    }
    for line in out.splitlines():
        line = line.strip()
        if not line:
            if current.get('slot'):
                output['pci_devices'].append(current)
            current = {}
            continue
        if ':' in line:
            key, _, val = line.partition(':')
            key = key.strip()
            val = val.strip()
            canon = field_map.get(key)
            if canon:
                current[canon] = val
    # Flush last block if file didn't end with blank line
    if current.get('slot'):
        output['pci_devices'].append(current)
    # Attach kernel driver from lspci -k (one line per device)
    # Format: "<slot> <class>: <desc>\n\tKernel driver in use: <driver>"
    out_k = run('lspci -k 2>/dev/null')
    driver_map = {}
    cur_slot = None
    for line in out_k.splitlines():
        if line and not line.startswith('\t') and not line.startswith(' '):
            cur_slot = line.split()[0]
        elif cur_slot and 'Kernel driver in use:' in line:
            driver_map[cur_slot] = line.split(':', 1)[1].strip()
    for dev in output['pci_devices']:
        if dev.get('slot') in driver_map:
            dev['driver'] = driver_map[dev['slot']]


# ---------------------------------------------------------------------------
# storage devices
# ---------------------------------------------------------------------------

def collect_storage_devices(output):
    """Collect block/storage devices via lsblk."""
    if not which('lsblk'):
        return
    out = run('lsblk -d -n -P -o NAME,TYPE,SIZE,MODEL,VENDOR,SERIAL,TRAN,RM 2>/dev/null')
    if not out:
        return
    import re as _re
    for line in out.splitlines():
        kv = dict(_re.findall(r'(\w+)="([^"]*)"', line))
        name = kv.get('NAME', '').strip()
        if not name:
            continue
        entry = {'name': name}
        if kv.get('TYPE'):   entry['type']      = kv['TYPE'].strip()
        if kv.get('MODEL'):  entry['model']      = kv['MODEL'].strip()
        if kv.get('VENDOR'): entry['vendor']     = kv['VENDOR'].strip()
        if kv.get('SIZE'):   entry['size']       = kv['SIZE'].strip()
        if kv.get('SERIAL'): entry['serial']     = kv['SERIAL'].strip()
        if kv.get('TRAN'):   entry['interface']  = kv['TRAN'].strip()
        if kv.get('RM'):     entry['removable']  = kv['RM'].strip() == '1'
        output['storage_devices'].append(entry)


# ---------------------------------------------------------------------------
# USB devices
# ---------------------------------------------------------------------------

def collect_usb_devices(output):
    """Collect USB devices via lsusb."""
    if not which('lsusb'):
        return
    out = run('lsusb 2>/dev/null')
    if not out:
        return
    import re as _re
    pat = _re.compile(
        r'Bus (\d+) Device (\d+): ID ([0-9a-fA-F]+):([0-9a-fA-F]+)\s+(.*)'
    )
    for line in out.splitlines():
        m = pat.match(line.strip())
        if not m:
            continue
        output['usb_devices'].append({
            'bus_id':     f'{m.group(1)}/{m.group(2)}',
            'vendor_id':  m.group(3).lower(),
            'product_id': m.group(4).lower(),
            'product':    m.group(5).strip(),
        })


# ---------------------------------------------------------------------------
# listening services
# ---------------------------------------------------------------------------

def collect_listening_services(output):
    proto_map = {'tcp': 'tcp', 'tcp6': 'tcp6', 'udp': 'udp', 'udp6': 'udp6'}

    # Prefer ss (iproute2); fall back to netstat (net-tools)
    # -t TCP -u UDP -l LISTEN -n numeric -p process (needs root for PIDs)
    if which('ss'):
        out = priv('ss -tlunp 2>/dev/null') or run('ss -tlunp 2>/dev/null')
    elif which('netstat'):
        out = priv('netstat -tlunp 2>/dev/null') or run('netstat -tluWnp 2>/dev/null')
    else:
        return

    for line in out.splitlines():
        line = line.strip()
        if not line or line.startswith('Netid') or line.startswith('Proto') or line.startswith('Active'):
            continue

        parts = line.split()
        if len(parts) < 5:
            continue

        # ss format:  Netid State RecvQ SendQ Local              Peer
        # netstat:    Proto RefCnt Flags Type State I-Node  Path  (unix)
        #             Proto Recv-Q Send-Q Local               Foreign  State   PID/prog

        proto_raw = parts[0].lower().rstrip('46')
        if proto_raw not in ('tcp', 'udp'):
            continue

        # ss has "LISTEN" in State (col 1), netstat has it in a later column
        # Determine local address column
        if parts[0].lower() in ('tcp', 'tcp6', 'udp', 'udp6'):
            # netstat layout
            local = parts[3]
            proto_str = proto_map.get(parts[0].lower(), parts[0].lower())
        else:
            # ss layout — col 0=Netid 1=State 2=RecvQ 3=SendQ 4=LocalAddress
            local = parts[4]
            proto_str = proto_map.get(parts[0].lower().rstrip('46') + ('6' if '6' in parts[0] else ''), 'tcp')

        # Parse address:port — handle IPv6 [::]:port
        if local.startswith('['):
            m = re.match(r'\[(.+)\]:(\d+)', local)
            if not m:
                continue
            local_addr, port_s = m.group(1), m.group(2)
        elif local.startswith('*:'):
            local_addr = '0.0.0.0'
            port_s = local[2:]
        else:
            local_addr, _, port_s = local.rpartition(':')

        try:
            port = int(port_s)
        except ValueError:
            continue

        # Extract process name / PID from the last column (if root)
        proc_name = ''
        pid = None
        last = parts[-1]
        # ss: users:(("sshd",pid=1234,fd=3))  netstat: 1234/sshd
        pid_m = re.search(r'pid=(\d+)', last)
        if pid_m:
            pid = int(pid_m.group(1))
            nm = re.search(r'"([^"]+)"', last)
            if nm:
                proc_name = nm.group(1)
        else:
            fwd_m = re.match(r'(\d+)/(.*)', last)
            if fwd_m:
                pid = int(fwd_m.group(1))
                proc_name = fwd_m.group(2)

        output['listening_services'].append({
            'protocol':      proto_str,
            'local_address': local_addr,
            'port':          port,
            'process_name':  proc_name,
            'pid':           pid,
            'user':          '',
        })
        if port not in output['network']['open_ports']:
            output['network']['open_ports'].append(port)


# ---------------------------------------------------------------------------
# firewall rules
# ---------------------------------------------------------------------------

def collect_firewall_rules(output):
    # nftables (modern: Debian 10+, RHEL 8+, Arch, etc.)
    if which('nft'):
        nft_out = priv('nft list ruleset 2>/dev/null')
        if nft_out:
            _parse_nft(nft_out, output)
            return

    # iptables-save (legacy / compatibility layer under nft on many distros)
    if which('iptables-save'):
        ipt_out = priv('iptables-save 2>/dev/null')
        if ipt_out:
            _parse_iptables_save(ipt_out, output)

    # ip6tables-save — separate table on older kernels
    if which('ip6tables-save'):
        ip6t_out = priv('ip6tables-save 2>/dev/null')
        if ip6t_out:
            _parse_iptables_save(ip6t_out, output, ip6=True)


def _parse_iptables_save(text, output, ip6=False):
    """Parse iptables-save / ip6tables-save output into firewall_rules."""
    current_chain = ''
    current_table = ''
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('*'):
            current_table = line[1:].strip()
            continue
        if line.startswith(':'):
            # Chain default policy — :CHAIN POLICY [packets:bytes]
            parts = line[1:].split()
            current_chain = parts[0] if parts else ''
            continue
        if not line.startswith('-A'):
            continue
        # -A CHAIN [options...]
        parts = line.split(None, 2)
        if len(parts) < 2:
            continue
        chain = parts[1]

        direction = 'in' if chain in ('INPUT', 'PREROUTING') else ('out' if chain in ('OUTPUT', 'POSTROUTING') else 'unknown')
        action  = ''
        proto   = 'any'
        source  = 'any'
        dest    = 'any'
        port    = ''

        rule_str = parts[2] if len(parts) > 2 else ''
        j_m = re.search(r'-j\s+(\S+)', rule_str)
        if j_m:
            action = j_m.group(1).lower()
        p_m = re.search(r'-p\s+(\S+)', rule_str)
        if p_m:
            proto = p_m.group(1)
        s_m = re.search(r'-s\s+(\S+)', rule_str)
        if s_m:
            source = s_m.group(1)
        d_m = re.search(r'-d\s+(\S+)', rule_str)
        if d_m:
            dest = d_m.group(1)
        dp_m = re.search(r'--dport\s+(\S+)', rule_str)
        if dp_m:
            port = dp_m.group(1)
        elif re.search(r'--sport\s+(\S+)', rule_str):
            port = re.search(r'--sport\s+(\S+)', rule_str).group(1)

        output['firewall_rules'].append({
            'chain':       chain,
            'direction':   direction,
            'action':      action,
            'protocol':    proto,
            'source':      source,
            'destination': dest,
            'port':        port,
            'enabled':     True,
            'description': rule_str,
            'source_tool': 'ip6tables' if ip6 else 'iptables',
        })


def _parse_nft(text, output):
    """Parse nft list ruleset text output into firewall_rules."""
    current_chain = ''
    current_table = ''
    hook_dir_map  = {
        'input': 'in', 'prerouting': 'in',
        'output': 'out', 'postrouting': 'out',
        'forward': 'unknown',
    }
    action_map = {'accept': 'allow', 'drop': 'block', 'reject': 'block', 'return': 'allow'}

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        # table declaration
        m = re.match(r'^table\s+\S+\s+(\S+)', line)
        if m:
            current_table = m.group(1)
            continue
        # chain declaration — capture hook type for direction
        m = re.match(r'^chain\s+(\S+)', line)
        if m:
            current_chain = m.group(1)
            continue
        hook_m = re.search(r'hook\s+(\S+)', line)
        if hook_m:
            current_chain = hook_m.group(1)
            continue
        # Skip meta / policy lines
        if line in ('{', '}') or line.startswith('type ') or line.startswith('policy '):
            continue

        direction = hook_dir_map.get(current_chain.lower(), 'unknown')
        action  = ''
        proto   = 'any'
        source  = 'any'
        dest    = 'any'
        port    = ''

        # Verdict — last word is usually accept/drop/reject/return
        words = line.split()
        if words and words[-1].lower() in action_map:
            action = action_map[words[-1].lower()]
        elif 'accept' in line:
            action = 'allow'
        elif 'drop' in line or 'reject' in line:
            action = 'block'
        else:
            action = 'unknown'

        # Protocol
        p_m = re.search(r'\b(tcp|udp|icmp|icmpv6)\b', line)
        if p_m:
            proto = p_m.group(1)

        # Source / destination address
        saddr_m = re.search(r'saddr\s+(\S+)', line)
        if saddr_m:
            source = saddr_m.group(1).rstrip(',')
        daddr_m = re.search(r'daddr\s+(\S+)', line)
        if daddr_m:
            dest = daddr_m.group(1).rstrip(',')

        # Port
        dport_m = re.search(r'dport\s+\{?([^};\n]+)', line)
        if dport_m:
            port = dport_m.group(1).strip().rstrip('}')

        output['firewall_rules'].append({
            'chain':       current_chain,
            'direction':   direction,
            'action':      action,
            'protocol':    proto,
            'source':      source,
            'destination': dest,
            'port':        port,
            'enabled':     True,
            'description': line,
            'source_tool': 'nftables',
        })


# ---------------------------------------------------------------------------
# sysctl
# ---------------------------------------------------------------------------

def collect_sysctl(output):
    # sysctl -a dumps all kernel parameters including per-interface entries
    # under net.ipv4.conf.<iface>.*, net.ipv6.neigh.<iface>.*, etc.
    # Virtual/ephemeral interface names change every time containers or VMs
    # restart, producing constant false-positive drift.  We only keep sysctl
    # keys that are either non-interface-scoped or scoped to a physical/stable
    # interface (eth*, ens*, enp*, em*, bond*, team*, lo, wlan*).
    _VIRTUAL_IFACE_RE = re.compile(
        r'\.(veth[0-9a-f]+'    # Docker/K8s veth pairs
        r'|br-[0-9a-f]+'       # Docker bridge networks (br-<id>)
        r'|docker[0-9]+'       # docker0, docker1, …
        r'|virbr[0-9]+'        # libvirt bridges
        r'|cni[0-9]+'          # CNI plugin interfaces
        r'|flannel'            # Flannel overlay
        r'|cali[0-9a-f]+'      # Calico interfaces
        r'|tunl[0-9]+'         # IP-in-IP tunnels
        r'|vxlan'              # VXLAN overlays
        r')(\.|$)'
    )
    sysctl_out = priv('sysctl -a 2>/dev/null')
    for line in sysctl_out.splitlines():
        if '=' not in line:
            continue
        k, _, v = line.partition('=')
        k = k.strip()
        if _VIRTUAL_IFACE_RE.search(k):
            continue
        output['sysctl'].append({
            'key':   k,
            'value': v.strip(),
        })


# ---------------------------------------------------------------------------
# startup items — rc.local, cron @reboot, systemd service WantedBy
# ---------------------------------------------------------------------------

def collect_startup_items(output):
    # rc.local
    for rc_path in ['/etc/rc.local', '/etc/rc.d/rc.local']:
        if not os.path.isfile(rc_path):
            continue
        for line in read_lines(rc_path):
            if line.startswith('#') or not line.strip() or line.strip() == 'exit 0':
                continue
            output['startup_items'].append({
                'name':    rc_path,
                'type':    'rc.local',
                'command': line.strip(),
                'path':    rc_path,
                'enabled': True,
            })

    # Systemd enabled services (WantedBy=multi-user.target or graphical.target)
    if _detect_init() == 'systemd':
        enabled_out = run('systemctl list-unit-files --state=enabled --type=service --no-pager --no-legend 2>/dev/null')
        for line in enabled_out.splitlines():
            parts = line.split()
            if parts:
                output['startup_items'].append({
                    'name':    parts[0].replace('.service', ''),
                    'type':    'systemd',
                    'command': '',
                    'path':    '',
                    'enabled': True,
                })

    # @reboot cron entries (already captured in scheduled_tasks; add to startup_items too)
    for task in output.get('scheduled_tasks', []):
        if '@reboot' in task.get('command', ''):
            output['startup_items'].append({
                'name':    task.get('name', ''),
                'type':    'cron-reboot',
                'command': task.get('command', ''),
                'path':    '',
                'enabled': True,
            })


# ---------------------------------------------------------------------------
# certificates — PEM/DER files in system trust stores
# ---------------------------------------------------------------------------

def collect_certificates(output):
    cert_dirs = [
        '/etc/ssl/certs',
        '/etc/pki/tls/certs',
        '/etc/pki/ca-trust/source/anchors',
        '/usr/share/ca-certificates',
        '/usr/local/share/ca-certificates',
    ]

    if not which('openssl'):
        return

    seen = set()
    for cert_dir in cert_dirs:
        if not os.path.isdir(cert_dir):
            continue
        for fname in os.listdir(cert_dir):
            if not fname.endswith(('.crt', '.pem', '.cer')):
                continue
            fpath = os.path.join(cert_dir, fname)
            if not os.path.isfile(fpath):
                continue

            # Parse with openssl — works on very old versions (0.9.x+)
            x509_out = run(
                'openssl x509 -in {0} -noout '
                '-subject -issuer -fingerprint -serial -dates 2>/dev/null'.format(fpath)
            )
            if not x509_out:
                continue

            def _x509_field(field):
                m = re.search(r'{0}=(.+)'.format(field), x509_out, re.IGNORECASE)
                return m.group(1).strip() if m else ''

            subject     = _x509_field('subject')
            issuer      = _x509_field('issuer')
            fingerprint = _x509_field('SHA1 Fingerprint')
            serial      = _x509_field('serial')
            not_before  = _x509_field('notBefore')
            not_after   = _x509_field('notAfter')

            if fingerprint in seen:
                continue
            seen.add(fingerprint)

            output['certificates'].append({
                'subject':    subject,
                'issuer':     issuer,
                'thumbprint': fingerprint,
                'serial':     serial,
                'not_before': not_before,
                'not_after':  not_after,
                'store':      cert_dir,
            })


# ---------------------------------------------------------------------------
# logging targets
# ---------------------------------------------------------------------------

def collect_logging_targets(output):
    # rsyslog — look for @@host (TCP) and @host (UDP) remote targets
    rsyslog_files = []
    if os.path.isfile('/etc/rsyslog.conf'):
        rsyslog_files.append('/etc/rsyslog.conf')
    if os.path.isdir('/etc/rsyslog.d'):
        for f in os.listdir('/etc/rsyslog.d'):
            rsyslog_files.append(os.path.join('/etc/rsyslog.d', f))

    seen_targets = set()
    for path in rsyslog_files:
        for line in read_lines(path):
            line = line.strip()
            if line.startswith('#') or not line:
                continue
            # @@host:port or @host:port
            m = re.search(r'@@([^;\s]+)', line)
            if m:
                dest = m.group(1)
                if dest not in seen_targets:
                    seen_targets.add(dest)
                    output['logging_targets'].append({
                        'type':        'syslog',
                        'destination': dest,
                        'protocol':    'tcp',
                        'enabled':     True,
                    })
            m = re.search(r'(?<!@)@([^@;\s][^;\s]*)', line)
            if m:
                dest = m.group(1)
                if dest not in seen_targets:
                    seen_targets.add(dest)
                    output['logging_targets'].append({
                        'type':        'syslog',
                        'destination': dest,
                        'protocol':    'udp',
                        'enabled':     True,
                    })

    # syslog-ng
    sng_conf = '/etc/syslog-ng/syslog-ng.conf'
    if os.path.isfile(sng_conf):
        for line in read_lines(sng_conf):
            m = re.search(r'ip\("([^"]+)"\)', line)
            if m:
                dest = m.group(1)
                proto = 'tcp' if 'tcp' in line.lower() else 'udp'
                if dest not in seen_targets:
                    seen_targets.add(dest)
                    output['logging_targets'].append({
                        'type':        'syslog',
                        'destination': dest,
                        'protocol':    proto,
                        'enabled':     True,
                    })

    # systemd-journal-remote
    jr_conf = '/etc/systemd/journal-remote.conf'
    if os.path.isfile(jr_conf):
        for line in read_lines(jr_conf):
            if line.startswith('URL=') or line.startswith('RemoteServAddr='):
                dest = line.split('=', 1)[-1].strip().strip('"')
                if dest and dest not in seen_targets:
                    seen_targets.add(dest)
                    output['logging_targets'].append({
                        'type':        'journal-remote',
                        'destination': dest,
                        'protocol':    'tcp',
                        'enabled':     True,
                    })


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

COLLECTORS = [
    ('device',             collect_device),
    ('hardware',           collect_hardware),
    ('os',                 collect_os),
    ('network',            collect_network),
    ('users',              collect_users),
    ('groups',             collect_groups),
    ('packages',           collect_packages),
    ('services',           collect_services),
    ('filesystem',         collect_filesystem),
    ('security',           collect_security),
    ('scheduled_tasks',    collect_scheduled_tasks),
    ('ssh_keys',           collect_ssh_keys),
    ('ssh_config',         collect_ssh_config),
    ('kernel_modules',     collect_kernel_modules),
    ('pci_devices',        collect_pci_devices),
    ('storage_devices',    collect_storage_devices),
    ('usb_devices',        collect_usb_devices),
    ('listening_services', collect_listening_services),
    ('firewall_rules',     collect_firewall_rules),
    ('sysctl',             collect_sysctl),
    ('startup_items',      collect_startup_items),
    ('certificates',       collect_certificates),
    ('logging_targets',    collect_logging_targets),
]


def collect():
    """Run all collectors and return the canonical dict."""
    output = empty_canonical()
    errors = {}

    for name, fn in COLLECTORS:
        try:
            fn(output)
        except Exception as e:
            errors[name] = str(e)

    if errors:
        output.setdefault('custom', {})['_collection_errors'] = errors

    return output


def _make_handler(token):
    """Return an HTTPRequestHandler class bound to the given shared secret."""
    class AgentHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            # Require token when one is configured
            if token:
                provided = self.headers.get('X-Agent-Token', '')
                if provided != token:
                    self.send_response(401)
                    self.send_header('Content-Type', 'text/plain')
                    self.end_headers()
                    self.wfile.write(b'Unauthorized')
                    return

            if self.path != '/collect':
                self.send_response(404)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'Not Found')
                return

            data = json.dumps(collect(), indent=2).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, fmt, *args):
            pass  # suppress per-request noise to stderr

    return AgentHandler


def main():
    # ---- argument parsing (argparse on 2.7+/3.x; manual fallback for 2.6) ----
    if HAS_ARGPARSE:
        parser = argparse.ArgumentParser(description='IsotopeIQ Linux Agent')
        parser.add_argument('--serve', action='store_true',
            help='Run as a persistent HTTP server instead of printing to stdout')
        parser.add_argument('--port', type=int, default=DEFAULT_AGENT_PORT,
            help='TCP port to listen on in serve mode (default: %(default)s)')
        parser.add_argument('--token', default='',
            help='Shared secret for X-Agent-Token')
        args = parser.parse_args()
    else:
        # Python 2.6 minimal fallback
        class args(object):
            serve = '--serve' in sys.argv
            port = DEFAULT_AGENT_PORT
            token = ''
        for i, a in enumerate(sys.argv[1:], 1):
            if a == '--port'  and i + 1 < len(sys.argv): args.port  = int(sys.argv[i + 1])
            if a == '--token' and i + 1 < len(sys.argv): args.token = sys.argv[i + 1]

    if args.serve:
        token = args.token or _read_config().get('token', '')
        server = HTTPServer(('0.0.0.0', args.port), _make_handler(token))
        sys.stderr.write('IsotopeIQ agent listening on 0.0.0.0:{0}\n'.format(args.port))
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    else:
        print(json.dumps(collect(), indent=2))


if __name__ == '__main__':
    main()
