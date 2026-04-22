"""
Management command: ensure_admin

Creates a Django superuser on first boot if no superuser exists.
Credentials are read from environment variables:

  DJANGO_SUPERUSER_USERNAME  (default: admin)
  DJANGO_SUPERUSER_EMAIL     (default: admin@localhost)
  DJANGO_SUPERUSER_PASSWORD  (required; skips creation if not set)

Idempotent — safe to call on every startup.
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create a superuser from env vars if none exists (idempotent)."

    def handle(self, *args, **options):
        User = get_user_model()

        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write("ensure_admin: superuser already exists, skipping.")
            return

        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "")
        if not password:
            self.stdout.write(
                self.style.WARNING(
                    "ensure_admin: DJANGO_SUPERUSER_PASSWORD not set — skipping auto-create. "
                    "Run 'manage.py createsuperuser' manually."
                )
            )
            return

        username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "admin")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "admin@localhost")

        User.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write(
            self.style.SUCCESS(f"ensure_admin: superuser '{username}' created.")
        )
