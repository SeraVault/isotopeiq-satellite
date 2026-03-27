from django.db import models


class ScriptPackage(models.Model):
    """
    A named pair of collection + parser scripts that belong together.

    Packages are the primary authoring unit: you write the collector and
    the parser side-by-side, test them against a real device, then assign
    the package to a policy.  Individual Script records continue to exist
    and can still be mixed freely in policies.
    """
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    collection_script = models.OneToOneField(
        'scripts.Script',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='package_as_collector',
        limit_choices_to={'script_type': 'collection'},
    )
    parser_script = models.OneToOneField(
        'scripts.Script',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='package_as_parser',
        limit_choices_to={'script_type': 'parser'},
    )
    target_os = models.CharField(
        max_length=20,
        choices=[
            ('linux', 'Linux'),
            ('windows', 'Windows'),
            ('macos', 'macOS'),
            ('any', 'Any'),
        ],
        default='any',
    )
    version = models.CharField(max_length=50, default='1.0.0')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name
