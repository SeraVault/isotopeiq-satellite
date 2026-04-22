# ─────────────────────────────────────────────────────────────────────────────
# IsotopeIQ Satellite — Combined Python image
#
# Stage 1  (frontend-builder): compiles the Vue 3 SPA with Vite.
# Stage 2  (python):           Django / Gunicorn / Celery image.
#
# The built Vue dist is embedded at /app/frontend/dist so that
# `python manage.py collectstatic` publishes its assets to the shared
# staticfiles volume, which nginx serves directly.
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: Build Vue frontend ───────────────────────────────────────────────
FROM node:22-alpine AS frontend-builder

WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ── Stage 2: Python / Django / Celery ────────────────────────────────────────
FROM python:3.12-slim

# System deps for psycopg2, python-ldap, pywinrm, djangosaml2/xmlsec1
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq-dev \
        libldap2-dev \
        libsasl2-dev \
        libssl-dev \
        xmlsec1 \
        libxmlsec1-openssl \
        gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

# Embed the pre-built Vue SPA so collectstatic publishes it to the
# staticfiles volume at startup.  nginx then serves the SPA directly
# from that volume without needing a separate frontend container.
COPY --from=frontend-builder /frontend/dist ./frontend/dist

EXPOSE 8000
