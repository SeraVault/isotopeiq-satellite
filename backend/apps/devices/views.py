from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsAdminOrReadOnly
from .models import Credential, Device
from .serializers import CredentialSerializer, DeviceSerializer


class CredentialViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrReadOnly]
    queryset = Credential.objects.all()
    serializer_class = CredentialSerializer
    search_fields = ['name']
    filterset_fields = ['credential_type']
    ordering_fields = ['name', 'created_at']


class DeviceViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrReadOnly]
    queryset = Device.objects.select_related('credential').all()
    serializer_class = DeviceSerializer
    search_fields = ['name', 'hostname', 'fqdn']
    filterset_fields = ['connection_type', 'is_active']
    ordering_fields = ['name', 'created_at']

    def perform_create(self, serializer):
        import secrets
        data = serializer.validated_data
        plaintext_token = None
        if data.get('connection_type') == 'agent' and not data.get('agent_token'):
            plaintext_token = secrets.token_hex(32)
            instance = serializer.save(agent_token=plaintext_token)
        else:
            instance = serializer.save()
        # Stash plaintext token so create() can include it in the response.
        instance._plaintext_agent_token = plaintext_token

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = serializer.instance
        headers = self.get_success_headers(serializer.data)
        response_data = serializer.data
        if getattr(instance, '_plaintext_agent_token', None):
            response_data = dict(response_data)
            response_data['agent_token'] = instance._plaintext_agent_token
        return Response(response_data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=True, methods=['post'], url_path='regenerate-token')
    def regenerate_token(self, request, pk=None):
        """Generate a new agent token for this device and return it in plaintext (only time it is readable)."""
        import secrets
        device = self.get_object()
        plaintext_token = secrets.token_hex(32)
        device.agent_token = plaintext_token
        device.save(update_fields=['agent_token', 'updated_at'])
        return Response({'agent_token': plaintext_token})

    @action(detail=True, methods=['get'], url_path='agent-bundle')
    def agent_bundle(self, request, pk=None):
        """
        Return a ZIP containing isotopeiq-agent.conf and the installer script
        for the requested OS.  Query param: ?os=windows|linux|macos (default linux).
        """
        import io
        import zipfile
        from pathlib import Path
        from django.http import HttpResponse

        from django.conf import settings as django_settings
        from apps.notifications.models import SystemSettings

        device = self.get_object()

        os_name = request.query_params.get('os', 'linux')
        installer_map = {
            'windows': 'windows_install.bat',
            'linux':   'linux_install.sh',
            'macos':   'macos_install.sh',
        }
        installer_file = installer_map.get(os_name, 'linux_install.sh')

        # Use the admin-configured satellite URL; fall back to the env/settings value.
        sys_settings = SystemSettings.objects.first()
        server_url = (
            sys_settings.satellite_url.rstrip('/')
            if sys_settings and sys_settings.satellite_url
            else getattr(django_settings, 'SATELLITE_URL', 'http://localhost:8000').rstrip('/')
        )

        token = device.agent_token or ''
        port  = device.agent_port or 9322
        config_content = f"server={server_url}\ntoken={token}\nport={port}\n"

        installer_path = Path('/agents/installers') / installer_file

        # Binaries to include per OS (all must live in /agents/)
        binary_map = {
            'windows': ['windows_collector.exe'],
            'linux':   ['linux_collector_amd64', 'linux_collector_i686'],
            'macos':   ['macos_collector'],
        }
        binaries = binary_map.get(os_name, [])

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('isotopeiq-agent.conf', config_content)
            if installer_path.is_file():
                zf.write(str(installer_path), installer_file)
            for binary in binaries:
                binary_path = Path('/agents') / binary
                if binary_path.is_file():
                    zf.write(str(binary_path), binary)
        buf.seek(0)

        import re
        safe_name = re.sub(r'[^\w\-.]', '_', device.name)
        response = HttpResponse(buf.read(), content_type='application/zip')
        zip_name  = f"isotopeiq-agent-{safe_name}-{os_name}.zip"
        response['Content-Disposition'] = f'attachment; filename="{zip_name}"'
        return response

    @action(detail=True, methods=['post'])
    def collect(self, request, pk=None):
        """Trigger an immediate collection for this device using one of its active policies."""
        from apps.jobs.tasks import run_policy

        device = self.get_object()
        policy_id = request.data.get('policy_id')

        policies = device.policies.filter(is_active=True).select_related(
            'script_package__collection_script', 'script_package__parser_script'
        )
        if policy_id:
            policy = policies.filter(pk=policy_id).first()
            if not policy:
                return Response({'detail': 'Policy not found or not active for this device.'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            policy = policies.first()
            if not policy:
                return Response({'detail': 'No active policy assigned to this device.'}, status=status.HTTP_400_BAD_REQUEST)

        if policy.collection_method == 'script':
            pkg = policy.script_package
            if not pkg or not pkg.collection_script or not pkg.parser_script:
                return Response(
                    {'detail': f'Policy "{policy.name}" requires a Collection Profile with both a collection and a parser script.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        task = run_policy.delay(policy.id, triggered_by='manual', device_id=device.id)
        return Response({'detail': f'Collection started using policy "{policy.name}".', 'task_id': task.id}, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=['post'], url_path='test-connection')
    def test_connection(self, request, pk=None):
        """Test connection to a saved device using its stored credentials."""
        device = self.get_object()
        return _run_connection_test(
            connection_type=device.connection_type,
            hostname=device.hostname,
            port=device.port,
            credential=device.credential,
            username=getattr(device, 'username', None),
            password=getattr(device, 'password', None),
            host_key=device.host_key,
        )

    @action(detail=False, methods=['post'], url_path='test-connection')
    def test_connection_inline(self, request):
        """
        Test a connection using parameters supplied in the request body —
        no saved device required. Accepts the same fields as the Device form.

        Body fields:
          connection_type, hostname, port, host_key (optional),
          credential (ID, optional), username, password
        """
        d = request.data
        credential = None
        cred_id = d.get('credential')
        if cred_id:
            try:
                credential = Credential.objects.get(pk=cred_id)
            except Credential.DoesNotExist:
                return Response({'detail': 'Credential not found.'}, status=status.HTTP_400_BAD_REQUEST)

        return _run_connection_test(
            connection_type=d.get('connection_type', 'ssh'),
            hostname=d.get('hostname', ''),
            port=int(d.get('port', 22)),
            credential=credential,
            username=d.get('username', ''),
            password=d.get('password', ''),
            host_key=d.get('host_key', ''),
        )


# ── helpers ────────────────────────────────────────────────────────────────

def _run_connection_test(connection_type, hostname, port, credential,
                         username, password, host_key):
    """Shared logic for both saved-device and inline connection tests."""
    if connection_type not in ('ssh', 'telnet', 'winrm'):
        return Response(
            {'detail': f'Test connection is not supported for connection type "{connection_type}".'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not hostname:
        return Response({'detail': 'hostname is required.'}, status=status.HTTP_400_BAD_REQUEST)

    # Build a lightweight proxy object the collectors accept
    class _DeviceProxy:
        pass

    dev = _DeviceProxy()
    dev.hostname = hostname
    dev.port = port
    dev.host_key = host_key or ''
    dev.name = hostname
    dev.credential = credential

    # Inline credential fields (used when no Credential record is linked)
    dev.username = username or ''
    dev.password = password or ''
    dev.ssh_private_key = ''

    try:
        if connection_type == 'ssh':
            from core.collection.ssh import SSHCollector
            SSHCollector(dev).run('true')
        elif connection_type == 'telnet':
            from core.collection.telnet import TelnetCollector
            TelnetCollector(dev).run('true')
        else:
            from core.collection.winrm import WinRMCollector
            collector = WinRMCollector(dev)
            collector.run('Write-Output ok')
            # Attempt to raise the WinRM envelope size limit now so that
            # large collection scripts succeed. Requires admin on target —
            # silently ignored if it fails.
            _winrm_configure_envelope(collector)
            return Response({'success': True, 'detail': _WINRM_ONBOARDING_DETAIL}, status=status.HTTP_200_OK)
    except Exception as exc:
        return Response({'success': False, 'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response({'success': True, 'detail': 'Connection successful.'}, status=status.HTTP_200_OK)


_WINRM_ONBOARDING_DETAIL = (
    'Connection successful.\n\n'
    'To ensure large collection scripts work, run the following on the\n'
    'Windows target as Administrator (if not already applied):\n\n'
    '  Set-Item -Path WSMan:\\localhost\\MaxEnvelopeSizeKb -Value 8192\n\n'
    'IsotopeIQ has attempted to apply this automatically.'
)


def _winrm_configure_envelope(collector):
    """Best-effort: raise WinRM envelope size on the target after connection test."""
    try:
        collector.run(
            'Set-Item -Path WSMan:\\localhost\\MaxEnvelopeSizeKb'
            ' -Value 8192 -ErrorAction SilentlyContinue'
        )
    except Exception:
        pass



