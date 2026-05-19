# IsotopeIQ Satellite — Deployment Guide

Two deployment paths are available. Choose the one that fits your environment:

| Path | When to use |
|---|---|
| **Docker** | Target server has Docker installed. No build tools, Python, or Node.js required on the server. Easiest for most environments. |
| **Systemd (bare-metal)** | Target server runs Ubuntu 24.04, you want native services without Docker, or you need direct OS integration. |

---

## Docker Deployment

### How it works

All services run as Docker containers managed by Compose:

| Container | Role |
|---|---|
| `nginx` | Reverse proxy — terminates TLS, serves static files, routes traffic |
| `backend` | Django REST API (Gunicorn) |
| `celery_worker` | Executes collection and drift jobs |
| `celery_beat` | Triggers scheduled policies |
| `frontend` | Vue 3 SPA (served by nginx within the container) |
| `db` | PostgreSQL 16 |
| `redis` | Celery broker |

Traffic flow:

```
Browser → nginx :80/:443 → backend :8000  (API, admin, SAML)
                         → frontend :80   (Vue SPA)
```

HTTP on port 80 is permanently redirected to HTTPS on port 443. A self-signed TLS
certificate is auto-generated on first start if no certificate is mounted.

---

### Option A — Docker Compose (source on server)

Use this when you can clone the repository directly onto the server.

#### Prerequisites (dev machine and server)

- Docker 24+ with the Compose plugin (`docker compose`)
- `git`

#### Step 1 — Clone and configure

```bash
git clone <repository-url> isotopeiq-satellite
cd isotopeiq-satellite
cp deploy/.env.docker.example .env
```

Edit `.env` and set the required values (see [Required environment variables](#required-environment-variables)).

#### Step 2 — Build the images

```bash
./deploy.sh build
```

This builds five images:
- `isotopeiq-satellite-2-backend`
- `isotopeiq-satellite-2-frontend`
- `isotopeiq-satellite-2-nginx`
- `isotopeiq-satellite-2-celery_worker`
- `isotopeiq-satellite-2-celery_beat`

#### Step 3 — Start the stack

```bash
./deploy.sh up
```

This builds images (if not already built), starts all containers, and runs Django database migrations automatically.

#### Step 4 — Create the admin user

```bash
./deploy.sh createsuperuser
```

#### Accessing the application

| Interface | URL |
|---|---|
| Web UI | `https://<host>` |
| REST API | `https://<host>/api/v1/` |

---

### Option B — Docker Bundle (no source or build tools on server)

Use this when the target server has no internet access, no build tools, or when you
want to ship a tested, immutable artefact. All images are pre-built on your dev machine
and bundled into a single archive.

#### Prerequisites

- **Dev machine:** Docker, `git`
- **Target server:** Docker only — no Python, Node.js, git, or compilers needed

#### Step 1 — Build the bundle (dev machine)

From the project root:

```bash
bash deploy/docker-bundle.sh
```

This will:
1. Build all Docker images (`./deploy.sh build`)
2. Tag them under the `isotopeiq-satellite/` namespace
3. Save all images (including `postgres:16-alpine` and `redis:7-alpine`) to `images.tar.gz`
4. Assemble the deployment package into `isotopeiq-satellite-docker-<date>.tar.gz`

Bundle contents:

| File | Purpose |
|---|---|
| `images.tar.gz` | All pre-built Docker images |
| `docker-compose.yml` | Compose file referencing images by name — no build needed |
| `.env.example` | Environment variable template |
| `deploy.sh` | Server-side deployment script |

#### Step 2 — Transfer the bundle

```bash
scp isotopeiq-satellite-docker-*.tar.gz user@YOUR_SERVER:~
```

#### Step 3 — Deploy on the server

```bash
ssh user@YOUR_SERVER
tar -xzf isotopeiq-satellite-docker-*.tar.gz
cd isotopeiq-satellite-docker-*

cp .env.example .env
nano .env      # fill in required values — see below
bash deploy.sh
```

`deploy.sh` will:
1. Load all images from `images.tar.gz` into the local Docker daemon
2. Validate that `SECRET_KEY` is set in `.env`
3. Start the full stack with `docker compose up -d`
4. Print the server's IP address and the `createsuperuser` command

#### Step 4 — Create the admin user

```bash
docker compose --file docker-compose.yml --env-file .env \
  exec backend python manage.py createsuperuser
```

#### Subsequent updates

Re-run the bundle builder on your dev machine. Transfer and extract the new bundle, then
run `bash deploy.sh` again. The new images replace the old ones and the stack restarts.

#### deploy.sh subcommands

```bash
bash deploy.sh           # start / update (default)
bash deploy.sh stop      # stop all containers
bash deploy.sh logs      # follow logs for all services
bash deploy.sh logs backend   # follow logs for a single service
bash deploy.sh status    # show container status
```

---

### Required environment variables

Generate these values before deploying:

| Variable | How to generate |
|---|---|
| `SECRET_KEY` | `python3 -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `FIELD_ENCRYPTION_KEY` | `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `DB_PASSWORD` | Choose a strong random password |
| `ALLOWED_HOSTS` | Your server's IP or domain name (comma-separated) |
| `DOMAIN` | Hostname/IP for the nginx self-signed certificate CN/SAN |

> **Important:** Back up `FIELD_ENCRYPTION_KEY`. If it changes after credentials are stored, all encrypted device passwords, SSH keys, and API tokens become unreadable.

---

### TLS certificates

By default nginx generates a self-signed certificate on first start. The certificate is
stored in the `tls_certs` Docker volume and reused across restarts.

To use your own certificate instead, mount it in `docker-compose.yml`:

```yaml
nginx:
  volumes:
    - /path/to/server.crt:/etc/nginx/tls/server.crt:ro
    - /path/to/server.key:/etc/nginx/tls/server.key:ro
```

The mounted certificate takes precedence — the entrypoint will not overwrite it.

---

### Docker service management

```bash
# Using ./deploy.sh (source deployment)
./deploy.sh logs
./deploy.sh logs backend
./deploy.sh restart backend
./deploy.sh status

# Using docker compose directly
docker compose ps
docker compose logs -f worker
docker compose restart nginx

# Open a shell in the backend container
./deploy.sh shell
# or
docker compose exec backend bash

# Run a Django management command
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py check
```

---

### Updating (source deployment)

```bash
git pull
./deploy.sh up
```

`up` rebuilds changed images and restarts affected containers. Migrations run
automatically on backend startup.

---

## Systemd (Bare-Metal) Deployment

### Prerequisites

- Ubuntu 24.04 LTS server
- SSH access with a user that has `sudo`
- `rsync` installed on your dev machine (standard on Linux/macOS)

---

### Quick reference

```bash
# First-time deployment (includes OS setup)
SETUP=true DOMAIN=myserver.lan bash deploy/push.sh isotopeiq@192.168.x.x

# Subsequent updates
bash deploy/push.sh isotopeiq@192.168.x.x
```

---

### First-time deployment

#### 1. Run push.sh with SETUP=true

From your dev machine project root:

```bash
# Plain HTTP
SETUP=true bash deploy/push.sh isotopeiq@YOUR_SERVER

# HTTPS — self-signed certificate (no internet required)
SETUP=true DOMAIN=myserver.example.com bash deploy/push.sh isotopeiq@YOUR_SERVER

# HTTPS — Let's Encrypt (requires internet access)
SETUP=true DOMAIN=myserver.example.com LETSENCRYPT=true bash deploy/push.sh isotopeiq@YOUR_SERVER

# HTTPS — bring your own certificate
SETUP=true DOMAIN=myserver.example.com \
  TLS_CERT=/path/on/server/server.crt \
  TLS_KEY=/path/on/server/server.key \
  bash deploy/push.sh isotopeiq@YOUR_SERVER
```

`push.sh` will:
1. Rsync the source to `~/isotopeiq-deploy/` on the server
2. Run `server-setup.sh` (OS packages, PostgreSQL, Redis, Nginx, Node.js 22, system user)
3. Run `install.sh` (venv, frontend build, collectstatic, migrate, systemd, nginx)

#### 2. Configure the environment (first time only)

If `/etc/isotopeiq/.env` doesn't exist yet, `push.sh` will warn you. SSH in and create it:

```bash
ssh isotopeiq@YOUR_SERVER
sudo mkdir -p /etc/isotopeiq
sudo cp ~/isotopeiq-deploy/deploy/.env.production /etc/isotopeiq/.env
sudo nano /etc/isotopeiq/.env
sudo chmod 640 /etc/isotopeiq/.env
sudo chown root:isotopeiq /etc/isotopeiq/.env
```

Required values to fill in:

| Variable | How to generate |
|---|---|
| `SECRET_KEY` | `python3 -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `FIELD_ENCRYPTION_KEY` | `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `DB_PASSWORD` | Choose a strong password — must match what `server-setup.sh` set |
| `ALLOWED_HOSTS` | Your server's IP address or domain name (or `*`) |

Then re-run `push.sh` (without `SETUP=true` this time).

#### 3. Create the admin user

```bash
sudo -u isotopeiq \
  DJANGO_SETTINGS_MODULE=config.settings.production \
  /opt/isotopeiq/venv/bin/python \
  /opt/isotopeiq/backend/manage.py createsuperuser
```

---

### Updating an existing installation

```bash
bash deploy/push.sh isotopeiq@YOUR_SERVER
# With HTTPS flags if applicable:
DOMAIN=myserver.example.com bash deploy/push.sh isotopeiq@YOUR_SERVER
```

`install.sh` is safe to re-run — it migrates the database, rebuilds the frontend, and reloads all services.

---

### Manual deployment (air-gapped / no rsync)

If you cannot rsync directly, use the source bundle approach:

```bash
bash deploy/bundle.sh
scp isotopeiq-satellite-*.tar.gz isotopeiq@YOUR_SERVER:~
ssh isotopeiq@YOUR_SERVER
tar -xzf isotopeiq-satellite-*.tar.gz && cd isotopeiq-satellite-*
sudo bash deploy/server-setup.sh          # first time only
sudo bash deploy/install.sh
```

---

### Systemd service management

```bash
# Status
systemctl status isotopeiq-backend isotopeiq-celery-worker isotopeiq-celery-beat

# Logs
journalctl -u isotopeiq-backend -f
journalctl -u isotopeiq-celery-worker -f
tail -f /var/log/isotopeiq/gunicorn.log
tail -f /var/log/isotopeiq/celery-worker.log

# Restart a service
sudo systemctl restart isotopeiq-backend
```

---

### File Locations

| Path | Purpose |
|---|---|
| `/opt/isotopeiq/` | Application code |
| `/etc/isotopeiq/.env` | Environment / secrets |
| `/etc/isotopeiq/tls/` | TLS certificate and key (when HTTPS is enabled) |
| `/var/log/isotopeiq/` | Application logs |
| `/run/isotopeiq/gunicorn.sock` | Gunicorn Unix socket |
| `/etc/nginx/sites-available/isotopeiq` | Nginx site config |
