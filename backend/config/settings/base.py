from pathlib import Path
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config('SECRET_KEY')

SATELLITE_URL = config('SATELLITE_URL', default='http://localhost:8000')

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'django_celery_beat',
    'django_celery_results',
    'django_filters',
    'import_export',
    # Authentication (conditionally added below when configured)

    # Local
    'apps.devices',
    'apps.scripts',
    'apps.policies',
    'apps.jobs',
    'apps.baselines',
    'apps.drift',
    'apps.notifications',
    'apps.users',
    'apps.retention',
    'apps.audit',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'apps.audit.middleware.AuditMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', default='isotopeiq'),
        'USER': config('DB_USER', default='isotopeiq'),
        'PASSWORD': config('DB_PASSWORD', default=''),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Redis
REDIS_URL = config('REDIS_URL', default='redis://localhost:6379/0')

# Celery
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = 'django-db'
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
# Use a project-specific queue so tasks from other projects sharing the same
# Redis instance are not accidentally consumed or discarded.
CELERY_TASK_DEFAULT_QUEUE = 'isotopeiq_satellite_2'
# Hard kill a task after 10 minutes; soft warning at 9 minutes.
# This is a safety net — individual collectors already have per-operation
# timeouts, but a hung TCP socket can still block recv_exit_status() forever
# without this guard.
CELERY_TASK_TIME_LIMIT = 600        # seconds — SIGKILL
CELERY_TASK_SOFT_TIME_LIMIT = 540   # seconds — SoftTimeLimitExceeded

# Static beat schedule — retention pruning runs daily at 03:00 UTC.
# Policy-driven schedules are registered dynamically via django_celery_beat.
from celery.schedules import crontab
CELERY_BEAT_SCHEDULE = {
    'prune-old-data-daily': {
        'task': 'apps.retention.tasks.prune_old_data',
        'schedule': crontab(hour=3, minute=0),
    },
}

# JWT token lifetimes — long enough to survive a working session without
# constant expiry-induced 401 storms on the 3-second dashboard poll.
from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME':  timedelta(hours=8),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS':  False,
    'UPDATE_LAST_LOGIN':      True,
}

# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'config.pagination.PageNumberPagination',
    'PAGE_SIZE': 25,
}

# Encryption key for sensitive Device fields.
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
FIELD_ENCRYPTION_KEY = config('FIELD_ENCRYPTION_KEY', default='')

# Syslog notifications
SYSLOG_HOST = config('SYSLOG_HOST', default='localhost')
SYSLOG_PORT = config('SYSLOG_PORT', default=514, cast=int)
SYSLOG_FACILITY = config('SYSLOG_FACILITY', default='local0')

# ── Authentication Backends ───────────────────────────────────────────────────
# Always include the local Django DB backend.
# The database-driven LDAP backend is always registered; it checks the
# SystemSettings.ldap_enabled flag at runtime so no restart is needed.
AUTHENTICATION_BACKENDS = [
    'core.auth.ldap.DatabaseLDAPBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# django-auth-ldap must be installed for DatabaseLDAPBackend to work.
# It is always added to INSTALLED_APPS since it's in requirements.txt.
INSTALLED_APPS += ['django_auth_ldap']

# ── SAML 2.0 (optional) ───────────────────────────────────────────────────────
_SAML_IDP_METADATA_URL = config('SAML_IDP_METADATA_URL', default='')
_SAML_IDP_METADATA_FILE = config('SAML_IDP_METADATA_FILE', default='')
if _SAML_IDP_METADATA_URL or _SAML_IDP_METADATA_FILE:
    import saml2
    import saml2.saml

    INSTALLED_APPS += ['djangosaml2']
    AUTHENTICATION_BACKENDS.insert(0, 'djangosaml2.backends.Saml2Backend')

    SAML_CONFIG = {
        'xmlsec_binary': '/usr/bin/xmlsec1',
        'entityid': config('SAML_SP_ENTITY_ID', default='http://localhost:8000/saml2/metadata/'),
        'attribute_map_dir': str(BASE_DIR / 'saml' / 'attribute-maps'),
        'service': {
            'sp': {
                'name': 'IsotopeIQ Satellite',
                'name_id_format': saml2.saml.NAMEID_FORMAT_EMAILADDRESS,
                'endpoints': {
                    'assertion_consumer_service': [
                        (
                            config('SAML_ACS_URL', default='http://localhost:8000/saml2/acs/'),
                            saml2.BINDING_HTTP_POST,
                        ),
                    ],
                    'single_logout_service': [
                        (
                            config('SAML_SLS_URL', default='http://localhost:8000/saml2/ls/'),
                            saml2.BINDING_HTTP_REDIRECT,
                        ),
                    ],
                },
                'required_attributes': ['uid'],
                'optional_attributes': ['mail', 'givenName', 'sn'],
                'authn_requests_signed': False,
                'want_assertions_signed': True,
            },
        },
        'metadata': {
            'remote': [{'url': _SAML_IDP_METADATA_URL}] if _SAML_IDP_METADATA_URL else [],
            'local': [_SAML_IDP_METADATA_FILE] if _SAML_IDP_METADATA_FILE else [],
        },
        'debug': False,
        'key_file': config('SAML_SP_KEY_FILE', default=''),
        'cert_file': config('SAML_SP_CERT_FILE', default=''),
        'encryption_keypairs': [],
    }
    SAML_CREATE_UNKNOWN_USER = True
    SAML_ATTRIBUTE_MAPPING = {
        'uid': ('username',),
        'mail': ('email',),
        'givenName': ('first_name',),
        'sn': ('last_name',),
    }
