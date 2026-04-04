#!/usr/bin/env bash
# vm.sh — Helper for managing the IsotopeIQ Satellite VM at 192.168.122.42
#
# Usage:
#   ./vm.sh <command> [args]
#
# Commands:
#   ssh                   Open an interactive SSH session
#   migrate               Run Django database migrations (fixes root-owned dirs first)
#   restart [service]     Restart services (default: all)
#                         Services: backend, worker, beat, frontend, all
#   logs [service]        Follow logs (default: backend)
#   status                Show status of all isotopeiq services
#   deploy                Push host code to VM, run migrations, restart all services
#   fix-perms             Fix root-owned migrations dirs (host + VM)
#   manage <args>         Run arbitrary manage.py command on the VM
#   help                  Show this message

set -euo pipefail

VM=192.168.122.42
VM_USER=dguedry
VM_VENV=/home/dguedry/isotopeiq-satellite/.venv
VM_ROOT=/srv/isotopeiq-satellite
VM_BACKEND=$VM_ROOT/backend
MIGRATIONS_DIR=$VM_BACKEND/apps/devices/migrations
HOST_MIGRATIONS_DIR="$(cd "$(dirname "$0")" && pwd)/backend/apps/devices/migrations"

SERVICES=(isotopeiq-backend isotopeiq-worker isotopeiq-beat isotopeiq-frontend)

# ── Helpers ───────────────────────────────────────────────────────────────────

log()  { printf '\033[1;34m[vm]\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m[ OK ]\033[0m %s\n' "$*"; }
err()  { printf '\033[1;31m[ERR ]\033[0m %s\n' "$*" >&2; }
die()  { err "$*"; exit 1; }

vm_ssh() { ssh "$VM_USER@$VM" "$@"; }

vm_sudo() {
    # Run a sudo command on the VM, prompting for password once.
    ssh -t "$VM_USER@$VM" "sudo $*"
}

vm_manage() {
    vm_ssh "cd $VM_BACKEND && $VM_VENV/bin/python manage.py $*"
}

resolve_service() {
    case "${1:-all}" in
        backend)  echo isotopeiq-backend ;;
        worker)   echo isotopeiq-worker ;;
        beat)     echo isotopeiq-beat ;;
        frontend) echo isotopeiq-frontend ;;
        all)      echo "${SERVICES[*]}" ;;
        *)        die "Unknown service '$1'. Use: backend, worker, beat, frontend, all" ;;
    esac
}

# ── Commands ──────────────────────────────────────────────────────────────────

cmd_ssh() {
    exec ssh "$VM_USER@$VM"
}

cmd_fix_perms() {
    log "Fixing root-owned migrations dir on host..."
    sudo chown -R "$USER:$USER" "$HOST_MIGRATIONS_DIR"
    ok "Host migrations dir ownership fixed."

    log "Fixing root-owned migrations dir on VM..."
    vm_sudo "chown -R $VM_USER:$VM_USER $MIGRATIONS_DIR"
    ok "VM migrations dir ownership fixed."
}

cmd_migrate() {
    log "Checking migrations dir permissions..."
    # Fix host-side if needed
    if [ ! -w "$HOST_MIGRATIONS_DIR" ]; then
        log "Host migrations dir not writable — fixing..."
        sudo chown -R "$USER:$USER" "$HOST_MIGRATIONS_DIR"
        ok "Host migrations dir ownership fixed."
    fi
    # Fix VM-side if needed
    vm_ssh "[ -w $MIGRATIONS_DIR ] || echo needs-fix" | grep -q needs-fix && {
        log "VM migrations dir not writable — fixing..."
        vm_sudo "chown -R $VM_USER:$VM_USER $MIGRATIONS_DIR"
        ok "VM migrations dir ownership fixed."
    } || true

    log "Running makemigrations on VM..."
    vm_manage "makemigrations --noinput" || true

    log "Running migrate on VM..."
    vm_manage "migrate --noinput"
    ok "Migrations complete."
}

cmd_restart() {
    local svc="${1:-all}"
    local units
    read -ra units <<< "$(resolve_service "$svc")"
    log "Restarting: ${units[*]}"
    vm_sudo "systemctl restart ${units[*]}"
    ok "Restarted."
    sleep 2
    vm_ssh "systemctl is-active ${units[*]} 2>&1 || true"
}

cmd_logs() {
    local svc="${1:-backend}"
    local unit
    unit="$(resolve_service "$svc")"
    log "Following logs for $unit (Ctrl-C to stop)..."
    ssh -t "$VM_USER@$VM" "journalctl -u $unit -f --no-hostname -n 50"
}

cmd_status() {
    vm_ssh "systemctl status ${SERVICES[*]} --no-pager 2>&1 || true"
}

cmd_deploy() {
    log "Deploy: migrate → restart all"
    cmd_migrate
    cmd_restart all
    ok "Deploy complete."
}

cmd_manage() {
    vm_manage "$@"
}

# ── Entrypoint ────────────────────────────────────────────────────────────────

usage() {
    sed -n '/^# Usage:/,/^[^#]/p' "$0" | grep '^#' | sed 's/^# \{0,2\}//'
}

COMMAND="${1:-help}"
shift || true

case "$COMMAND" in
    ssh)          cmd_ssh ;;
    migrate)      cmd_migrate ;;
    restart)      cmd_restart "${1:-all}" ;;
    logs)         cmd_logs "${1:-backend}" ;;
    status)       cmd_status ;;
    deploy)       cmd_deploy ;;
    fix-perms)    cmd_fix_perms ;;
    manage)       cmd_manage "$@" ;;
    help|--help)  usage ;;
    *)            err "Unknown command: $COMMAND"; usage; exit 1 ;;
esac
