from rest_framework import serializers
from .models import DriftEvent, VolatileFieldRule


class VolatileFieldRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = VolatileFieldRule
        fields = [
            'id', 'section', 'spec_type', 'field_name', 'aux',
            'description', 'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


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
    """Full serializer used for single-event retrieval — includes canonical payloads."""
    baseline_data = serializers.SerializerMethodField()
    result_data = serializers.SerializerMethodField()

    class Meta(DriftEventSerializer.Meta):
        fields = DriftEventSerializer.Meta.fields + ['baseline_data', 'result_data', 'baseline_snapshot']

    def get_baseline_data(self, obj):
        return obj.baseline_snapshot

    def get_result_data(self, obj):
        try:
            return obj.job_result.parsed_output
        except Exception:
            return None
