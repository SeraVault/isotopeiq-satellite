from rest_framework.routers import DefaultRouter
from .views import BaselineViewSet

router = DefaultRouter()
router.register('', BaselineViewSet, basename='baseline')

urlpatterns = router.urls
