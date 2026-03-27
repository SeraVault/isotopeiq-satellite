from django.apps import AppConfig


class PoliciesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.policies'

    def ready(self):
        import apps.policies.signals  # noqa: F401
