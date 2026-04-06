#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# IsotopeIQ Satellite — Remote Deploy Script
# Run from your dev machine.  Rsyncs source to the server and runs install.sh.
#
# Usage:
#   bash deploy/push.sh [user@]host
#
# Or set SERVER in the environment:
#   SERVER=isotopeiq@192.168.122.221 bash deploy/push.sh
#
# Optional env vars:
#   DOMAIN=myserver.example.com        # enables HTTPS (self-signed by default)
#   TLS_CERT=/path/on/server/cert.pem  # use own certificate
#   TLS_KEY=/path/on/server/key.pem    # use own certificate
#   LETSENCRYPT=true                   # use Let's Encrypt (requires internet)
#   SETUP=true                         # also run server-setup.sh (first time only)
#
# Examples:
#   # Plain HTTP update
#   bash deploy/push.sh isotopeiq@192.168.122.221
#
#   # First-time deployment with domain + self-signed cert
#   SETUP=true DOMAIN=myserver.lan bash deploy/push.sh isotopeiq@192.168.122.221
#
#   # Update with Let's Encrypt
#   DOMAIN=myserver.example.com LETSENCRYPT=true bash deploy/push.sh isotopeiq@myserver.example.com
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SERVER="${1:-${SERVER:-}}"
[[ -z "$SERVER" ]] && { echo "Usage: bash deploy/push.sh [user@]host   (or set SERVER=)"; exit 1; }

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE_STAGE="~/isotopeiq-deploy"

DOMAIN="${DOMAIN:-}"
TLS_CERT="${TLS_CERT:-}"
TLS_KEY="${TLS_KEY:-}"
LETSENCRYPT="${LETSENCRYPT:-}"
SETUP="${SETUP:-}"
CREATE_ADMIN="${CREATE_ADMIN:-}"

log()  { echo -e "\033[1;34m[ push ]\033[0m $*"; }
ok()   { echo -e "\033[1;32m[  OK  ]\033[0m $*"; }
warn() { echo -e "\033[1;33m[ WARN ]\033[0m $*"; }
die()  { echo -e "\033[1;31m[ ERR  ]\033[0m $*" >&2; exit 1; }

# ── SSH multiplexing — one password prompt for the entire script ──────────────
SSH_CTRL="$(mktemp -u /tmp/isotopeiq-ssh-XXXXXX)"
SSH_OPTS=(-o ControlMaster=auto -o ControlPath="$SSH_CTRL" -o ControlPersist=60)
ssh "${SSH_OPTS[@]}" -fN "$SERVER"   # open master connection (prompts once)
trap 'ssh -O exit -o ControlPath="$SSH_CTRL" "$SERVER" 2>/dev/null; true' EXIT
ssh()   { command ssh   "${SSH_OPTS[@]}" "$@"; }
rsync() { command rsync -e "ssh ${SSH_OPTS[*]}" "$@"; }

# ── 1. Check .env exists on server ───────────────────────────────────────────
if ! ssh "$SERVER" 'test -f /etc/isotopeiq/.env' 2>/dev/null; then
    warn "/etc/isotopeiq/.env not found on server."
    warn "After first sync, run:"
    warn "  ssh $SERVER 'sudo mkdir -p /etc/isotopeiq && sudo cp $REMOTE_STAGE/deploy/.env.production /etc/isotopeiq/.env'"
    warn "Then edit /etc/isotopeiq/.env on the server, and re-run this script."
fi

# ── 2. Rsync source to server ─────────────────────────────────────────────────
log "Syncing source to $SERVER:$REMOTE_STAGE …"
rsync -az --delete \
    --exclude='.venv' \
    --exclude='venv' \
    --exclude='node_modules' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.git' \
    --exclude='staticfiles' \
    --exclude='celerybeat-schedule' \
    --exclude='*.tar.gz' \
    "$ROOT/" "$SERVER:$REMOTE_STAGE/"
ok "Source synced."

# ── 3. First-time server setup (OS packages, postgres, redis, nginx) ──────────
if [[ -n "$SETUP" ]]; then
    log "Running server-setup.sh on $SERVER …"
    ssh -t "$SERVER" "sudo bash $REMOTE_STAGE/deploy/server-setup.sh"
    ok "Server setup complete."
fi

# ── 4. Prompt for admin credentials if needed ────────────────────────────────
DJANGO_SUPERUSER_USERNAME="${DJANGO_SUPERUSER_USERNAME:-}"
DJANGO_SUPERUSER_PASSWORD="${DJANGO_SUPERUSER_PASSWORD:-}"
DJANGO_SUPERUSER_EMAIL="${DJANGO_SUPERUSER_EMAIL:-}"

if [[ -z "$DJANGO_SUPERUSER_USERNAME" ]]; then
    # Always prompt if CREATE_ADMIN=true; otherwise only if no superuser exists yet
    SHOULD_PROMPT=false
    if [[ -n "$CREATE_ADMIN" ]]; then
        SHOULD_PROMPT=true
    else
        HAS_ADMIN=$(ssh "$SERVER" \
            "cd /opt/isotopeiq/backend && sudo -u isotopeiq \
             DJANGO_SETTINGS_MODULE=config.settings.production \
             /opt/isotopeiq/venv/bin/python manage.py shell \
             -c 'from django.contrib.auth import get_user_model; print(get_user_model().objects.filter(is_superuser=True).count())' \
             2>/dev/null || echo 0" 2>/dev/null | tail -1 || echo 0)
        [[ "${HAS_ADMIN//[^0-9]/}" -eq 0 ]] && SHOULD_PROMPT=true
    fi

    if [[ "$SHOULD_PROMPT" == true ]]; then
        echo
        log "Enter credentials for the Django admin user."
        read -rp    "  Admin username [admin]: " DJANGO_SUPERUSER_USERNAME
        DJANGO_SUPERUSER_USERNAME="${DJANGO_SUPERUSER_USERNAME:-admin}"
        read -rp    "  Admin email: "            DJANGO_SUPERUSER_EMAIL
        read -rs -p "  Admin password: "         DJANGO_SUPERUSER_PASSWORD; echo
        echo
    fi
fi

# ── 5. Build install command ──────────────────────────────────────────────────
# Use 'sudo -E env ...' so variables survive sudo's env_reset.
ENV_ARGS=""
[[ -n "$DOMAIN"                    ]] && ENV_ARGS+=" DOMAIN=$(printf '%q' "$DOMAIN")"
[[ -n "$TLS_CERT"                  ]] && ENV_ARGS+=" TLS_CERT=$(printf '%q' "$TLS_CERT")"
[[ -n "$TLS_KEY"                   ]] && ENV_ARGS+=" TLS_KEY=$(printf '%q' "$TLS_KEY")"
[[ -n "$LETSENCRYPT"               ]] && ENV_ARGS+=" LETSENCRYPT=$(printf '%q' "$LETSENCRYPT")"
[[ -n "$DJANGO_SUPERUSER_USERNAME" ]] && ENV_ARGS+=" DJANGO_SUPERUSER_USERNAME=$(printf '%q' "$DJANGO_SUPERUSER_USERNAME")"
[[ -n "$DJANGO_SUPERUSER_EMAIL"    ]] && ENV_ARGS+=" DJANGO_SUPERUSER_EMAIL=$(printf '%q' "$DJANGO_SUPERUSER_EMAIL")"
[[ -n "$DJANGO_SUPERUSER_PASSWORD" ]] && ENV_ARGS+=" DJANGO_SUPERUSER_PASSWORD=$(printf '%q' "$DJANGO_SUPERUSER_PASSWORD")"

# ── 6. Run install.sh on server ───────────────────────────────────────────────
log "Running install.sh on $SERVER …"
ssh -t "$SERVER" "sudo env${ENV_ARGS} bash $REMOTE_STAGE/deploy/install.sh"
ok "Deployment complete → $SERVER"
