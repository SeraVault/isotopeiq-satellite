from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import DriftEventViewSet, volatile_fields

router = DefaultRouter()
router.register('', DriftEventViewSet, basename='drift-event')

urlpatterns = [
    path('volatile-fields/', volatile_fields),
] + router.urls
