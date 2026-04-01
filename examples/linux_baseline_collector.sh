#!/usr/bin/env bash
# Linux Baseline Collector
# Gathers system information for the IsotopeIQ canonical schema.
# Each section is delimited by a [SECTION] marker for the parser.
# Requires: bash, standard coreutils, iproute2, systemd (most modern distros).
# Optional: ss/netstat, lsmod, sysctl, auditctl, iptables/nft, dmidecode (root).

set -uo pipefail

# Detect init system once — used in several sections below
if command -v systemctl &>/dev/null && systemctl --version &>/dev/null 2>&1; then
    INIT_SYSTEM="systemd"
elif [ -f /sbin/openrc ] || command -v rc-service &>/dev/null; then
    INIT_SYSTEM="openrc"
elif [ -f /sbin/initctl ] && /sbin/initctl --version 2>/dev/null | grep -q upstart; then
    INIT_SYSTEM="upstart"
else
    INIT_SYSTEM="sysvinit"
fi

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
            su -c "$(printf '%q ' "$@")" - root <<< "$ELEVATE_PASS" 2>/dev/null || true
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
hostname
hostname -f 2>/dev/null || echo ""
echo "server"    # device_type
# vendor / model from DMI (needs root or root-readable DMI)
priv cat /sys/class/dmi/id/sys_vendor    2>/dev/null || echo ""
priv cat /sys/class/dmi/id/product_name  2>/dev/null || echo ""

# ── Hardware ──────────────────────────────────────────────────────────────────
section "hardware"
grep -m1 "model name" /proc/cpuinfo 2>/dev/null | cut -d: -f2 | xargs || \
    grep -m1 "^cpu model" /proc/cpuinfo 2>/dev/null | cut -d: -f2 | xargs || echo ""
nproc --all 2>/dev/null || nproc 2>/dev/null || grep -c "^processor" /proc/cpuinfo 2>/dev/null || echo ""
awk '/MemTotal/ {printf "%.2f\n", $2/1024/1024}' /proc/meminfo
priv cat /sys/class/dmi/id/bios_version  2>/dev/null || echo ""
priv cat /sys/class/dmi/id/product_serial 2>/dev/null || echo ""
uname -m
# Virtualization detection
if command -v systemd-detect-virt &>/dev/null; then
    systemd-detect-virt 2>/dev/null || echo "bare-metal"
elif [ -f /proc/cpuinfo ]; then
    grep -qm1 "hypervisor" /proc/cpuinfo && echo "other" || echo "bare-metal"
else
    echo "bare-metal"
fi

# ── OS ────────────────────────────────────────────────────────────────────────
section "os"
# os-release fields (present on all modern distros including Alpine)
if [ -f /etc/os-release ]; then
    . /etc/os-release
    echo "${NAME:-}"
    echo "${VERSION_ID:-}"
    echo "${BUILD_ID:-${VERSION:-}}"
elif [ -f /etc/alpine-release ]; then
    echo "Alpine Linux"
    cat /etc/alpine-release
    echo ""
elif [ -f /etc/redhat-release ]; then
    # RHEL/CentOS/Fedora without os-release (very old versions)
    head -1 /etc/redhat-release
    grep -oP '[\d.]+' /etc/redhat-release | head -1 || echo ""
    echo ""
elif [ -f /etc/SuSE-release ]; then
    # Old SUSE without os-release
    head -1 /etc/SuSE-release
    grep -E "^VERSION" /etc/SuSE-release | cut -d= -f2 | xargs || echo ""
    grep -E "^PATCHLEVEL" /etc/SuSE-release | cut -d= -f2 | xargs || echo ""
else
    echo ""
    echo ""
    echo ""
fi
uname -r
# Timezone
if [ -f /etc/timezone ]; then
    cat /etc/timezone
elif command -v timedatectl &>/dev/null; then
    timedatectl show -p Timezone --value 2>/dev/null || echo ""
elif [ -f /etc/localtime ]; then
    # Resolve symlink to get tz name
    readlink /etc/localtime 2>/dev/null | sed 's|.*/zoneinfo/||' || echo ""
else
    echo ""
fi
# NTP servers
if [ -f /etc/systemd/timesyncd.conf ]; then
    grep -E "^NTP=" /etc/systemd/timesyncd.conf | cut -d= -f2 || echo ""
elif [ -f /etc/chrony.conf ]; then
    grep "^server " /etc/chrony.conf | awk '{print $2}' | tr '\n' ' ' || echo ""
elif [ -f /etc/ntp.conf ]; then
    grep "^server " /etc/ntp.conf | awk '{print $2}' | tr '\n' ' ' || echo ""
else
    echo ""
fi
# NTP synced?
if command -v timedatectl &>/dev/null; then
    timedatectl show -p NTPSynchronized --value 2>/dev/null || echo "unknown"
elif command -v ntpstat &>/dev/null; then
    ntpstat &>/dev/null && echo "yes" || echo "no"
else
    echo "unknown"
fi

# ── Network ───────────────────────────────────────────────────────────────────
section "network"
if command -v ip &>/dev/null; then
    ip -j addr show 2>/dev/null || ip addr show
else
    ifconfig -a 2>/dev/null || echo ""
fi

section "network_routes"
if command -v ip &>/dev/null; then
    ip -j route show 2>/dev/null || ip route show
else
    netstat -rn 2>/dev/null || route -n 2>/dev/null || echo ""
fi

section "network_dns"
grep "^nameserver" /etc/resolv.conf | awk '{print $2}' || echo ""

section "network_hosts"
grep -v "^#" /etc/hosts | grep -v "^$" || echo ""

# ── Users ─────────────────────────────────────────────────────────────────────
section "users"
# Format: username:uid:home:shell — then groups on next line
while IFS=: read -r uname _ uid _ _ home shell; do
    [[ "$uid" -ge 0 ]] 2>/dev/null || continue
    groups=$(id -Gn "$uname" 2>/dev/null | tr ' ' ',')
    lastlog_date=$(command -v lastlog &>/dev/null && lastlog -u "$uname" 2>/dev/null | tail -1 | awk '{print $4,$5,$6,$7,$8}' | xargs || echo "")
    # Password last changed (shadow - requires root or readable shadow)
    chage_date=$(priv chage -l "$uname" 2>/dev/null | grep "Last password change" | cut -d: -f2 | xargs || echo "")
    # sudo check
    sudo_priv=$(priv sudo -l -U "$uname" 2>/dev/null | grep -c "NOPASSWD\|ALL" || echo "0")
    echo "${uname}|${uid}|${home}|${shell}|${groups}|${chage_date}|${lastlog_date}|${sudo_priv}"
done < /etc/passwd

# ── Groups ────────────────────────────────────────────────────────────────────
section "groups"
while IFS=: read -r gname _ gid members; do
    echo "${gname}|${gid}|${members}"
done < /etc/group

# ── Packages ──────────────────────────────────────────────────────────────────
section "packages"
if command -v dpkg-query &>/dev/null; then
    # Use simpler format for older dpkg that may not support db-fsys
    dpkg-query -W -f='${Package}|${Version}|${Maintainer}|\n' 2>/dev/null || \
    dpkg-query -W -f='${Package}|${Version}||\n' 2>/dev/null || true
elif command -v rpm &>/dev/null; then
    rpm -qa --queryformat '%{NAME}|%{VERSION}-%{RELEASE}|%{VENDOR}|%{INSTALLTIME:date}\n' 2>/dev/null || true
elif command -v apk &>/dev/null; then
    # Alpine
    apk info -v 2>/dev/null | awk -F'-' '{name=$0; sub(/-[^-]+-r[0-9]+$/,"",name); ver=$0; sub(/^.*-/,"",ver); print name"|"ver"||"}' || true
elif command -v pacman &>/dev/null; then
    # Arch
    pacman -Q 2>/dev/null | awk '{print $1"|"$2"||"}' || true
elif command -v zypper &>/dev/null; then
    # SUSE / openSUSE
    zypper --no-color packages --installed-only 2>/dev/null \
        | awk -F'|' 'NR>2 && /^[[:space:]]*i/ {gsub(/^[[:space:]]+|[[:space:]]+$/,"",$3); gsub(/^[[:space:]]+|[[:space:]]+$/,"",$4); print $3"|"$4"||"}' || true
fi

# Snap packages (any distro)
if command -v snap &>/dev/null; then
    snap list 2>/dev/null | awk 'NR>1 {print $1"|"$2"||"}' || true
fi

# Flatpak packages (any distro)
if command -v flatpak &>/dev/null; then
    flatpak list --app --columns=application,version 2>/dev/null \
        | awk -F'\t' '{print $1"|"$2"||"}' || true
fi

# ── Services ──────────────────────────────────────────────────────────────────
section "services"
if [ "$INIT_SYSTEM" = "systemd" ]; then
    systemctl list-units --type=service --all --no-pager --no-legend \
        --output=json 2>/dev/null \
    || systemctl list-units --type=service --all --no-pager --no-legend 2>/dev/null
elif [ "$INIT_SYSTEM" = "openrc" ]; then
    rc-status --all --nocolor 2>/dev/null || rc-update show 2>/dev/null || true
elif [ "$INIT_SYSTEM" = "upstart" ]; then
    initctl list 2>/dev/null || true
else
    # SysVinit — list scripts in /etc/init.d
    if [ -d /etc/init.d ]; then
        for svc in /etc/init.d/*; do
            name=$(basename "$svc")
            status=$("$svc" status 2>/dev/null | grep -qiE "running|started" && echo "running" || echo "stopped")
            echo "${name}|${status}"
        done
    fi
fi

# ── Filesystem ────────────────────────────────────────────────────────────────
section "filesystem"
df -P -T 2>/dev/null | tail -n +2 || df -P 2>/dev/null | tail -n +2 || true

section "filesystem_mounts"
# Mount options from /proc/mounts
cat /proc/mounts 2>/dev/null || mount

section "filesystem_suid"
# SUID/SGID files (only real filesystems, skip slow network mounts)
priv find / -xdev \( -perm -4000 -o -perm -2000 \) -type f 2>/dev/null | sort || true

# ── Security ──────────────────────────────────────────────────────────────────
section "security"
# SELinux
getenforce 2>/dev/null || echo "disabled"
# AppArmor
if command -v apparmor_status &>/dev/null; then
    { apparmor_status --enabled 2>/dev/null && echo "enabled"; } || echo "disabled"
elif [ -d /sys/kernel/security/apparmor ]; then
    echo "enabled"
else
    echo "disabled"
fi
# Firewall (ufw / firewalld / iptables)
if command -v ufw &>/dev/null; then
    ufw status | head -1 || echo "inactive"
elif command -v firewall-cmd &>/dev/null; then
    firewall-cmd --state 2>/dev/null || echo "not running"
else
    iptables -L INPUT -n --line-numbers 2>/dev/null | head -1 || echo "unknown"
fi
# Secure boot (EFI systems only)
priv mokutil --sb-state 2>/dev/null || echo "unknown"
# Audit daemon
if [ "$INIT_SYSTEM" = "systemd" ]; then
    systemctl is-active auditd 2>/dev/null || echo "inactive"
elif command -v service &>/dev/null; then
    service auditd status 2>/dev/null | grep -qiE "running|active" && echo "active" || echo "inactive"
else
    echo "inactive"
fi
# Password policy from login.defs
priv grep -E "^(PASS_MIN_LEN|PASS_MAX_DAYS|PASS_WARN_AGE)" /etc/login.defs 2>/dev/null || echo ""

# ── Scheduled Tasks ───────────────────────────────────────────────────────────
section "scheduled_tasks"
# System crontabs (present on all distros)
for f in /etc/crontab /etc/cron.d/*; do
    [ -f "$f" ] || continue
    grep -v "^#" "$f" | grep -v "^$" | while read -r line; do
        echo "cron|system|${f}|${line}"
    done
done
# Per-user crontabs
for user in $(cut -d: -f1 /etc/passwd); do
    crontab -l -u "$user" 2>/dev/null | grep -v "^#" | grep -v "^$" | while read -r line; do
        echo "cron|${user}|crontab|${line}"
    done
done
# NOTE: do NOT use 'systemctl list-timers' — its NEXT/LAST timestamps are
# volatile and change on every timer activation.  Read OnCalendar= directly
# from the unit file on disk instead.  Skip /run/systemd/transient/ so only
# permanently-installed timers are captured.
if [ "$INIT_SYSTEM" = "systemd" ] && command -v systemctl >/dev/null 2>&1; then
    systemctl list-unit-files --type=timer --no-pager --no-legend 2>/dev/null \
    | while read -r unit state _rest; do
        [ -z "$unit" ] && continue
        [ "$state" = "masked" ] && continue
        unit_file=""
        for dir in /etc/systemd/system /usr/lib/systemd/system /lib/systemd/system; do
            [ -f "${dir}/${unit}" ] && unit_file="${dir}/${unit}" && break
        done
        [ -z "$unit_file" ] && continue
        cal=$(grep  -m1 '^OnCalendar='        "$unit_file" 2>/dev/null | cut -d= -f2-)
        boot=$(grep -m1 '^OnBootSec='         "$unit_file" 2>/dev/null | cut -d= -f2-)
        usec=$(grep -m1 '^OnUnitActiveSec='   "$unit_file" 2>/dev/null | cut -d= -f2-)
        schedule="${cal:-${boot:-${usec:-unknown}}}"
        echo "systemd-timer|root|${unit}|${schedule}"
    done
fi

# ── SSH Keys ──────────────────────────────────────────────────────────────────
section "ssh_keys"
while IFS=: read -r uname _ _ _ _ home _; do
    auth_keys="${home}/.ssh/authorized_keys"
    [ -f "$auth_keys" ] || continue
    while read -r line; do
        [[ "$line" =~ ^# ]] && continue
        [[ -z "$line" ]] && continue
        echo "${uname}|${line}"
    done < "$auth_keys"
done < /etc/passwd

# ── SSH Config ────────────────────────────────────────────────────────────────
section "ssh_config"
priv grep -v "^#" /etc/ssh/sshd_config 2>/dev/null | grep -v "^$" || echo ""

# ── Kernel Modules ────────────────────────────────────────────────────────────
section "kernel_modules"
lsmod 2>/dev/null | tail -n +2 || echo ""

# ── PCI Devices ──────────────────────────────────────────────────────────────
section "pci_devices"
# lspci -vmm produces a machine-parseable multi-record listing.
# Each device block ends with a blank line.
if command -v lspci &>/dev/null; then
    lspci -vmm 2>/dev/null || echo ""
else
    echo ""
fi

# ── Storage / Block Devices ───────────────────────────────────────────────────
section "storage_devices"
# lsblk -d lists only whole disks (no partitions); -P gives key="value" pairs.
if command -v lsblk &>/dev/null; then
    lsblk -d -n -P -o NAME,TYPE,SIZE,MODEL,VENDOR,SERIAL,TRAN,RM 2>/dev/null || echo ""
else
    echo ""
fi

# ── USB Devices ───────────────────────────────────────────────────────────────
section "usb_devices"
if command -v lsusb &>/dev/null; then
    lsusb 2>/dev/null || echo ""
else
    echo ""
fi

# ── Listening Services ────────────────────────────────────────────────────────
section "listening_services"
if command -v ss &>/dev/null; then
    priv ss -tlunp 2>/dev/null || true
elif command -v netstat &>/dev/null; then
    priv netstat -tlunp 2>/dev/null || true
else
    echo ""
fi

# ── Firewall Rules ────────────────────────────────────────────────────────────
section "firewall_rules"
if command -v nft &>/dev/null; then
    priv nft -j list ruleset 2>/dev/null || priv nft list ruleset 2>/dev/null || echo ""
elif command -v iptables &>/dev/null; then
    priv iptables-save 2>/dev/null || echo ""
fi

# ── Sysctl ────────────────────────────────────────────────────────────────────
section "sysctl"
# Filter out per-interface entries for ephemeral virtual interfaces
# (veth*, br-<hex>, docker*, virbr*, cni*, flannel*, cali*, tunl*, vxlan*).
# These change every time containers or VMs restart and produce false-positive
# drift.  Physical/stable interfaces (eth*, ens*, enp*, bond*, lo) are kept.
priv sysctl -a 2>/dev/null \
  | grep -Ev '\.(veth[0-9a-f]+|br-[0-9a-f]+|docker[0-9]+|virbr[0-9]+|cni[0-9]+|flannel[^.]*|cali[0-9a-f]+|tunl[0-9]+|vxlan[^.]*)(\.|[[:space:]]|$)' \
  || echo ""

# ── Logging Targets ───────────────────────────────────────────────────────────
section "logging_targets"
# rsyslog remote targets
priv grep -rh "^[^#].*@" /etc/rsyslog.conf /etc/rsyslog.d/ 2>/dev/null || echo ""
# systemd-journal remote
[ -f /etc/systemd/journal-remote.conf ] && priv cat /etc/systemd/journal-remote.conf 2>/dev/null || true

echo "${SEP}[END]"
