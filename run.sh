#!/bin/bash
# Dynasty Edge Dashboard Launcher
# Run with: ./run.sh

echo "🏈 Dynasty Edge Dashboard"
echo "========================="

# Load from .env file if it exists
if [ -f .env ]; then
    echo "📂 Loading .env file..."
    export $(grep -v '^#' .env | xargs)
fi

# Check for API key
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "⚠️  ANTHROPIC_API_KEY not set!"
    echo ""
    echo "Create a .env file with:"
    echo "  ANTHROPIC_API_KEY=your-key-here"
    echo ""
fi

# Set Sleeper league ID
export SLEEPER_LEAGUE_ID="${SLEEPER_LEAGUE_ID:-1180199027998867456}"

# Check if streamlit is installed
if ! command -v streamlit &> /dev/null; then
    echo "📦 Installing dependencies..."
    pip install streamlit pandas plotly anthropic nflreadpy polars pyarrow
fi

# Run dashboard
echo "🚀 Starting dashboard at http://localhost:8501"
echo ""
streamlit run dashboard.py
