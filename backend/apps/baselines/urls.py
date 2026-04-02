from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import BaselineViewSet

router = DefaultRouter()
router.register('', BaselineViewSet, basename='baseline')

# Register /import/ before router URLs so Django doesn't match it as a {pk}
urlpatterns = [
    path(
        'import/',
        BaselineViewSet.as_view({'post': 'import_baseline'}),
        name='baseline-import',
    ),
] + router.urls
