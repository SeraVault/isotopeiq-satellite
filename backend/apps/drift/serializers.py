from rest_framework import serializers
from .models import DriftEvent


class DriftEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = DriftEvent
        fields = '__all__'
        read_only_fields = ['created_at']
