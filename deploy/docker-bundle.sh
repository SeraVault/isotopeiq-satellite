#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# IsotopeIQ Satellite — Docker Bundle Builder
# Run from the project root on your dev machine.
#
# Builds all Docker images, tags them under the isotopeiq-satellite/ namespace,
# saves them to a single compressed archive, and packages everything needed for
# a server-side deployment that requires no build tools or source code.
#
# Produces:  isotopeiq-satellite-docker-<date>.tar.gz
#
# The bundle contains:
#   images.tar.gz          — all pre-built Docker images
#   docker-compose.yml     — compose file that references images by name
#   .env.docker.example    — environment template
#   deploy.sh              — deployment script (load images + start stack)
#   agents/                — pre-built collector executables and installers
#
# Usage:
#   bash deploy/docker-bundle.sh
#   scp isotopeiq-satellite-docker-*.tar.gz user@server:~
#
# Then on the server:
#   tar -xzf isotopeiq-satellite-docker-*.tar.gz
#   cd isotopeiq-satellite-docker-*
#   cp .env.docker.example .env.docker
#   nano .env.docker       # fill in secrets
#   bash deploy.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATE="$(date +%Y%m%d)"
BUNDLE_NAME="isotopeiq-satellite-docker-${DATE}"
BUNDLE_DIR="/tmp/${BUNDLE_NAME}"
ARCHIVE="${ROOT}/${BUNDLE_NAME}.tar.gz"

log() { echo -e "\033[1;34m[docker-bundle]\033[0m $*"; }
ok()  { echo -e "\033[1;32m[  OK  ]\033[0m $*"; }

cd "$ROOT"

# ── 1. Build images ───────────────────────────────────────────────────────────
log "Building Docker images…"
docker compose --file docker-compose.yml --env-file .env.docker build
ok "Images built."

# ── 2. Tag images under the isotopeiq-satellite/ namespace ───────────────────
log "Tagging images…"
docker tag isotopeiq-satellite-2-backend isotopeiq-satellite/backend:latest
docker tag isotopeiq-satellite-2-nginx   isotopeiq-satellite/nginx:latest
ok "Images tagged."

# ── 3. Save images ────────────────────────────────────────────────────────────
log "Saving images to archive (this may take a moment)…"
mkdir -p "$BUNDLE_DIR"
docker save \
    isotopeiq-satellite/backend:latest \
    isotopeiq-satellite/nginx:latest \
    postgres:16-alpine \
    redis:7-alpine \
    | gzip > "${BUNDLE_DIR}/images.tar.gz"
ok "Images saved."

# ── 4. Assemble bundle ────────────────────────────────────────────────────────
log "Assembling bundle…"
cp "$ROOT/docker-compose.images.yml"    "${BUNDLE_DIR}/docker-compose.yml"
cp "$ROOT/deploy/docker-deploy.sh"      "${BUNDLE_DIR}/deploy.sh"
cp "$ROOT/.env.docker.example"          "${BUNDLE_DIR}/.env.docker.example"
chmod +x "${BUNDLE_DIR}/deploy.sh"

# Copy agent executables and installers
cp -r "$ROOT/agents" "${BUNDLE_DIR}/agents"
ok "Agents copied."

# ── 5. Create archive ─────────────────────────────────────────────────────────
log "Creating bundle archive…"
tar -czf "$ARCHIVE" -C /tmp "$BUNDLE_NAME"
rm -rf "$BUNDLE_DIR"

SIZE=$(du -sh "$ARCHIVE" | cut -f1)
ok "Bundle created: $(basename "$ARCHIVE") (${SIZE})"
echo
echo "Deploy to server:"
echo "  scp $(basename "$ARCHIVE") user@YOUR_SERVER:~"
echo "  ssh user@YOUR_SERVER"
echo "  tar -xzf $(basename "$ARCHIVE")"
echo "  cd $BUNDLE_NAME"
echo "  cp .env.docker.example .env.docker"
echo "  nano .env.docker       # fill in secrets"
echo "  bash deploy.sh"
