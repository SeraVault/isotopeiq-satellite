"""
Role-based permission classes (SRD §17.1).

Two roles are defined:

  Admin   — Django staff/superuser.  Full read+write access to all resources.
  Analyst — Any authenticated non-staff user.  Read-only access plus the
            ability to acknowledge and resolve drift events.

Usage in views:
    permission_classes = [IsAdminOrReadOnly]
    permission_classes = [IsAdminUser]   # admin-only (Django built-in)
"""
from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdminOrReadOnly(BasePermission):
    """
    Analysts (authenticated, non-staff) may use safe HTTP methods only.
    Admins (staff) have unrestricted access.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_staff


class IsAdminOrDriftAction(BasePermission):
    """
    Analysts may read drift events and call the acknowledge/resolve actions.
    All other write operations require Admin.
    """
    _ANALYST_ACTIONS = {'acknowledge', 'resolve'}

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        if getattr(view, 'action', None) in self._ANALYST_ACTIONS:
            return True
        return request.user.is_staff
