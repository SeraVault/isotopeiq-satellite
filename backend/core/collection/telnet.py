import logging
import re
import telnetlib

logger = logging.getLogger(__name__)

CONNECT_TIMEOUT = 30     # seconds to establish the TCP connection
READ_TIMEOUT = 30        # seconds to wait for each prompt / command response
LOGIN_TIMEOUT = 10       # seconds to wait for login/password prompts

# Patterns that indicate a device is waiting for the next command.
# Matches common network device prompts: router#, switch>, hostname(config)#, etc.
_PROMPT_RE = re.compile(
    rb'[\w\-\.]+\s*(?:\([\w\-]+\))?\s*[#>$]\s*$',
    re.MULTILINE,
)

# Built-in fallback patterns used when no credential expectations are defined.
_LOGIN_RE = re.compile(rb'[Uu]ser\s*[Nn]ame[:\s]|[Ll]ogin[:\s]', re.IGNORECASE)
_PASS_RE = re.compile(rb'[Pp]ass(?:word)?[:\s]', re.IGNORECASE)


def _resolve_credentials(device):
    """Return (username, password, expectations) for the device."""
    cred = device.credential
    if cred:
        exps = list(
            cred.expectations.order_by('order').values_list('prompt_pattern', 'response')
        )
        return cred.username, cred.password, exps
    return device.username, device.password, []


class TelnetCollector:
    """
    Connects to a device via Telnet, authenticates, runs each non-empty
    non-comment line of the script as a command, and returns the
    concatenated output.

    Limitations vs SSH:
    - No encryption — use only on isolated management networks.
    - No host key verification — no equivalent concept in Telnet.
    - Output includes echoed commands and prompts; parser scripts must
      strip them as needed.
    - Paging commands (terminal length 0 / terminal pager 0) are prepended
      automatically to suppress "--More--" pauses on Cisco/Juniper devices.
    """

    # Commands to suppress paging on common platforms, sent before the script.
    _PAGING_CMDS = [
        b'terminal length 0\n',        # Cisco IOS / IOS-XE / NX-OS
        b'terminal pager 0\n',         # Cisco IOS-XR
        b'set cli screen-length 0\n',  # Juniper JunOS
    ]

    def __init__(self, device):
        self._device = device

    def run(self, script_content: str) -> str:
        """Connect via Telnet, execute each script line, return all output."""
        username, password, expectations = _resolve_credentials(self._device)
        port = self._device.port or 23

        tn = telnetlib.Telnet(self._device.hostname, port, timeout=CONNECT_TIMEOUT)
        try:
            if expectations:
                output = self._authenticate_custom(tn, username, password, expectations)
            else:
                output = self._authenticate(tn, username, password)
            output += self._run_script(tn, script_content)
        finally:
            tn.close()

        return output

    # ── private helpers ───────────────────────────────────────────────────

    def _authenticate_custom(
        self,
        tn: telnetlib.Telnet,
        username: str,
        password: str,
        expectations: list,
    ) -> str:
        """
        Drive the login sequence using the ordered prompt/response pairs
        stored on the credential.  Special response tokens:
          {username}  — substituted with the credential username
          {password}  — substituted with the credential password
        Any expectation whose pattern matches the received text causes the
        corresponding response to be sent.  Processing stops once the device
        prompt is detected.
        """
        buf = b''

        # Build compiled pattern list: credential expectations + prompt sentinel.
        patterns = [re.compile(p.encode(), re.IGNORECASE) for p, _ in expectations]
        patterns.append(_PROMPT_RE)
        prompt_index = len(patterns) - 1

        while True:
            index, _, data = tn.expect(patterns, timeout=LOGIN_TIMEOUT)
            buf += data
            if index == -1 or index == prompt_index:
                # Timed out or reached the shell prompt — done.
                break
            _, response = expectations[index]
            response = response.replace('{username}', username or '')
            response = response.replace('{password}', password or '')
            tn.write((response + '\n').encode())

        return buf.decode('utf-8', errors='replace')

    def _authenticate(self, tn: telnetlib.Telnet, username: str, password: str) -> str:
        """Handle login/password prompts using built-in patterns (no expectations set)."""
        buf = b''

        # Wait for either a login prompt or a command prompt (already logged in).
        index, _, data = tn.expect(
            [_LOGIN_RE, _PASS_RE, _PROMPT_RE],
            timeout=LOGIN_TIMEOUT,
        )
        buf += data

        if index == 0:
            # Username prompt
            tn.write((username + '\n').encode())
            _, _, data = tn.expect([_PASS_RE, _PROMPT_RE], timeout=LOGIN_TIMEOUT)
            buf += data
            if _PASS_RE.search(data):
                tn.write((password + '\n').encode())
                _, _, data = tn.expect([_PROMPT_RE], timeout=LOGIN_TIMEOUT)
                buf += data
        elif index == 1:
            # Password-only prompt (no username asked)
            tn.write((password + '\n').encode())
            _, _, data = tn.expect([_PROMPT_RE], timeout=LOGIN_TIMEOUT)
            buf += data
        # index == 2: already at a prompt, nothing to do

        return buf.decode('utf-8', errors='replace')

    def _run_script(self, tn: telnetlib.Telnet, script_content: str) -> str:
        """Send paging-suppression commands then each script line; collect output."""
        buf = b''

        # Suppress paging (best-effort — unknown platforms silently ignore unknown cmds).
        for cmd in self._PAGING_CMDS:
            tn.write(cmd)
            _, _, data = tn.expect([_PROMPT_RE], timeout=READ_TIMEOUT)
            buf += data

        # Execute each non-empty, non-comment line as a command.
        lines = [
            line for line in script_content.splitlines()
            if line.strip() and not line.strip().startswith('#')
        ]
        for line in lines:
            tn.write((line + '\n').encode())
            _, _, data = tn.expect([_PROMPT_RE], timeout=READ_TIMEOUT)
            buf += data

        return buf.decode('utf-8', errors='replace')
