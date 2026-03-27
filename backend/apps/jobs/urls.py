from rest_framework.routers import DefaultRouter
from .views import JobViewSet, DeviceJobResultViewSet

router = DefaultRouter()
router.register('results', DeviceJobResultViewSet, basename='device-job-result')
router.register('', JobViewSet, basename='job')

urlpatterns = router.urls
