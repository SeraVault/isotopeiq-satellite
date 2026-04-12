from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import JobViewSet, DeviceJobResultViewSet, UnifiedJobListView

router = DefaultRouter()
router.register('results', DeviceJobResultViewSet, basename='device-job-result')
router.register('', JobViewSet, basename='job')

urlpatterns = [
    path('unified/', UnifiedJobListView.as_view(), name='unified-jobs'),
] + router.urls
