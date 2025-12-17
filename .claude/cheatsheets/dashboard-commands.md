---
title: Dashboard Commands
link: dashboard-commands
type: cheatsheets
ontological_relations: []
tags:
- streamlit
- dashboard
- commands
created_at: 2025-12-17T16:15:22Z
updated_at: 2025-12-17T16:15:22Z
uuid: b5ebc830-2142-4452-bc9b-f2ab9cab2ffa
---

# Dashboard Commands Cheatsheet

## Running the Dashboard

```bash
# Activate virtual environment
source venv/bin/activate

# Run Streamlit dashboard
streamlit run dashboard.py

# Or use the launcher script
./run.sh
```

## Environment Setup

```bash
# Required in .env file
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
NEO4J_AUTH_DISABLED=true  # if running without auth
ANTHROPIC_API_KEY=sk-ant-xxx  # for Claude AI chat
```

## Data Refresh Commands

```bash
# Fetch latest KTC values
python scripts/fetch_ktc_data.py

# Fetch Sleeper league data
python scripts/fetch_sleeper_data.py

# Fetch NFL stats
python scripts/fetch_nfl_data.py

# Generate daily report
python scripts/generate_daily_report.py
```

## Neo4j Commands

```bash
# Initialize Neo4j with data
python setup_neo4j.py

# Run temporal pipeline
python temporal_pipeline.py
```

## ML Pipeline Commands

```bash
# Archive KTC snapshot (runs automatically via GitHub Actions)
python scripts/archive_ktc_snapshot.py

# Check prediction pipeline status
python pipelines/ktc_prediction_pipeline.py

# Data locations
ls data/historical/ktc_snapshots/  # Daily snapshots
cat data/historical/ktc_snapshots/ktc_all_snapshots.csv  # Consolidated
```

## Dashboard Features

| Tab | Function |
|-----|----------|
| Player Rankings | View/filter players by position, search, sort by KTC value |
| Trade Analyzer | Evaluate trades, compare player values |
| Roster Analysis | League roster breakdown, team valuations |
| Buy/Sell Signals | Edge scores showing undervalued/overvalued players |
| AI Chat | Claude-powered analysis (requires API key) |

## Troubleshooting

```bash
# Clear Streamlit cache
streamlit cache clear

# Check Neo4j connection
python -c "from neo4j import GraphDatabase; print('OK')"

# Verify data files exist
ls -la data/
```
