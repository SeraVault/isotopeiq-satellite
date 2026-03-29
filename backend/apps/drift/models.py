from django.db import models


class VolatileFieldRule(models.Model):
    """
    A single rule that tells the drift detector to ignore a field (or item)
    when comparing canonical snapshots.  Stored in the database so operators
    can tune drift sensitivity without a deployment.

    spec_type determines how field_name / aux are interpreted:

    section_field
        Drop `field_name` from the top-level section dict.
        Example: section=os, field_name=ntp_synced

    item_field
        Drop `field_name` from every item in the section array.
        Example: section=filesystem, field_name=free_gb

    nested_field
        Drop `field_name` from every item in the nested array named `aux`.
        Example: section=routing_protocols, aux=neighbors, field_name=state

    exclude_key
        Remove an entire item from the section array when item[aux] == field_name.
        `aux` defaults to 'key' (i.e. sysctl key names).
        Example: section=sysctl, aux=key, field_name=fs.dentry-state
    """
    SPEC_SECTION_FIELD = 'section_field'
    SPEC_ITEM_FIELD      = 'item_field'
    SPEC_NESTED_FIELD    = 'nested_field'
    SPEC_EXCLUDE_KEY     = 'exclude_key'
    SPEC_EXCLUDE_SECTION = 'exclude_section'
    SPEC_CHOICES = [
        (SPEC_SECTION_FIELD,   'Section field — drop from section dict'),
        (SPEC_ITEM_FIELD,      'Item field — drop from each array item'),
        (SPEC_NESTED_FIELD,    'Nested field — drop from nested array items'),
        (SPEC_EXCLUDE_KEY,     'Exclude item by key value'),
        (SPEC_EXCLUDE_SECTION, 'Exclude section — omit entire section from comparison'),
    ]

    section     = models.CharField(max_length=100)
    spec_type   = models.CharField(max_length=30, choices=SPEC_CHOICES)
    # field_name: the field to suppress, OR the value to match for exclude_key
    field_name  = models.CharField(max_length=200)
    # aux usage:
    #   nested_field → name of the nested array (e.g. 'neighbors', 'ports')
    #   exclude_key  → subfield to match on (e.g. 'key'); defaults to 'key'
    aux         = models.CharField(max_length=100, blank=True, default='')
    description = models.TextField(blank=True)
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('section', 'spec_type', 'field_name', 'aux')]
        ordering = ['section', 'spec_type', 'field_name']

    def __str__(self):
        return f'{self.section} / {self.spec_type} / {self.field_name}'


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
    baseline_snapshot = models.JSONField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    acknowledged_by = models.CharField(max_length=255, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledgement_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Drift on {self.device} at {self.created_at}'
