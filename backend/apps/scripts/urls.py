from rest_framework.routers import DefaultRouter
from .views import ScriptViewSet
from .job_views import ScriptJobViewSet, ScriptJobResultViewSet

router = DefaultRouter()
router.register('script-jobs/results', ScriptJobResultViewSet, basename='script-job-result')
router.register('script-jobs', ScriptJobViewSet, basename='script-job')
router.register('', ScriptViewSet, basename='script')

urlpatterns = router.urls
