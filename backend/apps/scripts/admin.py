from django.contrib import admin
from .models import Script


@admin.register(Script)
class ScriptAdmin(admin.ModelAdmin):
    list_display = ['name', 'script_type', 'target_os', 'version', 'is_active']
    list_filter = ['script_type', 'target_os', 'is_active']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
