# Dynasty Edge - Claude Code Instructions

## Project Overview
Dynasty fantasy football analysis platform using Neo4j graph database, KTC valuations, and Claude AI.

## Production Architecture

```
┌─────────────────────────┐     ┌────────────────────────────┐
│   Streamlit Cloud       │────▶│   Railway (Neo4j)          │
│   (Free - Dashboard)    │     │   ($5-10/mo - Database)    │
│   share.streamlit.io    │     │   sparkling-commitment     │
└─────────────────────────┘     └────────────────────────────┘
```

### Production URLs
| Service | URL |
|---------|-----|
| Neo4j HTTP | `https://sparkling-commitment-production.up.railway.app` |
| Neo4j Browser | `https://sparkling-commitment-production.up.railway.app/browser/` |
| Streamlit Dashboard | TBD (share.streamlit.io) |

### Production Credentials
- **Neo4j User**: `neo4j`
- **Neo4j Password**: `dynastyedge2025`
- Configure in Streamlit Cloud secrets (see `deploy/secrets.toml.example`)

### Deployment Files
- `deploy/DEPLOYMENT.md` - Step-by-step deployment guide
- `deploy/Dockerfile` - Neo4j Docker image for Railway
- `deploy/railway.toml` - Railway configuration
- `deploy/secrets.toml.example` - Streamlit secrets template
- `deploy/exports/` - Database export files (Cypher)
- `scripts/export_neo4j.py` - Database export script

## Knowledge Base Maintenance

This project uses `kb-claude` for structured documentation in `.claude/`. **When making code changes, update the relevant knowledge base entries.**

### IMPORTANT: Task Completion Checklist

**At the END of every task that modifies code, ALWAYS:**
1. Update relevant knowledge base entries
2. Run `kb-claude manifest` to regenerate the index
3. Explicitly list KB updates made in your response summary

Example task completion format:
```
## Knowledge Base Updated
- Added: `code_index/new-module.md` - Documents new module
- Updated: `cheatsheets/dashboard-commands.md` - Added new commands
- Manifest regenerated
```

### When to Update Knowledge Base

| Change Type | Action |
|-------------|--------|
| New file/module | Add entry to `code_index` |
| Bug fix with learnings | Add entry to `debug_history` |
| Architecture change | Update `patterns` entries |
| New command/script | Update `cheatsheets` |
| Answered a complex question | Add entry to `qa` |
| Implementation plan | Add entry to `plans` |

### Commands

```bash
# Create new entry
kb-claude new "Title" -t <type> -g <tag>

# Types: metadata, debug_history, qa, code_index, patterns, plans, cheatsheets, memory_anchors

# After changes, regenerate manifest
kb-claude manifest

# Validate entries
kb-claude validate
```

### Entry Template
When creating entries, include:
- Clear title describing the content
- Relevant tags (-g flag)
- Code snippets where applicable
- Links to related files

## Key Files

### Core Application
- `dashboard/app.py` - Streamlit web UI (multi-page)
- `thoth_agent.py` - Claude AI agent (Thoth branding)
- `src/database/queries.py` - Neo4j query utilities

### Data Ingestion Scripts
- `scripts/ingest_weather.py` - Game weather data (5,593 games, 2000-2020)
- `scripts/ingest_injuries.py` - Injury history data (49K reports, 2016-2024)
- `scripts/ingest_depth_charts.py` - Depth chart data (18K entries, 2023-2024)
- `scripts/process_ktc_timeseries.py` - KTC trend analysis (292 players)
- `scripts/fetch_ktc_data.py` - KTC snapshot fetching
- `scripts/fetch_sleeper_data.py` - Sleeper league data

### ML Pipeline
- `src/ml/expanded_dataset_builder.py` - Training dataset construction
- `src/ml/train_model.py` - Model training

## Neo4j Node Types

### Core Entities (700K+ total nodes)
| Node Type | Count | Description |
|-----------|-------|-------------|
| HistoricalSnapCount | 249,455 | Snap participation data |
| HistoricalWeeklyStats | 143,593 | Weekly game logs |
| KTCSnapshot | 52,013 | Dynasty valuations |
| InjuryReport | 49,484 | Injury history |
| Player | 25,312 | Player entities |
| HistoricalNGS | 24,068 | Next Gen Stats |
| DepthChartEntry | 18,496 | Depth chart positions |
| HistoricalSeasonStats | 14,182 | Season aggregates |
| CombineResult | 6,876 | Athletic testing |
| DraftPick | 6,640 | Draft capital |
| GameWeather | 5,593 | Weather conditions |
| PlayerInjuryProfile | 4,254 | Injury risk profiles |
| PlayerRoleProfile | 699 | Depth chart roles |
| KTCTrend | 292 | Value trend signals |

## Running the Project

```bash
# Dashboard
streamlit run dashboard/app.py

# Data refresh - Core
python scripts/fetch_ktc_data.py
python scripts/fetch_sleeper_data.py

# Data refresh - Extended sources
python scripts/ingest_weather.py
python scripts/ingest_injuries.py --years 2016 2017 2018 2019 2020 2021 2022 2023 2024
python scripts/ingest_depth_charts.py --years 2023 2024
python scripts/process_ktc_timeseries.py
```

## Environment Variables

### Local Development (`.env`)
```
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
ANTHROPIC_API_KEY=your-key
SLEEPER_LEAGUE_ID=your-league-id
```

### Production (Streamlit Cloud Secrets)
```toml
neo4j_uri = "bolt://sparkling-commitment-production.up.railway.app:7687"
neo4j_user = "neo4j"
neo4j_password = "dynastyedge2025"
ANTHROPIC_API_KEY = "your-key"
SLEEPER_LEAGUE_ID = "your-league-id"
```

## Database Management

### Export Local Database
```bash
# Full export (758K nodes, ~305MB)
python scripts/export_neo4j.py

# Sample export for testing
python scripts/export_neo4j.py --sample 1000

# Export specific labels
python scripts/export_neo4j.py --label Player Team Game
```

### Import to Production
The production database uses HTTP API for imports (Bolt TCP not exposed).
See `deploy/DEPLOYMENT.md` for import instructions.

### Betting Data
- `scripts/ingest_betting_data.py` - Import NFL betting data
- `data/betting/` - Betting datasets (Elo, spreads, O/U)
- 36,957 games with betting lines (1920-2025)
