from django.db import models


class AuditLog(models.Model):
    """Immutable record of a user action on a resource (SRD §17.3)."""

    ACTION_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('action', 'Action'),   # custom DRF @action (run, deploy, cancel, …)
        ('login',  'Login'),
        ('logout', 'Logout'),
    ]

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    username = models.CharField(max_length=255, blank=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    # e.g. "devices.Device", "policies.Policy"
    resource_type = models.CharField(max_length=100, blank=True)
    resource_id = models.CharField(max_length=64, blank=True)
    resource_name = models.CharField(max_length=255, blank=True)
    detail = models.TextField(blank=True)
    # HTTP metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    method = models.CharField(max_length=10, blank=True)
    path = models.CharField(max_length=500, blank=True)
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return (
            f'{self.timestamp:%Y-%m-%d %H:%M:%S} '
            f'{self.username} {self.action} {self.resource_type}/{self.resource_id}'
        )
