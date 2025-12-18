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

# Thoth Commands Cheatsheet

## Running the Platform

```bash
# Activate virtual environment
source venv/bin/activate

# Run 12-page Streamlit dashboard
streamlit run dashboard/app.py

# Or legacy single-file dashboard
streamlit run dashboard.py

# Run Thoth CLI agent
python thoth_agent.py

# Or use launcher script
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

## Weekly Data Jobs

```bash
# Run all weekly jobs (PBP, injuries, depth charts, KTC trends)
python scripts/weekly_data_job.py

# Run specific job only
python scripts/weekly_data_job.py --job pbp_features
python scripts/weekly_data_job.py --job injuries
python scripts/weekly_data_job.py --job depth_charts
python scripts/weekly_data_job.py --job ktc_trends

# Preview what would run
python scripts/weekly_data_job.py --dry-run

# Check last run status
python scripts/weekly_data_job.py --status

# Force run even outside NFL season
python scripts/weekly_data_job.py --force
```

## Play-by-Play Features

```bash
# Load historical data (multiple seasons)
python scripts/ingest_pbp_features.py --years 2023 2024

# Weekly update (current week only)
python scripts/ingest_pbp_features.py --current-week

# Test mode (no DB writes)
python scripts/ingest_pbp_features.py --years 2024 --test

# Force run (skip import lock check)
python scripts/ingest_pbp_features.py --years 2024 --force
```

## Scheduler Management (macOS)

```bash
# Install schedulers
./scripts/install_ktc_scheduler.sh       # KTC (6AM/6PM daily)
./scripts/install_weekly_scheduler.sh    # Weekly data (Tue 4AM)

# View all Thoth schedulers
launchctl list | grep thoth

# Run job manually
launchctl start com.thoth.ktc-snapshot
launchctl start com.thoth.weekly-data

# Stop/unload scheduler
launchctl unload ~/Library/LaunchAgents/com.thoth.weekly-data.plist

# View logs
tail -f logs/ktc_snapshot.log
tail -f logs/weekly_data_stdout.log
```

## Import Lock (Railway Safety)

```bash
# Create lock (prevents data jobs during Railway import)
touch data/.import_lock

# Remove lock when import completes
rm data/.import_lock

# Check if locked
ls data/.import_lock
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

## Dashboard Pages (12)

| Page | File | Function |
|------|------|----------|
| Player Intelligence | `1_Player_Analysis.py` | 4-tab deep dive (valuation, athletic, situation, history) |
| Dynasty Edge | `2_Dynasty_Edge_Scores.py` | Buy/sell signals with filtering |
| Trade Analyzer | `3_Trade_Analyzer.py` | ML-powered trade evaluation |
| League Analysis | `4_League_Analysis.py` | Sleeper roster analysis |
| Market Trends | `5_Market_Trends.py` | Value tracking over time |
| Graph Explorer | `6_Graph_Explorer.py` | Neo4j visualization |
| AI Chat (Thoth) | `7_Chat.py` | Natural language queries |
| Model Insights | `8_Model_Insights.py` | ML explainability, feature importance |
| Athletic Profiles | `9_Athletic_Profiles.py` | Combine data analysis |
| Contract Intel | `10_Contract_Intelligence.py` | NFL salary analysis |

## Troubleshooting

```bash
# Clear Streamlit cache
streamlit cache clear

# Check Neo4j connection
python -c "from neo4j import GraphDatabase; print('OK')"

# Verify data files exist
ls -la data/
```
