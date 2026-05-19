#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# IsotopeIQ Satellite — Docker Deployment Script
# Ships inside the docker bundle produced by deploy/docker-bundle.sh.
# Run on the target server after extracting the bundle.
#
# Usage:
#   bash deploy.sh          # first-time or update
#   bash deploy.sh stop     # stop all services
#   bash deploy.sh logs     # follow logs
#   bash deploy.sh status   # show container status
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.yml"
ENV_FILE="$SCRIPT_DIR/.env.docker"

log()  { echo -e "\033[1;34m[isotopeiq]\033[0m $*"; }
ok()   { echo -e "\033[1;32m[  OK  ]\033[0m $*"; }
die()  { echo -e "\033[1;31m[ ERR  ]\033[0m $*" >&2; exit 1; }

compose() {
    docker compose --file "$COMPOSE_FILE" --env-file "$ENV_FILE" "$@"
}

# ── Sub-commands ──────────────────────────────────────────────────────────────
case "${1:-up}" in
    stop)
        log "Stopping all services…"
        compose down
        ok "Stopped."
        exit 0
        ;;
    logs)
        compose logs -f "${2:-}"
        exit 0
        ;;
    status)
        compose ps
        exit 0
        ;;
    up|"")
        ;;  # fall through to main deploy logic
    *)
        echo "Usage: $0 [up|stop|logs|status]"
        exit 1
        ;;
esac

# ── Preflight checks ──────────────────────────────────────────────────────────
command -v docker >/dev/null 2>&1 || die "Docker not found. Install Docker first: https://docs.docker.com/engine/install/"
docker compose version >/dev/null 2>&1 || die "Docker Compose plugin not found."

# ── Environment file ──────────────────────────────────────────────────────────
if [[ ! -f "$ENV_FILE" ]]; then
    if [[ -f "$SCRIPT_DIR/.env.docker.example" ]]; then
        log "No .env.docker found — copying from .env.docker.example"
        cp "$SCRIPT_DIR/.env.docker.example" "$ENV_FILE"
        echo
        echo "  Edit $ENV_FILE and set at minimum:"
        echo "    SECRET_KEY              (generate: python3 -c \"import secrets; print(secrets.token_urlsafe(64))\")"
        echo "    FIELD_ENCRYPTION_KEY    (generate: python3 -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\")"
        echo "    DB_PASSWORD"
        echo "    ALLOWED_HOSTS"
        echo "    DJANGO_SUPERUSER_PASSWORD  (sets the initial admin password on first boot)"
        echo
        read -rp "Press Enter after editing .env.docker to continue, or Ctrl-C to exit…"
    else
        die ".env.docker not found. Create it from .env.docker.example before running this script."
    fi
fi

# Basic check — catch people who left the placeholder keys
SECRET_KEY_VAL=$(grep -E '^SECRET_KEY=' "$ENV_FILE" | cut -d= -f2-)
if [[ -z "$SECRET_KEY_VAL" || "$SECRET_KEY_VAL" == "CHANGE_ME"* ]]; then
    die "SECRET_KEY is not set in .env. Generate one and try again."
fi

# ── Load images (skip if already loaded) ─────────────────────────────────────
IMAGES_FILE="$SCRIPT_DIR/images.tar.gz"
if [[ -f "$IMAGES_FILE" ]]; then
    log "Loading Docker images from images.tar.gz…"
    docker load < "$IMAGES_FILE"
    ok "Images loaded."
else
    log "images.tar.gz not found — assuming images are already loaded."
fi

# ── Create host data directories ─────────────────────────────────────────────
log "Creating data directories…"
# Source the env file so DATA_* overrides are available
set -a; source "$ENV_FILE"; set +a
mkdir -p \
    "${DATA_POSTGRES:-$SCRIPT_DIR/data/postgres}" \
    "${DATA_REDIS:-$SCRIPT_DIR/data/redis}" \
    "${DATA_STATICFILES:-$SCRIPT_DIR/data/staticfiles}" \
    "${DATA_TLS:-$SCRIPT_DIR/data/tls}"

# ── Start the stack ───────────────────────────────────────────────────────────
log "Starting IsotopeIQ Satellite…"
compose up -d --remove-orphans

ok "IsotopeIQ Satellite is running."
echo
echo "  HTTP  → http://$(hostname -I | awk '{print $1}')"
echo "  HTTPS → https://$(hostname -I | awk '{print $1}')"
echo
echo "Admin login: use the DJANGO_SUPERUSER_USERNAME / DJANGO_SUPERUSER_PASSWORD set in .env.docker"
echo "(auto-created on first boot; change the password after first login)"
echo
echo "To create the admin manually instead:"
echo "  docker compose --file $COMPOSE_FILE --env-file $ENV_FILE exec backend python manage.py createsuperuser"
