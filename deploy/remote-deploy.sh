#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# IsotopeIQ Satellite — Remote Deploy
# Copies the docker bundle to a remote server over SSH and runs deploy.sh.
#
# Usage:
#   bash deploy/remote-deploy.sh [OPTIONS] user@host
#
# Options:
#   -b, --bundle PATH    Path to the .tar.gz bundle (default: newest in dist/)
#   -p, --port PORT      SSH port (default: 22)
#   -i, --identity FILE  SSH private key file
#   -r, --remote-dir DIR Remote directory to deploy into (default: ~/isotopeiq)
#   -h, --help           Show this help
#
# Example:
#   bash deploy/remote-deploy.sh admin@192.168.1.50
#   bash deploy/remote-deploy.sh -i ~/.ssh/mykey -p 2222 admin@192.168.1.50
#   bash deploy/remote-deploy.sh -b dist/isotopeiq-satellite-docker-20260421.tar.gz admin@192.168.1.50
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

log()  { echo -e "\033[1;34m[remote-deploy]\033[0m $*"; }
ok()   { echo -e "\033[1;32m[  OK  ]\033[0m $*"; }
die()  { echo -e "\033[1;31m[ ERR  ]\033[0m $*" >&2; exit 1; }

# ── Defaults ──────────────────────────────────────────────────────────────────
BUNDLE=""
SSH_PORT=22
SSH_IDENTITY=""
REMOTE_DIR="~/isotopeiq"
TARGET=""

# ── Argument parsing ──────────────────────────────────────────────────────────
usage() {
    sed -n '/^# Usage:/,/^# ──/p' "$0" | grep '^#' | sed 's/^# \{0,1\}//'
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -b|--bundle)     BUNDLE="$2";      shift 2 ;;
        -p|--port)       SSH_PORT="$2";    shift 2 ;;
        -i|--identity)   SSH_IDENTITY="$2"; shift 2 ;;
        -r|--remote-dir) REMOTE_DIR="$2";  shift 2 ;;
        -h|--help)       usage ;;
        -*)              die "Unknown option: $1" ;;
        *)               TARGET="$1";      shift ;;
    esac
done

[[ -n "$TARGET" ]] || die "No target specified. Usage: $0 [OPTIONS] user@host"

# ── Resolve bundle path ───────────────────────────────────────────────────────
if [[ -z "$BUNDLE" ]]; then
    BUNDLE=$(ls -t "${ROOT}/dist"/isotopeiq-satellite-docker-*.tar.gz 2>/dev/null | head -1)
    [[ -n "$BUNDLE" ]] || die "No bundle found in dist/. Run deploy/docker-bundle.sh first."
fi
[[ -f "$BUNDLE" ]] || die "Bundle not found: $BUNDLE"

BUNDLE_FILE="$(basename "$BUNDLE")"
BUNDLE_NAME="${BUNDLE_FILE%.tar.gz}"

# ── Build SSH / SCP argument lists ───────────────────────────────────────────
SSH_ARGS=(-p "$SSH_PORT" -o StrictHostKeyChecking=accept-new)
SCP_ARGS=(-P "$SSH_PORT" -o StrictHostKeyChecking=accept-new)
if [[ -n "$SSH_IDENTITY" ]]; then
    SSH_ARGS+=(-i "$SSH_IDENTITY")
    SCP_ARGS+=(-i "$SSH_IDENTITY")
fi

ssh_run() { ssh "${SSH_ARGS[@]}" "$TARGET" "$@"; }

# ── Preflight ─────────────────────────────────────────────────────────────────
log "Target:  $TARGET"
log "Bundle:  $BUNDLE_FILE ($(du -sh "$BUNDLE" | cut -f1))"
log "Remote:  $REMOTE_DIR"
echo

command -v scp  >/dev/null 2>&1 || die "scp not found."
command -v ssh  >/dev/null 2>&1 || die "ssh not found."

# ── 1. Create remote directory ────────────────────────────────────────────────
log "Creating remote directory…"
ssh_run "mkdir -p $REMOTE_DIR"
ok "Directory ready."

# ── 2. Copy bundle ────────────────────────────────────────────────────────────
log "Copying bundle to $TARGET:$REMOTE_DIR/ …"
scp "${SCP_ARGS[@]}" "$BUNDLE" "${TARGET}:${REMOTE_DIR}/${BUNDLE_FILE}"
ok "Upload complete."

# ── 3. Extract + deploy on remote ─────────────────────────────────────────────
log "Extracting and deploying on remote…"
ssh_run bash <<EOF
set -euo pipefail
cd $REMOTE_DIR

echo "[remote] Extracting ${BUNDLE_FILE}…"
tar -xzf "${BUNDLE_FILE}"

DEPLOY_DIR="\$(ls -td ${REMOTE_DIR}/${BUNDLE_NAME} 2>/dev/null | head -1)"
if [[ -z "\$DEPLOY_DIR" ]]; then
    echo "ERROR: Could not locate extracted bundle directory." >&2
    exit 1
fi

echo "[remote] Running deploy.sh in \$DEPLOY_DIR…"
cd "\$DEPLOY_DIR"
bash deploy.sh
EOF

ok "Deployment complete."
echo
echo "  HTTP  → http://$(ssh "${SSH_ARGS[@]}" "$TARGET" "hostname -I | awk '{print \$1}'" 2>/dev/null)"
echo "  HTTPS → https://$(ssh "${SSH_ARGS[@]}" "$TARGET" "hostname -I | awk '{print \$1}'" 2>/dev/null)"
