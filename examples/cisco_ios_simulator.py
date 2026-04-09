# flake8: noqa: E501
"""
Cisco IOS SSH Simulator
========================
A fake Cisco IOS device that listens on SSH and responds to the exact
commands issued by cisco_ios_baseline_collector.py.

Usage:
    python3 cisco_ios_simulator.py [--host 127.0.0.1] [--port 2222] \\
        [--username cisco] [--password cisco] [--enable-password cisco] \\
        [--host-key cisco_sim_host_key]

    A 2048-bit RSA host key is auto-generated on first run and written to
    the path given by --host-key so subsequent runs reuse the same key
    (avoids host-key-mismatch errors if you pin the key in Satellite).

Point your Satellite device at 127.0.0.1:2222 with credentials
cisco/cisco (enable: cisco).  The session starts in user EXEC mode (>)
so the collector's enable-mode flow is fully exercised.

Dependencies:  paramiko  (already in the project venv)
"""

import argparse
import logging
import os
import socket
import textwrap
import threading
import time

import paramiko

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
)
log = logging.getLogger('cisco-sim')

# ── Fake show-command responses ───────────────────────────────────────────────
# Keys match exactly what cisco_ios_baseline_collector.py sends.

RESPONSES = {
    'show version': textwrap.dedent("""\
        Cisco IOS Software, Version 15.2(4)M7, RELEASE SOFTWARE (fc4)
        Technical Support: http://www.cisco.com/techsupport
        Copyright (c) 1986-2014 by Cisco Systems, Inc.
        Compiled Wed 26-Mar-14 21:38 by prod_rel_team

        ROM: System Bootstrap, Version 15.0(1r)M15, RELEASE SOFTWARE (fc1)

        SIMULATOR uptime is 42 days, 3 hours, 7 minutes
        System returned to ROM by power-on
        System image file is "flash:c2900-universalk9-mz.SPA.152-4.M7.bin"
        Last reload type: Normal Reload

        cisco CISCO2911/K9 (revision 1.0) with 491520K/32768K bytes of memory.
        Processor board ID FTX1700AHEM
        3 Gigabit Ethernet interfaces
        DRAM configuration is 64 bits wide with parity disabled.
        255K bytes of non-volatile configuration memory.
        250880K bytes of ATA System CompactFlash 0 (Read/Write)

        License UDI:
        -------------------------------------------------
        Device#   PID                   SN
        -------------------------------------------------
        *0        CISCO2911/K9          FTX1700AHEM

        Technology Package License Information for Module:'c2900'

        Technology    Technology-package           Technology-package
                      Current       Type           Next reboot
        ---------------------------------------------------------------
        ipbase        ipbasek9       Permanent       ipbasek9
        security      securityk9     Permanent       securityk9
        data          datak9         Permanent       datak9

        Configuration register is 0x2102"""),

    'show running-config': textwrap.dedent("""\
        Building configuration...

        Current configuration : 4821 bytes
        !
        version 15.2
        service timestamps debug datetime msec
        service timestamps log datetime msec
        no service password-encryption
        !
        hostname SIMULATOR
        !
        enable secret 5 $1$mERr$fakehashedpassword
        !
        no aaa new-model
        ip cef
        !
        interface GigabitEthernet0/0
         ip address 192.168.1.1 255.255.255.0
         ip access-group ACL_IN in
         duplex auto
         speed auto
        !
        interface GigabitEthernet0/1
         ip address 10.0.0.1 255.255.255.0
         duplex auto
         speed auto
        !
        interface GigabitEthernet0/2
         no ip address
         shutdown
        !
        router ospf 1
         router-id 1.1.1.1
         network 192.168.1.0 0.0.0.255 area 0
         network 10.0.0.0 0.0.0.255 area 0
        !
        ip access-list standard ACL_IN
         permit 192.168.1.0 0.0.0.255
         deny   any
        !
        snmp-server community public RO
        snmp-server community private RW
        ntp server 192.168.1.254
        !
        line con 0
        line vty 0 4
         login local
         transport input ssh
        !
        end"""),

    'show interfaces': textwrap.dedent("""\
        GigabitEthernet0/0 is up, line protocol is up
          Hardware is CN Gigabit Ethernet, address is aabb.cc00.0100
          Description: Uplink to Core
          Internet address is 192.168.1.1/24
          MTU 1500 bytes, BW 1000000 Kbit/sec, DLY 10 usec,
             reliability 255/255, txload 1/255, rxload 1/255
          Encapsulation ARPA, loopback not set
          Full Duplex, 1000Mbps, media type is RJ45
          5 minute input rate 1000 bits/sec, 1 packets/sec
          5 minute output rate 500 bits/sec, 0 packets/sec
             123456 packets input, 9876543 bytes, 0 no buffer
             654321 packets output, 5432100 bytes, 0 underruns
        GigabitEthernet0/1 is up, line protocol is up
          Hardware is CN Gigabit Ethernet, address is aabb.cc00.0101
          Internet address is 10.0.0.1/24
          MTU 1500 bytes, BW 1000000 Kbit/sec, DLY 10 usec,
             reliability 255/255, txload 1/255, rxload 1/255
        GigabitEthernet0/2 is administratively down, line protocol is down
          Hardware is CN Gigabit Ethernet, address is aabb.cc00.0102
          MTU 1500 bytes, BW 1000000 Kbit/sec, DLY 10 usec,
             reliability 255/255, txload 1/255, rxload 1/255"""),

    'show ip interface brief': textwrap.dedent("""\
        Interface            IP-Address    OK? Method Status           Protocol
        GigabitEthernet0/0   192.168.1.1   YES NVRAM  up               up
        GigabitEthernet0/1   10.0.0.1      YES NVRAM  up               up
        GigabitEthernet0/2   unassigned    YES NVRAM  administratively down down"""),

    'show ip interface': textwrap.dedent("""\
        GigabitEthernet0/0 is up, line protocol is up
          Internet address is 192.168.1.1/24
          Broadcast address is 255.255.255.255
          Outgoing access list is not set
          Inbound  access list is ACL_IN
          Proxy ARP is enabled
          Split horizon is enabled
          ICMP redirects are always sent
          IP CEF switching is enabled
        GigabitEthernet0/1 is up, line protocol is up
          Internet address is 10.0.0.1/24
          Broadcast address is 255.255.255.255
          Outgoing access list is not set
          Inbound  access list is not set"""),

    'show ip route': textwrap.dedent("""\
        Codes: L - local, C - connected, S - static, O - OSPF

        Gateway of last resort is 192.168.1.254 to network 0.0.0.0

        S*    0.0.0.0/0 [1/0] via 192.168.1.254
              10.0.0.0/8 is variably subnetted, 2 subnets, 2 masks
        C        10.0.0.0/24 is directly connected, GigabitEthernet0/1
        L        10.0.0.1/32 is directly connected, GigabitEthernet0/1
              192.168.1.0/24 is variably subnetted, 2 subnets, 2 masks
        C        192.168.1.0/24 is directly connected, GigabitEthernet0/0
        L        192.168.1.1/32 is directly connected, GigabitEthernet0/0
        O     172.16.0.0/16 [110/2] via 192.168.1.2, 1d03h, GigabitEthernet0/0"""),

    'show ip bgp summary': '% BGP not active',

    'show ip ospf': textwrap.dedent("""\
        Routing Process "ospf 1" with ID 1.1.1.1
        Start time: 00:00:03.456, Time elapsed: 1d03h
        Number of areas in this router is 1. 1 normal 0 stub 0 nssa
        Reference bandwidth unit is 100 mbps
           Area BACKBONE(0)
               Number of interfaces in this area is 2
               Area has no authentication
               SPF algorithm last executed 00:01:23.456 ago
               Number of LSA 3. Checksum Sum 0x02A1B3"""),

    'show ip ospf neighbor': textwrap.dedent("""\
        Neighbor ID  Pri  State    Dead Time  Address      Interface
        2.2.2.2        1  FULL/DR  00:00:37   192.168.1.2  GigabitEthernet0/0"""),

    'show ip eigrp neighbors': '% EIGRP not running',

    'show vlan brief': textwrap.dedent("""\
        VLAN Name                             Status    Ports
        ---- -------------------------------- --------- ----------------------------
        1    default                          active    Gi0/0, Gi0/1
        10   MANAGEMENT                       active
        20   SERVERS                          active
        30   USERS                            active
        1002 fddi-default                     act/unsup
        1003 token-ring-default               act/unsup"""),

    'show spanning-tree': textwrap.dedent("""\
        VLAN0001
          Spanning tree enabled protocol ieee
          Root ID    Priority    32769
                     Address     aabb.cc00.0100
                     This bridge is the root
                     Hello Time   2 sec  Max Age 20 sec  Forward Delay 15 sec

          Bridge ID  Priority    32769  (priority 32768 sys-id-ext 1)
                     Address     aabb.cc00.0100
                     Hello Time   2 sec  Max Age 20 sec  Forward Delay 15 sec
                     Aging Time  300 sec

        Interface     Role Sts Cost  Prio.Nbr Type
        ------------- ---- --- ----- -------- ----
        Gi0/0         Desg FWD 4     128.1    P2p
        Gi0/1         Desg FWD 4     128.2    P2p"""),

    'show cdp neighbors detail': textwrap.dedent("""\
        -------------------------
        Device ID: SW-CORE-01
        Entry address(es):
          IP address: 192.168.1.2
        Platform: cisco WS-C3750X-48P,  Capabilities: Switch IGMP
        Interface: GigabitEthernet0/0,  Port ID (outgoing port): Gi1/0/1
        Holdtime : 145 sec

        Version :
        Cisco IOS Software, Version 12.2(55)SE12, RELEASE SOFTWARE (fc2)

        advertisement version: 2
        Native VLAN: 1
        Duplex: full
        Management address(es):
          IP address: 192.168.1.2"""),

    'show users': textwrap.dedent("""\
            Line       User       Host(s)         Idle       Location
        *  0 con 0                idle            00:00:00
           2 vty 0    admin      192.168.1.100   00:01:15"""),

    'show tacacs': textwrap.dedent("""\
        Tacacs+ Server : 192.168.1.50
                         Socket opens:       10
                         Total packets sent: 50
                         Total packets recv: 50"""),

    'show radius server-group all': textwrap.dedent("""\
        Server group radius
            Sharecount = 1  sg_unconfigured = FALSE
            Type       = standard
            Server(0) : public:AAA/RADIUS/SERVER(0x0)
                        server 192.168.1.51 auth-port 1812 acct-port 1813"""),

    'show snmp group': textwrap.dedent("""\
        groupname: public              security model:v1
        readview : v1default           writeview: <no writeview specified>
        row status: active

        groupname: public              security model:v2c
        readview : v1default           writeview: <no writeview specified>
        row status: active"""),

    'show snmp user': textwrap.dedent("""\
        User name: admin
        Engine ID: 800000090300AABBCC000100
        storage-type: nonvolatile   active
        Authentication Protocol: SHA
        Privacy Protocol: AES128
        Group-name: NETWORK-ADMIN"""),

    'show snmp community': textwrap.dedent("""\
        Community name: public
        Community Index: cisco0
        Community SecurityName: public
        storage-type: nonvolatile   active

        Community name: private
        Community Index: cisco1
        Community SecurityName: private
        storage-type: nonvolatile   active"""),

    'show access-lists': textwrap.dedent("""\
        Standard IP access list ACL_IN
            10 permit 192.168.1.0, wildcard bits 0.0.0.255
            20 deny   any
        Extended IP access list MGMT_ACCESS
            10 permit tcp 192.168.1.0 0.0.0.255 any eq 22
            20 permit tcp 192.168.1.0 0.0.0.255 any eq 443
            30 deny   ip any any"""),

    'show ip nat translations': textwrap.dedent("""\
        Pro  Inside global    Inside local      Outside local   Outside global
        tcp  203.0.113.1:54321 192.168.1.100:54321 93.184.216.34:80 93.184.216.34:80"""),

    'show crypto isakmp sa': textwrap.dedent("""\
        IPv4 Crypto ISAKMP SA
        dst          src          state    conn-id status
        203.0.113.2  203.0.113.1  QM_IDLE  1001    ACTIVE"""),

    'show crypto ipsec sa': textwrap.dedent("""\
        interface: GigabitEthernet0/0
            Crypto map tag: VPN_MAP, local addr 203.0.113.1
           local  ident: (192.168.1.0/255.255.255.0/0/0)
           remote ident: (10.0.0.0/255.255.255.0/0/0)
           current_peer 203.0.113.2 port 500
            #pkts encaps: 12345, #pkts encrypt: 12345
            #pkts decaps: 23456, #pkts decrypt: 23456"""),

    'show ntp status': textwrap.dedent("""\
        Clock is synchronized, stratum 3, reference is 192.168.1.254
        nominal freq is 250.0000 Hz, actual freq is 250.0001 Hz
        reference time is E1234567.89ABCDEF (09:15:23.537 UTC Thu Apr 9 2026)
        clock offset is -0.5000 msec, root delay is 2.14 msec
        system poll interval is 1024, last update was 512 sec ago."""),

    'show ntp associations': textwrap.dedent("""\
          address        ref clock    st  when  poll reach delay  offset  disp
        *~192.168.1.254  10.0.0.254    2   512  1024   377  2.142  -0.500  0.478
         + = selected, * = sys.peer, # = selected, ~ = configured"""),

    'show clock detail': textwrap.dedent("""\
        09:15:23.537 UTC Thu Apr 9 2026
        Time source is NTP
        Summer time disabled"""),

    'show logging': textwrap.dedent("""\
        Syslog logging: enabled (0 messages dropped, 3 messages rate-limited)
            Console logging: level debugging, 42 messages logged
            Buffer logging:  level debugging, 42 messages logged
            Trap logging: level informational, 42 message lines logged
                Logging to 192.168.1.50  (udp port 514)

        Log Buffer (8192 bytes):
        Apr  9 09:00:00.000: %SYS-5-CONFIG_I: Configured from console by admin
        Apr  9 09:01:00.000: %OSPF-5-ADJCHG: Process 1, Nbr 2.2.2.2 FULL"""),

    'show processes cpu sorted': textwrap.dedent("""\
        CPU utilization for five seconds: 2%/1%; one minute: 3%; five minutes: 2%
         PID Runtime(ms) Invoked  uSecs  5Sec  1Min  5Min TTY Process
           1          52     627     82  0.00% 0.00% 0.00%   0 Chunk Manager
           2         736    5162    142  0.00% 0.00% 0.00%   0 Load Meter
          30       17384  393049     44  0.15% 0.12% 0.10%   0 ARP Input
          55        7820  152749     51  0.07% 0.06% 0.05%   0 IP Input
         842       12345  987654     12  0.31% 0.28% 0.24%   0 OSPF Router"""),

    'show memory statistics': textwrap.dedent("""\
                 Head    Total(b)    Used(b)    Free(b)   Lowest(b)  Largest(b)
        Processor 7F12AB34 503316480 123456789 379859691  350000000  378000000
             I/O  7F56CD78 104857600  52428800  52428800   52000000   52000000"""),

    'show flash:': textwrap.dedent("""\
        -#- --length-- -----date/time------ path
          1   43867976 Apr  1 2026 10:00:00 c2900-universalk9-mz.SPA.152-4.M7.bin
          2       4096 Apr  1 2026 10:01:00 home

        253255680 bytes available (44957696 bytes used)"""),

    'show environment all': textwrap.dedent("""\
        SYSTEM TEMPERATURE is OK
        Temperature Value: 38 Degree Celsius
        Temperature State: GREEN
        Yellow Threshold : 60 Degree Celsius
        Red Threshold    : 75 Degree Celsius
        POWER SUPPLY 0 is OK
        POWER SUPPLY 1 is ABSENT
        FAN 0 is OK"""),

    'show inventory': textwrap.dedent("""\
        NAME: "Chassis", DESCR: "Cisco 2911 Chassis"
        PID: CISCO2911/K9      , VID: V02  , SN: FTX1700AHEM

        NAME: "WIC/HWIC Slot 0", DESCR: "WIC-2T Serial WAN Interface Card"
        PID: WIC-2T            , VID: V02  , SN: FOC1234X5Y6"""),

    'show boot': textwrap.dedent("""\
        BOOT path-list      : flash:c2900-universalk9-mz.SPA.152-4.M7.bin
        Config file         : flash:running-config
        Enable Break        : yes
        Manual Boot         : no
        Auto upgrade        : yes"""),

    'show ip ssh': textwrap.dedent("""\
        SSH Enabled - version 2.0
        Authentication timeout: 60 secs; Authentication retries: 3
        Minimum expected Diffie Hellman key size : 1024 bits"""),

    'show ip scp server': 'SCP server is not active',

    'show line': textwrap.dedent("""\
           Tty Typ     Tx/Rx    A Roty AccO AccI   Uses   Noise  Overruns   Int
             0 CTY              -    -    -    -      0       0     0/0       -
             1 AUX   9600/9600  -    -    -    -      0       0     0/0       -
           130 VTY              -    -    -    -      1       0     0/0       -
           131 VTY              -    -    -    -      0       0     0/0       -"""),

    'show ip inspect sessions brief': textwrap.dedent("""\
        Established Sessions
         Session 7F12AB34 (192.168.1.100:54321)=>(93.184.216.34:80) http SIS_OPEN"""),

    'show ip interface | include line|access list': textwrap.dedent("""\
        GigabitEthernet0/0 is up, line protocol is up
          Inbound  access list is ACL_IN
        GigabitEthernet0/1 is up, line protocol is up
          Inbound  access list is not set"""),
}

# Commands that require privileged EXEC mode (#)
PRIV_ONLY = {
    'show running-config',
    'show ip nat translations',
    'show crypto isakmp sa',
    'show crypto ipsec sa',
    'show ip inspect sessions brief',
    'show memory statistics',
    'show flash:',
    'show environment all',
}


# ── Response lookup ───────────────────────────────────────────────────────────

def _lookup(cmd: str):
    """Return the canned response string or None (case-insensitive)."""
    key = cmd.strip()
    if key in RESPONSES:
        return RESPONSES[key]
    key_lower = key.lower()
    for k, v in RESPONSES.items():
        if k.lower() == key_lower:
            return v
    return None


# ── SSH server interface ──────────────────────────────────────────────────────

class _IOSServerInterface(paramiko.ServerInterface):
    def __init__(self, username: str, password: str):
        self._username = username
        self._password = password
        self.shell_event = threading.Event()

    def check_channel_request(self, kind, chanid):
        if kind == 'session':
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_auth_password(self, username, password):
        if username == self._username and password == self._password:
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def check_auth_publickey(self, username, key):
        return paramiko.AUTH_FAILED

    def get_allowed_auths(self, username):
        return 'password'

    def check_channel_shell_request(self, channel):
        self.shell_event.set()
        return True

    def check_channel_exec_request(self, channel, command):
        # exec_command is used by SSHCollector.run() for the test-connection ping.
        # Must respond in a thread — channel isn't fully open inside this callback.
        def _reply():
            time.sleep(0.05)
            try:
                channel.send_exit_status(0)
                channel.close()
            except Exception:
                pass
        threading.Thread(target=_reply, daemon=True).start()
        return True

    def check_channel_pty_request(
        self, channel, term, width, height, pixelwidth, pixelheight, modes
    ):
        return True


# ── IOS interactive shell ─────────────────────────────────────────────────────

def _ios_shell(
    channel: paramiko.Channel,
    enable_password: str,
    hostname: str = 'SIMULATOR',
):
    """
    Emulate an IOS interactive shell.

    State machine:
      - Starts in user EXEC mode  HOSTNAME>
      - 'enable' prompts for password; correct answer → HOSTNAME#
      - 'terminal length/width' silently accepted
      - All COMMANDS from the collector are looked up in RESPONSES
      - Unknown commands → IOS-style error marker
      - 'exit' / 'logout' → closes channel
    """
    privileged = False

    def tx(text: str):
        try:
            channel.sendall(text.encode('utf-8', errors='replace'))
        except OSError:
            pass

    def prompt():
        return f'{hostname}{"#" if privileged else ">"} '

    tx(
        '\r\nCisco IOS Software, Version 15.2(4)M7\r\n'
        f'Welcome to {hostname}\r\n\r\n'
    )
    tx(prompt())

    buf = ''
    awaiting_enable_pass = False

    while True:
        try:
            if getattr(channel, 'closed', False):
                break
            if not channel.recv_ready():
                time.sleep(0.01)
                continue
            data = channel.recv(512)
            if not data:
                break
        except OSError:
            break

        for ch in data.decode('utf-8', errors='replace'):
            if ch in ('\r', '\n'):
                line = buf.strip()
                buf = ''

                if awaiting_enable_pass:
                    tx('\r\n')
                    if line == enable_password or enable_password == '':
                        privileged = True
                    else:
                        tx('% Access denied\r\n')
                    awaiting_enable_pass = False
                    tx(prompt())
                    continue

                tx('\r\n')
                lower = line.lower()

                if not lower:
                    pass  # blank line — just re-print prompt

                elif lower in ('exit', 'quit', 'logout'):
                    tx('Goodbye.\r\n')
                    try:
                        channel.close()
                    except (OSError, EOFError):
                        pass
                    return

                elif lower == 'enable':
                    if not privileged:
                        tx('Password: ')
                        awaiting_enable_pass = True
                        continue  # skip prompt — sent after password

                elif lower == 'disable':
                    privileged = False

                elif (
                    lower.startswith('terminal length')
                    or lower.startswith('terminal width')
                ):
                    pass  # silently absorb terminal setup

                else:
                    response = _lookup(line)
                    if response is None:
                        tx(
                            '                      ^\r\n'
                            "% Invalid input detected at '^' marker.\r\n"
                        )
                    elif line.strip() in PRIV_ONLY and not privileged:
                        tx('% Authorization failed\r\n')
                    else:
                        for resp_line in response.splitlines():
                            tx(resp_line + '\r\n')

                tx(prompt())

            elif ch in ('\x03',):    # Ctrl-C
                tx('^C\r\n')
                buf = ''
                tx(prompt())
            elif ch in ('\x7f', '\x08'):  # backspace / DEL
                buf = buf[:-1] if buf else ''
            else:
                buf += ch


# ── Per-connection handler ────────────────────────────────────────────────────

def _handle_connection(
    conn: socket.socket,
    host_key: paramiko.RSAKey,
    username: str,
    password: str,
    enable_password: str,
):
    transport = paramiko.Transport(conn)
    transport.add_server_key(host_key)
    transport.local_version = 'SSH-2.0-Cisco-1.25'

    server = _IOSServerInterface(username, password)
    try:
        transport.start_server(server=server)
    except paramiko.SSHException as exc:
        log.warning('SSH negotiation failed: %s', exc)
        return

    channel = transport.accept(30)
    if channel is None:
        log.warning('No channel opened (timeout).')
        return

    server.shell_event.wait(10)
    if not server.shell_event.is_set():
        log.warning('Client never requested a shell.')
        return

    log.info('Shell session opened.')
    try:
        _ios_shell(channel, enable_password)
    finally:
        try:
            transport.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
        log.info('Connection closed.')


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description='Fake Cisco IOS SSH device for testing the baseline collector.'
    )
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=2222)
    ap.add_argument('--username', default='cisco')
    ap.add_argument('--password', default='cisco')
    ap.add_argument(
        '--enable-password', default='cisco', dest='enable_password',
    )
    ap.add_argument(
        '--host-key', default='cisco_sim_host_key',
        help='RSA host key PEM path; auto-generated if absent',
    )
    args = ap.parse_args()

    if os.path.exists(args.host_key):
        host_key = paramiko.RSAKey.from_private_key_file(args.host_key)
        log.info('Loaded host key from %s', args.host_key)
    else:
        host_key = paramiko.RSAKey.generate(2048)
        host_key.write_private_key_file(args.host_key)
        log.info('Generated new host key -> %s', args.host_key)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((args.host, args.port))
    sock.listen(5)
    log.info(
        'Cisco IOS simulator listening on %s:%d', args.host, args.port,
    )
    log.info(
        'Credentials: %s / %s  |  enable: %s',
        args.username, args.password, args.enable_password,
    )

    try:
        while True:
            conn, addr = sock.accept()
            log.info('Connection from %s', addr)
            t = threading.Thread(
                target=_handle_connection,
                args=(
                    conn, host_key,
                    args.username, args.password, args.enable_password,
                ),
                daemon=True,
            )
            t.start()
    except KeyboardInterrupt:
        log.info('Simulator stopped.')
    finally:
        sock.close()


if __name__ == '__main__':
    main()
