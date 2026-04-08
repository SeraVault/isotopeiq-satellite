from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from core.permissions import IsAdminOrReadOnly
from .models import Policy
from .serializers import PolicySerializer


class PolicyViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrReadOnly]
    queryset = Policy.objects.prefetch_related('devices', 'script_job__steps__script').all()
    serializer_class = PolicySerializer
    search_fields = ['name', 'description']
    filterset_fields = ['is_active', 'devices']
    ordering_fields = ['name', 'created_at']

    @action(detail=True, methods=['post'])
    def run(self, request, pk=None):
        policy = self.get_object()
        from apps.jobs.tasks import run_policy
        task = run_policy.delay(policy.id, triggered_by='manual')
        return Response({'task_id': task.id}, status=status.HTTP_202_ACCEPTED)
