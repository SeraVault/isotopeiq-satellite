#!/usr/bin/env python3
"""Standalone Windows baseline exporter.

Collects a system baseline and writes it as JSON in the schema-1.2.0
format produced by the ansible-baseline collector (see
dguedry-windows.json). No network transport -- output is a local JSON
file only.

Designed to be compiled with PyInstaller (like windows_collector.py).
PowerShell is preferred where it gives richer data, but every section
has a fallback (wmic.exe, winreg, net.exe, schtasks, certutil, secedit)
so the exporter still works on machines without PowerShell.

Usage (elevated prompt recommended for complete results):
    windows_baseline_export.exe [--identifier NAME] [-o FILE]
"""

import argparse
import base64
import json
import os
import re
import socket
import subprocess
import sys
from datetime import datetime, timezone

try:
    import winreg
except ImportError:          # not on Windows (unit testing the parsers)
    winreg = None

try:
    import ctypes
except ImportError:
    ctypes = None

SCHEMA_VERSION = '1.2.0'
COLLECTOR_VERSION = '1.0.0'


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _decode_output(data):
    """
    Decode command output. wmic.exe writes UTF-16LE (with BOM) when its
    stdout is a pipe, so sniff for that before assuming UTF-8.
    """
    if data.startswith(b'\xff\xfe'):
        return data.decode('utf-16', errors='replace')
    if b'\x00' in data[:200]:
        return data.decode('utf-16-le', errors='replace')
    return data.decode('utf-8', errors='replace')


def run(cmd, timeout=60):
    """Run a shell command, return stdout as text. Never raises."""
    proc = None
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, shell=True)
        stdout, _ = proc.communicate(timeout=timeout)
        return _decode_output(stdout)
    except subprocess.TimeoutExpired:
        if proc is not None:
            try:
                proc.kill()
                proc.communicate(timeout=5)
            except Exception:
                pass
        return ''
    except Exception:
        return ''


def run_lines(cmd, timeout=60):
    return [ln for ln in run(cmd, timeout).splitlines() if ln.strip()]


_HAS_POWERSHELL = None


def has_powershell():
    global _HAS_POWERSHELL
    if _HAS_POWERSHELL is None:
        _HAS_POWERSHELL = run(
            'powershell -NoProfile -NonInteractive -Command "Write-Output ok"'
        ).strip() == 'ok'
    return _HAS_POWERSHELL


def ps(script, timeout=120):
    """
    Run a PowerShell script via -EncodedCommand (bypasses cmd.exe quoting).
    Returns stdout, or '' when PowerShell is unavailable or the script fails.
    """
    if not has_powershell():
        return ''
    encoded = base64.b64encode(script.encode('utf-16-le')).decode('ascii')
    return run('powershell -NoProfile -NonInteractive -EncodedCommand '
               + encoded, timeout)


def ps_table(script, n_fields, timeout=120):
    """
    Run a PowerShell script that emits '|||'-prefixed, '|'-joined rows;
    return them as lists of n_fields strings.
    """
    rows = []
    for line in ps(script, timeout).splitlines():
        line = line.strip()
        if not line.startswith('|||'):
            continue
        # maxsplit so a '|' inside the LAST field can't shift columns
        parts = line[3:].split('|', n_fields - 1)
        parts += [''] * (n_fields - len(parts))
        rows.append([p.strip() for p in parts[:n_fields]])
    return rows


def parse_value_blocks(text):
    """
    Parse 'Field=Value' list output (wmic /value, certutil-style blocks)
    into a list of dicts. Blocks are separated by blank lines.
    """
    blocks = []
    current = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            if current:
                blocks.append(current)
                current = {}
            continue
        if '=' in line:
            k, v = line.split('=', 1)
            current[k.strip()] = v.strip()
    if current:
        blocks.append(current)
    return blocks


def wmic_query(alias, cim_class, fields, where=''):
    """
    Query WMI: PowerShell Get-CimInstance first, wmic.exe /value fallback.
    Returns a list of dicts keyed by the requested field names.
    """
    if has_powershell():
        filter_clause = " -Filter '{}'".format(where) if where else ''
        field_expr = ','.join('$_.{}'.format(f) for f in fields)
        script = (
            "Get-CimInstance -ClassName {cls}{flt} | ForEach-Object {{"
            " '|||' + (({fields}) -join '|') }}"
        ).format(cls=cim_class, flt=filter_clause, fields=field_expr)
        rows = ps_table(script, len(fields))
        if rows:
            return [dict(zip(fields, r)) for r in rows]

    # No explicit field list: wmic errors out the ENTIRE query when any
    # requested property does not exist on this Windows version (e.g. XP
    # has no Win32_OperatingSystem.OSArchitecture). 'get /value' returns
    # every available property; missing ones simply come back empty.
    cmd = 'wmic {}{} get /value'.format(
        alias, ' where "{}"'.format(where) if where else '')
    out = []
    for block in parse_value_blocks(run(cmd)):
        row = {f: block.get(f, '') for f in fields}
        if any(row.values()):
            out.append(row)
    return out


def wmi_array(raw):
    """Parse a wmic /value array like {"a","b"} into a list of strings."""
    return re.findall(r'"([^"]*)"', raw)


def reg_open(hive, path, view=0):
    """Open a registry key; view 64/32 forces the corresponding WOW64 view."""
    access = winreg.KEY_READ
    if view == 64:
        access |= winreg.KEY_WOW64_64KEY
    elif view == 32:
        access |= winreg.KEY_WOW64_32KEY
    return winreg.OpenKey(hive, path, 0, access)


def reg_get(hive, path, name, view=0):
    """Read one registry value. Returns None on any error."""
    if winreg is None:
        return None
    try:
        with reg_open(hive, path, view) as key:
            value, _ = winreg.QueryValueEx(key, name)
            return value
    except Exception:
        return None


def reg_values(hive, path, view=0):
    """Return {name: value} for all values under hive\\path."""
    out = {}
    if winreg is None:
        return out
    try:
        with reg_open(hive, path, view) as key:
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


def reg_subkeys(hive, path, view=0):
    """Return subkey names under hive\\path."""
    out = []
    if winreg is None:
        return out
    try:
        with reg_open(hive, path, view) as key:
            i = 0
            while True:
                try:
                    out.append(winreg.EnumKey(key, i))
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


def is_64bit_os():
    return (os.environ.get('PROCESSOR_ARCHITECTURE', '') == 'AMD64'
            or os.environ.get('PROCESSOR_ARCHITEW6432', '') == 'AMD64')


def to_bool(val):
    return str(val).strip().upper() in ('TRUE', '1', 'YES')


# ---------------------------------------------------------------------------
# host / os / hardware
# ---------------------------------------------------------------------------

def collect_host(identifier):
    hostname = os.environ.get('COMPUTERNAME', '') or socket.gethostname()
    fqdn = hostname
    rows = wmic_query('computersystem', 'Win32_ComputerSystem',
                      ['DNSHostName', 'Domain', 'PartOfDomain'])
    if rows:
        cs = rows[0]
        fqdn = cs.get('DNSHostName') or hostname
        if to_bool(cs.get('PartOfDomain')) and cs.get('Domain'):
            fqdn = '{}.{}'.format(fqdn, cs['Domain'])
    return {
        'fqdn': fqdn,
        'hostname': hostname,
        'identifier': identifier or hostname.lower(),
        'os_family': 'windows',
        'platform': 'windows',
    }


def collect_os():
    rows = wmic_query('os', 'Win32_OperatingSystem',
                      ['Caption', 'Version', 'BuildNumber', 'OSArchitecture',
                       'CSDVersion'])
    o = rows[0] if rows else {}
    arch = o.get('OSArchitecture', '')
    if not arch:  # property missing on XP
        arch = '64-bit' if is_64bit_os() else '32-bit'
    return {
        'architecture': arch,
        'build': o.get('BuildNumber', ''),
        'kernel': o.get('Version', ''),
        'name': o.get('Caption', '').strip(),
        'service_pack': o.get('CSDVersion', ''),
        'version': o.get('Version', ''),
    }


def collect_hardware():
    cpu_rows = wmic_query('cpu', 'Win32_Processor', ['Name'])
    cs_rows = wmic_query('computersystem', 'Win32_ComputerSystem',
                         ['Manufacturer', 'Model', 'TotalPhysicalMemory',
                          'NumberOfLogicalProcessors'])
    bios_rows = wmic_query('bios', 'Win32_BIOS', ['SerialNumber'])
    cs = cs_rows[0] if cs_rows else {}

    try:
        cores = int(cs.get('NumberOfLogicalProcessors') or 0)
    except ValueError:
        cores = 0
    if not cores:
        try:
            cores = int(os.environ.get('NUMBER_OF_PROCESSORS', '0'))
        except ValueError:
            cores = None

    try:
        memory_mb = int(round(int(cs.get('TotalPhysicalMemory') or 0)
                              / (1024.0 * 1024.0))) or None
    except ValueError:
        memory_mb = None

    disks = []
    for d in wmic_query('diskdrive', 'Win32_DiskDrive',
                        ['DeviceID', 'Model', 'SerialNumber', 'Size',
                         'MediaType']):
        media = d.get('MediaType', '')
        if 'Fixed' in media:
            dtype = 'fixed'
        elif 'Removable' in media:
            dtype = 'removable'
        elif 'External' in media:
            dtype = 'external'
        else:
            dtype = 'unknown'
        try:
            size_gb = int(round(int(d.get('Size') or 0) / (1024.0 ** 3)))
        except ValueError:
            size_gb = 0
        disks.append({
            'model': d.get('Model', '').strip(),
            'name': re.sub(r'^\\\\\.\\', '', d.get('DeviceID', '')),
            'serial_number': d.get('SerialNumber', '').strip(),
            'size_gb': size_gb,
            'type': dtype,
        })
    disks.sort(key=lambda d: d['name'])

    return {
        'cpu': (cpu_rows[0].get('Name', '').strip() if cpu_rows else ''),
        'cpu_cores': cores,
        'disks': disks,
        'manufacturer': cs.get('Manufacturer', ''),
        'memory_mb': memory_mb,
        'model': cs.get('Model', ''),
        'serial_number': (bios_rows[0].get('SerialNumber', '').strip()
                          if bios_rows else ''),
    }


# ---------------------------------------------------------------------------
# network
# ---------------------------------------------------------------------------

def _iface(name, mac, dhcp, ipv4, ipv6):
    return {
        'dhcp': dhcp,
        'ipv4_addresses': [a for a in ipv4 if not a.startswith('169.254.')],
        'ipv6_addresses': [a for a in ipv6
                           if not a.lower().startswith('fe80')],
        'mac': mac.replace('-', ':').upper(),
        'name': name,
        'type': 'ether',
    }


def collect_network():
    interfaces = []
    dns = []

    if has_powershell():
        script = (
            "foreach ($a in (Get-NetAdapter | Where-Object {$_.Status -eq"
            " 'Up'})) {"
            " $i = $a.ifIndex;"
            " $v4 = @(Get-NetIPAddress -InterfaceIndex $i -AddressFamily"
            " IPv4 -ErrorAction SilentlyContinue |"
            " ForEach-Object {$_.IPAddress});"
            " $v6 = @(Get-NetIPAddress -InterfaceIndex $i -AddressFamily"
            " IPv6 -ErrorAction SilentlyContinue |"
            " ForEach-Object {$_.IPAddress});"
            " $if4 = @(Get-NetIPInterface -InterfaceIndex $i -AddressFamily"
            " IPv4 -ErrorAction SilentlyContinue)[0];"
            " $d = @(Get-DnsClientServerAddress -InterfaceIndex $i"
            " -AddressFamily IPv4 -ErrorAction SilentlyContinue |"
            " ForEach-Object {$_.ServerAddresses});"
            " '|||' + ($a.InterfaceDescription, $a.MacAddress,"
            " [string]$if4.Dhcp, ($v4 -join ' '), ($v6 -join ' '),"
            " ($d -join ' ') -join '|') }"
        )
        for row in ps_table(script, 6):
            name, mac, dhcp_s, v4, v6, d = row
            dhcp = None
            if dhcp_s in ('Enabled', 'Disabled'):
                dhcp = dhcp_s == 'Enabled'
            interfaces.append(_iface(name, mac, dhcp, v4.split(), v6.split()))
            for server in d.split():
                if server and server not in dns:
                    dns.append(server)

    if not interfaces:
        # wmic fallback (Windows XP/7, no PowerShell)
        for block in parse_value_blocks(
                run('wmic nicconfig where "IPEnabled=TRUE" get Description,'
                    'MACAddress,DHCPEnabled,IPAddress,DNSServerSearchOrder'
                    ' /value')):
            addrs = wmi_array(block.get('IPAddress', ''))
            ipv4 = [a for a in addrs if ':' not in a]
            ipv6 = [a for a in addrs if ':' in a]
            interfaces.append(_iface(
                block.get('Description', ''),
                block.get('MACAddress', ''),
                to_bool(block.get('DHCPEnabled', '')),
                ipv4, ipv6))
            for server in wmi_array(block.get('DNSServerSearchOrder', '')):
                if server and server not in dns:
                    dns.append(server)

    interfaces.sort(key=lambda i: i['name'])
    return {'dns_servers': dns, 'interfaces': interfaces}


# ---------------------------------------------------------------------------
# users / groups
# ---------------------------------------------------------------------------

def net_localgroup_members(group_name):
    """Member names of a local group via 'net localgroup' (universal)."""
    members = []
    in_list = False
    for line in run('net localgroup "{}"'.format(group_name)).splitlines():
        line = line.rstrip()
        if line.startswith('---'):
            in_list = True
            continue
        if not in_list or not line.strip():
            continue
        if 'The command completed' in line or line.startswith('*'):
            if line.startswith('*'):        # nested group marker
                members.append(line.strip().lstrip('*').split('\\')[-1])
            continue
        members.append(line.strip().split('\\')[-1])
    return sorted(m for m in members if m)


def collect_users():
    admins = set(net_localgroup_members('Administrators'))
    users = []

    rows = []
    if has_powershell():
        # free-text Description goes last so ps_table's maxsplit protects it
        rows = ps_table(
            "Get-LocalUser | ForEach-Object { '|||' + ($_.Name,"
            " $_.SID.Value, $_.Enabled, $_.Description -join '|') }", 4)
    if rows:
        for name, sid, enabled, desc in rows:
            users.append({
                'admin': name in admins,
                'description': desc,
                'enabled': enabled == 'True',
                'home': '',
                'id': sid,
                'name': name,
                'shell': '',
            })
    else:
        for u in wmic_query('useraccount', 'Win32_UserAccount',
                            ['Name', 'SID', 'Description', 'Disabled'],
                            where='LocalAccount=TRUE'):
            if not u.get('Name'):
                continue
            users.append({
                'admin': u['Name'] in admins,
                'description': u.get('Description', ''),
                'enabled': not to_bool(u.get('Disabled', '')),
                'home': '',
                'id': u.get('SID', ''),
                'name': u['Name'],
                'shell': '',
            })

    return sorted(users, key=lambda u: u['name'])


def collect_groups():
    groups = []
    for g in wmic_query('group', 'Win32_Group', ['Name', 'SID'],
                        where='LocalAccount=TRUE'):
        if not g.get('Name'):
            continue
        groups.append({
            'id': g.get('SID', ''),
            'members': net_localgroup_members(g['Name']),
            'name': g['Name'],
        })
    return sorted(groups, key=lambda g: g['name'])


# ---------------------------------------------------------------------------
# applications / patches
# ---------------------------------------------------------------------------

_UNINSTALL = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall'


def collect_applications():
    apps = []
    seen = set()

    hives = [(winreg.HKEY_LOCAL_MACHINE, 64, ''),
             (winreg.HKEY_CURRENT_USER, 0, '')]
    if is_64bit_os():
        hives.append((winreg.HKEY_LOCAL_MACHINE, 32, 'x86'))

    for hive, view, arch in hives:
        for sub in reg_subkeys(hive, _UNINSTALL, view):
            vals = reg_values(hive, _UNINSTALL + '\\' + sub, view)
            name = vals.get('DisplayName')
            if not name or vals.get('SystemComponent') == 1:
                continue
            key = ('registry', name, str(vals.get('DisplayVersion', '')))
            if key in seen:
                continue
            seen.add(key)
            apps.append({
                'architecture': arch,
                'name': str(name),
                'source': 'registry',
                'vendor': str(vals.get('Publisher', '') or ''),
                'version': str(vals.get('DisplayVersion', '') or ''),
            })

    # Store apps require PowerShell; machines without it predate the Store.
    appx_cmd = ("{} | ForEach-Object {{ '|||' + ($_.Name, $_.Version,"
                " $_.Architecture, $_.Publisher -join '|') }}")
    rows = []
    if is_admin():
        rows = ps_table(appx_cmd.format('Get-AppxPackage -AllUsers'), 4)
    if not rows:
        rows = ps_table(appx_cmd.format('Get-AppxPackage'), 4)
    for name, version, arch, publisher in rows:
        key = ('store', name, version)
        if key in seen or not name:
            continue
        seen.add(key)
        apps.append({
            'architecture': arch,
            'name': name,
            'source': 'store',
            'vendor': publisher,
            'version': version,
        })

    return sorted(apps, key=lambda a: (a['name'], a['version']))


def collect_patches():
    patches = []
    for p in wmic_query('qfe', 'Win32_QuickFixEngineering',
                        ['HotFixID', 'Description']):
        if p.get('HotFixID'):
            patches.append({
                'description': p.get('Description', ''),
                'id': p['HotFixID'],
            })
    return sorted(patches, key=lambda p: p['id'])


# ---------------------------------------------------------------------------
# services
# ---------------------------------------------------------------------------

def collect_services():
    services = []
    for s in wmic_query('service', 'Win32_Service',
                        ['Name', 'DisplayName', 'PathName', 'StartMode',
                         'StartName']):
        if not s.get('Name'):
            continue
        services.append({
            'display_name': s.get('DisplayName', ''),
            'name': s['Name'],
            'path': s.get('PathName', ''),
            'run_as': s.get('StartName', ''),
            'source': 'windows_service',
            'startup': s.get('StartMode', '').lower(),
        })
    return sorted(services, key=lambda s: s['name'])


# ---------------------------------------------------------------------------
# startup items
# ---------------------------------------------------------------------------

_RUN_KEY = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Run'
_RUNONCE_KEY = r'SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce'


def _parse_schtasks_csv(text):
    """Parse `schtasks /query /v /fo CSV` output into a list of dicts."""
    import csv
    from io import StringIO
    rows = []
    header = None
    for parsed in csv.reader(StringIO(text)):
        if not parsed:
            continue
        if 'TaskName' in parsed:      # (repeated) header row
            header = parsed
            continue
        if header and len(parsed) >= len(header):
            rows.append(dict(zip(header, parsed)))
    return rows


def collect_startup_items():
    items = []
    username = os.environ.get('USERNAME', 'user')

    reg_sources = [
        (winreg.HKEY_LOCAL_MACHINE, 64, _RUN_KEY,
         'HKLM\\' + _RUN_KEY, 'machine'),
        (winreg.HKEY_LOCAL_MACHINE, 64, _RUNONCE_KEY,
         'HKLM\\' + _RUNONCE_KEY, 'machine'),
        (winreg.HKEY_CURRENT_USER, 0, _RUN_KEY,
         'HKCU\\' + _RUN_KEY, username),
        (winreg.HKEY_CURRENT_USER, 0, _RUNONCE_KEY,
         'HKCU\\' + _RUNONCE_KEY, username),
    ]
    if is_64bit_os():
        reg_sources.append(
            (winreg.HKEY_LOCAL_MACHINE, 32, _RUN_KEY,
             'HKLM\\SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\'
             'CurrentVersion\\Run', 'machine'))

    for hive, view, path, location, scope in reg_sources:
        for name, value in reg_values(hive, path, view).items():
            items.append({
                'command': str(value),
                'location': location,
                'name': str(name),
                'scope': scope,
            })

    for task in _parse_schtasks_csv(run('schtasks /query /v /fo CSV', 120)):
        schedule = task.get('Schedule Type', '') or task.get('Schedule', '')
        if not re.search(r'logon|start', schedule, re.IGNORECASE):
            continue
        command = (task.get('Task To Run', '') or '').strip()
        if not command or command == 'COM handler':
            continue
        items.append({
            'command': command,
            'location': 'schtasks:',
            'name': task.get('TaskName', '').split('\\')[-1],
            'scope': task.get('Run As User', ''),
        })

    return sorted(items, key=lambda i: (i['location'], i['name']))


# ---------------------------------------------------------------------------
# firewall rules (registry FirewallRules store -- no PowerShell needed)
# ---------------------------------------------------------------------------

_FW_KEY = (r'SYSTEM\CurrentControlSet\Services\SharedAccess'
           r'\Parameters\FirewallPolicy\FirewallRules')

_PROTOCOL_NAMES = {'1': 'icmpv4', '2': 'igmp', '6': 'tcp', '17': 'udp',
                   '41': 'ipv6', '47': 'gre', '58': 'icmpv6'}


def parse_firewall_rule(rule_id, raw):
    """Parse one registry FirewallRules value into a schema rule dict."""
    rule = {
        'action': '',
        'application': '',
        'direction': '',
        'enabled': False,
        'id': rule_id,
        'local_ports': [],
        'name': '',
        'profiles': [],
        'protocol': '',
        'raw': raw,
        'remote_ports': [],
        'service': '',
        'source': 'windows_firewall',
    }
    for token in raw.split('|'):
        if '=' not in token:
            continue
        key, value = token.split('=', 1)
        if key == 'Action':
            rule['action'] = value.lower()
        elif key == 'Active':
            rule['enabled'] = value.upper() == 'TRUE'
        elif key == 'Dir':
            rule['direction'] = value.lower()
        elif key == 'Protocol':
            rule['protocol'] = _PROTOCOL_NAMES.get(value, value)
        elif key == 'Profile':
            rule['profiles'].append(value.lower())
        elif re.match(r'^LPort(2_\d+)?$', key):
            rule['local_ports'].append(value)
        elif re.match(r'^RPort(2_\d+)?$', key):
            rule['remote_ports'].append(value)
        elif key == 'App':
            rule['application'] = value
        elif key == 'Svc':
            rule['service'] = value
        elif key == 'Name':
            rule['name'] = value
    rule['local_ports'].sort()
    rule['remote_ports'].sort()
    rule['profiles'].sort()
    return rule


def collect_firewall_rules():
    rules = []
    for name, value in reg_values(winreg.HKEY_LOCAL_MACHINE,
                                  _FW_KEY, 64).items():
        if isinstance(value, str) and value.startswith('v'):
            rules.append(parse_firewall_rule(name, value))
    return sorted(rules, key=lambda r: r['id'])


# ---------------------------------------------------------------------------
# security settings
# ---------------------------------------------------------------------------

def _add_reg_settings(settings, path, mapping, prefix, view=64):
    vals = reg_values(winreg.HKEY_LOCAL_MACHINE, path, view)
    for reg_name, key_name in mapping.items():
        if reg_name in vals and vals[reg_name] is not None:
            settings['{}.{}'.format(prefix, key_name)] = str(vals[reg_name])


def _collect_antivirus(settings):
    products = []
    for namespace in ('SecurityCenter2', 'SecurityCenter'):
        out = run(r'wmic /namespace:\\root\{} path AntiVirusProduct get '
                  r'displayName /value'.format(namespace))
        products = [b['displayName'] for b in parse_value_blocks(out)
                    if b.get('displayName')]
        if not products and has_powershell():
            rows = ps_table(
                "Get-CimInstance -Namespace root/{} -ClassName"
                " AntiVirusProduct -ErrorAction SilentlyContinue |"
                " ForEach-Object {{ '|||' + $_.displayName }}"
                .format(namespace), 1)
            products = [r[0] for r in rows if r[0]]
        if products:
            break
    if products:
        settings['antivirus.products'] = ', '.join(products)


def _collect_audit_policy(settings):
    if not is_admin():
        return
    lines = run('auditpol /get /category:* /r').splitlines()
    header = None
    import csv
    for parsed in csv.reader(lines):
        if not parsed:
            continue
        if header is None:
            header = parsed
            continue
        row = dict(zip(header, parsed))
        sub = row.get('Subcategory', '').strip()
        if sub:
            settings['audit.' + sub] = row.get('Inclusion Setting', '')


_CERT_STORES = (('root', 'Root'), ('ca', 'CA'),
                ('trustedpublisher', 'TrustedPublisher'))


def _collect_certificates(settings):
    got_any = False
    if has_powershell():
        for prefix, store in _CERT_STORES:
            rows = ps_table(
                "Get-ChildItem Cert:\\LocalMachine\\{} -ErrorAction"
                " SilentlyContinue | ForEach-Object {{ '|||' +"
                " ($_.Thumbprint, $_.NotAfter.ToString('yyyy-MM-dd'),"
                " $_.Subject -join '|') }}".format(store), 3)
            for thumb, expires, subject in rows:
                if thumb:
                    got_any = True
                    settings['cert.{}.{}'.format(prefix, thumb.lower())] = \
                        '{} (expires {})'.format(subject, expires)
    if not got_any:
        for prefix, store in _CERT_STORES:
            _certutil_store(settings, prefix, store)


def _certutil_store(settings, prefix, store):
    """certutil fallback for machines without PowerShell."""
    subject, not_after, thumb = '', '', ''

    def flush():
        if thumb and subject:
            expires = _parse_us_date(not_after)
            value = subject
            if expires:
                value += ' (expires {})'.format(expires)
            settings['cert.{}.{}'.format(prefix, thumb)] = value
    for line in run('certutil -store {}'.format(store), 120).splitlines():
        stripped = line.strip()
        if stripped.startswith('=====') and 'Certificate' in stripped:
            flush()
            subject, not_after, thumb = '', '', ''
        elif stripped.startswith('Subject:'):
            subject = stripped[len('Subject:'):].strip()
        elif stripped.startswith('NotAfter:'):
            not_after = stripped[len('NotAfter:'):].strip()
        elif stripped.lower().startswith('cert hash(sha1):'):
            thumb = stripped.split(':', 1)[1].strip().replace(' ', '').lower()
    flush()


def _parse_us_date(text):
    """Best-effort m/d/y -> yyyy-MM-dd (certutil dates are locale format)."""
    m = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', text)
    if not m:
        return ''
    return '{:04d}-{:02d}-{:02d}'.format(
        int(m.group(3)), int(m.group(1)), int(m.group(2)))


def _collect_account_policy(settings):
    if not is_admin():
        return
    import tempfile
    cfg = os.path.join(tempfile.gettempdir(),
                       'secpol_{}.cfg'.format(os.getpid()))
    run('secedit /export /cfg "{}" /areas SECURITYPOLICY /quiet'.format(cfg),
        120)
    try:
        with open(cfg, 'r', encoding='utf-16', errors='replace') as f:
            content = f.read()
    except Exception:
        try:
            with open(cfg, 'r', errors='replace') as f:
                content = f.read()
        except Exception:
            content = ''
    finally:
        try:
            os.remove(cfg)
        except OSError:
            pass
    in_section = False
    for line in content.splitlines():
        line = line.strip()
        if line.startswith('['):
            in_section = line == '[System Access]'
            continue
        if in_section and '=' in line:
            key, value = line.split('=', 1)
            settings['policy.' + key.strip()] = value.strip().strip('"')


def collect_security():
    settings = {}

    _collect_antivirus(settings)
    _collect_audit_policy(settings)
    _collect_certificates(settings)

    fw_base = (r'SYSTEM\CurrentControlSet\Services\SharedAccess'
               r'\Parameters\FirewallPolicy')
    for profile in ('DomainProfile', 'PublicProfile', 'StandardProfile'):
        enabled = reg_get(winreg.HKEY_LOCAL_MACHINE,
                          fw_base + '\\' + profile, 'EnableFirewall', 64)
        if enabled is not None:
            settings['firewall.{}.enabled'.format(profile.lower())] = \
                str(enabled)

    _add_reg_settings(settings, r'SYSTEM\CurrentControlSet\Control\Lsa', {
        'EveryoneIncludesAnonymous': 'everyone_includes_anonymous',
        'LimitBlankPasswordUse': 'limit_blank_password_use',
        'NoLMHash': 'no_lm_hash',
        'RestrictAnonymous': 'restrict_anonymous',
        'RestrictAnonymousSAM': 'restrict_anonymous_sam',
    }, 'lsa')

    _collect_account_policy(settings)

    _add_reg_settings(
        settings, r'SYSTEM\CurrentControlSet\Control\Terminal Server',
        {'fDenyTSConnections': 'deny_connections'}, 'rdp')
    _add_reg_settings(
        settings,
        r'SYSTEM\CurrentControlSet\Control\Terminal Server'
        r'\WinStations\RDP-Tcp',
        {'UserAuthentication': 'nla_required'}, 'rdp')

    secure_boot = reg_get(winreg.HKEY_LOCAL_MACHINE,
                          r'SYSTEM\CurrentControlSet\Control\SecureBoot'
                          r'\State', 'UEFISecureBootEnabled', 64)
    if secure_boot is not None:
        settings['secure_boot.enabled'] = \
            'true' if secure_boot == 1 else 'false'

    _add_reg_settings(
        settings, r'SYSTEM\CurrentControlSet\Services\W32Time\Parameters',
        {'NtpServer': 'ntp_servers', 'Type': 'ntp_type'}, 'time')
    tz = run('tzutil /g').strip()
    if not tz:
        tz = str(reg_get(
            winreg.HKEY_LOCAL_MACHINE,
            r'SYSTEM\CurrentControlSet\Control\TimeZoneInformation',
            'TimeZoneKeyName', 64) or
            reg_get(
                winreg.HKEY_LOCAL_MACHINE,
                r'SYSTEM\CurrentControlSet\Control\TimeZoneInformation',
                'StandardName', 64) or '')
    if tz:
        settings['time.timezone'] = tz

    _add_reg_settings(
        settings,
        r'SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System', {
            'ConsentPromptBehaviorAdmin': 'consent_prompt_admin',
            'ConsentPromptBehaviorUser': 'consent_prompt_user',
            'EnableInstallerDetection': 'enable_installer_detection',
            'EnableLUA': 'enable_lua',
            'PromptOnSecureDesktop': 'prompt_on_secure_desktop',
        }, 'uac')

    return {
        'file_integrity': [],
        'settings': [{'key': k, 'value': v}
                     for k, v in sorted(settings.items())],
    }


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def collect(identifier, collector, method):
    return {
        'applications': collect_applications(),
        'collection': {
            'collected_at': datetime.now(
                timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
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
                        help='device identifier (default: hostname, lowered)')
    parser.add_argument('-o', '--output', default='',
                        help='output file (default: <identifier>.json)')
    parser.add_argument('--collector', default='baseline-export',
                        help='collection.collector value')
    parser.add_argument('--method', default='local',
                        help='collection.method value')
    args = parser.parse_args()

    if not is_admin():
        sys.stderr.write('warning: not elevated -- audit policy, account '
                         'policy and all-user store apps will be '
                         'incomplete\n')
    if not has_powershell():
        sys.stderr.write('note: PowerShell unavailable -- using wmic/'
                         'certutil fallbacks (no store apps)\n')

    data = collect(args.identifier, args.collector, args.method)
    out_path = args.output or '{}.json'.format(data['host']['identifier'])
    with open(out_path, 'w') as f:
        f.write(json.dumps(data, indent=4, sort_keys=True) + '\n')
    sys.stderr.write('wrote {}\n'.format(os.path.abspath(out_path)))


if __name__ == '__main__':
    main()
