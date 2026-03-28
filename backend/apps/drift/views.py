from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone

from core.canonical import VOLATILE_FIELDS
from core.permissions import IsAdminOrDriftAction
from .models import DriftEvent
from .serializers import DriftEventSerializer


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def volatile_fields(request):
    """Return the volatile field definitions used for drift comparison."""
    # Convert sets to lists for JSON serialisation
    serialisable = {}
    for section, spec in VOLATILE_FIELDS.items():
        serialisable[section] = {}
        if 'fields' in spec:
            serialisable[section]['fields'] = list(spec['fields'])
        if 'items' in spec:
            serialisable[section]['items'] = list(spec['items'])
        if 'nested' in spec:
            serialisable[section]['nested'] = {
                k: list(v) for k, v in spec['nested'].items()
            }
    return Response(serialisable)


class DriftEventViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAdminOrDriftAction]
    queryset = DriftEvent.objects.select_related('device', 'job_result').all()
    serializer_class = DriftEventSerializer
    filterset_fields = ['device', 'status']
    ordering_fields = ['created_at']

    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        reason = request.data.get('reason', '').strip()
        if not reason:
            return Response({'error': 'A reason is required to acknowledge drift.'}, status=status.HTTP_400_BAD_REQUEST)
        event = self.get_object()
        event.status = 'acknowledged'
        event.acknowledged_by = request.user.username
        event.acknowledged_at = timezone.now()
        event.acknowledgement_reason = reason
        event.save()

        # Promote the collection result that triggered this drift event
        # as the new official baseline for the device.
        result = event.job_result
        if result and result.parsed_output:
            from apps.baselines.models import Baseline
            Baseline.objects.filter(device=event.device).update(
                parsed_data=result.parsed_output,
                source_result=result,
                established_by=request.user.username,
            )

        return Response(DriftEventSerializer(event).data)

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        event = self.get_object()
        event.status = 'resolved'
        event.save()
        return Response(DriftEventSerializer(event).data)
