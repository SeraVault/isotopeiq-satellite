# IsotopeIQ Satellite — Developer Guide

This guide covers setting up a local development environment, the project layout,
and day-to-day development workflows.

---

## 1. Prerequisites

### System packages (Ubuntu / Debian)

```bash
sudo apt install \
    redis-server \
    postgresql postgresql-client \
    libldap2-dev libsasl2-dev libssl-dev libpq-dev \
    python3.12 python3.12-venv \
    nodejs npm
```

> **RHEL / CentOS / Fedora:** replace `apt install` with `dnf install` and the package
> names with their RPM equivalents (e.g. `openldap-devel`, `cyrus-sasl-devel`,
> `postgresql-devel`). The CA certificate directory is `/etc/pki/tls/certs` instead of
> `/etc/ssl/certs`.

Ensure the services are running:

```bash
sudo systemctl enable --now redis-server postgresql
```

### Node dependencies (frontend)

```bash
cd frontend
npm install
```

---

## 2. Python virtual environment

Create and activate a virtual environment at the repo root (the VS Code launch configs
expect it at `.venv/`):

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt
```

---

## 3. Environment file

Copy the example file and edit it for local development:

```bash
cp .env.example .env
```

Key values to change from their defaults:

| Variable | Dev value | Note |
|---|---|---|
| `SECRET_KEY` | any long random string | Required |
| `FIELD_ENCRYPTION_KEY` | generate below | Required |
| `DB_HOST` | `localhost` | Default in `.env.example` is `db` (Docker service name) |
| `DB_PASSWORD` | your local Postgres password | |
| `REDIS_URL` | `redis://localhost:6379/0` | Default in `.env.example` points to Docker |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173` | Vite dev server origin |
| `VITE_API_URL` | `http://localhost:8000` | Used by the Vite proxy |

Generate the encryption key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

The settings module for local development is `config.settings.development`, which
extends `base` with `DEBUG = True` and console logging at `DEBUG` level.
Set `DJANGO_SETTINGS_MODULE` in your shell or `.env` if you are not using the VS Code
launch config (which sets it automatically):

```bash
export DJANGO_SETTINGS_MODULE=config.settings.development
```

---

## 4. Database setup

Create the database and user in PostgreSQL:

```bash
sudo -u postgres psql <<'SQL'
CREATE USER isotopeiq WITH PASSWORD 'changeme';
CREATE DATABASE isotopeiq OWNER isotopeiq;
SQL
```

Run Django migrations:

```bash
cd backend
python manage.py migrate
python manage.py ensure_admin   # creates the default admin account
```

---

## 5. Running the development stack

### Option A — VS Code (recommended)

Three launch configurations are available in the **Run and Debug** panel:

| Configuration | What it starts |
|---|---|
| **Django: Local** | Celery Worker + Beat (via pre-launch task), then Django `runserver` with the debugpy debugger attached |
| **Vue: Frontend (Vite)** | Vite dev server on port 5173 |
| **Full Stack: Django + Vue** | Both of the above together (compound) |

All services are stopped automatically when you stop the debugger (`Stop All` post-debug
task kills Celery and Vite).

### Option B — manual terminals

```bash
# Terminal 1 — Celery worker
source .venv/bin/activate
cd backend
celery -A config worker -l info

# Terminal 2 — Celery beat
source .venv/bin/activate
cd backend
celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler

# Terminal 3 — Django
source .venv/bin/activate
cd backend
DJANGO_SETTINGS_MODULE=config.settings.development python manage.py runserver 0.0.0.0:8000

# Terminal 4 — Vue / Vite
cd frontend
npm run dev -- --host
```

Access the app at `http://localhost:5173`. The Vite dev server proxies `/api` and `/ws`
requests to Django on port 8000.

---

## 6. Project structure

```
backend/
  apps/
    audit/          Audit log entries
    baselines/      Canonical JSON baselines per device
    devices/        Device inventory
    drift/          Drift detection and diff storage
    jobs/           Script execution jobs
    notifications/  SystemSettings (syslog, email, FTP, LDAP config)
    policies/       Collection / drift-alert policies
    retention/      Data retention pruning
    scripts/        Script / Bundle management
    users/          User management
  config/
    settings/
      base.py       Shared settings (loaded by all environments)
      development.py  Dev overrides (DEBUG=True, console logging)
      production.py   Production overrides
  core/
    auth/
      ldap.py       Database-driven LDAP authentication backend
frontend/
  src/
    views/          Page-level Vue components
    components/     Shared UI components
    stores/         Pinia state stores
    router/         Vue Router configuration
```

---

## 7. LDAP development notes

LDAP authentication is handled by `core/auth/ldap.py`. It reads all configuration from
`SystemSettings` at authenticate-time (no restart needed when settings change via the UI).

When `LDAP_START_TLS=True` or `ldaps://` is used, the backend must be able to verify the
LDAP server's certificate. In development, ensure your system trust store includes the
relevant CA:

```bash
# Debian / Ubuntu
sudo cp /path/to/your-ca.crt /usr/local/share/ca-certificates/
sudo update-ca-certificates

# RHEL / CentOS / Fedora
sudo cp /path/to/your-ca.crt /etc/pki/ca-trust/source/anchors/
sudo update-ca-trust
```

In the Docker deployment, the host's certificate directory is bind-mounted read-only
into the backend and Celery containers at `/etc/ssl/certs`. Override the path via
`LDAP_CA_CERTS_DIR` in `.env.docker` if your host stores CAs elsewhere
(e.g. `/etc/pki/tls/certs` on RHEL).

---

## 8. Docker-based development

If you prefer to run the full stack in Docker instead of installing services locally:

```bash
cp .env.example .env.docker
# Edit .env.docker — values can stay at their Docker defaults (DB_HOST=db, etc.)

docker compose up --build
```

The frontend is embedded in the backend image at build time (Vite output copied into
`/app/frontend/dist`). For live frontend iteration, run only the backend services in
Docker and the Vite dev server locally:

```bash
docker compose up db redis backend celery_worker celery_beat
cd frontend && npm run dev -- --host
```

---

## 9. Useful commands

```bash
# Create a new migration after model changes
python manage.py makemigrations

# Open the Django shell
python manage.py shell

# Run the full test suite
python manage.py test

# Collect static files (not needed in dev — Vite serves them directly)
python manage.py collectstatic --noinput
```
