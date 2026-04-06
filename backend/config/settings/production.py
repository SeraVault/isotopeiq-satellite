from .base import *  # noqa: F401, F403
from decouple import config, Csv

DEBUG = False

# Nginx terminates TLS and forwards X-Forwarded-Proto — let Django trust it.
# SECURE_SSL_REDIRECT must be False here; nginx handles the HTTP→HTTPS redirect.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = False

SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

_cors_origins = [o for o in config('CORS_ALLOWED_ORIGINS', default='', cast=Csv()) if o]
if '*' in _cors_origins:
    CORS_ALLOW_ALL_ORIGINS = True
else:
    CORS_ALLOWED_ORIGINS = _cors_origins
