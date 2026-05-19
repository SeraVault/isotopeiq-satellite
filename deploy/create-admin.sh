#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# IsotopeIQ Satellite — Create Django Admin User
# Run as root on the server when no superuser exists yet.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

PYTHON=/opt/isotopeiq/venv/bin/python
APP_DIR=/opt/isotopeiq

[[ $EUID -ne 0 ]] && { echo "Run as root or with sudo."; exit 1; }

read -rp        "Admin username [admin]: " DJANGO_SUPERUSER_USERNAME
DJANGO_SUPERUSER_USERNAME="${DJANGO_SUPERUSER_USERNAME:-admin}"
read -rp        "Admin email: "            DJANGO_SUPERUSER_EMAIL
read -rs -p     "Admin password: "         DJANGO_SUPERUSER_PASSWORD; echo
read -rs -p     "Confirm password: "       CONFIRM; echo

[[ "$DJANGO_SUPERUSER_PASSWORD" != "$CONFIRM" ]] && { echo "Passwords do not match."; exit 1; }

cd "$APP_DIR/backend"
sudo -u isotopeiq \
    DJANGO_SETTINGS_MODULE=config.settings.production \
    DJANGO_SUPERUSER_USERNAME="$DJANGO_SUPERUSER_USERNAME" \
    DJANGO_SUPERUSER_PASSWORD="$DJANGO_SUPERUSER_PASSWORD" \
    DJANGO_SUPERUSER_EMAIL="$DJANGO_SUPERUSER_EMAIL" \
    "$PYTHON" manage.py createsuperuser --noinput

echo "Admin user '$DJANGO_SUPERUSER_USERNAME' created."
