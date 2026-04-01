"""
Post-collection action dispatcher.

Called from jobs/tasks.py after a successful collection to fire any
PostCollectionActions configured for the policy.
"""
import logging

from django.db.models import Q

logger = logging.getLogger(__name__)


def dispatch_actions(trigger: str, policy, device, baseline=None, drift_event=None) -> None:
    """
    Fire all active PostCollectionActions that match the given trigger.

    Actions with trigger='always' fire on every successful collection (both
    new-baseline and drift events). Actions with a specific trigger only fire
    for that event type.

    Args:
        trigger:     'new_baseline' | 'drift_detected'
        policy:      policies.Policy instance (may be None for agent-pull jobs
                     without an associated policy)
        device:      devices.Device instance
        baseline:    baselines.Baseline instance (may be None for drift-only calls)
        drift_event: drift.DriftEvent instance (may be None for new-baseline calls)
    """
    if policy is None:
        return

    from .models import PostCollectionAction  # noqa: PLC0415

    actions = PostCollectionAction.objects.filter(
        policy=policy,
        is_active=True,
    ).filter(
        Q(trigger=trigger) | Q(trigger=PostCollectionAction.TRIGGER_ALWAYS)
    )

    for action in actions:
        try:
            _dispatch_one(action, trigger, device, baseline=baseline, drift_event=drift_event)
        except Exception:
            logger.exception(
                'PostCollectionAction id=%s (policy=%s, trigger=%s, dest=%s) raised an error.',
                action.pk, policy.pk, trigger, action.destination,
            )


def dispatch_adhoc(destination: str, device, baseline) -> None:
    """
    Send a one-off export/notification for a baseline without needing a policy.
    Used by the BaselinesView "Send" action.
    """
    try:
        _send_to_destination(destination, device, baseline=baseline, drift_event=None)
    except Exception:
        logger.exception(
            'Ad-hoc dispatch to "%s" for device "%s" raised an error.',
            destination, device,
        )


# ── Internal ──────────────────────────────────────────────────────────────────

def _dispatch_one(action, trigger, device, baseline, drift_event) -> None:
    _send_to_destination(action.destination, device, baseline=baseline, drift_event=drift_event)


def _send_to_destination(destination: str, device, baseline, drift_event) -> None:
    from .models import PostCollectionAction  # noqa: PLC0415

    if destination == PostCollectionAction.DEST_SYSLOG:
        from .syslog import SyslogNotifier  # noqa: PLC0415
        notifier = SyslogNotifier()
        if drift_event is not None:
            notifier.notify_drift(device, drift_event)
        elif baseline is not None:
            notifier.notify_baseline_established(device, baseline)

    elif destination == PostCollectionAction.DEST_EMAIL:
        from .email import EmailNotifier  # noqa: PLC0415
        notifier = EmailNotifier()
        if drift_event is not None:
            notifier.notify_drift(device, drift_event)
        elif baseline is not None:
            notifier.export_baseline(device, baseline)

    elif destination == PostCollectionAction.DEST_FTP:
        if baseline is not None:
            from .ftp import FtpExporter  # noqa: PLC0415
            FtpExporter().export_baseline(device, baseline)
        else:
            logger.debug(
                'FTP dispatch skipped for device "%s": no baseline available.', device
            )
