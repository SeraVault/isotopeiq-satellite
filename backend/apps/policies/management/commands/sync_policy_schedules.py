from django.core.management.base import BaseCommand

from apps.policies.models import Policy
from apps.policies.schedule import sync_policy, delete_policy_schedule


class Command(BaseCommand):
    help = (
        'Synchronise all Policy records with django_celery_beat PeriodicTasks. '
        'Run once after initial deployment or after bulk-importing policies.'
    )

    def handle(self, *args, **options):
        policies = Policy.objects.all()
        synced = 0
        for policy in policies:
            sync_policy(policy)
            synced += 1
        self.stdout.write(self.style.SUCCESS(f'Synced {synced} policy schedule(s).'))
