from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scripts', '0007_scriptjobstep'),
    ]

    operations = [
        migrations.RemoveField(model_name='scriptjob', name='cron_schedule'),
        migrations.RemoveField(model_name='scriptjob', name='devices'),
    ]
