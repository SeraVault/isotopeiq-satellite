import logging

import winrm
from winrm.protocol import Protocol

logger = logging.getLogger(__name__)

TIMEOUT = 30  # seconds
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
        """Connect via WinRM, execute script_content as a PowerShell command, return stdout."""
        username, password = _resolve_credentials(self._device)

        protocol = 'https' if self._device.port == 5986 else 'http'
        endpoint = f'{protocol}://{self._device.hostname}:{self._device.port}/wsman'

        session = winrm.Session(
            target=endpoint,
            auth=(username, password),
            transport='ntlm',
            server_cert_validation='ignore',
            operation_timeout_sec=TIMEOUT,
            read_timeout_sec=TIMEOUT + 5,
        )
        session.protocol.max_env_sz = MAX_ENVELOPE_SIZE

        result = session.run_ps(script_content)

        if result.status_code != 0:
            stderr = result.std_err.decode('utf-8', errors='replace')
            raise RuntimeError(
                f'PowerShell script exited with code {result.status_code}. stderr: {stderr}'
            )

        return result.std_out.decode('utf-8', errors='replace')
