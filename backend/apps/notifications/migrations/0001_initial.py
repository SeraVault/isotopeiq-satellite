from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='SystemSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('syslog_host', models.CharField(default='localhost', max_length=253)),
                ('syslog_port', models.PositiveIntegerField(default=514)),
                ('syslog_facility', models.CharField(default='local0', max_length=32)),
                ('syslog_enabled', models.BooleanField(default=False)),
                ('satellite_url', models.CharField(
                    default='http://localhost:8000',
                    help_text='Public base URL of this satellite (used in agent download links, etc.)',
                    max_length=255,
                )),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'System Settings',
                'verbose_name_plural': 'System Settings',
            },
        ),
    ]
