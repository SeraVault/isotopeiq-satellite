#!/bin/bash
# IsotopeIQ macOS Agent Installer
# Installs the agent binary as a root-owned launchd daemon on port 9322.
# The agent self-enrolls with the satellite on first install; the device-specific
# token is saved to /etc/isotopeiq-agent.token and never appears in service args.
#
# Usage:
#   sudo bash macos_install.sh <enrollment-token> <satellite-url> [port] [path-to-binary]
#
# Arguments:
#   enrollment-token — system-wide enrollment secret from the satellite admin panel
#   satellite-url    — base URL of the satellite, e.g. https://satellite.example.com
#   port             — TCP listen port (default: 9322)
#   path-to-binary   — path to the compiled macos_collector binary
#                       (default: ./macos_collector)

set -euo pipefail

ENROLLMENT_TOKEN="${1:?ERROR: enrollment-token is required.  Usage: sudo bash macos_install.sh <enrollment-token> <satellite-url> [port] [binary]}"
SATELLITE="${2:?ERROR: satellite-url is required.  Usage: sudo bash macos_install.sh <enrollment-token> <satellite-url> [port] [binary]}"
PORT="${3:-9322}"
BINARY="${4:-./macos_collector}"

INSTALL_PATH="/usr/local/bin/isotopeiq-agent"
PLIST_PATH="/Library/LaunchDaemons/com.isotopeiq.agent.plist"
LOG_PATH="/var/log/isotopeiq-agent.log"

if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: This script must be run as root (sudo)." >&2
    exit 1
fi

if [ ! -f "$BINARY" ]; then
    echo "ERROR: Binary not found: ${BINARY}" >&2
    exit 1
fi

echo "Installing binary → ${INSTALL_PATH}"
cp -f "$BINARY" "$INSTALL_PATH"
chmod 700 "$INSTALL_PATH"
chown root:wheel "$INSTALL_PATH"

echo "Enrolling with satellite at ${SATELLITE} ..."
"$INSTALL_PATH" --enroll --satellite "$SATELLITE" --enrollment-token "$ENROLLMENT_TOKEN" --port "$PORT" || {
    echo "ERROR: Enrollment failed. Verify the satellite URL and enrollment token." >&2
    exit 1
}

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

# Unload if already loaded (ignore errors on first install)
launchctl unload "$PLIST_PATH" 2>/dev/null || true

echo "Loading com.isotopeiq.agent"
launchctl load -w "$PLIST_PATH"

echo ""
echo "Done.  Agent enrolled and listening on 0.0.0.0:${PORT}"
echo "Check status:  sudo launchctl list com.isotopeiq.agent"
echo "View logs:     tail -f ${LOG_PATH}"
