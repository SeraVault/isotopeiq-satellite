from django.db import migrations, models
import encrypted_model_fields.fields


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0002_rename_credential_types'),
    ]

    operations = [
        migrations.AlterField(
            model_name='device',
            name='connection_type',
            field=models.CharField(
                choices=[
                    ('ssh', 'SSH'),
                    ('telnet', 'Telnet'),
                    ('winrm', 'WinRM'),
                    ('https', 'HTTPS/API'),
                    ('push', 'Push (Device-Initiated)'),
                    ('agent', 'Agent Pull (port 9322)'),
                ],
                default='ssh',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='device',
            name='agent_port',
            field=models.PositiveIntegerField(
                blank=True,
                default=9322,
                null=True,
                help_text='TCP port the IsotopeIQ agent is listening on (default: 9322).',
            ),
        ),
        migrations.AddField(
            model_name='device',
            name='agent_token',
            field=encrypted_model_fields.fields.EncryptedCharField(
                blank=True,
                max_length=512,
                help_text='Shared secret sent as X-Agent-Token header when pulling from the agent.',
            ),
        ),
    ]
