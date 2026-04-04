#!/bin/bash
# IsotopeIQ macOS Agent Installer
# Installs the agent binary as a root-owned launchd daemon.
#
# Workflow:
#   1. Add the device in IsotopeIQ and download isotopeiq-agent.conf.
#   2. Place isotopeiq-agent.conf in the same directory as this script.
#   3. Run:  sudo bash macos_install.sh [config-file] [path-to-binary]
#
# The binary is downloaded automatically from the IsotopeIQ server unless
# you pass an explicit [path-to-binary] or place one alongside this script.
#
# Arguments:
#   config-file    — path to isotopeiq-agent.conf (default: ./isotopeiq-agent.conf)
#   path-to-binary — path to the macos_collector binary (optional; auto-downloaded if omitted)

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

REMOTE_BINARY="macos_collector"

# Locate or download the binary
CLEANUP_BINARY=0
if [ -n "${2:-}" ]; then
    BINARY="$2"
elif [ -f "./macos_collector" ]; then
    BINARY="./macos_collector"
elif [ -n "$SERVER" ]; then
    echo "Downloading macos_collector from ${SERVER}..."
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
        ACTUAL=$(shasum -a 256 "$TMP_BINARY" | cut -d' ' -f1)
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
PLIST_PATH="/Library/LaunchDaemons/com.isotopeiq.agent.plist"
LOG_PATH="/var/log/isotopeiq-agent.log"

if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: This script must be run as root (sudo)." >&2
    exit 1
fi

echo "Installing binary → ${INSTALL_PATH}"
cp -f "$BINARY" "$INSTALL_PATH"
chmod 700 "$INSTALL_PATH"
chown root:wheel "$INSTALL_PATH"

echo "Installing config → ${CONFIG_DEST}"
cp -f "$CONFIG_FILE" "$CONFIG_DEST"
chmod 600 "$CONFIG_DEST"
chown root:wheel "$CONFIG_DEST"

echo "Writing launchd plist → ${PLIST_PATH}"
cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.isotopeiq.agent</string>

    <key>ProgramArguments</key>
    <array>
        <string>${INSTALL_PATH}</string>
        <string>--serve</string>
        <string>--port</string>
        <string>${PORT}</string>
    </array>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>UserName</key>
    <string>root</string>

    <key>StandardOutPath</key>
    <string>${LOG_PATH}</string>

    <key>StandardErrorPath</key>
    <string>${LOG_PATH}</string>
</dict>
</plist>
PLIST

chmod 644 "$PLIST_PATH"
chown root:wheel "$PLIST_PATH"

# Stop and remove any existing installation
if launchctl list com.isotopeiq.agent &>/dev/null; then
    echo "Stopping existing com.isotopeiq.agent daemon..."
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
    # Kill any lingering process
    pkill -f isotopeiq-agent 2>/dev/null || true
fi

echo "Loading com.isotopeiq.agent"
launchctl load -w "$PLIST_PATH"

# Clean up temp download if we created one
if [ "$CLEANUP_BINARY" = "1" ]; then rm -f "$TMP_BINARY"; fi

echo ""
echo "Done.  Agent listening on 0.0.0.0:${PORT}"
echo "Check status:  sudo launchctl list com.isotopeiq.agent"
echo "View logs:     tail -f ${LOG_PATH}"
