#!/bin/sh
# ─────────────────────────────────────────────────────────────────────────────
# IsotopeIQ Satellite — nginx container entrypoint
#
# Generates a self-signed TLS certificate for $DOMAIN if none is already
# present at /etc/nginx/tls/server.crt.  Mount your own certificate and key
# files at that path to use a real certificate instead.
# ─────────────────────────────────────────────────────────────────────────────
set -e

DOMAIN="${DOMAIN:-localhost}"
CERT_DIR="/etc/nginx/tls"
CERT="$CERT_DIR/server.crt"
KEY="$CERT_DIR/server.key"

mkdir -p "$CERT_DIR"

if [ ! -f "$CERT" ] || [ ! -f "$KEY" ]; then
    echo "[nginx] No certificate found — generating self-signed certificate for: $DOMAIN"
    openssl req -x509 -newkey rsa:2048 -nodes \
        -keyout "$KEY" \
        -out    "$CERT" \
        -days   3650 \
        -subj   "/CN=$DOMAIN" \
        -addext "subjectAltName=DNS:$DOMAIN,DNS:localhost,IP:127.0.0.1" \
        2>/dev/null
    chmod 600 "$KEY"
    echo "[nginx] Self-signed certificate generated (valid 10 years)."
    echo "[nginx] To use a real certificate, mount it at:"
    echo "[nginx]   $CERT"
    echo "[nginx]   $KEY"
else
    echo "[nginx] Using existing certificate at $CERT"
fi

exec "$@"
