from rest_framework import viewsets
from core.permissions import IsAdminOrReadOnly
from .models import Script
from .serializers import ScriptSerializer


class ScriptViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrReadOnly]
    queryset = Script.objects.all()
    serializer_class = ScriptSerializer
    search_fields = ['name', 'description']
    filterset_fields = ['script_type', 'target_os', 'is_active']
    ordering_fields = ['name', 'created_at']
