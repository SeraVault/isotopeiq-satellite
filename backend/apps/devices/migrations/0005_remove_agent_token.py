from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0004_remove_push'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='device',
            name='agent_token',
        ),
    ]
