import hashlib
import mimetypes
import os
from pathlib import Path

from django.apps import apps
from django.contrib import admin
from django.http import FileResponse, Http404, JsonResponse
from django.urls import path, include
from django.views.decorators.http import require_GET
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

_AGENTS_DIR = Path(os.environ.get('AGENTS_DIR', '/agents'))


@require_GET
def agents_list(request):
    """Return a list of available agent files."""
    try:
        files = sorted(f.name for f in _AGENTS_DIR.iterdir() if f.is_file())
    except OSError:
        files = []
    return JsonResponse({'agents': files})


@require_GET
def agents_download(request, filename):
    """Serve a single file from the agents directory."""
    # Prevent path traversal
    safe = Path(filename).name
    path = _AGENTS_DIR / safe
    if not path.is_file():
        raise Http404
    mime, _ = mimetypes.guess_type(str(path))
    response = FileResponse(open(path, 'rb'), content_type=mime or 'application/octet-stream')
    response['Content-Disposition'] = 'attachment; filename="{}"'.format(safe)
    return response


@require_GET
def agents_info(request, filename):
    """Return SHA-256 and size for an agent file so clients can detect updates."""
    safe = Path(filename).name
    fpath = _AGENTS_DIR / safe
    if not fpath.is_file():
        raise Http404
    h = hashlib.sha256()
    with open(fpath, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    # Optional: read a companion .version file if the admin placed one alongside
    version = None
    version_file = _AGENTS_DIR / (safe + '.version')
    if version_file.is_file():
        version = version_file.read_text(encoding='utf-8').strip()
    return JsonResponse({
        'filename': safe,
        'size':     fpath.stat().st_size,
        'sha256':   h.hexdigest(),
        'version':  version,
    })


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
    path('api/settings/', include('apps.notifications.urls')),
    path('api/users/', include('apps.users.urls')),
    path('api/audit/', include('apps.audit.urls')),
    path('api/agents/', agents_list, name='agents-list'),
    path('api/agents/<str:filename>/info', agents_info, name='agents-info'),
    path('api/agents/<str:filename>', agents_download, name='agents-download'),
]

# SAML 2.0 URLs — only registered when djangosaml2 is in INSTALLED_APPS
if apps.is_installed('djangosaml2'):
    urlpatterns += [path('saml2/', include('djangosaml2.urls'))]
