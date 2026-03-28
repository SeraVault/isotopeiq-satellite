from rest_framework import serializers
from .models import Baseline


class BaselineSerializer(serializers.ModelSerializer):
    device_name = serializers.CharField(source='device.name', read_only=True)

    class Meta:
        model = Baseline
        fields = ['id', 'device', 'device_name', 'established_at', 'established_by', 'parsed_data']
        read_only_fields = ['established_at']
