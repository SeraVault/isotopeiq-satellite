from rest_framework import serializers
from .models import RetentionPolicy


class RetentionPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = RetentionPolicy
        fields = '__all__'
        read_only_fields = ['updated_at']
