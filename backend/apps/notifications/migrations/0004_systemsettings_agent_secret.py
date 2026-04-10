from django.db import migrations
import encrypted_model_fields.fields


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0003_ldap_settings'),
    ]

    operations = [
        migrations.AddField(
            model_name='systemsettings',
            name='agent_secret',
            field=encrypted_model_fields.fields.EncryptedCharField(
                blank=True,
                help_text='Shared secret for agent authentication. Agents must supply this value in '
                          'the X-Agent-Secret request header. Leave blank to disable secret enforcement.',
                max_length=255,
            ),
        ),
    ]
