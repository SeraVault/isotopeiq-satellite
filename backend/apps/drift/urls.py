from rest_framework.routers import DefaultRouter
from .views import DriftEventViewSet

router = DefaultRouter()
router.register('', DriftEventViewSet, basename='drift-event')

urlpatterns = router.urls
