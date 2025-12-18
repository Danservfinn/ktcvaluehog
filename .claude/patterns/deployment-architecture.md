---
title: Production Deployment Architecture
link: deployment-architecture
type: patterns
ontological_relations: []
tags:
- deployment
- railway
- streamlit
- neo4j
- infrastructure
created_at: 2025-12-17T00:00:00Z
updated_at: 2025-12-17T00:00:00Z
uuid: a1b2c3d4-e5f6-7890-abcd-ef1234567890
---

# Production Deployment Architecture

## Overview

Dynasty Edge uses a hybrid cloud architecture optimized for cost (~$5-10/month):

```
┌─────────────────────────┐     ┌────────────────────────────┐
│   Streamlit Cloud       │────▶│   Railway (Neo4j)          │
│   (Free - Dashboard)    │     │   ($5-10/mo - Database)    │
│   share.streamlit.io    │     │   sparkling-commitment     │
└─────────────────────────┘     └────────────────────────────┘
         │                               │
         │ HTTPS                         │ HTTP API
         ▼                               ▼
    [Users/Browser]               [758K Nodes]
                                 [193K Relationships]
```

## Components

### Railway Neo4j
- **Project**: sparkling-commitment
- **Image**: neo4j:5.15-community with socat proxy
- **Memory**: 512MB page cache, 1GB heap
- **Storage**: Persistent volume at /data
- **Networking**: HTTP API exposed via Railway proxy (Bolt TCP not exposed)

### Streamlit Cloud
- **Host**: share.streamlit.io
- **Entry Point**: dashboard/app.py
- **Secrets**: Configured via Streamlit Cloud settings

## Connection Details

| Service | URL | Protocol |
|---------|-----|----------|
| Neo4j HTTP | `https://sparkling-commitment-production.up.railway.app` | HTTPS |
| Neo4j Browser | `https://sparkling-commitment-production.up.railway.app/browser/` | HTTPS |
| Transaction API | `https://sparkling-commitment-production.up.railway.app/db/neo4j/tx/commit` | HTTPS |

## Authentication
- **Username**: `neo4j`
- **Password**: `dynastyedge2025`

## Key Files

| File | Purpose |
|------|---------|
| `Dockerfile` | Neo4j image with socat proxy for Railway PORT |
| `railway.toml` | Railway deployment configuration |
| `deploy/DEPLOYMENT.md` | Step-by-step deployment guide |
| `deploy/secrets.toml.example` | Streamlit secrets template |
| `scripts/export_neo4j.py` | Database export to Cypher files |

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
| Railway | Hobby | $5-10 |
| Streamlit Cloud | Free | $0 |
| **Total** | | **~$5-10** |

## Deployment Commands

```bash
# Export local database
python scripts/export_neo4j.py

# Deploy to Railway
railway login
railway link -p sparkling-commitment
railway up --detach

# Check status
railway service status --all
railway logs
```

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
