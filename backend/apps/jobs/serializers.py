from rest_framework import serializers
from .models import Job, DeviceJobResult


class DeviceJobResultSerializer(serializers.ModelSerializer):
    # Inline the associated drift event (if any) so the job detail view can
    # display raw data, parsed data, and drift results in a single request
    # (SRD §15.4).
    drift_event = serializers.SerializerMethodField()

    class Meta:
        model = DeviceJobResult
        fields = '__all__'

    def get_drift_event(self, obj):
        from apps.drift.serializers import DriftEventSerializer
        # drift_events is a reverse FK — take the most recent one if any
        event = obj.drift_events.order_by('-created_at').first()
        return DriftEventSerializer(event).data if event else None


class JobSerializer(serializers.ModelSerializer):
    device_results = DeviceJobResultSerializer(many=True, read_only=True)

    class Meta:
        model = Job
        fields = '__all__'
