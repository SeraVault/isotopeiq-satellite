from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from core.permissions import IsAdminOrReadOnly
from .job_models import ScriptJob, ScriptJobResult
from .job_serializers import ScriptJobSerializer, ScriptJobResultSerializer
from .tasks import run_script_job


class ScriptJobViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrReadOnly]
    queryset = ScriptJob.objects.prefetch_related('steps__script')
    serializer_class = ScriptJobSerializer
    search_fields = ['name', 'description']
    filterset_fields = ['is_active', 'job_type']
    ordering_fields = ['name', 'created_at']

    @action(detail=True, methods=['post'], url_path='run')
    def run(self, request, pk=None):
        """Trigger an immediate (ad-hoc) run of this ScriptJob."""
        script_job = self.get_object()
        device_id = request.data.get('device_id')
        task = run_script_job.delay(
            script_job_id=script_job.pk,
            triggered_by='manual',
            device_id=device_id,
        )
        return Response({'task_id': task.id}, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=['get'], url_path='results')
    def results(self, request, pk=None):
        """List execution history for this ScriptJob."""
        script_job = self.get_object()
        qs = ScriptJobResult.objects.filter(script_job=script_job).select_related('device')
        serializer = ScriptJobResultSerializer(qs, many=True)
        return Response(serializer.data)


class ScriptJobResultViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAdminOrReadOnly]
    queryset = ScriptJobResult.objects.select_related('script_job', 'device')
    serializer_class = ScriptJobResultSerializer
    filterset_fields = ['script_job', 'device', 'status', 'triggered_by']
    ordering_fields = ['started_at']
