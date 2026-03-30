from django.db import models


class SystemSettings(models.Model):
    """
    Singleton model for runtime-configurable system settings.
    Values here override the corresponding .env defaults at request time.
    """
    # Syslog
    syslog_host = models.CharField(max_length=253, default='localhost')
    syslog_port = models.PositiveIntegerField(default=514)
    syslog_facility = models.CharField(max_length=32, default='local0')
    syslog_enabled = models.BooleanField(default=False)

    # General
    satellite_url = models.CharField(
        max_length=255,
        default='http://localhost:8000',
        help_text='Public base URL of this satellite (used in agent download links, etc.)',
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'System Settings'
        verbose_name_plural = 'System Settings'

    def __str__(self):
        return f'SystemSettings (syslog={self.syslog_host}:{self.syslog_port})'

    @classmethod
    def get(cls) -> 'SystemSettings':
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
