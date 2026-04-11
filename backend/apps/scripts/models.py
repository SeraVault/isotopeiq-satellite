from django.db import models


class Script(models.Model):
    SCRIPT_TYPE_CHOICES = [
        ('collection', 'Collection'),
        ('parser', 'Parser'),
        ('deployment', 'Deployment'),
        ('utility', 'Utility'),
    ]
    RUN_ON_CHOICES = [
        ('client', 'Client (remote device)'),
        ('server', 'Server (satellite)'),
        ('both', 'Both'),
    ]

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    script_type = models.CharField(max_length=20, choices=SCRIPT_TYPE_CHOICES)
    run_on = models.CharField(max_length=10, choices=RUN_ON_CHOICES, default='client')
    language = models.CharField(max_length=30, default='shell')
    content = models.TextField()
    version = models.CharField(max_length=50, default='1.0.0')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.script_type})'


# Import here so re-exports from apps.scripts.models work.
from apps.scripts.job_models import ScriptJob, ScriptJobStep, ScriptJobResult  # noqa: E402, F401
