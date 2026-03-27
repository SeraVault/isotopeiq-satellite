from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from .models import RetentionPolicy
from .serializers import RetentionPolicySerializer


class RetentionPolicyView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        return Response(RetentionPolicySerializer(RetentionPolicy.get()).data)

    def put(self, request):
        instance = RetentionPolicy.get()
        serializer = RetentionPolicySerializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def patch(self, request):
        instance = RetentionPolicy.get()
        serializer = RetentionPolicySerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
