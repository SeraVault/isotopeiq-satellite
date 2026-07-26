from django.db import models


class Job(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('success', 'Success'),
        ('partial', 'Partial'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    # The device this job ran against.  Nullable only to preserve existing rows
    # created before this field was added; all new jobs set this explicitly.
    device = models.ForeignKey(
        'devices.Device',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='jobs',
    )
    # Policy that triggered this job (null for ad-hoc / push jobs).
    policy = models.ForeignKey(
        'policies.Policy',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='jobs',
    )
    triggered_by = models.CharField(max_length=50, default='scheduler')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    celery_task_id = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            # List views order by this by default (see Meta.ordering) and
            # most API list filters narrow by it too.
            models.Index(fields=['-created_at']),
            # reap_stale_jobs filters status='running' AND started_at__lt=...
            # every 5 minutes — this is the exact shape of that query.
            models.Index(fields=['status', 'started_at']),
        ]

    def __str__(self):
        return f'Job {self.pk} ({self.status})'


class DeviceJobResult(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='device_results')
    device = models.ForeignKey('devices.Device', on_delete=models.CASCADE, related_name='job_results')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    raw_output = models.TextField(blank=True)
    parsed_output = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-job__created_at']
        indexes = [
            # reap_stale_jobs filters status='running' AND started_at__lt=...
            # every 5 minutes — this is the exact shape of that query.
            models.Index(fields=['status', 'started_at']),
            # retention/tasks.py filters on started_at alone for the
            # raw_output/parsed_output/error_message clearing passes.
            models.Index(fields=['started_at']),
        ]

    def __str__(self):
        return f'Result for {self.device} in Job {self.job_id}'
