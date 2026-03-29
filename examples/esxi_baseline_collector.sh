#!/bin/sh
# ESXi Baseline Collector
# Gathers system information for the IsotopeIQ canonical schema.
# Each section is delimited by a [SECTION] marker for the parser.
# Targets: VMware ESXi 6.x, 7.x, 8.x (busybox sh — no bash arrays).
# Tools used: esxcli, vim-cmd, vsish, vmware, uname, standard busybox utils.
# ESXi always runs as root — no privilege elevation needed, but priv() is
# included for consistency with other IsotopeIQ collectors.

# ── Privilege elevation ───────────────────────────────────────────────────────
# ESXi collectors always run as root, so ELEVATE defaults to "none".
# The {{PLACEHOLDER}} syntax is substituted by IsotopeIQ before the script runs.
#
# Available placeholders:
#   {{ELEVATE}}       — elevation method (password→sudo_pass, key→sudo, else none)
#   {{ELEVATE_PASS}}  — credential password
#   {{USERNAME}}      — credential username
#   {{PASSWORD}}      — credential password (same as ELEVATE_PASS)
#   {{HOSTNAME}}      — device hostname
#
ELEVATE="${ELEVATE:-{{ELEVATE}}}"
ELEVATE_PASS="${ELEVATE_PASS:-{{ELEVATE_PASS}}}"

# priv <command...> — run a command with the configured elevation method.
# On ESXi this always degrades to a passthrough; included for schema consistency.
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
        *)
            "$@" 2>/dev/null || true
            ;;
    esac
}

SEP="---ISOTOPEIQ---"

section() { echo "${SEP}[$1]"; }

# ── Device ────────────────────────────────────────────────────────────────────
section "device"
uname -n
uname -n   # ESXi has no hostname -f; emit same value for fqdn
echo "server"   # device_type
echo "VMware"   # vendor
esxcli hardware platform get 2>/dev/null | grep "Product Name" | cut -d: -f2 | xargs || echo ""
esxcli hardware platform get 2>/dev/null | grep "Serial Number" | cut -d: -f2 | xargs || echo ""

# ── Hardware ──────────────────────────────────────────────────────────────────
section "hardware"
# CPU model
esxcli hardware cpu global get 2>/dev/null | grep "CPU Model" | cut -d: -f2 | xargs || echo ""
# Number of CPU packages (sockets) * cores per package = total cores
_cpu_packages=$(esxcli hardware cpu global get 2>/dev/null | grep "Number of Packages" | cut -d: -f2 | xargs)
_cpu_cores=$(esxcli hardware cpu global get 2>/dev/null | grep "Number of Cores" | cut -d: -f2 | xargs)
echo "${_cpu_cores:-0}"
# RAM in GB — esxcli reports bytes
_mem_bytes=$(esxcli hardware memory get 2>/dev/null | grep "Physical Memory" | grep -oE '[0-9]+' | head -1)
if [ -n "$_mem_bytes" ] && [ "$_mem_bytes" -gt 0 ] 2>/dev/null; then
    awk "BEGIN {printf \"%.2f\n\", $_mem_bytes/1073741824}"
else
    echo "0"
fi
# BIOS version and date
esxcli hardware platform get 2>/dev/null | grep "BIOS Version" | cut -d: -f2 | xargs || echo ""
esxcli hardware platform get 2>/dev/null | grep "Serial Number" | cut -d: -f2 | xargs || echo ""
uname -m
# ESXi IS the hypervisor — always bare-metal from its own perspective
echo "bare-metal"

# ── OS ────────────────────────────────────────────────────────────────────────
section "os"
# OS name: e.g. "VMware ESXi"
vmware -v 2>/dev/null | awk '{print $1" "$2}' || echo "VMware ESXi"
# Version from esxcli (e.g. "8.0.3")
esxcli system version get 2>/dev/null | grep "^Version" | cut -d: -f2 | xargs || \
    vmware -v 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || echo ""
# Build number
esxcli system version get 2>/dev/null | grep "^Build" | cut -d: -f2 | xargs || echo ""
# Kernel
uname -r
# Timezone — ESXi stores it differently across versions
if esxcli system time get 2>/dev/null | grep -qi "timezone"; then
    esxcli system time get 2>/dev/null | grep -i "timezone" | cut -d: -f2 | xargs || echo "UTC"
elif [ -f /etc/localtime ]; then
    # Busybox readlink may not exist; try /etc/TZ
    if [ -f /etc/TZ ]; then
        cat /etc/TZ
    else
        echo "UTC"
    fi
else
    echo "UTC"
fi
# NTP servers
esxcli system ntp get 2>/dev/null | grep "Server" | cut -d: -f2 | xargs || echo ""
# NTP enabled/synced
_ntp_enabled=$(esxcli system ntp get 2>/dev/null | grep "Enabled" | cut -d: -f2 | xargs | tr '[:upper:]' '[:lower:]')
case "$_ntp_enabled" in
    true|yes|1) echo "yes" ;;
    false|no|0) echo "no"  ;;
    *)          echo "unknown" ;;
esac

# ── Network interfaces ────────────────────────────────────────────────────────
section "network_interfaces"
echo "=== VMkernel Interfaces ==="
esxcli network ip interface list 2>/dev/null || echo ""
echo "=== VMkernel IPv4 ==="
esxcli network ip interface ipv4 get 2>/dev/null || echo ""
echo "=== Physical NICs ==="
esxcli network nic list 2>/dev/null || echo ""

# ── Network routes ────────────────────────────────────────────────────────────
section "network_routes"
esxcli network ip route ipv4 list 2>/dev/null || echo ""

# ── Network DNS ───────────────────────────────────────────────────────────────
section "network_dns"
echo "=== DNS Servers ==="
esxcli network ip dns server list 2>/dev/null || echo ""
echo "=== DNS Search ==="
esxcli network ip dns search list 2>/dev/null || echo ""

# ── Users ─────────────────────────────────────────────────────────────────────
section "users"
esxcli system account list 2>/dev/null || echo ""

# ── Groups / Permissions ──────────────────────────────────────────────────────
section "groups"
esxcli system permission list 2>/dev/null || echo ""

# ── Packages (VIBs) ───────────────────────────────────────────────────────────
section "packages"
esxcli software vib list 2>/dev/null || echo ""

# ── Services ──────────────────────────────────────────────────────────────────
section "services"
echo "=== Maintenance Mode ==="
esxcli system maintenanceMode get 2>/dev/null || echo ""
echo "=== Service List ==="
esxcli system service list 2>/dev/null || \
    chkconfig --list 2>/dev/null || echo ""

# ── Filesystem ────────────────────────────────────────────────────────────────
section "filesystem"
echo "=== df ==="
df -k 2>/dev/null || echo ""
echo "=== Storage Filesystems ==="
esxcli storage filesystem list 2>/dev/null || echo ""

# ── Security ──────────────────────────────────────────────────────────────────
section "security"
echo "=== Lockdown Mode ==="
esxcli system lockdown get 2>/dev/null || echo "disabled"
echo "=== SSH Service ==="
esxcli system service list 2>/dev/null | grep -i ssh || echo "unknown"
echo "=== Shell Service ==="
esxcli system service list 2>/dev/null | grep -i "ESXi Shell\|esxshell\|shell" || echo "unknown"
echo "=== DCUI Service ==="
esxcli system service list 2>/dev/null | grep -i dcui || echo "unknown"
echo "=== Password Complexity ==="
esxcli system security passwordcomplexity get 2>/dev/null || echo ""
echo "=== Firewall Status ==="
esxcli network firewall get 2>/dev/null || echo ""
echo "=== TLS Rules ==="
esxcli system tls rules list 2>/dev/null || echo ""
echo "=== Syslog Config ==="
esxcli system syslog config get 2>/dev/null || echo ""
echo "=== SNMP ==="
esxcli system snmp get 2>/dev/null || echo ""

# ── Scheduled Tasks ───────────────────────────────────────────────────────────
section "scheduled_tasks"
echo "=== Root Crontab ==="
cat /var/spool/cron/crontabs/root 2>/dev/null | grep -v "^#" | grep -v "^$" | \
    while read -r line; do
        echo "cron|root|/var/spool/cron/crontabs/root|${line}"
    done || true
echo "=== Task List ==="
vim-cmd internalsvc/task_manager/getTaskList 2>/dev/null || \
    esxcli system task list 2>/dev/null || echo ""

# ── Listening Services ────────────────────────────────────────────────────────
section "listening_services"
esxcli network ip connection list 2>/dev/null | grep LISTEN || echo ""

# ── Firewall Rules ────────────────────────────────────────────────────────────
section "firewall_rules"
esxcli network firewall ruleset list 2>/dev/null || echo ""

# ── Sysctl (ESXi advanced config) ────────────────────────────────────────────
section "sysctl"
esxcli system settings advanced list 2>/dev/null || echo ""

# ── Logging Targets ───────────────────────────────────────────────────────────
section "logging_targets"
echo "=== Syslog Config ==="
esxcli system syslog config get 2>/dev/null || echo ""
echo "=== Syslog Loggers ==="
esxcli system syslog config loggers list 2>/dev/null || echo ""

# ── SSH Config ────────────────────────────────────────────────────────────────
section "ssh_config"
if [ -f /etc/ssh/sshd_config ]; then
    grep -v "^#" /etc/ssh/sshd_config 2>/dev/null | grep -v "^$" || echo ""
else
    echo ""
fi

# ── SNMP ──────────────────────────────────────────────────────────────────────
section "snmp"
esxcli system snmp get 2>/dev/null || echo ""

# ── Certificates ──────────────────────────────────────────────────────────────
section "certificates"
echo "=== TLS Rules ==="
esxcli system tls rules list 2>/dev/null || echo ""
echo "=== Host Certificate ==="
cat /etc/vmware/ssl/rui.crt 2>/dev/null || echo ""

# ── VLANs ─────────────────────────────────────────────────────────────────────
section "vlans"
echo "=== Standard vSwitches ==="
esxcli network vswitch standard list 2>/dev/null || echo ""
echo "=== DVS vSwitches ==="
esxcli network vswitch dvs vmware list 2>/dev/null || echo ""

echo "${SEP}[END]"
