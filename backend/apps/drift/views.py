from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone

from core.permissions import IsAdminOrDriftAction
from .models import DriftEvent
from .serializers import DriftEventSerializer


class DriftEventViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAdminOrDriftAction]
    queryset = DriftEvent.objects.select_related('device', 'job_result').all()
    serializer_class = DriftEventSerializer
    filterset_fields = ['device', 'status']
    ordering_fields = ['created_at']

    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        event = self.get_object()
        event.status = 'acknowledged'
        event.acknowledged_by = request.user.username
        event.acknowledged_at = timezone.now()
        event.save()
        return Response(DriftEventSerializer(event).data)

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        event = self.get_object()
        event.status = 'resolved'
        event.save()
        return Response(DriftEventSerializer(event).data)
