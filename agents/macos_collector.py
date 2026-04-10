"""
IsotopeIQ macOS Agent
Collects system baseline data and outputs the canonical object as JSON to stdout.

Requires Python 3.6+ (available on macOS 10.14 Mojave through macOS 15 Sequoia).
No third-party dependencies — stdlib only.

Compile with PyInstaller (produces a single self-contained binary):
    pyinstaller --onefile macos_collector.py

The resulting binary can be copied to any compatible macOS host and run
as any user.  Privileged data (FileVault, SIP, keychain certs, etc.) is
collected automatically when running as root; non-root runs attempt
passwordless sudo and silently skip commands that require elevation.
"""

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
    from socketserver import ThreadingMixIn  # Python 3
except ImportError:
    from SocketServer import ThreadingMixIn  # Python 2


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle each HTTP request in its own daemon thread."""
    daemon_threads = True

try:
    import argparse
    HAS_ARGPARSE = True
except ImportError:
    HAS_ARGPARSE = False

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


def priv(cmd):
    """Run cmd with privilege; tries passwordless sudo if not root."""
    if is_root():
        return run(cmd)
    return run('sudo -n {0} 2>/dev/null'.format(cmd))


# ---------------------------------------------------------------------------
# system_profiler helper
# ---------------------------------------------------------------------------

def _sp_kv(data_type):
    """
    Run `system_profiler <data_type>` and return a flat dict of
    key->value pairs from indented "  Key: Value" lines.
    """
    out = run('system_profiler {0} 2>/dev/null'.format(data_type))
    kv = {}
    for line in out.splitlines():
        if ':' in line:
            k, _, v = line.partition(':')
            key = k.strip()
            val = v.strip()
            if key and val:
                kv.setdefault(key, val)   # first occurrence wins
    return kv


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
    hostname = run('scutil --get ComputerName 2>/dev/null').strip() or run('hostname').strip()
    try:
        fqdn = socket.getfqdn()
    except Exception:
        fqdn = hostname

    hw = _sp_kv('SPHardwareDataType')
    model  = hw.get('Model Name') or hw.get('Model Identifier') or ''
    serial = hw.get('Serial Number (system)') or ''

    output['device']['hostname']    = hostname
    output['device']['fqdn']        = fqdn
    output['device']['device_type'] = 'server'
    output['device']['vendor']      = 'Apple'
    output['device']['model']       = model.strip()
    # Stash serial for hardware section too
    output['_serial'] = serial.strip()


# ---------------------------------------------------------------------------
# hardware
# ---------------------------------------------------------------------------

def collect_hardware(output):
    hw = _sp_kv('SPHardwareDataType')

    cpu_model = (hw.get('Chip') or hw.get('Processor Name') or '').strip()

    core_raw = (
        hw.get('Total Number of Cores') or
        hw.get('Number of Cores') or
        hw.get('Number of CPUs') or
        ''
    ).strip()
    cpu_cores = None
    m = re.search(r'\d+', core_raw)
    if m:
        try:
            cpu_cores = int(m.group(0))
        except ValueError:
            pass

    mem_raw = hw.get('Memory', '').strip()           # e.g. "16 GB"
    mem_gb = None
    m = re.match(r'([\d.]+)', mem_raw)
    if m:
        try:
            mem_gb = float(m.group(1))
        except ValueError:
            pass

    bios_ver = (hw.get('Boot ROM Version') or hw.get('SMC Version (system)') or '').strip()
    serial   = output.pop('_serial', '') or hw.get('Serial Number (system)', '').strip()
    arch     = run('uname -m').strip()

    # Virtualization detection — model name heuristics
    model_str = (hw.get('Model Name') or hw.get('Model Identifier') or '').lower()
    if 'vmware' in model_str:
        virt = 'vmware'
    elif 'virtualbox' in model_str:
        virt = 'virtualbox'
    elif 'parallels' in model_str:
        virt = 'other'
    else:
        virt = 'bare-metal'

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
    name    = run('sw_vers -productName 2>/dev/null').strip()  or 'macOS'
    version = run('sw_vers -productVersion 2>/dev/null').strip()
    build   = run('sw_vers -buildVersion 2>/dev/null').strip()
    kernel  = run('uname -r').strip()

    tz = ''
    tz_out = run('systemsetup -gettimezone 2>/dev/null').strip()
    m = re.search(r'Time Zone:\s*(.+)', tz_out)
    if m:
        tz = m.group(1).strip()
    if not tz:
        link = run('readlink /etc/localtime 2>/dev/null').strip()
        m = re.search(r'zoneinfo/(.+)', link)
        if m:
            tz = m.group(1)

    ntp_servers = []
    ntp_out = run('systemsetup -getnetworktimeserver 2>/dev/null').strip()
    m = re.search(r'Network Time Server:\s*(.+)', ntp_out)
    if m:
        server = m.group(1).strip()
        if server:
            ntp_servers = [server]

    ntp_synced = None
    nt_out = run('systemsetup -getusingnetworktime 2>/dev/null').strip().lower()
    if 'network time: on' in nt_out or nt_out.endswith('on'):
        ntp_synced = True
    elif 'off' in nt_out:
        ntp_synced = False

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


def collect_network(output):
    iface_map = {}

    for line in run('ifconfig -a 2>/dev/null').splitlines():
        # New interface block: "en0: flags=8863<UP,RUNNING,...> mtu 1500"
        m = re.match(r'^(\S+):\s+flags=\S+\s+mtu\s+(\d+)', line)
        if m:
            name, mtu = m.group(1), int(m.group(2))
            iface_map[name] = _empty_iface(name)
            iface_map[name]['mtu'] = mtu
            flags_m = re.search(r'<([^>]*)>', line)
            if flags_m:
                fl = flags_m.group(1).split(',')
                iface_map[name]['admin_status'] = 'up'   if 'UP'      in fl else 'down'
                iface_map[name]['oper_status']  = 'up'   if 'RUNNING' in fl else 'down'
            continue

        if not iface_map:
            continue
        current = list(iface_map.keys())[-1]

        m = re.match(r'^\s+ether\s+([0-9a-f:]+)', line)
        if m:
            iface_map[current]['mac'] = m.group(1)
            continue

        m = re.match(r'^\s+inet\s+(\d+\.\d+\.\d+\.\d+)\s+netmask\s+(\S+)', line)
        if m:
            ip = m.group(1)
            if not ip.startswith('127.'):
                try:
                    prefix = bin(int(m.group(2), 16)).count('1')
                except ValueError:
                    prefix = 32
                iface_map[current]['ipv4'].append('{0}/{1}'.format(ip, prefix))
            continue

        m = re.match(r'^\s+inet6\s+(\S+)\s+prefixlen\s+(\d+)', line)
        if m:
            addr = m.group(1).split('%')[0]
            if not addr.startswith('::1'):
                iface_map[current]['ipv6'].append('{0}/{1}'.format(addr, m.group(2)))

    output['network']['interfaces'] = list(iface_map.values())

    # DNS — scutil --dns or /etc/resolv.conf
    dns = []
    scutil_out = run('scutil --dns 2>/dev/null')
    for line in scutil_out.splitlines():
        m = re.match(r'\s+nameserver\[\d+\]\s*:\s*(\S+)', line)
        if m and m.group(1) not in dns:
            dns.append(m.group(1))
    if not dns:
        for line in read_lines('/etc/resolv.conf'):
            if line.startswith('nameserver'):
                parts = line.split()
                if len(parts) >= 2:
                    dns.append(parts[1])
    output['network']['dns_servers'] = dns

    # Default gateway
    gw = ''
    gw_out = run('netstat -rn 2>/dev/null')
    for line in gw_out.splitlines():
        parts = line.split()
        if parts and parts[0] in ('default', '0.0.0.0'):
            if len(parts) >= 2:
                gw = parts[1]
                break
    output['network']['default_gateway'] = gw

    # Routes from netstat -rn
    routes = []
    in_table = False
    for line in gw_out.splitlines():
        if re.match(r'^Destination\s+Gateway', line):
            in_table = True
            continue
        if not in_table or not line.strip() or re.match(r'^Internet', line):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        dest = parts[0]
        gw_r = parts[1]
        iface = ''
        for p in reversed(parts[2:]):
            if re.match(r'^[a-z][a-z0-9]+\d*$', p) and not p.isdigit():
                iface = p
                break
        routes.append({'destination': dest, 'gateway': gw_r, 'interface': iface, 'metric': None})
    output['network']['routes'] = routes

    # Hosts file
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
    # Users with UID >= 500 excluding service accounts (_*)
    uid_out = run('dscl . -list /Users UniqueID 2>/dev/null')
    for line in uid_out.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        uname, uid_s = parts[0], parts[1]
        if uname.startswith('_'):
            continue
        try:
            uid_i = int(uid_s)
        except ValueError:
            continue
        if uid_i < 500:
            continue

        home  = run('dscl . -read /Users/{0} NFSHomeDirectory 2>/dev/null'.format(uname))
        home  = home.split(':', 1)[-1].strip() if ':' in home else ''
        shell = run('dscl . -read /Users/{0} UserShell 2>/dev/null'.format(uname))
        shell = shell.split(':', 1)[-1].strip() if ':' in shell else ''

        pw_raw = run('dscl . -read /Users/{0} passwordLastSetTime 2>/dev/null'.format(uname))
        pwd_last = pw_raw.split(':', 1)[-1].strip() if ':' in pw_raw else ''

        last_login = ''
        last_out = run('last -1 {0} 2>/dev/null'.format(uname))
        for ln in last_out.splitlines():
            if uname in ln and 'still' not in ln.lower() and 'wtmp' not in ln.lower():
                last_login = ln.strip()
                break

        is_admin = run(
            'dseditgroup -o checkmember -m {0} admin 2>/dev/null'.format(uname)
        )
        sudo_priv = 'ALL' if 'yes' in is_admin.lower() else ''

        output['users'].append({
            'username':          uname,
            'uid':               uid_s,
            'groups':            [],
            'home':              home,
            'shell':             shell,
            'disabled':          None,
            'password_last_set': pwd_last,
            'last_login':        last_login,
            'sudo_privileges':   sudo_priv,
        })


# ---------------------------------------------------------------------------
# groups
# ---------------------------------------------------------------------------

def collect_groups(output):
    gid_out = run('dscl . -list /Groups PrimaryGroupID 2>/dev/null')
    for line in gid_out.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        gname, gid = parts[0], parts[1]
        members_raw = run('dscl . -read /Groups/{0} GroupMembership 2>/dev/null'.format(gname))
        members = []
        if ':' in members_raw:
            members = [m.strip() for m in members_raw.split(':', 1)[1].split() if m.strip()]
        output['groups'].append({
            'group_name': gname,
            'gid':        gid,
            'members':    members,
        })


# ---------------------------------------------------------------------------
# packages
# ---------------------------------------------------------------------------

def collect_packages(output):
    # system_profiler SPApplicationsDataType — installed .app bundles
    sp_out = run('system_profiler SPApplicationsDataType 2>/dev/null')
    current_app = None
    ver = ''
    vendor = ''
    for line in sp_out.splitlines():
        # App name lines are indented 6 spaces and end with ':'
        m = re.match(r'^      ([^:]+):$', line)
        if m:
            if current_app:
                output['packages'].append({
                    'name':         current_app,
                    'version':      ver,
                    'vendor':       vendor,
                    'install_date': '',
                    'source':       'macos-app',
                })
            current_app = m.group(1).strip()
            ver = ''
            vendor = ''
            continue
        if current_app:
            vm = re.match(r'^\s+Version:\s+(.+)', line)
            if vm:
                ver = vm.group(1).strip()
            gm = re.match(r'^\s+(?:Get Info String|Obtained from):\s+(.+)', line)
            if gm and not vendor:
                vendor = gm.group(1).strip()
    if current_app:
        output['packages'].append({
            'name':         current_app,
            'version':      ver,
            'vendor':       vendor,
            'install_date': '',
            'source':       'macos-app',
        })

    # pkgutil receipts — CLI tools and .pkg installers
    for pkg_id in run_lines('pkgutil --pkgs 2>/dev/null'):
        info = run('pkgutil --pkg-info {0} 2>/dev/null'.format(pkg_id))
        ver_m = re.search(r'^version:\s*(.+)', info, re.MULTILINE)
        ts_m  = re.search(r'^install-time:\s*(\d+)', info, re.MULTILINE)
        pkg_ver = ver_m.group(1).strip() if ver_m else ''
        install_date = ''
        if ts_m:
            install_date = run('date -r {0} "+%Y-%m-%d" 2>/dev/null'.format(ts_m.group(1))).strip()
        output['packages'].append({
            'name':         pkg_id,
            'version':      pkg_ver,
            'vendor':       '',
            'install_date': install_date,
            'source':       'pkgutil',
        })

    # Homebrew
    if which('brew'):
        for line in run_lines('brew list --versions 2>/dev/null'):
            parts = line.split(None, 1)
            output['packages'].append({
                'name':         parts[0],
                'version':      parts[1].split()[-1] if len(parts) > 1 else '',
                'vendor':       '',
                'install_date': '',
                'source':       'brew',
            })

    # MacPorts
    if which('port'):
        for line in run_lines('port installed 2>/dev/null'):
            m = re.match(r'^\s+(\S+)\s+@([^\s+]+)', line)
            if m:
                output['packages'].append({
                    'name':         m.group(1),
                    'version':      m.group(2),
                    'vendor':       '',
                    'install_date': '',
                    'source':       'macports',
                })


# ---------------------------------------------------------------------------
# services
# ---------------------------------------------------------------------------

def collect_services(output):
    # launchctl list: PID  LastExitStatus  Label
    for line in run_lines('launchctl list 2>/dev/null'):
        parts = line.split('\t')
        if len(parts) < 3 or parts[0] == 'PID':
            continue
        pid_s  = parts[0].strip()
        label  = parts[2].strip()
        status = 'running' if pid_s != '-' and pid_s.isdigit() else 'stopped'

        # Startup state — check if plist has Disabled=true
        startup = 'enabled'
        for d in ('/Library/LaunchDaemons', '/Library/LaunchAgents',
                  '/System/Library/LaunchDaemons', '/System/Library/LaunchAgents'):
            plist = os.path.join(d, '{0}.plist'.format(label))
            if os.path.isfile(plist):
                disabled = run('defaults read {0} Disabled 2>/dev/null'.format(plist)).strip()
                if disabled == '1':
                    startup = 'disabled'
                break

        output['services'].append({
            'name':    label,
            'status':  status,
            'startup': startup,
        })


# ---------------------------------------------------------------------------
# filesystem
# ---------------------------------------------------------------------------

def collect_filesystem(output):
    # SUID / SGID files (root only)
    suid_map = {}
    if is_root():
        suid_out = run('find / -xdev \\( -perm -4000 -o -perm -2000 \\) -type f 2>/dev/null | sort')
        for path in suid_out.splitlines():
            path = path.strip()
            if not path:
                continue
            # Best-match mount point
            best = '/'
            for mp in suid_map:
                if path.startswith(mp) and len(mp) > len(best):
                    best = mp
            suid_map.setdefault(best, []).append(path)

    for line in run('df -P -k 2>/dev/null').splitlines():
        parts = line.split()
        if not parts or parts[0] == 'Filesystem':
            continue
        if len(parts) < 6:
            continue
        device, blocks, used, avail, _pct, mount = parts[:6]

        # Skip pseudo/virtual FSes
        if device.startswith('devfs') or device in ('none', 'map'):
            continue
        if mount.startswith('/dev') and not device.startswith('/dev'):
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
            'mount':       mount,
            'device':      device,
            'fstype':      '',
            'size_gb':     size_gb,
            'free_gb':     free_gb,
            'options':     [],
            'suid_files':  suid_map.get(mount, []),
        })


# ---------------------------------------------------------------------------
# security
# ---------------------------------------------------------------------------

def collect_security(output):
    # SIP (System Integrity Protection) — maps to selinux_mode
    sip_out = priv('csrutil status 2>/dev/null').lower()
    if 'enabled' in sip_out:
        output['security']['selinux_mode'] = 'enforcing'
    elif 'disabled' in sip_out:
        output['security']['selinux_mode'] = 'disabled'
    else:
        output['security']['selinux_mode'] = 'unknown'

    # FileVault — maps to secure_boot
    fv_out = priv('fdesetup status 2>/dev/null').lower()
    if 'filevault is on' in fv_out:
        output['security']['secure_boot'] = True
    elif 'filevault is off' in fv_out:
        output['security']['secure_boot'] = False

    # Gatekeeper — maps to apparmor_status
    gk_out = run('spctl --status 2>/dev/null').lower()
    output['security']['apparmor_status'] = 'enabled' if 'assessments enabled' in gk_out else 'disabled'

    # Application firewall global state
    fw_out = priv('/usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate 2>/dev/null').lower()
    output['security']['firewall_enabled'] = 'enabled' in fw_out or 'on' in fw_out

    # Audit logging (ASL/Unified Log always present on macOS)
    output['security']['audit_logging_enabled'] = True


# ---------------------------------------------------------------------------
# scheduled tasks (launchd plists)
# ---------------------------------------------------------------------------

def collect_scheduled_tasks(output):
    dirs = [
        '/Library/LaunchDaemons',
        '/Library/LaunchAgents',
        '/System/Library/LaunchDaemons',
        '/System/Library/LaunchAgents',
        os.path.expanduser('~/Library/LaunchAgents'),
    ]
    for d in dirs:
        if not os.path.isdir(d):
            continue
        for fname in sorted(os.listdir(d)):
            if not fname.endswith('.plist'):
                continue
            plist_path = os.path.join(d, fname)
            label   = run('defaults read {0} Label 2>/dev/null'.format(plist_path)).strip()
            if not label:
                label = fname[:-6]
            program = run('defaults read {0} Program 2>/dev/null'.format(plist_path)).strip()
            if not program:
                program = run('defaults read {0} ProgramArguments 2>/dev/null'.format(plist_path)).strip()
            disabled = run('defaults read {0} Disabled 2>/dev/null'.format(plist_path)).strip()
            output['scheduled_tasks'].append({
                'name':    label,
                'command': program,
                'enabled': disabled != '1',
            })


# ---------------------------------------------------------------------------
# ssh keys
# ---------------------------------------------------------------------------

def collect_ssh_keys(output):
    uid_out = run('dscl . -list /Users UniqueID 2>/dev/null')
    for line in uid_out.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        uname = parts[0]
        if uname.startswith('_'):
            continue
        try:
            if int(parts[1]) < 500:
                continue
        except ValueError:
            continue

        home_raw = run('dscl . -read /Users/{0} NFSHomeDirectory 2>/dev/null'.format(uname))
        home = home_raw.split(':', 1)[-1].strip() if ':' in home_raw else ''
        if not home:
            continue

        auth_keys = os.path.join(home, '.ssh', 'authorized_keys')
        for line in read_lines(auth_keys):
            if line.startswith('#'):
                continue
            parts2 = line.split()
            key_type    = parts2[0] if parts2 else ''
            key_value   = parts2[1] if len(parts2) > 1 else ''
            key_comment = parts2[2] if len(parts2) > 2 else ''
            output['ssh_keys'].append({
                'username':    uname,
                'key_type':    key_type,
                'key_value':   key_value,
                'comment':     key_comment,
                'source_file': auth_keys,
            })


# ---------------------------------------------------------------------------
# ssh config
# ---------------------------------------------------------------------------

def collect_ssh_config(output):
    config = {}
    for line in read_lines('/etc/ssh/sshd_config'):
        if line.strip().startswith('#') or '=' not in line and ' ' not in line:
            continue
        if line.startswith('#'):
            continue
        # Directives are "Keyword value" (space-separated, not '=')
        parts = line.split(None, 1)
        if len(parts) == 2:
            config[parts[0]] = parts[1].strip()
    if config:
        output['ssh_config'] = config


# ---------------------------------------------------------------------------
# kernel modules (kext)
# ---------------------------------------------------------------------------

def collect_kernel_modules(output):
    out = run('kextstat 2>/dev/null') or run('kmutil showloaded 2>/dev/null')
    for line in out.splitlines():
        parts = line.split()
        if not parts or parts[0] == 'Index':
            continue
        # kextstat format: Index Refs Address  Size   Wired   Name (Version)
        if len(parts) < 6:
            continue
        name = parts[5] if len(parts) > 5 else parts[-1]
        name = re.sub(r'\(.*\)$', '', name).strip()
        if not name:
            continue
        ver_m = re.search(r'\(([^)]+)\)', line)
        ver = ver_m.group(1) if ver_m else ''
        output['kernel_modules'].append({
            'name':    name,
            'version': ver,
            'type':    'kext',
        })


# ---------------------------------------------------------------------------
# PCI devices
# ---------------------------------------------------------------------------

def collect_pci_devices(output):
    """Collect PCI devices via system_profiler SPPCIDataType."""
    out = run('system_profiler SPPCIDataType 2>/dev/null')
    if not out:
        return

    current = {}
    for line in out.splitlines():
        # Section header (device name) — indented 6 spaces, ends with ':'
        m = re.match(r'^      ([^:]+):$', line)
        if m:
            if current.get('slot'):
                output['pci_devices'].append(current)
            current = {}
            continue

        if not current and '      ' in line:
            current = {}

        if ':' not in line:
            continue
        k, _, v = line.partition(':')
        key = k.strip()
        val = v.strip()

        key_map = {
            'Slot':                   'slot',
            'Type':                   'class',
            'Vendor ID':               'vendor',
            'Device ID':               'device',
            'Subsystem Vendor ID':    'subsystem_vendor',
            'Subsystem ID':            'subsystem_device',
        }
        canon = key_map.get(key)
        if canon:
            current[canon] = val

        # Device name doubles as the slot address on macOS if Slot not present
        if key == 'Slot' and 'slot' not in current:
            current['slot'] = val

    if current.get('slot'):
        output['pci_devices'].append(current)

    # If system_profiler returned records without a Slot field, use the block
    # title as fallback — re-run with a simpler block parser
    if not output['pci_devices']:
        _parse_sp_pci_simple(out, output)


def _parse_sp_pci_simple(out, output):
    """Fallback: treat each top-level block title as the device name/slot."""
    current = {}
    title = None
    for line in out.splitlines():
        m = re.match(r'^      ([^:]+):$', line)
        if m:
            if title:
                entry = dict(current)
                entry.setdefault('slot', title)
                output['pci_devices'].append(entry)
            title   = m.group(1).strip()
            current = {}
            continue
        if title and ':' in line:
            k, _, v = line.partition(':')
            current[k.strip()] = v.strip()

    if title:
        entry = dict(current)
        entry.setdefault('slot', title)
        output['pci_devices'].append(entry)


# ---------------------------------------------------------------------------
# storage devices
# ---------------------------------------------------------------------------

def collect_storage_devices(output):
    """Collect physical drives via diskutil list + diskutil info."""
    # diskutil list -plist would be cleaner but requires plistlib;
    # plain text is more portable.
    disk_out = run('diskutil list 2>/dev/null')
    # Find whole-disk entries: lines like "/dev/disk0 (internal, physical):"
    for line in disk_out.splitlines():
        m = re.match(r'^(/dev/disk\d+)\s+\(([^)]+)\)', line)
        if not m:
            continue
        dev_path = m.group(1)
        tags     = m.group(2).lower()

        info_out = run('diskutil info {0} 2>/dev/null'.format(dev_path))
        info = {}
        for il in info_out.splitlines():
            if ':' in il:
                k, _, v = il.partition(':')
                info[k.strip()] = v.strip()

        dev_type   = 'disk'
        removable  = 'external' in tags or 'removable' in tags
        interface  = info.get('Protocol', '').lower()
        model      = info.get('Device / Media Name') or info.get('Media Name', '')
        size_str   = info.get('Disk Size', '')
        serial     = info.get('Serial / Platform Serial No.') or info.get('Disk Serial Number', '')

        # Simplify size: "500.1 GB (..." → "500.1G"
        size = ''
        sm = re.match(r'([\d.]+)\s+([KMGT]B)', size_str)
        if sm:
            unit = sm.group(2).replace('B', '').replace('K', 'K')
            size = '{0}{1}'.format(sm.group(1), unit[0])

        # Detect optical drives
        if 'optical' in info.get('Media Type', '').lower() or 'dvd' in model.lower() or 'cd' in model.lower():
            dev_type = 'optical'

        entry = {'name': dev_path.replace('/dev/', '')}
        if dev_type:    entry['type']      = dev_type
        if model:       entry['model']     = model.strip()
        if size:        entry['size']      = size
        if serial:      entry['serial']    = serial.strip()
        if interface:   entry['interface'] = interface
        entry['removable'] = removable

        output['storage_devices'].append(entry)


# ---------------------------------------------------------------------------
# USB devices
# ---------------------------------------------------------------------------

def collect_usb_devices(output):
    """Collect USB devices via system_profiler SPUSBDataType."""
    out = run('system_profiler SPUSBDataType 2>/dev/null')
    if not out:
        return

    current = {}
    for line in out.splitlines():
        # Device name — indented 6 spaces, ends with ':'
        m = re.match(r'^      ([^:]+):$', line)
        if m:
            if current.get('bus_id') or (current.get('vendor_id') and current.get('product_id')):
                output['usb_devices'].append(current)
            current = {'product': m.group(1).strip()}
            continue

        if ':' not in line:
            continue
        k, _, v = line.partition(':')
        key = k.strip()
        val = v.strip()

        if key == 'Product ID':
            current['product_id'] = val.lstrip('0x').lower()
        elif key == 'Vendor ID':
            vid = val.split()[0].lstrip('0x').lower()
            current['vendor_id'] = vid
        elif key == 'Manufacturer':
            current['manufacturer'] = val
        elif key in ('Location ID',):
            # "0x14200000 / 4" — use the numeric part as bus_id
            m2 = re.search(r'/\s*(\d+)', val)
            if m2:
                current['bus_id'] = m2.group(1)

    if current.get('bus_id') or (current.get('vendor_id') and current.get('product_id')):
        output['usb_devices'].append(current)

    # Ensure bus_id is present; fall back to vendor_id/product_id combo
    for dev in output['usb_devices']:
        if 'bus_id' not in dev:
            dev['bus_id'] = '{0}:{1}'.format(
                dev.get('vendor_id', ''), dev.get('product_id', '')
            )


# ---------------------------------------------------------------------------
# listening services
# ---------------------------------------------------------------------------

def collect_listening_services(output):
    # lsof -nP -iTCP -sTCP:LISTEN  +  -iUDP
    out = run('lsof -nP -iTCP -iUDP -sTCP:LISTEN 2>/dev/null')
    if not out:
        # Fallback: netstat -an
        out = run('netstat -an 2>/dev/null')
        for line in out.splitlines():
            parts = line.split()
            if len(parts) < 4:
                continue
            proto_raw = parts[0].lower()
            if proto_raw not in ('tcp', 'tcp6', 'udp', 'udp6'):
                continue
            local = parts[3]
            state = parts[-1].upper() if len(parts) > 5 else 'LISTEN'
            if proto_raw.startswith('tcp') and state != 'LISTEN':
                continue
            addr_m = re.match(r'^(.*)[.:](\d+)$', local)
            if not addr_m:
                continue
            output['listening_services'].append({
                'protocol':      proto_raw,
                'local_address': addr_m.group(1).strip('*').replace('*', '0.0.0.0'),
                'port':          int(addr_m.group(2)),
                'process_name':  '',
                'pid':           None,
                'user':          '',
            })
        return

    proto_map = {'tcp': 'tcp', 'tcp6': 'tcp6', 'udp': 'udp', 'udp6': 'udp6'}
    for line in out.splitlines():
        parts = line.split()
        if not parts or parts[0] == 'COMMAND':
            continue
        if len(parts) < 9:
            continue
        proc  = parts[0]
        pid_s = parts[1]
        user  = parts[2]
        proto_raw = parts[7].lower()
        name_col  = parts[8]   # e.g. "*:80" or "127.0.0.1:443"
        proto = proto_map.get(proto_raw, 'unknown')

        # Parse address:port
        if name_col.startswith('['):
            # IPv6: [::1]:80
            am = re.match(r'\[([^\]]+)\]:(\d+)', name_col)
            if not am:
                continue
            addr, port_s = am.group(1), am.group(2)
        else:
            addr, _, port_s = name_col.rpartition(':')

        if not port_s.isdigit():
            continue
        port = int(port_s)
        if addr in ('*', ''):
            addr = '0.0.0.0'

        try:
            pid = int(pid_s)
        except ValueError:
            pid = None

        output['listening_services'].append({
            'protocol':      proto,
            'local_address': addr,
            'port':          port,
            'process_name':  proc,
            'pid':           pid,
            'user':          user,
        })


# ---------------------------------------------------------------------------
# firewall rules
# ---------------------------------------------------------------------------

def collect_firewall_rules(output):
    # macOS Application Firewall — list allowed/blocked apps
    fw_out = priv('/usr/libexec/ApplicationFirewall/socketfilterfw --listapps 2>/dev/null')
    for line in fw_out.splitlines():
        line = line.strip()
        if not line or line.startswith('ALF'):
            continue
        # Lines look like: "/path/to/App.app 2"  (2=allow, 3=block)
        parts = line.rsplit(None, 1)
        if len(parts) == 2:
            path, state_s = parts
            output['firewall_rules'].append({
                'chain':      'application',
                'action':     'allow' if state_s == '2' else 'deny',
                'protocol':   'any',
                'src':        '',
                'dst':        '',
                'port':       None,
                'comment':    path.strip(),
            })


# ---------------------------------------------------------------------------
# sysctl
# ---------------------------------------------------------------------------

def collect_sysctl(output):
    # Exclude volatile per-interface counters and high-churn keys
    EXCLUDE_RE = re.compile(
        r'\.(utun|vmnet|llw|anpi|ipsec|gif|stf)\d+[.\s]|'
        r'^(kern\.boottime|kern\.clockrate|net\.inet\.ip\.(id|stats)\.|'
        r'net\.inet6\.ip6\.stats\.|kern\.ipc\.so(recv|send)stats)',
        re.IGNORECASE,
    )
    for line in run('sysctl -a 2>/dev/null').splitlines():
        m = re.match(r'^(\S+)\s*[=:]\s*(.*)', line)
        if not m:
            continue
        key = m.group(1)
        val = m.group(2).strip()
        if EXCLUDE_RE.search(key):
            continue
        output['sysctl'].append({'key': key, 'value': val})


# ---------------------------------------------------------------------------
# certificates
# ---------------------------------------------------------------------------

def collect_certificates(output):
    # Dump PEM certs from System keychain, parse with openssl
    pem_out = priv(
        'security find-certificate -a -p /Library/Keychains/System.keychain 2>/dev/null'
    )
    if not pem_out:
        return

    pem_blocks = re.findall(
        r'(-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----)',
        pem_out, re.DOTALL,
    )
    for pem in pem_blocks:
        info = run(
            'echo "{0}" | openssl x509 -noout -subject -issuer -serial '
            '-dates 2>/dev/null'.format(pem.replace('\n', '\\n'))
        )
        entry = {
            'subject':    '',
            'issuer':     '',
            'thumbprint': '',
            'serial':     '',
            'not_before': '',
            'not_after':  '',
            'store':      'System',
        }
        for cert_line in info.splitlines():
            if cert_line.startswith('subject'):
                entry['subject'] = cert_line.split('=', 1)[-1].strip()
            elif cert_line.startswith('issuer'):
                entry['issuer'] = cert_line.split('=', 1)[-1].strip()
            elif cert_line.startswith('serial'):
                entry['serial'] = cert_line.split('=', 1)[-1].strip()
            elif cert_line.startswith('notBefore'):
                entry['not_before'] = cert_line.split('=', 1)[-1].strip()
            elif cert_line.startswith('notAfter'):
                entry['not_after'] = cert_line.split('=', 1)[-1].strip()
        if entry['subject']:
            output['certificates'].append(entry)


# ---------------------------------------------------------------------------
# logging targets
# ---------------------------------------------------------------------------

def collect_logging_targets(output):
    seen = set()

    for conf_path in ('/etc/asl.conf', '/etc/syslog.conf'):
        if not os.path.isfile(conf_path):
            continue
        for line in read_lines(conf_path):
            if line.startswith('#'):
                continue
            # Syslog: *.* @host:port  or  > host
            m = re.search(r'@([^\s:]+):?(\d+)?', line)
            if m:
                host = m.group(1)
                port = m.group(2) or '514'
                dest = '{0}:{1}'.format(host, port)
                if dest not in seen:
                    seen.add(dest)
                    output['logging_targets'].append({
                        'type':        'syslog',
                        'destination': dest,
                        'protocol':    'udp',
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
        output['custom']['_collection_errors'] = errors

    return output


def _run_script(script_content, language):
    """
    Write script_content to a temp file and execute it.

    language — 'shell' (default) or 'python'.

    Returns a dict: {exit_code, stdout, stderr}.
    """
    import tempfile
    ext = '.py' if language == 'python' else '.sh'
    fd, path = tempfile.mkstemp(suffix=ext, prefix='isotopeiq_')
    try:
        os.write(fd, script_content.encode('utf-8'))
        os.close(fd)
        os.chmod(path, 0o700)
        cmd = [sys.executable, path] if language == 'python' else ['/bin/bash', path]
        with open(os.devnull, 'rb') as devnull:
            proc = subprocess.Popen(cmd, stdin=devnull, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate()
        return {
            'exit_code': proc.returncode,
            'stdout': stdout.decode('utf-8', errors='replace'),
            'stderr': stderr.decode('utf-8', errors='replace'),
        }
    except Exception as exc:
        return {'exit_code': -1, 'stdout': '', 'stderr': str(exc)}
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def _make_handler(satellite_ip=None):
    """Return an HTTPRequestHandler class for the agent.

    satellite_ip — if set, only requests from this IP are accepted on
                   endpoints other than /health.
    """
    class AgentHandler(BaseHTTPRequestHandler):
        def _allowed(self):
            if not satellite_ip:
                return True
            return self.client_address[0] == satellite_ip

        def _send_json(self, code, obj):
            body = json.dumps(obj).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == '/health':
                self._send_json(200, {'status': 'ok'})
                return

            if not self._allowed():
                self.send_response(403)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'Forbidden')
                return

            if self.path != '/collect':
                self.send_response(404)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'Not Found')
                return

            data = json.dumps(collect(), default=str).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            if not self._allowed():
                self.send_response(403)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'Forbidden')
                return

            if self.path != '/run':
                self.send_response(404)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'Not Found')
                return

            try:
                length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(length)
                payload = json.loads(body.decode('utf-8'))
            except Exception as exc:
                self._send_json(400, {'error': 'Invalid JSON: {0}'.format(exc)})
                return

            script = payload.get('script', '')
            language = payload.get('language', 'shell').lower()
            if not script:
                self._send_json(400, {'error': 'script is required'})
                return

            self._send_json(200, _run_script(script, language))

        def log_message(self, fmt, *args):
            pass  # suppress per-request noise to stderr

    return AgentHandler


def main():
    # ---- argument parsing (argparse on 2.7+/3.x; manual fallback for 2.6) ----
    if HAS_ARGPARSE:
        parser = argparse.ArgumentParser(description='IsotopeIQ macOS Agent')
        parser.add_argument(
            '--serve', action='store_true',
            help='Run as a persistent HTTP server instead of printing to stdout')
        parser.add_argument(
            '--port', type=int, default=DEFAULT_AGENT_PORT,
            help='TCP port to listen on in serve mode (default: %(default)s)')
        parser.add_argument(
            '--satellite',
            help='IP or hostname of the satellite server; only requests from '
                 'this address are accepted (recommended)')
        args = parser.parse_args()
    else:
        # Minimal fallback for environments without argparse
        class args(object):
            serve = '--serve' in sys.argv
            port = DEFAULT_AGENT_PORT
            satellite = None
        for i, a in enumerate(sys.argv[1:], 1):
            if a == '--port' and i + 1 < len(sys.argv):
                args.port = int(sys.argv[i + 1])
            if a == '--satellite' and i + 1 < len(sys.argv):
                args.satellite = sys.argv[i + 1]

    if args.serve:
        satellite_ip = getattr(args, 'satellite', None) or None
        server = ThreadedHTTPServer(('0.0.0.0', args.port), _make_handler(satellite_ip))
        sys.stderr.write(
            'IsotopeIQ agent listening on 0.0.0.0:{0}\n'.format(args.port))
        if satellite_ip:
            sys.stderr.write(
                'Accepting requests from satellite: {0}\n'.format(satellite_ip))
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    else:
        print(json.dumps(collect(), default=str))


if __name__ == '__main__':
    main()
