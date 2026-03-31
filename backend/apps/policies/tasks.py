"""Celery tasks for policy-level operations (deployment scripts)."""
import logging

from celery import shared_task
from django.utils import timezone

from apps.jobs.models import Job, DeviceJobResult
from apps.jobs.tasks import (
    _get_collector,
    _SUPPORTED_CONNECTION_TYPES,
)
from apps.policies.models import Policy

logger = logging.getLogger(__name__)


def _finish_job(job, overall_ok):
    job.status = (
        'success' if overall_ok
        else 'partial' if job.device_results.filter(status='success').exists()
        else 'failed'
    )
    job.finished_at = timezone.now()
    job.save()


@shared_task(bind=True)
def run_deployment(self, policy_id: int, triggered_by: str = 'manual'):
    """Run the deployment script against all active devices in the policy.

    Creates a Job record and one DeviceJobResult per device.
    Parsed output and drift detection are skipped — deployment scripts
    are setup scripts, not data collectors.
    """
    policy = (
        Policy.objects
        .prefetch_related('devices')
        .select_related('deployment_script')
        .get(pk=policy_id)
    )

    if not policy.deployment_script:
        raise ValueError(
            f'Policy {policy_id} has no deployment script configured.'
        )

    job = Job.objects.create(
        policy=policy,
        triggered_by=triggered_by,
        status='running',
        started_at=timezone.now(),
        celery_task_id=self.request.id or '',
    )
    overall_ok = True
    devices = list(
        policy.devices.filter(
            is_active=True,
            connection_type__in=_SUPPORTED_CONNECTION_TYPES,
        )
    )

    for device in devices:
        result = DeviceJobResult.objects.create(
            job=job,
            device=device,
            status='running',
            started_at=timezone.now(),
        )
        try:
            output = _get_collector(device).run(
                policy.deployment_script.content
            )
            result.raw_output = output
            result.status = 'success'
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                'Deployment error on device "%s" (job %s).', device, job.id
            )
            result.status = 'failed'
            result.error_message = str(exc)
            overall_ok = False
        finally:
            result.finished_at = timezone.now()
            result.save()

    _finish_job(job, overall_ok)
