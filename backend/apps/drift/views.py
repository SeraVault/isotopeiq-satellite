from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from core.permissions import IsAdminOrDriftAction, IsAdminOrReadOnly
from .models import DriftEvent, VolatileFieldRule
from .serializers import DriftEventSerializer, DriftEventDetailSerializer, VolatileFieldRuleSerializer
from .volatile_utils import get_volatile_spec, invalidate_spec_cache, build_spec_from_rules


def _broadcast_drift(event) -> None:
    layer = get_channel_layer()
    if not layer:
        return
    data = dict(DriftEventSerializer(event).data)
    async_to_sync(layer.group_send)('drift', {'type': 'drift.event', 'data': data})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def volatile_fields(request):
    """Return the volatile field definitions used for drift comparison (from DB)."""
    spec = get_volatile_spec()
    # Convert sets to lists for JSON serialisation
    serialisable = {}
    for section, entry in spec.items():
        serialisable[section] = {}
        if 'fields' in entry:
            serialisable[section]['fields'] = list(entry['fields'])
        if 'items' in entry:
            serialisable[section]['items'] = list(entry['items'])
        if 'nested' in entry:
            serialisable[section]['nested'] = {
                k: list(v) for k, v in entry['nested'].items()
            }
        if 'exclude_keys' in entry:
            serialisable[section]['exclude_keys'] = {
                'key_field': entry['exclude_keys']['key_field'],
                'values': list(entry['exclude_keys']['values']),
            }
        if entry.get('exclude_section'):
            serialisable[section]['exclude_section'] = True
    return Response(serialisable)


class VolatileFieldRuleViewSet(viewsets.ModelViewSet):
    """CRUD for volatile field rules.  Write access is admin-only."""
    permission_classes = [IsAdminOrReadOnly]
    queryset = VolatileFieldRule.objects.all()
    serializer_class = VolatileFieldRuleSerializer
    ordering_fields = ['section', 'spec_type', 'field_name', 'is_active']
    ordering = ['section', 'spec_type', 'field_name']

    def perform_create(self, serializer):
        serializer.save()
        invalidate_spec_cache()

    def perform_update(self, serializer):
        serializer.save()
        invalidate_spec_cache()

    def perform_destroy(self, instance):
        instance.delete()
        invalidate_spec_cache()


class DriftEventViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAdminOrDriftAction]
    queryset = DriftEvent.objects.select_related('device', 'job_result').all()
    serializer_class = DriftEventSerializer
    filterset_fields = ['device', 'status']
    ordering_fields = ['created_at', 'status', 'device__name']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action in ('retrieve', 'acknowledge', 'resolve'):
            return DriftEventDetailSerializer
        return DriftEventSerializer

    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        reason = request.data.get('reason', '').strip()
        if not reason:
            return Response({'error': 'A reason is required to acknowledge drift.'}, status=status.HTTP_400_BAD_REQUEST)
        event = self.get_object()
        event.status = 'resolved'
        event.acknowledged_by = request.user.username
        event.acknowledged_at = timezone.now()
        event.acknowledgement_reason = reason
        event.save()

        # Promote the collection result that triggered this drift event
        # as the new official baseline for the device.
        result = event.job_result
        if result and result.parsed_output is not None:
            from apps.baselines.models import Baseline
            # Use save() so auto_now=True on established_at fires correctly.
            try:
                b = Baseline.objects.get(device=event.device)
                b.parsed_data = result.parsed_output
                b.source_result = result
                b.established_by = request.user.username
                b.save()
            except Baseline.DoesNotExist:
                Baseline.objects.create(
                    device=event.device,
                    parsed_data=result.parsed_output,
                    source_result=result,
                    established_by=request.user.username,
                )

        _broadcast_drift(event)
        return Response(DriftEventSerializer(event).data)

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        event = self.get_object()
        event.status = 'resolved'
        event.save()
        _broadcast_drift(event)
        return Response(DriftEventSerializer(event).data)
