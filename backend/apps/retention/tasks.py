import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


@shared_task
def prune_old_data():
    """
    Delete data older than the configured retention windows.
    Runs via Celery Beat (daily).  A value of 0 means keep forever.
    """
    from .models import RetentionPolicy
    from apps.jobs.models import Job, DeviceJobResult

    policy = RetentionPolicy.get()
    now = timezone.now()
    totals = {}

    # ── Raw output ────────────────────────────────────────────────────────────
    if policy.raw_data_days:
        cutoff = now - timedelta(days=policy.raw_data_days)
        qs = DeviceJobResult.objects.filter(
            started_at__lt=cutoff,
        ).exclude(raw_output='')
        count = qs.update(raw_output='')
        totals['raw_output_cleared'] = count
        logger.info('Retention: cleared raw_output on %d results (older than %d days).', count, policy.raw_data_days)

    # ── Parsed output ─────────────────────────────────────────────────────────
    if policy.parsed_data_days:
        cutoff = now - timedelta(days=policy.parsed_data_days)
        qs = DeviceJobResult.objects.filter(
            started_at__lt=cutoff,
        ).exclude(parsed_output=None)
        count = qs.update(parsed_output=None)
        totals['parsed_output_cleared'] = count
        logger.info('Retention: cleared parsed_output on %d results (older than %d days).', count, policy.parsed_data_days)

    # ── Job records (cascades to DeviceJobResult) ─────────────────────────────
    if policy.job_history_days:
        cutoff = now - timedelta(days=policy.job_history_days)
        deleted, _ = Job.objects.filter(created_at__lt=cutoff).delete()
        totals['jobs_deleted'] = deleted
        logger.info('Retention: deleted %d job records (older than %d days).', deleted, policy.job_history_days)

    # ── Error / log text on results ───────────────────────────────────────────
    if policy.log_days:
        cutoff = now - timedelta(days=policy.log_days)
        qs = DeviceJobResult.objects.filter(
            started_at__lt=cutoff,
        ).exclude(error_message='')
        count = qs.update(error_message='')
        totals['error_logs_cleared'] = count
        logger.info('Retention: cleared error_message on %d results (older than %d days).', count, policy.log_days)

    return totals
