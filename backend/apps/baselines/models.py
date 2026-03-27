from django.db import models


class Baseline(models.Model):
    device = models.OneToOneField(
        'devices.Device',
        on_delete=models.CASCADE,
        related_name='baseline',
    )
    parsed_data = models.JSONField()
    source_result = models.ForeignKey(
        'jobs.DeviceJobResult',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='baseline_source',
    )
    established_at = models.DateTimeField(auto_now=True)
    established_by = models.CharField(max_length=255, default='system')

    class Meta:
        ordering = ['device__name']

    def __str__(self):
        return f'Baseline for {self.device}'
