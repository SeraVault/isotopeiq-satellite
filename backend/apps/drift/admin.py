from django.contrib import admin
from .models import DriftEvent


@admin.register(DriftEvent)
class DriftEventAdmin(admin.ModelAdmin):
    list_display = ['device', 'status', 'created_at', 'acknowledged_by']
    list_filter = ['status']
    search_fields = ['device__name']
    readonly_fields = ['created_at', 'diff', 'job_result']
