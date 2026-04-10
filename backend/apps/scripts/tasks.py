import json
import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


def _get_collector(device):
    from apps.jobs.tasks import _get_collector as _base_get_collector
    return _base_get_collector(device)


def _run_agent_script(device, script_content, language):
    """
    POST a script to the agent's /run endpoint and return its stdout.

    Raises RuntimeError on HTTP error or non-zero exit code.
    """
    from urllib.request import Request, urlopen
    from urllib.error import URLError

    port = device.agent_port or 9322
    url = 'http://{host}:{port}/run'.format(host=device.hostname, port=port)
    payload = json.dumps({'script': script_content, 'language': language}).encode('utf-8')
    headers = {'Content-Type': 'application/json'}
    try:
        from apps.notifications.models import SystemSettings
        _secret = SystemSettings.get().agent_secret or ''
    except Exception:
        _secret = ''
    if _secret:
        headers['X-Agent-Secret'] = _secret
    req = Request(url, data=payload, headers=headers)
    try:
        with urlopen(req, timeout=300) as resp:  # noqa: S310
            result = json.loads(resp.read().decode('utf-8'))
    except URLError as exc:
        raise RuntimeError('Agent unreachable at {0}: {1}'.format(url, exc))

    if result.get('exit_code', -1) != 0:
        raise RuntimeError(
            'Agent script exited {0}: {1}'.format(
                result.get('exit_code'), result.get('stderr', '').strip()
            )
        )
    return result.get('stdout', '')


def _run_server_step(script_content, previous_output, device):
    """
    Execute a server-side script step in an isolated namespace.

    Variables available inside the script:
        raw_output  — stdout string from the previous step (empty string if first step)
        result      — alias for raw_output (parser script compatibility)
        device      — the Device ORM instance (None for server-only jobs)
        output      — canonical-schema dict the script can populate; returned as JSON

    Returns the JSON-serialised `output` dict as a string.
    """
    from core.canonical import CANONICAL_EMPTY

    ns = {
        'raw_output': previous_output,
        'result': previous_output,   # alias for parser-script compatibility
        'device': device,
        'output': {
            k: (v.copy() if isinstance(v, dict) else list(v))
            for k, v in CANONICAL_EMPTY.items()
        },
    }
    exec(script_content, ns)  # noqa: S102 — admin-created scripts only
    result = ns['output']
    # Collection scripts set output to a plain string; return it as-is so the
    # next step (parser) receives raw text in `result`/`raw_output`.
    # Parser scripts set output to a canonical dict; JSON-serialise it.
    if isinstance(result, str):
        return result
    return json.dumps(result)


def _execute_steps(steps, device, collector):
    """
    Execute an ordered list of ScriptJobSteps for a single device.

    Returns:
        step_outputs    — list of {order, script, run_on, output} dicts
        raw_output      — the "primary" output to store (save_output step, else
                          first client step)
        parsed_output   — canonical JSON dict from enable_baseline/enable_drift
                          step (or None)
        any_baseline    — True if at least one step had enable_baseline=True
        any_drift       — True if at least one step had enable_drift=True
    """
    from core.collection.render import render_script
    from core.canonical import validate_canonical

    step_outputs = []
    previous_output = ''
    first_client_output = ''
    final_saved_output = ''
    final_parsed_output = None
    any_baseline = False
    any_drift = False

    for step in steps:
        run_on = step.script.run_on
        if run_on in ('client', 'both'):
            if not device:
                raise ValueError(
                    f'Step {step.order} ("{step.script}") runs on the device '
                    'but no device connection is available.'
                )
            rendered = render_script(step.script.content, device)
            if device.connection_type == 'agent':
                step_out = _run_agent_script(device, rendered, step.script.language)
            else:
                step_out = collector.run(rendered)
            if not first_client_output:
                first_client_output = step_out
        else:  # server
            step_out = _run_server_step(step.script.content, previous_output, device)

        if step.save_output:
            final_saved_output = step_out

        if step.enable_baseline or step.enable_drift:
            parsed = json.loads(step_out)
            validate_canonical(parsed)
            final_parsed_output = parsed
            any_baseline = any_baseline or step.enable_baseline
            any_drift = any_drift or step.enable_drift

        step_outputs.append({
            'order': step.order,
            'script': step.script.name,
            'run_on': run_on,
            'output': step_out,
        })

        previous_output = step_out if step.pipe_to_next else ''

    raw_output = final_saved_output or first_client_output
    return step_outputs, raw_output, final_parsed_output, any_baseline, any_drift


@shared_task(bind=True)
def run_script_job(self, script_job_id: int, triggered_by: str = 'manual', device_id: int = None):
    """
    Execute a ScriptJob by running its ordered pipeline of ScriptJobSteps.
    """
    from .job_models import ScriptJob, ScriptJobResult  # noqa: F401 — imported for side effects

    script_job = (
        ScriptJob.objects
        .prefetch_related('steps__script')
        .get(pk=script_job_id)
    )

    if device_id is not None:
        from apps.devices.models import Device
        try:
            device = Device.objects.get(pk=device_id, is_active=True)
        except Device.DoesNotExist:
            logger.error('run_script_job: device %s not found or inactive.', device_id)
            return
        _run_single(self, script_job, device, triggered_by)
    else:
        # No device — server-only run.
        _run_single(self, script_job, None, triggered_by)


def _run_single(task, script_job, device, triggered_by):
    from .job_models import ScriptJobResult

    result = ScriptJobResult.objects.create(
        script_job=script_job,
        device=device,
        triggered_by=triggered_by,
        status='running',
        started_at=timezone.now(),
        celery_task_id=task.request.id or '',
    )

    any_baseline = False
    any_drift = False

    try:
        steps = list(script_job.steps.select_related('script').order_by('order'))

        collector = _get_collector(device) if device else None

        step_outputs, raw_output, parsed_output, any_baseline, any_drift = _execute_steps(
            steps, device, collector
        )

        result.step_outputs = step_outputs
        result.client_output = raw_output  # legacy field — first client / save_output step
        result.parsed_output = parsed_output
        result.status = 'success'

    except Exception as exc:
        logger.exception(
            'ScriptJob "%s" failed for device "%s".',
            script_job.name,
            device,
        )
        result.status = 'failed'
        result.error_message = str(exc)

    finally:
        result.finished_at = timezone.now()
        result.save()

    # Baseline / Drift — only on success with parsed data
    if result.status == 'success' and result.parsed_output and device:
        if any_baseline or any_drift:
            try:
                _apply_baseline_and_drift(device, result, any_baseline, any_drift, script_job.name)
            except Exception:
                logger.exception(
                    'Baseline/drift error for ScriptJob "%s" device "%s".',
                    script_job.name,
                    device,
                )


def _apply_baseline_and_drift(device, result, enable_baseline, enable_drift, job_label='ScriptJob'):
    """
    Save a device baseline and/or run drift detection against the stored baseline.
    `result` must have a `parsed_output` attribute containing canonical JSON.
    """
    from apps.baselines.models import Baseline
    from apps.drift.detector import detect_drift
    from apps.drift.models import DriftEvent
    from apps.notifications.dispatcher import dispatch_actions

    baseline = Baseline.objects.filter(device=device).first()

    if enable_baseline and baseline is None:
        baseline = Baseline.objects.create(
            device=device,
            parsed_data=result.parsed_output,
            source_result=None,
        )
        logger.info('Baseline established for device "%s" via %s.', device, job_label)
        dispatch_actions('new_baseline', None, device, baseline=baseline)
        return

    if not enable_drift or baseline is None:
        if baseline:
            dispatch_actions('collection_success', None, device, baseline=baseline)
        return

    diffs = detect_drift(baseline.parsed_data, result.parsed_output)
    if diffs:
        existing = DriftEvent.objects.filter(device=device, status='new').order_by('-created_at').first()
        if existing:
            existing.diff = diffs
            existing.baseline_snapshot = baseline.parsed_data
            existing.save(update_fields=['diff', 'baseline_snapshot'])
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
        dispatch_actions('drift_detected', None, device, baseline=baseline, drift_event=drift_event)
    else:
        dispatch_actions('collection_success', None, device, baseline=baseline)


