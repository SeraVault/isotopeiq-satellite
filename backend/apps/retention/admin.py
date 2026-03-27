from django.contrib import admin
from .models import RetentionPolicy


@admin.register(RetentionPolicy)
class RetentionPolicyAdmin(admin.ModelAdmin):
    list_display = ['raw_data_days', 'parsed_data_days', 'job_history_days', 'log_days', 'updated_at']
    readonly_fields = ['updated_at']

    def has_add_permission(self, request):
        return not RetentionPolicy.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
