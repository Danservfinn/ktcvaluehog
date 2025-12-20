#!/bin/bash
# Install Weekly Data Scheduler for macOS
# Runs every Tuesday at 4:00 AM during NFL season

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PLIST_SRC="$PROJECT_DIR/config/com.thoth.weekly-data.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.thoth.weekly-data.plist"

echo "=============================================="
echo "Installing Weekly Data Scheduler"
echo "=============================================="

# Create logs directory
mkdir -p "$PROJECT_DIR/logs"

# Create LaunchAgents directory if needed
mkdir -p "$HOME/Library/LaunchAgents"

# Unload existing agent if present
if launchctl list | grep -q "com.thoth.weekly-data"; then
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
if launchctl list | grep -q "com.thoth.weekly-data"; then
    echo ""
    echo "=============================================="
    echo "SUCCESS: Weekly Data Scheduler installed!"
    echo "=============================================="
    echo ""
    echo "Schedule: Tuesday 4:00 AM"
    echo "Logs: $PROJECT_DIR/logs/"
    echo ""
    echo "Jobs included:"
    echo "  - Play-by-Play Features"
    echo "  - Injury Reports"
    echo "  - Depth Charts"
    echo "  - KTC Trends"
    echo ""
    echo "Commands:"
    echo "  View status:   launchctl list | grep thoth"
    echo "  Run now:       launchctl start com.thoth.weekly-data"
    echo "  Stop:          launchctl unload $PLIST_DST"
    echo "  View logs:     tail -f $PROJECT_DIR/logs/weekly_data_stdout.log"
    echo "  Manual run:    python $PROJECT_DIR/scripts/weekly_data_job.py"
    echo ""
else
    echo "ERROR: Failed to install scheduler"
    exit 1
fi
