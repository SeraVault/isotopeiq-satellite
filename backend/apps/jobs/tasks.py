import json
import logging
import time
from urllib.request import Request, urlopen
from urllib.error import URLError
from celery import shared_task
from django.utils import timezone

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


def _apply_baseline_and_drift(device, result) -> None:
    from apps.baselines.models import Baseline
    from apps.drift.detector import detect_drift
    from apps.drift.models import DriftEvent
    from apps.notifications.syslog import SyslogNotifier
    from apps.notifications.dispatcher import dispatch_actions

    policy = getattr(getattr(result, 'job', None), 'policy', None)

    baseline, created = Baseline.objects.get_or_create(
        device=device,
        defaults={'parsed_data': result.parsed_output, 'source_result': result},
    )
    if created:
        logger.info('Baseline established for device "%s".', device)
        dispatch_actions('new_baseline', policy, device, baseline=baseline)
        return

    baseline_data = baseline.parsed_data
    diffs = detect_drift(baseline_data, result.parsed_output)
    if diffs:
        # Reuse an existing open event rather than piling up one per collection run.
        existing = DriftEvent.objects.filter(device=device, status='new').order_by('-created_at').first()
        if existing:
            existing.diff = diffs
            existing.job_result = result
            existing.baseline_snapshot = baseline_data
            existing.save(update_fields=['diff', 'job_result', 'baseline_snapshot'])
            logger.warning('Drift updated for device "%s" (event %s).', device, existing.pk)
            drift_event = existing
        else:
            drift_event = DriftEvent.objects.create(
                device=device,
                job_result=result,
                diff=diffs,
                baseline_snapshot=baseline_data,
            )
            # Global syslog notification (always fires when syslog is enabled in settings)
            SyslogNotifier().notify_drift(device, drift_event)
            logger.warning('Drift detected for device "%s" (event %s).', device, drift_event.pk)
        # Per-policy post-collection actions (email, FTP, additional syslog rules, etc.)
        dispatch_actions('drift_detected', policy, device, baseline=baseline, drift_event=drift_event)


@shared_task(bind=True)
def run_policy(self, policy_id: int, triggered_by: str = 'scheduler', device_id: int = None):
    from apps.policies.models import Policy

    policy = (
        Policy.objects
        .prefetch_related('devices')
        .select_related('script_package__collection_script', 'script_package__parser_script')
        .get(pk=policy_id)
    )

    if policy.collection_method == 'script':
        config_error = None
        if not policy.script_package:
            config_error = 'Policy misconfigured: no Collection Profile assigned.'
        elif not policy.script_package.collection_script:
            config_error = 'Policy misconfigured: Collection Profile has no collection script.'
        elif not policy.script_package.parser_script:
            config_error = 'Policy misconfigured: Collection Profile has no parser script.'
        if config_error:
            job = Job.objects.create(
                policy=policy,
                triggered_by=triggered_by,
                status='failed',
                started_at=timezone.now(),
                finished_at=timezone.now(),
                celery_task_id=self.request.id or '',
            )
            logger.error('run_policy: %s (policy_id=%s, job_id=%s)', config_error, policy_id, job.id)
            return

    if policy.collection_method == 'agent':
        candidates = list(policy.devices.filter(is_active=True, connection_type='agent'))
        script_devices = []
        agent_devices  = candidates
    else:
        candidates = list(policy.devices.filter(is_active=True, connection_type__in=_SUPPORTED_CONNECTION_TYPES))
        script_devices = candidates
        agent_devices  = []

    if device_id is not None:
        script_devices = [d for d in script_devices if d.id == device_id]
        agent_devices  = [d for d in agent_devices  if d.id == device_id]

    # ── SSH / WinRM / Telnet devices ─────────────────────────────────────────
    devices = script_devices
    # One independent Job per device so history and status are tracked at the
    # device level rather than being aggregated under a single policy run.
    for idx, device in enumerate(devices):
        job = Job.objects.create(
            policy=policy,
            device=device,
            triggered_by=triggered_by,
            status='running',
            started_at=timezone.now(),
            celery_task_id=self.request.id or '',
        )

        result = DeviceJobResult.objects.create(
            job=job,
            device=device,
            status='running',
            started_at=timezone.now(),
        )

        try:
            collector = _get_collector(device)
            raw_output = collector.run(render_script(policy.script_package.collection_script.content, device))
            result.raw_output = raw_output

            parsed = run_parser(policy.script_package.parser_script.content, raw_output)
            validate_canonical(parsed)
            result.parsed_output = parsed
            result.status = 'success'
        except Exception as exc:
            logger.exception('Error processing device "%s" in job %s.', device, job.id)
            result.status = 'failed'
            result.error_message = str(exc)
        finally:
            result.finished_at = timezone.now()
            result.save()

        job.status = result.status
        job.finished_at = timezone.now()
        job.save()

        if result.status == 'success':
            try:
                _apply_baseline_and_drift(device, result)
            except Exception:
                logger.exception('Baseline/drift error for device "%s".', device)

        # Respect inter-device delay (skip after the last device).
        if policy.delay_between_devices and idx < len(devices) - 1:
            time.sleep(policy.delay_between_devices)

    # ── Agent Pull devices ────────────────────────────────────────────────────
    for idx, device in enumerate(agent_devices):
        job = Job.objects.create(
            policy=policy,
            device=device,
            triggered_by=triggered_by,
            status='running',
            started_at=timezone.now(),
            celery_task_id=self.request.id or '',
        )
        result = DeviceJobResult.objects.create(
            job=job,
            device=device,
            status='running',
            started_at=timezone.now(),
        )
        try:
            port = device.agent_port or 9322
            url = 'http://{host}:{port}/collect'.format(host=device.hostname, port=port)
            req = Request(url)  # nosec — internal network, known agent endpoint
            with urlopen(req, timeout=30) as resp:  # noqa: S310
                raw = resp.read().decode('utf-8')
            result.raw_output = raw
            parsed = json.loads(raw)
            if policy.script_package and policy.script_package.parser_script:
                parsed = run_parser(policy.script_package.parser_script.content, raw)
            validate_canonical(parsed)
            result.parsed_output = parsed
            result.status = 'success'
        except (URLError, OSError) as exc:
            logger.error('Agent pull network error for device "%s": %s', device, exc)
            result.status = 'failed'
            result.error_message = str(exc)
        except Exception as exc:
            logger.exception('Agent pull failed for device "%s".', device)
            result.status = 'failed'
            result.error_message = str(exc)
        finally:
            result.finished_at = timezone.now()
            result.save()

        job.status = result.status
        job.finished_at = timezone.now()
        job.save()

        if result.status == 'success':
            try:
                _apply_baseline_and_drift(device, result)
            except Exception:
                logger.exception('Baseline/drift error for device "%s".', device)

        if policy.delay_between_devices and idx < len(agent_devices) - 1:
            time.sleep(policy.delay_between_devices)


@shared_task(bind=True)
def run_agent_pull(self, device_id: int, triggered_by: str = 'manual'):
    """
    Pull a baseline collection from an IsotopeIQ agent running on the device.

    The agent must be listening on device.agent_port (default 9322) and
    expose GET /collect, optionally protected by X-Agent-Token.
    """
    from apps.devices.models import Device

    device = Device.objects.get(pk=device_id)

    job = Job.objects.create(
        device=device,
        triggered_by=triggered_by,
        status='running',
        started_at=timezone.now(),
        celery_task_id=self.request.id or '',
    )
    result = DeviceJobResult.objects.create(
        job=job,
        device=device,
        status='running',
        started_at=timezone.now(),
    )

    try:
        port = device.agent_port or 9322
        url = 'http://{host}:{port}/collect'.format(host=device.hostname, port=port)
        req = Request(url)  # nosec — internal network call to a known agent endpoint
        with urlopen(req, timeout=30) as resp:  # noqa: S310
            raw = resp.read().decode('utf-8')

        result.raw_output = raw
        parsed = json.loads(raw)
        validate_canonical(parsed)
        result.parsed_output = parsed
        result.status = 'success'

    except (URLError, OSError) as exc:
        logger.error('Agent pull network error for device "%s": %s', device, exc)
        result.status = 'failed'
        result.error_message = str(exc)
    except Exception as exc:
        logger.exception('Agent pull failed for device "%s".', device)
        result.status = 'failed'
        result.error_message = str(exc)
    finally:
        result.finished_at = timezone.now()
        result.save()

    job.status = result.status
    job.finished_at = timezone.now()
    job.save()

    if result.status == 'success':
        try:
            _apply_baseline_and_drift(device, result)
        except Exception:
            logger.exception('Baseline/drift error for device "%s".', device)

    return {'job_id': job.id, 'result_id': result.id}
