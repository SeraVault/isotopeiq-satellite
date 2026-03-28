from rest_framework import serializers
from .models import DriftEvent


class DriftEventSerializer(serializers.ModelSerializer):
    device_name = serializers.SerializerMethodField()

    class Meta:
        model = DriftEvent
        fields = '__all__'
        read_only_fields = ['created_at']

    def get_device_name(self, obj):
        try:
            return obj.device.name or obj.device.hostname
        except Exception:
            return str(obj.device_id)
