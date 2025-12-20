# Thoth - Claude Code Instructions

## Project Overview
Thoth - Dynasty fantasy football analysis platform using Neo4j graph database, KTC valuations, and Claude AI (BYOK). Named after the Egyptian god of wisdom and knowledge.

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
- Frontend: Cloudflare Pages (FREE, unlimited requests)
- Backend + DB: Railway Hobby ($5-10/mo)
- Auth: Supabase Free tier
- AI: BYOK (users provide own Anthropic API key)

### Production URLs
| Service | URL |
|---------|-----|
| Frontend (Cloudflare) | `https://dynastyedge.pages.dev` |
| Backend API | `https://dynasty-api-production.up.railway.app` |
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
- **Navigation**: 6 items (Dashboard, Players, Trade, Projections, Chat, Settings)
- **Dashboard**: 5-7 widgets per view
- **Tables**: 7 columns default, more in expandable section
- **Search Results**: 7 items initially, paginate rest
- **Forms**: Chunk into 5-7 field groups
- **Player Research Modal**: 7 collapsible sections

### Deployment Files
- `deploy/DEPLOYMENT.md` - Step-by-step deployment guide
- `deploy/Dockerfile` - Neo4j Docker image for Railway
- `deploy/railway.toml` - Railway configuration
- `deploy/secrets.toml.example` - Streamlit secrets template
- `deploy/exports/` - Database export files (Cypher)
- `scripts/export_neo4j.py` - Database export script

## Next.js Frontend

### Directory Structure
```
frontend/
├── app/
│   ├── page.tsx                    # Landing page (7 Miller's Law sections)
│   ├── layout.tsx                  # Root layout + AuthProvider
│   ├── globals.css                 # CSS vars, position colors, trends
│   ├── login/page.tsx              # Login page (Admin/Email modes)
│   ├── pricing/page.tsx            # 3-tier pricing comparison
│   └── (dashboard)/
│       ├── layout.tsx              # 6-item nav sidebar + user state
│       ├── page.tsx                # Dashboard (5 widgets)
│       ├── players/page.tsx        # Redirects to /rankings
│       ├── rankings/page.tsx       # Consolidated Players page with research modal
│       ├── trade/page.tsx          # Trade analyzer (5 max per side)
│       ├── projections/page.tsx    # Elite-gated projections
│       ├── chat/page.tsx           # Thoth AI with BYOK
│       └── settings/page.tsx       # API key management
├── components/
│   ├── ui/                         # shadcn-style components
│   │   ├── button.tsx              # Button with asChild support
│   │   ├── card.tsx                # Card variants (glass, premium, elevated)
│   │   ├── badge.tsx               # Position-colored badges
│   │   ├── dialog.tsx              # Radix Dialog primitive
│   │   └── input.tsx               # Input component
│   ├── player/
│   │   └── player-research-modal.tsx  # Player research breakdown modal
│   └── trade/
│       ├── elite-trade-report.tsx  # Elite trade analysis report
│       └── written-report-section.tsx  # AI-enhanced trade narrative
├── contexts/
│   └── auth-context.tsx            # Auth provider (admin bypass + Supabase)
├── lib/
│   ├── utils.ts                    # cn() utility
│   ├── api.ts                      # FastAPI client
│   ├── supabase.ts                 # Supabase client (lazy init)
│   └── byok.ts                     # BYOK key management
├── next.config.mjs                 # Static export config
├── tailwind.config.ts              # Thoth brand colors
├── wrangler.toml                   # Cloudflare Pages config
└── package.json                    # Next.js 14, Tailwind, Recharts
```

### Key Features Built
- **Miller's Law UI**: All elements follow 7±2 principle
- **Static Export**: `output: "export"` for Cloudflare Pages static hosting
- **BYOK Pattern**: API keys stored in localStorage, never on server
- **Auth System**: Admin bypass + Supabase integration for tier gating
- **Tier Gating**: Elite features require authentication
- **Light Theme**: Professional warm cream/gold theme with glass effects
- **Position Colors**: QB amber, RB emerald, WR sky, TE purple
- **Trend Indicators**: Rising/falling with color coding (emerald/rose)
- **Suspense Boundaries**: Proper handling for useSearchParams in static export
- **Player Research Modal**: Click any player row to see comprehensive breakdown

### Player Research Modal

Click any player row in the Players page to open a research modal with 7 sections:

1. **Header** - Name, position badge, team, age, grade, KTC value with trend
2. **Value Analysis** - Current value, 1yr/2yr/3yr projections, rank (default open)
3. **Production Metrics** - PPG, receiving/rushing stats, EPA, WOPR (default open)
4. **Dynasty Outlook** - Aging curve, peak window, ML projections
5. **Risk Assessment** - Injury burden, games missed, depth chart security
6. **Athletic Profile** - Combine metrics (collapsed by default)
7. **Draft Capital** - Round, pick, college (collapsed by default)

**Neo4j Data Sources**: KTCTrend, PlayerInjuryProfile, PlayerRoleProfile, PlayByPlayAggregates, HistoricalSeasonStats, CombineResult, DraftPick

**Files**:
- `frontend/components/player/player-research-modal.tsx` - Modal component
- `frontend/components/ui/dialog.tsx` - Radix Dialog primitive
- `backend/app/routers/players.py` - `/research` endpoint
- `backend/app/models/player.py` - `PlayerResearch` model

### Authentication

#### Admin Login (Testing)
For testing Elite features without Supabase:
1. Navigate to `/login`
2. Use Admin tab (default)
3. Password: `thoth2025elite`
4. Session lasts 24 hours (localStorage)

#### Auth Context Usage
```typescript
import { useAuth } from "@/contexts/auth-context";

function MyComponent() {
  const { user, isElite, isPro, loading, logout } = useAuth();

  if (loading) return <Loading />;
  if (!isElite) return <UpgradePrompt />;

  return <EliteContent />;
}
```

#### Supabase (Production)
When configured, auth uses Supabase:
- Email/password authentication
- User tier from `app_metadata.tier`
- Falls back to admin bypass when unavailable

### Theme Design
```css
/* Light theme CSS variables */
--background: 40 33% 98%;        /* Warm cream */
--foreground: 240 10% 10%;       /* Near black text */
--primary: 43 74% 42%;           /* Gold accent */
--card: 0 0% 100%;               /* White cards */
--secondary: 40 20% 94%;         /* Light secondary */

/* Glass effects */
.glass { background: white/70; backdrop-blur: xl; }
```

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

### Deploy to Cloudflare Pages
```bash
# First time: login to Cloudflare
npx wrangler login

# Deploy to Cloudflare Pages
npx wrangler pages deploy out --project-name=dynastyedge

# Or via Cloudflare dashboard: Direct Upload to dynastyedge project
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
GET  /api/v1/players/{id}/research  # Comprehensive player research (modal data)
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
GET  /api/v1/projections/model-info  # Stacked ensemble details (R²=0.80)
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
│         Stacked Ensemble (R² = 0.80, RMSE = 2.47 PPG)                │
├──────────────────────────────────────────────────────────────────────┤
│  Meta-Model: RidgeCV (learned weights, cv=5)                         │
│  ├── Feature Attention NN (Huber loss, R²=0.695)                    │
│  ├── LightGBM Gradient Boosting (800 est, R²=0.803)                 │
│  ├── Random Forest (300 est, R²=0.765)                              │
│  └── Ridge Regression (R²=0.707)                                    │
├──────────────────────────────────────────────────────────────────────┤
│  Training: 1999-2023 (10,596 samples, 168 features)                  │
│  Test: 2023 season only (maximize training data)                     │
│  Era-Normalized: Z-scores, percentiles for cross-era consistency     │
└──────────────────────────────────────────────────────────────────────┘
```

#### Key Optimizations
| Optimization | Impact | File |
|-------------|--------|------|
| Era-normalized features | Cross-era training consistency | `expanded_dataset_builder.py` |
| Extended training (1999-2023) | 10,596 samples vs 5,659 | `expanded_dataset_builder.py` |
| LightGBM tuning | GBM R²=0.803 (best component) | `train_optimized_models.py` |
| Stacking meta-model | Learned weights vs fixed | `train_optimized_models.py` |
| Single test year (2023) | More training data | `train_optimized_models.py` |

#### Extended Neo4j Features (80+ total)

**Base Features (54)**: Season stats, snap counts, NGS, combine, draft capital

**New Neo4j Features (December 2024)**:
| Source Node | Features Added |
|-------------|----------------|
| PlayByPlayAggregates | `epa_per_target`, `epa_per_carry`, `adot`, `wopr`, `rz_td_rate`, `gl_td_rate` |
| PlayerRoleProfile | `starter_rate`, `slot_rate`, `role_numeric`, `alignment_numeric` |
| GameWeather | `dome_game_pct`, `cold_game_pct`, `weather_favorability` |
| PlayerInjuryProfile | `injury_burden_score`, `overall_injury_risk_numeric` |
| KTCTrend | `trend_slope`, `ktc_momentum`, `value_signal_numeric`, `dip_opportunity` |

#### Connecting to Railway Neo4j

```bash
# Set environment variables for Railway Neo4j
export NEO4J_URI="bolt://sparkling-commitment-production.up.railway.app:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="dynastyedge2025"

# Or add to .env file
echo 'NEO4J_URI=bolt://sparkling-commitment-production.up.railway.app:7687' >> .env
echo 'NEO4J_USER=neo4j' >> .env
echo 'NEO4J_PASSWORD=dynastyedge2025' >> .env
```

#### Build Expanded Dataset (80+ features)

```bash
# Build full dataset from Railway Neo4j
python -m src.ml.expanded_dataset_builder

# Output: data/ml_training/expanded_season_projection.parquet
```

#### Training Commands
```bash
# Full training with Neo4j (80+ features, requires connection)
python scripts/train_optimized_models.py --compare-baseline

# Training with base dataset only (54 features, no Neo4j needed)
python scripts/train_optimized_models.py --use-base-dataset --compare-baseline

# Train specific position
python scripts/train_optimized_models.py --position QB

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
- Threshold: R² >= 0.75 required for deployment (temporal evaluation)
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

**Era-Normalized Extended Dataset (1999-2023):**

| Metric | Value |
|--------|-------|
| Training Samples | 9,414 player-seasons |
| Test Samples | 1,182 (2023 only) |
| Features | 168 |
| **Ensemble R²** | **0.801** |
| **RMSE** | **2.47 PPG** |
| MAE | 1.92 PPG |

**Component Model Performance:**
| Component | R² Score |
|-----------|----------|
| LightGBM | 0.803 |
| Random Forest | 0.765 |
| Ridge | 0.707 |
| Neural Network | 0.695 |
| **Stacked Ensemble** | **0.801** |

**Position-Specific R² (2023 test set):**
| Position | R² | Samples |
|----------|-----|---------|
| QB | 0.59 | ~50 |
| RB | 0.78 | ~300 |
| WR | 0.77 | ~400 |
| TE | 0.72 | ~150 |

**Era-Normalized Features Added:**
- `ppg_ppr_zscore`, `ppg_ppr_percentile` - Within-era PPG normalization
- `targets_zscore`, `receptions_zscore` - Usage normalization
- `snap_pct_zscore` - Opportunity normalization
- `sample_weight` - Time decay (0.92^years_ago)
- `yoy_ppg_change`, `yoy_targets_change` - Year-over-year deltas

### ML Pipeline Files
- `src/ml/expanded_dataset_builder.py` - Training dataset construction with era-normalized features
- `src/ml/neural_network_models.py` - NN architectures (FFN, LSTM, Attention, MultiTask)
- `src/ml/model_registry.py` - Model version tracking and management
- `src/ml/predict.py` - Inference pipeline
- `scripts/train_optimized_models.py` - Master training script (stacked ensemble)
- `scripts/train_improved_models.py` - Enhanced ensemble training
- `scripts/train_neural_networks.py` - Neural network training
- `scripts/update_neo4j_projections.py` - **NEW** Update Neo4j Player nodes with projections

#### Update Neo4j Projections
```bash
# Preview projections without updating
python scripts/update_neo4j_projections.py --dry-run

# Update all players (379 with KTC values)
python scripts/update_neo4j_projections.py

# Update specific position only
python scripts/update_neo4j_projections.py --position WR
```

Updates Player nodes with:
- `projected_ppg` - Points per game projection
- `projected_points` - Season total (17 games)
- `projection_confidence` - Model confidence (0-1)
- `projection_floor` / `projection_ceiling` - Range estimates
- `projection_updated` - Timestamp

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
