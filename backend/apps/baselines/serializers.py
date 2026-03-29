from rest_framework import serializers
from .models import Baseline


class BaselineListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list endpoints — omits parsed_data."""
    device_name = serializers.CharField(source='device.name', read_only=True)

    class Meta:
        model = Baseline
        fields = ['id', 'device', 'device_name', 'established_at', 'established_by']
        read_only_fields = ['established_at']


class BaselineSerializer(serializers.ModelSerializer):
    device_name = serializers.CharField(source='device.name', read_only=True)

    class Meta:
        model = Baseline
        fields = ['id', 'device', 'device_name', 'established_at', 'established_by', 'parsed_data']
        read_only_fields = ['established_at']
