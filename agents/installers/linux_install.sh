#!/bin/bash
# IsotopeIQ Linux Agent Installer
# Installs the agent binary as a root-owned systemd service.
#
# Workflow:
#   1. Add the device in IsotopeIQ and download isotopeiq-agent.conf.
#   2. Place isotopeiq-agent.conf in the same directory as this script.
#   3. Run:  sudo bash linux_install.sh [config-file] [path-to-binary]
#
# The binary is downloaded automatically from the IsotopeIQ server unless
# you pass an explicit [path-to-binary] or place one alongside this script.
#
# Arguments:
#   config-file    — path to isotopeiq-agent.conf (default: ./isotopeiq-agent.conf)
#   path-to-binary — path to the linux_collector binary (optional; auto-downloaded if omitted)

set -euo pipefail

CONFIG_FILE="${1:-./isotopeiq-agent.conf}"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "ERROR: Config file not found: ${CONFIG_FILE}" >&2
    echo "Download isotopeiq-agent.conf from IsotopeIQ and place it alongside this script." >&2
    exit 1
fi

# Parse config file
PORT=$(  grep -E '^port='   "$CONFIG_FILE" | head -1 | cut -d= -f2-)
SERVER=$(grep -E '^server=' "$CONFIG_FILE" | head -1 | cut -d= -f2-)
PORT="${PORT:-9322}"

# Pick the right binary name for this architecture
ARCH=$(uname -m)
case "$ARCH" in
    x86_64)    REMOTE_BINARY="linux_collector_amd64" ;;
    i686|i386) REMOTE_BINARY="linux_collector_i686"  ;;
    *)         REMOTE_BINARY="linux_collector_amd64" ;;
esac

# Locate or download the binary
CLEANUP_BINARY=0
if [ -n "${2:-}" ]; then
    BINARY="$2"
elif [ -f "./${REMOTE_BINARY}" ]; then
    BINARY="./${REMOTE_BINARY}"
elif [ -f "./linux_collector" ]; then
    BINARY="./linux_collector"
elif [ -n "$SERVER" ]; then
    echo "Downloading ${REMOTE_BINARY} from ${SERVER}..."
    TMP_BINARY=$(mktemp)
    if ! curl -fsSL "${SERVER}/api/agents/${REMOTE_BINARY}" -o "$TMP_BINARY"; then
        rm -f "$TMP_BINARY"
        echo "ERROR: Download failed from ${SERVER}/api/agents/${REMOTE_BINARY}" >&2
        exit 1
    fi
    # Verify SHA-256 against the server's info endpoint
    INFO=$(curl -fsSL "${SERVER}/api/agents/${REMOTE_BINARY}/info" 2>/dev/null || true)
    if [ -n "$INFO" ]; then
        EXPECTED=$(echo "$INFO" | grep -o '"sha256":"[^"]*"' | cut -d'"' -f4)
        ACTUAL=$(sha256sum "$TMP_BINARY" | cut -d' ' -f1)
        if [ "$EXPECTED" != "$ACTUAL" ]; then
            rm -f "$TMP_BINARY"
            echo "ERROR: SHA-256 mismatch (expected ${EXPECTED}, got ${ACTUAL})." >&2
            exit 1
        fi
        echo "SHA-256 verified: ${ACTUAL}"
    fi
    chmod +x "$TMP_BINARY"
    BINARY="$TMP_BINARY"
    CLEANUP_BINARY=1
else
    echo "ERROR: Binary not found locally and no 'server' in ${CONFIG_FILE} to download from." >&2
    exit 1
fi

INSTALL_PATH="/usr/local/bin/isotopeiq-agent"
CONFIG_DEST="/etc/isotopeiq-agent.conf"
UNIT_PATH="/etc/systemd/system/isotopeiq-agent.service"

if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: This script must be run as root (sudo)." >&2
    exit 1
fi

# Stop and remove any existing installation
if systemctl is-active --quiet isotopeiq-agent 2>/dev/null; then
    echo "Stopping existing isotopeiq-agent service..."
    systemctl stop isotopeiq-agent
fi
if systemctl is-enabled --quiet isotopeiq-agent 2>/dev/null; then
    systemctl disable isotopeiq-agent
fi
if [ -f "$UNIT_PATH" ]; then
    rm -f "$UNIT_PATH"
    systemctl daemon-reload
fi

echo "Installing binary → ${INSTALL_PATH}"
cp -f "$BINARY" "$INSTALL_PATH"
chmod 700 "$INSTALL_PATH"
chown root:root "$INSTALL_PATH"

echo "Installing config → ${CONFIG_DEST}"
cp -f "$CONFIG_FILE" "$CONFIG_DEST"
chmod 600 "$CONFIG_DEST"
chown root:root "$CONFIG_DEST"

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
Environment=PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
StandardOutput=journal
StandardError=journal
NoNewPrivileges=yes
ProtectSystem=strict
ReadWritePaths=/etc /tmp

[Install]
WantedBy=multi-user.target
UNIT

echo "Enabling and starting isotopeiq-agent.service"
systemctl daemon-reload
systemctl enable --now isotopeiq-agent.service

# Clean up temp download if we created one
if [ "$CLEANUP_BINARY" = "1" ]; then rm -f "$TMP_BINARY"; fi

echo ""
echo "Done.  Agent listening on 0.0.0.0:${PORT}"
echo "Check status:  systemctl status isotopeiq-agent"
echo "View logs:     journalctl -u isotopeiq-agent -f"
