from rest_framework import serializers
from .models import Job, DeviceJobResult


class DeviceJobResultSerializer(serializers.ModelSerializer):
    # Inline the associated drift event (if any) so the job detail view can
    # display raw data, parsed data, and drift results in a single request
    # (SRD §15.4).
    drift_event = serializers.SerializerMethodField()
    device_name = serializers.CharField(source='device.name', read_only=True)

    class Meta:
        model = DeviceJobResult
        fields = [
            'id', 'job', 'device', 'device_name', 'status',
            'raw_output', 'parsed_output', 'error_message',
            'started_at', 'finished_at', 'drift_event',
        ]

    def get_drift_event(self, obj):
        from apps.drift.serializers import DriftEventSerializer
        # drift_events is a reverse FK — take the most recent one if any
        event = obj.drift_events.order_by('-created_at').first()
        return DriftEventSerializer(event).data if event else None


class DeviceJobResultListSerializer(serializers.ModelSerializer):
    """Lightweight result serializer for the job list (no raw/parsed output)."""
    device_name = serializers.CharField(source='device.name', read_only=True)

    class Meta:
        model = DeviceJobResult
        fields = ['id', 'device', 'device_name', 'status', 'started_at', 'finished_at', 'error_message']


class JobSerializer(serializers.ModelSerializer):
    device_results = DeviceJobResultSerializer(many=True, read_only=True)
    device_name = serializers.CharField(source='device.name', read_only=True, default=None)
    policy_name = serializers.CharField(source='policy.name', read_only=True, default=None)

    class Meta:
        model = Job
        fields = [
            'id', 'device', 'device_name', 'policy', 'policy_name',
            'triggered_by', 'status', 'started_at', 'finished_at',
            'created_at', 'celery_task_id', 'device_results',
        ]


class JobListSerializer(serializers.ModelSerializer):
    """Lightweight job serializer for the list endpoint."""
    device_name = serializers.CharField(source='device.name', read_only=True, default=None)
    policy_name = serializers.CharField(source='policy.name', read_only=True, default=None)
    device_results = DeviceJobResultListSerializer(many=True, read_only=True)

    class Meta:
        model = Job
        fields = ['id', 'device', 'device_name', 'policy', 'policy_name',
                  'triggered_by', 'status', 'started_at', 'finished_at',
                  'created_at', 'device_results']
