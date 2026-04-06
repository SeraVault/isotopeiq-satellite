from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from .models import Job, DeviceJobResult


class DeviceJobResultInline(admin.TabularInline):
    model = DeviceJobResult
    extra = 0
    readonly_fields = ['device', 'status', 'error_message', 'started_at', 'finished_at']
    fields = ['device', 'status', 'error_message', 'started_at', 'finished_at']
    can_delete = False


@admin.register(Job)
class JobAdmin(ImportExportModelAdmin):
    list_display = ['id', 'policy', 'status', 'triggered_by', 'started_at', 'finished_at']
    list_filter = ['status', 'triggered_by']
    readonly_fields = ['celery_task_id', 'created_at', 'started_at', 'finished_at']
    inlines = [DeviceJobResultInline]


@admin.register(DeviceJobResult)
class DeviceJobResultAdmin(ImportExportModelAdmin):
    list_display = ['id', 'job', 'device', 'status', 'started_at', 'finished_at']
    list_filter = ['status']
    search_fields = ['device__name']
    readonly_fields = ['raw_output', 'parsed_output', 'started_at', 'finished_at']
