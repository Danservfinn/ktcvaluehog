#!/bin/bash
# Run the Autonomous ML Monitor Dashboard
# Usage: ./scripts/run_ml_monitor.sh

cd "$(dirname "$0")/.."

echo "🤖 Starting Autonomous ML Monitor Dashboard..."
echo ""
echo "Dashboard URL: http://localhost:8502"
echo ""
echo "Press Ctrl+C to stop"
echo ""

streamlit run dashboard/autonomous_ml_monitor.py --server.port 8502 --server.headless true
