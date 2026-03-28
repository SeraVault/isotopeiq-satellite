from celery.app.control import Control  # noqa: F401 (imported for side-effects)
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from core.permissions import IsAdminOrReadOnly
from .filters import JobFilter
from .models import Job, DeviceJobResult
from .serializers import JobSerializer, JobListSerializer, DeviceJobResultSerializer


class JobViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAdminOrReadOnly]
    queryset = Job.objects.prefetch_related('device_results__device').select_related('policy').all()
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
        from django.utils import timezone
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

        return Response({'detail': 'Job cancelled.'}, status=status.HTTP_200_OK)


class DeviceJobResultViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAdminOrReadOnly]
    queryset = DeviceJobResult.objects.select_related('device', 'job').all()
    serializer_class = DeviceJobResultSerializer
    filterset_fields = ['job', 'device', 'status']
    ordering_fields = ['started_at']
