from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import CredentialViewSet, DeviceViewSet, EnrollView

router = DefaultRouter()
router.register('credentials', CredentialViewSet, basename='credential')
router.register('', DeviceViewSet, basename='device')

urlpatterns = router.urls + [
    path('enroll/', EnrollView.as_view(), name='device-enroll'),
]
