from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated
import django_filters

from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogFilter(django_filters.FilterSet):
    timestamp_after  = django_filters.IsoDateTimeFilter(field_name='timestamp', lookup_expr='gte')
    timestamp_before = django_filters.IsoDateTimeFilter(field_name='timestamp', lookup_expr='lte')

    class Meta:
        model = AuditLog
        fields = ['username', 'action', 'resource_type', 'resource_id', 'status_code']


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only audit log — any authenticated user can view."""
    permission_classes = [IsAuthenticated]
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    filterset_class = AuditLogFilter
    filter_backends = [
        django_filters.rest_framework.DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    search_fields = ['username', 'path', 'resource_type']
    ordering_fields = ['timestamp']
    ordering = ['-timestamp']
