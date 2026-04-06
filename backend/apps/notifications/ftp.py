"""
FTP / SFTP baseline export for IsotopeIQ.

FTP  — Python standard library ftplib
SFTP — paramiko (already a project dependency for SSH collection)
"""
import io
import json
import logging

logger = logging.getLogger(__name__)


def _get_ftp_config():
    from .models import SystemSettings  # noqa: PLC0415
    return SystemSettings.get()


class FtpExporter:
    """Uploads baseline JSON files to a configured FTP or SFTP server."""

    def export_baseline(self, device, baseline) -> None:
        s = _get_ftp_config()
        if not s.ftp_enabled:
            return
        filename = '{}_baseline.json'.format(device.name.replace(' ', '_'))
        content = json.dumps(baseline.parsed_data, indent=2).encode('utf-8')
        remote_path = s.ftp_remote_path.rstrip('/') + '/' + filename

        try:
            if s.ftp_protocol == 'sftp':
                self._sftp_upload(s, remote_path, content)
            else:
                self._ftp_upload(s, remote_path, content)
            logger.info('FtpExporter: uploaded %s to %s:%s.', filename, s.ftp_host, remote_path)
        except Exception:
            logger.exception('FtpExporter: failed to upload %s.', filename)

    # ── SFTP ─────────────────────────────────────────────────────────────────

    def _sftp_upload(self, s, remote_path: str, content: bytes) -> None:
        import paramiko  # noqa: PLC0415 — already a project dependency
        transport = paramiko.Transport((s.ftp_host, s.ftp_port))
        try:
            transport.connect(username=s.ftp_username, password=s.ftp_password or None)
            sftp = paramiko.SFTPClient.from_transport(transport)
            try:
                _sftp_makedirs(sftp, remote_path.rsplit('/', 1)[0])
                sftp.putfo(io.BytesIO(content), remote_path)
            finally:
                sftp.close()
        finally:
            transport.close()

    # ── FTP ──────────────────────────────────────────────────────────────────

    def _ftp_upload(self, s, remote_path: str, content: bytes) -> None:
        import ftplib  # noqa: PLC0415 — standard library
        with ftplib.FTP(timeout=30) as ftp:  # nosec — user-configured destination
            ftp.connect(s.ftp_host, s.ftp_port)
            ftp.login(s.ftp_username or '', s.ftp_password or '')
            _ftp_makedirs(ftp, remote_path.rsplit('/', 1)[0])
            ftp.storbinary(f'STOR {remote_path}', io.BytesIO(content))


# ── Directory helpers ─────────────────────────────────────────────────────────

def _sftp_makedirs(sftp, remote_dir: str) -> None:
    """Recursively create remote_dir over SFTP if it does not already exist."""
    if not remote_dir or remote_dir == '/':
        return
    try:
        sftp.stat(remote_dir)
        return  # already exists
    except IOError:
        pass
    parent = remote_dir.rsplit('/', 1)[0]
    if parent and parent != remote_dir:
        _sftp_makedirs(sftp, parent)
    try:
        sftp.mkdir(remote_dir)
    except IOError:
        pass  # created by a concurrent process between stat and mkdir


def _ftp_makedirs(ftp, remote_dir: str) -> None:
    """Recursively create remote_dir over FTP if it does not already exist."""
    if not remote_dir or remote_dir == '/':
        return
    parts = remote_dir.strip('/').split('/')
    path = ''
    for part in parts:
        path = path + '/' + part
        try:
            ftp.mkd(path)
        except Exception:  # noqa: BLE001 — directory already exists
            pass
