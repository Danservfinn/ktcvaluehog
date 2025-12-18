---
title: Platform Launch v2 - Next.js + FastAPI
link: platform-launch-v2
type: plans
ontological_relations: []
tags:
- deployment
- nextjs
- fastapi
- freemium
- millers-law
created_at: 2025-12-17T00:00:00Z
updated_at: 2025-12-17T00:00:00Z
uuid: b2c3d4e5-f6a7-8901-bcde-f234567890ab
---

# Platform Launch v2 - Next.js + FastAPI

## Overview

Transform Dynasty Edge from Streamlit to a production-ready SaaS platform with:
- **Next.js 14** frontend on Cloudflare Pages (FREE)
- **FastAPI** backend on Railway ($5-10/mo)
- **Neo4j** graph database (existing Railway deployment)
- **Supabase** for auth (FREE)
- **BYOK** (Bring Your Own Key) for Claude AI

## Architecture

```
Frontend (Cloudflare Pages) → FastAPI (Railway) → Neo4j (Railway)
                                    ↓
                            Supabase (Auth)
```

## Cost: ~$5-15/month

| Service | Cost |
|---------|------|
| Cloudflare Pages | $0 |
| Railway (FastAPI + Neo4j) | $5-10 |
| Supabase Auth | $0 |
| BYOK Claude | $0 |

## Freemium Tiers

| Feature | Free | Pro ($9.99) | Elite ($19.99) |
|---------|------|-------------|----------------|
| Rankings | Top 100 | Top 500 | All |
| Trade Analyzer | 3/day | Unlimited | + ML |
| ML Projections | - | - | Yes |
| Thoth AI | - | - | BYOK |
| Data Export | - | - | CSV + API |

## Miller's Law UI (7±2 Principle)

- Navigation: 7 items max
- Dashboard: 5-7 widgets
- Tables: 7 columns default
- Search: 7 results per page
- Forms: 5-7 fields per group

## Key Files

### Frontend (`frontend/`)
- `app/page.tsx` - Landing page
- `app/(dashboard)/page.tsx` - Dashboard
- `app/(dashboard)/players/page.tsx` - Player search
- `app/(dashboard)/rankings/page.tsx` - Rankings
- `app/(dashboard)/trade/page.tsx` - Trade analyzer
- `app/(dashboard)/chat/page.tsx` - Thoth AI (Elite)
- `components/` - shadcn/ui components

### Backend (`backend/`)
- `app/main.py` - FastAPI entry
- `app/routers/` - API endpoints
- `app/services/neo4j.py` - Database client

## Data Automation

- **Daily**: KTC refresh (6 AM, 6 PM UTC)
- **Weekly**: ML model retrain (Sundays)
- **GitHub Actions**: Automated pipelines

## Related Files
- `.claude/patterns/deployment-architecture.md` - Deployment details
- `.claude/patterns/data-pipeline-architecture.md` - Data pipelines
- `CLAUDE.md` - Project overview
