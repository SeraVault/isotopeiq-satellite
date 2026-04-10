from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from core.permissions import IsAdminOrReadOnly
from .models import SystemSettings, PostCollectionAction
from .serializers import SystemSettingsSerializer, PostCollectionActionSerializer
from apps.retention.models import RetentionPolicy
from apps.retention.serializers import RetentionPolicySerializer

RETENTION_FIELDS = {'raw_data_days', 'parsed_data_days', 'job_history_days', 'log_days'}


def _merged_response(settings_instance):
    """Return a single dict with SystemSettings + RetentionPolicy fields."""
    data = SystemSettingsSerializer(settings_instance).data
    data.update(RetentionPolicySerializer(RetentionPolicy.get()).data)
    return data


class SystemSettingsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        return Response(_merged_response(SystemSettings.get()))

    def put(self, request):
        return self._save(request, partial=False)

    def patch(self, request):
        return self._save(request, partial=True)

    def _save(self, request, partial):
        # Split payload into settings vs. retention fields
        retention_data = {k: v for k, v in request.data.items() if k in RETENTION_FIELDS}
        settings_data  = {k: v for k, v in request.data.items() if k not in RETENTION_FIELDS}

        settings_instance = SystemSettings.get()
        s_ser = SystemSettingsSerializer(settings_instance, data=settings_data, partial=partial)
        s_ser.is_valid(raise_exception=True)
        s_ser.save()

        if retention_data:
            r_instance = RetentionPolicy.get()
            r_ser = RetentionPolicySerializer(r_instance, data=retention_data, partial=True)
            r_ser.is_valid(raise_exception=True)
            r_ser.save()

        return Response(_merged_response(settings_instance))


class PostCollectionActionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrReadOnly]
    serializer_class   = PostCollectionActionSerializer
    filterset_fields   = ['policy', 'trigger', 'destination', 'is_active']
    ordering_fields    = ['trigger', 'destination']

    def get_queryset(self):
        return PostCollectionAction.objects.select_related('policy').all()
