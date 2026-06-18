from rest_framework import serializers
from .models import DriftEvent, VolatileFieldRule


class VolatileFieldRuleSerializer(serializers.ModelSerializer):
    script_job_name = serializers.SerializerMethodField()

    class Meta:
        model = VolatileFieldRule
        fields = [
            'id', 'script_job', 'script_job_name',
            'section', 'spec_type', 'field_name', 'aux',
            'description', 'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_script_job_name(self, obj):
        if obj.script_job_id:
            return str(obj.script_job)
        return None


class DriftEventSerializer(serializers.ModelSerializer):
    """Lean serializer used for list/polling — no heavy JSON payloads."""
    device_name = serializers.SerializerMethodField()

    class Meta:
        model = DriftEvent
        fields = [
            'id', 'device', 'device_name', 'job_result',
            'diff', 'status',
            'acknowledged_by', 'acknowledged_at', 'acknowledgement_reason',
            'created_at',
        ]
        read_only_fields = ['created_at']

    def get_device_name(self, obj):
        try:
            return obj.device.name or obj.device.hostname
        except Exception:
            return str(obj.device_id)


class DriftEventDetailSerializer(DriftEventSerializer):
    """Full serializer for single-event retrieval."""
    baseline_data = serializers.SerializerMethodField()
    result_data = serializers.SerializerMethodField()
    script_job_id = serializers.SerializerMethodField()

    class Meta(DriftEventSerializer.Meta):
        fields = DriftEventSerializer.Meta.fields + [
            'baseline_data', 'result_data',
            'baseline_snapshot', 'script_job_id',
        ]

    def get_baseline_data(self, obj):
        return obj.baseline_snapshot

    def get_result_data(self, obj):
        try:
            return obj.job_result.parsed_output
        except Exception:
            return None

    def get_script_job_id(self, obj):
        try:
            return obj.job_result.job.policy.script_job_id
        except Exception:
            return None
