from celery.app.control import Control  # noqa: F401 (imported for side-effects)
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsAdminOrReadOnly
from .filters import JobFilter
from .models import Job, DeviceJobResult
from .serializers import JobSerializer, JobListSerializer, DeviceJobResultSerializer

class JobViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAdminOrReadOnly]
    queryset = Job.objects.prefetch_related('device_results__device').select_related('policy', 'device').all()
    serializer_class = JobSerializer
    filterset_class = JobFilter
    ordering_fields = ['created_at', 'started_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return JobListSerializer
        return JobSerializer

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """
        Cancel a running or pending job.

        Revokes the Celery task (with terminate=True so the worker process is
        killed if it is already executing) and marks the job and any still-
        running device results as cancelled.
        """
        from celery import current_app

        job = self.get_object()

        if job.status not in ('pending', 'running'):
            return Response(
                {'detail': f'Job is already {job.status} and cannot be cancelled.'},
                status=status.HTTP_409_CONFLICT,
            )

        # Revoke the Celery task so the worker stops (or never starts) it.
        if job.celery_task_id:
            current_app.control.revoke(job.celery_task_id, terminate=True, signal='SIGTERM')

        now = timezone.now()
        job.status = 'cancelled'
        job.finished_at = job.finished_at or now
        job.save(update_fields=['status', 'finished_at'])

        # Mark any device results that haven't finished yet.
        job.device_results.filter(status__in=['pending', 'running']).update(
            status='cancelled',
            finished_at=now,
        )

        # Also cancel any sibling jobs that share the same Celery task
        # (created in the same run_policy invocation but not yet started).
        if job.celery_task_id:
            Job.objects.filter(
                celery_task_id=job.celery_task_id,
                status__in=['pending', 'running'],
            ).exclude(pk=job.pk).update(status='cancelled', finished_at=now)

        return Response({'detail': 'Job cancelled.'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='trigger-agent-pull')
    def trigger_agent_pull(self, request):
        """
        Enqueue an asynchronous agent-pull job for a device.

        Request body: { "device_id": <int> }

        The device must have connection_type='agent' and be active.
        Returns 202 Accepted with the Celery task ID.
        """
        from apps.devices.models import Device
        from .tasks import run_agent_pull

        device_id = request.data.get('device_id')
        if not device_id:
            return Response({'detail': 'device_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            device = Device.objects.get(pk=device_id, connection_type='agent', is_active=True)
        except Device.DoesNotExist:
            return Response(
                {'detail': 'No active agent device found with that id.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        task = run_agent_pull.delay(device.id, triggered_by='manual')
        return Response(
            {'detail': 'Agent pull triggered.', 'task_id': task.id},
            status=status.HTTP_202_ACCEPTED,
        )


class DeviceJobResultViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAdminOrReadOnly]
    queryset = DeviceJobResult.objects.select_related('device', 'job').all()
    serializer_class = DeviceJobResultSerializer
    filterset_fields = ['job', 'device', 'status']
    ordering_fields = ['started_at']


class UnifiedJobListView(APIView):
    """
    Single endpoint that merges policy Job runs and bundle ScriptJobResult runs
    into one chronological list.  Clients receive a common shape with a
    `record_type` discriminator ('policy_job' | 'bundle_run') and `record_id`
    pointing to the original model PK for detail fetches.
    """
    permission_classes = [IsAdminOrReadOnly]

    def get(self, request):
        from django.utils.dateparse import parse_datetime
        from apps.scripts.job_models import ScriptJobResult

        try:
            page = max(1, int(request.query_params.get('page', 1)))
            page_size = min(100, max(1, int(request.query_params.get('page_size', 25))))
        except (ValueError, TypeError):
            page, page_size = 1, 25

        rf_type   = request.query_params.get('type')    # 'policy_job' | 'bundle_run'
        rf_status = request.query_params.get('status')
        rf_device = request.query_params.get('device')
        rf_after  = request.query_params.get('created_after')
        rf_before = request.query_params.get('created_before')

        # Fetch enough records from each side to slice the requested page.
        # Over-fetching page*page_size from each guarantees a correct merge.
        limit = page * page_size

        items = []

        # ── Policy Jobs ───────────────────────────────────────────────────────
        if rf_type in (None, 'policy_job'):
            qs = Job.objects.select_related('policy', 'device').order_by('-started_at', '-created_at')
            if rf_status: qs = qs.filter(status=rf_status)
            if rf_device: qs = qs.filter(device=rf_device)
            if rf_after:  qs = qs.filter(started_at__gte=parse_datetime(rf_after))
            if rf_before: qs = qs.filter(started_at__lte=parse_datetime(rf_before))
            for j in qs[:limit]:
                items.append({
                    'record_type': 'policy_job',
                    'record_id':   j.pk,
                    'device':      j.device_id,
                    'device_name': j.device.name if j.device else None,
                    'source':      j.policy.name if j.policy else 'Ad-hoc',
                    'triggered_by': j.triggered_by,
                    'status':      j.status,
                    'started_at':  j.started_at,
                    'finished_at': j.finished_at,
                })

        # ── Bundle Runs ───────────────────────────────────────────────────────
        if rf_type in (None, 'bundle_run'):
            qs = ScriptJobResult.objects.select_related('script_job', 'device').order_by('-started_at')
            if rf_status: qs = qs.filter(status=rf_status)
            if rf_device: qs = qs.filter(device=rf_device)
            if rf_after:  qs = qs.filter(started_at__gte=parse_datetime(rf_after))
            if rf_before: qs = qs.filter(started_at__lte=parse_datetime(rf_before))
            for r in qs[:limit]:
                items.append({
                    'record_type': 'bundle_run',
                    'record_id':   r.pk,
                    'device':      r.device_id,
                    'device_name': r.device.name if r.device else None,
                    'source':      r.script_job.name,
                    'triggered_by': r.triggered_by,
                    'status':      r.status,
                    'started_at':  r.started_at,
                    'finished_at': r.finished_at,
                })

        # ── Count ─────────────────────────────────────────────────────────────
        total = 0
        if rf_type in (None, 'policy_job'):
            cqs = Job.objects
            if rf_status: cqs = cqs.filter(status=rf_status)
            if rf_device: cqs = cqs.filter(device=rf_device)
            total += cqs.count()
        if rf_type in (None, 'bundle_run'):
            cqs = ScriptJobResult.objects
            if rf_status: cqs = cqs.filter(status=rf_status)
            if rf_device: cqs = cqs.filter(device=rf_device)
            total += cqs.count()

        # ── Merge, sort, paginate ─────────────────────────────────────────────
        EPOCH = timezone.datetime.min.replace(tzinfo=timezone.utc)
        items.sort(key=lambda x: x['started_at'] or EPOCH, reverse=True)

        offset = (page - 1) * page_size
        page_items = items[offset:offset + page_size]

        for item in page_items:
            item['started_at']  = item['started_at'].isoformat()  if item['started_at']  else None
            item['finished_at'] = item['finished_at'].isoformat() if item['finished_at'] else None

        return Response({'count': total, 'results': page_items})
