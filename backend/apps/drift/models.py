from django.db import models


class VolatileFieldRule(models.Model):
    """
    A single rule telling the drift detector to ignore a field or item.

    script_job — when set, the rule applies only to drift comparisons
    triggered by that ScriptJob.  Null means global (all jobs).

    spec_type determines how field_name / aux are interpreted:

    section_field  — drop field_name from the top-level section dict
    item_field     — drop field_name from every item in the section array
    nested_field   — drop field_name from every item in nested array `aux`
    exclude_key    — remove array item where item[aux] == field_name
    exclude_section — omit the entire section from comparison
    key_prefix     — remove array items whose key starts with field_name
    """

    SPEC_SECTION_FIELD = 'section_field'
    SPEC_ITEM_FIELD = 'item_field'
    SPEC_NESTED_FIELD = 'nested_field'
    SPEC_EXCLUDE_KEY = 'exclude_key'
    SPEC_EXCLUDE_SECTION = 'exclude_section'
    SPEC_KEY_PREFIX = 'key_prefix'
    SPEC_CHOICES = [
        (SPEC_SECTION_FIELD, 'Section field — drop from section dict'),
        (SPEC_ITEM_FIELD, 'Item field — drop from each array item'),
        (SPEC_NESTED_FIELD, 'Nested field — drop from nested array items'),
        (SPEC_EXCLUDE_KEY, 'Exclude item by key value'),
        (SPEC_EXCLUDE_SECTION, 'Exclude section — omit entire section'),
        (SPEC_KEY_PREFIX, 'Exclude items whose key starts with prefix'),
    ]

    # When non-null this rule is scoped to the given ScriptJob; null = global.
    script_job = models.ForeignKey(
        'scripts.ScriptJob',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='volatile_rules',
    )
    section = models.CharField(max_length=100)
    spec_type = models.CharField(max_length=30, choices=SPEC_CHOICES)
    # field to suppress, or key value matched by exclude_key / key_prefix
    field_name = models.CharField(max_length=200)
    # aux: nested array name (nested_field) or match subfield (exclude_key)
    aux = models.CharField(max_length=100, blank=True, default='')
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [
            ('script_job', 'section', 'spec_type', 'field_name', 'aux'),
        ]
        ordering = ['section', 'spec_type', 'field_name']

    def __str__(self):
        scope = f'{self.script_job} / ' if self.script_job_id else 'global / '
        return f'{scope}{self.section} / {self.spec_type} / {self.field_name}'


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
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='drift_events',
    )
    diff = models.JSONField()
    baseline_snapshot = models.JSONField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    acknowledged_by = models.CharField(max_length=255, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledgement_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            # The dedup/auto-resolve lookups in jobs/tasks.py and
            # scripts/tasks.py always filter on (device, status) together.
            models.Index(fields=['device', 'status']),
            # List views order by this by default (see Meta.ordering).
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f'Drift on {self.device} at {self.created_at}'
