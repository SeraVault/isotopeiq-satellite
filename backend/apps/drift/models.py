from django.db import models


class DriftEvent(models.Model):
    STATUS_CHOICES = [
        ('new', 'New'),
        ('acknowledged', 'Acknowledged'),
        ('resolved', 'Resolved'),
    ]

    device = models.ForeignKey(
        'devices.Device',
        on_delete=models.CASCADE,
        related_name='drift_events',
    )
    job_result = models.ForeignKey(
        'jobs.DeviceJobResult',
        on_delete=models.CASCADE,
        related_name='drift_events',
    )
    diff = models.JSONField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    acknowledged_by = models.CharField(max_length=255, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Drift on {self.device} at {self.created_at}'
