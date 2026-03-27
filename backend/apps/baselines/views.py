from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from core.permissions import IsAdminOrReadOnly
from .models import Baseline
from .serializers import BaselineSerializer


class BaselineViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAdminOrReadOnly]
    queryset = Baseline.objects.select_related('device').all()
    serializer_class = BaselineSerializer
    filterset_fields = ['device']
    ordering_fields = ['device__name', 'established_at']

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
