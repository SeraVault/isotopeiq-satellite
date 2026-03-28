import logging
import time
from celery import shared_task
from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import Job, DeviceJobResult
from core.collection.ssh import SSHCollector
from core.collection.telnet import TelnetCollector
from core.collection.winrm import WinRMCollector
from core.collection.render import render_script
from core.parser.runner import run_parser
from core.canonical import validate_canonical

_SUPPORTED_CONNECTION_TYPES = ('ssh', 'telnet', 'winrm')


def _get_collector(device):
    """Return the appropriate collector instance for the device's connection type."""
    if device.connection_type == 'telnet':
        return TelnetCollector(device)
    if device.connection_type == 'winrm':
        return WinRMCollector(device)
    return SSHCollector(device)

logger = logging.getLogger(__name__)


def _broadcast(data: dict) -> None:
    """Push a job status update to all connected WebSocket clients."""
    layer = get_channel_layer()
    if layer:
        async_to_sync(layer.group_send)('jobs', {'type': 'job.update', 'data': data})


def _apply_baseline_and_drift(device, result) -> None:
    from apps.baselines.models import Baseline
    from apps.drift.detector import detect_drift
    from apps.drift.models import DriftEvent
    from apps.notifications.syslog import SyslogNotifier

    baseline, created = Baseline.objects.get_or_create(
        device=device,
        defaults={'parsed_data': result.parsed_output, 'source_result': result},
    )
    if created:
        logger.info('Baseline established for device "%s".', device)
        return

    diffs = detect_drift(baseline.parsed_data, result.parsed_output)
    if diffs:
        event = DriftEvent.objects.create(device=device, job_result=result, diff=diffs)
        SyslogNotifier().notify_drift(device, event)
        logger.warning('Drift detected for device "%s" (event %s).', device, event.pk)


@shared_task(bind=True)
def run_policy(self, policy_id: int, triggered_by: str = 'scheduler'):
    from apps.policies.models import Policy

    policy = (
        Policy.objects
        .prefetch_related('devices')
        .select_related('collection_script', 'parser_script')
        .get(pk=policy_id)
    )

    if not policy.collection_script or not policy.parser_script:
        raise ValueError(f'Policy {policy_id} requires both a collection and a parser script.')

    job = Job.objects.create(
        policy=policy,
        triggered_by=triggered_by,
        status='running',
        started_at=timezone.now(),
        celery_task_id=self.request.id or '',
    )
    _broadcast({'job_id': job.id, 'status': 'running'})

    overall_ok = True
    devices = list(policy.devices.filter(is_active=True, connection_type__in=_SUPPORTED_CONNECTION_TYPES))
    for idx, device in enumerate(devices):
        result = DeviceJobResult.objects.create(
            job=job,
            device=device,
            status='running',
            started_at=timezone.now(),
        )
        try:
            collector = _get_collector(device)
            raw_output = collector.run(render_script(policy.collection_script.content, device))
            result.raw_output = raw_output

            parsed = run_parser(policy.parser_script.content, raw_output)
            validate_canonical(parsed)
            result.parsed_output = parsed
            result.status = 'success'
        except Exception as exc:
            logger.exception('Error processing device "%s" in job %s.', device, job.id)
            result.status = 'failed'
            result.error_message = str(exc)
            overall_ok = False
        finally:
            result.finished_at = timezone.now()
            result.save()

        if result.status == 'success':
            try:
                _apply_baseline_and_drift(device, result)
            except Exception:
                logger.exception('Baseline/drift error for device "%s".', device)

        # Respect inter-device delay (skip after the last device).
        if policy.delay_between_devices and idx < len(devices) - 1:
            time.sleep(policy.delay_between_devices)

    job.status = 'success' if overall_ok else ('partial' if job.device_results.filter(status='success').exists() else 'failed')
    job.finished_at = timezone.now()
    job.save()
    _broadcast({'job_id': job.id, 'status': job.status})
