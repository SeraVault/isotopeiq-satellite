from rest_framework import serializers
from .models import SystemSettings, PostCollectionAction


class SystemSettingsSerializer(serializers.ModelSerializer):
    # Passwords are write-only: they are accepted on PUT/PATCH but never
    # returned in GET responses to avoid leaking credentials over the API.
    email_password = serializers.CharField(
        write_only=True, required=False, allow_blank=True,
        style={'input_type': 'password'},
    )
    ftp_password = serializers.CharField(
        write_only=True, required=False, allow_blank=True,
        style={'input_type': 'password'},
    )
    # Expose boolean flags so the UI knows whether a password is stored
    # without revealing the value itself.
    email_password_set = serializers.SerializerMethodField(read_only=True)
    ftp_password_set   = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = SystemSettings
        fields = '__all__'
        read_only_fields = ['updated_at']

    def get_email_password_set(self, obj):
        return bool(obj.email_password)

    def get_ftp_password_set(self, obj):
        return bool(obj.ftp_password)

    def update(self, instance, validated_data):
        # If a password field is omitted or blank, keep the existing value.
        for field in ('email_password', 'ftp_password'):
            if field in validated_data and not validated_data[field]:
                validated_data.pop(field)
        return super().update(instance, validated_data)


class PostCollectionActionSerializer(serializers.ModelSerializer):
    trigger_label     = serializers.CharField(source='get_trigger_display',     read_only=True)
    destination_label = serializers.CharField(source='get_destination_display', read_only=True)

    class Meta:
        model  = PostCollectionAction
        fields = [
            'id', 'policy', 'trigger', 'trigger_label',
            'destination', 'destination_label', 'is_active', 'created_at',
        ]
        read_only_fields = ['created_at']
