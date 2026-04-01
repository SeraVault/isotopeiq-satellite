from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from core.permissions import IsAdminOrReadOnly
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

    @action(detail=True, methods=['post'])
    def promote(self, request, pk=None):
        """Promote a DeviceJobResult's parsed output as the new baseline for its device."""
        baseline = self.get_object()
        result_id = request.data.get('result_id')
        if not result_id:
            return Response({'error': 'result_id required'}, status=status.HTTP_400_BAD_REQUEST)
        from apps.jobs.models import DeviceJobResult
        try:
            result = DeviceJobResult.objects.get(pk=result_id, device=baseline.device)
        except DeviceJobResult.DoesNotExist:
            return Response({'error': 'Result not found for this device'}, status=status.HTTP_404_NOT_FOUND)
        if result.parsed_output is None:
            return Response({'error': 'Result has no parsed output'}, status=status.HTTP_400_BAD_REQUEST)
        baseline.parsed_data = result.parsed_output
        baseline.source_result = result
        baseline.established_by = request.user.username
        baseline.save()
        return Response(BaselineSerializer(baseline).data)

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
