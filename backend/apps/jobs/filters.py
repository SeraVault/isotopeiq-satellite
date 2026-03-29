"""
Custom django-filters filterset for Job history (SRD §15.4).

SRD requires: filter by Device, Policy, Script, Status, Date.

Jobs don't store the script directly — they reference a Policy which has
collection_script and parser_script FKs.  We expose a single `script`
filter that matches jobs whose policy uses that script in either role.
"""
import django_filters
from django.db.models import Q

from .models import Job


class JobFilter(django_filters.FilterSet):
    # Pass script ID → match jobs whose policy references that script
    script = django_filters.NumberFilter(method='filter_by_script', label='Script ID')

    # Device ID → filter directly on the Job.device FK
    device = django_filters.NumberFilter(
        field_name='device',
        label='Device ID',
    )

    # Date range on created_at
    created_after = django_filters.IsoDateTimeFilter(
        field_name='created_at',
        lookup_expr='gte',
        label='Created after (ISO 8601)',
    )
    created_before = django_filters.IsoDateTimeFilter(
        field_name='created_at',
        lookup_expr='lte',
        label='Created before (ISO 8601)',
    )

    class Meta:
        model = Job
        fields = ['status', 'policy', 'triggered_by']

    def filter_by_script(self, queryset, name, value):  # noqa: ARG002
        return queryset.filter(
            Q(policy__collection_script_id=value)
            | Q(policy__parser_script_id=value)
            | Q(policy__deployment_script_id=value)
        ).distinct()
