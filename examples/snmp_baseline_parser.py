# SNMP Baseline Parser
# Parses output from snmp_baseline_collector.sh into the canonical schema.
#
# `result` — raw string output from the collector (snmpwalk -Oqn lines)
# `output` — canonical dict to populate (pre-filled with empty structure)
#
# All snmpwalk output uses numeric OIDs and stripped values (-Oqn flag),
# producing lines of the form:
#   .1.3.6.1.2.1.1.5.0 "router-core-01"
#   .1.3.6.1.2.1.2.2.1.2.1 "GigabitEthernet0/0"

import re

SEP = "---ISOTOPEIQ---"

# ── Split raw output into named sections ──────────────────────────────────────

sections: dict = {}
current = None
buf: list = []

for line in result.splitlines():
    if line.startswith(SEP + "[") and line.endswith("]"):
        if current is not None:
            sections[current] = "\n".join(buf).strip()
        current = line[len(SEP) + 1:-1]
        buf = []
    elif current is not None:
        buf.append(line)

if current and current != "END":
    sections[current] = "\n".join(buf).strip()


def sec_lines(section: str) -> list:
    return [l for l in sections.get(section, "").splitlines() if l.strip()]


# ── Core SNMP helpers ─────────────────────────────────────────────────────────

def _snmp_val(raw: str) -> str:
    """Strip SNMP type prefixes from a raw value token.

    Examples:
        STRING: "foo bar"   -> foo bar
        INTEGER: 3          -> 3
        Hex-STRING: 08 00 2b -> 08002b
        OID: .1.3.6.1...    -> .1.3.6.1...
        Timeticks: (123456) 0:00:00  -> 123456
        ""                  -> ""
    """
    raw = raw.strip()
    if not raw:
        return ""

    # Timeticks: (centiseconds) human-readable
    m = re.match(r'Timeticks:\s*\((\d+)\)', raw)
    if m:
        return m.group(1)

    # Known prefix: TYPE: value
    m = re.match(r'^(\w[\w-]*):\s*(.*)', raw, re.DOTALL)
    if m:
        prefix, value = m.group(1), m.group(2).strip()
        if prefix in ("STRING", "IpAddress", "NetworkAddress"):
            # Strip surrounding quotes if present
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            return value
        if prefix == "INTEGER":
            return value.split()[0] if value else ""
        if prefix == "Hex-STRING":
            # Remove spaces to produce a compact hex string
            return value.replace(" ", "")
        if prefix == "OID":
            return value
        if prefix == "Gauge32":
            return value.split()[0] if value else ""
        if prefix == "Counter32":
            return value.split()[0] if value else ""
        if prefix == "Counter64":
            return value.split()[0] if value else ""
        # DateAndTime OCTET-STRING comes as Hex-STRING in snmpwalk -Oqn output,
        # but some agents emit it as STRING.  Return as-is; caller parses.
        return value

    # No recognised prefix — return as-is (already stripped)
    return raw


def _parse_oid_line(line: str):
    """Return (oid_str, value_str) from a single snmpwalk -Oqn output line.

    The format is:  .OID.INDEX  VALUE
    where VALUE may contain spaces (e.g. STRING with spaces).
    Returns (None, None) if the line is not parseable.
    """
    line = line.strip()
    if not line or not line.startswith("."):
        return None, None
    # Split on first whitespace
    parts = line.split(None, 1)
    if len(parts) < 2:
        return parts[0], ""
    return parts[0], parts[1]


def _parse_snmp_table(raw: str, base_oid: str) -> dict:
    """Group OID=value lines into a table keyed by row index.

    For an OID  .base_oid.column.row_index  the result is:
        { row_index : { column : cleaned_value } }

    base_oid should be the common prefix including the table entry node,
    e.g. ".1.3.6.1.2.1.2.2.1" for ifEntry.  Both dotted-prefix and
    non-dotted forms are accepted.

    Returns dict of { row_index_str : { column_str : value_str } }
    """
    if not base_oid.startswith("."):
        base_oid = "." + base_oid
    # Ensure trailing dot for prefix matching
    prefix = base_oid.rstrip(".") + "."
    table: dict = {}
    for line in raw.splitlines():
        oid, raw_val = _parse_oid_line(line)
        if oid is None:
            continue
        if not oid.startswith(prefix):
            continue
        remainder = oid[len(prefix):]
        # remainder is "column.row_index" — row_index may itself contain dots
        # (e.g. IP-indexed rows like ipAddrTable).
        dot_pos = remainder.find(".")
        if dot_pos < 0:
            continue
        col = remainder[:dot_pos]
        row = remainder[dot_pos + 1:]
        value = _snmp_val(raw_val)
        table.setdefault(row, {})[col] = value
    return table


def _parse_scalar(raw: str, oid: str) -> str:
    """Extract a single scalar value from a raw section string."""
    if not oid.startswith("."):
        oid = "." + oid
    for line in raw.splitlines():
        o, v = _parse_oid_line(line)
        if o == oid:
            return _snmp_val(v)
    return ""


def _hex_mac_to_str(hex_str: str) -> str:
    """Convert a compact hex string 'aabbccddeeff' to 'aabbccddeeff'."""
    return hex_str.lower().replace(":", "").replace(" ", "")


def _bps_to_speed_label(bps_str: str) -> str:
    """Convert bps integer string to '1G', '10G', '100M' etc."""
    try:
        bps = int(bps_str)
    except (ValueError, TypeError):
        return ""
    if bps >= 400_000_000_000:
        return "400G"
    if bps >= 100_000_000_000:
        return "100G"
    if bps >= 40_000_000_000:
        return "40G"
    if bps >= 25_000_000_000:
        return "25G"
    if bps >= 10_000_000_000:
        return "10G"
    if bps >= 1_000_000_000:
        return "1G"
    if bps >= 100_000_000:
        return "100M"
    if bps >= 10_000_000:
        return "10M"
    if bps >= 1_000_000:
        return "1M"
    if bps > 0:
        return f"{bps}bps"
    return ""


def _highspeed_to_label(mbps_str: str) -> str:
    """Convert ifHighSpeed (Mbps) integer string to speed label."""
    try:
        mbps = int(mbps_str)
    except (ValueError, TypeError):
        return ""
    if mbps == 0:
        return ""
    return _bps_to_speed_label(str(mbps * 1_000_000))


def _parse_dateantime(hex_str: str) -> str:
    """Parse an SNMP DateAndTime OCTET-STRING hex value to ISO-8601 date.

    DateAndTime is 8 or 11 bytes:
      year(2) month(1) day(1) hour(1) min(1) sec(1) decisec(1)
      [direction(1) utc_hour(1) utc_min(1)]
    The hex string from snmpwalk has no separators, e.g. "07e6030e10..."
    Returns "YYYY-MM-DD" or "" on parse failure.
    """
    h = hex_str.replace(" ", "").replace(":", "")
    if len(h) < 16:  # need at least 8 bytes = 16 hex chars
        return ""
    try:
        year = int(h[0:4], 16)
        month = int(h[4:6], 16)
        day = int(h[6:8], 16)
        return f"{year:04d}-{month:02d}-{day:02d}"
    except (ValueError, IndexError):
        return ""


# ── Vendor detection ──────────────────────────────────────────────────────────

_VENDOR_OID_MAP = [
    (".1.3.6.1.4.1.9.",     "Cisco"),
    (".1.3.6.1.4.1.2636.",  "Juniper"),
    (".1.3.6.1.4.1.25506.", "HP/Aruba"),
    (".1.3.6.1.4.1.11.",    "HP"),
    (".1.3.6.1.4.1.6527.",  "Alcatel-Lucent"),
    (".1.3.6.1.4.1.2.",     "IBM"),
    (".1.3.6.1.4.1.4526.",  "Netgear"),
    (".1.3.6.1.4.1.890.",   "Zyxel"),
]

_DESCR_VENDOR_PATTERNS = [
    (r"Cisco IOS",  "Cisco"),
    (r"IOS-XE",     "Cisco"),
    (r"IOS XR",     "Cisco"),
    (r"NX-OS",      "Cisco"),
    (r"Junos",      "Juniper"),
    (r"\bEOS\b",    "Arista"),
    (r"FortiOS",    "Fortinet"),
    (r"PAN-OS",     "Palo Alto"),
    (r"Aruba",      "HP/Aruba"),
    (r"ExtremeXOS", "Extreme"),
    (r"FTOS",       "Dell"),
]

_DESCR_OS_PATTERNS = [
    (r"Cisco IOS[- ]XE\s+Software.*?Version\s+([\d.()A-Za-z]+)", "IOS-XE"),
    (r"Cisco IOS XR Software.*?Version\s+([\d.]+)",               "IOS-XR"),
    (r"Cisco IOS Software.*?Version\s+([\d.()A-Za-z]+)",          "IOS"),
    (r"NX-OS.*?version\s+([\d.()\w]+)",                           "NX-OS"),
    (r"Juniper Networks.*?JUNOS\s+([\d.A-Z\-]+)",                 "Junos"),
    (r"Arista Networks EOS.*?version\s+([\d.]+)",                 "EOS"),
    (r"FortiOS\s+v?([\d.]+)",                                     "FortiOS"),
    (r"PAN-OS\s+([\d.]+)",                                        "PAN-OS"),
]


def _detect_vendor(sys_oid: str, sys_descr: str) -> str:
    for prefix, vendor in _VENDOR_OID_MAP:
        if sys_oid.startswith(prefix):
            return vendor
    for pattern, vendor in _DESCR_VENDOR_PATTERNS:
        if re.search(pattern, sys_descr, re.IGNORECASE):
            return vendor
    return ""


def _detect_os(sys_descr: str) -> tuple:
    """Return (os_name, os_version) from sysDescr."""
    for pattern, name in _DESCR_OS_PATTERNS:
        m = re.search(pattern, sys_descr, re.IGNORECASE)
        if m:
            return name, m.group(1)
    return "", ""


def _detect_device_type(sys_descr: str, vendor: str) -> str:
    descr_lower = sys_descr.lower()
    if any(kw in descr_lower for kw in ("router", "routing", "junos", "ios xr", "ios-xr")):
        return "network"
    if any(kw in descr_lower for kw in ("switch", "catalyst", "nexus", "eos", "extreme")):
        return "network"
    if any(kw in descr_lower for kw in ("firewall", "pan-os", "fortios", "asa")):
        return "network"
    if any(kw in descr_lower for kw in ("ups", "uninterruptible")):
        return "appliance"
    if any(kw in descr_lower for kw in ("printer", "jetdirect")):
        return "appliance"
    if vendor in ("Cisco", "Juniper", "HP/Aruba", "Arista", "Extreme",
                  "Fortinet", "Palo Alto", "Alcatel-Lucent", "Netgear", "Zyxel"):
        return "network"
    return "appliance"


# ── system_metadata — vendor / OS detection ───────────────────────────────────

meta_raw = sections.get("system_metadata", "")

SYS_DESCR   = _parse_scalar(meta_raw, ".1.3.6.1.2.1.1.1.0")
SYS_OID     = _parse_scalar(meta_raw, ".1.3.6.1.2.1.1.2.0")
SYS_NAME    = _parse_scalar(meta_raw, ".1.3.6.1.2.1.1.5.0")
SYS_CONTACT = _parse_scalar(meta_raw, ".1.3.6.1.2.1.1.4.0")
SYS_LOCATION = _parse_scalar(meta_raw, ".1.3.6.1.2.1.1.6.0")
SYS_UPTIME  = _parse_scalar(meta_raw, ".1.3.6.1.2.1.1.3.0")  # centiseconds

VENDOR = _detect_vendor(SYS_OID, SYS_DESCR)
OS_NAME, OS_VERSION = _detect_os(SYS_DESCR)


# ── device ────────────────────────────────────────────────────────────────────

dev_raw = sections.get("device", "")

# Entity MIB: pick the chassis entry — the row with the lowest numeric index.
# entPhysicalDescr  = col 2,  entPhysicalSerialNum = col 11
# entPhysicalMfgName= col 12, entPhysicalSoftwareRev = col 10
# entPhysicalFirmwareRev = col 9
ent_descr_table   = _parse_snmp_table(dev_raw, ".1.3.6.1.2.1.47.1.1.1.1.2")
ent_serial_table  = _parse_snmp_table(dev_raw, ".1.3.6.1.2.1.47.1.1.1.1.11")
ent_mfg_table     = _parse_snmp_table(dev_raw, ".1.3.6.1.2.1.47.1.1.1.1.12")
ent_swrev_table   = _parse_snmp_table(dev_raw, ".1.3.6.1.2.1.47.1.1.1.1.10")
ent_fwrev_table   = _parse_snmp_table(dev_raw, ".1.3.6.1.2.1.47.1.1.1.1.9")

def _chassis_val(table: dict) -> str:
    """Return the value from the lowest numeric row of an Entity MIB table."""
    if not table:
        return ""
    def _sort_key(k):
        try:
            return int(k)
        except ValueError:
            return 999999
    rows = sorted(table.keys(), key=_sort_key)
    # The table was built with one column ("2","11", etc.) — each row has
    # exactly one key since we walked a single column OID.
    row_data = table[rows[0]]
    return next(iter(row_data.values()), "") if row_data else ""

ent_model    = _chassis_val(ent_descr_table)
ent_serial   = _chassis_val(ent_serial_table)
ent_vendor   = _chassis_val(ent_mfg_table)
ent_sw_rev   = _chassis_val(ent_swrev_table)
ent_fw_rev   = _chassis_val(ent_fwrev_table)

# Prefer Entity MIB vendor over pattern-matched vendor when available
effective_vendor = ent_vendor or VENDOR

device_type = _detect_device_type(SYS_DESCR, effective_vendor)

output["device"]["hostname"]    = SYS_NAME
output["device"]["fqdn"]        = SYS_NAME   # SNMP does not expose FQDN; use sysName
output["device"]["device_type"] = device_type
output["device"]["vendor"]      = effective_vendor
output["device"]["model"]       = ent_model


# ── hardware ──────────────────────────────────────────────────────────────────

# CPU load is collected in cpu_memory section; pre-populate model from Entity MIB.
output["hardware"]["cpu_model"]          = ent_model or SYS_DESCR[:120]
output["hardware"]["bios_version"]       = ent_fw_rev
output["hardware"]["serial_number"]      = ent_serial
output["hardware"]["architecture"]       = ""
output["hardware"]["virtualization_type"] = "bare-metal"

# CPU cores: count of hrProcessorLoad rows
cpu_raw = sections.get("cpu_memory", "")
cpu_table = _parse_snmp_table(cpu_raw, ".1.3.6.1.2.1.25.3.3.1.2")
if cpu_table:
    output["hardware"]["cpu_cores"] = len(cpu_table)

# RAM: hrStorageTable row where hrStorageType = .1.3.6.1.2.1.25.2.1.2 (hrStorageRam)
_HR_STORAGE_TYPE_RAM = "1.3.6.1.2.1.25.2.1.2"
# hrStorageTable entry columns: type=2, descr=3, allocationUnits=4, size=5, used=6
storage_type_table  = _parse_snmp_table(cpu_raw, ".1.3.6.1.2.1.25.2.3.1.2")
storage_units_table = _parse_snmp_table(cpu_raw, ".1.3.6.1.2.1.25.2.3.1.4")
storage_size_table  = _parse_snmp_table(cpu_raw, ".1.3.6.1.2.1.25.2.3.1.5")

def _get_single_col(table: dict, row: str) -> str:
    row_data = table.get(row, {})
    return next(iter(row_data.values()), "") if row_data else ""

for row in storage_type_table:
    type_val = _get_single_col(storage_type_table, row)
    # type_val may be ".1.3.6.1.2.1.25.2.1.2" or "1.3.6.1.2.1.25.2.1.2"
    if _HR_STORAGE_TYPE_RAM in type_val:
        units_str = _get_single_col(storage_units_table, row)
        size_str  = _get_single_col(storage_size_table, row)
        try:
            ram_bytes = int(units_str) * int(size_str)
            output["hardware"]["memory_gb"] = round(ram_bytes / 1024 / 1024 / 1024, 2)
        except (ValueError, TypeError):
            pass
        break


# ── os ────────────────────────────────────────────────────────────────────────

# Use Entity MIB software revision when available; fall back to sysDescr parse
effective_os_name    = ent_sw_rev or OS_NAME or VENDOR
effective_os_version = ""
if ent_sw_rev:
    # entPhysicalSoftwareRev often looks like "15.2(4)E8" or "17.06.01a"
    effective_os_version = ent_sw_rev
elif OS_VERSION:
    effective_os_version = OS_VERSION

# Uptime in centiseconds -> human-readable string
uptime_str = ""
try:
    cs = int(SYS_UPTIME)
    total_secs = cs // 100
    days  = total_secs // 86400
    hours = (total_secs % 86400) // 3600
    mins  = (total_secs % 3600) // 60
    uptime_str = f"{days}d {hours}h {mins}m"
except (ValueError, TypeError):
    uptime_str = SYS_UPTIME

output["os"]["name"]    = effective_os_name
output["os"]["version"] = effective_os_version
output["os"]["build"]   = ent_fw_rev   # firmware rev as a proxy for build
output["os"]["kernel"]  = SYS_DESCR[:200] if SYS_DESCR else ""

# SNMP location/contact -> store as custom fields; no direct OS mapping
output["custom"]["snmp_location"] = SYS_LOCATION
output["custom"]["snmp_contact"]  = SYS_CONTACT
output["custom"]["snmp_uptime"]   = uptime_str
output["custom"]["sys_object_id"] = SYS_OID


# ── network interfaces ────────────────────────────────────────────────────────
#
# Join:
#   ifTable       (.1.3.6.1.2.1.2.2.1)   — core interface data
#   ifXTable      (.1.3.6.1.2.1.31.1.1.1) — alias + high-speed
#   ipAddrTable   (.1.3.6.1.2.1.4.20)    — IP addresses (indexed by IP)

iface_raw = sections.get("interfaces", "")

# ifEntry columns we care about:
#   1=ifIndex, 2=ifDescr, 3=ifType, 4=ifMtu, 5=ifSpeed,
#   6=ifPhysAddress, 7=ifAdminStatus, 8=ifOperStatus
if_descr_tbl    = _parse_snmp_table(iface_raw, ".1.3.6.1.2.1.2.2.1.2")
if_type_tbl     = _parse_snmp_table(iface_raw, ".1.3.6.1.2.1.2.2.1.3")
if_mtu_tbl      = _parse_snmp_table(iface_raw, ".1.3.6.1.2.1.2.2.1.4")
if_speed_tbl    = _parse_snmp_table(iface_raw, ".1.3.6.1.2.1.2.2.1.5")
if_mac_tbl      = _parse_snmp_table(iface_raw, ".1.3.6.1.2.1.2.2.1.6")
if_admin_tbl    = _parse_snmp_table(iface_raw, ".1.3.6.1.2.1.2.2.1.7")
if_oper_tbl     = _parse_snmp_table(iface_raw, ".1.3.6.1.2.1.2.2.1.8")

# ifXEntry: ifAlias (col 18) and ifHighSpeed (col 15)
if_alias_tbl    = _parse_snmp_table(iface_raw, ".1.3.6.1.2.1.31.1.1.1.18")
if_hispeed_tbl  = _parse_snmp_table(iface_raw, ".1.3.6.1.2.1.31.1.1.1.15")

# ipAddrTable: indexed by IP address
# ipAdEntIfIndex (col 2), ipAdEntNetMask (col 3)
ip_ifindex_tbl = _parse_snmp_table(iface_raw, ".1.3.6.1.2.1.4.20.1.2")
ip_mask_tbl    = _parse_snmp_table(iface_raw, ".1.3.6.1.2.1.4.20.1.3")

# Build: ifindex -> list of (ip, prefix_len)
def _mask_to_prefix(mask: str) -> int:
    try:
        parts = [int(x) for x in mask.split(".")]
        bits = sum(bin(b).count("1") for b in parts)
        return bits
    except (ValueError, AttributeError):
        return 32

ip_by_ifindex: dict = {}
for ip_addr, row_data in ip_ifindex_tbl.items():
    ifindex = next(iter(row_data.values()), "")
    mask_row = ip_mask_tbl.get(ip_addr, {})
    mask = next(iter(mask_row.values()), "255.255.255.255")
    prefix = _mask_to_prefix(mask)
    ip_by_ifindex.setdefault(ifindex, []).append(f"{ip_addr}/{prefix}")

_STATUS_MAP = {"1": "up", "2": "down", "3": "unknown"}

# Collect all known ifIndex values
all_ifindexes = set(if_descr_tbl.keys())

for idx in sorted(all_ifindexes, key=lambda x: int(x) if x.isdigit() else 0):
    descr     = _get_single_col(if_descr_tbl, idx)
    mac_hex   = _get_single_col(if_mac_tbl, idx)
    admin_raw = _get_single_col(if_admin_tbl, idx)
    oper_raw  = _get_single_col(if_oper_tbl, idx)
    speed_raw = _get_single_col(if_speed_tbl, idx)
    hispd_raw = _get_single_col(if_hispeed_tbl, idx)
    alias     = _get_single_col(if_alias_tbl, idx)
    mtu_raw   = _get_single_col(if_mtu_tbl, idx)

    admin_status = _STATUS_MAP.get(admin_raw, "unknown")
    oper_status  = _STATUS_MAP.get(oper_raw, "unknown")
    mac = _hex_mac_to_str(mac_hex) if mac_hex else ""

    # Prefer ifHighSpeed (Mbps) over ifSpeed (bps) for high-speed interfaces
    speed = _highspeed_to_label(hispd_raw) if hispd_raw and hispd_raw != "0" else _bps_to_speed_label(speed_raw)

    try:
        mtu = int(mtu_raw) if mtu_raw else None
    except ValueError:
        mtu = None

    iface: dict = {
        "name":         descr,
        "description":  alias,
        "mac":          mac,
        "ipv4":         ip_by_ifindex.get(idx, []),
        "ipv6":         [],
        "admin_status": admin_status,
        "oper_status":  oper_status,
        "speed":        speed,
        "duplex":       "unknown",
        "mtu":          mtu,
        "port_mode":    "routed",
    }
    output["network"]["interfaces"].append(iface)


# ── network routes ────────────────────────────────────────────────────────────
#
# ipRouteTable (.1.3.6.1.2.1.4.21.1):
#   col 1=ipRouteDest, col 2=ipRouteIfIndex, col 3=ipRouteMetric1,
#   col 7=ipRouteNextHop, col 8=ipRouteType, col 11=ipRouteMask
#
# Row index = destination IP address
#
# inetCidrRouteTable (.1.3.6.1.2.1.4.24.7.1) uses a more complex index;
# we collect entries from whichever table is non-empty.

route_raw = sections.get("routes", "")

rt_nexthop_tbl = _parse_snmp_table(route_raw, ".1.3.6.1.2.1.4.21.1.7")
rt_metric_tbl  = _parse_snmp_table(route_raw, ".1.3.6.1.2.1.4.21.1.3")
rt_mask_tbl    = _parse_snmp_table(route_raw, ".1.3.6.1.2.1.4.21.1.11")
rt_ifindex_tbl = _parse_snmp_table(route_raw, ".1.3.6.1.2.1.4.21.1.2")

# Build ifIndex -> interface name lookup from already-parsed interfaces
_ifindex_to_name: dict = {}
for _iface in output["network"]["interfaces"]:
    # We need the original ifIndex — re-derive from descr table
    pass
# Rebuild: iterate if_descr_tbl for name
for _idx, _row in if_descr_tbl.items():
    _name = next(iter(_row.values()), "")
    _ifindex_to_name[_idx] = _name

routes_seen: set = set()
for dest_ip, row_data in rt_nexthop_tbl.items():
    gw       = next(iter(row_data.values()), "")
    mask_row = rt_mask_tbl.get(dest_ip, {})
    mask     = next(iter(mask_row.values()), "")
    metric_row = rt_metric_tbl.get(dest_ip, {})
    metric_str = next(iter(metric_row.values()), "")
    ifidx_row  = rt_ifindex_tbl.get(dest_ip, {})
    ifidx      = next(iter(ifidx_row.values()), "")

    # Build CIDR destination
    if mask:
        prefix = _mask_to_prefix(mask)
        destination = f"{dest_ip}/{prefix}"
    else:
        destination = dest_ip

    iface_name = _ifindex_to_name.get(ifidx, ifidx)

    try:
        metric = int(metric_str) if metric_str else None
    except ValueError:
        metric = None

    key = (destination, gw)
    if key in routes_seen:
        continue
    routes_seen.add(key)

    entry: dict = {
        "destination": destination,
        "gateway":     gw,
        "interface":   iface_name,
        "metric":      metric,
    }
    output["network"]["routes"].append(entry)

# Default gateway
for r in output["network"]["routes"]:
    if r["destination"] in ("0.0.0.0/0", "0.0.0.0"):
        output["network"]["default_gateway"] = r.get("gateway", "")
        break


# ── network DNS ───────────────────────────────────────────────────────────────
# SNMP has no standard DNS MIB; the dns_servers list will be empty unless
# vendor-specific OIDs returned data.  We emit an empty list to satisfy schema.
output["network"]["dns_servers"] = []


# ── packages — hrSWInstalledTable ─────────────────────────────────────────────
#
# hrSWInstalledTable (.1.3.6.1.2.1.25.6.3.1):
#   col 2=hrSWInstalledName, col 4=hrSWInstalledVersion,
#   col 5=hrSWInstalledDate (DateAndTime OCTET-STRING)

pkg_raw = sections.get("packages", "")

sw_name_tbl    = _parse_snmp_table(pkg_raw, ".1.3.6.1.2.1.25.6.3.1.2")
sw_ver_tbl     = _parse_snmp_table(pkg_raw, ".1.3.6.1.2.1.25.6.3.1.4")
sw_date_tbl    = _parse_snmp_table(pkg_raw, ".1.3.6.1.2.1.25.6.3.1.5")

for row in sorted(sw_name_tbl.keys(), key=lambda x: int(x) if x.isdigit() else 0):
    name = _get_single_col(sw_name_tbl, row)
    if not name:
        continue
    version  = _get_single_col(sw_ver_tbl, row)
    date_hex = _get_single_col(sw_date_tbl, row)
    install_date = _parse_dateantime(date_hex) if date_hex else ""
    output["packages"].append({
        "name":         name,
        "version":      version,
        "vendor":       effective_vendor,
        "install_date": install_date,
        "source":       "other",
    })


# ── services — hrSWRunTable ───────────────────────────────────────────────────
#
# hrSWRunTable (.1.3.6.1.2.1.25.4.2.1):
#   col 2=hrSWRunName, col 7=hrSWRunStatus
#   hrSWRunStatus: 1=running, 2=runnable, 3=notRunnable, 4=invalid

svc_raw = sections.get("services", "")

sw_run_name_tbl   = _parse_snmp_table(svc_raw, ".1.3.6.1.2.1.25.4.2.1.2")
sw_run_status_tbl = _parse_snmp_table(svc_raw, ".1.3.6.1.2.1.25.4.2.1.7")

_RUN_STATUS_MAP = {"1": "running", "2": "running", "3": "stopped", "4": "stopped"}

for row in sorted(sw_run_name_tbl.keys(), key=lambda x: int(x) if x.isdigit() else 0):
    name = _get_single_col(sw_run_name_tbl, row)
    if not name:
        continue
    status_raw = _get_single_col(sw_run_status_tbl, row)
    status = _RUN_STATUS_MAP.get(status_raw, "unknown")
    output["services"].append({
        "name":    name,
        "status":  status,
        "startup": "unknown",
    })


# ── filesystem — hrStorageTable ───────────────────────────────────────────────
#
# hrStorageTable (.1.3.6.1.2.1.25.2.3.1):
#   col 2=hrStorageType, col 3=hrStorageDescr,
#   col 4=hrStorageAllocationUnits (bytes), col 5=hrStorageSize, col 6=hrStorageUsed
#
# Storage types we report:
#   .1.3.6.1.2.1.25.2.1.4 = hrStorageFixedDisk
#   .1.3.6.1.2.1.25.2.1.9 = hrStorageFlashMemory
#   .1.3.6.1.2.1.25.2.1.2 = hrStorageRam  (already used above for memory_gb)

fs_raw = sections.get("filesystem", "")

fs_type_tbl  = _parse_snmp_table(fs_raw, ".1.3.6.1.2.1.25.2.3.1.2")
fs_descr_tbl = _parse_snmp_table(fs_raw, ".1.3.6.1.2.1.25.2.3.1.3")
fs_units_tbl = _parse_snmp_table(fs_raw, ".1.3.6.1.2.1.25.2.3.1.4")
fs_size_tbl  = _parse_snmp_table(fs_raw, ".1.3.6.1.2.1.25.2.3.1.5")
fs_used_tbl  = _parse_snmp_table(fs_raw, ".1.3.6.1.2.1.25.2.3.1.6")

_FS_TYPES_INCLUDE = {
    "1.3.6.1.2.1.25.2.1.4",   # hrStorageFixedDisk
    "1.3.6.1.2.1.25.2.1.9",   # hrStorageFlashMemory
}

for row in sorted(fs_type_tbl.keys(), key=lambda x: int(x) if x.isdigit() else 0):
    type_val = _get_single_col(fs_type_tbl, row).lstrip(".")
    if type_val not in _FS_TYPES_INCLUDE:
        continue
    descr = _get_single_col(fs_descr_tbl, row) or f"storage-{row}"
    units_str = _get_single_col(fs_units_tbl, row)
    size_str  = _get_single_col(fs_size_tbl, row)
    used_str  = _get_single_col(fs_used_tbl, row)
    try:
        units  = int(units_str)
        size_bytes = units * int(size_str)
        used_bytes = units * int(used_str)
        size_gb = round(size_bytes / 1024 / 1024 / 1024, 2)
        free_gb = round((size_bytes - used_bytes) / 1024 / 1024 / 1024, 2)
    except (ValueError, TypeError):
        size_gb = free_gb = None

    fs_type_label = "flash" if "9" in type_val.split(".")[-1:] else "fixed"

    output["filesystem"].append({
        "mount":         descr,
        "type":          fs_type_label,
        "size_gb":       size_gb,
        "free_gb":       free_gb,
        "mount_options": [],
        "suid_files":    [],
    })


# ── security ──────────────────────────────────────────────────────────────────
# SNMP collection has no firewall rule introspection capability.
output["security"]["firewall_enabled"]      = None
output["security"]["secure_boot"]           = None
output["security"]["audit_logging_enabled"] = None


# ── SNMP section ──────────────────────────────────────────────────────────────
#
# snmpTargetAddrTable (.1.3.6.1.6.3.12.1.2.1):
#   col 3=snmpTargetAddrTDomain, col 4=snmpTargetAddrTAddress (transport addr)
#   col 9=snmpTargetAddrStorageType

snmp_raw = sections.get("snmp_info", "")

trap_addr_tbl = _parse_snmp_table(snmp_raw, ".1.3.6.1.6.3.12.1.2.1.4")

trap_targets = []
for row, row_data in trap_addr_tbl.items():
    addr_hex = next(iter(row_data.values()), "")
    if not addr_hex:
        continue
    # snmpTargetAddrTAddress for UDP: 6 bytes = 4 IP + 2 port (hex)
    h = addr_hex.replace(" ", "")
    if len(h) == 12:
        try:
            ip = ".".join(str(int(h[i:i+2], 16)) for i in range(0, 8, 2))
            port = int(h[8:12], 16)
            trap_targets.append(f"{ip}:{port}")
        except (ValueError, IndexError):
            trap_targets.append(addr_hex)
    else:
        trap_targets.append(addr_hex)

# Determine which SNMP version was used for collection
versions = [f"v{SNMP_VERSION}"] if "SNMP_VERSION" in dir() else []

output["snmp"] = {
    "enabled":      True,
    "versions":     versions,
    "communities":  [],
    "v3_users":     [],
    "trap_targets": trap_targets,
    "location":     SYS_LOCATION,
    "contact":      SYS_CONTACT,
}


# ── VLANs ─────────────────────────────────────────────────────────────────────
#
# Cisco VTP: vtpVlanTable (.1.3.6.1.4.1.9.9.46.1.3.1.1)
#   Index is "management_domain.vlan_id"
#   col 2=vtpVlanState, col 4=vtpVlanName
#
# Q-BRIDGE-MIB: dot1qVlanStaticTable (.1.3.6.1.2.1.17.7.1.4.3.1)
#   Index is vlan_id
#   col 1=dot1qVlanStaticName, col 4=dot1qVlanStaticRowStatus

vlan_raw = sections.get("vlans", "")

# Cisco VTP state values: 1=active, 2=suspended, 3=mtuTooBigForDevice, 4=mtuTooBigForTrunk
_VTP_STATE_MAP = {"1": "active", "2": "suspended", "3": "unknown", "4": "unknown"}

vtp_state_tbl = _parse_snmp_table(vlan_raw, ".1.3.6.1.4.1.9.9.46.1.3.1.1.2")
vtp_name_tbl  = _parse_snmp_table(vlan_raw, ".1.3.6.1.4.1.9.9.46.1.3.1.1.4")

vlans: list = []

if vtp_state_tbl:
    for row in sorted(vtp_state_tbl.keys()):
        # VTP row index is "domain.vlan_id" — split on last dot
        dot_pos = row.rfind(".")
        vlan_id_str = row[dot_pos + 1:] if dot_pos >= 0 else row
        try:
            vlan_id = int(vlan_id_str)
        except ValueError:
            continue
        state_raw = _get_single_col(vtp_state_tbl, row)
        state = _VTP_STATE_MAP.get(state_raw, "unknown")
        name_row  = vtp_name_tbl.get(row, {})
        vlan_name = next(iter(name_row.values()), "") if name_row else ""
        vlans.append({"id": vlan_id, "name": vlan_name, "state": state})
else:
    # Q-BRIDGE-MIB fallback
    dot1q_name_tbl   = _parse_snmp_table(vlan_raw, ".1.3.6.1.2.1.17.7.1.4.3.1.1")
    dot1q_status_tbl = _parse_snmp_table(vlan_raw, ".1.3.6.1.2.1.17.7.1.4.3.1.5")
    # dot1qVlanStaticRowStatus: 1=active, 2=notInService
    for row in sorted(dot1q_name_tbl.keys(), key=lambda x: int(x) if x.isdigit() else 0):
        try:
            vlan_id = int(row)
        except ValueError:
            continue
        vlan_name = _get_single_col(dot1q_name_tbl, row)
        status_raw = _get_single_col(dot1q_status_tbl, row)
        state = "active" if status_raw == "1" else ("suspended" if status_raw == "2" else "unknown")
        vlans.append({"id": vlan_id, "name": vlan_name, "state": state})

if vlans:
    output["vlans"] = vlans


# ── routing_protocols — BGP + OSPF ───────────────────────────────────────────
#
# BGP4-MIB bgpPeerTable (.1.3.6.1.2.1.15.3.1):
#   Index = peer IP address
#   col 2=bgpPeerState, col 7=bgpPeerRemoteAs, col 11=bgpPeerRemoteAddr
#
# BGP peer states: 1=idle, 2=connect, 3=active, 4=opensent, 5=openconfirm, 6=established
_BGP_STATE_MAP = {
    "1": "Idle", "2": "Connect", "3": "Active",
    "4": "OpenSent", "5": "OpenConfirm", "6": "Established",
}

bgp_raw = sections.get("bgp", "")

bgp_state_tbl   = _parse_snmp_table(bgp_raw, ".1.3.6.1.2.1.15.3.1.2")
bgp_remoteas_tbl = _parse_snmp_table(bgp_raw, ".1.3.6.1.2.1.15.3.1.7")
bgp_remoteip_tbl = _parse_snmp_table(bgp_raw, ".1.3.6.1.2.1.15.3.1.11")

bgp_neighbors: list = []
for peer_ip in sorted(bgp_state_tbl.keys()):
    state_raw  = _get_single_col(bgp_state_tbl, peer_ip)
    state      = _BGP_STATE_MAP.get(state_raw, state_raw)
    remote_as  = _get_single_col(bgp_remoteas_tbl, peer_ip)
    remote_ip  = _get_single_col(bgp_remoteip_tbl, peer_ip) or peer_ip
    try:
        asn = int(remote_as)
    except (ValueError, TypeError):
        asn = remote_as or None
    bgp_neighbors.append({
        "address":    remote_ip,
        "remote_asn": asn,
        "state":      state,
        "description": "",
    })

# OSPF-MIB ospfNbrTable (.1.3.6.1.2.1.14.10.1):
#   Index = neighbor IP address + address-less index
#   col 1=ospfNbrIpAddr, col 6=ospfNbrState
#
# OSPF neighbor states: 1=down, 2=attempt, 3=init, 4=twoWay, 5=exchangeStart,
#                       6=exchange, 7=loading, 8=full
_OSPF_STATE_MAP = {
    "1": "Down", "2": "Attempt", "3": "Init", "4": "TwoWay",
    "5": "ExchangeStart", "6": "Exchange", "7": "Loading", "8": "Full",
}

ospf_raw = sections.get("ospf", "")

ospf_addr_tbl  = _parse_snmp_table(ospf_raw, ".1.3.6.1.2.1.14.10.1.1")
ospf_state_tbl = _parse_snmp_table(ospf_raw, ".1.3.6.1.2.1.14.10.1.6")

ospf_neighbors: list = []
for row in sorted(ospf_addr_tbl.keys()):
    nbr_ip    = _get_single_col(ospf_addr_tbl, row) or row
    state_raw = _get_single_col(ospf_state_tbl, row)
    state     = _OSPF_STATE_MAP.get(state_raw, state_raw)
    ospf_neighbors.append({
        "address":    nbr_ip,
        "remote_asn": None,
        "state":      state,
        "description": "",
    })

routing_protocols: list = []
if bgp_neighbors:
    routing_protocols.append({
        "protocol":  "bgp",
        "instance":  "",
        "router_id": "",
        "networks":  [],
        "neighbors": bgp_neighbors,
    })
if ospf_neighbors:
    routing_protocols.append({
        "protocol":  "ospf",
        "instance":  "",
        "router_id": "",
        "networks":  [],
        "neighbors": ospf_neighbors,
    })

if routing_protocols:
    output["routing_protocols"] = routing_protocols


# ── users / groups — SNMP has no user MIB ────────────────────────────────────
# Leave as empty lists (already initialised by CANONICAL_EMPTY).
# output["users"] and output["groups"] remain [].
