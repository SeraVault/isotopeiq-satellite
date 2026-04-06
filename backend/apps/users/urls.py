from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, me

router = DefaultRouter()
router.register('', UserViewSet, basename='users')

urlpatterns = [path('me/', me)] + router.urls
