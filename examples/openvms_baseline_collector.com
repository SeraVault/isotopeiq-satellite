$! OpenVMS Baseline Collector
$! Gathers system information for the IsotopeIQ canonical schema.
$! Each section is delimited by a [SECTION] marker for the parser.
$!
$! Compatibility: OpenVMS VAX 6.x+, Alpha 7.x+, Integrity (IA-64) 8.x+
$! No third-party tools required — uses only DCL built-ins and standard
$! OpenVMS utilities (SHOW, ANALYZE, SYSGEN, UAF, etc.).
$!
$! Usage:
$!   @ISOTOPEIQ_COLLECTOR.COM
$!
$! Privilege requirements:
$!   Most sections run as any user.  The following sections produce richer
$!   output when run with SYSPRV, BYPASS, or as SYSTEM:
$!     users, groups, security, scheduled_tasks (batch queues), sysctl
$!
$! Placeholders substituted by IsotopeIQ before the script runs:
$!   {{USERNAME}}   — credential username
$!   {{PASSWORD}}   — credential password
$!   {{HOSTNAME}}   — device node name
$!
$! Output format: key=value lines within each section.
$! Multi-value fields use a pipe-delimited list on a single value line.
$! Array sections (users, packages, etc.) emit one record per line using
$! the pipe delimiter: field1|field2|field3
$!
$! ── Suppress all DCL error output to keep stdout clean ───────────────────────
$ SET MESSAGE/NOFACILITY/NOIDENTIFICATION/NOSEVERITY/NOTEXT
$ ON ERROR THEN CONTINUE
$ ON WARNING THEN CONTINUE
$!
$ SEP = "---ISOTOPEIQ---"
$!
$! ── Helper: emit a section delimiter ─────────────────────────────────────────
$ SECTION:
$   SUBROUTINE
$   WRITE SYS$OUTPUT SEP + "[" + P1 + "]"
$   ENDSUBROUTINE
$!
$! ── Helper: run a command and suppress errors ─────────────────────────────────
$! (DCL's ON ERROR THEN CONTINUE handles this globally above)
$!
$! ────────────────────────────────────────────────────────────────────────────
$! DEVICE
$! ────────────────────────────────────────────────────────────────────────────
$ CALL SECTION "device"
$ WRITE SYS$OUTPUT "hostname=" + F$GETSYI("NODENAME")
$ WRITE SYS$OUTPUT "fqdn=" + F$GETSYI("NODENAME")
$ WRITE SYS$OUTPUT "device_type=server"
$!
$! Hardware manufacturer / model from SYS$SYSDEVICE logical
$ HW_MODEL = F$GETSYI("HW_MODEL")
$ HW_NAME  = F$GETSYI("HW_NAME")
$ WRITE SYS$OUTPUT "vendor=" + F$GETSYI("NODE_SWVERS")  !filled properly below
$ WRITE SYS$OUTPUT "model=" + HW_NAME
$!
$! ────────────────────────────────────────────────────────────────────────────
$! HARDWARE
$! ────────────────────────────────────────────────────────────────────────────
$ CALL SECTION "hardware"
$!
$! CPU model string — SHOW CPU gives verbose output; extract key fields
$ CPU_COUNT = F$GETSYI("ACTIVECPU_CNT")
$ IF CPU_COUNT .EQ. 0 THEN CPU_COUNT = F$GETSYI("CPU_AVAIL")
$ WRITE SYS$OUTPUT "cpu_model=" + HW_NAME
$ WRITE SYS$OUTPUT "cpu_cores=" + F$STRING(CPU_COUNT)
$!
$! Physical memory in MB from GETSYI MEMSIZE (pages * 512 bytes / 1MB)
$ MEM_PAGES = F$GETSYI("MEMSIZE")
$ MEM_GB    = F$INTEGER(MEM_PAGES * 512 / 1048576) / 1024.0
$ WRITE SYS$OUTPUT "memory_gb=" + F$STRING(MEM_GB)
$!
$! Firmware / SRM version
$ WRITE SYS$OUTPUT "bios_version=" + F$GETSYI("SID")
$!
$! Serial number (requires SYSPRV on some versions)
$ WRITE SYS$OUTPUT "serial_number=" + F$GETSYI("SER_NUM")
$!
$! Architecture
$ ARCH = F$GETSYI("ARCH_NAME")
$ WRITE SYS$OUTPUT "architecture=" + ARCH
$!
$! Virtualization — HPVM / VirtualBox / bare-metal
$ VIRT = "bare-metal"
$ IF F$GETSYI("HYPERVISOR") .NE. "" THEN VIRT = "other"
$ WRITE SYS$OUTPUT "virtualization_type=" + VIRT
$!
$! ────────────────────────────────────────────────────────────────────────────
$! OS
$! ────────────────────────────────────────────────────────────────────────────
$ CALL SECTION "os"
$ OS_NAME    = "OpenVMS"
$ OS_VERSION = F$GETSYI("VERSION")
$ WRITE SYS$OUTPUT "name=" + OS_NAME
$ WRITE SYS$OUTPUT "version=" + OS_VERSION
$ WRITE SYS$OUTPUT "build=" + F$GETSYI("BOOTTIME")
$ WRITE SYS$OUTPUT "kernel=" + OS_VERSION
$!
$! Timezone: read SYS$TIMEZONE_NAME logical
$ TZ = F$LOGICAL("SYS$TIMEZONE_NAME")
$ IF TZ .EQS. "" THEN TZ = F$LOGICAL("SYS$TIMEZONE_RULE")
$ WRITE SYS$OUTPUT "timezone=" + TZ
$!
$! NTP — check TCPIP$NTP_CONF or SYS$SPECIFIC:[TCPIP$NTP]NTP.CONF
$ NTP_SERVERS = ""
$ NTP_FILE    = "SYS$SPECIFIC:[TCPIP$NTP]NTP.CONF"
$ IF F$SEARCH(NTP_FILE) .NES. ""
$ THEN
$   OPEN/READ/ERROR=NTP_DONE NTP_UNIT 'NTP_FILE'
$   NTP_LOOP:
$     READ/END_OF_FILE=NTP_CLOSE NTP_UNIT NTP_LINE
$     NTP_LINE = F$EDIT(NTP_LINE, "COMPRESS,TRIM")
$     IF F$LOCATE("server ", NTP_LINE) .EQ. 0
$     THEN
$       NTP_HOST = F$ELEMENT(1, " ", NTP_LINE)
$       IF NTP_SERVERS .NES. "" THEN NTP_SERVERS = NTP_SERVERS + "|"
$       NTP_SERVERS = NTP_SERVERS + NTP_HOST
$     ENDIF
$     GOTO NTP_LOOP
$   NTP_CLOSE:
$     CLOSE NTP_UNIT
$   NTP_DONE:
$ ENDIF
$ WRITE SYS$OUTPUT "ntp_servers=" + NTP_SERVERS
$!
$! NTP sync status via TCPIP$NTP status
$ NTP_SYNC = "unknown"
$ DEFINE/USER SYS$ERROR NL:
$ TCPIP SHOW NTP/BRIEF >SYS$SCRATCH:IQ_NTP_STATUS.TMP
$ IF F$SEARCH("SYS$SCRATCH:IQ_NTP_STATUS.TMP") .NES. ""
$ THEN
$   OPEN/READ/ERROR=NTP_STAT_DONE NTP_STAT_U SYS$SCRATCH:IQ_NTP_STATUS.TMP
$   NTP_STAT_L:
$     READ/END_OF_FILE=NTP_STAT_C NTP_STAT_U NTP_STAT_LINE
$     IF F$LOCATE("synchronized", F$EDIT(NTP_STAT_LINE,"LOWERCASE")) .LT. F$LENGTH(NTP_STAT_LINE)
$     THEN
$       NTP_SYNC = "yes"
$       GOTO NTP_STAT_C
$     ENDIF
$     GOTO NTP_STAT_L
$   NTP_STAT_C:
$     CLOSE NTP_STAT_U
$   DELETE/NOLOG SYS$SCRATCH:IQ_NTP_STATUS.TMP;*
$   NTP_STAT_DONE:
$ ENDIF
$ WRITE SYS$OUTPUT "ntp_synced=" + NTP_SYNC
$!
$! ────────────────────────────────────────────────────────────────────────────
$! NETWORK — interfaces
$! ────────────────────────────────────────────────────────────────────────────
$ CALL SECTION "network_interfaces"
$! TCPIP SHOW INTERFACE outputs one block per interface
$ DEFINE/USER SYS$ERROR NL:
$ TCPIP SHOW INTERFACE >SYS$SCRATCH:IQ_IFACES.TMP
$ IF F$SEARCH("SYS$SCRATCH:IQ_IFACES.TMP") .NES. ""
$ THEN
$   TYPE SYS$SCRATCH:IQ_IFACES.TMP
$   DELETE/NOLOG SYS$SCRATCH:IQ_IFACES.TMP;*
$ ENDIF
$!
$! ────────────────────────────────────────────────────────────────────────────
$! NETWORK — routing
$! ────────────────────────────────────────────────────────────────────────────
$ CALL SECTION "network_routes"
$ DEFINE/USER SYS$ERROR NL:
$ TCPIP SHOW ROUTE >SYS$SCRATCH:IQ_ROUTES.TMP
$ IF F$SEARCH("SYS$SCRATCH:IQ_ROUTES.TMP") .NES. ""
$ THEN
$   TYPE SYS$SCRATCH:IQ_ROUTES.TMP
$   DELETE/NOLOG SYS$SCRATCH:IQ_ROUTES.TMP;*
$ ENDIF
$!
$! ────────────────────────────────────────────────────────────────────────────
$! NETWORK — DNS
$! ────────────────────────────────────────────────────────────────────────────
$ CALL SECTION "network_dns"
$ DEFINE/USER SYS$ERROR NL:
$ TCPIP SHOW NAME_SERVICE >SYS$SCRATCH:IQ_DNS.TMP
$ IF F$SEARCH("SYS$SCRATCH:IQ_DNS.TMP") .NES. ""
$ THEN
$   TYPE SYS$SCRATCH:IQ_DNS.TMP
$   DELETE/NOLOG SYS$SCRATCH:IQ_DNS.TMP;*
$ ENDIF
$!
$! ────────────────────────────────────────────────────────────────────────────
$! USERS  (from SYSUAF via AUTHORIZE)
$! Format: username|uic_group|uic_member|home|default_device|shell|disabled|priv
$! ────────────────────────────────────────────────────────────────────────────
$ CALL SECTION "users"
$! Dump SYSUAF to a scratch file using AUTHORIZE SHOW/FULL
$! Requires SYSPRV or running as SYSTEM for full output
$ DEFINE/USER SYS$ERROR NL:
$ MCR AUTHORIZE SHOW * /FULL >SYS$SCRATCH:IQ_UAF.TMP
$ IF F$SEARCH("SYS$SCRATCH:IQ_UAF.TMP") .NES. ""
$ THEN
$   TYPE SYS$SCRATCH:IQ_UAF.TMP
$   DELETE/NOLOG SYS$SCRATCH:IQ_UAF.TMP;*
$ ENDIF
$!
$! ────────────────────────────────────────────────────────────────────────────
$! RIGHTS IDENTIFIERS / GROUPS
$! Format: identifier|value|attributes
$! ────────────────────────────────────────────────────────────────────────────
$ CALL SECTION "groups"
$ DEFINE/USER SYS$ERROR NL:
$ MCR AUTHORIZE SHOW/RIGHTS * >SYS$SCRATCH:IQ_RIGHTS.TMP
$ IF F$SEARCH("SYS$SCRATCH:IQ_RIGHTS.TMP") .NES. ""
$ THEN
$   TYPE SYS$SCRATCH:IQ_RIGHTS.TMP
$   DELETE/NOLOG SYS$SCRATCH:IQ_RIGHTS.TMP;*
$ ENDIF
$!
$! ────────────────────────────────────────────────────────────────────────────
$! PACKAGES — installed products via PCSI (PRODUCT SHOW PRODUCT)
$! Format: name|version|producer|date
$! ────────────────────────────────────────────────────────────────────────────
$ CALL SECTION "packages"
$ DEFINE/USER SYS$ERROR NL:
$ PRODUCT SHOW PRODUCT */FULL >SYS$SCRATCH:IQ_PKGS.TMP
$ IF F$SEARCH("SYS$SCRATCH:IQ_PKGS.TMP") .NES. ""
$ THEN
$   TYPE SYS$SCRATCH:IQ_PKGS.TMP
$   DELETE/NOLOG SYS$SCRATCH:IQ_PKGS.TMP;*
$ ENDIF
$!
$! ────────────────────────────────────────────────────────────────────────────
$! SERVICES — detached processes and system services
$! Format: name|pid|status|image
$! ────────────────────────────────────────────────────────────────────────────
$ CALL SECTION "services"
$ SHOW SYSTEM /FULL
$!
$! ────────────────────────────────────────────────────────────────────────────
$! FILESYSTEM — disk devices
$! Format: device|label|total_blocks|free_blocks|used_pct|mount
$! ────────────────────────────────────────────────────────────────────────────
$ CALL SECTION "filesystem"
$ SHOW DEVICE /MOUNTED /FULL
$!
$! ────────────────────────────────────────────────────────────────────────────
$! SECURITY — system security parameters
$! ────────────────────────────────────────────────────────────────────────────
$ CALL SECTION "security"
$!
$! Intrusion detection / break-in evasion status
$ SHOW INTRUSION/FULL
$!
$! System password (exists / not exists)
$ HAS_SYSPWD = "no"
$ IF F$SEARCH("SYS$SYSTEM:SYSUAF.DAT") .NES. "" THEN HAS_SYSPWD = "yes"
$ WRITE SYS$OUTPUT "system_password_file=" + HAS_SYSPWD
$!
$! Security audit journal
$ AUDIT_FILE = F$SEARCH("SYS$MANAGER:SECURITY_AUDIT.AUDIT$JOURNAL")
$ IF AUDIT_FILE .NES. ""
$ THEN
$   WRITE SYS$OUTPUT "audit_journal=enabled"
$ ELSE
$   WRITE SYS$OUTPUT "audit_journal=disabled"
$ ENDIF
$!
$! SYSGEN parameters relevant to security
$ DEFINE/USER SYS$ERROR NL:
$ MCR SYSGEN SHOW UAFALTERNATE   >SYS$SCRATCH:IQ_SYSGEN1.TMP
$ MCR SYSGEN SHOW SECURITY_POLICY >>SYS$SCRATCH:IQ_SYSGEN1.TMP
$ MCR SYSGEN SHOW MAXBUF          >>SYS$SCRATCH:IQ_SYSGEN1.TMP
$ IF F$SEARCH("SYS$SCRATCH:IQ_SYSGEN1.TMP") .NES. ""
$ THEN
$   TYPE SYS$SCRATCH:IQ_SYSGEN1.TMP
$   DELETE/NOLOG SYS$SCRATCH:IQ_SYSGEN1.TMP;*
$ ENDIF
$!
$! Password policy from UAF defaults
$ DEFINE/USER SYS$ERROR NL:
$ MCR AUTHORIZE SHOW DEFAULT >SYS$SCRATCH:IQ_UAFDEF.TMP
$ IF F$SEARCH("SYS$SCRATCH:IQ_UAFDEF.TMP") .NES. ""
$ THEN
$   TYPE SYS$SCRATCH:IQ_UAFDEF.TMP
$   DELETE/NOLOG SYS$SCRATCH:IQ_UAFDEF.TMP;*
$ ENDIF
$!
$! ────────────────────────────────────────────────────────────────────────────
$! SCHEDULED TASKS — batch queues
$! Format: job_name|queue|status|username|command_file
$! ────────────────────────────────────────────────────────────────────────────
$ CALL SECTION "scheduled_tasks"
$ SHOW QUEUE /BATCH /FULL /ALL_JOBS
$!
$! ────────────────────────────────────────────────────────────────────────────
$! SYSCTL — SYSGEN tunable parameters (security / network relevant subset)
$! ────────────────────────────────────────────────────────────────────────────
$ CALL SECTION "sysctl"
$ DEFINE/USER SYS$ERROR NL:
$ MCR SYSGEN SHOW/ALL >SYS$SCRATCH:IQ_SYSGEN_ALL.TMP
$ IF F$SEARCH("SYS$SCRATCH:IQ_SYSGEN_ALL.TMP") .NES. ""
$ THEN
$   TYPE SYS$SCRATCH:IQ_SYSGEN_ALL.TMP
$   DELETE/NOLOG SYS$SCRATCH:IQ_SYSGEN_ALL.TMP;*
$ ENDIF
$!
$! ────────────────────────────────────────────────────────────────────────────
$! LISTENING SERVICES — open TCP/UDP sockets (TCPIP SHOW SERVICE)
$! ────────────────────────────────────────────────────────────────────────────
$ CALL SECTION "listening_services"
$ DEFINE/USER SYS$ERROR NL:
$ TCPIP SHOW SERVICE >SYS$SCRATCH:IQ_SVCS.TMP
$ IF F$SEARCH("SYS$SCRATCH:IQ_SVCS.TMP") .NES. ""
$ THEN
$   TYPE SYS$SCRATCH:IQ_SVCS.TMP
$   DELETE/NOLOG SYS$SCRATCH:IQ_SVCS.TMP;*
$ ENDIF
$!
$! ────────────────────────────────────────────────────────────────────────────
$! LOGGING TARGETS — TCPIP syslog configuration
$! ────────────────────────────────────────────────────────────────────────────
$ CALL SECTION "logging_targets"
$ SYSLOG_FILE = "TCPIP$ETC:SYSLOG.CONF"
$ IF F$SEARCH(SYSLOG_FILE) .NES. ""
$ THEN
$   OPEN/READ/ERROR=SYSLOG_DONE SYSLOG_U 'SYSLOG_FILE'
$   SYSLOG_LOOP:
$     READ/END_OF_FILE=SYSLOG_CLOSE SYSLOG_U SYSLOG_LINE
$     WRITE SYS$OUTPUT SYSLOG_LINE
$     GOTO SYSLOG_LOOP
$   SYSLOG_CLOSE:
$     CLOSE SYSLOG_U
$   SYSLOG_DONE:
$ ENDIF
$!
$! ────────────────────────────────────────────────────────────────────────────
$! SSH CONFIG — HP SSH / VSI SSH server configuration
$! ────────────────────────────────────────────────────────────────────────────
$ CALL SECTION "ssh_config"
$ SSH_CONF = "TCPIP$SSH_DEVICE:[TCPIP$SSH]SSH2_CONFIG.DAT"
$ IF F$SEARCH(SSH_CONF) .NES. ""
$ THEN
$   OPEN/READ/ERROR=SSH_DONE SSH_U 'SSH_CONF'
$   SSH_LOOP:
$     READ/END_OF_FILE=SSH_CLOSE SSH_U SSH_LINE
$     SSH_LINE = F$EDIT(SSH_LINE, "COMPRESS,TRIM")
$     IF F$EXTRACT(0,1,SSH_LINE) .NES. "#" THEN WRITE SYS$OUTPUT SSH_LINE
$     GOTO SSH_LOOP
$   SSH_CLOSE:
$     CLOSE SSH_U
$   SSH_DONE:
$ ENDIF
$! Also check VSI-SSH location
$ SSH_CONF2 = "SYS$SPECIFIC:[SSH2]SSHD2_CONFIG"
$ IF F$SEARCH(SSH_CONF2) .NES. ""
$ THEN
$   OPEN/READ/ERROR=SSH2_DONE SSH2_U 'SSH_CONF2'
$   SSH2_LOOP:
$     READ/END_OF_FILE=SSH2_CLOSE SSH2_U SSH2_LINE
$     SSH2_LINE = F$EDIT(SSH2_LINE, "COMPRESS,TRIM")
$     IF F$EXTRACT(0,1,SSH2_LINE) .NES. "#" THEN WRITE SYS$OUTPUT SSH2_LINE
$     GOTO SSH2_LOOP
$   SSH2_CLOSE:
$     CLOSE SSH2_U
$   SSH2_DONE:
$ ENDIF
$!
$! ────────────────────────────────────────────────────────────────────────────
$! SNMP — TCPIP SNMP configuration
$! ────────────────────────────────────────────────────────────────────────────
$ CALL SECTION "snmp"
$ DEFINE/USER SYS$ERROR NL:
$ TCPIP SHOW SNMP >SYS$SCRATCH:IQ_SNMP.TMP
$ IF F$SEARCH("SYS$SCRATCH:IQ_SNMP.TMP") .NES. ""
$ THEN
$   TYPE SYS$SCRATCH:IQ_SNMP.TMP
$   DELETE/NOLOG SYS$SCRATCH:IQ_SNMP.TMP;*
$ ENDIF
$!
$! ────────────────────────────────────────────────────────────────────────────
$! SHARES — NFS and SAMBA exports
$! ────────────────────────────────────────────────────────────────────────────
$ CALL SECTION "shares"
$ DEFINE/USER SYS$ERROR NL:
$ TCPIP SHOW NFS/SERVER/EXPORT >SYS$SCRATCH:IQ_NFS.TMP
$ IF F$SEARCH("SYS$SCRATCH:IQ_NFS.TMP") .NES. ""
$ THEN
$   TYPE SYS$SCRATCH:IQ_NFS.TMP
$   DELETE/NOLOG SYS$SCRATCH:IQ_NFS.TMP;*
$ ENDIF
$!
$! ────────────────────────────────────────────────────────────────────────────
$! CERTIFICATES — X.509 certificates in SSL certificate database
$! ────────────────────────────────────────────────────────────────────────────
$ CALL SECTION "certificates"
$ DEFINE/USER SYS$ERROR NL:
$ CRYPTO SHOW CERTIFICATE/FULL >SYS$SCRATCH:IQ_CERTS.TMP
$ IF F$SEARCH("SYS$SCRATCH:IQ_CERTS.TMP") .NES. ""
$ THEN
$   TYPE SYS$SCRATCH:IQ_CERTS.TMP
$   DELETE/NOLOG SYS$SCRATCH:IQ_CERTS.TMP;*
$ ENDIF
$!
$ WRITE SYS$OUTPUT "---ISOTOPEIQ---[END]"
$ EXIT
