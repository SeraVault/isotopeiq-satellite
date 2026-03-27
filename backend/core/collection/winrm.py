import logging
import winrm

logger = logging.getLogger(__name__)

TIMEOUT = 30  # seconds


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

        session = winrm.Session(
            target=f'{protocol}://{self._device.hostname}:{self._device.port}/wsman',
            auth=(username, password),
            transport='ntlm',
            server_cert_validation='ignore',
            operation_timeout_sec=TIMEOUT,
            read_timeout_sec=TIMEOUT + 5,
        )

        result = session.run_ps(script_content)

        if result.status_code != 0:
            stderr = result.std_err.decode('utf-8', errors='replace')
            raise RuntimeError(
                f'PowerShell script exited with code {result.status_code}. stderr: {stderr}'
            )

        return result.std_out.decode('utf-8', errors='replace')
