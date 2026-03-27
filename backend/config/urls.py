from django.apps import apps
from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/devices/', include('apps.devices.urls')),
    path('api/scripts/', include('apps.scripts.urls')),
    path('api/policies/', include('apps.policies.urls')),
    path('api/jobs/', include('apps.jobs.urls')),
    path('api/baselines/', include('apps.baselines.urls')),
    path('api/drift/', include('apps.drift.urls')),
    path('api/push/', include('apps.jobs.push_urls')),
    path('api/retention/', include('apps.retention.urls')),
    path('api/audit/', include('apps.audit.urls')),
]

# SAML 2.0 URLs — only registered when djangosaml2 is in INSTALLED_APPS
if apps.is_installed('djangosaml2'):
    urlpatterns += [path('saml2/', include('djangosaml2.urls'))]
