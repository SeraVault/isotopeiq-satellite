from rest_framework import serializers
from .models import Policy


class PolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = Policy
        fields = '__all__'

    def to_representation(self, instance):
        from apps.devices.serializers import DeviceSerializer  # noqa: PLC0415
        ret = super().to_representation(instance)
        ret['devices'] = DeviceSerializer(
            instance.devices.all(), many=True, context=self.context
        ).data
        return ret
