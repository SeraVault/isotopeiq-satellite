from rest_framework import serializers
from .models import Baseline


class BaselineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Baseline
        fields = '__all__'
        read_only_fields = ['established_at']
