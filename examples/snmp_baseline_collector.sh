#!/usr/bin/env bash
# SNMP Baseline Collector
# Gathers system information from a remote device via SNMP for the IsotopeIQ
# canonical schema.  Runs on the IsotopeIQ satellite (Linux host) and polls
# the target device remotely — no SSH/CLI access required.
#
# Each section is delimited by a ---ISOTOPEIQ---[SECTION] marker for the parser.
# Requires: snmpwalk, snmpget (net-snmp package on the satellite).
# Supports: SNMPv2c, SNMPv3 (noAuthNoPriv / authNoPriv / authPriv).

set -uo pipefail

# ── SNMP connection parameters ────────────────────────────────────────────────
# These placeholders are substituted by IsotopeIQ before the script runs.
# Do not hardcode secrets here.
#
#   {{HOSTNAME}}        — target device IP or DNS hostname
#   {{SNMP_VERSION}}    — "2c" or "3"
#   {{SNMP_COMMUNITY}}  — community string (v2c only)
#   {{SNMP_USER}}       — SNMPv3 username
#   {{SNMP_AUTH_PROTO}} — SNMPv3 auth protocol: MD5 or SHA
#   {{SNMP_AUTH_PASS}}  — SNMPv3 auth passphrase
#   {{SNMP_PRIV_PROTO}} — SNMPv3 priv protocol: DES or AES
#   {{SNMP_PRIV_PASS}}  — SNMPv3 priv passphrase
#   {{SNMP_SEC_LEVEL}}  — noAuthNoPriv | authNoPriv | authPriv

TARGET="${TARGET:-{{HOSTNAME}}}"
SNMP_VERSION="${SNMP_VERSION:-{{SNMP_VERSION}}}"
SNMP_COMMUNITY="${SNMP_COMMUNITY:-{{SNMP_COMMUNITY}}}"
SNMP_USER="${SNMP_USER:-{{SNMP_USER}}}"
SNMP_AUTH_PROTO="${SNMP_AUTH_PROTO:-{{SNMP_AUTH_PROTO}}}"
SNMP_AUTH_PASS="${SNMP_AUTH_PASS:-{{SNMP_AUTH_PASS}}}"
SNMP_PRIV_PROTO="${SNMP_PRIV_PROTO:-{{SNMP_PRIV_PROTO}}}"
SNMP_PRIV_PASS="${SNMP_PRIV_PASS:-{{SNMP_PRIV_PASS}}}"
SNMP_SEC_LEVEL="${SNMP_SEC_LEVEL:-{{SNMP_SEC_LEVEL}}}"

# Common snmpwalk/snmpget options: numeric OIDs (-Oqn), no retries on timeout,
# short timeout so unreachable devices fail fast and don't block collection.
SNMP_COMMON_OPTS="-Oqn -t 5 -r 1 -m ALL"

SEP="---ISOTOPEIQ---"
section() { echo "${SEP}[$1]"; }

# ── v2c / v3 argument builders ────────────────────────────────────────────────

_v2c_args() {
    echo "-v 2c -c ${SNMP_COMMUNITY}"
}

_v3_args() {
    local args="-v 3 -u ${SNMP_USER} -l ${SNMP_SEC_LEVEL}"
    case "${SNMP_SEC_LEVEL}" in
        authNoPriv)
            args="${args} -a ${SNMP_AUTH_PROTO} -A ${SNMP_AUTH_PASS}"
            ;;
        authPriv)
            args="${args} -a ${SNMP_AUTH_PROTO} -A ${SNMP_AUTH_PASS}"
            args="${args} -x ${SNMP_PRIV_PROTO} -X ${SNMP_PRIV_PASS}"
            ;;
        # noAuthNoPriv — no extra flags needed
    esac
    echo "${args}"
}

_snmp_version_args() {
    if [ "${SNMP_VERSION}" = "3" ]; then
        _v3_args
    else
        _v2c_args
    fi
}

# snmpwalk_oid <OID>
# Walk an OID subtree.  Numeric output (-Oqn) so the parser always has raw
# OID=value lines regardless of local MIB resolution.  Never exits non-zero.
snmpwalk_oid() {
    local oid="$1"
    # shellcheck disable=SC2046
    snmpwalk ${SNMP_COMMON_OPTS} $(_snmp_version_args) "${TARGET}" "${oid}" 2>/dev/null || true
}

# snmpget_oid <OID> [OID ...]
# Fetch one or more scalar OIDs in a single PDU.  Never exits non-zero.
snmpget_oid() {
    # shellcheck disable=SC2046
    snmpget ${SNMP_COMMON_OPTS} $(_snmp_version_args) "${TARGET}" "$@" 2>/dev/null || true
}

# ── system_metadata ───────────────────────────────────────────────────────────
# Emitted first; the parser uses these for vendor/model detection before
# processing any other section.
section "system_metadata"
snmpget_oid \
    .1.3.6.1.2.1.1.1.0 \
    .1.3.6.1.2.1.1.2.0 \
    .1.3.6.1.2.1.1.3.0 \
    .1.3.6.1.2.1.1.5.0 \
    .1.3.6.1.2.1.1.4.0 \
    .1.3.6.1.2.1.1.6.0

# ── device ────────────────────────────────────────────────────────────────────
# RFC 1213 / SNMPv2-MIB system group + Entity MIB chassis row
section "device"
# System group scalars (already retrieved above, re-fetch for section isolation)
snmpget_oid \
    .1.3.6.1.2.1.1.5.0 \
    .1.3.6.1.2.1.1.1.0 \
    .1.3.6.1.2.1.1.2.0 \
    .1.3.6.1.2.1.1.4.0 \
    .1.3.6.1.2.1.1.6.0
# Entity MIB: physical description, serial, manufacturer, SW rev, FW rev
# (full subtrees — parser picks chassis row = row 1 or lowest index)
snmpwalk_oid .1.3.6.1.2.1.47.1.1.1.1.2   # entPhysicalDescr
snmpwalk_oid .1.3.6.1.2.1.47.1.1.1.1.11  # entPhysicalSerialNum
snmpwalk_oid .1.3.6.1.2.1.47.1.1.1.1.12  # entPhysicalMfgName
snmpwalk_oid .1.3.6.1.2.1.47.1.1.1.1.10  # entPhysicalSoftwareRev
snmpwalk_oid .1.3.6.1.2.1.47.1.1.1.1.9   # entPhysicalFirmwareRev

# ── interfaces ────────────────────────────────────────────────────────────────
section "interfaces"
# ifTable: index, descr, type, mtu, speed, physAddress, adminStatus, operStatus
snmpwalk_oid .1.3.6.1.2.1.2.2
# ifXTable: ifAlias (interface description), ifHighSpeed
snmpwalk_oid .1.3.6.1.2.1.31.1.1
# ipAddrTable: IP addresses assigned to interfaces
snmpwalk_oid .1.3.6.1.2.1.4.20

# ── routes ────────────────────────────────────────────────────────────────────
section "routes"
# Classic ipRouteTable (RFC 1213)
snmpwalk_oid .1.3.6.1.2.1.4.21
# IP-FORWARD-MIB inetCidrRouteTable (preferred on modern devices)
snmpwalk_oid .1.3.6.1.2.1.4.24.7

# ── network_dns ───────────────────────────────────────────────────────────────
# Best-effort: HOST-RESOURCES-MIB does not define a DNS table, so we attempt
# vendor-specific OIDs commonly used by Cisco/Juniper/generic.
section "network_dns"
# Cisco IOS: ciiIPAddressTable resolver entries (best-effort)
snmpwalk_oid .1.3.6.1.4.1.9.2.11.17  2>/dev/null || true
# Generic: try ipDomainName and ipDefaultRouterTable — no standard DNS OID,
# emit sysDescr again so the parser can note the absence.
snmpget_oid .1.3.6.1.2.1.1.1.0 2>/dev/null || true

# ── packages — installed software (HOST-RESOURCES-MIB) ───────────────────────
section "packages"
# hrSWInstalledTable: name, version, install date
snmpwalk_oid .1.3.6.1.2.1.25.6.3.1

# ── services — running processes (HOST-RESOURCES-MIB) ────────────────────────
section "services"
# hrSWRunTable: process name and run-status
snmpwalk_oid .1.3.6.1.2.1.25.4.2.1

# ── filesystem — storage (HOST-RESOURCES-MIB) ────────────────────────────────
section "filesystem"
# hrStorageTable: type, description, allocation unit, size, used
snmpwalk_oid .1.3.6.1.2.1.25.2.3.1

# ── cpu_memory ────────────────────────────────────────────────────────────────
section "cpu_memory"
# hrProcessorLoad: one row per CPU
snmpwalk_oid .1.3.6.1.2.1.25.3.3.1.2
# hrStorageTable already collected above — re-walk for RAM type filtering
snmpwalk_oid .1.3.6.1.2.1.25.2.3.1

# ── vlans ─────────────────────────────────────────────────────────────────────
section "vlans"
# Cisco VTP MIB: vtpVlanTable (vtpVlanState, vtpVlanName)
snmpwalk_oid .1.3.6.1.4.1.9.9.46.1.3.1
# Q-BRIDGE-MIB fallback: dot1qVlanStaticTable
snmpwalk_oid .1.3.6.1.2.1.17.7.1.4.3

# ── snmp_info ─────────────────────────────────────────────────────────────────
section "snmp_info"
# SNMP-TARGET-MIB: configured trap destinations
snmpwalk_oid .1.3.6.1.6.3.12.1.2
# SNMP-VIEW-BASED-ACM-MIB: security model info
snmpwalk_oid .1.3.6.1.6.3.16.1.2

# ── bgp ───────────────────────────────────────────────────────────────────────
section "bgp"
# BGP4-MIB: bgpPeerTable (state, remoteAs, remoteAddr)
snmpwalk_oid .1.3.6.1.2.1.15.3

# ── ospf ──────────────────────────────────────────────────────────────────────
section "ospf"
# OSPF-MIB: ospfNbrTable (neighborIpAddr, state)
snmpwalk_oid .1.3.6.1.2.1.14.10

echo "${SEP}[END]"
