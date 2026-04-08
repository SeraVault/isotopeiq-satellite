from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from core.permissions import IsAdminOrReadOnly
from .models import Script
from .serializers import ScriptSerializer


class ScriptViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrReadOnly]
    queryset = Script.objects.all()
    serializer_class = ScriptSerializer
    search_fields = ['name', 'description']
    filterset_fields = ['script_type', 'run_on', 'target_os', 'is_active']
    ordering_fields = ['name', 'created_at']

    @action(detail=False, methods=['post'], url_path='test')
    def test_script(self, request):
        """
        Run a script ad-hoc and return its output.

        Body:
          content   — script source (required)
          run_on    — 'client' | 'server' (required)
          language  — e.g. 'shell', 'python', 'powershell' (informational for client)
          device_id — int, required when run_on == 'client'
          stdin     — string piped as previous_output for server scripts (optional)
        """
        import json
        import traceback
        from django.utils import timezone

        content   = request.data.get('content', '')
        run_on    = request.data.get('run_on', 'server')
        device_id = request.data.get('device_id')
        stdin     = request.data.get('stdin', '')

        if not content:
            return Response({'error': 'content is required'}, status=status.HTTP_400_BAD_REQUEST)

        started = timezone.now()

        if run_on == 'client':
            if not device_id:
                return Response(
                    {'error': 'device_id is required for client scripts'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                from apps.devices.models import Device
                from apps.jobs.tasks import _get_collector
                from core.collection.render import render_script

                device = Device.objects.get(pk=device_id, is_active=True)
                rendered = render_script(content, device)
                collector = _get_collector(device)
                output = collector.run(rendered)
                error = None
            except Device.DoesNotExist:
                return Response({'error': 'Device not found'}, status=status.HTTP_404_NOT_FOUND)
            except Exception as exc:
                output = ''
                error = ''.join(traceback.format_exception(exc))
        else:  # server
            try:
                from apps.scripts.tasks import _run_server_step
                device = None
                if device_id:
                    from apps.devices.models import Device
                    try:
                        device = Device.objects.get(pk=device_id, is_active=True)
                    except Device.DoesNotExist:
                        pass
                output = _run_server_step(content, stdin, device)
                error = None
            except Exception as exc:
                output = ''
                error = ''.join(traceback.format_exception(exc))

        finished = timezone.now()
        duration_ms = int((finished - started).total_seconds() * 1000)

        return Response({
            'output': output,
            'error': error,
            'duration_ms': duration_ms,
        })
