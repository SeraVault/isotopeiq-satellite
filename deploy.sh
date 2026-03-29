#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="$(cd "$(dirname "$0")" && pwd)/docker-compose.yml"
ENV_FILE="$(cd "$(dirname "$0")" && pwd)/.env"

# ── Helpers ──────────────────────────────────────────────────────────────────
log()  { echo -e "\033[1;34m[isotopeiq]\033[0m $*"; }
ok()   { echo -e "\033[1;32m[  OK  ]\033[0m $*"; }
err()  { echo -e "\033[1;31m[ ERR  ]\033[0m $*" >&2; }
die()  { err "$*"; exit 1; }

SERVICES="db redis backend worker beat frontend"

usage() {
  cat <<EOF
Usage: $(basename "$0") [COMMAND] [SERVICE]

Commands:
  build                 Build (or rebuild) all images
  up                    Build + start all services in the background
  down                  Stop and remove containers (data volumes are preserved)
  restart [SERVICE]     Restart all services, or a single one if specified
  logs    [SERVICE]     Follow logs for all services, or a single one
  migrate               Run Django database migrations
  createsuperuser       Create a Django admin superuser
  shell                 Open a bash shell in the backend container
  status                Show running container status
  reset-db              !! Destroy and recreate the postgres volume (ALL DATA LOST)
  help                  Show this message

Services:  $SERVICES

If no command is given, 'up' is assumed.
EOF
}

require_docker() {
  command -v docker >/dev/null 2>&1 || die "docker not found. Install Docker first."
  docker compose version >/dev/null 2>&1 || die "docker compose plugin not found."
}

require_env() {
  [[ -f "$ENV_FILE" ]] || die ".env file not found at $ENV_FILE. Copy .env.example and fill it in."
}

compose() {
  docker compose --file "$COMPOSE_FILE" --env-file "$ENV_FILE" "$@"
}

# Resolve friendly name -> compose service name
resolve_service() {
  case "$1" in
    db|redis|backend|frontend) echo "$1" ;;
    worker)  echo "celery_worker" ;;
    beat)    echo "celery_beat" ;;
    *)       die "Unknown service '$1'. Valid services: $SERVICES" ;;
  esac
}

# ── Commands ─────────────────────────────────────────────────────────────────
cmd_build() {
  log "Building images…"
  compose build --pull
  ok "Build complete."
}

cmd_up() {
  log "Starting all services…"
  compose up --build --detach
  ok "Services started. Backend: http://localhost:8000  Frontend: http://localhost:5173"
  log "Waiting for postgres to be ready…"
  local retries=20
  until compose exec db pg_isready -q 2>/dev/null || [[ $retries -eq 0 ]]; do
    sleep 1
    ((retries--))
  done
  [[ $retries -gt 0 ]] || die "Postgres did not become ready in time."
  ok "Postgres is ready."
  cmd_migrate
}

cmd_down() {
  log "Stopping services…"
  compose down --remove-orphans
  ok "Services stopped."
}

cmd_restart() {
  local svc="${1:-}"
  if [[ -n "$svc" ]]; then
    local compose_svc
    compose_svc="$(resolve_service "$svc")"
    log "Restarting $svc…"
    compose restart "$compose_svc"
    ok "$svc restarted."
  else
    cmd_down
    cmd_up
  fi
}

cmd_logs() {
  local svc="${1:-}"
  if [[ -n "$svc" ]]; then
    local compose_svc
    compose_svc="$(resolve_service "$svc")"
    compose logs --follow --tail=100 "$compose_svc"
  else
    compose logs --follow --tail=100
  fi
}

cmd_migrate() {
  log "Running migrations…"
  compose exec backend python manage.py migrate --noinput
  ok "Migrations applied."
}

cmd_createsuperuser() {
  compose exec backend python manage.py createsuperuser
}

cmd_shell() {
  compose exec backend bash
}

cmd_status() {
  compose ps
}

cmd_reset_db() {
  echo
  err "WARNING: This will permanently delete ALL database data."
  read -r -p "Type 'yes' to confirm: " confirm
  [[ "$confirm" == "yes" ]] || { log "Aborted."; exit 0; }
  compose down --volumes --remove-orphans
  ok "Volume destroyed. Run './deploy.sh up' to recreate."
}

# ── Entrypoint ────────────────────────────────────────────────────────────────
require_docker
require_env

COMMAND="${1:-up}"
shift || true

case "$COMMAND" in
  build)            cmd_build ;;
  up)               cmd_up ;;
  down)             cmd_down ;;
  restart)          cmd_restart "${1:-}" ;;
  logs)             cmd_logs "${1:-}" ;;
  migrate)          cmd_migrate ;;
  createsuperuser)  cmd_createsuperuser ;;
  shell)            cmd_shell ;;
  status)           cmd_status ;;
  reset-db)         cmd_reset_db ;;
  help|--help|-h)   usage ;;
  *)                err "Unknown command: $COMMAND"; usage; exit 1 ;;
esac
