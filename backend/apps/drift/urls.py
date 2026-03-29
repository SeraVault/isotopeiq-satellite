from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import DriftEventViewSet, VolatileFieldRuleViewSet, volatile_fields

router = DefaultRouter()
router.register('volatile-rules', VolatileFieldRuleViewSet, basename='volatile-rule')
router.register('', DriftEventViewSet, basename='drift-event')

urlpatterns = [
    path('volatile-fields/', volatile_fields),
] + router.urls
