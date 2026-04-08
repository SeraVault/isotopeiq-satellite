from django.db import models


class Policy(models.Model):
    COLLECTION_METHOD_CHOICES = [
        ('agent',  'Agent Pull'),
        ('script', 'Script Execution'),
    ]

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    collection_method = models.CharField(
        max_length=10,
        choices=COLLECTION_METHOD_CHOICES,
        default='script',
        help_text='How collection is performed: poll agent HTTP endpoint or run a script via SSH/WinRM/Telnet.',
    )
    devices = models.ManyToManyField('devices.Device', related_name='policies', blank=True)
    script_job = models.ForeignKey(
        'scripts.ScriptJob',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='policies',
        help_text='Script Job containing the collection and parser scripts to run. Required for Script Execution policies.',
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
