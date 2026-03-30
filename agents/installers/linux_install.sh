#!/bin/bash
# IsotopeIQ Linux Agent Installer
# Installs the agent binary as a root-owned systemd service on port 9322.
# The agent self-enrolls with the satellite on first install; the device-specific
# token is saved to /etc/isotopeiq-agent.token and never appears in service args.
#
# Usage:
#   sudo bash linux_install.sh <enrollment-token> <satellite-url> [port] [path-to-binary]
#
# Arguments:
#   enrollment-token — system-wide enrollment secret from the satellite admin panel
#   satellite-url    — base URL of the satellite, e.g. https://satellite.example.com
#   port             — TCP listen port (default: 9322)
#   path-to-binary   — path to the compiled linux_collector binary
#                       (default: ./linux_collector_amd64 if it exists, else ./linux_collector)

set -euo pipefail

ENROLLMENT_TOKEN="${1:?ERROR: enrollment-token is required.  Usage: sudo bash linux_install.sh <enrollment-token> <satellite-url> [port] [binary]}"
SATELLITE="${2:?ERROR: satellite-url is required.  Usage: sudo bash linux_install.sh <enrollment-token> <satellite-url> [port] [binary]}"
PORT="${3:-9322}"

# Locate the binary
if [ -n "${4:-}" ]; then
    BINARY="$4"
elif [ -f "./linux_collector_amd64" ]; then
    BINARY="./linux_collector_amd64"
elif [ -f "./linux_collector" ]; then
    BINARY="./linux_collector"
else
    echo "ERROR: Could not find linux_collector binary.  Pass the path as the fourth argument." >&2
    exit 1
fi

INSTALL_PATH="/usr/local/bin/isotopeiq-agent"
UNIT_PATH="/etc/systemd/system/isotopeiq-agent.service"

if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: This script must be run as root (sudo)." >&2
    exit 1
fi

echo "Installing binary → ${INSTALL_PATH}"
cp -f "$BINARY" "$INSTALL_PATH"
chmod 700 "$INSTALL_PATH"
chown root:root "$INSTALL_PATH"

echo "Enrolling with satellite at ${SATELLITE} ..."
"$INSTALL_PATH" --enroll --satellite "$SATELLITE" --enrollment-token "$ENROLLMENT_TOKEN" --port "$PORT" || {
    echo "ERROR: Enrollment failed. Verify the satellite URL and enrollment token." >&2
    exit 1
}

echo "Writing systemd unit → ${UNIT_PATH}"
cat > "$UNIT_PATH" <<UNIT
[Unit]
Description=IsotopeIQ Baseline Collection Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=${INSTALL_PATH} --serve --port ${PORT}
Restart=on-failure
RestartSec=30
User=root
StandardOutput=journal
StandardError=journal
# Harden the service surface.
NoNewPrivileges=yes
ProtectSystem=strict
ReadWritePaths=/etc /tmp

[Install]
WantedBy=multi-user.target
UNIT

echo "Enabling and starting isotopeiq-agent.service"
systemctl daemon-reload
systemctl enable --now isotopeiq-agent.service

echo ""
echo "Done.  Agent enrolled and listening on 0.0.0.0:${PORT}"
echo "Check status:  systemctl status isotopeiq-agent"
echo "View logs:     journalctl -u isotopeiq-agent -f"
