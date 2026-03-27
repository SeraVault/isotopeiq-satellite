from django.db import models


class Script(models.Model):
    SCRIPT_TYPE_CHOICES = [
        ('collection', 'Collection'),
        ('parser', 'Parser'),
        ('deployment', 'Deployment'),
    ]
    TARGET_OS_CHOICES = [
        ('linux', 'Linux'),
        ('windows', 'Windows'),
        ('macos', 'macOS'),
        ('any', 'Any'),
    ]

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    script_type = models.CharField(max_length=20, choices=SCRIPT_TYPE_CHOICES)
    target_os = models.CharField(max_length=20, choices=TARGET_OS_CHOICES, default='any')
    content = models.TextField()
    version = models.CharField(max_length=50, default='1.0.0')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.script_type})'


# Import here so `from apps.scripts.models import ScriptPackage` works.
from apps.scripts.package_models import ScriptPackage  # noqa: E402, F401
