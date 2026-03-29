import hmac
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from django.utils import timezone
from apps.devices.models import Device
from .models import Job, DeviceJobResult
from core.parser.runner import run_parser
from core.canonical import validate_canonical
from apps.baselines.models import Baseline
from apps.drift.detector import detect_drift
from apps.drift.models import DriftEvent
from apps.notifications.syslog import SyslogNotifier


class PushDataView(APIView):
    """
    Receives raw collection data submitted by a device (push mode).
    Authentication is via X-Push-Token header matched against the stored device token.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.headers.get('X-Push-Token', '')
        if not token:
            return Response({'error': 'X-Push-Token header required'}, status=status.HTTP_401_UNAUTHORIZED)

        # Find the matching device via constant-time token comparison.
        # Iterate all active push devices so every token check takes similar time
        # regardless of whether the device exists, preventing enumeration.
        device = None
        for candidate in Device.objects.filter(connection_type='push', is_active=True):
            if candidate.push_token and hmac.compare_digest(str(candidate.push_token), token):
                device = candidate
                break
        if device is None:
            return Response({'error': 'Invalid token'}, status=status.HTTP_401_UNAUTHORIZED)

        raw_data = request.data.get('raw_data', '')
        canonical_data = request.data.get('canonical_data')

        if not raw_data and not canonical_data:
            return Response({'error': 'raw_data or canonical_data required'}, status=status.HTTP_400_BAD_REQUEST)

        policy = (
            device.policies
            .filter(is_active=True)
            .select_related('parser_script')
            .order_by('-updated_at')
            .first()
        )

        job = Job.objects.create(
            policy=policy,
            device=device,
            triggered_by='push',
            status='running',
            started_at=timezone.now(),
        )
        result = DeviceJobResult.objects.create(
            job=job,
            device=device,
            status='running',
            started_at=timezone.now(),
            raw_output=raw_data or '',
        )

        try:
            if canonical_data:
                # Agent outputs canonical JSON directly — skip parsing
                validate_canonical(canonical_data)
                result.parsed_output = canonical_data
                result.status = 'success'
            elif policy and policy.parser_script:
                parsed = run_parser(policy.parser_script.content, raw_data)
                validate_canonical(parsed)
                result.parsed_output = parsed
                result.status = 'success'
            else:
                result.status = 'failed'
                result.error_message = 'No active policy with a parser script found for this device.'
        except Exception as exc:
            result.status = 'failed'
            result.error_message = str(exc)
        finally:
            result.finished_at = timezone.now()
            result.save()

        if result.status == 'success':
            _apply_baseline_and_drift(device, result)

        job.status = result.status
        job.finished_at = timezone.now()
        job.save()

        return Response({'job_id': job.id, 'result_id': result.id}, status=status.HTTP_201_CREATED)


def _apply_baseline_and_drift(device, result):
    baseline, created = Baseline.objects.get_or_create(
        device=device,
        defaults={'parsed_data': result.parsed_output, 'source_result': result},
    )
    if created:
        return
    diffs = detect_drift(baseline.parsed_data, result.parsed_output)
    if diffs:
        event = DriftEvent.objects.create(device=device, job_result=result, diff=diffs)
        SyslogNotifier().notify_drift(device, event)
