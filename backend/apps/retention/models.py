from django.db import models
from django.core.exceptions import ValidationError


class RetentionPolicy(models.Model):
    """
    Singleton model — only one row should ever exist.
    Controls how long raw data, parsed data, job history, and logs are kept.
    Set any value to 0 to disable pruning for that category.
    """
    raw_data_days = models.PositiveIntegerField(
        default=90,
        help_text='Days to retain raw collection output. 0 = keep forever.',
    )
    parsed_data_days = models.PositiveIntegerField(
        default=365,
        help_text='Days to retain parsed canonical JSON. 0 = keep forever.',
    )
    job_history_days = models.PositiveIntegerField(
        default=180,
        help_text='Days to retain job records. 0 = keep forever.',
    )
    log_days = models.PositiveIntegerField(
        default=90,
        help_text='Days to retain job stdout/stderr logs. 0 = keep forever.',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Retention Policy'
        verbose_name_plural = 'Retention Policy'

    def clean(self):
        if not self.pk and RetentionPolicy.objects.exists():
            raise ValidationError('Only one RetentionPolicy record is allowed.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f'Retention: raw={self.raw_data_days}d  parsed={self.parsed_data_days}d  '
            f'jobs={self.job_history_days}d  logs={self.log_days}d'
        )

    @classmethod
    def get(cls) -> 'RetentionPolicy':
        """Return the singleton instance, creating it with defaults if absent."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
