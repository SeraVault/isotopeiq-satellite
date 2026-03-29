#!/usr/bin/env expect
# Cisco IOS / IOS-XE Baseline Collector
# Gathers device configuration and state for the IsotopeIQ canonical schema.
# Each section is delimited by a [SECTION] marker for the parser.
#
# Delivery method: run as an Expect script over SSH or a direct console session.
# The script connects via SSH, issues show commands, then disconnects.
#
# Prerequisites: expect (any version ≥ 5.45), ssh access to the device.
#
# Usage (SSH):
#   DEVICE_HOST=192.0.2.1 DEVICE_USER=admin DEVICE_PASS=secret \
#     expect cisco_ios_baseline_collector.sh
#
# Usage with key-based auth:
#   DEVICE_HOST=192.0.2.1 DEVICE_USER=admin SSH_KEY=/path/to/key \
#     expect cisco_ios_baseline_collector.sh
#
# Placeholders substituted by IsotopeIQ before the script runs:
#   {{HOSTNAME}}      — device IP or hostname to connect to
#   {{USERNAME}}      — SSH username
#   {{PASSWORD}}      — SSH password (leave blank for key auth)
#   {{ENABLE_PASS}}   — enable password (leave blank if already privileged)
#   {{SSH_KEY}}       — path to private key file (optional)
#   {{SSH_PORT}}      — SSH port (default 22)

set timeout 30
set SEP "---ISOTOPEIQ---"

# ── Runtime configuration (injected by IsotopeIQ or set via env) ──────────────

set host     [expr {[info exists env(DEVICE_HOST)]  ? $env(DEVICE_HOST)  : "{{HOSTNAME}}"}]
set user     [expr {[info exists env(DEVICE_USER)]  ? $env(DEVICE_USER)  : "{{USERNAME}}"}]
set pass     [expr {[info exists env(DEVICE_PASS)]  ? $env(DEVICE_PASS)  : "{{PASSWORD}}"}]
set enpass   [expr {[info exists env(ENABLE_PASS)]  ? $env(ENABLE_PASS)  : "{{ENABLE_PASS}}"}]
set ssh_key  [expr {[info exists env(SSH_KEY)]      ? $env(SSH_KEY)      : "{{SSH_KEY}}"}]
set ssh_port [expr {[info exists env(SSH_PORT)]     ? $env(SSH_PORT)     : "22"}]

proc section {name} {
    global SEP
    puts "${SEP}\[${name}\]"
}

proc send_cmd {cmd} {
    send "$cmd\r"
    # Wait for a prompt: hostname# or hostname>
    expect -re {[>#]\s*$}
}

proc drain_output {} {
    # Flush any pending output and return it
    set buf ""
    while {[expect -timeout 1 -re {(.+)} ]} {
        append buf $expect_out(1,string)
    }
    return $buf
}

# ── Establish SSH connection ───────────────────────────────────────────────────

if {$ssh_key ne "" && $ssh_key ne "{{SSH_KEY}}"} {
    spawn ssh -o StrictHostKeyChecking=no \
              -o ConnectTimeout=15 \
              -i $ssh_key \
              -p $ssh_port \
              ${user}@${host}
} else {
    spawn ssh -o StrictHostKeyChecking=no \
              -o ConnectTimeout=15 \
              -p $ssh_port \
              ${user}@${host}
}

# Handle password prompt or key-based auth
expect {
    -re {[Pp]assword:} {
        send "$pass\r"
        exp_continue
    }
    -re {Are you sure.*\?} {
        send "yes\r"
        exp_continue
    }
    timeout {
        puts stderr "ERROR: Connection timed out"
        exit 1
    }
    -re {[>#]\s*$} {
        # Connected
    }
}

# Enter enable mode if not already privileged
expect -re {[>#]\s*$}
set prompt $expect_out(buffer)
if {[string match "*>" $prompt]} {
    send "enable\r"
    expect {
        -re {[Pp]assword:} {
            send "$enpass\r"
            expect -re {#\s*$}
        }
        -re {#\s*$} {}
    }
}

# Disable terminal paging so output is not interrupted
send_cmd "terminal length 0"
send_cmd "terminal width 0"

# ── Collect sections ──────────────────────────────────────────────────────────
# Each section() call emits the delimiter; send_cmd issues the IOS command
# and the expect pattern captures everything up to the next prompt.

# Helper: capture the output of a show command
proc collect {section_name cmd} {
    global SEP
    section $section_name
    send "$cmd\r"
    expect -re {[>#]\s*$}
    # Print captured output (strip the echoed command on the first line)
    set raw $expect_out(buffer)
    set lines [split $raw "\n"]
    # Drop the first line (echoed command) and the last line (prompt)
    set body [lrange $lines 1 end-1]
    puts [join $body "\n"]
    flush stdout
}

collect "version"         "show version"
collect "running_config"  "show running-config"
collect "interfaces"      "show interfaces"
collect "ip_interfaces"   "show ip interface brief"
collect "ip_int_detail"   "show ip interface"
collect "ip_routes"       "show ip route"
collect "ip_bgp_sum"      "show ip bgp summary"
collect "ip_ospf"         "show ip ospf"
collect "ip_ospf_neigh"   "show ip ospf neighbor"
collect "ip_eigrp_neigh"  "show ip eigrp neighbors"
collect "vlans"           "show vlan brief"
collect "spanning_tree"   "show spanning-tree"
collect "cdp_neighbors"   "show cdp neighbors detail"
collect "users_detail"    "show users"
collect "aaa_servers"     "show tacacs"
collect "aaa_radius"      "show radius server-group all"
collect "snmp_groups"     "show snmp group"
collect "snmp_users"      "show snmp user"
collect "snmp_community"  "show snmp community"
collect "access_lists"    "show access-lists"
collect "ip_nat"          "show ip nat translations"
collect "crypto_isakmp"   "show crypto isakmp sa"
collect "crypto_ipsec"    "show crypto ipsec sa"
collect "ntp_status"      "show ntp status"
collect "ntp_assoc"       "show ntp associations"
collect "clock"           "show clock detail"
collect "logging"         "show logging"
collect "processes_cpu"   "show processes cpu sorted"
collect "memory"          "show memory statistics"
collect "flash"           "show flash:"
collect "environment"     "show environment all"
collect "inventory"       "show inventory"
collect "boot"            "show boot"
collect "ip_ssh"          "show ip ssh"
collect "ip_scp"          "show ip scp server"
collect "line_config"     "show line"
collect "tcp_intercept"   "show ip inspect sessions brief"
collect "ip_access_int"   "show ip interface | include line|access list"

puts "${SEP}\[END\]"
flush stdout

send "exit\r"
expect eof
