from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import Policy


@receiver(post_save, sender=Policy)
def on_policy_save(sender, instance, **kwargs):
    from .schedule import sync_policy
    sync_policy(instance)


@receiver(post_delete, sender=Policy)
def on_policy_delete(sender, instance, **kwargs):
    from .schedule import delete_policy_schedule
    delete_policy_schedule(instance.pk)
