from django.contrib import admin
from .models import Baseline


@admin.register(Baseline)
class BaselineAdmin(admin.ModelAdmin):
    list_display = ['device', 'established_at', 'established_by']
    list_filter = ['established_by']
    search_fields = ['device__name']
    readonly_fields = ['established_at', 'parsed_data']
