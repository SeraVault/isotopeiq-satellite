import re
import logging
import logging.handlers
from django.conf import settings

logger = logging.getLogger(__name__)

# DeepDiff change-type keys and their short labels.
_DIFF_LABELS = {
    'values_changed': 'changed',
    'dictionary_item_added': 'added',
    'dictionary_item_removed': 'removed',
    'iterable_item_added': 'added',
    'iterable_item_removed': 'removed',
    'type_changes': 'type_changed',
    'attribute_added': 'added',
    'attribute_removed': 'removed',
}

# Strips the leading "root[" and trailing "]" from DeepDiff path strings,
# then converts ["key"] notation to .key for readability.
_PATH_RE = re.compile(r"\['?([^'\]]+)'?\]|\[(\d+)\]")


def _clean_path(raw: str) -> str:
    """Convert a DeepDiff root path string to a readable dotted path."""
    raw = raw.removeprefix('root')
    parts = []
    for m in _PATH_RE.finditer(raw):
        parts.append(m.group(1) or m.group(2))
    return '.'.join(parts) if parts else raw


def _summarise_diff(diff: dict) -> list:
    """
    Return a flat list of human-readable change strings from a DeepDiff dict.
    Example: ["changed: interfaces.Gi0/0.ip_address", "added: ntp.servers[2]"]
    """
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


def _get_syslog_config():
    """Return (host, port, facility_str, enabled) from DB, falling back to env."""
    try:
        from .models import SystemSettings  # noqa: PLC0415
        s = SystemSettings.get()
        return s.syslog_host, s.syslog_port, s.syslog_facility, s.syslog_enabled
    except Exception:  # noqa: BLE001
        return (
            getattr(settings, 'SYSLOG_HOST', 'localhost'),
            getattr(settings, 'SYSLOG_PORT', 514),
            getattr(settings, 'SYSLOG_FACILITY', 'local0'),
            True,
        )


class SyslogNotifier:
    """Emits structured syslog messages for drift events."""

    def __init__(self):
        self._handler = None
        host, port, facility_str, enabled = _get_syslog_config()
        if not enabled:
            return
        try:
            facility = getattr(
                logging.handlers.SysLogHandler,
                f'LOG_{facility_str.upper()}',
                logging.handlers.SysLogHandler.LOG_LOCAL0,
            )
            self._handler = logging.handlers.SysLogHandler(
                address=(host, port),
                facility=facility,
            )
        except Exception:  # noqa: BLE001
            logger.warning(
                'Syslog handler unavailable; falling back to local logging only.'
            )

    def _emit(self, message: str) -> None:
        if self._handler:
            record = logging.LogRecord(
                'isotopeiq', logging.WARNING, '', 0, message, (), None
            )
            self._handler.emit(record)
        logger.warning(message)

    def notify_drift(self, device, drift_event) -> None:
        """Emit a DRIFT_DETECTED syslog message with per-field change detail."""
        changes = _summarise_diff(drift_event.diff)
        self._emit(
            f'IsotopeIQ DRIFT_DETECTED'
            f' device="{device.name}"'
            f' hostname="{device.hostname}"'
            f' event_id={drift_event.pk}'
            f' changes={changes}'
        )
