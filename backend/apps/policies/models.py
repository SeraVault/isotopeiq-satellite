from django.db import models


class Policy(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    devices = models.ManyToManyField('devices.Device', related_name='policies', blank=True)
    collection_script = models.ForeignKey(
        'scripts.Script',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='policies_as_collector',
        limit_choices_to={'script_type': 'collection'},
    )
    parser_script = models.ForeignKey(
        'scripts.Script',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='policies_as_parser',
        limit_choices_to={'script_type': 'parser'},
    )
    deployment_script = models.ForeignKey(
        'scripts.Script',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='policies_as_deployment',
        limit_choices_to={'script_type': 'deployment'},
        help_text='Optional deployment script run via the Deploy action.',
    )
    cron_schedule = models.CharField(
        max_length=100,
        default='0 2 * * *',
        help_text='Cron expression: minute hour dom month dow',
    )
    start_time = models.TimeField(
        null=True,
        blank=True,
        help_text='Optional fixed start time (UTC) overriding cron hour/minute.',
    )
    delay_between_devices = models.PositiveIntegerField(
        default=0,
        help_text='Seconds to wait between executing each device in this policy.',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'policies'

    def __str__(self):
        return self.name
