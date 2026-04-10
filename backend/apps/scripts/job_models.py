from django.db import models


class ScriptJob(models.Model):
    """
    A reusable script execution definition consisting of an ordered pipeline of
    ScriptJobSteps.  Each step's execution location (device or Satellite) is
    determined by the script's own run_on field — not set per-step.
    """

    JOB_TYPE_CHOICES = [
        ('baseline_collection', 'Baseline Collection'),
        ('compliance_audit',    'Compliance Audit'),
        ('remediation',         'Remediation'),
        ('discovery',           'Discovery'),
        ('data_export',         'Data Export'),
        ('maintenance',         'Maintenance'),
        ('notification',        'Notification'),
        ('custom',              'Custom'),
    ]

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    job_type = models.CharField(
        max_length=64,
        choices=JOB_TYPE_CHOICES,
        default='custom',
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class ScriptJobStep(models.Model):
    """
    A single step in a ScriptJob pipeline.

    Steps run in ascending `order`.  Execution location (device or Satellite)
    is inherited from the script's run_on field.  Each step can:
      - receive the previous step's output as context (`pipe_to_next` on previous)
      - persist its raw output (`save_output`)
      - produce canonical JSON and save it as a device baseline (`enable_baseline`)
      - compare canonical JSON against the existing baseline (`enable_drift`)
    """

    script_job = models.ForeignKey(
        ScriptJob,
        on_delete=models.CASCADE,
        related_name='steps',
    )
    order = models.PositiveIntegerField(default=0)
    script = models.ForeignKey(
        'scripts.Script',
        on_delete=models.PROTECT,
        related_name='job_steps',
    )
    pipe_to_next = models.BooleanField(
        default=True,
        help_text="Pass this step's output to the next step as input.",
    )
    save_output = models.BooleanField(
        default=False,
        help_text='Persist the raw output of this step in the job result.',
    )
    enable_baseline = models.BooleanField(
        default=False,
        help_text="Save this step's output as the device baseline (output must be canonical JSON).",
    )
    enable_drift = models.BooleanField(
        default=False,
        help_text="Compare this step's output against the existing baseline and create DriftEvents.",
    )

    class Meta:
        ordering = ['script_job', 'order']
        unique_together = [['script_job', 'order']]

    def __str__(self):
        return f'{self.script_job} / step {self.order} ({self.script})'


class ScriptJobResult(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ]

    script_job = models.ForeignKey(
        ScriptJob,
        on_delete=models.CASCADE,
        related_name='results',
    )
    # Null when the job has no devices (server-side only).
    device = models.ForeignKey(
        'devices.Device',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='script_job_results',
    )
    triggered_by = models.CharField(max_length=50, default='manual')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Per-step outputs: [{order, script, run_on, output}]
    step_outputs = models.JSONField(null=True, blank=True)
    # Convenience fields populated from the pipeline (kept for backwards compat).
    # raw_output  = first client step output (or save_output step output)
    # parsed_output = canonical JSON from the last enable_baseline/enable_drift step
    client_output = models.TextField(blank=True)
    server_output = models.TextField(blank=True)
    parsed_output = models.JSONField(null=True, blank=True)

    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    celery_task_id = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        device_str = str(self.device) if self.device else 'server'
        return f'ScriptJobResult {self.pk} ({self.script_job} / {device_str})'
