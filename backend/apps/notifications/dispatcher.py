"""
Post-collection action dispatcher.

Called from jobs/tasks.py after a successful collection to fire any
PostCollectionActions configured for the policy.
"""
import logging

from django.db.models import Q

logger = logging.getLogger(__name__)


def dispatch_actions(
    trigger: str, policy, device, baseline=None, drift_event=None, error_message=None,
) -> None:
    """
    Fire all active PostCollectionActions that match the given trigger.

    Actions with trigger='always' fire on every successful collection (both
    new-baseline and drift events) — never on job_failed, since "always"
    actions are export/baseline-shaped and a failed job has no baseline data
    for them to act on.

    Args:
        trigger:       'new_baseline' | 'drift_detected' | 'job_failed'
        policy:        policies.Policy instance (may be None for agent-pull
                       jobs without an associated policy)
        device:        devices.Device instance
        baseline:      baselines.Baseline instance (may be None for
                       drift/failure calls)
        drift_event:   drift.DriftEvent instance (may be None for
                       new-baseline/failure calls)
        error_message: failure detail, only set when trigger='job_failed'
    """
    from .models import PostCollectionAction  # noqa: PLC0415

    if policy is None:
        # No policy — fall back to global SystemSettings-level FTP/syslog if enabled.
        _dispatch_global_fallback(
            trigger, device, baseline=baseline, drift_event=drift_event,
            error_message=error_message,
        )
        return

    trigger_filter = Q(trigger=trigger)
    if trigger != PostCollectionAction.TRIGGER_JOB_FAILED:
        trigger_filter |= Q(trigger=PostCollectionAction.TRIGGER_ALWAYS)

    actions = PostCollectionAction.objects.filter(
        policy=policy,
        is_active=True,
    ).filter(trigger_filter)

    for action in actions:
        try:
            _dispatch_one(
                action, trigger, device, baseline=baseline, drift_event=drift_event,
                error_message=error_message,
            )
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


def dispatch_device_offline(device, last_seen_at) -> None:
    """
    Notify that a device has gone offline (no successful collection within
    the configured threshold). Unlike dispatch_actions, this isn't scoped to
    a Policy — a device can belong to many policies or none, and "offline"
    is a fleet-wide health signal, not a per-policy-run event — so it only
    goes through the global SystemSettings-level syslog/email channels.
    """
    from .models import SystemSettings  # noqa: PLC0415
    try:
        s = SystemSettings.get()
    except Exception:
        return

    if s.syslog_enabled:
        try:
            from .syslog import SyslogNotifier  # noqa: PLC0415
            SyslogNotifier().notify_device_offline(device, last_seen_at)
        except Exception:
            logger.exception('dispatch_device_offline: syslog error for device "%s".', device)

    if s.email_enabled:
        try:
            from .email import EmailNotifier  # noqa: PLC0415
            EmailNotifier().notify_device_offline(device, last_seen_at)
        except Exception:
            logger.exception('dispatch_device_offline: email error for device "%s".', device)


# ── Internal ──────────────────────────────────────────────────────────────────

def _dispatch_one(action, trigger, device, baseline, drift_event, error_message=None) -> None:
    _send_to_destination(
        action.destination, device, baseline=baseline, drift_event=drift_event,
        error_message=error_message,
    )


def _send_to_destination(destination: str, device, baseline, drift_event, error_message=None) -> None:
    from .models import PostCollectionAction  # noqa: PLC0415

    if destination == PostCollectionAction.DEST_SYSLOG:
        from .syslog import SyslogNotifier  # noqa: PLC0415
        notifier = SyslogNotifier()
        if error_message is not None:
            notifier.notify_job_failed(device, error_message)
        elif drift_event is not None:
            notifier.notify_drift(device, drift_event)
        elif baseline is not None:
            notifier.notify_baseline_established(device, baseline)

    elif destination == PostCollectionAction.DEST_EMAIL:
        from .email import EmailNotifier  # noqa: PLC0415
        notifier = EmailNotifier()
        if error_message is not None:
            notifier.notify_job_failed(device, error_message)
        elif drift_event is not None:
            notifier.notify_drift(device, drift_event)
        elif baseline is not None:
            notifier.export_baseline(device, baseline)

    elif destination == PostCollectionAction.DEST_FTP:
        # FTP is an export channel, not an alert channel — nothing to export
        # on a failed job (no baseline data), so silently skip.
        if baseline is not None:
            from .ftp import FtpExporter  # noqa: PLC0415
            FtpExporter().export_baseline(device, baseline)
        else:
            logger.debug(
                'FTP dispatch skipped for device "%s": no baseline available.', device
            )


def _dispatch_global_fallback(
    trigger: str, device, baseline=None, drift_event=None, error_message=None,
) -> None:
    """
    When there is no policy, fire syslog/FTP based purely on whether they are
    enabled in global SystemSettings. This covers agent-push and import flows
    where no PostCollectionAction rows exist.
    """
    from .models import SystemSettings  # noqa: PLC0415
    try:
        s = SystemSettings.get()
    except Exception:
        return

    if s.syslog_enabled:
        try:
            from .syslog import SyslogNotifier  # noqa: PLC0415
            notifier = SyslogNotifier()
            if error_message is not None:
                notifier.notify_job_failed(device, error_message)
            elif drift_event is not None:
                notifier.notify_drift(device, drift_event)
            elif baseline is not None and trigger == 'new_baseline':
                notifier.notify_baseline_established(device, baseline)
        except Exception:
            logger.exception('_dispatch_global_fallback: syslog error for device "%s".', device)

    if s.ftp_enabled and baseline is not None and trigger == 'new_baseline':
        try:
            from .ftp import FtpExporter  # noqa: PLC0415
            FtpExporter().export_baseline(device, baseline)
        except Exception:
            logger.exception('_dispatch_global_fallback: FTP error for device "%s".', device)
