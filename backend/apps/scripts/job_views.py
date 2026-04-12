from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from core.permissions import IsAdminOrReadOnly
from .job_models import ScriptJob, ScriptJobResult
from .job_serializers import ScriptJobSerializer, ScriptJobResultSerializer
from .pack import export_script_job, import_script_pack
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

    @action(detail=True, methods=['get'], url_path='export')
    def export(self, request, pk=None):
        """
        Export this ScriptJob and all its referenced scripts as a portable
        Script Pack (JSON).

        Response body is the pack dict.  The Content-Disposition header
        suggests a filename so browsers / fetch clients can save it directly.
        """
        script_job = self.get_object()
        pack = export_script_job(script_job)
        safe_name = script_job.name.lower().replace(' ', '_')
        response = Response(pack)
        response['Content-Disposition'] = f'attachment; filename="{safe_name}.scriptpack.json"'
        return response

    @action(detail=False, methods=['post'], url_path='import')
    def import_pack(self, request):
        """
        Import a Script Pack JSON document.

        Request body:
            pack      object  required — the full pack document
            overwrite bool    optional — if true, update existing scripts/jobs
                                         with the same name (default: false)

        Response:
            summary   object  — created/updated/skipped counts per resource type
        """
        pack = request.data.get('pack')
        if not pack or not isinstance(pack, dict):
            return Response(
                {'error': "'pack' must be a JSON object."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        overwrite = bool(request.data.get('overwrite', False))

        try:
            summary = import_script_pack(pack, overwrite=overwrite)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:  # noqa: BLE001
            return Response(
                {'error': f'Import failed: {exc}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(summary, status=status.HTTP_200_OK)


class ScriptJobResultViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAdminOrReadOnly]
    queryset = ScriptJobResult.objects.select_related('script_job', 'device')
    serializer_class = ScriptJobResultSerializer
    filterset_fields = ['script_job', 'device', 'status', 'triggered_by']
    ordering_fields = ['started_at']
