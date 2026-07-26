"""
Device "last seen" tracking, used to derive offline status.

Call mark_seen() from every task code path where a collection job against a
device actually succeeds — not just the baseline/drift paths, since a job
can legitimately succeed with neither enabled (e.g. a discovery or
remediation ScriptJob).
"""
from django.utils import timezone


def mark_seen(device) -> None:
    if device is None:
        return
    device.last_seen_at = timezone.now()
    fields = ['last_seen_at']
    if device.offline_notified_at is not None:
        # Coming back online — clear the offline flag so a future outage
        # fires a fresh device_offline notification instead of staying
        # silent because the device was already marked offline once.
        device.offline_notified_at = None
        fields.append('offline_notified_at')
    device.save(update_fields=fields)
