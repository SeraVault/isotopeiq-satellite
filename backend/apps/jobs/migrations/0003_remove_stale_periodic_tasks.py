from django.db import migrations


STALE_TASK_NAMES = [
    'devices.run_scheduled_scripts',
    'devices.run_scheduled_collections',
]


def remove_stale_tasks(apps, schema_editor):
    try:
        PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')
    except LookupError:
        return  # django_celery_beat not installed — skip
    PeriodicTask.objects.filter(task__in=STALE_TASK_NAMES).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('jobs', '0002_job_add_device'),
    ]

    operations = [
        migrations.RunPython(remove_stale_tasks, migrations.RunPython.noop),
    ]
