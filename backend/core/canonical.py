import jsonschema

# ── Sub-schemas ───────────────────────────────────────────────────────────────

_DEVICE_SCHEMA = {
    'type': 'object',
    'properties': {
        'hostname':    {'type': 'string'},
        'fqdn':        {'type': 'string'},
        'device_type': {'type': 'string'},
        'vendor':      {'type': 'string'},
        'model':       {'type': 'string'},
    },
    'additionalProperties': False,
}

_HARDWARE_SCHEMA = {
    'type': 'object',
    'properties': {
        'cpu_model':           {'type': 'string'},
        'cpu_cores':           {'type': ['integer', 'null']},
        'memory_gb':           {'type': ['number', 'null']},
        'bios_version':        {'type': 'string'},
        'serial_number':       {'type': 'string'},
        'architecture':        {'type': 'string'},
        # bare-metal | vmware | hyperv | kvm | xen | virtualbox | wsl | other
        'virtualization_type': {'type': 'string'},
    },
    'additionalProperties': False,
}

_OS_SCHEMA = {
    'type': 'object',
    'properties': {
        'name':        {'type': 'string'},
        'version':     {'type': 'string'},
        'build':       {'type': 'string'},
        'kernel':      {'type': 'string'},
        'timezone':    {'type': 'string'},
        'ntp_servers': {'type': 'array', 'items': {'type': 'string'}},
        'ntp_synced':  {'type': ['boolean', 'null']},
    },
    'additionalProperties': False,
}

_NETWORK_INTERFACE_SCHEMA = {
    'type': 'object',
    'properties': {
        'name':         {'type': 'string'},
        'description':  {'type': 'string'},
        'mac':          {'type': 'string'},
        'ipv4':         {'type': 'array', 'items': {'type': 'string'}},
        'ipv6':         {'type': 'array', 'items': {'type': 'string'}},
        'admin_status': {'type': 'string', 'enum': ['up', 'down', 'unknown']},
        'oper_status':  {'type': 'string', 'enum': ['up', 'down', 'unknown']},
        # e.g. "1G", "10G", "100G", "400G"
        'speed':        {'type': 'string'},
        'duplex':       {'type': 'string', 'enum': ['full', 'half', 'auto', 'unknown']},
        'mtu':          {'type': ['integer', 'null']},
        # access | trunk | routed | unknown  (network device port roles)
        'port_mode':    {'type': 'string', 'enum': ['access', 'trunk', 'routed', 'unknown']},
        # VLAN ID for access ports
        'access_vlan':  {'type': ['integer', 'null']},
        # Allowed VLAN range string for trunk ports, e.g. "1-100,200,300-400"
        'trunk_vlans':  {'type': 'string'},
    },
    'additionalProperties': False,
}

_ROUTE_SCHEMA = {
    'type': 'object',
    'properties': {
        'destination': {'type': 'string'},
        'gateway':     {'type': 'string'},
        'interface':   {'type': 'string'},
        'metric':      {'type': ['integer', 'null']},
    },
    'additionalProperties': False,
}

_HOSTS_ENTRY_SCHEMA = {
    'type': 'object',
    'properties': {
        'ip':       {'type': 'string'},
        'hostname': {'type': 'string'},
    },
    'required': ['ip', 'hostname'],
    'additionalProperties': False,
}

_NETWORK_SCHEMA = {
    'type': 'object',
    'properties': {
        'interfaces':      {'type': 'array', 'items': _NETWORK_INTERFACE_SCHEMA},
        'dns_servers':     {'type': 'array', 'items': {'type': 'string'}},
        'default_gateway': {'type': 'string'},
        'routes':          {'type': 'array', 'items': _ROUTE_SCHEMA},
        'hosts_file':      {'type': 'array', 'items': _HOSTS_ENTRY_SCHEMA},
        # Kept for backwards compat; prefer listening_services for detail.
        'open_ports':      {'type': 'array', 'items': {'type': ['integer', 'string']}},
    },
    'additionalProperties': False,
}

_USER_SCHEMA = {
    'type': 'object',
    'properties': {
        'username':          {'type': 'string'},
        'uid':               {'type': 'string'},
        'groups':            {'type': 'array', 'items': {'type': 'string'}},
        'home':              {'type': 'string'},
        'shell':             {'type': 'string'},
        'disabled':          {'type': ['boolean', 'null']},
        'password_last_set': {'type': 'string'},   # ISO-8601 or empty
        'last_login':        {'type': 'string'},   # ISO-8601 or empty
        # Linux: 'sudo'; Windows: 'Administrators' membership etc.
        'sudo_privileges':   {'type': 'string'},
    },
    'additionalProperties': False,
}

_GROUP_SCHEMA = {
    'type': 'object',
    'properties': {
        'group_name': {'type': 'string'},
        'gid':        {'type': 'string'},
        'members':    {'type': 'array', 'items': {'type': 'string'}},
    },
    'additionalProperties': False,
}

# Single unified list covering OS packages (apt/yum/rpm), Windows MSI/Programs,
# package managers (brew/pip/gem/npm/winget/chocolatey), and manual installs.
# Use the `source` field to distinguish origin.
_SOFTWARE_SCHEMA = {
    'type': 'object',
    'properties': {
        'name':         {'type': 'string'},
        'version':      {'type': 'string'},
        'vendor':       {'type': 'string'},
        'install_date': {'type': 'string'},
        'source':       {
            'type': 'string',
            'enum': ['apt', 'deb', 'yum', 'rpm', 'msi', 'brew', 'manual',
                     'pip', 'gem', 'npm', 'winget', 'chocolatey',
                     'apk', 'pacman', 'snap', 'flatpak', 'other'],
        },
    },
    'required': ['name'],
    'additionalProperties': False,
}

_SERVICE_SCHEMA = {
    'type': 'object',
    'properties': {
        'name':    {'type': 'string'},
        'status':  {'type': 'string', 'enum': ['running', 'stopped', 'unknown']},
        'startup': {'type': 'string', 'enum': [
            'enabled', 'disabled', 'manual', 'unknown',
            'enabled-runtime', 'static', 'indirect', 'transient', 'generated', 'masked',
        ]},
    },
    'required': ['name'],
    'additionalProperties': False,
}

_FILESYSTEM_SCHEMA = {
    'type': 'object',
    'properties': {
        'mount':         {'type': 'string'},
        'type':          {'type': 'string'},
        'size_gb':       {'type': ['number', 'null']},
        'free_gb':       {'type': ['number', 'null']},
        # e.g. ["noexec", "nosuid", "nodev", "ro"]
        'mount_options': {'type': 'array', 'items': {'type': 'string'}},
        'suid_files': {
            'type': 'array',
            'items': {'type': 'string'},
            'description': 'Paths of SUID/SGID files on this mount (Linux/macOS).',
        },
    },
    'required': ['mount'],
    'additionalProperties': False,
}

_PASSWORD_POLICY_SCHEMA = {
    'type': 'object',
    'properties': {
        'min_length':          {'type': ['integer', 'null']},
        'max_age_days':        {'type': ['integer', 'null']},
        'warn_age_days':       {'type': ['integer', 'null']},
        'complexity_required': {'type': ['boolean', 'null']},
        'lockout_threshold':   {'type': ['integer', 'null']},
    },
    'additionalProperties': False,
}

_SECURITY_SCHEMA = {
    'type': 'object',
    'properties': {
        'firewall_enabled':      {'type': ['boolean', 'null']},
        'antivirus':             {'type': 'string'},
        'secure_boot':           {'type': ['boolean', 'null']},
        # Linux
        'selinux_mode':          {'type': 'string'},   # enforcing | permissive | disabled | unknown
        'apparmor_status':       {'type': 'string'},   # enabled | disabled | unknown
        'audit_logging_enabled': {'type': ['boolean', 'null']},
        # Windows
        'uac_enabled':           {'type': ['boolean', 'null']},
        'defender_enabled':      {'type': ['boolean', 'null']},
        'password_policy':       _PASSWORD_POLICY_SCHEMA,
    },
    'additionalProperties': False,
}

_SCHEDULED_TASK_SCHEMA = {
    'type': 'object',
    'properties': {
        'name':     {'type': 'string'},
        # cron | systemd-timer | windows-task-scheduler | launchd | at | other
        'type':     {'type': 'string'},
        'command':  {'type': 'string'},
        'schedule': {'type': 'string'},
        'user':     {'type': 'string'},
        'enabled':  {'type': ['boolean', 'null']},
    },
    'required': ['name'],
    'additionalProperties': False,
}

_STARTUP_ITEM_SCHEMA = {
    'type': 'object',
    'properties': {
        'name':    {'type': 'string'},
        # systemd | runkey | loginitem | initd | rclocal | other
        'type':    {'type': 'string'},
        'command': {'type': 'string'},
        'path':    {'type': 'string'},
        'enabled': {'type': ['boolean', 'null']},
    },
    'required': ['name'],
    'additionalProperties': False,
}

_SSH_KEY_SCHEMA = {
    'type': 'object',
    'properties': {
        'username':   {'type': 'string'},
        'key_type':   {'type': 'string'},
        'public_key': {'type': 'string'},
        'comment':    {'type': 'string'},
    },
    'required': ['username', 'public_key'],
    'additionalProperties': False,
}

_KERNEL_MODULE_SCHEMA = {
    'type': 'object',
    'properties': {
        'name':        {'type': 'string'},
        # Linux: lsmod | Windows: driver (SCM) | macOS: kext
        'type':        {'type': 'string'},
        'description': {'type': 'string'},
        'path':        {'type': 'string'},
        'hash':        {'type': 'string'},
        'signed':      {'type': ['boolean', 'null']},
    },
    'required': ['name'],
    'additionalProperties': False,
}

_PCI_DEVICE_SCHEMA = {
    'type': 'object',
    'properties': {
        # PCI slot address, e.g. "00:02.0" or "0000:00:1f.2"
        'slot':    {'type': 'string'},
        # PCI device class string, e.g. "VGA compatible controller"
        'class':   {'type': 'string'},
        # Vendor name or ID string
        'vendor':  {'type': 'string'},
        # Device/product name or ID string
        'device':  {'type': 'string'},
        # Kernel driver in use, e.g. "i915", "ahci"
        'driver':  {'type': 'string'},
        # Subsystem vendor string (optional)
        'subsystem_vendor': {'type': 'string'},
        # Subsystem device string (optional)
        'subsystem_device': {'type': 'string'},
    },
    'required': ['slot'],
    'additionalProperties': False,
}

_STORAGE_DEVICE_SCHEMA = {
    'type': 'object',
    'properties': {
        # Device node or path, e.g. "sda", "nvme0n1", "\\\\.\\PHYSICALDRIVE0"
        'name':      {'type': 'string'},
        # Device category: "disk", "optical", "flash"
        'type':      {'type': 'string'},
        # Model string as reported by the drive/OS
        'model':     {'type': 'string'},
        # Manufacturer/vendor name
        'vendor':    {'type': 'string'},
        # Capacity with unit suffix, e.g. "500G", "1T", "32G"
        'size':      {'type': 'string'},
        # Drive serial number
        'serial':    {'type': 'string'},
        # Transport/bus type: "sata", "nvme", "usb", "ide", "scsi", "ata"
        'interface': {'type': 'string'},
        # True for removable media (USB stick, card reader, optical, etc.)
        'removable': {'type': 'boolean'},
    },
    'required': ['name'],
    'additionalProperties': False,
}

_USB_DEVICE_SCHEMA = {
    'type': 'object',
    'properties': {
        # Bus and device address, e.g. "001/002"
        'bus_id':       {'type': 'string'},
        # 4-hex-digit USB vendor ID, e.g. "8087"
        'vendor_id':    {'type': 'string'},
        # 4-hex-digit USB product ID, e.g. "0024"
        'product_id':   {'type': 'string'},
        # Manufacturer name string, if available
        'manufacturer': {'type': 'string'},
        # Product/device name string
        'product':      {'type': 'string'},
    },
    'required': ['bus_id'],
    'additionalProperties': False,
}

_LISTENING_SERVICE_SCHEMA = {
    'type': 'object',
    'properties': {
        'protocol':      {'type': 'string', 'enum': ['tcp', 'udp', 'tcp6', 'udp6', 'unknown']},
        'local_address': {'type': 'string'},
        'port':          {'type': 'integer'},
        'process_name':  {'type': 'string'},
        'pid':           {'type': ['integer', 'null']},
        'user':          {'type': 'string'},
    },
    'required': ['port'],
    'additionalProperties': False,
}

_CERTIFICATE_SCHEMA = {
    'type': 'object',
    'properties': {
        'subject':    {'type': 'string'},
        'issuer':     {'type': 'string'},
        'thumbprint': {'type': 'string'},
        'serial':     {'type': 'string'},
        'not_before': {'type': 'string'},   # ISO-8601
        'not_after':  {'type': 'string'},   # ISO-8601
        # system | user | machine | java-keystore | other
        'store':      {'type': 'string'},
    },
    'required': ['subject', 'thumbprint'],
    'additionalProperties': False,
}

# ── Optional sections (cross-platform — omit keys that don't apply) ──────────

_FIREWALL_RULE_SCHEMA = {
    'type': 'object',
    'properties': {
        # Chain / policy name: INPUT | OUTPUT | FORWARD | custom name
        'chain':       {'type': 'string'},
        'direction':   {'type': 'string', 'enum': ['in', 'out', 'both', 'unknown']},
        # accept | drop | reject | allow | block | log
        'action':      {'type': 'string'},
        'protocol':    {'type': 'string'},   # tcp | udp | icmp | any | etc.
        'source':      {'type': 'string'},   # CIDR, IP, or "any"
        'destination': {'type': 'string'},
        'port':        {'type': 'string'},   # "22", "80,443", "1024:65535"
        'enabled':     {'type': ['boolean', 'null']},
        'description': {'type': 'string'},
        # iptables | nftables | ufw | windows-firewall | pf | ipfw | other
        'source_tool': {'type': 'string'},
    },
    'additionalProperties': False,
}

_SYSCTL_SCHEMA = {
    'type': 'object',
    'properties': {
        'key':   {'type': 'string'},
        'value': {'type': 'string'},
    },
    'required': ['key'],
    'additionalProperties': False,
}

_SSH_CONFIG_SCHEMA = {
    'type': 'object',
    'properties': {
        'port':                   {'type': ['integer', 'null']},
        'protocol':               {'type': 'string'},
        # yes | no | prohibit-password | forced-commands-only
        'permit_root_login':      {'type': 'string'},
        'password_authentication':{'type': ['boolean', 'null']},
        'pubkey_authentication':  {'type': ['boolean', 'null']},
        'permit_empty_passwords': {'type': ['boolean', 'null']},
        'x11_forwarding':         {'type': ['boolean', 'null']},
        'max_auth_tries':         {'type': ['integer', 'null']},
        'allow_users':            {'type': 'array', 'items': {'type': 'string'}},
        'deny_users':             {'type': 'array', 'items': {'type': 'string'}},
        'allow_groups':           {'type': 'array', 'items': {'type': 'string'}},
        'deny_groups':            {'type': 'array', 'items': {'type': 'string'}},
        'use_pam':                {'type': ['boolean', 'null']},
    },
    'additionalProperties': False,
}

_SNMP_V3_USER_SCHEMA = {
    'type': 'object',
    'properties': {
        'username':       {'type': 'string'},
        # MD5 | SHA | SHA-256 | SHA-512 | none
        'auth_protocol':  {'type': 'string'},
        # DES | AES | AES-256 | none
        'priv_protocol':  {'type': 'string'},
        # noAuthNoPriv | authNoPriv | authPriv
        'security_level': {'type': 'string'},
    },
    'required': ['username'],
    'additionalProperties': False,
}

_SNMP_SCHEMA = {
    'type': 'object',
    'properties': {
        'enabled':      {'type': ['boolean', 'null']},
        # e.g. ["v2c", "v3"] — presence of v1/v2c is a security finding
        'versions':     {'type': 'array', 'items': {'type': 'string'}},
        'communities':  {'type': 'array', 'items': {'type': 'string'}},
        'v3_users':     {'type': 'array', 'items': _SNMP_V3_USER_SCHEMA},
        'trap_targets': {'type': 'array', 'items': {'type': 'string'}},
        'location':     {'type': 'string'},
        'contact':      {'type': 'string'},
    },
    'additionalProperties': False,
}

_SHARE_SCHEMA = {
    'type': 'object',
    'properties': {
        'name':        {'type': 'string'},
        # smb | nfs | afp | ftp | other
        'type':        {'type': 'string'},
        'path':        {'type': 'string'},
        'comment':     {'type': 'string'},
        'permissions': {'type': 'string'},   # free-form, e.g. "everyone:read-write"
        'read_only':   {'type': ['boolean', 'null']},
        'enabled':     {'type': ['boolean', 'null']},
    },
    'required': ['name'],
    'additionalProperties': False,
}

_LOGGING_TARGET_SCHEMA = {
    'type': 'object',
    'properties': {
        # syslog | windows-event-forwarding | splunk-forwarder | elastic-agent | other
        'type':        {'type': 'string'},
        'destination': {'type': 'string'},   # host:port or URL
        'protocol':    {'type': 'string', 'enum': ['udp', 'tcp', 'tls', 'unknown']},
        'facility':    {'type': 'string'},   # local0..local7, daemon, auth, etc.
        'enabled':     {'type': ['boolean', 'null']},
    },
    'required': ['destination'],
    'additionalProperties': False,
}

_VPN_TUNNEL_SCHEMA = {
    'type': 'object',
    'properties': {
        'name':           {'type': 'string'},
        # ipsec | gre | wireguard | openvpn | l2tp | other
        'type':           {'type': 'string'},
        'local_address':  {'type': 'string'},
        'remote_address': {'type': 'string'},
        'status':         {'type': 'string', 'enum': ['up', 'down', 'unknown']},
        'cipher_suite':   {'type': 'string'},
        # pre-shared-key | certificate | eap | other
        'auth_method':    {'type': 'string'},
    },
    'required': ['name'],
    'additionalProperties': False,
}

# ── Network-device-specific sections (optional — absent on servers) ───────────

_VLAN_SCHEMA = {
    'type': 'object',
    'properties': {
        'id':    {'type': 'integer'},
        'name':  {'type': 'string'},
        'state': {'type': 'string', 'enum': ['active', 'suspended', 'unknown']},
    },
    'required': ['id'],
    'additionalProperties': False,
}

_ACL_ENTRY_SCHEMA = {
    'type': 'object',
    'properties': {
        'sequence':    {'type': ['integer', 'null']},
        'action':      {'type': 'string', 'enum': ['permit', 'deny', 'remark', 'unknown']},
        'protocol':    {'type': 'string'},
        'source':      {'type': 'string'},
        'destination': {'type': 'string'},
        'description': {'type': 'string'},
    },
    'additionalProperties': False,
}

_ACL_SCHEMA = {
    'type': 'object',
    'properties': {
        'name':    {'type': 'string'},
        # standard | extended | prefix-list | named | firewall-policy | other
        'type':    {'type': 'string'},
        'entries': {'type': 'array', 'items': _ACL_ENTRY_SCHEMA},
    },
    'required': ['name'],
    'additionalProperties': False,
}

_BGP_NEIGHBOR_SCHEMA = {
    'type': 'object',
    'properties': {
        'address':     {'type': 'string'},
        'remote_asn':  {'type': ['integer', 'string', 'null']},
        'state':       {'type': 'string'},   # Established | Active | Idle | etc.
        'description': {'type': 'string'},
    },
    'required': ['address'],
    'additionalProperties': False,
}

_ROUTING_PROTOCOL_SCHEMA = {
    'type': 'object',
    'properties': {
        # bgp | ospf | eigrp | rip | isis | static | other
        'protocol':  {'type': 'string'},
        # ASN for BGP, process-id for OSPF, etc.
        'instance':  {'type': 'string'},
        'router_id': {'type': 'string'},
        'networks':  {'type': 'array', 'items': {'type': 'string'}},
        'neighbors': {'type': 'array', 'items': _BGP_NEIGHBOR_SCHEMA},
    },
    'required': ['protocol'],
    'additionalProperties': False,
}

_AAA_SCHEMA = {
    'type': 'object',
    'properties': {
        'tacacs_servers':       {'type': 'array', 'items': {'type': 'string'}},
        'radius_servers':       {'type': 'array', 'items': {'type': 'string'}},
        # e.g. "group tacacs+ local"
        'authentication_lists': {'type': 'array', 'items': {
            'type': 'object',
            'properties': {
                'name':    {'type': 'string'},
                'methods': {'type': 'array', 'items': {'type': 'string'}},
            },
            'required': ['name'],
            'additionalProperties': False,
        }},
        'authorization_lists':  {'type': 'array', 'items': {
            'type': 'object',
            'properties': {
                'name':    {'type': 'string'},
                'methods': {'type': 'array', 'items': {'type': 'string'}},
            },
            'required': ['name'],
            'additionalProperties': False,
        }},
        'accounting_lists':     {'type': 'array', 'items': {
            'type': 'object',
            'properties': {
                'name':    {'type': 'string'},
                'methods': {'type': 'array', 'items': {'type': 'string'}},
            },
            'required': ['name'],
            'additionalProperties': False,
        }},
    },
    'additionalProperties': False,
}

_STP_PORT_SCHEMA = {
    'type': 'object',
    'properties': {
        'interface':   {'type': 'string'},
        # root | designated | alternate | backup | disabled | unknown
        'role':        {'type': 'string'},
        # forwarding | blocking | learning | listening | disabled | unknown
        'state':       {'type': 'string'},
        'bpdu_guard':  {'type': ['boolean', 'null']},
        'bpdu_filter': {'type': ['boolean', 'null']},
        'root_guard':  {'type': ['boolean', 'null']},
    },
    'required': ['interface'],
    'additionalProperties': False,
}

_SPANNING_TREE_SCHEMA = {
    'type': 'object',
    'properties': {
        # stp | rstp | mstp | rapid-pvst | pvst | other
        'mode':          {'type': 'string'},
        'root_bridge':   {'type': ['boolean', 'null']},
        'root_priority': {'type': ['integer', 'null']},
        'root_address':  {'type': 'string'},
        'ports':         {'type': 'array', 'items': _STP_PORT_SCHEMA},
    },
    'additionalProperties': False,
}

# ── Top-level schema ──────────────────────────────────────────────────────────
#
# Required keys = the sections listed in SRD §13.1.
# "packages" is the SRD-listed OS-package array (apt/yum/rpm/winget/brew/etc.);
# "installed_software" covers broader app installs.  Both are required so
# parser authors include them explicitly even when empty.
#
# All extended sections (ssh_keys, firewall_rules, vlans, …) are OPTIONAL —
# the SRD states "device types do NOT need to populate every section."
# They will be validated against their schemas only when present.

CANONICAL_SCHEMA = {
    'type': 'object',
    'required': [
        # Core sections — required by SRD §13.1
        'device', 'hardware', 'os', 'network',
        'users', 'groups',
        'packages',
        'services', 'filesystem',
        'security',
    ],
    'properties': {
        # ── SRD-required sections ─────────────────────────────────────────
        'device':             _DEVICE_SCHEMA,
        'hardware':           _HARDWARE_SCHEMA,
        'os':                 _OS_SCHEMA,
        'network':            _NETWORK_SCHEMA,
        'users':              {'type': 'array', 'items': _USER_SCHEMA},
        'groups':             {'type': 'array', 'items': _GROUP_SCHEMA},
        # packages — all software installs: OS packages, registry entries, app bundles, etc.
        'packages':           {'type': 'array', 'items': _SOFTWARE_SCHEMA},
        'services':           {'type': 'array', 'items': _SERVICE_SCHEMA},
        'filesystem':         {'type': 'array', 'items': _FILESYSTEM_SCHEMA},
        'security':           _SECURITY_SCHEMA,
        'custom':             {'type': 'object'},
        # ── Optional extended sections (validated when present) ───────────
        'scheduled_tasks':    {'type': 'array', 'items': _SCHEDULED_TASK_SCHEMA},
        'startup_items':      {'type': 'array', 'items': _STARTUP_ITEM_SCHEMA},
        'ssh_keys':           {'type': 'array', 'items': _SSH_KEY_SCHEMA},
        'kernel_modules':     {'type': 'array', 'items': _KERNEL_MODULE_SCHEMA},
        'pci_devices':        {'type': 'array', 'items': _PCI_DEVICE_SCHEMA},
        'storage_devices':    {'type': 'array', 'items': _STORAGE_DEVICE_SCHEMA},
        'usb_devices':        {'type': 'array', 'items': _USB_DEVICE_SCHEMA},
        'listening_services': {'type': 'array', 'items': _LISTENING_SERVICE_SCHEMA},
        'certificates':       {'type': 'array', 'items': _CERTIFICATE_SCHEMA},
        'firewall_rules':     {'type': 'array', 'items': _FIREWALL_RULE_SCHEMA},
        'sysctl':             {'type': 'array', 'items': _SYSCTL_SCHEMA},
        'ssh_config':         _SSH_CONFIG_SCHEMA,
        'snmp':               _SNMP_SCHEMA,
        'shares':             {'type': 'array', 'items': _SHARE_SCHEMA},
        'logging_targets':    {'type': 'array', 'items': _LOGGING_TARGET_SCHEMA},
        'vpn_tunnels':        {'type': 'array', 'items': _VPN_TUNNEL_SCHEMA},
        # ── Network-device-only optional sections ─────────────────────────
        'vlans':              {'type': 'array', 'items': _VLAN_SCHEMA},
        'acls':               {'type': 'array', 'items': _ACL_SCHEMA},
        'routing_protocols':  {'type': 'array', 'items': _ROUTING_PROTOCOL_SCHEMA},
        'aaa':                _AAA_SCHEMA,
        'spanning_tree':      _SPANNING_TREE_SCHEMA,
    },
    'additionalProperties': False,
}

# ── Empty canonical document (template for parser authors) ───────────────────
# Contains only the keys that are REQUIRED by the SRD.  Optional extended
# sections (ssh_keys, firewall_rules, vlans, …) may be added as needed.

CANONICAL_EMPTY: dict = {
    'device':             {},
    'hardware':           {},
    'os':                 {},
    'network':            {'interfaces': [], 'open_ports': []},
    'users':              [],
    'groups':             [],
    'packages':           [],
    'services':           [],
    'filesystem':         [],
    'security':           {},
    'custom':             {},
}

# ── Volatile field definitions ────────────────────────────────────────────────
#
# Volatile fields are excluded from baseline comparison because they change
# frequently for reasons unrelated to configuration drift (e.g. timestamps,
# resource utilisation, runtime state).  The full parsed data is still stored
# in the baseline and job result for display purposes — only the diff is
# computed against stripped copies.
#
# Structure:
#   top-level section key ->
#       'fields'  : set of scalar fields to drop from the section object, OR
#       'items'   : set of fields to drop from every item when the section is
#                   an array, OR
#       'nested'  : dict mapping an item field name to a further 'items' set
#                   for one level of nesting within array items, OR
#       'exclude_keys': {'key_field': str, 'values': set[str]} — remove entire
#                   items from an array whose `key_field` is in `values`

VOLATILE_FIELDS: dict = {
    # Disk utilisation changes constantly; mount/type/options/suid are static
    'filesystem': {
        'items': {'free_gb'},
    },
    # last_login and password_last_set are timestamps that change on every login
    'users': {
        'items': {'last_login', 'password_last_set'},
    },
    # Runtime service status is volatile; startup (enabled/disabled) is static
    'services': {
        'items': {'status'},
    },
    # PID is volatile; port, process_name, protocol, user are static
    'listening_services': {
        'items': {'pid'},
    },
    # open_ports is a runtime snapshot that changes with connections/services
    'network': {
        'fields': {'open_ports'},
    },
    # NTP sync state is volatile; configured servers are static
    'os': {
        'fields': {'ntp_synced'},
    },
    # Certificate validity window changes on renewal — track expiry separately
    'certificates': {
        'items': {'not_before', 'not_after'},
    },
    # BGP/OSPF neighbour session state is runtime, not configuration
    'routing_protocols': {
        'nested': {
            'neighbors': {'state'},
        },
    },
    # VPN tunnel up/down state is runtime
    'vpn_tunnels': {
        'items': {'status'},
    },
    # VLAN operational state is volatile; id and name are static
    'vlans': {
        'items': {'state'},
    },
    # STP dynamic state: who is root, port roles/states change on topology events
    'spanning_tree': {
        'fields': {'root_bridge', 'root_priority', 'root_address'},
        'nested': {
            'ports': {'role', 'state'},
        },
    },
    # These sysctl entries are kernel runtime counters, not tunable config.
    # They change every few seconds regardless of any admin action and would
    # flood drift events if tracked.
    'sysctl': {
        'exclude_keys': {
            'key_field': 'key',
            'values': {
                # VFS dentry/inode cache hit/miss counters
                'fs.dentry-state',
                'fs.inode-state',
                # Open file descriptor counts (runtime, not a limit)
                'fs.file-nr',
                'fs.inode-nr',
                # Kernel PID counter — increments with every fork
                'kernel.ns_last_pid',
                # Entropy pool levels — change continuously
                'kernel.random.entropy_avail',
                'kernel.random.write_wakeup_threshold',
                # UUIDs — different on every read
                'kernel.random.uuid',
                'kernel.random.boot_id',
                # netfilter connection tracking counters
                'net.netfilter.nf_conntrack_count',
                'net.netfilter.nf_conntrack_expect_count',
                # NFS-related runtime counters (not present on most hosts)
                'fs.nfs.nfs_congestion_kb',
            },
        },
    },
}


def strip_volatile(data: dict, spec: dict | None = None) -> dict:
    """
    Return a deep copy of a canonical document with all volatile fields removed.

    If `spec` is supplied it overrides the built-in VOLATILE_FIELDS dict; pass
    the result of drift.volatile_utils.get_volatile_spec() to use DB-managed
    rules.  Falls back to VOLATILE_FIELDS when spec is None.
    """
    import copy
    data = copy.deepcopy(data)
    effective = spec if spec is not None else VOLATILE_FIELDS

    for section, spec_entry in effective.items():
        if section not in data:
            continue

        # Remove the entire section from comparison
        if spec_entry.get('exclude_section'):
            del data[section]
            continue

        section_data = data[section]

        # Scalar fields on a section object (e.g. os.ntp_synced)
        if 'fields' in spec_entry and isinstance(section_data, dict):
            for field in spec_entry['fields']:
                section_data.pop(field, None)

        # Fields on every item in an array section (e.g. filesystem[*].free_gb)
        if 'items' in spec_entry and isinstance(section_data, list):
            for item in section_data:
                if isinstance(item, dict):
                    for field in spec_entry['items']:
                        item.pop(field, None)

        # Fields within a nested array inside each item
        # (e.g. routing_protocols[*].neighbors[*].state)
        if 'nested' in spec_entry:
            items = section_data if isinstance(section_data, list) else [section_data]
            for item in items:
                if not isinstance(item, dict):
                    continue
                for nested_key, nested_fields in spec_entry['nested'].items():
                    for nested_item in item.get(nested_key, []):
                        if isinstance(nested_item, dict):
                            for field in nested_fields:
                                nested_item.pop(field, None)

        # Exclude entire items whose key field is in a known-volatile set
        # (e.g. sysctl entries that are runtime counters, not config)
        if 'exclude_keys' in spec_entry and isinstance(section_data, list):
            cfg = spec_entry['exclude_keys']
            key_field   = cfg['key_field']
            exclude_set = cfg['values']
            data[section] = [
                item for item in section_data
                if not (isinstance(item, dict) and item.get(key_field) in exclude_set)
            ]

    return data


_validator = jsonschema.Draft7Validator(CANONICAL_SCHEMA)


def validate_canonical(data: dict) -> None:
    """Raise ValueError if data does not conform to the canonical JSON schema."""
    errors = sorted(_validator.iter_errors(data), key=lambda e: list(e.path))
    if errors:
        messages = '; '.join(e.message for e in errors)
        raise ValueError(f'Canonical schema validation failed: {messages}')
