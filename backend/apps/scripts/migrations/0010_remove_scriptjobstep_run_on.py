from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scripts', '0009_add_run_on_language_to_script'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='scriptjobstep',
            name='run_on',
        ),
    ]
