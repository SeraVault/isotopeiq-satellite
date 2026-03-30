# IsotopeIQ Satellite — Administrator Guide

## Table of Contents

1. [Overview](#1-overview)
2. [Prerequisites](#2-prerequisites)
3. [Installation](#3-installation)
4. [Environment Configuration](#4-environment-configuration)
5. [Starting and Stopping Services](#5-starting-and-stopping-services)
6. [Authentication Configuration](#6-authentication-configuration)
   - [Local Authentication](#61-local-authentication)
   - [LDAP](#62-ldap)
   - [SAML 2.0](#63-saml-20)
7. [Notification Configuration (Syslog)](#7-notification-configuration-syslog)
8. [Service Management Reference](#8-service-management-reference)
9. [Data Retention](#9-data-retention)
10. [Upgrading](#10-upgrading)
11. [Backup and Restore](#11-backup-and-restore)
12. [Troubleshooting](#12-troubleshooting)
13. [Security Hardening](#13-security-hardening)
14. [Architecture Reference](#14-architecture-reference)

---

## 1. Overview

IsotopeIQ Satellite is a configuration collection, baseline, and drift-detection platform. It connects to managed devices (Linux, Windows, macOS, network devices, SNMP systems), collects their configuration state, normalizes the output into a canonical JSON structure, stores baselines, and continuously alerts when device configuration drifts from those baselines.

**Core workflow:**

```
Devices → Credentials → Scripts → Policies → Jobs → Baselines → Drift Alerts
```

**Service stack:**

| Container | Role | Default Port |
|---|---|---|
| `db` | PostgreSQL 16 | 5432 (internal) |
| `redis` | Celery broker / cache | 6379 (internal) |
| `backend` | Django REST API | 8000 |
| `celery_worker` | Job execution | — |
| `celery_beat` | Job scheduler | — |
| `frontend` | Vue 3 / Vite UI | 5173 |

---

## 2. Prerequisites

- **Docker** 24+ with the Compose plugin (`docker compose` — not legacy `docker-compose`)
- **Git** (to clone the repository)
- **Python 3** on the host (only required to generate the `FIELD_ENCRYPTION_KEY`)
- Network access from the Satellite host to all managed devices on their management ports (SSH 22, WinRM 5985/5986, SNMP 161, etc.)

Verify Docker is ready:

```bash
docker --version
docker compose version
```

---

## 3. Installation

### 3.1 Clone the Repository

```bash
git clone <repository-url> isotopeiq-satellite
cd isotopeiq-satellite
```

### 3.2 Create the Environment File

```bash
cp .env.example .env
```

Edit `.env` and fill in all required values before proceeding. See [Section 4](#4-environment-configuration) for details.

### 3.3 Build and Start

```bash
./deploy.sh up
```

This command:
1. Builds all Docker images
2. Starts all containers in the background
3. Waits for PostgreSQL to become ready
4. Runs all Django database migrations automatically

### 3.4 Create the First Admin User

```bash
./deploy.sh createsuperuser
```

Follow the prompts to set a username, email address, and password. This account has full administrative access to the UI and API.

### 3.5 Access the Application

| Interface | URL |
|---|---|
| Web UI | `http://<host>:5173` |
| REST API | `http://<host>:8000/api/v1/` |
| API Auth | `http://<host>:8000/api/v1/auth/token/` |

---

## 4. Environment Configuration

All runtime configuration is supplied via the `.env` file. **Never commit this file to version control.**

### 4.1 Required Settings

| Variable | Description | Example |
|---|---|---|
| `SECRET_KEY` | Django secret key — must be long and random | See below |
| `FIELD_ENCRYPTION_KEY` | Fernet key for encrypting stored credentials | See below |
| `DB_PASSWORD` | PostgreSQL password | `s3cur3p@ssw0rd` |
| `ALLOWED_HOSTS` | Comma-separated list of allowed hostnames/IPs | `satellite.corp.example.com,10.0.1.50` |

**Generate `SECRET_KEY`:**

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```

**Generate `FIELD_ENCRYPTION_KEY`:**

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

> **Important:** If `FIELD_ENCRYPTION_KEY` changes after credentials have been stored, all encrypted fields (passwords, SSH keys, tokens) become unreadable. Back up the key and treat it with the same care as a certificate private key.

### 4.2 Database Settings

```ini
DB_NAME=isotopeiq
DB_USER=isotopeiq
DB_PASSWORD=<strong-password>
DB_HOST=db          # container name; do not change unless using an external DB
DB_PORT=5432
```

### 4.3 Redis / Celery Broker

```ini
REDIS_URL=redis://redis:6379/0
```

Change the host from `redis` only if pointing to an external Redis instance.

### 4.4 Satellite URL

```ini
SATELLITE_URL=http://localhost:8000
```

Set this to the URL that managed devices can reach when using Push mode. For external devices this must be a publicly routable address or hostname.

### 4.5 Syslog Notifications

```ini
SYSLOG_HOST=your-siem.corp.example.com
SYSLOG_PORT=514
SYSLOG_FACILITY=local0
```

See [Section 8](#8-notification-configuration-syslog) for details.

### 4.6 LDAP (Optional)

See [Section 7.2](#72-ldap).

### 4.7 SAML 2.0 (Optional)

See [Section 7.3](#73-saml-20).

---

## 5. Starting and Stopping Services

All lifecycle operations are handled through `deploy.sh`.

```
Usage: ./deploy.sh [COMMAND] [SERVICE]
```

| Command | Description |
|---|---|
| `./deploy.sh up` | Build images, start all services, run migrations |
| `./deploy.sh down` | Stop and remove containers (data volumes preserved) |
| `./deploy.sh restart` | Full stop + start |
| `./deploy.sh restart <service>` | Restart a single service |
| `./deploy.sh build` | Rebuild all images without starting |
| `./deploy.sh logs` | Follow logs for all services |
| `./deploy.sh logs <service>` | Follow logs for one service |
| `./deploy.sh status` | Show running container status |
| `./deploy.sh migrate` | Run Django migrations manually |
| `./deploy.sh createsuperuser` | Create a Django admin user |
| `./deploy.sh shell` | Open a bash shell in the backend container |
| `./deploy.sh reset-db` | **DESTRUCTIVE:** destroy and recreate the database volume |

**Valid service names:** `db`, `redis`, `backend`, `frontend`, `worker`, `beat`

**Examples:**

```bash
# Restart only the Celery worker after a code change
./deploy.sh restart worker

# Tail backend logs
./deploy.sh logs backend

# Check all container health
./deploy.sh status
```

---

## 6. Authentication Configuration

### 6.1 Local Authentication

Local authentication is enabled by default. Create accounts via the `createsuperuser` command or through the Django admin interface at `http://<host>:8000/admin/`.

JWT tokens are issued at `/api/v1/auth/token/` and refreshed at `/api/v1/auth/token/refresh/`. The web UI handles token management automatically.

### 6.2 LDAP

LDAP authentication is configured entirely through `.env`. No code changes are required.

```ini
# LDAP server
LDAP_SERVER_URI=ldap://dc01.corp.example.com:389
LDAP_BIND_DN=cn=satellite-readonly,ou=service-accounts,dc=corp,dc=example,dc=com
LDAP_BIND_PASSWORD=<service-account-password>
LDAP_START_TLS=False           # Set True to use STARTTLS (recommended for production)

# User lookup
LDAP_USER_SEARCH_BASE=ou=users,dc=corp,dc=example,dc=com
LDAP_USER_SEARCH_FILTER=(sAMAccountName=%(user)s)   # Active Directory example
# LDAP_USER_SEARCH_FILTER=(uid=%(user)s)            # OpenLDAP example

# Group membership (for role assignment)
LDAP_GROUP_SEARCH_BASE=ou=groups,dc=corp,dc=example,dc=com
LDAP_SUPERUSER_GROUP=cn=satellite-admins,ou=groups,dc=corp,dc=example,dc=com
LDAP_STAFF_GROUP=cn=satellite-users,ou=groups,dc=corp,dc=example,dc=com

# Attribute mapping
LDAP_ATTR_FIRST_NAME=givenName
LDAP_ATTR_LAST_NAME=sn
LDAP_ATTR_EMAIL=mail
```

**Role mapping:**

| LDAP Group | Django Role | Access Level |
|---|---|---|
| `LDAP_SUPERUSER_GROUP` | Superuser | Full admin access |
| `LDAP_STAFF_GROUP` | Staff | UI access, no admin panel |

After updating `.env`, restart the backend:

```bash
./deploy.sh restart backend
```

### 6.3 SAML 2.0

SAML 2.0 configuration also lives entirely in `.env`.

```ini
# Service Provider (Satellite) identity
SAML_SP_ENTITY_ID=https://satellite.corp.example.com/saml2/metadata/
SAML_ACS_URL=https://satellite.corp.example.com/saml2/acs/
SAML_SLS_URL=https://satellite.corp.example.com/saml2/ls/

# Identity Provider metadata — use URL or local file (not both)
SAML_IDP_METADATA_URL=https://idp.corp.example.com/metadata
# SAML_IDP_METADATA_FILE=/path/to/idp-metadata.xml

# SP key and certificate (optional; required for signed requests)
SAML_SP_KEY_FILE=/run/secrets/saml_sp.key
SAML_SP_CERT_FILE=/run/secrets/saml_sp.crt
```

**SP metadata** for registering with the IdP is available at:

```
https://satellite.corp.example.com/saml2/metadata/
```

Register this URL (or download and upload the XML) in your IdP's application configuration.

After updating `.env`, restart the backend:

```bash
./deploy.sh restart backend
```

---

## 7. Notification Configuration (Syslog)

IsotopeIQ Satellite sends drift detection alerts via syslog. Configure the target in `.env`:

```ini
SYSLOG_HOST=siem.corp.example.com
SYSLOG_PORT=514
SYSLOG_FACILITY=local0
```

Drift events are sent when a collection run produces output that differs from the stored baseline. The syslog message includes the device name, policy, and a summary of changed fields.

To verify notifications are reaching your SIEM, trigger a manual collection on a device and modify a monitored value (e.g., add a test user) before re-running. The resulting drift event will generate a syslog message.

After changing syslog settings, restart the backend and workers:

```bash
./deploy.sh restart backend
./deploy.sh restart worker
```

---

## 8. Service Management Reference

### 8.1 Service Descriptions

| Service | Container | Notes |
|---|---|---|
| `db` | `iq-db` | PostgreSQL 16; data stored in Docker volume `postgres_data` |
| `redis` | `iq-redis` | Redis 7; no persistent storage by default |
| `backend` | `iq-backend` | Django app + Gunicorn on port 8000; debugpy on 5678 |
| `worker` | `iq-worker` | Celery worker; runs collection jobs; concurrency=4 |
| `beat` | `iq-beat` | Celery beat scheduler; triggers policy schedules |
| `frontend` | `iq-frontend` | Vite dev server on port 5173 |

### 8.2 Viewing Logs

```bash
# All services
./deploy.sh logs

# Single service
./deploy.sh logs backend
./deploy.sh logs worker
./deploy.sh logs beat
```

### 8.3 Running Django Management Commands

```bash
# Open a shell inside the backend container
./deploy.sh shell

# Or run a command directly
docker compose exec backend python manage.py <command>
```

Common management commands:

```bash
# Apply new migrations after an upgrade
docker compose exec backend python manage.py migrate

# Check for issues
docker compose exec backend python manage.py check

# Clear expired tokens
docker compose exec backend python manage.py flushexpiredtokens
```

### 8.4 Celery Worker Concurrency

The Celery worker defaults to 4 concurrent job slots. To change this, edit `docker-compose.yml` and update the `--concurrency` argument on the `celery_worker` service, then rebuild:

```bash
./deploy.sh restart worker
```

---

## 9. Data Retention

Retention settings control how long raw collection output, parsed JSON, job history, and logs are kept. They are stored in the database and configurable via the REST API at `/api/v1/retention/`.

| Setting | Default | Description |
|---|---|---|
| Raw data retention | 90 days | Raw text output from collection scripts |
| Parsed data retention | 365 days | Normalized canonical JSON |
| Job history retention | 90 days | Job execution records |
| Log retention | 30 days | System and audit logs |

The retention pruning job runs automatically each day at **03:00 UTC**. No manual action is required after setting the values.

---

## 10. Upgrading

1. Pull the latest code:

   ```bash
   git pull
   ```

2. Rebuild images and restart (migrations run automatically):

   ```bash
   ./deploy.sh up
   ```

   If only the backend changed and you want to avoid frontend rebuild:

   ```bash
   ./deploy.sh restart backend
   ./deploy.sh restart worker
   ./deploy.sh restart beat
   ```

3. Verify services are healthy:

   ```bash
   ./deploy.sh status
   ./deploy.sh logs backend
   ```

---

## 11. Backup and Restore

### 11.1 Database Backup

```bash
# Dump the database to a file
docker compose exec db pg_dump -U isotopeiq isotopeiq > backup-$(date +%Y%m%d).sql
```

### 11.2 Database Restore

```bash
# Stop the application services (leave db running)
docker compose stop backend celery_worker celery_beat frontend

# Restore
cat backup-20260329.sql | docker compose exec -T db psql -U isotopeiq isotopeiq

# Restart
./deploy.sh up
```

### 11.3 Backing Up the Encryption Key

Back up `.env` (especially `FIELD_ENCRYPTION_KEY`) to a secure secrets store (e.g., HashiCorp Vault, AWS Secrets Manager). Without the encryption key, all stored credentials in the database are unreadable.

---

## 12. Troubleshooting

### Services fail to start

```bash
./deploy.sh logs
```

Check for missing `.env` values. The most common causes are:
- `FIELD_ENCRYPTION_KEY` is empty
- `SECRET_KEY` is set to the default placeholder
- `DB_PASSWORD` mismatch between the `db` and `backend` containers

### PostgreSQL not ready

If the backend starts before PostgreSQL is ready, the `deploy.sh up` command retries automatically up to 20 times (1 second apart). If it still fails:

```bash
./deploy.sh logs db
```

Look for disk space or permission errors in the volume.

### Migrations fail

```bash
./deploy.sh logs backend
./deploy.sh migrate
```

If there are conflicting migrations from a failed upgrade, open a shell and inspect:

```bash
./deploy.sh shell
python manage.py showmigrations
```

### Collection jobs fail

1. Check worker logs for the error message:

   ```bash
   ./deploy.sh logs worker
   ```

2. Common causes:
   - Credential incorrect — verify the username/password or key is correct for the target device
   - Network path blocked between Satellite and device — confirm the relevant port (22, 5985/5986, 161) is reachable
   - Collection script syntax error — test the script manually against a device via the API or a direct SSH session
   - Parser raised an exception — the full traceback appears in the worker logs

### Push mode devices not registering

- Confirm `SATELLITE_URL` in `.env` is reachable from the device
- Verify the device's push token matches the token configured on the Device record
- Check backend logs for incoming POST requests to `/api/push/`

### LDAP login fails

```bash
./deploy.sh logs backend
```

Look for `django_auth_ldap` log entries. Common issues:
- Incorrect `LDAP_USER_SEARCH_FILTER` for your directory schema
- Service account (`LDAP_BIND_DN`) lacks search permission
- `LDAP_START_TLS=True` but server certificate is not trusted — mount the CA certificate into the container

### SAML login fails

Check that:
- `SAML_SP_ENTITY_ID`, `SAML_ACS_URL`, and `SAML_SLS_URL` match exactly what is registered in the IdP
- The IdP metadata URL is reachable from the backend container
- System clocks on both Satellite and IdP are synchronized (SAML assertions are time-sensitive)

---

## 13. Security Hardening

### Rotate the Encryption Key

If `FIELD_ENCRYPTION_KEY` is ever exposed:

1. Decrypt all credentials before rotation (export or document them)
2. Generate a new key: `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
3. Update `.env`
4. Re-enter all credentials in the UI (they will be re-encrypted with the new key)

### Network Exposure

- The frontend (5173) and backend (8000) ports should not be exposed directly to untrusted networks. Place a TLS-terminating reverse proxy (nginx, Caddy, HAProxy) in front of both.
- The database (5432) and Redis (6379) ports are not exposed outside Docker by default — do not change this.
- For the push API endpoint (`/api/push/`), ensure the device-to-Satellite path uses HTTPS.

### Credential Scope

- Create a dedicated read-only LDAP service account for `LDAP_BIND_DN`. Do not use a domain admin account.
- Use SSH key authentication for managed devices wherever possible rather than passwords.
- Assign devices to credentials with the minimum required privilege (e.g., a user with only `sudo /usr/bin/cat` rather than full sudo).

### Audit Log Review

The audit log is queryable via the REST API at `/api/v1/audit-logs/`. Review it regularly for:
- Unexpected logins (source IPs, off-hours access)
- Credential or device deletions
- Script modifications (which could alter what data is collected)

### Updates

Keep the platform updated and monitor for security advisories in the dependencies (Django, Celery, paramiko, pywinrm, djangosaml2).

---

## 14. Architecture Reference

### Service Interaction

```
Browser
  │
  ▼
frontend (Vite / Vue 3)  :5173
  │   REST + WebSocket
  ▼
backend (Django / DRF)   :8000
  ├── PostgreSQL (db)     :5432  — persistent data store
  ├── Redis (redis)       :6379  — Celery broker + result backend
  ├── celery_worker       — executes collection jobs
  └── celery_beat         — triggers scheduled policies
```

### Collection Data Flow

```
Policy schedule fires
  → celery_beat enqueues task
    → celery_worker picks up task
      → connects to device (SSH / WinRM / HTTPS / Push)
        → runs collection script on device
          → raw output returned to worker
            → parser script runs on worker (stdin → stdout)
              → canonical JSON validated against schema
                → stored in Job record
                  → compared against stored Baseline
                    → DriftEvent created if diff detected
                      → syslog alert sent
```

### Key Directories

| Path | Contents |
|---|---|
| `backend/apps/` | Django application modules (devices, jobs, drift, etc.) |
| `backend/core/` | Collection engine, parser engine, canonical schema |
| `backend/config/settings/` | Django settings (base, development, production) |
| `frontend/src/` | Vue 3 application source |
| `agents/` | Pre-built collector binaries and source (Linux, Windows, macOS) |
| `examples/` | Example collector and parser scripts for 8+ device types |

### Agent Binaries

Pre-compiled agents are available for push-mode or deployment scenarios:

| Binary | Platform |
|---|---|
| `agents/linux_collector_amd64` | Linux x86-64 (glibc 2.17+, RHEL 7+) |
| `agents/linux_collector_i686` | Linux x86 32-bit |
| `agents/macos_collector` | macOS (recent versions) |
| `agents/windows_collector.exe` | Windows 10+ |

Agents can be downloaded by managed devices directly from the Satellite at:

```
GET /api/v1/agents/download/<filename>
```

Python source equivalents are available in `agents/*.py` for environments where running a compiled binary is not permitted.
