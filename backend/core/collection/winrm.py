import base64
import logging
import uuid

import winrm
from winrm.protocol import Protocol

logger = logging.getLogger(__name__)

TIMEOUT = 300  # seconds — collector scripts can take a while
# 8 MB — large enough for verbose firewall rules and driver lists.
MAX_ENVELOPE_SIZE = 8 * 1024 * 1024

# pywinrm hardcodes MaxEnvelopeSize=153600 in build_wsman_header regardless
# of self.max_env_sz.  Patch it once at import time so all Protocol instances
# advertise the larger value to the server.
_orig_build_wsman_header = Protocol.build_wsman_header


def _patched_build_wsman_header(
    self, action, resource_uri, shell_id=None, message_id=None
):
    result = _orig_build_wsman_header(
        self, action, resource_uri, shell_id, message_id
    )
    size = getattr(self, 'max_env_sz', MAX_ENVELOPE_SIZE)
    result['env:Header']['w:MaxEnvelopeSize']['#text'] = str(size)
    return result


Protocol.build_wsman_header = _patched_build_wsman_header


def _resolve_credentials(device):
    cred = device.credential
    if cred:
        return cred.username, cred.password
    return device.username, device.password


class WinRMCollector:
    def __init__(self, device):
        self._device = device

    def run(self, script_content: str) -> str:
        """Connect via WinRM, write script to a temp file, execute it, return stdout.

        run_ps() encodes the entire script as a base64 -EncodedCommand argument
        which hits the Windows command-line length limit (~32 KB) for large
        collector scripts.  Instead we write the script to a temp file first,
        then execute it via `powershell -File`, sidestepping the limit entirely.
        """
        username, password = _resolve_credentials(self._device)

        scheme = 'https' if self._device.port == 5986 else 'http'
        endpoint = f'{scheme}://{self._device.hostname}:{self._device.port}/wsman'

        session = winrm.Session(
            target=endpoint,
            auth=(username, password),
            transport='ntlm',
            server_cert_validation='ignore',
            operation_timeout_sec=TIMEOUT,
            read_timeout_sec=TIMEOUT + 5,
        )
        session.protocol.max_env_sz = MAX_ENVELOPE_SIZE

        tmp = f'C:\\Windows\\Temp\\iqcol_{uuid.uuid4().hex}.ps1'
        proto = session.protocol

        # Write the script to a temp file in chunks via cmd.exe echo to avoid
        # the ~32 KB command-line length limit on -EncodedCommand.
        shell_id = proto.open_shell()
        try:
            # Write file chunk by chunk (2000 bytes per echo call to stay safe).
            encoded_script = base64.b64encode(script_content.encode('utf-8')).decode('ascii')
            chunk_size = 2000
            chunks = [encoded_script[i:i+chunk_size] for i in range(0, len(encoded_script), chunk_size)]

            # First chunk: create the file
            cmd_id = proto.run_command(shell_id, f'echo {chunks[0]}> "{tmp}.b64"')
            proto.get_command_output(shell_id, cmd_id)
            proto.cleanup_command(shell_id, cmd_id)

            # Remaining chunks: append
            for chunk in chunks[1:]:
                cmd_id = proto.run_command(shell_id, f'echo {chunk}>> "{tmp}.b64"')
                proto.get_command_output(shell_id, cmd_id)
                proto.cleanup_command(shell_id, cmd_id)

            # Decode base64 file to the actual .ps1 script
            decode_ps = (
                f"$b=[System.IO.File]::ReadAllText('{tmp}.b64').Trim();"
                f"$d=[System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($b));"
                f"[System.IO.File]::WriteAllText('{tmp}',$d)"
            )
            encoded_decode = base64.b64encode(decode_ps.encode('utf-16-le')).decode('ascii')
            cmd_id = proto.run_command(shell_id, 'powershell', ['-NonInteractive', '-EncodedCommand', encoded_decode])
            stdout, stderr, rc = proto.get_command_output(shell_id, cmd_id)
            proto.cleanup_command(shell_id, cmd_id)
            if rc != 0:
                raise RuntimeError(f'Failed to decode script on remote: {stderr.decode("utf-8", errors="replace")}')

            # Execute the .ps1 file
            cmd_id = proto.run_command(
                shell_id, 'powershell',
                ['-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', tmp],
            )
            stdout, stderr, rc = proto.get_command_output(shell_id, cmd_id)
            proto.cleanup_command(shell_id, cmd_id)

            if rc != 0:
                raise RuntimeError(
                    f'PowerShell script exited with code {rc}. '
                    f'stderr: {stderr.decode("utf-8", errors="replace")}'
                )
            return stdout.decode('utf-8', errors='replace')
        finally:
            proto.run_command(shell_id, f'del /f /q "{tmp}" "{tmp}.b64"')
            proto.close_shell(shell_id)
