#!/bin/bash
# IsotopeIQ macOS Agent Installer
# Installs the agent binary as a root-owned launchd daemon.
#
# Usage:  sudo bash macos_install.sh [path-to-binary]
#
# The binary is included in the ZIP downloaded from IsotopeIQ.
# Pass an explicit path only if placing the binary elsewhere.

set -euo pipefail

# Port the agent will listen on.  Substituted automatically by the IsotopeIQ
# server when generating the installer bundle.
PORT=9322

REMOTE_BINARY="macos_collector"

# Locate binary — bundled in the ZIP alongside this script
if [ -n "${1:-}" ]; then
    BINARY="$1"
elif [ -f "./macos_collector" ]; then
    BINARY="./macos_collector"
else
    echo "ERROR: Binary not found. Place macos_collector alongside this script." >&2
    exit 1
fi

INSTALL_PATH="/usr/local/bin/isotopeiq-agent"
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
true  # nothing to clean up — binary was bundled

echo ""
echo "Done.  Agent listening on 0.0.0.0:${PORT}"
echo "Check status:  sudo launchctl list com.isotopeiq.agent"
echo "View logs:     tail -f ${LOG_PATH}"
