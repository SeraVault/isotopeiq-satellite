from rest_framework import serializers
from .models import Credential, Device


class CredentialSerializer(serializers.ModelSerializer):
    class Meta:
        model = Credential
        fields = '__all__'
        extra_kwargs = {
            'password':    {'write_only': True},
            'private_key': {'write_only': True},
            'token':       {'write_only': True},
        }


class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = '__all__'
        extra_kwargs = {
            'password':        {'write_only': True},
            'ssh_private_key': {'write_only': True},
        }
