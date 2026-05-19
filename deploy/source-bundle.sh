#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# IsotopeIQ Satellite — Source Bundle Builder
# Run from the project root on your dev machine.
#
# Creates a clean zip of the source code, excluding runtime artifacts,
# secrets, and build caches.
#
# Produces:  isotopeiq-satellite-source-<date>.zip  (in the parent directory)
#
# Excluded:
#   .git/                  — version history
#   .venv/                 — Python virtualenv
#   frontend/node_modules/ — npm packages
#   data/                  — postgres/redis/staticfiles/tls runtime data
#   *.tar.gz               — docker bundles
#   .env / .env.docker     — secrets (examples are included)
#   __pycache__/ / *.pyc   — Python bytecode
#
# Usage:
#   bash deploy/source-bundle.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PARENT="$(dirname "$ROOT")"
DIRNAME="$(basename "$ROOT")"
DATE="$(date +%Y%m%d)"
mkdir -p "${ROOT}/dist"
ARCHIVE="${ROOT}/dist/isotopeiq-satellite-source-${DATE}.zip"

log() { echo -e "\033[1;34m[source-bundle]\033[0m $*"; }
ok()  { echo -e "\033[1;32m[  OK  ]\033[0m $*"; }

cd "$PARENT"

log "Creating source bundle…"
zip -r "$ARCHIVE" "$DIRNAME/" \
  --exclude "${DIRNAME}/.git/*" \
  --exclude "${DIRNAME}/.venv/*" \
  --exclude "${DIRNAME}/frontend/node_modules/*" \
  --exclude "${DIRNAME}/data/*" \
  --exclude "${DIRNAME}/*.tar.gz" \
  --exclude "${DIRNAME}/.env" \
  --exclude "${DIRNAME}/.env.docker" \
  --exclude "${DIRNAME}/*/__pycache__/*" \
  --exclude "${DIRNAME}/*/*/__pycache__/*" \
  --exclude "${DIRNAME}/*/*/*/__pycache__/*" \
  --exclude "${DIRNAME}/**/*.pyc"

SIZE=$(du -sh "$ARCHIVE" | cut -f1)
ok "Bundle created: $(basename "$ARCHIVE") (${SIZE})"
