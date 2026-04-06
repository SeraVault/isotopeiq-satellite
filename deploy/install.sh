#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# IsotopeIQ Satellite — Application Installer / Updater
# Run as root (or with sudo) after server-setup.sh has been run.
# Safe to re-run for updates — migrates DB, rebuilds frontend, reloads services.
#
# HTTPS modes (all optional — plain HTTP works with no extra flags):
#
#   Self-signed certificate (auto-generated, no internet needed):
#     sudo DOMAIN=myserver.example.com bash deploy/install.sh
#
#   Own certificate (internal CA / existing cert):
#     sudo DOMAIN=myserver.example.com \
#          TLS_CERT=/path/to/server.crt \
#          TLS_KEY=/path/to/server.key \
#          bash deploy/install.sh
#
#   Let's Encrypt (requires internet access):
#     sudo DOMAIN=myserver.example.com LETSENCRYPT=true bash deploy/install.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

APP_USER=isotopeiq
APP_DIR=/opt/isotopeiq
ENV_FILE=/etc/isotopeiq/.env
DEPLOY_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC_DIR="$(cd "$DEPLOY_DIR/.." && pwd)"
VENV="$APP_DIR/venv"
PYTHON="$VENV/bin/python"
PIP="$VENV/bin/pip"

# HTTPS configuration (all optional — leave blank for plain HTTP)
DOMAIN="${DOMAIN:-}"           # server name / domain
TLS_CERT="${TLS_CERT:-}"       # path to existing cert PEM (skips auto-generation)
TLS_KEY="${TLS_KEY:-}"         # path to existing key PEM (skips auto-generation)
LETSENCRYPT="${LETSENCRYPT:-}" # set to 'true' to use Let's Encrypt (requires internet)

log()  { echo -e "\033[1;34m[install]\033[0m $*"; }
ok()   { echo -e "\033[1;32m[  OK  ]\033[0m $*"; }
die()  { echo -e "\033[1;31m[ ERR  ]\033[0m $*" >&2; exit 1; }

[[ $EUID -ne 0 ]] && die "Run as root or with sudo: sudo bash $0"
[[ -f "$ENV_FILE" ]] || die ".env not found at $ENV_FILE — copy deploy/.env.production there and fill it in."

# ── 1. Sync source code ───────────────────────────────────────────────────────
log "Syncing source code to $APP_DIR…"
rsync -a --delete \
    --exclude='.venv' \
    --exclude='venv' \
    --exclude='node_modules' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.git' \
    --exclude='deploy' \
    --exclude='staticfiles' \
    --exclude='celerybeat-schedule' \
    --chown="$APP_USER:$APP_USER" \
    "$SRC_DIR/" "$APP_DIR/"

# Keep the .env in /etc/isotopeiq; symlink it where Django/decouple expects it
ln -sf "$ENV_FILE" "$APP_DIR/backend/.env"
ok "Source synced."

# ── 2. Python virtualenv ─────────────────────────────────────────────────────
log "Setting up Python virtualenv…"
if [[ ! -f "$VENV/bin/activate" ]]; then
    sudo -u "$APP_USER" python3.12 -m venv "$VENV"
fi
sudo -u "$APP_USER" "$PIP" install --quiet --upgrade pip
sudo -u "$APP_USER" "$PIP" install --quiet -r "$APP_DIR/backend/requirements.txt"
ok "Python dependencies installed."

# ── 3. Build frontend ────────────────────────────────────────────────────────
log "Installing Node dependencies and building frontend…"
cd "$APP_DIR/frontend"
sudo -u "$APP_USER" npm ci --silent
sudo -u "$APP_USER" npm run build
ok "Frontend built → $APP_DIR/frontend/dist"

# ── 4. Django: collectstatic + migrate ───────────────────────────────────────
log "Collecting static files…"
cd "$APP_DIR/backend"
sudo -u "$APP_USER" DJANGO_SETTINGS_MODULE=config.settings.production \
    "$PYTHON" manage.py collectstatic --noinput -v 0

log "Running database migrations…"
sudo -u "$APP_USER" DJANGO_SETTINGS_MODULE=config.settings.production \
    "$PYTHON" manage.py migrate --noinput
ok "Static files collected and migrations applied."

# ── Create superuser if none exists yet ───────────────────────────────────────
SUPERUSER_COUNT=$(sudo -u "$APP_USER" DJANGO_SETTINGS_MODULE=config.settings.production \
    "$PYTHON" manage.py shell -c \
    "from django.contrib.auth import get_user_model; print(get_user_model().objects.filter(is_superuser=True).count())" \
    2>/dev/null || echo 0)

if [[ "$SUPERUSER_COUNT" -eq 0 ]]; then
    if [[ -n "${DJANGO_SUPERUSER_USERNAME:-}" && -n "${DJANGO_SUPERUSER_PASSWORD:-}" && -n "${DJANGO_SUPERUSER_EMAIL:-}" ]]; then
        log "Creating superuser '${DJANGO_SUPERUSER_USERNAME}'…"
        sudo -u "$APP_USER" \
            DJANGO_SETTINGS_MODULE=config.settings.production \
            DJANGO_SUPERUSER_USERNAME="$DJANGO_SUPERUSER_USERNAME" \
            DJANGO_SUPERUSER_PASSWORD="$DJANGO_SUPERUSER_PASSWORD" \
            DJANGO_SUPERUSER_EMAIL="$DJANGO_SUPERUSER_EMAIL" \
            "$PYTHON" manage.py createsuperuser --noinput
        ok "Superuser created."
    else
        log "No superuser exists yet. Create one after deploy:"
        log "  sudo bash $DEPLOY_DIR/create-admin.sh"
    fi
else
    ok "Superuser already exists — skipping."
fi

# ── 5. Install systemd units ─────────────────────────────────────────────────
log "Installing systemd service units…"
cp "$DEPLOY_DIR/isotopeiq-backend.service"      /etc/systemd/system/
cp "$DEPLOY_DIR/isotopeiq-celery-worker.service" /etc/systemd/system/
cp "$DEPLOY_DIR/isotopeiq-celery-beat.service"   /etc/systemd/system/
systemctl daemon-reload
ok "Systemd units installed."

# ── 6. Install nginx config ───────────────────────────────────────────────────
log "Installing nginx config…"
# Always write a fresh copy so re-runs don't accumulate sed patches.
sed "s/YOUR_SERVER_NAME/${DOMAIN:-_}/g" \
    "$DEPLOY_DIR/nginx-isotopeiq.conf" \
    > /etc/nginx/sites-available/isotopeiq
ln -sf /etc/nginx/sites-available/isotopeiq /etc/nginx/sites-enabled/isotopeiq
# Remove default site if present
rm -f /etc/nginx/sites-enabled/default
nginx -t
ok "Nginx config installed."

# ── 7. Enable and restart services ───────────────────────────────────────────
log "Enabling and restarting services…"
for svc in isotopeiq-backend isotopeiq-celery-worker isotopeiq-celery-beat; do
    systemctl enable "$svc"
    systemctl restart "$svc"
    sleep 1
    systemctl is-active --quiet "$svc" \
        && ok "$svc is running." \
        || { echo; journalctl -u "$svc" -n 20 --no-pager; die "$svc failed to start."; }
done
systemctl reload nginx
ok "Nginx reloaded."

# ── 8. HTTPS (optional) ──────────────────────────────────────────────────────
_configure_nginx_tls() {
    local cert="$1" key="$2"
    local conf=/etc/nginx/sites-available/isotopeiq
    # Rewrite the config from the template with TLS server block replacing the HTTP one.
    sed "s/YOUR_SERVER_NAME/${DOMAIN}/g" "$DEPLOY_DIR/nginx-isotopeiq.conf" \
    | awk -v cert="$cert" -v key="$key" -v domain="$DOMAIN" '
        /listen 80;/ {
            print "    listen 80;"
            print "    listen 443 ssl;"
            print "    ssl_certificate     " cert ";"
            print "    ssl_certificate_key " key ";"
            print "    ssl_protocols TLSv1.2 TLSv1.3;"
            print "    ssl_ciphers HIGH:!aNULL:!MD5;"
            print "    if ($scheme = http) { return 301 https://$host$request_uri; }"
            next
        }
        { print }
    ' > "$conf"
    nginx -t && systemctl reload nginx
}

if [[ -z "$DOMAIN" ]]; then
    log "DOMAIN not set — running on plain HTTP (port 80)."
    log "To add HTTPS later see the comments at the top of this script."

elif [[ "$LETSENCRYPT" == "true" ]]; then
    # ── Let's Encrypt (requires internet access) ─────────────────────────────
    log "Configuring HTTPS for $DOMAIN via Let's Encrypt (requires internet)…"
    if ! command -v certbot &>/dev/null; then
        apt-get install -y -q certbot python3-certbot-nginx
    fi
    sed -i "s/YOUR_SERVER_NAME/$DOMAIN/g" /etc/nginx/sites-available/isotopeiq
    nginx -t && systemctl reload nginx
    certbot --nginx \
        --non-interactive \
        --agree-tos \
        --redirect \
        --email "admin@${DOMAIN}" \
        -d "$DOMAIN"
    ok "HTTPS configured for $DOMAIN. Certificate auto-renewal is handled by certbot.timer."

elif [[ -n "$TLS_CERT" && -n "$TLS_KEY" ]]; then
    # ── Provided certificate (internal CA, air-gapped) ───────────────────────
    [[ -f "$TLS_CERT" ]] || die "TLS_CERT file not found: $TLS_CERT"
    [[ -f "$TLS_KEY"  ]] || die "TLS_KEY file not found: $TLS_KEY"
    log "Configuring HTTPS for $DOMAIN with provided certificate…"
    CERT_DIR=/etc/isotopeiq/tls
    mkdir -p "$CERT_DIR"
    cp "$TLS_CERT" "$CERT_DIR/server.crt"
    cp "$TLS_KEY"  "$CERT_DIR/server.key"
    chmod 640 "$CERT_DIR/server.key"
    chown root:isotopeiq "$CERT_DIR/server.key"
    _configure_nginx_tls "$CERT_DIR/server.crt" "$CERT_DIR/server.key"
    ok "HTTPS configured for $DOMAIN using provided certificate."

else
    # ── Auto-generated self-signed certificate (default, no internet needed) ──
    log "Generating self-signed TLS certificate for $DOMAIN…"
    CERT_DIR=/etc/isotopeiq/tls
    mkdir -p "$CERT_DIR"
    openssl req -x509 -nodes -newkey rsa:2048 \
        -keyout "$CERT_DIR/server.key" \
        -out    "$CERT_DIR/server.crt" \
        -days   7300 \
        -subj   "/CN=$DOMAIN/O=IsotopeIQ Satellite/C=US" \
        -addext "subjectAltName=DNS:$DOMAIN,IP:127.0.0.1"
    chmod 640 "$CERT_DIR/server.key"
    chown root:isotopeiq "$CERT_DIR/server.key"
    _configure_nginx_tls "$CERT_DIR/server.crt" "$CERT_DIR/server.key"
    ok "Self-signed certificate generated (valid 20 years): $CERT_DIR/server.crt"
    log "To trust it on clients, copy $CERT_DIR/server.crt to their trusted CA store."
fi

echo
ok "──────────────────────────────────────────────────────"
ok "IsotopeIQ Satellite deployment complete."
ok ""
if [[ -n "$DOMAIN" ]]; then
ok "  URL: https://$DOMAIN/"
else
ok "  URL: http://<server-ip>/"
fi
ok ""
ok "Create a superuser:"
ok "  sudo -u isotopeiq DJANGO_SETTINGS_MODULE=config.settings.production \\"
ok "    $PYTHON $APP_DIR/backend/manage.py createsuperuser"
ok "──────────────────────────────────────────────────────"
