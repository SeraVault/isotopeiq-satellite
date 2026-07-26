import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def detect_offline_devices():
    """
    Flag active devices that haven't had a successful collection within the
    configured threshold (SystemSettings.device_offline_threshold_hours) and
    fire a device_offline notification once per offline transition.

    Devices that have never been seen at all (last_seen_at is None) are
    skipped — that's a "never collected" state, not an observed outage, and
    would otherwise fire spuriously for every newly-added device before its
    first scheduled run.
    """
    from apps.notifications.models import SystemSettings
    from apps.notifications.dispatcher import dispatch_device_offline
    from .models import Device

    settings_row = SystemSettings.get()
    threshold_hours = settings_row.device_offline_threshold_hours
    if not threshold_hours:
        return {'flagged': 0, 'reason': 'offline detection disabled (threshold=0)'}

    cutoff = timezone.now() - timezone.timedelta(hours=threshold_hours)
    newly_offline = Device.objects.filter(
        is_active=True,
        last_seen_at__lt=cutoff,
        offline_notified_at__isnull=True,
    ).exclude(last_seen_at__isnull=True)

    flagged = 0
    for device in newly_offline:
        try:
            dispatch_device_offline(device, device.last_seen_at)
        except Exception:
            logger.exception('detect_offline_devices: notify failed for device "%s".', device)
        device.offline_notified_at = timezone.now()
        device.save(update_fields=['offline_notified_at'])
        flagged += 1

    if flagged:
        logger.warning('detect_offline_devices: flagged %d device(s) as offline.', flagged)
    return {'flagged': flagged}
