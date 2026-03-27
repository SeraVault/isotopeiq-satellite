from django.contrib import admin
from .models import Policy


@admin.register(Policy)
class PolicyAdmin(admin.ModelAdmin):
    list_display = ['name', 'cron_schedule', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'description']
    filter_horizontal = ['devices']
    readonly_fields = ['created_at', 'updated_at']
