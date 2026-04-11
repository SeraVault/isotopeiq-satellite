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
    filterset_fields = ['script_type', 'run_on', 'is_active']
    ordering_fields = ['name', 'created_at']

    @action(detail=False, methods=['post'], url_path='test')
    def test_script(self, request):
        """
        Run a script ad-hoc and return its output.

        Mirrors _execute_steps branching exactly:
          run_on client/both  — send to device via collector (or agent)
          run_on server       — exec as Python via _run_server_step

        Body:
          content   — script source (required)
          run_on    — 'client' | 'server' | 'both' (required)
          language  — e.g. 'shell', 'python', 'powershell'
          device_id — int, required when run_on is 'client' or 'both'
          stdin     — string piped as previous_output for server scripts (optional)
        """
        import io
        import contextlib
        import traceback
        from django.utils import timezone
        from apps.scripts.tasks import _get_collector, _run_agent_script, _run_server_step
        from core.collection.render import render_script

        content   = request.data.get('content', '')
        run_on    = request.data.get('run_on', 'server')
        language  = request.data.get('language', 'shell')
        device_id = request.data.get('device_id')
        stdin     = request.data.get('stdin', '')

        if not content:
            return Response({'error': 'content is required'}, status=status.HTTP_400_BAD_REQUEST)

        device = None
        if device_id:
            from apps.devices.models import Device
            try:
                device = Device.objects.get(pk=device_id, is_active=True)
            except Device.DoesNotExist:
                return Response({'error': 'Device not found'}, status=status.HTTP_404_NOT_FOUND)

        if run_on in ('client', 'both') and not device:
            return Response(
                {'error': 'device_id is required for client scripts'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        started = timezone.now()
        try:
            if run_on in ('client', 'both'):
                rendered = render_script(content, device)
                if device.connection_type == 'agent':
                    output = _run_agent_script(device, rendered, language)
                else:
                    collector = _get_collector(device)
                    output = collector.run(rendered)
                print_output = None
                error = None
            else:  # server
                stdout_cap = io.StringIO()
                with contextlib.redirect_stdout(stdout_cap):
                    output = _run_server_step(content, stdin, device)
                print_output = stdout_cap.getvalue() or None
                error = None
        except Exception as exc:
            output = ''
            print_output = None
            error = ''.join(traceback.format_exception(exc))

        finished = timezone.now()
        duration_ms = int((finished - started).total_seconds() * 1000)

        return Response({
            'output': output,
            'print_output': print_output,
            'error': error,
            'duration_ms': duration_ms,
        })
