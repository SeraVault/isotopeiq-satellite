#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# IsotopeIQ Satellite — Bundle Builder
# Run from the project root on your dev machine.
# Produces:  isotopeiq-satellite-<date>.tar.gz
#
# Usage:
#   bash deploy/bundle.sh
#   scp isotopeiq-satellite-*.tar.gz user@server:~
#
# Then on the server:
#   tar -xzf isotopeiq-satellite-*.tar.gz
#   cd isotopeiq-satellite
#   sudo bash deploy/server-setup.sh          # first time only
#   cp deploy/.env.production /etc/isotopeiq/.env
#   # edit /etc/isotopeiq/.env
#   sudo bash deploy/install.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATE="$(date +%Y%m%d)"
BUNDLE_NAME="isotopeiq-satellite-${DATE}"
ARCHIVE="${ROOT}/${BUNDLE_NAME}.tar.gz"

log() { echo -e "\033[1;34m[bundle]\033[0m $*"; }
ok()  { echo -e "\033[1;32m[  OK  ]\033[0m $*"; }

cd "$ROOT"

log "Creating bundle: $ARCHIVE"

# Write to /tmp first so tar doesn't see the archive being created inside the source tree
ARCHIVE_TMP="/tmp/${BUNDLE_NAME}.tar.gz"
tar -czf "$ARCHIVE_TMP" \
    --transform "s|^\.|${BUNDLE_NAME}|" \
    --exclude='./.git' \
    --exclude='./.venv' \
    --exclude='./venv' \
    --exclude='./frontend/node_modules' \
    --exclude='./frontend/dist' \
    --exclude='./backend/staticfiles' \
    --exclude='./backend/celerybeat-schedule' \
    --exclude='./backend/**/__pycache__' \
    --exclude='./**/*.pyc' \
    --exclude='./**/*.pyo' \
    --exclude='./.env' \
    --exclude='./isotopeiq-satellite-*.tar.gz' \
    .
mv "$ARCHIVE_TMP" "$ARCHIVE"

SIZE=$(du -sh "$ARCHIVE" | cut -f1)
ok "Bundle created: $(basename "$ARCHIVE") (${SIZE})"
echo
echo "Deploy to server:"
echo "  scp $(basename "$ARCHIVE") user@YOUR_SERVER:~"
echo "  ssh user@YOUR_SERVER"
echo "  tar -xzf $(basename "$ARCHIVE")"
echo "  cd $BUNDLE_NAME"
echo "  sudo bash deploy/server-setup.sh    # first time only"
echo "  sudo cp deploy/.env.production /etc/isotopeiq/.env"
echo "  sudo nano /etc/isotopeiq/.env       # fill in secrets"
echo "  sudo bash deploy/install.sh"
