import django.db.models.deletion
from django.db import migrations, models


def migrate_steps_forward(apps, schema_editor):
    """Convert existing ScriptJob FK fields into ordered ScriptJobStep records."""
    ScriptJob = apps.get_model('scripts', 'ScriptJob')
    ScriptJobStep = apps.get_model('scripts', 'ScriptJobStep')

    for job in ScriptJob.objects.all():
        order = 0
        has_more = bool(job.server_script_id or job.parser_script_id)

        if job.client_script_id:
            ScriptJobStep.objects.create(
                script_job=job,
                order=order,
                script_id=job.client_script_id,
                run_on='client',
                pipe_to_next=bool(job.server_script_id or job.parser_script_id),
                save_output=True,
                enable_baseline=False,
                enable_drift=False,
            )
            order += 10

        if job.server_script_id:
            ScriptJobStep.objects.create(
                script_job=job,
                order=order,
                script_id=job.server_script_id,
                run_on='server',
                pipe_to_next=bool(job.parser_script_id),
                save_output=False,
                enable_baseline=False,
                enable_drift=False,
            )
            order += 10

        if job.parser_script_id:
            ScriptJobStep.objects.create(
                script_job=job,
                order=order,
                script_id=job.parser_script_id,
                run_on='server',
                pipe_to_next=False,
                save_output=False,
                enable_baseline=job.enable_baseline,
                enable_drift=job.enable_drift,
            )


def migrate_steps_backward(apps, schema_editor):
    """Restore FK fields from ScriptJobStep records (best-effort)."""
    ScriptJob = apps.get_model('scripts', 'ScriptJob')
    ScriptJobStep = apps.get_model('scripts', 'ScriptJobStep')

    for job in ScriptJob.objects.all():
        steps = list(ScriptJobStep.objects.filter(script_job=job).order_by('order'))
        client_steps = [s for s in steps if s.run_on == 'client']
        server_steps = [s for s in steps if s.run_on == 'server' and not s.enable_baseline and not s.enable_drift]
        parser_steps = [s for s in steps if s.run_on == 'server' and (s.enable_baseline or s.enable_drift)]

        job.client_script_id = client_steps[0].script_id if client_steps else None
        job.server_script_id = server_steps[0].script_id if server_steps else None
        job.parser_script_id = parser_steps[0].script_id if parser_steps else None

        any_baseline = any(s.enable_baseline for s in steps)
        any_drift = any(s.enable_drift for s in steps)
        job.enable_baseline = any_baseline
        job.enable_drift = any_drift
        job.save()


class Migration(migrations.Migration):

    dependencies = [
        ('scripts', '0006_delete_scriptpackage'),
    ]

    operations = [
        # 1. Add step_outputs to ScriptJobResult
        migrations.AddField(
            model_name='scriptjobresult',
            name='step_outputs',
            field=models.JSONField(blank=True, null=True),
        ),

        # 2. Create the ScriptJobStep table
        migrations.CreateModel(
            name='ScriptJobStep',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.PositiveIntegerField(default=0)),
                ('run_on', models.CharField(
                    choices=[('client', 'Client (remote device)'), ('server', 'Server (satellite)')],
                    default='client',
                    max_length=20,
                    help_text='Where this script runs.',
                )),
                ('pipe_to_next', models.BooleanField(
                    default=True,
                    help_text="Pass this step's output to the next step as input.",
                )),
                ('save_output', models.BooleanField(
                    default=False,
                    help_text='Persist the raw output of this step in the job result.',
                )),
                ('enable_baseline', models.BooleanField(
                    default=False,
                    help_text="Save this step's output as the device baseline (output must be canonical JSON).",
                )),
                ('enable_drift', models.BooleanField(
                    default=False,
                    help_text="Compare this step's output against the existing baseline and create DriftEvents.",
                )),
                ('script_job', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='steps',
                    to='scripts.scriptjob',
                )),
                ('script', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='job_steps',
                    to='scripts.script',
                )),
            ],
            options={
                'ordering': ['script_job', 'order'],
                'unique_together': {('script_job', 'order')},
            },
        ),

        # 3. Migrate existing FK data to steps
        migrations.RunPython(migrate_steps_forward, migrate_steps_backward),

        # 4. Remove old FK and boolean fields from ScriptJob
        migrations.RemoveField(model_name='scriptjob', name='client_script'),
        migrations.RemoveField(model_name='scriptjob', name='server_script'),
        migrations.RemoveField(model_name='scriptjob', name='parser_script'),
        migrations.RemoveField(model_name='scriptjob', name='enable_baseline'),
        migrations.RemoveField(model_name='scriptjob', name='enable_drift'),
    ]
