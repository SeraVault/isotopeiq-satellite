from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from core.permissions import IsAdminOrReadOnly
from core.canonical import validate_canonical
from apps.devices.models import Device
from apps.drift.detector import detect_drift
from apps.drift.models import DriftEvent
from apps.jobs.models import Job, DeviceJobResult
from apps.notifications.syslog import SyslogNotifier
from .models import Baseline
from .serializers import BaselineSerializer, BaselineListSerializer


class BaselineViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAdminOrReadOnly]
    queryset = Baseline.objects.select_related('device').all()
    serializer_class = BaselineSerializer
    filterset_fields = ['device']
    ordering_fields = ['device__name', 'established_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return BaselineListSerializer
        return BaselineSerializer

    @action(detail=False, methods=['post'], url_path='import')
    def import_baseline(self, request):
        """
        Manually import a canonical JSON baseline for a device.

        Body: { "device_id": <int>, "canonical_data": { ... } }

        Validates the canonical schema, creates a Job/DeviceJobResult for audit
        purposes, runs drift detection against the existing baseline (if any),
        then writes the new baseline directly.
        """
        device_id = request.data.get('device_id')
        canonical_data = request.data.get('canonical_data')

        if not device_id:
            return Response({'error': 'device_id required'}, status=status.HTTP_400_BAD_REQUEST)
        if not canonical_data:
            return Response({'error': 'canonical_data required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            device = Device.objects.get(pk=device_id, is_active=True)
        except Device.DoesNotExist:
            return Response({'error': 'Device not found'}, status=status.HTTP_404_NOT_FOUND)

        try:
            validate_canonical(canonical_data)
        except Exception as exc:
            return Response({'error': f'Invalid canonical data: {exc}'}, status=status.HTTP_400_BAD_REQUEST)

        now = timezone.now()
        job = Job.objects.create(
            device=device,
            triggered_by='import',
            status='running',
            started_at=now,
        )
        result = DeviceJobResult.objects.create(
            job=job,
            device=device,
            status='success',
            started_at=now,
            finished_at=now,
            parsed_output=canonical_data,
        )
        job.status = 'success'
        job.finished_at = now
        job.save()

        baseline, created = Baseline.objects.get_or_create(
            device=device,
            defaults={
                'parsed_data': canonical_data,
                'source_result': result,
                'established_by': request.user.username,
            },
        )
        drift_count = 0
        if not created:
            diffs = detect_drift(baseline.parsed_data, canonical_data)
            if diffs:
                event = DriftEvent.objects.create(device=device, job_result=result, diff=diffs,
                                                  baseline_snapshot=baseline.parsed_data)
                SyslogNotifier().notify_drift(device, event)
                drift_count = len(diffs)
            baseline.parsed_data = canonical_data
            baseline.source_result = result
            baseline.established_by = request.user.username
            baseline.save()
        else:
            from apps.notifications.dispatcher import dispatch_actions
            dispatch_actions('new_baseline', None, device, baseline=baseline)

        return Response(
            {
                'baseline_id': baseline.id,
                'job_id': job.id,
                'created': created,
                'drift_changes': drift_count,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'])
    def send(self, request, pk=None):
        """Ad-hoc export/notification for a single baseline.

        Body: { "destination": "syslog" | "email" | "ftp" }
        """
        baseline = self.get_object()
        destination = request.data.get('destination', '')
        valid = {'syslog', 'email', 'ftp'}
        if destination not in valid:
            return Response(
                {'error': f'destination must be one of: {", ".join(sorted(valid))}'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from apps.notifications.dispatcher import dispatch_adhoc
        dispatch_adhoc(destination, baseline.device, baseline)
        return Response({'status': 'dispatched', 'destination': destination})

