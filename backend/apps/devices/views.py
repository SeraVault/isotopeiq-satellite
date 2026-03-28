from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

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
    filterset_fields = ['device_type', 'os_type', 'connection_type', 'is_active']
    ordering_fields = ['name', 'created_at']

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
