from rest_framework.routers import DefaultRouter
from .views import CredentialViewSet, DeviceViewSet

router = DefaultRouter()
router.register('credentials', CredentialViewSet, basename='credential')
router.register('', DeviceViewSet, basename='device')

urlpatterns = router.urls
