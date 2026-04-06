from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from .models import Baseline


@admin.register(Baseline)
class BaselineAdmin(ImportExportModelAdmin):
    list_display = ['device', 'established_at', 'established_by']
    list_filter = ['established_by']
    search_fields = ['device__name']
    readonly_fields = ['established_at', 'parsed_data']
