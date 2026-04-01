from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from core.permissions import IsAdminOrReadOnly
from .models import SystemSettings, PostCollectionAction
from .serializers import SystemSettingsSerializer, PostCollectionActionSerializer


class SystemSettingsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        return Response(SystemSettingsSerializer(SystemSettings.get()).data)

    def put(self, request):
        instance = SystemSettings.get()
        serializer = SystemSettingsSerializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(SystemSettingsSerializer(instance).data)

    def patch(self, request):
        instance = SystemSettings.get()
        serializer = SystemSettingsSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(SystemSettingsSerializer(instance).data)


class PostCollectionActionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrReadOnly]
    serializer_class   = PostCollectionActionSerializer
    filterset_fields   = ['policy', 'trigger', 'destination', 'is_active']
    ordering_fields    = ['trigger', 'destination']

    def get_queryset(self):
        return PostCollectionAction.objects.select_related('policy').all()
