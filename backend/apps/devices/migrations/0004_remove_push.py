from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0003_device_agent_fields'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='device',
            name='push_token',
        ),
        migrations.AlterField(
            model_name='device',
            name='connection_type',
            field=models.CharField(
                choices=[
                    ('ssh', 'SSH'),
                    ('telnet', 'Telnet'),
                    ('winrm', 'WinRM'),
                    ('https', 'HTTPS/API'),
                    ('agent', 'Agent Pull (port 9322)'),
                ],
                default='ssh',
                max_length=20,
            ),
        ),
    ]
