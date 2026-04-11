import io
import base64
import logging
import paramiko

logger = logging.getLogger(__name__)

TIMEOUT = 300  # seconds — Windows PS collection can be slow


_KEY_TYPES = [
    paramiko.Ed25519Key,
    paramiko.ECDSAKey,
    paramiko.RSAKey,
]


def _load_private_key(private_key_str: str):
    """Try each key type in turn; return the first that succeeds."""
    for key_cls in _KEY_TYPES:
        try:
            return key_cls.from_private_key(io.StringIO(private_key_str))
        except paramiko.SSHException:
            continue
    raise paramiko.SSHException('Unsupported or invalid private key format.')


class _PinnedHostKeyPolicy(paramiko.MissingHostKeyPolicy):
    """Accept only the host key stored on the Device record."""

    def __init__(self, expected_key_b64: str):
        self._expected = expected_key_b64

    def missing_host_key(self, client, hostname, key):
        actual = base64.b64encode(key.asbytes()).decode()
        if actual != self._expected:
            raise paramiko.SSHException(
                f'Host key mismatch for {hostname}. '
                f'Update the device host_key field with the correct public key.'
            )


def _resolve_credentials(device):
    """
    Return (username, password, private_key_str) for the device.
    Prefers the linked Credential record; falls back to inline device fields.
    """
    cred = device.credential
    if cred:
        if cred.credential_type in ('private_key', 'ssh_key'):
            return cred.username, None, cred.private_key
        else:
            return cred.username, cred.password, None
    # Inline legacy fields
    return device.username, device.password, device.ssh_private_key


class SSHCollector:
    def __init__(self, device):
        self._device = device

    def run(self, script_content: str, language: str = 'shell') -> str:
        """Connect via SSH, execute script_content, and return stdout.

        language — 'shell' (default) or 'python'.  Shell scripts are piped
                   directly to exec_command.  Python scripts are uploaded to a
                   temp file via SFTP and executed with python3.
        """
        username, password, private_key_str = _resolve_credentials(self._device)

        client = paramiko.SSHClient()
        if self._device.host_key:
            client.set_missing_host_key_policy(_PinnedHostKeyPolicy(self._device.host_key))
        else:
            logger.warning(
                'Device "%s" has no host_key set — connecting without host key verification. '
                'Set host_key (from ssh-keyscan -t rsa <hostname>) to enable pinning.',
                self._device.name,
            )
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            connect_kwargs = {
                'hostname': self._device.hostname,
                'port': self._device.port,
                'username': username,
                'timeout': TIMEOUT,
                'allow_agent': False,
                'look_for_keys': False,
            }
            if private_key_str:
                connect_kwargs['pkey'] = _load_private_key(private_key_str)
            else:
                connect_kwargs['password'] = password

            client.connect(**connect_kwargs)

            # OpenSSH on Windows defaults to cmd.exe. Use SFTP to upload the
            # script to a temp file then execute it with PowerShell, bypassing
            # the cmd.exe shell entirely.
            os_type = getattr(self._device, 'os_type', '')
            if os_type == 'windows':
                import uuid as _uuid
                tmp = f'C:/Windows/Temp/isotopeiq_{_uuid.uuid4().hex}.ps1'
                sftp = client.open_sftp()
                try:
                    with sftp.open(tmp, 'w') as f:
                        f.write(script_content)
                finally:
                    sftp.close()
                _, stdout, stderr = client.exec_command(
                    f'powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{tmp}" ; Remove-Item -Force "{tmp}" -ErrorAction SilentlyContinue',
                    timeout=TIMEOUT,
                )
            elif language == 'python':
                # Upload to a temp file and execute with python3 so Python
                # syntax is not interpreted by the remote shell.
                import uuid as _uuid
                tmp = f'/tmp/isotopeiq_{_uuid.uuid4().hex}.py'
                sftp = client.open_sftp()
                try:
                    with sftp.open(tmp, 'w') as f:
                        f.write(script_content)
                    sftp.chmod(tmp, 0o700)
                finally:
                    sftp.close()
                _, stdout, stderr = client.exec_command(
                    f'python3 {tmp} ; _rc=$? ; rm -f {tmp} ; exit $_rc',
                    timeout=TIMEOUT,
                )
            else:
                _, stdout, stderr = client.exec_command(script_content, timeout=TIMEOUT)
            try:
                output = stdout.read().decode('utf-8', errors='replace')
                error = stderr.read().decode('utf-8', errors='replace')
                exit_code = stdout.channel.recv_exit_status()
            except Exception as inner:
                err_so_far = ''
                try:
                    err_so_far = stderr.read().decode('utf-8', errors='replace')
                except Exception:
                    pass
                raise RuntimeError(
                    f'Channel error: {inner}. stderr: {err_so_far or "(empty)"}'
                )

            if exit_code != 0:
                raise RuntimeError(
                    f'Collection script exited with code {exit_code}. stderr: {error}'
                )
            return output
        finally:
            client.close()
