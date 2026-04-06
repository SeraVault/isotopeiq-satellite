"""
Database-driven LDAP authentication backend.

Reads LDAP configuration from SystemSettings at authenticate() time so
settings can be toggled in the UI without restarting the server.

When ldap_enabled is False the backend returns None immediately, delegating
to the next backend in AUTHENTICATION_BACKENDS.
"""
import logging

logger = logging.getLogger(__name__)


class DatabaseLDAPBackend:
    """Authenticate against LDAP using settings stored in SystemSettings."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            from apps.notifications.models import SystemSettings
            cfg = SystemSettings.get()
        except Exception:
            return None

        if not cfg.ldap_enabled or not cfg.ldap_server_uri:
            return None

        try:
            import ldap as _ldap
            from django_auth_ldap.config import LDAPSearch, GroupOfNamesType
            from django_auth_ldap.backend import LDAPBackend
        except ImportError:
            logger.error('django-auth-ldap is not installed; LDAP authentication unavailable.')
            return None

        backend = LDAPBackend()

        # Build a fresh LDAPSettings object from DB values each call
        from django_auth_ldap import config as ldap_config
        import django.conf as django_conf

        # Temporarily patch Django settings with DB values for this call.
        # django-auth-ldap reads AUTH_LDAP_* from django.conf.settings.
        overrides = {
            'AUTH_LDAP_SERVER_URI':    cfg.ldap_server_uri,
            'AUTH_LDAP_BIND_DN':       cfg.ldap_bind_dn,
            'AUTH_LDAP_BIND_PASSWORD': cfg.ldap_bind_password,
            'AUTH_LDAP_START_TLS':     cfg.ldap_start_tls,
            'AUTH_LDAP_ALWAYS_UPDATE_USER': True,
            'AUTH_LDAP_FIND_GROUP_PERMS':   True,
            'AUTH_LDAP_CACHE_TIMEOUT': 0,  # no cache — settings may change
            'AUTH_LDAP_USER_ATTR_MAP': {
                'first_name': cfg.ldap_attr_first_name or 'givenName',
                'last_name':  cfg.ldap_attr_last_name  or 'sn',
                'email':      cfg.ldap_attr_email       or 'mail',
            },
        }

        if cfg.ldap_user_search_base:
            overrides['AUTH_LDAP_USER_SEARCH'] = LDAPSearch(
                cfg.ldap_user_search_base,
                _ldap.SCOPE_SUBTREE,
                cfg.ldap_user_search_filter or '(uid=%(user)s)',
            )

        if cfg.ldap_group_search_base:
            overrides['AUTH_LDAP_GROUP_SEARCH'] = LDAPSearch(
                cfg.ldap_group_search_base,
                _ldap.SCOPE_SUBTREE,
                '(objectClass=groupOfNames)',
            )
            overrides['AUTH_LDAP_GROUP_TYPE'] = GroupOfNamesType()

        flags_by_group = {}
        if cfg.ldap_superuser_group:
            flags_by_group['is_superuser'] = cfg.ldap_superuser_group
        if cfg.ldap_staff_group:
            flags_by_group['is_staff'] = cfg.ldap_staff_group
        if flags_by_group:
            overrides['AUTH_LDAP_USER_FLAGS_BY_GROUP'] = flags_by_group

        # Apply overrides, call authenticate, then restore
        original = {}
        settings = django_conf.settings
        for key, value in overrides.items():
            original[key] = getattr(settings, key, None)
            setattr(settings, key, value)

        # Clear the cached LDAPSettings so our new values are picked up
        if hasattr(backend, 'settings'):
            try:
                backend.settings = ldap_config.LDAPSettings(defaults=overrides)
            except Exception:
                pass

        try:
            return backend.authenticate(request, username=username, password=password)
        except Exception as exc:
            logger.warning('LDAP authentication error: %s', exc)
            return None
        finally:
            for key, value in original.items():
                if value is None:
                    try:
                        delattr(settings, key)
                    except AttributeError:
                        pass
                else:
                    setattr(settings, key, value)

    def get_user(self, user_id):
        try:
            from django.contrib.auth import get_user_model
            return get_user_model().objects.get(pk=user_id)
        except Exception:
            return None
