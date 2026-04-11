"""
IsotopeIQ Windows Agent
Collects system baseline data and outputs the canonical object as JSON to stdout.

Compatible with Python 3.4+ on 32-bit Windows 7 and later.
Compile with PyInstaller:
    pyinstaller --onefile windows_collector.py
"""
from __future__ import print_function

import base64
import ctypes
import json
import os
import re
import socket
import subprocess
import sys
try:
    import winreg
except ImportError:
    winreg = None  # not on Windows — should not happen in production

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

def run(cmd, timeout=60):
    """Run a shell command, return stdout as a string. Never raises."""
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
        )
        stdout, _ = proc.communicate(timeout=timeout)
        return stdout.decode('utf-8', errors='replace').strip()
    except Exception:
        return ''


def run_lines(cmd, timeout=60):
    """Run a command and return non-empty lines."""
    return [ln for ln in run(cmd, timeout).splitlines() if ln.strip()]


def wmic(wmi_class, fields, where=''):
    """
    Query WMI and return a list of dicts, one per instance.

    Tries PowerShell Get-CimInstance first (Windows 8+, works on 10/11).
    Falls back to wmic.exe (Windows 7 / early Windows 10).

    wmi_class: WMI class name, e.g. 'Win32_Processor'
               Also accepts legacy wmic path syntax like 'cpu' or
               'logicaldisk where DriveType=3' for the fallback.
    fields:    list of property names to retrieve.
    where:     optional WQL WHERE clause, e.g. "DriveType=3".
    """
    rows = _wmic_cim(wmi_class, fields, where)
    if rows is None:
        rows = _wmic_cli(wmi_class, fields)
    return rows or []


# Map legacy wmic.exe path aliases to proper WMI class names for CIM
_WMIC_CLASS_MAP = {
    'cpu':           'Win32_Processor',
    'computersystem': 'Win32_ComputerSystem',
    'bios':          'Win32_BIOS',
    'os':            'Win32_OperatingSystem',
    'useraccount':   'Win32_UserAccount',
    'group':         'Win32_Group',
    'service':       'Win32_Service',
    'sysdriver':     'Win32_SystemDriver',
    'logicaldisk':   'Win32_LogicalDisk',
    'nicconfig':     'Win32_NetworkAdapterConfiguration',
    'startup':       'Win32_StartupCommand',
    'process':       'Win32_Process',
}


def _wmic_class_name(path):
    """Resolve a wmic path alias or Win32_ class name."""
    base = path.split()[0].lower()
    return _WMIC_CLASS_MAP.get(base, path.split()[0])


def _wmic_cim(wmi_class, fields, where=''):
    """
    Query via PowerShell Get-CimInstance.
    Returns list of dicts, or None if PowerShell is unavailable.
    """
    cls = _wmic_class_name(wmi_class)
    where_clause = ''
    if where:
        where_clause = ' -Filter "{}"'.format(where)
    elif ' where ' in wmi_class.lower():
        # Parse legacy wmic 'class where condition' syntax
        parts = wmi_class.split(None, 2)
        if len(parts) == 3 and parts[1].lower() == 'where':
            where_clause = ' -Filter "{}"'.format(parts[2])

    field_str = ', '.join(['$_.{}'.format(f) for f in fields])
    sep = '|||'
    ps_cmd = (
        'Get-CimInstance -ClassName {cls}{where}'
        ' | ForEach-Object {{ "{sep}" + ({fields} -join "|") }}'
    ).format(
        cls=cls,
        where=where_clause,
        fields=field_str,
        sep=sep,
    )
    # Encode as UTF-16LE Base64 so the command is passed to PowerShell via
    # -EncodedCommand, bypassing cmd.exe pipe/metacharacter interpretation.
    encoded = base64.b64encode(ps_cmd.encode('utf-16-le')).decode('ascii')
    out = run('powershell -NoProfile -NonInteractive -EncodedCommand {}'.format(encoded))
    if not out or 'not recognized' in out.lower() or 'error' in out.lower()[:50]:
        return None
    rows = []
    for line in out.splitlines():
        line = line.strip()
        if not line.startswith(sep):
            continue
        parts = line[len(sep):].split('|')
        row = {}
        for i, f in enumerate(fields):
            row[f] = parts[i].strip() if i < len(parts) else ''
        rows.append(row)
    return rows


def _wmic_cli(path, fields):
    """
    Query via legacy wmic.exe. Returns list of dicts.
    Works on Windows 7 through early Windows 10.
    """
    field_str = ','.join(fields)
    out = run('wmic {} get {} /format:csv'.format(path, field_str))
    rows = []
    lines = [ln for ln in out.splitlines() if ln.strip()]
    if len(lines) < 2:
        return rows
    # First non-empty line is the CSV header (Node,Field1,Field2,...)
    header = [h.strip() for h in lines[0].split(',')]
    for line in lines[1:]:
        parts = line.split(',')
        if len(parts) < len(header):
            continue
        row = {}
        for i, h in enumerate(header):
            row[h] = parts[i].strip() if i < len(parts) else ''
        rows.append(row)
    return rows


def reg_get(hive, path, name):
    """Read a single registry value. Returns None on any error."""
    if winreg is None:
        return None
    hive_map = {
        'HKLM': winreg.HKEY_LOCAL_MACHINE,
        'HKCU': winreg.HKEY_CURRENT_USER,
    }
    try:
        root = hive_map.get(hive, winreg.HKEY_LOCAL_MACHINE)
        with winreg.OpenKey(root, path) as key:
            value, _ = winreg.QueryValueEx(key, name)
            return value
    except Exception:
        return None


def reg_subkeys(hive, path):
    """Return list of subkey names under hive\\path."""
    if winreg is None:
        return []
    hive_map = {
        'HKLM': winreg.HKEY_LOCAL_MACHINE,
        'HKCU': winreg.HKEY_CURRENT_USER,
    }
    keys = []
    try:
        root = hive_map.get(hive, winreg.HKEY_LOCAL_MACHINE)
        with winreg.OpenKey(root, path) as key:
            i = 0
            while True:
                try:
                    keys.append(winreg.EnumKey(key, i))
                    i += 1
                except OSError:
                    break
    except Exception:
        pass
    return keys


def reg_values(hive, path):
    """Return dict of all values under hive\\path."""
    if winreg is None:
        return {}
    hive_map = {
        'HKLM': winreg.HKEY_LOCAL_MACHINE,
        'HKCU': winreg.HKEY_CURRENT_USER,
    }
    out = {}
    try:
        root = hive_map.get(hive, winreg.HKEY_LOCAL_MACHINE)
        with winreg.OpenKey(root, path) as key:
            i = 0
            while True:
                try:
                    name, value, _ = winreg.EnumValue(key, i)
                    out[name] = value
                    i += 1
                except OSError:
                    break
    except Exception:
        pass
    return out


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


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
    }


# ---------------------------------------------------------------------------
# device
# ---------------------------------------------------------------------------

def collect_device(output):
    hostname = os.environ.get('COMPUTERNAME', socket.gethostname())
    try:
        fqdn = socket.getfqdn()
    except Exception:
        fqdn = hostname

    rows = wmic('computersystem', ['Manufacturer', 'Model'])
    vendor = rows[0].get('Manufacturer', '') if rows else ''
    model  = rows[0].get('Model', '') if rows else ''

    output['device']['hostname']    = hostname
    output['device']['fqdn']        = fqdn
    output['device']['device_type'] = 'server'
    output['device']['vendor']      = vendor
    output['device']['model']       = model


# ---------------------------------------------------------------------------
# hardware
# ---------------------------------------------------------------------------

def collect_hardware(output):
    cpu_rows  = wmic('cpu', ['Name', 'NumberOfLogicalProcessors'])
    cs_rows   = wmic('computersystem', ['TotalPhysicalMemory', 'NumberOfLogicalProcessors'])
    bios_rows = wmic('bios', ['SMBIOSBIOSVersion', 'SerialNumber'])

    cpu_model = cpu_rows[0].get('Name', '').strip() if cpu_rows else ''
    try:
        cpu_cores = int(cpu_rows[0].get('NumberOfLogicalProcessors', '')) if cpu_rows else None
    except (ValueError, TypeError):
        cpu_cores = None

    try:
        mem_bytes = int(cs_rows[0].get('TotalPhysicalMemory', 0)) if cs_rows else 0
        mem_gb = round(mem_bytes / (1024 ** 3), 2) if mem_bytes else None
    except (ValueError, TypeError):
        mem_gb = None

    bios_ver = bios_rows[0].get('SMBIOSBIOSVersion', '') if bios_rows else ''
    serial   = bios_rows[0].get('SerialNumber', '') if bios_rows else ''
    arch     = os.environ.get('PROCESSOR_ARCHITECTURE', '')

    # Virtualization detection
    virt = 'bare-metal'
    if cs_rows:
        m   = cs_rows[0].get('Model', '').lower()
        mfr = cs_rows[0].get('Manufacturer', '').lower() if cs_rows else ''
        if 'vmware' in m:
            virt = 'vmware'
        elif 'virtualbox' in m or 'vbox' in m:
            virt = 'virtualbox'
        elif 'hyper-v' in m or 'hyperv' in m or 'microsoft' in mfr:
            virt = 'hyperv'
        elif 'virtual' in m:
            virt = 'other'

    output['hardware']['cpu_model']          = cpu_model
    output['hardware']['cpu_cores']          = cpu_cores
    output['hardware']['memory_gb']          = mem_gb
    output['hardware']['bios_version']       = bios_ver
    output['hardware']['serial_number']      = serial
    output['hardware']['architecture']       = arch
    output['hardware']['virtualization_type'] = virt


# ---------------------------------------------------------------------------
# os
# ---------------------------------------------------------------------------

def collect_os(output):
    os_rows = wmic('os', ['Caption', 'Version', 'BuildNumber'])
    name    = os_rows[0].get('Caption', 'Windows').strip() if os_rows else 'Windows'
    version = os_rows[0].get('Version', '').strip() if os_rows else ''
    build   = os_rows[0].get('BuildNumber', '').strip() if os_rows else ''

    # Timezone
    tz = run('tzutil /g').strip() or 'unknown'

    # NTP servers from registry
    ntp_raw = reg_get('HKLM',
        r'SYSTEM\CurrentControlSet\Services\W32Time\Parameters', 'NtpServer') or ''
    ntp_servers = []
    for s in ntp_raw.split():
        srv = s.split(',')[0].strip()
        if srv:
            ntp_servers.append(srv)

    # NTP sync status
    ntp_synced = None
    w32_out = run('w32tm /query /status')
    if w32_out:
        m = re.search(r'Source:\s*(.+)', w32_out)
        if m:
            src = m.group(1).strip()
            ntp_synced = src not in ('Local CMOS Clock', 'Free-running system clock', 'unspecified')

    output['os']['name']        = name
    output['os']['version']     = version
    output['os']['build']       = build
    output['os']['kernel']      = version
    output['os']['timezone']    = tz
    output['os']['ntp_servers'] = ntp_servers
    output['os']['ntp_synced']  = ntp_synced


# ---------------------------------------------------------------------------
# network
# ---------------------------------------------------------------------------

# InterfaceType values from NET_IF_TYPE (ifdef.h / MSDN)
# https://docs.microsoft.com/en-us/windows/win32/api/ifdef/ne-ifdef-net_if_type
_WIN_IF_TYPE_MAP = {
    6:   'physical',   # Ethernet (IF_TYPE_ETHERNET_CSMACD)
    71:  'physical',   # IEEE 802.11 Wi-Fi (IF_TYPE_IEEE80211)
    24:  'loopback',   # Software Loopback (IF_TYPE_SOFTWARE_LOOPBACK)
    131: 'tunnel',     # Tunnel (IF_TYPE_TUNNEL)
    53:  'tunnel',     # PPP (IF_TYPE_PPP)
    23:  'tunnel',     # PPP (IF_TYPE_PPP alternate)
    157: 'virtual',    # NDIS virtual (IF_TYPE_IEEE8023AD_LAG)
}


def _collect_network_powershell(iface_map):
    """
    Populate iface_map using PowerShell Get-NetAdapter + Get-NetIPAddress.
    Preferred on Windows 8 / Server 2012 and later (including Windows 11 where
    wmic.exe is deprecated).  Returns True on success, False if unavailable.
    """
    import csv as _csv, io as _io

    # ── adapters ────────────────────────────────────────────────────────────
    adapter_out = run(
        'powershell -NoProfile -NonInteractive -Command '
        '"Get-NetAdapter | Select-Object Name,MacAddress,Status,Speed,'
        'InterfaceType,InterfaceDescription | ConvertTo-Csv -NoTypeInformation"',
        timeout=30,
    )
    # If the cmdlet is absent, PowerShell echoes an error to stderr and returns
    # empty stdout, or the string contains "not recognized".
    if not adapter_out or 'not recognized' in adapter_out.lower():
        return False

    try:
        for row in _csv.DictReader(_io.StringIO(adapter_out)):
            name = row.get('Name', '').strip()
            if not name:
                continue
            mac  = row.get('MacAddress', '').strip().replace('-', ':').lower()
            desc = row.get('InterfaceDescription', '').strip()
            status = row.get('Status', '').strip().lower()

            try:
                if_type_int = int(row.get('InterfaceType', '0') or 0)
            except ValueError:
                if_type_int = 0

            # Use NDIS type enum first; fall back to name/description heuristic
            iface_type = _WIN_IF_TYPE_MAP.get(if_type_int)
            if iface_type is None:
                iface_type = _classify_iface_windows(desc or name)

            if iface_type in _WIN_SKIP_TYPES:
                continue

            speed_raw = row.get('Speed', '').strip()
            try:
                speed_bps = int(speed_raw)
                if speed_bps >= 1_000_000_000:
                    speed = '{}G'.format(speed_bps // 1_000_000_000)
                elif speed_bps >= 1_000_000:
                    speed = '{}M'.format(speed_bps // 1_000_000)
                else:
                    speed = speed_raw
            except (ValueError, TypeError):
                speed = ''

            oper = 'up' if status in ('up', 'connected') else 'down'
            iface_map[name] = {
                'name': name, 'mac': mac, 'description': desc,
                'ipv4': [], 'ipv6': [],
                'admin_status': oper, 'oper_status': oper,
                'speed': speed, 'duplex': 'unknown', 'mtu': None,
                'port_mode': 'routed', 'access_vlan': None, 'trunk_vlans': '',
                'interface_type': iface_type,
            }
    except Exception:
        return False

    if not iface_map:
        return False

    # ── IP addresses ────────────────────────────────────────────────────────
    ip_out = run(
        'powershell -NoProfile -NonInteractive -Command '
        '"Get-NetIPAddress | Select-Object InterfaceAlias,IPAddress,'
        'PrefixLength,AddressFamily | ConvertTo-Csv -NoTypeInformation"',
        timeout=30,
    )
    try:
        for row in _csv.DictReader(_io.StringIO(ip_out)):
            alias = row.get('InterfaceAlias', '').strip()
            ip    = row.get('IPAddress', '').strip()
            pfx   = row.get('PrefixLength', '').strip()
            fam   = row.get('AddressFamily', '').strip()  # '2'=IPv4, '23'=IPv6
            if not alias or not ip or alias not in iface_map:
                continue
            if ip in ('127.0.0.1', '::1'):
                continue
            cidr = '{}/{}'.format(ip, pfx) if pfx else ip
            if fam in ('2', 'IPv4'):
                iface_map[alias]['ipv4'].append(cidr)
            elif fam in ('23', 'IPv6'):
                iface_map[alias]['ipv6'].append(cidr)
    except Exception:
        pass

    # ── MTU via Get-NetIPInterface ───────────────────────────────────────────
    mtu_out = run(
        'powershell -NoProfile -NonInteractive -Command '
        '"Get-NetIPInterface | Select-Object InterfaceAlias,NlMtu | '
        'ConvertTo-Csv -NoTypeInformation"',
        timeout=30,
    )
    try:
        for row in _csv.DictReader(_io.StringIO(mtu_out)):
            alias = row.get('InterfaceAlias', '').strip()
            mtu_s = row.get('NlMtu', '').strip()
            if alias in iface_map and mtu_s:
                try:
                    iface_map[alias]['mtu'] = int(mtu_s)
                except ValueError:
                    pass
    except Exception:
        pass

    return True


def collect_network(output):
    iface_map = {}

    # ── Try PowerShell-native path first (Windows 8 / Server 2012+) ─────────
    # Get-NetAdapter provides NDIS InterfaceType enum for accurate classification,
    # speed in bps, description, and link status without relying on wmic.exe
    # (deprecated in Windows 11).
    ps_ok = _collect_network_powershell(iface_map)

    if not ps_ok:
        # ── Legacy fallback: netsh + getmac + wmic (Windows 7) ──────────────

        # IP addresses via netsh
        netsh_out = run('netsh interface ip show address')
        current   = None
        for line in netsh_out.splitlines():
            m = re.match(r'Configuration for interface "(.+)"', line.strip())
            if m:
                current = m.group(1).strip()
                if current not in iface_map:
                    iface_map[current] = _empty_iface(current)
                continue
            if current:
                m4 = re.search(r'IP Address:\s+(\d+\.\d+\.\d+\.\d+)', line)
                if m4:
                    ip = m4.group(1)
                    if ip not in ('127.0.0.1',):
                        iface_map[current]['ipv4'].append(ip)
                m6 = re.search(r'IPv6 Address.*?:\s+([0-9a-fA-F:]+)', line)
                if m6:
                    ip = m6.group(1).strip()
                    if ip not in ('::1',):
                        iface_map[current]['ipv6'].append(ip)

        # MAC addresses via getmac
        getmac_out = run('getmac /v /fo csv /nh')
        for line in getmac_out.splitlines():
            line = line.strip().strip('"')
            parts = [p.strip().strip('"') for p in line.split('","')]
            if len(parts) >= 3:
                name = parts[0]
                mac  = parts[2].replace('-', ':')
                if name in iface_map:
                    iface_map[name]['mac'] = mac

        # Subnet masks via wmic / Get-CimInstance to build proper CIDRs
        nic_rows = wmic(
            'nicconfig where IPEnabled=TRUE',
            ['Description', 'IPAddress', 'IPSubnet', 'MACAddress']
        )
        for row in nic_rows:
            desc = row.get('Description', '').strip()
            ips  = row.get('IPAddress', '').strip('{} ')
            subs = row.get('IPSubnet', '').strip('{} ')
            mac  = row.get('MACAddress', '').strip()
            ip_list  = [i.strip() for i in ips.split(';') if i.strip()] if ips else []
            sub_list = [s.strip() for s in subs.split(';') if s.strip()] if subs else []

            iface = None
            for ifname, ifobj in iface_map.items():
                if mac and ifobj.get('mac', '').replace('-', ':').upper() == mac.upper():
                    iface = ifobj
                    break
            if iface is None:
                iface = _empty_iface(desc)
                iface_map[desc] = iface

            if mac:
                iface['mac'] = mac

            iface['ipv4'] = []
            iface['ipv6'] = []
            for i, ip in enumerate(ip_list):
                sub = sub_list[i] if i < len(sub_list) else ''
                if ':' in ip:
                    try:
                        prefix = int(sub) if sub.isdigit() else 64
                        iface['ipv6'].append('{}/{}'.format(ip, prefix))
                    except Exception:
                        iface['ipv6'].append(ip)
                else:
                    prefix = _mask_to_prefix(sub) if sub else 24
                    if ip not in ('127.0.0.1',):
                        iface['ipv4'].append('{}/{}'.format(ip, prefix))

    output['network']['interfaces'] = [
        i for i in iface_map.values()
        if i.get('interface_type') not in _WIN_SKIP_TYPES
    ]

    # DNS servers
    dns_out = run('netsh interface ip show dns')
    dns_servers = []
    seen = set()
    for line in dns_out.splitlines():
        m = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
        if m:
            ip = m.group(1)
            if ip not in seen:
                seen.add(ip)
                dns_servers.append(ip)
    output['network']['dns_servers'] = dns_servers

    # Default gateway
    route_out = run('route print 0.0.0.0')
    for line in route_out.splitlines():
        m = re.match(r'\s*0\.0\.0\.0\s+0\.0\.0\.0\s+(\S+)', line)
        if m:
            output['network']['default_gateway'] = m.group(1)
            break

    # Routes
    routes = []
    route_all = run('route print')
    in_ipv4 = False
    for line in route_all.splitlines():
        if 'IPv4 Route Table' in line:
            in_ipv4 = True
        if 'IPv6 Route Table' in line or 'Persistent Routes' in line:
            in_ipv4 = False
        if not in_ipv4:
            continue
        m = re.match(r'\s*(\d+\.\d+\.\d+\.\d+)\s+(\d+\.\d+\.\d+\.\d+)\s+(\S+)\s+(\S+)\s+(\d+)', line)
        if m:
            dest, mask, gw, iface, metric = m.groups()
            prefix = _mask_to_prefix(mask)
            routes.append({
                'destination': '{}/{}'.format(dest, prefix),
                'gateway':     gw,
                'interface':   iface,
                'metric':      int(metric),
            })
    output['network']['routes'] = routes

    # Hosts file
    hosts = []
    hosts_path = r'C:\Windows\System32\drivers\etc\hosts'
    try:
        with open(hosts_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    hosts.append({'ip': parts[0], 'hostname': parts[1]})
    except Exception:
        pass
    output['network']['hosts_file'] = hosts


_WIN_SKIP_TYPES = {'loopback', 'skip'}


def _classify_iface_windows(name):
    """Classify a Windows adapter by its display name."""
    nl = name.lower()
    if 'loopback' in nl:
        return 'loopback'
    if 'teredo' in nl or 'isatap' in nl or '6to4' in nl:
        return 'tunnel'
    if any(v in nl for v in ('vmware', 'virtualbox', 'hyper-v', 'virtual adapter')):
        return 'virtual'
    if 'wan miniport' in nl or 'kernel debug' in nl:
        return 'skip'
    return 'physical'


def _empty_iface(name):
    return {
        'name': name, 'mac': '', 'description': '',
        'ipv4': [], 'ipv6': [],
        'admin_status': 'unknown', 'oper_status': 'unknown',
        'speed': '', 'duplex': 'unknown', 'mtu': None,
        'port_mode': 'routed', 'access_vlan': None, 'trunk_vlans': '',
        'interface_type': _classify_iface_windows(name),
    }


def _mask_to_prefix(mask):
    try:
        return sum(bin(int(o)).count('1') for o in mask.split('.'))
    except Exception:
        return 24


# ---------------------------------------------------------------------------
# users
# ---------------------------------------------------------------------------

def collect_users(output):
    # Build admin set from net localgroup Administrators
    admin_set = set()
    admin_out = run('net localgroup Administrators')
    in_members = False
    for line in admin_out.splitlines():
        if '---' in line:
            in_members = True
            continue
        if in_members:
            name = line.strip()
            if name and 'The command completed' not in name:
                admin_set.add(name.lower())

    # User list from wmic
    user_rows = wmic('useraccount where LocalAccount=TRUE',
                     ['Name', 'SID', 'Disabled', 'PasswordLastSet', 'Lockout'])
    for row in user_rows:
        name     = row.get('Name', '').strip()
        sid      = row.get('SID', '').strip()
        disabled = row.get('Disabled', 'FALSE').strip().upper() == 'TRUE'
        is_admin = name.lower() in admin_set

        # Get user's groups
        groups = []
        grp_out = run('net user "{}"'.format(name))
        for line in grp_out.splitlines():
            if line.strip().startswith('Local Group Memberships'):
                parts = re.split(r'\s{2,}', line)
                for p in parts[1:]:
                    g = p.strip().lstrip('*')
                    if g:
                        groups.append(g)

        output['users'].append({
            'username':          name,
            'uid':               sid,
            'groups':            groups,
            'home':              '',
            'shell':             '',
            'disabled':          disabled,
            'password_last_set': '',
            'last_login':        '',
            'sudo_privileges':   'Administrators' if is_admin else '',
        })


# ---------------------------------------------------------------------------
# groups
# ---------------------------------------------------------------------------

def collect_groups(output):
    group_rows = wmic('group where LocalAccount=TRUE', ['Name', 'SID'])
    for row in group_rows:
        name = row.get('Name', '').strip()
        sid  = row.get('SID', '').strip()
        if not name:
            continue
        members = []
        mem_out = run('net localgroup "{}"'.format(name))
        in_members = False
        for line in mem_out.splitlines():
            if '---' in line:
                in_members = True
                continue
            if in_members:
                m = line.strip()
                if m and 'The command completed' not in m:
                    members.append(m)
        output['groups'].append({
            'group_name': name,
            'gid':        sid,
            'members':    members,
        })


# ---------------------------------------------------------------------------
# packages
# ---------------------------------------------------------------------------

def collect_packages(output):
    reg_paths = [
        (winreg.HKEY_LOCAL_MACHINE,
         r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall'),
        (winreg.HKEY_LOCAL_MACHINE,
         r'SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall'),
        (winreg.HKEY_CURRENT_USER,
         r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall'),
    ]
    seen = set()
    for hive, path in reg_paths:
        try:
            with winreg.OpenKey(hive, path) as base:
                i = 0
                while True:
                    try:
                        sub = winreg.EnumKey(base, i)
                        i += 1
                        with winreg.OpenKey(base, sub) as k:
                            try:
                                name, _ = winreg.QueryValueEx(k, 'DisplayName')
                            except OSError:
                                continue
                            if not name:
                                continue
                            try:
                                ver, _ = winreg.QueryValueEx(k, 'DisplayVersion')
                            except OSError:
                                ver = ''
                            try:
                                pub, _ = winreg.QueryValueEx(k, 'Publisher')
                            except OSError:
                                pub = ''
                            try:
                                idate, _ = winreg.QueryValueEx(k, 'InstallDate')
                            except OSError:
                                idate = ''
                            key = '{}|{}'.format(name, ver)
                            if key in seen:
                                continue
                            seen.add(key)
                            output['packages'].append({
                                'name':         name,
                                'version':      ver or '',
                                'vendor':       pub or '',
                                'install_date': idate or '',
                                'source':       'msi',
                            })
                    except OSError:
                        break
        except Exception:
            pass


# ---------------------------------------------------------------------------
# services
# ---------------------------------------------------------------------------

def collect_services(output):
    rows = wmic('service', ['Name', 'State', 'StartMode'])
    status_map  = {'running': 'running', 'stopped': 'stopped'}
    startup_map = {
        'auto': 'enabled', 'automatic': 'enabled',
        'manual': 'manual', 'disabled': 'disabled',
        'boot': 'enabled', 'system': 'enabled',
    }
    for row in rows:
        name  = row.get('Name', '').strip()
        state = row.get('State', '').strip().lower()
        start = row.get('StartMode', '').strip().lower()
        if not name:
            continue
        output['services'].append({
            'name':    name,
            'status':  status_map.get(state, 'unknown'),
            'startup': startup_map.get(start, 'unknown'),
        })


# ---------------------------------------------------------------------------
# filesystem
# ---------------------------------------------------------------------------

def collect_filesystem(output):
    rows = wmic('logicaldisk where DriveType=3',
                ['DeviceID', 'FileSystem', 'Size', 'FreeSpace'])
    for row in rows:
        drive  = row.get('DeviceID', '').strip()
        fstype = row.get('FileSystem', '').strip()
        try:
            size_gb = round(int(row.get('Size', 0)) / (1024 ** 3), 2)
        except (ValueError, TypeError):
            size_gb = None
        try:
            free_gb = round(int(row.get('FreeSpace', 0)) / (1024 ** 3), 2)
        except (ValueError, TypeError):
            free_gb = None
        if not drive:
            continue
        output['filesystem'].append({
            'mount':         drive,
            'type':          fstype,
            'size_gb':       size_gb,
            'free_gb':       free_gb,
            'mount_options': [],
            'suid_files':    [],
        })


# ---------------------------------------------------------------------------
# security
# ---------------------------------------------------------------------------

def collect_security(output):
    # UAC
    uac_val = reg_get('HKLM',
        r'SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System', 'EnableLUA')
    output['security']['uac_enabled'] = bool(uac_val) if uac_val is not None else None

    # Firewall
    fw_out = run('netsh advfirewall show allprofiles state')
    if 'ON' in fw_out.upper():
        output['security']['firewall_enabled'] = True
    elif 'OFF' in fw_out.upper():
        output['security']['firewall_enabled'] = False

    # Antivirus via WMI SecurityCenter2
    av_out = run(
        'wmic /namespace:\\\\root\\SecurityCenter2 path AntiVirusProduct '
        'get displayName /format:csv'
    )
    av_names = []
    for line in av_out.splitlines():
        parts = line.split(',')
        if len(parts) >= 2 and parts[1].strip() and parts[1].strip().lower() != 'displayname':
            av_names.append(parts[1].strip())
    output['security']['antivirus'] = ','.join(av_names) if av_names else ''

    # Secure boot
    sb_out = run('powershell -NoProfile -Command "Confirm-SecureBootUEFI" 2>nul')
    if sb_out.strip().lower() == 'true':
        output['security']['secure_boot'] = True
    elif sb_out.strip().lower() == 'false':
        output['security']['secure_boot'] = False

    # Audit logging — check if any category has Success/Failure configured
    audit_out = run('auditpol /get /category:* 2>nul')
    if audit_out:
        output['security']['audit_logging_enabled'] = (
            'Success' in audit_out or 'Failure' in audit_out
        )

    # Password policy
    net_out = run('net accounts')
    policy = {}
    for line in net_out.splitlines():
        if 'Minimum password length' in line:
            m = re.search(r'(\d+)', line)
            if m:
                try:
                    policy['min_length'] = int(m.group(1))
                except ValueError:
                    pass
        elif 'Maximum password age' in line:
            m = re.search(r'(\d+)', line)
            if m:
                try:
                    policy['max_age_days'] = int(m.group(1))
                except ValueError:
                    pass
        elif 'Lockout threshold' in line:
            m = re.search(r'(\d+)', line)
            if m:
                try:
                    policy['lockout_threshold'] = int(m.group(1))
                except ValueError:
                    pass
    if policy:
        output['security']['password_policy'] = policy


# ---------------------------------------------------------------------------
# scheduled tasks
# ---------------------------------------------------------------------------

def collect_scheduled_tasks(output):
    out = run('schtasks /query /fo CSV /v')
    lines = [ln for ln in out.splitlines() if ln.strip()]
    if len(lines) < 2:
        return

    # Parse header
    header = []
    for f in lines[0].split('","'):
        header.append(f.strip().strip('"'))

    def get_field(parts, name):
        try:
            idx = header.index(name)
            return parts[idx].strip().strip('"') if idx < len(parts) else ''
        except ValueError:
            return ''

    for line in lines[1:]:
        # Simple CSV split (fields are all quoted in /fo CSV)
        parts = line.split('","')
        if not parts:
            continue
        name    = get_field(parts, 'TaskName')
        user    = get_field(parts, 'Run As User')
        sched   = get_field(parts, 'Schedule')
        cmd     = get_field(parts, 'Task To Run')
        status  = get_field(parts, 'Status')
        enabled = status.lower() not in ('disabled',)
        if not name or name == 'TaskName':
            continue
        output['scheduled_tasks'].append({
            'name':     name,
            'type':     'windows-task-scheduler',
            'command':  cmd,
            'schedule': sched,
            'user':     user,
            'enabled':  enabled,
        })


# ---------------------------------------------------------------------------
# ssh keys
# ---------------------------------------------------------------------------

def collect_ssh_keys(output):
    paths = [
        (r'C:\ProgramData\ssh\administrators_authorized_keys', 'SYSTEM'),
    ]
    # Per-user keys
    users_dir = r'C:\Users'
    try:
        for uname in os.listdir(users_dir):
            p = os.path.join(users_dir, uname, '.ssh', 'authorized_keys')
            paths.append((p, uname))
    except Exception:
        pass

    for path, uname in paths:
        try:
            with open(path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    parts = line.split(None, 2)
                    if len(parts) < 2:
                        continue
                    output['ssh_keys'].append({
                        'username':   uname,
                        'key_type':   parts[0],
                        'public_key': parts[1],
                        'comment':    parts[2] if len(parts) > 2 else '',
                    })
        except Exception:
            pass


# ---------------------------------------------------------------------------
# kernel modules (drivers)
# ---------------------------------------------------------------------------

def collect_kernel_modules(output):
    rows = wmic('sysdriver', ['Name', 'State', 'StartMode', 'PathName'])
    for row in rows:
        name = row.get('Name', '').strip()
        if not name:
            continue
        output['kernel_modules'].append({
            'name':        name,
            'type':        'driver',
            'description': '',
            'path':        row.get('PathName', '').strip(),
            'hash':        '',
            'signed':      None,
        })


# ---------------------------------------------------------------------------
# PCI devices
# ---------------------------------------------------------------------------

def collect_pci_devices(output):
    """Collect PCI devices via Win32_PnPEntity (WMI)."""
    # Fetch all PnPEntity rows and filter in Python to avoid WQL backslash/
    # percent escaping issues when the command passes through cmd.exe.
    rows = wmic('Win32_PnPEntity', ['PNPDeviceID', 'PNPClass', 'Manufacturer', 'Name'])
    for row in rows:
        slot = row.get('PNPDeviceID', '').strip()
        if not slot.upper().startswith('PCI\\'):
            continue
        output['pci_devices'].append({
            'slot':   slot,
            'class':  row.get('PNPClass', '').strip(),
            'vendor': row.get('Manufacturer', '').strip(),
            'device': row.get('Name', '').strip(),
        })


# ---------------------------------------------------------------------------
# listening services
# ---------------------------------------------------------------------------

def collect_storage_devices(output):
    """Collect physical drives and optical media via WMI."""
    rows = wmic('Win32_DiskDrive', ['DeviceID', 'Model', 'Manufacturer', 'Size', 'SerialNumber', 'InterfaceType'])
    for row in rows:
        name = row.get('DeviceID', '').strip()
        if not name:
            continue
        size_bytes = row.get('Size', '').strip()
        try:
            size = f"{round(int(size_bytes) / (1024**3), 2)}G"
        except (ValueError, TypeError):
            size = ''
        iface = row.get('InterfaceType', '').strip().lower()
        entry = {'name': name, 'type': 'disk'}
        if row.get('Model'):        entry['model']     = row['Model'].strip()
        if row.get('Manufacturer'): entry['vendor']    = row['Manufacturer'].strip()
        if size:                    entry['size']      = size
        if row.get('SerialNumber'): entry['serial']    = row['SerialNumber'].strip()
        if iface:                   entry['interface'] = iface
        entry['removable'] = False
        output['storage_devices'].append(entry)

    rows = wmic('Win32_CDROMDrive', ['Drive', 'Caption', 'Manufacturer'])
    for row in rows:
        name = row.get('Drive', '').strip() or 'CDROM'
        entry = {'name': name, 'type': 'optical', 'removable': True, 'interface': 'ide'}
        if row.get('Caption'):      entry['model']  = row['Caption'].strip()
        if row.get('Manufacturer'): entry['vendor'] = row['Manufacturer'].strip()
        output['storage_devices'].append(entry)


def collect_usb_devices(output):
    """Collect USB devices via Win32_PnPEntity."""
    # Filter in Python — avoids WQL backslash/percent escaping through cmd.exe.
    rows = wmic('Win32_PnPEntity', ['PNPDeviceID', 'Manufacturer', 'Name'])
    for row in rows:
        if 'VID_' not in row.get('PNPDeviceID', '').upper():
            continue
        bus_id = row.get('PNPDeviceID', '').strip()
        if not bus_id:
            continue
        vid = ''
        pid = ''
        m = re.search(r'VID_([0-9A-Fa-f]+)', bus_id)
        if m:
            vid = m.group(1).lower()
        m = re.search(r'PID_([0-9A-Fa-f]+)', bus_id)
        if m:
            pid = m.group(1).lower()
        entry = {'bus_id': bus_id}
        if vid: entry['vendor_id']    = vid
        if pid: entry['product_id']   = pid
        if row.get('Manufacturer'): entry['manufacturer'] = row['Manufacturer'].strip()
        if row.get('Name'):         entry['product']      = row['Name'].strip()
        output['usb_devices'].append(entry)


# ---------------------------------------------------------------------------
# listening services
# ---------------------------------------------------------------------------

def collect_listening_services(output):
    out = run('netstat -ano')
    proto_map = {'tcp': 'tcp', 'tcp6': 'tcp6', 'udp': 'udp', 'udp6': 'udp6'}
    for line in out.splitlines():
        line = line.strip()
        if not line or line.lower().startswith('proto') or line.lower().startswith('active'):
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        proto_raw = parts[0].lower()
        if proto_raw not in proto_map:
            continue
        proto = proto_map[proto_raw]
        local = parts[1]
        state = parts[3].upper() if len(parts) > 3 else ''

        if proto in ('tcp', 'tcp6') and state != 'LISTENING':
            continue

        # Parse address:port (handle IPv6 [::]:port)
        if local.startswith('['):
            m = re.match(r'\[(.+)\]:(\d+)', local)
            if not m:
                continue
            local_addr, port_s = m.group(1), m.group(2)
        else:
            local_addr, _, port_s = local.rpartition(':')

        try:
            port = int(port_s)
        except ValueError:
            continue

        pid = None
        try:
            pid = int(parts[-1])
        except (ValueError, IndexError):
            pass

        output['listening_services'].append({
            'protocol':      proto,
            'local_address': local_addr,
            'port':          port,
            'process_name':  '',
            'pid':           pid,
            'user':          '',
        })
        if port not in output['network']['open_ports']:
            output['network']['open_ports'].append(port)


# ---------------------------------------------------------------------------
# firewall rules
# ---------------------------------------------------------------------------

def collect_firewall_rules(output):
    direction_map = {'in': 'in', 'inbound': 'in', 'out': 'out', 'outbound': 'out'}
    action_map    = {'allow': 'allow', 'block': 'block', 'bypass': 'allow'}

    # Try modern PowerShell Get-NetFirewallRule (Win 8 / Server 2012+, including Win 10/11).
    # All string literals use single quotes to avoid cmd.exe/PowerShell quoting conflicts.
    # Outputs one sentinel line per rule: |||Name|Direction|Action|Enabled|Protocol|LocalPort|RemoteAddress
    ps_script = (
        "if (Get-Command Get-NetFirewallRule -ErrorAction SilentlyContinue) {"
        " Get-NetFirewallRule -ErrorAction SilentlyContinue | ForEach-Object {"
        "  $r=$_;"
        "  $pf=$r|Get-NetFirewallPortFilter -ErrorAction SilentlyContinue;"
        "  $af=$r|Get-NetFirewallAddressFilter -ErrorAction SilentlyContinue;"
        "  $proto=if ($pf){$pf.Protocol}else{'Any'};"
        "  $lport=if ($pf){($pf.LocalPort -join ',')}else{'Any'};"
        "  $raddr=if ($af){($af.RemoteAddress -join ',')}else{'Any'};"
        "  $n=($r.DisplayName -replace '[|]',' ');"
        "  Write-Output ('|||'+($n,$r.Direction.ToString(),$r.Action.ToString(),$r.Enabled.ToString(),$proto,$lport,$raddr -join '|'))"
        " }"
        "}"
    )
    ps_out = run('powershell -NoProfile -NonInteractive -Command "{}"'.format(
        ps_script.replace('"', '\\"')
    ))

    if ps_out and '|||' in ps_out:
        for line in ps_out.splitlines():
            line = line.strip()
            if not line.startswith('|||'):
                continue
            parts = line[3:].split('|', 6)
            if len(parts) < 4 or not parts[0]:
                continue
            direction = parts[1].lower() if len(parts) > 1 else ''
            action    = parts[2].lower() if len(parts) > 2 else ''
            enabled   = parts[3].lower() in ('true', 'yes') if len(parts) > 3 else True
            protocol  = parts[4] if len(parts) > 4 else 'Any'
            lport     = parts[5] if len(parts) > 5 else ''
            raddr     = parts[6] if len(parts) > 6 else 'Any'
            output['firewall_rules'].append({
                'chain':       parts[0],
                'direction':   direction_map.get(direction, 'unknown'),
                'action':      action_map.get(action, action),
                'protocol':    protocol,
                'source':      raddr,
                'destination': 'any',
                'port':        lport,
                'enabled':     enabled,
                'description': '',
                'source_tool': 'windows-firewall',
            })
        return

    # Fallback: netsh advfirewall (Windows 7 / when PowerShell unavailable).
    # netsh verbose output uses "Rule Name:" (with a space) as the rule name field.
    out = run('netsh advfirewall firewall show rule name=all verbose')
    rule_buf = {}
    for line in out.splitlines():
        line = line.strip()
        if re.match(r'^-{3,}$', line):
            if rule_buf.get('rule name'):
                _flush_fw_rule(rule_buf, output, direction_map, action_map)
            rule_buf = {}
            continue
        if ':' in line:
            k, _, v = line.partition(':')
            rule_buf[k.strip().lower()] = v.strip()
    if rule_buf.get('rule name'):
        _flush_fw_rule(rule_buf, output, direction_map, action_map)


def _flush_fw_rule(buf, output, direction_map, action_map):
    direction_raw = buf.get('direction', '').lower()
    action_raw    = buf.get('action', '').lower()
    enabled_raw   = buf.get('enabled', 'yes').lower()
    output['firewall_rules'].append({
        'chain':       buf.get('rule name', ''),
        'direction':   direction_map.get(direction_raw, 'unknown'),
        'action':      action_map.get(action_raw, action_raw),
        'protocol':    buf.get('protocol', 'any'),
        'source':      buf.get('remoteip', 'any'),
        'destination': buf.get('localip', 'any'),
        'port':        buf.get('localport', ''),
        'enabled':     enabled_raw in ('yes', 'true'),
        'description': buf.get('description', ''),
        'source_tool': 'windows-firewall',
    })


# ---------------------------------------------------------------------------
# sysctl — Windows equivalent: registry security/kernel settings (LSA, UAC, etc.)
# ---------------------------------------------------------------------------

def collect_sysctl(output):
    reg_targets = [
        ('HKLM', r'SYSTEM\CurrentControlSet\Control\Lsa', [
            'LmCompatibilityLevel', 'NoLMHash', 'RestrictAnonymous',
            'RestrictAnonymousSAM', 'EveryoneIncludesAnonymous',
            'DisableDomainCreds', 'ForceGuest', 'LimitBlankPasswordUse',
            'AuditBaseObjects', 'FullPrivilegeAuditing',
            'SCENoApplyLegacyAuditPolicy', 'CrashOnAuditFail',
        ]),
        ('HKLM', r'SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System', [
            'EnableLUA', 'ConsentPromptBehaviorAdmin',
            'ConsentPromptBehaviorUser', 'EnableInstallerDetection',
            'ValidateAdminCodeSignatures', 'EnableSecureUIAPaths',
            'EnableVirtualization', 'PromptOnSecureDesktop',
            'FilterAdministratorToken', 'DontDisplayLastUserName',
        ]),
    ]
    for hive, path, names in reg_targets:
        for name in names:
            val = reg_get(hive, path, name)
            if val is not None:
                output['sysctl'].append({
                    'key':   '{}\\{}\\{}'.format(hive, path, name),
                    'value': str(val),
                })


# ---------------------------------------------------------------------------
# startup items
# ---------------------------------------------------------------------------

def collect_startup_items(output):
    rows = wmic('startup', ['Caption', 'Command', 'Location'])
    for row in rows:
        name = row.get('Caption', '').strip()
        cmd  = row.get('Command', '').strip()
        loc  = row.get('Location', '').strip()
        if not name:
            continue
        item_type = 'other'
        loc_lower = loc.lower()
        if 'run' in loc_lower:
            item_type = 'runkey'
        elif 'startup' in loc_lower:
            item_type = 'loginitem'
        output['startup_items'].append({
            'name':    name,
            'type':    item_type,
            'command': cmd,
            'path':    loc,
            'enabled': True,
        })


# ---------------------------------------------------------------------------
# certificates
# ---------------------------------------------------------------------------

def collect_certificates(output):
    stores = ['My', 'Root', 'CA', 'TrustedPublisher']
    for store in stores:
        out = run(
            'powershell -NoProfile -Command "'
            'Get-ChildItem -Path Cert:\\LocalMachine\\{store} -ErrorAction SilentlyContinue'
            ' | ForEach-Object {{'
            ' $_.Subject + \'|\' + $_.Issuer + \'|\' + $_.Thumbprint + \'|\' +'
            ' $_.SerialNumber + \'|\' + $_.NotBefore.ToString(\'o\') + \'|\' +'
            ' $_.NotAfter.ToString(\'o\')'
            ' }}"'.format(store=store)
        )
        for line in out.splitlines():
            parts = line.strip().split('|')
            if len(parts) < 3 or not parts[2].strip():
                continue
            output['certificates'].append({
                'subject':    parts[0].strip(),
                'issuer':     parts[1].strip(),
                'thumbprint': parts[2].strip(),
                'serial':     parts[3].strip() if len(parts) > 3 else '',
                'not_before': parts[4].strip() if len(parts) > 4 else '',
                'not_after':  parts[5].strip() if len(parts) > 5 else '',
                'store':      'LocalMachine/{}'.format(store),
            })


# ---------------------------------------------------------------------------
# logging targets
# ---------------------------------------------------------------------------

def collect_logging_targets(output):
    # Windows Event Forwarding subscriptions
    subs = run('wecutil es 2>nul')
    for sub in subs.splitlines():
        sub = sub.strip()
        if not sub:
            continue
        config = run('wecutil gs "{}" 2>nul'.format(sub))
        for line in config.splitlines():
            if 'SubscriptionManager' in line or 'Address' in line:
                m = re.search(r'Server=([^,;"\s]+)', line)
                if m:
                    dest = m.group(1).strip()
                    output['logging_targets'].append({
                        'type':        'windows-event-forwarding',
                        'destination': dest,
                        'protocol':    'tcp',
                        'enabled':     True,
                    })

    # Registry-based subscription manager
    sm_path = r'SOFTWARE\Policies\Microsoft\Windows\EventLog\EventForwarding\SubscriptionManager'
    vals = reg_values('HKLM', sm_path)
    for v in vals.values():
        m = re.search(r'Server=([^,;"\s]+)', str(v))
        if m:
            dest = m.group(1).strip()
            output['logging_targets'].append({
                'type':        'windows-event-forwarding',
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
        output['_collection_errors'] = errors

    return output


def _run_script(script_content, language):
    """
    Write script_content to a temp file and execute it.

    language — 'shell'/'bat' (cmd.exe), 'powershell', or 'python'.

    Returns a dict: {exit_code, stdout, stderr}.
    """
    import tempfile
    lang = language.lower()
    if lang == 'python':
        # When running as a compiled PyInstaller binary sys.executable
        # points to the agent binary itself, not a Python interpreter.
        if getattr(sys, 'frozen', False):
            import shutil
            _py = shutil.which('python3') or shutil.which('python') or 'python3'
        else:
            _py = sys.executable
        ext, cmd_fn = '.py', lambda p, _e=_py: [_e, p]
    elif lang in ('powershell', 'ps1'):
        ext = '.ps1'
        cmd_fn = lambda p: [  # noqa: E731
            'powershell.exe',
            '-NonInteractive', '-ExecutionPolicy', 'Bypass',
            '-File', p,
        ]
    else:
        # shell / bat / cmd — default
        ext, cmd_fn = '.bat', lambda p: ['cmd.exe', '/c', p]

    fd, path = tempfile.mkstemp(suffix=ext, prefix='isotopeiq_')
    try:
        os.write(fd, script_content.encode('utf-8'))
        os.close(fd)
        with open(os.devnull, 'rb') as devnull:
            proc = subprocess.Popen(
                cmd_fn(path),
                stdin=devnull,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
            )
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


def _make_handler(secret=None):
    """Return an HTTPRequestHandler class for the agent.

    secret — if set, requests must supply this value in the X-Agent-Secret
              header on endpoints other than /health.
    """
    class AgentHandler(BaseHTTPRequestHandler):
        def _allowed(self):
            if not secret:
                return True
            return self.headers.get('X-Agent-Secret') == secret

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

            data = json.dumps(collect(), indent=2).encode('utf-8')
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
    # ---- argument parsing ----
    if HAS_ARGPARSE:
        parser = argparse.ArgumentParser(description='IsotopeIQ Windows Agent')
        parser.add_argument('--serve', action='store_true',
            help='Run as a persistent HTTP server instead of printing to stdout')
        parser.add_argument('--port', type=int, default=DEFAULT_AGENT_PORT,
            help='TCP port to listen on in serve mode (default: %(default)s)')
        parser.add_argument('--secret',
            help='Shared secret; requests must supply this value in the '
                 'X-Agent-Secret header (recommended)')
        args = parser.parse_args()
    else:
        class args(object):
            serve = '--serve' in sys.argv
            port = DEFAULT_AGENT_PORT
            secret = None
        for i, a in enumerate(sys.argv[1:], 1):
            if a == '--port' and i + 1 < len(sys.argv):
                args.port = int(sys.argv[i + 1])
            if a == '--secret' and i + 1 < len(sys.argv):
                args.secret = sys.argv[i + 1]

    if args.serve:
        agent_secret = getattr(args, 'secret', None) or None
        server = ThreadedHTTPServer(('0.0.0.0', args.port), _make_handler(agent_secret))
        sys.stderr.write('IsotopeIQ agent listening on 0.0.0.0:{0}\n'.format(args.port))
        if agent_secret:
            sys.stderr.write('Agent secret authentication enabled.\n')
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    else:
        print(json.dumps(collect(), indent=2))


if __name__ == '__main__':
    main()
