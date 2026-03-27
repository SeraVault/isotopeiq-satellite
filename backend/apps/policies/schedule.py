"""
Keeps django_celery_beat.PeriodicTask records in sync with Policy records.

Each active Policy gets one PeriodicTask named "policy-<id>".
Inactive or deleted policies have their PeriodicTask disabled / removed.
"""
import json
import logging

logger = logging.getLogger(__name__)

_TASK_NAME_PREFIX = 'policy-'
_TASK_PATH = 'apps.jobs.tasks.run_policy'


def _task_name(policy_id: int) -> str:
    return f'{_TASK_NAME_PREFIX}{policy_id}'


def _parse_cron(cron_expr: str):
    """
    Parse a 5-field cron expression and return a CrontabSchedule, creating it
    if it does not already exist.
    """
    from django_celery_beat.models import CrontabSchedule

    parts = cron_expr.strip().split()
    if len(parts) != 5:
        raise ValueError(f'Invalid cron expression (need 5 fields): {cron_expr!r}')

    minute, hour, day_of_month, month_of_year, day_of_week = parts
    schedule, _ = CrontabSchedule.objects.get_or_create(
        minute=minute,
        hour=hour,
        day_of_month=day_of_month,
        month_of_year=month_of_year,
        day_of_week=day_of_week,
        timezone='UTC',
    )
    return schedule


def sync_policy(policy) -> None:
    """Create or update the PeriodicTask for a single Policy."""
    from django_celery_beat.models import PeriodicTask

    name = _task_name(policy.pk)

    if not policy.is_active:
        # Disable rather than delete so history is preserved.
        PeriodicTask.objects.filter(name=name).update(enabled=False)
        return

    try:
        crontab = _parse_cron(policy.cron_schedule)
    except ValueError:
        logger.error('Policy %s has an invalid cron schedule %r; skipping beat sync.', policy.pk, policy.cron_schedule)
        return

    kwargs_json = json.dumps({'policy_id': policy.pk, 'triggered_by': 'scheduler'})

    PeriodicTask.objects.update_or_create(
        name=name,
        defaults={
            'task': _TASK_PATH,
            'crontab': crontab,
            'kwargs': kwargs_json,
            'enabled': True,
            'description': f'Auto-scheduled run for policy "{policy.name}"',
        },
    )
    logger.debug('Beat schedule synced for policy %s (%s).', policy.pk, policy.cron_schedule)


def delete_policy_schedule(policy_id: int) -> None:
    """Remove the PeriodicTask when a policy is deleted."""
    from django_celery_beat.models import PeriodicTask

    deleted, _ = PeriodicTask.objects.filter(name=_task_name(policy_id)).delete()
    if deleted:
        logger.debug('Beat schedule removed for policy %s.', policy_id)
