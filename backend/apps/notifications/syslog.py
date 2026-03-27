import logging
import logging.handlers
from django.conf import settings

logger = logging.getLogger(__name__)


class SyslogNotifier:
    def __init__(self):
        self._handler = None
        try:
            facility = getattr(
                logging.handlers.SysLogHandler,
                f'LOG_{settings.SYSLOG_FACILITY.upper()}',
                logging.handlers.SysLogHandler.LOG_LOCAL0,
            )
            self._handler = logging.handlers.SysLogHandler(
                address=(settings.SYSLOG_HOST, settings.SYSLOG_PORT),
                facility=facility,
            )
        except Exception:
            logger.warning('Syslog handler unavailable; falling back to local logging only.')

    def _emit(self, message: str) -> None:
        if self._handler:
            record = logging.LogRecord(
                'isotopeiq', logging.WARNING, '', 0, message, (), None
            )
            self._handler.emit(record)
        logger.warning(message)

    def notify_drift(self, device, drift_event) -> None:
        self._emit(
            f'IsotopeIQ DRIFT_DETECTED device="{device.name}" '
            f'hostname="{device.hostname}" '
            f'event_id={drift_event.pk} '
            f'diff_keys={list(drift_event.diff.keys())}'
        )
