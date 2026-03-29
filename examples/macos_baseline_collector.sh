#!/usr/bin/env bash
# macOS Baseline Collector
# Gathers system information for the IsotopeIQ canonical schema.
# Each section is delimited by a [SECTION] marker for the parser.
# Requires: bash, standard macOS tools (no third-party dependencies).
# Supports: macOS 10.14 Mojave through macOS 15 Sequoia.
# Optional (root): SUID scan, firewall app list, MDM profiles, system keychain certs.

set -uo pipefail

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
scutil --get ComputerName 2>/dev/null || hostname
scutil --get LocalHostName 2>/dev/null || echo ""
echo "server"    # device_type
echo "Apple"     # vendor is always Apple
# Model identifier and serial from system_profiler
system_profiler SPHardwareDataType 2>/dev/null \
    | awk -F': ' '/Model Name|Model Identifier/{if(!model){model=$2}} /Serial Number \(system\)/{serial=$2} END{print model; print serial}'

# ── Hardware ──────────────────────────────────────────────────────────────────
section "hardware"
# CPU model
system_profiler SPHardwareDataType 2>/dev/null \
    | awk -F': ' '/Chip:|Processor Name:/{print $2; exit}'
# CPU core count (total: performance + efficiency cores on Apple Silicon,
# or logical core count on Intel)
system_profiler SPHardwareDataType 2>/dev/null \
    | awk -F': ' '/Total Number of Cores:|Number of CPUs:/{print $2; exit}'
# Memory in GB (reported as e.g. "16 GB")
system_profiler SPHardwareDataType 2>/dev/null \
    | awk -F': ' '/Memory:/{gsub(/ GB.*/,"",$2); print $2; exit}'
# Boot ROM version (equivalent to BIOS version)
system_profiler SPHardwareDataType 2>/dev/null \
    | awk -F': ' '/Boot ROM Version:/{print $2; exit}'
# Serial number (repeated here for hardware section consistency)
system_profiler SPHardwareDataType 2>/dev/null \
    | awk -F': ' '/Serial Number \(system\):/{print $2; exit}'
# Architecture
uname -m
# Virtualization detection via model string
system_profiler SPHardwareDataType 2>/dev/null \
    | awk -F': ' '/Model (Name|Identifier):/{
        model=tolower($2)
        if (model ~ /vmware/)      { print "vmware";      exit }
        if (model ~ /virtualbox/)  { print "virtualbox";  exit }
        if (model ~ /parallels/)   { print "other";       exit }
        print "bare-metal"; exit
    }'

# ── OS ────────────────────────────────────────────────────────────────────────
section "os"
sw_vers -productName  2>/dev/null || echo "macOS"
sw_vers -productVersion 2>/dev/null || echo ""
sw_vers -buildVersion 2>/dev/null || echo ""
uname -r
# Timezone
systemsetup -gettimezone 2>/dev/null | awk -F': ' '{print $2}' || \
    readlink /etc/localtime 2>/dev/null | sed 's|.*/zoneinfo/||' || echo ""
# NTP server
systemsetup -getnetworktimeserver 2>/dev/null | awk -F': ' '{print $2}' || echo ""
# NTP synced?
if systemsetup -getusingnetworktime 2>/dev/null | grep -qi "on"; then
    echo "yes"
else
    echo "no"
fi

# ── Network ───────────────────────────────────────────────────────────────────
section "network_interfaces"
ifconfig -a 2>/dev/null || echo ""

section "network_routes"
netstat -rn 2>/dev/null || route -n get default 2>/dev/null || echo ""

section "network_dns"
scutil --dns 2>/dev/null || echo ""

# ── Users ─────────────────────────────────────────────────────────────────────
section "users"
# List non-system users (UID >= 500), skipping _* service accounts
dscl . -list /Users UniqueID 2>/dev/null \
    | awk '$2 >= 500 && $1 !~ /^_/' \
    | while read -r uname uid; do
        home=$(dscl . -read "/Users/${uname}" NFSHomeDirectory 2>/dev/null \
               | awk '{print $2}')
        shell=$(dscl . -read "/Users/${uname}" UserShell 2>/dev/null \
                | awk '{print $2}')
        # Password last set — not directly readable; use account modification time
        pw_last_set=$(dscl . -read "/Users/${uname}" passwordLastSetTime 2>/dev/null \
                      | awk '{print $2}' || echo "")
        # Last login from 'last'
        last_login=$(last -1 "${uname}" 2>/dev/null \
                     | head -1 | awk '{if(NF>=8) print $5,$6,$7,$8}' || echo "")
        # Admin group membership
        admin_member=$(dseditgroup -o checkmember -m "${uname}" admin 2>/dev/null \
                       | grep -c "yes" || echo "0")
        echo "${uname}|${uid}|${home}|${shell}||${pw_last_set}|${last_login}|${admin_member}"
    done

# ── Groups ────────────────────────────────────────────────────────────────────
section "groups"
dscl . -list /Groups PrimaryGroupID 2>/dev/null \
    | while read -r gname gid; do
        members=$(dscl . -read "/Groups/${gname}" GroupMembership 2>/dev/null \
                  | sed 's/^GroupMembership: //' | tr ' ' ',' || echo "")
        echo "${gname}|${gid}|${members}"
    done

# ── Packages ──────────────────────────────────────────────────────────────────
section "packages"
# system_profiler SPApplicationsDataType is faster than pkgutil --pkg-info per-package
# Output format varies; we request XML and parse with awk for reliability, but
# the plain-text output is pipe-delimited enough for our purposes.
# Use -xml for structured output, parsed by the Python parser.
system_profiler SPApplicationsDataType 2>/dev/null \
    | awk -F': ' '
        /^    [^ ]/{
            # New top-level app block starts with a line that is indented exactly 4 spaces
            # and contains the app name (no colon suffix)
            if ($0 ~ /^    [^ ].+:$/) {
                if (appname != "") {
                    print appname "|" ver "|" vendor "|"
                }
                appname = $1
                gsub(/^ +| +:?$/, "", appname)
                ver = ""
                vendor = ""
            }
        }
        /Version:/{ver=$2; gsub(/^ +/, "", ver)}
        /Get Info String:|Obtained from:/{
            if (vendor == "") { vendor=$2; gsub(/^ +/, "", vendor) }
        }
        END {
            if (appname != "") print appname "|" ver "|" vendor "|"
        }
    '

# pkgutil receipts — covers CLI tools and packages installed via .pkg installers
pkgutil --pkgs 2>/dev/null \
    | while read -r pkg_id; do
        info=$(pkgutil --pkg-info "$pkg_id" 2>/dev/null) || continue
        ver=$(echo "$info" | awk -F': ' '/^version:/{print $2}')
        install_time=$(echo "$info" | awk -F': ' '/^install-time:/{print $2}')
        # Convert epoch to human-readable if numeric
        if [[ "$install_time" =~ ^[0-9]+$ ]]; then
            install_time=$(date -r "$install_time" "+%Y-%m-%d" 2>/dev/null || echo "$install_time")
        fi
        echo "${pkg_id}|${ver}||${install_time}"
    done

# Homebrew (if present) — format: name version
if command -v brew &>/dev/null; then
    brew list --versions 2>/dev/null \
        | awk '{print $1 "|" $2 "||"}'
fi

# ── Services ──────────────────────────────────────────────────────────────────
section "services"
# launchctl list: PID  LastExitStatus  Label
launchctl list 2>/dev/null || echo ""

# ── Filesystem ────────────────────────────────────────────────────────────────
section "filesystem"
df -P -k 2>/dev/null | tail -n +2 || true

section "filesystem_suid"
priv find / -xdev \( -perm -4000 -o -perm -2000 \) -type f 2>/dev/null | sort || true

# ── Security ──────────────────────────────────────────────────────────────────
section "security"
# SIP status (maps to selinux_mode: "enforcing" = enabled, "disabled" = disabled)
csrutil status 2>/dev/null || echo "unknown"
# FileVault status (maps to secure_boot field)
fdesetup status 2>/dev/null || echo "unknown"
# Gatekeeper status (maps to firewall_enabled)
spctl --status 2>/dev/null || echo "unknown"
# Application firewall global state
/usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate 2>/dev/null || echo "unknown"
# Auto-login check
defaults read /Library/Preferences/com.apple.loginwindow autoLoginUser 2>/dev/null || echo "disabled"
# MDM enrollment (requires root)
priv profiles -P 2>/dev/null | grep -c "profileIdentifier" || echo "0"
# Secure boot state: try Apple Silicon (bputil) then Intel (nvram)
if command -v bputil &>/dev/null; then
    priv bputil -d 2>/dev/null | grep -i "security mode" || echo ""
else
    priv nvram 94b73556-2197-4702-82a8-3e1337dafbfb:AppleSecureBootPolicy 2>/dev/null || echo ""
fi

# ── Scheduled Tasks ───────────────────────────────────────────────────────────
section "scheduled_tasks"
# LaunchDaemons and LaunchAgents — emit path|label|program for each plist
for dir in \
    /Library/LaunchDaemons \
    /Library/LaunchAgents \
    /System/Library/LaunchDaemons \
    /System/Library/LaunchAgents; do
    [ -d "$dir" ] || continue
    for plist in "$dir"/*.plist; do
        [ -f "$plist" ] || continue
        label=$(defaults read "$plist" Label 2>/dev/null || basename "$plist" .plist)
        program=$(defaults read "$plist" Program 2>/dev/null \
                  || defaults read "$plist" ProgramArguments 2>/dev/null \
                  | tr -d '(\n)' | xargs 2>/dev/null \
                  || echo "")
        disabled=$(defaults read "$plist" Disabled 2>/dev/null || echo "0")
        echo "${dir}|${label}|${program}|${disabled}"
    done
done
# Current user LaunchAgents
if [ -d ~/Library/LaunchAgents ]; then
    for plist in ~/Library/LaunchAgents/*.plist; do
        [ -f "$plist" ] || continue
        label=$(defaults read "$plist" Label 2>/dev/null || basename "$plist" .plist)
        program=$(defaults read "$plist" Program 2>/dev/null \
                  || defaults read "$plist" ProgramArguments 2>/dev/null \
                  | tr -d '(\n)' | xargs 2>/dev/null \
                  || echo "")
        disabled=$(defaults read "$plist" Disabled 2>/dev/null || echo "0")
        echo "~/Library/LaunchAgents|${label}|${program}|${disabled}"
    done
fi

# ── Listening Services ────────────────────────────────────────────────────────
section "listening_services"
# lsof: NAME column contains proto-addr:port; PID and USER columns present
lsof -nP -iTCP -iUDP -sTCP:LISTEN 2>/dev/null \
    || netstat -an 2>/dev/null | grep -E "LISTEN|udp" \
    || true

# ── Firewall Rules ────────────────────────────────────────────────────────────
section "firewall_rules"
priv /usr/libexec/ApplicationFirewall/socketfilterfw --listapps 2>/dev/null || echo ""

# ── Sysctl ────────────────────────────────────────────────────────────────────
section "sysctl"
# Filter out volatile per-interface keys (utun*, vmnet*, llw*, anpi*, ipsec*)
# as well as high-churn counters.  Keep stable kernel/vm/security keys.
sysctl -a 2>/dev/null \
    | grep -Ev '\.(utun[0-9]+|vmnet[0-9]+|llw[0-9]+|anpi[0-9]+|ipsec[0-9]+|gif[0-9]+|stf[0-9]+)(\.|[[:space:]]|$)' \
    | grep -Ev '^(kern\.boottime|kern\.clockrate)' \
    || echo ""

# ── Logging Targets ───────────────────────────────────────────────────────────
section "logging_targets"
# ASL / syslog remote targets
if [ -f /etc/asl.conf ]; then
    grep -v "^#" /etc/asl.conf | grep -v "^$" | grep ">" || true
fi
if [ -f /etc/syslog.conf ]; then
    grep -v "^#" /etc/syslog.conf | grep -v "^$" | grep "@" || true
fi
# Unified log configuration status
log config --status 2>/dev/null | grep -i "remote" || true

# ── SSH Config ────────────────────────────────────────────────────────────────
section "ssh_config"
grep -v "^#" /etc/ssh/sshd_config 2>/dev/null | grep -v "^$" || echo ""

# ── SSH Keys ──────────────────────────────────────────────────────────────────
section "ssh_keys"
dscl . -list /Users UniqueID 2>/dev/null \
    | awk '$2 >= 500 && $1 !~ /^_/{print $1}' \
    | while read -r uname; do
        home=$(dscl . -read "/Users/${uname}" NFSHomeDirectory 2>/dev/null \
               | awk '{print $2}')
        auth_keys="${home}/.ssh/authorized_keys"
        [ -f "$auth_keys" ] || continue
        while read -r line; do
            [[ "$line" =~ ^# ]] && continue
            [[ -z "$line" ]] && continue
            echo "${uname}|${line}"
        done < "$auth_keys"
    done

# ── Certificates ──────────────────────────────────────────────────────────────
section "certificates"
# Extract PEM certs from System keychain and annotate with openssl text headers
# Use priv because the System keychain is root-readable on most configurations
priv security find-certificate -a -p /Library/Keychains/System.keychain 2>/dev/null \
    | while IFS= read -r line; do
        echo "$line"
        if [ "$line" = "-----END CERTIFICATE-----" ]; then
            echo "##CERTBOUNDARY##"
        fi
    done || true

echo "${SEP}[END]"
