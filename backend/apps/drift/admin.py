from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from .models import DriftEvent


@admin.register(DriftEvent)
class DriftEventAdmin(ImportExportModelAdmin):
    list_display = ['device', 'status', 'created_at', 'acknowledged_by']
    list_filter = ['status']
    search_fields = ['device__name']
    readonly_fields = ['created_at', 'diff', 'job_result']
