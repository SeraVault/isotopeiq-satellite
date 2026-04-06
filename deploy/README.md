# IsotopeIQ Satellite — Deployment Guide

## Prerequisites

- Ubuntu 24.04 LTS server
- SSH access with a user that has `sudo`
- `rsync` installed on your dev machine (standard on Linux/macOS)

---

## Quick Reference

```bash
# First-time deployment (includes OS setup)
SETUP=true DOMAIN=myserver.lan bash deploy/push.sh isotopeiq@192.168.x.x

# Subsequent updates
bash deploy/push.sh isotopeiq@192.168.x.x
```

---

## First-Time Deployment

### 1. Run push.sh with SETUP=true

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

### 2. Configure the environment (first time only)

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

### 3. Create the admin user

```bash
sudo -u isotopeiq \
  DJANGO_SETTINGS_MODULE=config.settings.production \
  /opt/isotopeiq/venv/bin/python \
  /opt/isotopeiq/backend/manage.py createsuperuser
```

---

## Updating an Existing Installation

```bash
bash deploy/push.sh isotopeiq@YOUR_SERVER
# With HTTPS flags if applicable:
DOMAIN=myserver.example.com bash deploy/push.sh isotopeiq@YOUR_SERVER
```

`install.sh` is safe to re-run — it migrates the database, rebuilds the frontend, and reloads all services.

---

## Manual Deployment (air-gapped / no rsync)

If you cannot rsync directly, use the bundle approach:

```bash
bash deploy/bundle.sh
scp isotopeiq-satellite-*.tar.gz isotopeiq@YOUR_SERVER:~
ssh isotopeiq@YOUR_SERVER
tar -xzf isotopeiq-satellite-*.tar.gz && cd isotopeiq-satellite-*
sudo bash deploy/server-setup.sh          # first time only
sudo bash deploy/install.sh
```

---

## Service Management

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

## File Locations

| Path | Purpose |
|---|---|
| `/opt/isotopeiq/` | Application code |
| `/etc/isotopeiq/.env` | Environment / secrets |
| `/etc/isotopeiq/tls/` | TLS certificate and key (when HTTPS is enabled) |
| `/var/log/isotopeiq/` | Application logs |
| `/run/isotopeiq/gunicorn.sock` | Gunicorn Unix socket |
| `/etc/nginx/sites-available/isotopeiq` | Nginx site config |
