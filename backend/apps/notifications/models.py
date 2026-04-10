from django.db import models
from encrypted_model_fields.fields import EncryptedCharField


class SystemSettings(models.Model):
    """
    Singleton model for runtime-configurable system settings.
    Values here override the corresponding .env defaults at request time.
    """
    # Syslog
    syslog_host = models.CharField(max_length=253, default='localhost')
    syslog_port = models.PositiveIntegerField(default=514)
    syslog_facility = models.CharField(max_length=32, default='local0')
    syslog_enabled = models.BooleanField(default=False)

    # Email
    email_enabled = models.BooleanField(default=False)
    email_host = models.CharField(max_length=253, default='localhost')
    email_port = models.PositiveIntegerField(default=587)
    email_use_tls = models.BooleanField(default=True)
    email_username = models.CharField(max_length=255, blank=True)
    email_password = EncryptedCharField(max_length=1024, blank=True)
    email_from = models.CharField(
        max_length=255, blank=True,
        help_text='From address used in outbound email (e.g. isotopeiq@example.com)',
    )
    email_recipients = models.TextField(
        blank=True,
        help_text='Comma-separated list of recipient email addresses for notifications.',
    )

    # FTP / SFTP
    ftp_enabled = models.BooleanField(default=False)
    ftp_protocol = models.CharField(
        max_length=10,
        choices=[('ftp', 'FTP'), ('sftp', 'SFTP')],
        default='sftp',
    )
    ftp_host = models.CharField(max_length=253, default='localhost')
    ftp_port = models.PositiveIntegerField(default=22)
    ftp_username = models.CharField(max_length=255, blank=True)
    ftp_password = EncryptedCharField(max_length=1024, blank=True)
    ftp_remote_path = models.CharField(
        max_length=500, default='/',
        help_text='Remote directory path where baseline JSON files will be deposited.',
    )

    # General
    satellite_url = models.CharField(
        max_length=255,
        default='http://localhost:8000',
        help_text='Public base URL of this satellite (used in agent download links, etc.)',
    )
    agent_secret = EncryptedCharField(
        max_length=255,
        blank=True,
        help_text='Shared secret for agent authentication. Agents must supply this value in '
                  'the X-Agent-Secret request header. Leave blank to disable secret enforcement.',
    )

    # LDAP authentication (optional)
    ldap_enabled = models.BooleanField(default=False)
    ldap_server_uri = models.CharField(
        max_length=255, blank=True,
        help_text='LDAP server URI, e.g. ldap://ldap.example.com:389',
    )
    ldap_bind_dn = models.CharField(
        max_length=255, blank=True,
        help_text='DN of the account used to bind for searches',
    )
    ldap_bind_password = EncryptedCharField(max_length=1024, blank=True)
    ldap_start_tls = models.BooleanField(default=False)
    ldap_user_search_base = models.CharField(
        max_length=255, blank=True,
        help_text='Base DN for user searches, e.g. ou=users,dc=example,dc=com',
    )
    ldap_user_search_filter = models.CharField(
        max_length=255, blank=True, default='(uid=%(user)s)',
        help_text='LDAP filter for user lookup',
    )
    ldap_group_search_base = models.CharField(
        max_length=255, blank=True,
        help_text='Base DN for group searches (optional)',
    )
    ldap_attr_first_name = models.CharField(max_length=64, blank=True, default='givenName')
    ldap_attr_last_name  = models.CharField(max_length=64, blank=True, default='sn')
    ldap_attr_email      = models.CharField(max_length=64, blank=True, default='mail')
    ldap_superuser_group = models.CharField(
        max_length=255, blank=True,
        help_text='Full DN of the group whose members become Django superusers',
    )
    ldap_staff_group = models.CharField(
        max_length=255, blank=True,
        help_text='Full DN of the group whose members get Django staff access',
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'System Settings'
        verbose_name_plural = 'System Settings'

    def __str__(self):
        return f'SystemSettings (syslog={self.syslog_host}:{self.syslog_port})'

    @classmethod
    def get(cls) -> 'SystemSettings':
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class PostCollectionAction(models.Model):
    """
    Defines an automated action to fire when a policy run produces a result.

    trigger  — when the action fires (new baseline, drift, or every success)
    destination — where data/notification is sent (syslog, email, ftp/sftp)
    """
    TRIGGER_NEW_BASELINE  = 'new_baseline'
    TRIGGER_DRIFT         = 'drift_detected'
    TRIGGER_ALWAYS        = 'always'
    TRIGGER_CHOICES = [
        (TRIGGER_NEW_BASELINE, 'New Baseline Established'),
        (TRIGGER_DRIFT,        'Drift Detected'),
        (TRIGGER_ALWAYS,       'Always (every successful collection)'),
    ]

    DEST_SYSLOG = 'syslog'
    DEST_EMAIL  = 'email'
    DEST_FTP    = 'ftp'
    DEST_CHOICES = [
        (DEST_SYSLOG, 'Syslog'),
        (DEST_EMAIL,  'Email'),
        (DEST_FTP,    'FTP/SFTP'),
    ]

    policy = models.ForeignKey(
        'policies.Policy',
        on_delete=models.CASCADE,
        related_name='post_collection_actions',
    )
    trigger     = models.CharField(max_length=30, choices=TRIGGER_CHOICES)
    destination = models.CharField(max_length=20, choices=DEST_CHOICES)
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('policy', 'trigger', 'destination')]
        ordering = ['trigger', 'destination']

    def __str__(self):
        return f'Policy {self.policy_id}: {self.trigger} → {self.destination}'
