from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from .models import Script
from .package_models import ScriptPackage


@admin.register(Script)
class ScriptAdmin(ImportExportModelAdmin):
    list_display = ['name', 'script_type', 'target_os', 'version', 'is_active']
    list_filter = ['script_type', 'target_os', 'is_active']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ScriptPackage)
class ScriptPackageAdmin(ImportExportModelAdmin):
    list_display = ['name', 'target_os', 'collection_script', 'parser_script', 'is_active']
    list_filter = ['target_os', 'is_active']
    search_fields = ['name', 'description']
    autocomplete_fields = ['collection_script', 'parser_script']
