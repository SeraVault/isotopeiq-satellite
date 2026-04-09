from rest_framework import serializers
from .job_models import ScriptJob, ScriptJobStep, ScriptJobResult


class ScriptJobStepSerializer(serializers.ModelSerializer):
    script_name = serializers.CharField(source='script.name', read_only=True, default=None)
    script_run_on = serializers.CharField(source='script.run_on', read_only=True, default=None)

    class Meta:
        model = ScriptJobStep
        fields = [
            'id', 'order', 'script', 'script_name', 'script_run_on',
            'pipe_to_next', 'save_output', 'enable_baseline', 'enable_drift',
        ]


class ScriptJobSerializer(serializers.ModelSerializer):
    steps = ScriptJobStepSerializer(many=True, read_only=True)

    class Meta:
        model = ScriptJob
        fields = '__all__'

    def _sync_steps(self, instance, steps_data):
        """Replace all steps on `instance` with the provided list."""
        instance.steps.all().delete()
        for item in steps_data:
            item = dict(item)
            item['script_id'] = item.pop('script', None)
            item.pop('run_on', None)          # no longer a step field
            item.pop('script_run_on', None)   # read-only, never written
            item.pop('script_name', None)     # read-only, never written
            ScriptJobStep.objects.create(script_job=instance, **item)

    def create(self, validated_data):
        steps_data = self.initial_data.get('steps', [])
        instance = super().create(validated_data)
        self._sync_steps(instance, steps_data)
        return instance

    def update(self, instance, validated_data):
        steps_data = self.initial_data.get('steps', None)
        instance = super().update(instance, validated_data)
        if steps_data is not None:
            self._sync_steps(instance, steps_data)
        return instance


class ScriptJobResultSerializer(serializers.ModelSerializer):
    device_name = serializers.CharField(source='device.name', read_only=True, default=None)
    script_job_name = serializers.CharField(source='script_job.name', read_only=True)

    class Meta:
        model = ScriptJobResult
        fields = '__all__'
        read_only_fields = [
            'script_job', 'device', 'status', 'step_outputs',
            'client_output', 'server_output', 'parsed_output',
            'error_message', 'started_at', 'finished_at', 'celery_task_id',
        ]
