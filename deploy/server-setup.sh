#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# IsotopeIQ Satellite — Server Setup
# Run ONCE on a fresh Ubuntu 24.04 LTS server as a user with sudo.
# Installs all OS-level dependencies and creates the isotopeiq system account.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

APP_USER=isotopeiq
APP_DIR=/opt/isotopeiq
DB_NAME=isotopeiq
DB_USER=isotopeiq

log()  { echo -e "\033[1;34m[setup]\033[0m $*"; }
ok()   { echo -e "\033[1;32m[  OK  ]\033[0m $*"; }
die()  { echo -e "\033[1;31m[ ERR  ]\033[0m $*" >&2; exit 1; }

[[ $EUID -ne 0 ]] && die "Run as root or with sudo: sudo bash $0"

# ── 1. System packages ───────────────────────────────────────────────────────
log "Updating apt and installing packages…"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q \
    python3.12 python3.12-venv python3.12-dev \
    postgresql postgresql-client libpq-dev \
    redis-server \
    nginx \
    xmlsec1 \
    build-essential libldap2-dev libsasl2-dev \
    git curl openssl \
    logrotate
ok "Packages installed."

# ── 2. Node.js 22 LTS (via NodeSource) ──────────────────────────────────────
# Do NOT install nodejs/npm from Ubuntu repos — they conflict with NodeSource.
if ! node --version 2>/dev/null | grep -q "^v2[0-9]"; then
    log "Installing Node.js 22 LTS from NodeSource…"
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
    apt-get install -y nodejs
    ok "Node.js $(node --version) installed (npm $(npm --version))."
else
    ok "Node.js $(node --version) already available."
fi

# ── 3. System user ───────────────────────────────────────────────────────────
if ! id "$APP_USER" &>/dev/null; then
    log "Creating system user '$APP_USER'…"
    useradd --system --shell /bin/bash --home "$APP_DIR" --create-home "$APP_USER"
    ok "User created."
else
    ok "User '$APP_USER' already exists."
fi

# ── 4. Application directories ───────────────────────────────────────────────
log "Creating application directories…"
mkdir -p "$APP_DIR"
mkdir -p /etc/isotopeiq
mkdir -p /run/isotopeiq
mkdir -p /var/log/isotopeiq
chown -R "$APP_USER:$APP_USER" "$APP_DIR" /etc/isotopeiq /var/log/isotopeiq

# /run/isotopeiq must persist across reboots — add tmpfiles.d entry
cat > /etc/tmpfiles.d/isotopeiq.conf <<EOF
d /run/isotopeiq 0755 $APP_USER $APP_USER -
EOF
systemd-tmpfiles --create /etc/tmpfiles.d/isotopeiq.conf
ok "Directories created."

# ── 5. PostgreSQL ─────────────────────────────────────────────────────────────
log "Configuring PostgreSQL…"
systemctl enable --now postgresql

# Prompt for a DB password if not already set via env
if [[ -z "${DB_PASSWORD:-}" ]]; then
    read -r -s -p "Enter a password for the PostgreSQL '$DB_USER' user: " DB_PASSWORD
    echo
fi

if sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1; then
    sudo -u postgres psql -c "ALTER USER $DB_USER WITH PASSWORD '$DB_PASSWORD';"
else
    sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';"
fi

sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" \
    | grep -q 1 || sudo -u postgres createdb -O "$DB_USER" "$DB_NAME"

ok "PostgreSQL database '$DB_NAME' ready."

# ── 6. Redis ─────────────────────────────────────────────────────────────────
log "Enabling Redis…"
systemctl enable --now redis-server
ok "Redis running."

# ── 7. Nginx ─────────────────────────────────────────────────────────────────
log "Enabling Nginx…"
systemctl enable --now nginx
ok "Nginx running."

# ── 8. Firewall ───────────────────────────────────────────────────────────────
log "Configuring firewall…"
if command -v ufw &>/dev/null; then
    ufw allow OpenSSH
    ufw allow 'Nginx Full'
    ufw --force enable
    ok "ufw: SSH + HTTP/HTTPS allowed."
else
    ok "ufw not found — skipping firewall configuration."
fi

# ── 9. Logrotate ─────────────────────────────────────────────────────────────
cat > /etc/logrotate.d/isotopeiq <<'EOF'
/var/log/isotopeiq/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 isotopeiq isotopeiq
    sharedscripts
    postrotate
        systemctl kill --signal=USR1 isotopeiq-backend.service 2>/dev/null || true
    endscript
}
EOF
ok "Log rotation configured."

echo
ok "──────────────────────────────────────────────────────"
ok "Server setup complete."
ok ""
ok "Next steps:"
ok "  1. Edit /etc/isotopeiq/.env  (copy from deploy/.env.production)"
ok "  2. Run:  sudo bash deploy/install.sh"
ok "──────────────────────────────────────────────────────"
