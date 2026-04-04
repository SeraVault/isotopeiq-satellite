from django.db import models
from encrypted_model_fields.fields import EncryptedCharField


class Credential(models.Model):
    CREDENTIAL_TYPE_CHOICES = [
        ('password', 'Username / Password'),
        ('private_key', 'Username / Private Key'),
        ('api_token', 'API Token'),
    ]

    name = models.CharField(max_length=255, unique=True)
    credential_type = models.CharField(max_length=20, choices=CREDENTIAL_TYPE_CHOICES)
    username = models.CharField(max_length=255, blank=True)
    password = EncryptedCharField(max_length=1024, blank=True)
    private_key = EncryptedCharField(max_length=4096, blank=True)
    token = EncryptedCharField(max_length=1024, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.credential_type})'


class Device(models.Model):
    DEVICE_TYPE_CHOICES = [
        ('linux', 'Linux'),
        ('windows', 'Windows'),
        ('macos', 'macOS'),
        ('network', 'Network Device'),
        ('other', 'Other'),
    ]
    CONNECTION_TYPE_CHOICES = [
        ('ssh', 'SSH'),
        ('telnet', 'Telnet'),
        ('winrm', 'WinRM'),
        ('https', 'HTTPS/API'),
        ('agent', 'Agent Pull (port 9322)'),
    ]
    OS_TYPE_CHOICES = [
        ('linux', 'Linux'),
        ('windows', 'Windows'),
        ('macos', 'macOS'),
        ('ios', 'Cisco IOS'),
        ('junos', 'Juniper JunOS'),
        ('other', 'Other'),
    ]

    name = models.CharField(max_length=255, unique=True)
    hostname = models.CharField(max_length=255)
    fqdn = models.CharField(max_length=255, blank=True)
    port = models.PositiveIntegerField(default=22)
    device_type = models.CharField(max_length=50, choices=DEVICE_TYPE_CHOICES, default='linux')
    os_type = models.CharField(max_length=50, choices=OS_TYPE_CHOICES, default='linux')
    connection_type = models.CharField(max_length=20, choices=CONNECTION_TYPE_CHOICES, default='ssh')
    tags = models.JSONField(default=list, blank=True)

    # Preferred: link to a managed Credential record.
    credential = models.ForeignKey(
        Credential,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='devices',
    )

    # Inline credential fields — prefer the credential FK above for SSH/WinRM devices.
    username = models.CharField(max_length=255, blank=True)
    password = EncryptedCharField(max_length=1024, blank=True)
    ssh_private_key = EncryptedCharField(max_length=4096, blank=True)
    # Agent pull fields — used when connection_type='agent'.
    agent_port = models.PositiveIntegerField(
        default=9322,
        blank=True,
        null=True,
        help_text='TCP port the IsotopeIQ agent is listening on (default: 9322).',
    )
    # SSH host public key for host verification (base64 encoded).
    host_key = models.TextField(
        blank=True,
        help_text='SSH host public key (output of ssh-keyscan). Optional but strongly recommended — omitting disables host verification.',
    )

    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name
