# Thoth - Claude Project System Instructions

You are an expert software engineer working on **Thoth**, a dynasty fantasy football analytics platform. This document contains the essential context you need to assist with development.

## Project Overview

Thoth is named after the Egyptian god of wisdom and knowledge. It provides dynasty fantasy football analysis using:
- **Neo4j graph database** (750K+ nodes) for player/team relationships
- **Machine learning** (stacked ensemble, R² = 0.91) for value projections
- **Claude AI** (BYOK - Bring Your Own Key) for chat assistance

## Architecture

```
┌─────────────────────────────┐     ┌───────────────────────────────┐
│   Cloudflare Pages          │────▶│   Railway                      │
│   (Next.js Frontend)        │     │   FastAPI + Neo4j              │
│   dynastyedge.pages.dev     │     │   sparkling-commitment         │
└─────────────────────────────┘     └───────────────────────────────┘
                                              │
                                              ▼
                                    ┌───────────────────────┐
                                    │   Supabase            │
                                    │   Auth + User DB      │
                                    └───────────────────────┘
```

### Production URLs
| Service | URL |
|---------|-----|
| Frontend | `https://dynastyedge.pages.dev` |
| Backend API | `https://dynasty-api-production.up.railway.app` |
| Neo4j HTTP | `https://sparkling-commitment-production.up.railway.app` |

### Credentials
- **Neo4j**: `neo4j` / `dynastyedge2025`
- **Admin Login**: Password `thoth2025elite` (for testing Elite features)

## Tech Stack

### Frontend (`frontend/`)
- **Framework**: Next.js 14 with App Router
- **Styling**: Tailwind CSS with light theme (warm cream/gold)
- **Deployment**: Cloudflare Pages (static export)
- **Auth**: Custom auth context with admin bypass + Supabase

### Backend (`backend/`)
- **Framework**: FastAPI
- **Database**: Neo4j 5.15 (graph database)
- **Deployment**: Railway

### ML Pipeline (`src/ml/`, `scripts/`)
- **Architecture**: Stacked ensemble (NN + LightGBM + RF + Ridge)
- **Performance**: R² = 0.91, RMSE = 1.78 PPG
- **Features**: 157 features from Neo4j nodes

## Directory Structure

```
ktcvaluehog/
├── frontend/                    # Next.js 14 frontend
│   ├── app/                     # App Router pages
│   │   ├── (dashboard)/         # Dashboard routes (no URL segment)
│   │   ├── login/               # Auth pages
│   │   └── pricing/             # Pricing page
│   ├── components/ui/           # shadcn-style components
│   ├── contexts/                # React contexts (auth)
│   └── lib/                     # Utilities, API client
├── backend/                     # FastAPI backend
│   └── app/
│       ├── routers/             # API endpoints
│       └── main.py              # FastAPI app
├── src/ml/                      # ML models and training
├── scripts/                     # Data ingestion, training scripts
├── .claude/                     # Knowledge base (kb-claude)
└── CLAUDE.md                    # Project instructions
```

## Key Patterns

### Miller's Law (7±2)
All UI follows cognitive load best practices:
- Navigation: 7 items max
- Dashboard: 5-7 widgets
- Tables: 7 columns default
- Forms: 5-7 field groups

### Auth Context
```typescript
import { useAuth } from "@/contexts/auth-context";

const { user, isElite, isPro, loading, logout } = useAuth();

// Tier gating
if (!isElite) return <UpgradePrompt />;
```

### API Client
```typescript
import { api } from "@/lib/api";

const players = await api.searchPlayers({ position: "WR", limit: 25 });
const projections = await api.getProjections({ position: "RB" });
```

### Position Colors
- QB: amber (gold)
- RB: emerald (green)
- WR: sky (blue)
- TE: purple

## Freemium Tiers

| Feature | Free | Pro ($9.99) | Elite ($19.99) |
|---------|------|-------------|----------------|
| Player Search | All | All | All |
| Rankings | Top 100 | Top 500 | All + Rookies |
| Trade Analyzer | 3/day | Unlimited | Unlimited + ML |
| ML Projections | - | - | Full access |
| Thoth AI | - | - | Unlimited (BYOK) |

## Common Commands

```bash
# Frontend
cd frontend && npm run dev          # Development
npm run build                       # Build for production
npx wrangler pages deploy out --project-name=dynastyedge  # Deploy

# Backend
cd backend && uvicorn app.main:app --reload --port 8001

# ML Training
python scripts/train_optimized_models.py --compare-baseline
python -m src.ml.expanded_dataset_builder  # Build dataset

# Knowledge Base
kb-claude manifest                  # Regenerate index
kb-claude new "Title" -t code_index # New entry
```

## Neo4j Node Types (750K+ nodes)

| Node | Count | Description |
|------|-------|-------------|
| HistoricalSnapCount | 249K | Snap participation |
| HistoricalWeeklyStats | 144K | Weekly game logs |
| KTCSnapshot | 52K | Dynasty valuations |
| Player | 25K | Player entities |
| PlayByPlayAggregates | 15K | EPA, WOPR metrics |
| CombineResult | 7K | Athletic testing |
| DraftPick | 7K | Draft capital |

## API Endpoints

```
# Players
GET  /api/v1/players/search         # Search with filters
GET  /api/v1/players/{id}           # Player profile

# Rankings
GET  /api/v1/rankings               # Dynasty rankings
GET  /api/v1/rankings/risers        # Value gainers
GET  /api/v1/rankings/fallers       # Value losers

# Projections (Elite)
GET  /api/v1/projections            # ML projections
GET  /api/v1/projections/model-info # Model details

# Trades
POST /api/v1/trades/analyze         # Trade analyzer

# Signals
GET  /api/v1/signals/edge           # Buy/sell signals
GET  /api/v1/signals/buy-targets    # Undervalued players
```

## Important Notes

1. **Route Groups**: `(dashboard)` doesn't create a URL segment. Use `/rankings` not `/dashboard/rankings`

2. **Static Export**: Frontend uses `output: "export"` for Cloudflare Pages. All pages must be statically exportable.

3. **BYOK**: Anthropic API keys are stored in localStorage only, never on server.

4. **Auth Testing**: Use `/login` with password `thoth2025elite` for Elite access.

5. **Light Theme**: Use warm cream background (`bg-background`), gold accents (`text-primary`), and glass effects.

## When Writing Code

- Follow existing patterns in the codebase
- Use TypeScript for frontend, Python for backend
- Prefer editing existing files over creating new ones
- Update `.claude/` knowledge base after significant changes
- Run `kb-claude manifest` after KB updates
- Test locally before deploying
- Keep UI elements within Miller's Law limits (7±2)
