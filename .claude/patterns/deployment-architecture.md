---
title: Production Deployment Architecture
link: deployment-architecture
type: patterns
ontological_relations: []
tags:
- deployment
- vercel
- railway
- nextjs
- fastapi
- neo4j
- supabase
- infrastructure
created_at: 2025-12-17T00:00:00Z
updated_at: 2025-12-18T00:00:00Z
uuid: a1b2c3d4-e5f6-7890-abcd-ef1234567890
---

# Production Deployment Architecture (v2)

## Overview

Thoth uses a modern JAMstack architecture with freemium monetization (~$5-15/month):

```
┌─────────────────────────────┐     ┌───────────────────────────────┐
│   Vercel                    │────▶│   Railway                      │
│   (FREE - Next.js Frontend) │     │   FastAPI + Neo4j ($5-15/mo)  │
│   thoth.vercel.app          │     │   sparkling-commitment         │
└─────────────────────────────┘     └───────────────────────────────┘
                                              │
                                              ▼
                                    ┌───────────────────────┐
                                    │   Supabase (FREE)     │
                                    │   Auth + User DB      │
                                    └───────────────────────┘
```

## Components

### Vercel (Frontend)
- **Framework**: Next.js 14 with static export
- **Host**: `https://frontend-jvxdlwhwi-dannys-projects-de68569e.vercel.app`
- **Cost**: FREE (generous limits)
- **Theme**: Light theme with warm cream/gold design
- **UI Design**: Miller's Law (7±2 items per view)

### Railway (Backend + Database)
- **API**: FastAPI with Neo4j integration
- **Database**: Neo4j 5.15-community
- **Project**: sparkling-commitment
- **Cost**: $5-15/mo (Hobby plan)

### Supabase (Auth)
- **Features**: User auth, session management, user preferences
- **Cost**: FREE tier
- **Integration**: JWT tokens for API auth

### AI (BYOK - Bring Your Own Key)
- Users provide their own Anthropic API key
- Stored securely in localStorage (never server-side)
- No AI costs for platform operator

## Connection Details

| Service | URL | Protocol |
|---------|-----|----------|
| Frontend | `https://frontend-jvxdlwhwi-dannys-projects-de68569e.vercel.app` | HTTPS |
| Backend API | `https://api.thoth.gg` (TBD) | HTTPS |
| Neo4j HTTP | `https://sparkling-commitment-production.up.railway.app` | HTTPS |
| Neo4j Browser | `https://sparkling-commitment-production.up.railway.app/browser/` | HTTPS |

## Neo4j Credentials
- **Username**: `neo4j`
- **Password**: `dynastyedge2025`

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

## Frontend Deployment

### Vercel Setup
```bash
# Install Vercel CLI
npm i -g vercel

# Deploy from frontend directory
cd frontend
vercel

# Or link to Git for automatic deploys
vercel link
```

### Environment Variables (Vercel Dashboard)
```
NEXT_PUBLIC_API_URL=https://api.thoth.gg
NEXT_PUBLIC_SUPABASE_URL=your-supabase-url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
```

## Backend Deployment

### Key Files

| File | Purpose |
|------|---------|
| `Dockerfile` | Neo4j image with socat proxy for Railway PORT |
| `railway.toml` | Railway deployment configuration |
| `deploy/DEPLOYMENT.md` | Step-by-step deployment guide |
| `deploy/secrets.toml.example` | Streamlit secrets template |
| `scripts/export_neo4j.py` | Database export to Cypher files |

### Railway Commands
```bash
# Login and link
railway login
railway link -p sparkling-commitment

# Deploy
railway up --detach

# Check status
railway service status --all
railway logs
```

## Data Import

Production uses HTTP Transaction API (Bolt TCP not exposed):

```python
import requests

url = 'https://sparkling-commitment-production.up.railway.app/db/neo4j/tx/commit'
auth = ('neo4j', 'dynastyedge2025')
headers = {'Content-Type': 'application/json'}

data = {'statements': [{'statement': 'MATCH (n) RETURN count(n)'}]}
resp = requests.post(url, json=data, auth=auth, headers=headers)
print(resp.json())
```

## Cost Breakdown

| Service | Plan | Monthly Cost |
|---------|------|--------------|
| Vercel | Free | $0 |
| Railway | Hobby | $5-10 |
| Supabase | Free | $0 |
| **Total** | | **~$5-10** |

## Troubleshooting

### HTTP 502 Error
- Neo4j needs ~30 seconds to start
- Check `railway logs` for startup errors
- Verify socat proxy is forwarding PORT to 7474

### Authentication Failed
- Default password `neo4j` requires change on first start
- Use HTTP API to change: `ALTER CURRENT USER SET PASSWORD`

### Import Slow
- HTTP API is slower than Bolt (~100 nodes/sec)
- Full 758K node import takes ~2 hours
- Consider importing essential data first (Player, Team, Game)

### Vercel Build Errors
- Ensure `output: "export"` in next.config.mjs
- Add Suspense boundaries around useSearchParams
- Check for missing environment variables
