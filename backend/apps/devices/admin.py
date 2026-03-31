from django.contrib import admin
from .models import Credential, Device


@admin.register(Credential)
class CredentialAdmin(admin.ModelAdmin):
    list_display = ['name', 'credential_type', 'username', 'created_at']
    list_filter = ['credential_type']
    search_fields = ['name', 'username']
    readonly_fields = ['created_at', 'updated_at']
    exclude = ['password', 'private_key', 'token']  # never display secrets in admin


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ['name', 'hostname', 'port', 'connection_type', 'is_active']
    list_filter = ['connection_type', 'is_active']
    search_fields = ['name', 'hostname', 'fqdn']
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['credential']
