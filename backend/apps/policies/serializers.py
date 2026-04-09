from rest_framework import serializers
from .models import Policy


class PolicySerializer(serializers.ModelSerializer):
    script_job_detail = serializers.SerializerMethodField()

    class Meta:
        model = Policy
        fields = '__all__'

    def get_script_job_detail(self, obj):
        if obj.script_job_id:
            sj = obj.script_job
            steps = list(sj.steps.select_related('script').order_by('order'))
            return {
                'id': sj.id,
                'name': sj.name,
                'step_count': len(steps),
                'steps': [
                    {
                        'order': s.order,
                        'script_name': s.script.name,
                        'run_on': s.script.run_on,
                    }
                    for s in steps
                ],
            }
        return None

    def to_representation(self, instance):
        from apps.devices.serializers import DeviceSerializer  # noqa: PLC0415
        ret = super().to_representation(instance)
        ret['devices'] = DeviceSerializer(
            instance.devices.all(), many=True, context=self.context
        ).data
        return ret
