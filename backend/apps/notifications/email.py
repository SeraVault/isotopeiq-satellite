"""
Email notification delivery for IsotopeIQ.

Uses Python's built-in smtplib so no extra dependencies are needed.
"""
import json
import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

logger = logging.getLogger(__name__)


def _get_email_config():
    """Return SystemSettings email config, or raise if email not enabled."""
    from .models import SystemSettings  # noqa: PLC0415
    s = SystemSettings.get()
    return s


class EmailNotifier:
    """Sends email notifications for baseline and drift events."""

    def notify_baseline_established(self, device, baseline) -> None:
        s = _get_email_config()
        if not s.email_enabled:
            return
        subject = f'[IsotopeIQ] Baseline Established: {device.name}'
        body = (
            f'A new baseline has been established for device "{device.name}" '
            f'({device.hostname}).\n\n'
            f'Established at : {baseline.established_at}\n'
            f'Established by : {baseline.established_by}\n'
        )
        self._send(s, subject, body)

    def notify_drift(self, device, drift_event) -> None:
        s = _get_email_config()
        if not s.email_enabled:
            return
        subject = f'[IsotopeIQ] Drift Detected: {device.name}'
        changes = _summarise_diff(drift_event.diff)
        body = (
            f'Configuration drift has been detected for device "{device.name}" '
            f'({device.hostname}).\n\n'
            f'Event ID  : {drift_event.pk}\n'
            f'Detected  : {drift_event.created_at}\n\n'
            f'Changes ({len(changes)}):\n'
            + '\n'.join(f'  • {c}' for c in changes)
        )
        self._send(s, subject, body)

    def export_baseline(self, device, baseline) -> None:
        """Send the full canonical baseline JSON as an email attachment."""
        s = _get_email_config()
        if not s.email_enabled:
            return
        subject = f'[IsotopeIQ] Baseline Export: {device.name}'
        body = (
            f'Baseline export for device "{device.name}" ({device.hostname}).\n\n'
            f'Established at : {baseline.established_at}\n'
            f'Established by : {baseline.established_by}\n\n'
            f'The canonical baseline data is attached as a JSON file.'
        )
        filename = f'{device.name}_baseline.json'
        attachment = json.dumps(baseline.parsed_data, indent=2).encode('utf-8')
        self._send(s, subject, body, attachments=[(filename, attachment)])

    # ── Internal ──────────────────────────────────────────────────────────────

    def _send(self, settings, subject: str, body: str, attachments=None) -> None:
        recipients = [r.strip() for r in settings.email_recipients.split(',') if r.strip()]
        if not recipients:
            logger.warning('EmailNotifier: no recipients configured, skipping send.')
            return

        from_addr = settings.email_from or settings.email_username or 'isotopeiq@localhost'

        if attachments:
            msg = MIMEMultipart()
            msg.attach(MIMEText(body, 'plain'))
            for fname, data in attachments:
                part = MIMEApplication(data, Name=fname)
                part['Content-Disposition'] = f'attachment; filename="{fname}"'
                msg.attach(part)
        else:
            msg = MIMEText(body, 'plain')

        msg['Subject'] = subject
        msg['From']    = from_addr
        msg['To']      = ', '.join(recipients)

        try:
            if settings.email_use_tls:
                context = ssl.create_default_context()
                with smtplib.SMTP(settings.email_host, settings.email_port, timeout=15) as smtp:
                    smtp.starttls(context=context)
                    if settings.email_username and settings.email_password:
                        smtp.login(settings.email_username, settings.email_password)
                    smtp.sendmail(from_addr, recipients, msg.as_string())
            else:
                with smtplib.SMTP(settings.email_host, settings.email_port, timeout=15) as smtp:
                    if settings.email_username and settings.email_password:
                        smtp.login(settings.email_username, settings.email_password)
                    smtp.sendmail(from_addr, recipients, msg.as_string())
            logger.info('EmailNotifier: sent "%s" to %s.', subject, recipients)
        except Exception:
            logger.exception('EmailNotifier: failed to send "%s".', subject)


# ── Helpers ───────────────────────────────────────────────────────────────────

import re  # noqa: E402

_PATH_RE = re.compile(r"\['?([^'\]]+)'?\]|\[(\d+)\]")
_DIFF_LABELS = {
    'values_changed':       'changed',
    'dictionary_item_added':   'added',
    'dictionary_item_removed': 'removed',
    'iterable_item_added':     'added',
    'iterable_item_removed':   'removed',
    'type_changes':         'type_changed',
    'attribute_added':      'added',
    'attribute_removed':    'removed',
}


def _clean_path(raw: str) -> str:
    raw = raw.removeprefix('root')
    parts = [m.group(1) or m.group(2) for m in _PATH_RE.finditer(raw)]
    return '.'.join(parts) if parts else raw


def _summarise_diff(diff: dict) -> list:
    out = []
    for diff_type, items in diff.items():
        label = _DIFF_LABELS.get(diff_type, diff_type)
        if isinstance(items, dict):
            for path in items:
                out.append(f'{label}: {_clean_path(str(path))}')
        elif isinstance(items, (list, set)):
            for path in items:
                out.append(f'{label}: {_clean_path(str(path))}')
    return out
