#!/bin/bash
# Install KTC Snapshot Scheduler for macOS
# Runs twice daily at 6 AM and 6 PM

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PLIST_SRC="$PROJECT_DIR/config/com.thoth.ktc-snapshot.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.thoth.ktc-snapshot.plist"

echo "=============================================="
echo "Installing KTC Snapshot Scheduler"
echo "=============================================="

# Create logs directory
mkdir -p "$PROJECT_DIR/logs"

# Create LaunchAgents directory if needed
mkdir -p "$HOME/Library/LaunchAgents"

# Unload existing agent if present
if launchctl list | grep -q "com.thoth.ktc-snapshot"; then
    echo "Unloading existing agent..."
    launchctl unload "$PLIST_DST" 2>/dev/null || true
fi

# Copy plist to LaunchAgents
echo "Installing launch agent..."
cp "$PLIST_SRC" "$PLIST_DST"

# Load the agent
echo "Loading launch agent..."
launchctl load "$PLIST_DST"

# Verify
if launchctl list | grep -q "com.thoth.ktc-snapshot"; then
    echo ""
    echo "=============================================="
    echo "SUCCESS: KTC Snapshot Scheduler installed!"
    echo "=============================================="
    echo ""
    echo "Schedule: 6:00 AM and 6:00 PM daily"
    echo "Logs: $PROJECT_DIR/logs/"
    echo ""
    echo "Commands:"
    echo "  View status:   launchctl list | grep ktc"
    echo "  Run now:       launchctl start com.thoth.ktc-snapshot"
    echo "  Stop:          launchctl unload $PLIST_DST"
    echo "  View logs:     tail -f $PROJECT_DIR/logs/ktc_snapshot.log"
    echo ""
else
    echo "ERROR: Failed to install scheduler"
    exit 1
fi
