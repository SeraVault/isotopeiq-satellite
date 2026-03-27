from rest_framework.routers import DefaultRouter
from .views import ScriptViewSet
from .package_views import ScriptPackageViewSet

router = DefaultRouter()
router.register('packages', ScriptPackageViewSet, basename='script-package')
router.register('', ScriptViewSet, basename='script')

urlpatterns = router.urls
