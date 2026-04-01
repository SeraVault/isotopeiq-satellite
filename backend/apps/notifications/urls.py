from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import SystemSettingsView, PostCollectionActionViewSet

router = DefaultRouter()
router.register('actions', PostCollectionActionViewSet, basename='postcollectionaction')

urlpatterns = [
    path('', SystemSettingsView.as_view(), name='system-settings'),
] + router.urls
