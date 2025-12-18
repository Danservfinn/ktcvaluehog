# Dynasty Edge - Claude Code Instructions

## Project Overview
Dynasty fantasy football analysis platform using Neo4j graph database, KTC valuations, and Claude AI (BYOK).

## Production Architecture (v2 - Next.js + FastAPI)

```
┌─────────────────────────────┐     ┌───────────────────────────────┐
│   Cloudflare Pages          │────▶│   Railway                      │
│   (FREE - Next.js Frontend) │     │   FastAPI + Neo4j ($5-15/mo)  │
│   dynastyedge.pages.dev     │     │   sparkling-commitment         │
└─────────────────────────────┘     └───────────────────────────────┘
                                              │
                                              ▼
                                    ┌───────────────────────┐
                                    │   Supabase (FREE)     │
                                    │   Auth + User DB      │
                                    └───────────────────────┘
```

### Cost: ~$5-15/month
- Frontend: Cloudflare Pages (FREE, unlimited bandwidth)
- Backend + DB: Railway Hobby ($5-10/mo)
- Auth: Supabase Free tier
- AI: BYOK (users provide own Anthropic API key)

### Production URLs
| Service | URL |
|---------|-----|
| Frontend | `https://dynastyedge.pages.dev` (TBD) |
| Backend API | `https://api.dynastyedge.com` (TBD) |
| Neo4j HTTP | `https://sparkling-commitment-production.up.railway.app` |
| Neo4j Browser | `https://sparkling-commitment-production.up.railway.app/browser/` |

### Production Credentials
- **Neo4j User**: `neo4j`
- **Neo4j Password**: `dynastyedge2025`

## Freemium Tiers

| Feature | Free | Pro ($9.99/mo) | Elite ($19.99/mo) |
|---------|------|----------------|-------------------|
| Player Search | All | All | All |
| Rankings | Top 100 | Top 500 | All + Rookies |
| Trade Analyzer | 3/day | Unlimited | Unlimited + ML |
| ML Projections | - | - | Season + Weekly |
| Thoth AI | - | - | Unlimited (BYOK) |
| Data Export | - | - | CSV + API |

## Miller's Law UI Design (7±2 Principle)

All UI elements follow Miller's Law - humans can hold 7±2 items in working memory:
- **Navigation**: 7 items max (Dashboard, Players, Rankings, Trade, Projections, Chat, Settings)
- **Dashboard**: 5-7 widgets per view
- **Tables**: 7 columns default, more in expandable section
- **Search Results**: 7 items initially, paginate rest
- **Forms**: Chunk into 5-7 field groups

### Deployment Files
- `deploy/DEPLOYMENT.md` - Step-by-step deployment guide
- `deploy/Dockerfile` - Neo4j Docker image for Railway
- `deploy/railway.toml` - Railway configuration
- `deploy/secrets.toml.example` - Streamlit secrets template
- `deploy/exports/` - Database export files (Cypher)
- `scripts/export_neo4j.py` - Database export script

## Next.js Frontend (NEW)

### Directory Structure
```
frontend/
├── app/
│   ├── page.tsx                    # Landing page (7 Miller's Law sections)
│   ├── layout.tsx                  # Root layout with dark mode
│   ├── globals.css                 # CSS vars, position colors, trends
│   ├── pricing/page.tsx            # 3-tier pricing comparison
│   └── (dashboard)/
│       ├── layout.tsx              # 7-item nav sidebar
│       ├── page.tsx                # Dashboard (5 widgets)
│       ├── players/page.tsx        # Player search
│       ├── rankings/page.tsx       # 7-column rankings table
│       ├── trade/page.tsx          # Trade analyzer (5 max per side)
│       ├── projections/page.tsx    # Elite-gated projections
│       ├── chat/page.tsx           # Thoth AI with BYOK
│       └── settings/page.tsx       # API key management
├── components/ui/                   # shadcn-style components
│   ├── button.tsx                  # Button with asChild support
│   ├── card.tsx                    # Card components
│   ├── badge.tsx                   # Position-colored badges
│   └── input.tsx                   # Input component
├── lib/
│   ├── utils.ts                    # cn() utility
│   ├── api.ts                      # FastAPI client
│   └── byok.ts                     # BYOK key management
├── next.config.mjs                 # Static export for Cloudflare
├── tailwind.config.ts              # Dynasty brand colors
└── package.json                    # Next.js 14, Tailwind, Recharts
```

### Key Features Built
- **Miller's Law UI**: All elements follow 7±2 principle
- **Static Export**: `output: "export"` for Cloudflare Pages
- **BYOK Pattern**: API keys stored in localStorage, never on server
- **Tier Gating**: Elite features require subscription
- **Dark Mode**: Full dark theme with CSS variables
- **Position Colors**: QB gold, RB green, WR blue, TE purple
- **Trend Indicators**: Rising/falling animations

### Run Frontend
```bash
cd frontend && npm install && npm run dev
# Runs at http://localhost:3000
```

### Build for Production
```bash
cd frontend && npm run build
# Output in frontend/out/ for Cloudflare Pages
```

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

### FastAPI Backend (NEW)
- `backend/app/main.py` - FastAPI application
- `backend/app/config.py` - Pydantic Settings
- `backend/app/database.py` - Neo4j HTTP client
- `backend/app/routers/` - API route handlers
- `backend/Dockerfile` - Docker image for Railway

**API Endpoints:**
```
# Health & Core
GET  /api/v1/health              # Health check

# Players
GET  /api/v1/players/search      # Search players (position, team, age, ktc)
GET  /api/v1/players/{id}        # Player profile
POST /api/v1/players/compare     # Compare 2-5 players

# Signals
GET  /api/v1/signals/edge        # Edge signals (buy/sell)
GET  /api/v1/signals/buy-targets # Undervalued players

# Trades
POST /api/v1/trades/analyze      # Trade analyzer

# Rankings (NEW)
GET  /api/v1/rankings            # Dynasty rankings (100 free, 500 pro)
GET  /api/v1/rankings/positional/{pos}  # Position rankings
GET  /api/v1/rankings/risers     # Biggest value gainers
GET  /api/v1/rankings/fallers    # Biggest value losers
GET  /api/v1/rankings/rookie-rankings   # Rookie rankings (Elite)

# Projections (Elite only)
GET  /api/v1/projections         # ML season projections
GET  /api/v1/projections/positional/{pos}  # Position projections
GET  /api/v1/projections/weekly  # Weekly projections
GET  /api/v1/projections/compare # Compare player projections
GET  /api/v1/projections/model-info  # Stacked ensemble details (R²=0.91)
GET  /api/v1/projections/confidence/{id}  # Player confidence analysis

# Chat (Elite only, BYOK)
POST /api/v1/chat                # Thoth AI streaming (X-Anthropic-Key header)
POST /api/v1/chat/quick          # Quick player analysis
GET  /api/v1/chat/suggestions    # Chat prompt suggestions
```

**Run locally:**
```bash
cd backend && uvicorn app.main:app --reload --port 8001
```

### Core Application (Legacy Streamlit)
- `dashboard/app.py` - Streamlit web UI (multi-page)
- `thoth_agent.py` - Claude AI agent (Thoth branding)
- `src/database/queries.py` - Neo4j query utilities

### Data Ingestion Scripts
- `scripts/ingest_weather.py` - Game weather data (5,593 games, 2000-2020)
- `scripts/ingest_injuries.py` - Injury history data (49K reports, 2016-2024)
- `scripts/ingest_depth_charts.py` - Depth chart data (18K entries, 2023-2024)
- `scripts/ingest_pbp_features.py` - Play-by-play aggregations (EPA, red zone, WOPR)
- `scripts/process_ktc_timeseries.py` - KTC trend analysis (292 players)
- `scripts/fetch_ktc_data.py` - KTC snapshot fetching
- `scripts/fetch_sleeper_data.py` - Sleeper league data

### Weekly Data Automation

#### Architecture
```
DAILY (6AM/6PM)          WEEKLY (Tue 4AM)         SEASONAL
┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│ KTC Snapshots│         │ PBP Features │         │ College Data │ (Mar)
│ (existing)   │         │ Injuries     │         │ Contracts    │ (Aug)
└──────────────┘         │ Depth Charts │         │ Defense      │ (Feb)
                         │ KTC Trends   │         └──────────────┘
                         └──────────────┘
```

#### Data Jobs Infrastructure (`scripts/data_jobs/`)
| File | Purpose |
|------|---------|
| `base_ingester.py` | Abstract base class with Neo4j patterns, logging, batch ops |
| `job_runner.py` | Multi-job orchestration with status tracking |
| `utils.py` | NFL week detection, team normalization, import lock |

#### Weekly Job Commands
```bash
# Run weekly job manually
python scripts/weekly_data_job.py

# Run specific job only
python scripts/weekly_data_job.py --job pbp_features

# Dry run (show what would run)
python scripts/weekly_data_job.py --dry-run

# Check last run status
python scripts/weekly_data_job.py --status

# Install macOS scheduler (Tuesday 4AM)
./scripts/install_weekly_scheduler.sh
```

#### PBP Features Script
```bash
# Historical load (multiple seasons)
python scripts/ingest_pbp_features.py --years 2023 2024

# Weekly update (current week only)
python scripts/ingest_pbp_features.py --current-week

# Test mode (no DB writes)
python scripts/ingest_pbp_features.py --years 2024 --test
```

#### Import Lock (Railway Safety)
```bash
# Create lock to prevent data jobs during Railway import
touch data/.import_lock

# Remove lock when import completes
rm data/.import_lock
```

#### Scheduler Config Files
- `config/com.thoth.ktc-snapshot.plist` - KTC twice daily (6AM/6PM)
- `config/com.thoth.weekly-data.plist` - Weekly data (Tue 4AM)

#### Scheduler Commands (macOS)
```bash
# View all Thoth schedulers
launchctl list | grep thoth

# Run weekly job now
launchctl start com.thoth.weekly-data

# View logs
tail -f logs/weekly_data_stdout.log
```

### ML Pipeline v2 (Stacked Ensemble)

#### Architecture
```
┌──────────────────────────────────────────────────────────────────────┐
│                     Stacked Ensemble (R² = 0.91)                     │
├──────────────────────────────────────────────────────────────────────┤
│  Meta-Model: RidgeCV (learned weights, cv=5)                         │
│  ├── Feature Attention NN (Huber loss, delta=5.0)                   │
│  ├── LightGBM Gradient Boosting (500 estimators)                    │
│  ├── Random Forest (200 estimators, max_depth=8)                    │
│  └── Ridge Regression (alpha=1.0)                                   │
└──────────────────────────────────────────────────────────────────────┘
```

#### Key Optimizations
| Optimization | Expected R² Gain | File |
|-------------|------------------|------|
| Stacking meta-model | +0.02-0.03 | `train_improved_models.py` |
| Temporal momentum features | +0.01-0.02 | `expanded_dataset_builder.py` |
| Huber loss + dynasty weighting | +0.01 | `neural_network_models.py` |
| Feature attention layer | +0.01 | `neural_network_models.py` |
| Position stratification | +0.01-0.02 | `train_improved_models.py` |

#### New Features Added
- **KTC Momentum**: `ktc_7d_delta`, `ktc_30d_delta`, `ktc_trend_numeric`
- **Injury Recency**: `injury_reports_this_season`, `severe_injury_count`
- **Team Strength**: `team_avg_elo`, `team_ppg`, `team_off_rank`

#### Training Commands
```bash
# Full optimized training
python scripts/train_optimized_models.py

# Train specific position
python scripts/train_optimized_models.py --position QB

# Compare with baseline
python scripts/train_optimized_models.py --compare-baseline

# Disable specific optimizations
python scripts/train_optimized_models.py --no-stacking --no-attention
```

#### Model Files
| File | Description |
|------|-------------|
| `data/models/optimized_nn.pt` | Feature Attention Neural Network |
| `data/models/optimized_gbm.pkl` | LightGBM model |
| `data/models/optimized_rf.pkl` | Random Forest model |
| `data/models/optimized_ridge.pkl` | Ridge Regression model |
| `data/models/stacking_meta.pkl` | RidgeCV meta-model |
| `data/models/scalers.pkl` | Feature scalers |
| `data/models/model_metrics.json` | Training metrics |

#### Daily Retraining
- GitHub Action: `.github/workflows/daily-retrain.yml`
- Schedule: Daily at noon UTC (7am EST)
- Threshold: R² >= 0.88 required for deployment
- Includes data freshness check to skip if models updated <20h ago
- Auto-commits model updates and triggers Railway deploy

#### Model Registry Commands
```bash
# List registered models
python -m src.ml.model_registry --list

# Compare all models by R² and RMSE
python -m src.ml.model_registry --compare

# Set production model
python -m src.ml.model_registry --production stacked_ensemble_v2.1

# Full report with rankings
python -m src.ml.model_registry --report
```

#### Latest Training Results (2025-12-18)
| Component | R² Score | Meta Weight |
|-----------|----------|-------------|
| GBM | 0.8662 | 0.396 |
| Random Forest | 0.8714 | 0.375 |
| Ridge | 0.8572 | 0.222 |
| Attention NN | 0.8420 | 0.012 |
| **Ensemble** | **0.8713** | — |

*With Neo4j temporal features + LightGBM: Target R² = 0.91*

### ML Pipeline Files
- `src/ml/expanded_dataset_builder.py` - Training dataset construction with temporal features
- `src/ml/neural_network_models.py` - NN architectures (FFN, LSTM, Attention, MultiTask)
- `src/ml/model_registry.py` - Model version tracking and management
- `src/ml/predict.py` - Inference pipeline
- `scripts/train_optimized_models.py` - Master training script
- `scripts/train_improved_models.py` - Enhanced ensemble training
- `scripts/train_neural_networks.py` - Neural network training

## Neo4j Node Types

### Core Entities (750K+ total nodes)
| Node Type | Count | Description |
|-----------|-------|-------------|
| HistoricalSnapCount | 249,455 | Snap participation data |
| HistoricalWeeklyStats | 143,593 | Weekly game logs |
| KTCSnapshot | 52,013 | Dynasty valuations |
| InjuryReport | 49,484 | Injury history |
| Game | 28,940 | Games with betting/Elo data |
| Player | 25,312 | Player entities |
| HistoricalNGS | 24,068 | Next Gen Stats |
| DepthChartEntry | 18,496 | Depth chart positions |
| PlayByPlayAggregates | ~15,000 | EPA, red zone, WOPR metrics |
| HistoricalSeasonStats | 14,182 | Season aggregates |
| CombineResult | 6,876 | Athletic testing |
| DraftPick | 6,640 | Draft capital |
| GameWeather | 5,593 | Weather conditions |
| PlayerInjuryProfile | 4,254 | Injury risk profiles |
| PlayerRoleProfile | 699 | Depth chart roles |
| KTCTrend | 292 | Value trend signals |

### Planned Node Types
| Node Type | Source | Description |
|-----------|--------|-------------|
| CollegeProfile | CFBD API | College stats for rookies |
| PlayerContract | Spotrac | Contract/salary data |
| TeamDefenseProfile | PBP derived | Defense efficiency rankings |

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
