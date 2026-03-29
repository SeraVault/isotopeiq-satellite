#!/usr/bin/sh
# HP-UX Baseline Collector
# Gathers system information for the IsotopeIQ canonical schema.
# Each section is delimited by a [SECTION] marker for the parser.
# Targets: HP-UX 11i v1 (B.11.11), v2 (B.11.23), v3 (B.11.31).
# Requires: POSIX /usr/bin/sh — NO bash-specific syntax.
# Optional (root): machinfo, swlist, kmadmin/kcmodule, kctune/kmtune,
#                  ipfstat, audsys, getprdef, rmsock, lsof.

# ── Privilege elevation ───────────────────────────────────────────────────────
# These values are injected at runtime from the device's credential record.
# Do not hardcode secrets here — use the {{PLACEHOLDER}} syntax instead.
#
# Available placeholders (substituted by IsotopeIQ before the script runs):
#   {{ELEVATE}}       — elevation method derived from credential type:
#                         password    → sudo_pass
#                         private_key → sudo
#                         api_token / none → none
#   {{ELEVATE_PASS}}  — the credential password (for sudo_pass / su)
#   {{ELEVATE_CMD}}   — custom elevation binary (e.g. dzdo, pbrun)
#                       only used when ELEVATE=custom; override below if needed
#   {{USERNAME}}      — credential username
#   {{PASSWORD}}      — credential password (same as ELEVATE_PASS)
#   {{HOSTNAME}}      — device hostname
#
ELEVATE="${ELEVATE:-{{ELEVATE}}}"
ELEVATE_PASS="${ELEVATE_PASS:-{{ELEVATE_PASS}}}"
ELEVATE_CMD="${ELEVATE_CMD:-}"   # set to e.g. "dzdo" for custom elevation

# priv <command...> — run a command with the configured elevation method.
# Never exits non-zero; failed privileged commands produce no output rather
# than aborting the collection run.
# HP-UX may lack sudo; fall back to /usr/lbin/su or direct execution.
priv() {
    case "$ELEVATE" in
        none)
            "$@" 2>/dev/null || true
            ;;
        sudo)
            sudo "$@" 2>/dev/null || true
            ;;
        sudo_pass)
            echo "$ELEVATE_PASS" | sudo -S "$@" 2>/dev/null || true
            ;;
        su)
            # /usr/lbin/su is the HP-UX su location; fall back to /usr/bin/su
            _SU=/usr/lbin/su
            [ -x "$_SU" ] || _SU=/usr/bin/su
            echo "$ELEVATE_PASS" | "$_SU" - root -c "$*" 2>/dev/null || true
            ;;
        custom)
            $ELEVATE_CMD "$@" 2>/dev/null || true
            ;;
        *)
            # Unknown method — skip rather than abort
            true
            ;;
    esac
}

SEP="---ISOTOPEIQ---"

section() { echo "${SEP}[$1]"; }

# ── Device ────────────────────────────────────────────────────────────────────
section "device"
hostname 2>/dev/null || uname -n
# FQDN — hostname -f may not be supported on all HP-UX versions
hostname -f 2>/dev/null || uname -n 2>/dev/null || echo ""
echo "server"     # device_type
echo "HP"         # vendor
# Model: machinfo is available on Integrity (IA-64); fall back to uname -m
if [ -x /usr/contrib/bin/machinfo ]; then
    /usr/contrib/bin/machinfo 2>/dev/null | grep -i "model:" | head -1 | sed 's/.*[Mm]odel:[[:space:]]*//'
else
    uname -m 2>/dev/null || echo ""
fi

# ── Hardware ──────────────────────────────────────────────────────────────────
section "hardware"
# CPU model
if [ -x /usr/contrib/bin/machinfo ]; then
    /usr/contrib/bin/machinfo 2>/dev/null | grep "CPU:" | head -1 | sed 's/.*CPU:[[:space:]]*//'
else
    echo ""
fi
# CPU core/socket count
if [ -x /usr/contrib/bin/machinfo ]; then
    _cores=$(/usr/contrib/bin/machinfo 2>/dev/null | grep -i "logical proc" | head -1 | sed 's/[^0-9]//g')
    if [ -z "$_cores" ]; then
        _cores=$(/usr/contrib/bin/machinfo 2>/dev/null | grep -i "Number of CPUs" | head -1 | sed 's/[^0-9]//g')
    fi
    if [ -z "$_cores" ]; then
        _cores=$(ioscan -fnC processor 2>/dev/null | grep -c processor || echo "")
    fi
    echo "${_cores:-}"
else
    ioscan -fnC processor 2>/dev/null | grep -c processor || echo ""
fi
# RAM in GB — machinfo "Memory:" line gives MB or GB
if [ -x /usr/contrib/bin/machinfo ]; then
    _memline=$(/usr/contrib/bin/machinfo 2>/dev/null | grep -i "^[[:space:]]*Memory:" | head -1)
    _memval=$(echo "$_memline" | sed 's/[^0-9.]//g')
    _memunit=$(echo "$_memline" | grep -oi "GB\|MB" | head -1)
    if [ "$_memunit" = "GB" ]; then
        echo "${_memval}"
    elif [ "$_memunit" = "MB" ]; then
        # Convert MB to GB via awk
        echo "$_memval" | awk '{printf "%.2f\n", $1/1024}'
    else
        # Fall back: swapinfo -t reports physical memory in KB
        swapinfo -t 2>/dev/null | awk '/^[Mm]em/ {printf "%.2f\n", $2/1024/1024}' || echo ""
    fi
else
    swapinfo -t 2>/dev/null | awk '/^[Mm]em/ {printf "%.2f\n", $2/1024/1024}' || echo ""
fi
# BIOS / firmware revision
if [ -x /usr/contrib/bin/machinfo ]; then
    /usr/contrib/bin/machinfo 2>/dev/null | grep -i "Firmware revision" | head -1 | sed 's/.*:[[:space:]]*//'
else
    echo ""
fi
# Serial number
if [ -x /usr/contrib/bin/machinfo ]; then
    /usr/contrib/bin/machinfo 2>/dev/null | grep -i "serial number" | head -1 | sed 's/.*:[[:space:]]*//'
else
    echo ""
fi
# Architecture
uname -m 2>/dev/null || echo ""
# Virtualization detection
# HP Integrity Virtual Machine (HPVM) or vPars
if [ -x /usr/contrib/bin/machinfo ]; then
    if /usr/contrib/bin/machinfo 2>/dev/null | grep -qi "HP Integrity Virtual Machine"; then
        echo "hpvm"
    elif [ -f /proc/vmtype ]; then
        cat /proc/vmtype 2>/dev/null || echo "other"
    else
        echo "bare-metal"
    fi
elif [ -f /proc/vmtype ]; then
    cat /proc/vmtype 2>/dev/null || echo "other"
else
    echo "bare-metal"
fi

# ── OS ────────────────────────────────────────────────────────────────────────
section "os"
echo "HP-UX"                      # os name
uname -r 2>/dev/null || echo ""   # version (e.g. B.11.31)
uname -v 2>/dev/null || echo ""   # build / version string
uname -r 2>/dev/null || echo ""   # kernel (same as version on HP-UX)
# Timezone — check TZ env var then /etc/TIMEZONE
if [ -n "${TZ:-}" ]; then
    echo "$TZ"
elif [ -f /etc/TIMEZONE ]; then
    grep "^TZ=" /etc/TIMEZONE | head -1 | cut -d= -f2 || echo ""
else
    echo ""
fi
# NTP servers from /etc/ntp.conf
if [ -f /etc/ntp.conf ]; then
    grep "^server " /etc/ntp.conf | awk '{print $2}' | tr '\n' ' ' || echo ""
else
    echo ""
fi
# NTP sync status
if command -v ntpq >/dev/null 2>&1; then
    ntpq -p 2>/dev/null | grep -q "^\*" && echo "yes" || echo "no"
elif command -v ntpstat >/dev/null 2>&1; then
    ntpstat >/dev/null 2>&1 && echo "yes" || echo "no"
else
    echo "unknown"
fi

# ── Network interfaces ────────────────────────────────────────────────────────
section "network_interfaces"
ifconfig -a 2>/dev/null || echo ""

section "network_routes"
netstat -rn 2>/dev/null || echo ""

section "network_dns"
grep "^nameserver" /etc/resolv.conf 2>/dev/null | awk '{print $2}' || echo ""

section "network_hosts"
grep -v "^#" /etc/hosts 2>/dev/null | grep -v "^$" || echo ""

# ── Users ─────────────────────────────────────────────────────────────────────
section "users"
# Format: username|uid|home|shell|groups|pw_last_changed|last_login|sudo_count
while IFS=: read -r uname _pw uid _gid _gecos home shell; do
    # Skip malformed lines
    case "$uid" in
        *[!0-9]*) continue ;;
    esac
    groups=$(id -Gn "$uname" 2>/dev/null | tr ' ' ',')
    # Last login from 'last' command
    lastlog_date=$(last "$uname" 2>/dev/null | head -2 | tail -1 | awk '{print $4,$5,$6,$7}' | xargs 2>/dev/null || echo "")
    # Password last changed — passwd -s (needs root on HP-UX)
    pw_date=$(priv passwd -s "$uname" 2>/dev/null | awk '{print $3}' || echo "")
    # sudo privileges
    sudo_priv=$(priv sudo -l -U "$uname" 2>/dev/null | grep -c "NOPASSWD\|ALL" || echo "0")
    echo "${uname}|${uid}|${home}|${shell}|${groups}|${pw_date}|${lastlog_date}|${sudo_priv}"
done < /etc/passwd

# ── Groups ────────────────────────────────────────────────────────────────────
section "groups"
while IFS=: read -r gname _pw gid members; do
    echo "${gname}|${gid}|${members}"
done < /etc/group

# ── Packages ──────────────────────────────────────────────────────────────────
section "packages"
# HP-UX SD-UX software depot
# swlist -l product format (fixed-width or whitespace-separated):
#   # Product(s) not contained in a bundle:
#   HPUXBaseAux          B.11.31.0712  HP-UX Base OS Auxiliary
if command -v swlist >/dev/null 2>&1; then
    swlist -l product 2>/dev/null | grep -v "^#" | grep -v "^$" | while read -r _name _rev _desc; do
        [ -z "$_name" ] && continue
        # Attempt install date via swlist -a install_date
        _date=$(swlist -a install_date "$_name" 2>/dev/null | grep -v "^#" | grep -v "^$" | awk '{print $2}' | head -1 || echo "")
        echo "${_name}|${_rev}||${_date}"
    done
fi

# ── Services ──────────────────────────────────────────────────────────────────
section "services"
# Running services from ps -ef
# Startup state from /sbin/rc3.d symlinks (S* = enabled, K* = disabled)
_startup_dir=/sbin/rc3.d
# Build a quick enabled/disabled map by scanning S*/K* symlinks
_enabled_svcs=""
_disabled_svcs=""
if [ -d "$_startup_dir" ]; then
    for _lnk in "${_startup_dir}"/S*; do
        [ -e "$_lnk" ] || continue
        _svc=$(basename "$_lnk" | sed 's/^S[0-9]*//')
        _enabled_svcs="${_enabled_svcs} ${_svc}"
    done
    for _lnk in "${_startup_dir}"/K*; do
        [ -e "$_lnk" ] || continue
        _svc=$(basename "$_lnk" | sed 's/^K[0-9]*//')
        _disabled_svcs="${_disabled_svcs} ${_svc}"
    done
fi

# Emit one line per init.d script: name|status|startup
if [ -d /sbin/init.d ]; then
    for _script in /sbin/init.d/*; do
        [ -f "$_script" ] || continue
        _svcname=$(basename "$_script")
        # Determine run status from ps
        _running="stopped"
        if ps -ef 2>/dev/null | grep -q "$_svcname"; then
            _running="running"
        fi
        # Determine startup state
        _startup="unknown"
        case " $_enabled_svcs " in
            *" $_svcname "*) _startup="enabled" ;;
        esac
        case " $_disabled_svcs " in
            *" $_svcname "*) _startup="disabled" ;;
        esac
        echo "${_svcname}|${_running}|${_startup}"
    done
fi

# ── Filesystem ────────────────────────────────────────────────────────────────
section "filesystem"
# bdf output (HP-UX df):
# Filesystem          kbytes    used   avail %used Mounted on
bdf 2>/dev/null | tail -n +2 || true

section "filesystem_mounts"
# /etc/mnttab: device mountpoint fstype options freq passno
if [ -f /etc/mnttab ]; then
    cat /etc/mnttab 2>/dev/null
else
    mount -p 2>/dev/null || mount 2>/dev/null || true
fi

section "filesystem_suid"
priv find / -xdev \( -perm -4000 -o -perm -2000 \) -type f 2>/dev/null | sort || true

# ── Security ──────────────────────────────────────────────────────────────────
section "security"
# HP-UX Trusted Mode (TCB) — getprdef -r or check /tcb existence
if command -v getprdef >/dev/null 2>&1; then
    priv getprdef -r 2>/dev/null || echo ""
elif [ -d /tcb/files/auth/system ]; then
    echo "trusted_mode=enabled"
else
    echo "trusted_mode=disabled"
fi
# Audit subsystem
priv audsys -q 2>/dev/null || echo "audit=unknown"
# Firewall — IPFilter
if command -v ipf >/dev/null 2>&1; then
    ipf -V 2>/dev/null | head -3 || echo "ipf=present"
elif [ -f /etc/opt/ipf/ipf.conf ]; then
    echo "ipf=conf_present"
else
    echo "ipf=absent"
fi
# Security patches
swlist -l product 2>/dev/null | grep -i security | head -20 || echo ""
# Password policy from getprdef
if command -v getprdef >/dev/null 2>&1; then
    priv getprdef 2>/dev/null | grep -E "maxpwlen|minpwlen|pw_expire|u_exp|maxlogins|loginFailures" || echo ""
fi

# ── Scheduled Tasks ───────────────────────────────────────────────────────────
section "scheduled_tasks"
# System-level crontabs
for _cf in /etc/crontab /etc/cron.d/*; do
    [ -f "$_cf" ] || continue
    grep -v "^#" "$_cf" | grep -v "^$" | while read -r _line; do
        echo "cron|system|${_cf}|${_line}"
    done
done
# Per-user crontabs from /var/spool/cron/crontabs
if [ -d /var/spool/cron/crontabs ]; then
    for _ctab in /var/spool/cron/crontabs/*; do
        [ -f "$_ctab" ] || continue
        _cuser=$(basename "$_ctab")
        grep -v "^#" "$_ctab" | grep -v "^$" | while read -r _line; do
            echo "cron|${_cuser}|crontab|${_line}"
        done
    done
fi

# ── SSH Keys ──────────────────────────────────────────────────────────────────
section "ssh_keys"
while IFS=: read -r uname _pw _uid _gid _gecos home _shell; do
    _akfile="${home}/.ssh/authorized_keys"
    [ -f "$_akfile" ] || continue
    while read -r _line; do
        case "$_line" in
            "#"*|"") continue ;;
        esac
        echo "${uname}|${_line}"
    done < "$_akfile"
done < /etc/passwd

# ── SSH Config ────────────────────────────────────────────────────────────────
section "ssh_config"
if [ -f /etc/ssh/sshd_config ]; then
    priv grep -v "^#" /etc/ssh/sshd_config 2>/dev/null | grep -v "^$" || echo ""
elif [ -f /opt/ssh/etc/sshd_config ]; then
    # HP SSH may be installed under /opt/ssh
    priv grep -v "^#" /opt/ssh/etc/sshd_config 2>/dev/null | grep -v "^$" || echo ""
fi

# ── Kernel Modules ────────────────────────────────────────────────────────────
section "kernel_modules"
if command -v kcmodule >/dev/null 2>&1; then
    # HP-UX 11.31 — kcmodule lists all kernel modules
    priv kcmodule 2>/dev/null || true
elif command -v kmadmin >/dev/null 2>&1; then
    # HP-UX 11.23 and earlier
    priv kmadmin -s 2>/dev/null || true
elif command -v kmsystem >/dev/null 2>&1; then
    priv kmsystem -s 2>/dev/null || true
else
    echo ""
fi

# ── Listening Services ────────────────────────────────────────────────────────
section "listening_services"
# netstat -an gives LISTEN lines; rmsock maps socket to process on HP-UX
netstat -an 2>/dev/null | grep "LISTEN" || true
# If rmsock or lsof is available, emit richer process info
if command -v lsof >/dev/null 2>&1; then
    priv lsof -i -n -P 2>/dev/null | grep "LISTEN" || true
fi

# ── Firewall Rules ────────────────────────────────────────────────────────────
section "firewall_rules"
if command -v ipfstat >/dev/null 2>&1; then
    priv ipfstat -io 2>/dev/null || true
elif [ -f /etc/opt/ipf/ipf.conf ]; then
    priv cat /etc/opt/ipf/ipf.conf 2>/dev/null || true
else
    echo ""
fi

# ── Sysctl / Kernel Tunables ─────────────────────────────────────────────────
section "sysctl"
if command -v kctune >/dev/null 2>&1; then
    # HP-UX 11.31
    kctune -v 2>/dev/null | grep -v "^#" | grep -v "^$" || true
elif command -v kmtune >/dev/null 2>&1; then
    # HP-UX 11.11 / 11.23
    kmtune 2>/dev/null | grep -v "^#" | grep -v "^$" || true
else
    echo ""
fi

# ── Logging Targets ───────────────────────────────────────────────────────────
section "logging_targets"
if [ -f /etc/syslog.conf ]; then
    grep "^[^#].*@" /etc/syslog.conf 2>/dev/null || echo ""
else
    echo ""
fi

# ── SNMP ─────────────────────────────────────────────────────────────────────
section "snmp"
if [ -f /etc/SnmpAgent.d/snmpd.conf ]; then
    grep -v "^#" /etc/SnmpAgent.d/snmpd.conf 2>/dev/null | grep -v "^$" || echo ""
elif [ -f /etc/snmpd.conf ]; then
    grep -v "^#" /etc/snmpd.conf 2>/dev/null | grep -v "^$" || echo ""
else
    echo ""
fi

echo "${SEP}[END]"
