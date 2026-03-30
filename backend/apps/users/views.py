from django.contrib.auth import get_user_model
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from .serializers import UserSerializer

User = get_user_model()


class UserViewSet(viewsets.ModelViewSet):
    """
    Admin-only CRUD for Django users.
    SSO users (LDAP/SAML) are visible and their flags are editable,
    but passwords cannot be set on them.
    """
    permission_classes = [IsAdminUser]
    queryset = User.objects.all().order_by('username')
    serializer_class = UserSerializer
    filterset_fields = ['is_active', 'is_staff']
    search_fields = ['username', 'first_name', 'last_name', 'email']

    @action(detail=True, methods=['post'], url_path='set-password')
    def set_password(self, request, pk=None):
        user = self.get_object()
        if not user.has_usable_password():
            return Response(
                {'detail': 'Cannot set a password on an SSO-managed user.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        password = request.data.get('password', '')
        if not password:
            return Response(
                {'detail': 'Password may not be blank.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.set_password(password)
        user.save()
        return Response({'detail': 'Password updated.'})
