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


def _apply_baseline_and_drift(device, result, enable_baseline=True, enable_drift=True) -> None:
    from apps.baselines.models import Baseline
    from apps.drift.detector import detect_drift
    from apps.drift.models import DriftEvent
    from apps.notifications.dispatcher import dispatch_actions

    policy = getattr(getattr(result, 'job', None), 'policy', None)

    baseline = Baseline.objects.filter(device=device).first()

    if enable_baseline and baseline is None:
        baseline = Baseline.objects.create(
            device=device,
            parsed_data=result.parsed_output,
            source_result=result,
        )
        logger.info('Baseline established for device "%s".', device)
        dispatch_actions('new_baseline', policy, device, baseline=baseline)
        return

    if not enable_drift or baseline is None:
        if baseline:
            dispatch_actions('collection_success', policy, device, baseline=baseline)
        return

    diffs = detect_drift(baseline.parsed_data, result.parsed_output)
    if diffs:
        existing = DriftEvent.objects.filter(device=device, status='new').order_by('-created_at').first()
        if existing:
            existing.diff = diffs
            existing.job_result = result
            existing.baseline_snapshot = baseline.parsed_data
            existing.save(update_fields=['diff', 'job_result', 'baseline_snapshot'])
            logger.warning('Drift updated for device "%s" (event %s).', device, existing.pk)
            drift_event = existing
        else:
            drift_event = DriftEvent.objects.create(
                device=device,
                job_result=result,
                diff=diffs,
                baseline_snapshot=baseline.parsed_data,
            )
            logger.warning('Drift detected for device "%s" (event %s).', device, drift_event.pk)
        dispatch_actions('drift_detected', policy, device, baseline=baseline, drift_event=drift_event)
    else:
        dispatch_actions('collection_success', policy, device, baseline=baseline)


@shared_task(bind=True)
def run_policy(self, policy_id: int, triggered_by: str = 'scheduler', device_id: int = None):
    from apps.policies.models import Policy

    policy = (
        Policy.objects
        .prefetch_related('devices', 'script_job__steps__script')
        .get(pk=policy_id)
    )

    if policy.collection_method == 'script':
        config_error = None
        if not policy.script_job:
            config_error = 'Policy misconfigured: no Script Job assigned.'
        elif not policy.script_job.steps.exists():
            config_error = 'Policy misconfigured: Script Job has no steps.'
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

    _eligible = _SUPPORTED_CONNECTION_TYPES + ('agent',)
    all_active = list(policy.devices.filter(is_active=True))

    if policy.collection_method == 'agent':
        eligible = [d for d in all_active if d.connection_type == 'agent']
        skipped  = [d for d in all_active if d.connection_type != 'agent']
    else:
        eligible = [d for d in all_active if d.connection_type in _eligible]
        skipped  = [d for d in all_active if d.connection_type not in _eligible]

    if device_id is not None:
        eligible = [d for d in eligible if d.id == device_id]
        skipped  = [d for d in skipped  if d.id == device_id]

    # Create failed Job records for devices whose connection type is incompatible
    # with this policy so they show up in the job monitor rather than silently disappearing.
    for device in skipped:
        expected = 'agent' if policy.collection_method == 'agent' else '/'.join(_SUPPORTED_CONNECTION_TYPES + ('agent',))
        msg = (
            f'Device skipped: connection type "{device.connection_type}" is not compatible '
            f'with this policy\'s collection method "{policy.collection_method}" '
            f'(expected {expected}).'
        )
        logger.warning('run_policy id=%s: %s (device=%s)', policy_id, msg, device)
        _now = timezone.now()
        _job = Job.objects.create(
            policy=policy, device=device, triggered_by=triggered_by,
            status='failed', started_at=_now, finished_at=_now,
            celery_task_id=self.request.id or '',
        )
        DeviceJobResult.objects.create(
            job=_job, device=device,
            status='failed', started_at=_now, finished_at=_now,
            error_message=msg,
        )

    # Guard: if no eligible devices remain emit a single failed sentinel job.
    if not eligible:
        _now = timezone.now()
        msg = (
            'No eligible devices for this policy run. '
            'Check that assigned devices are active and have a compatible connection type.'
        )
        logger.warning('run_policy id=%s: %s', policy_id, msg)
        Job.objects.create(
            policy=policy, device=None, triggered_by=triggered_by,
            status='failed', started_at=_now, finished_at=_now,
            celery_task_id=self.request.id or '',
        )
        return

    if policy.collection_method == 'agent':
        # Agent pull: call GET /collect on each eligible agent device.
        for idx, device in enumerate(eligible):
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
                req = Request(url)  # nosec — internal network call to a known agent endpoint
                try:
                    from apps.notifications.models import SystemSettings
                    _secret = SystemSettings.get().agent_secret or ''
                except Exception:
                    _secret = ''
                if _secret:
                    req.add_header('X-Agent-Secret', _secret)
                with urlopen(req, timeout=300) as resp:  # noqa: S310
                    raw = resp.read().decode('utf-8')
                result.raw_output = raw
                parsed = json.loads(raw)
                validate_canonical(parsed)
                result.parsed_output = parsed
                result.status = 'success'
            except (URLError, OSError) as exc:
                logger.error('Agent pull network error for device "%s" in job %s: %s', device, job.id, exc)
                result.status = 'failed'
                result.error_message = str(exc)
            except Exception as exc:
                logger.exception('Agent pull failed for device "%s" in job %s.', device, job.id)
                result.status = 'failed'
                result.error_message = str(exc)
            finally:
                result.finished_at = timezone.now()
                result.save()

            job.status = result.status
            job.finished_at = timezone.now()
            job.save()

            if result.status == 'success' and result.parsed_output:
                try:
                    _apply_baseline_and_drift(device, result)
                except Exception:
                    logger.exception('Baseline/drift error for device "%s".', device)

            if policy.delay_between_devices and idx < len(eligible) - 1:
                time.sleep(policy.delay_between_devices)

    else:
        # ── Script policies — SSH / WinRM / Telnet / Agent-with-scripts ───────
        # _execute_steps routes each step to the right transport based on
        # device.connection_type and script.run_on, so a single loop handles all.
        from apps.scripts.tasks import _execute_steps
        sj_steps = list(policy.script_job.steps.select_related('script').order_by('order'))

        for idx, device in enumerate(eligible):
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

            any_baseline = any_drift = False
            try:
                collector = _get_collector(device) if device.connection_type != 'agent' else None
                step_outputs, raw_output, parsed_output, any_baseline, any_drift = _execute_steps(
                    sj_steps, device, collector
                )
                result.raw_output = raw_output
                result.parsed_output = parsed_output
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

            if result.status == 'success' and result.parsed_output and (any_baseline or any_drift):
                try:
                    _apply_baseline_and_drift(device, result, enable_baseline=any_baseline, enable_drift=any_drift)
                except Exception:
                    logger.exception('Baseline/drift error for device "%s".', device)

            if policy.delay_between_devices and idx < len(eligible) - 1:
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
        try:
            from apps.notifications.models import SystemSettings
            _secret = SystemSettings.get().agent_secret or ''
        except Exception:
            _secret = ''
        if _secret:
            req.add_header('X-Agent-Secret', _secret)
        with urlopen(req, timeout=300) as resp:  # noqa: S310
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
