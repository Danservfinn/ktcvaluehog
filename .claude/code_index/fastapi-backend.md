---
title: FastAPI Backend API
link: fastapi-backend
type: code_index
ontological_relations: []
tags:
- fastapi
- api
- backend
- neo4j
created_at: 2025-12-17T00:00:00Z
updated_at: 2025-12-17T00:00:00Z
uuid: c3d4e5f6-a7b8-9012-cdef-345678901234
---

# FastAPI Backend API

## Directory Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py           # FastAPI app entry point
│   ├── config.py         # Settings (Pydantic Settings)
│   ├── database.py       # Neo4j HTTP client
│   ├── models/
│   │   ├── player.py     # Player Pydantic models
│   │   ├── trade.py      # Trade analysis models
│   │   └── response.py   # API response wrappers
│   └── routers/
│       ├── health.py     # Health check endpoints
│       ├── players.py    # Player search/profile
│       ├── signals.py    # Edge signals/buy-sell
│       └── trades.py     # Trade analyzer
├── requirements.txt
├── Dockerfile
└── .env.example
```

## API Endpoints

### Health
- `GET /api/v1/health` - Health check with DB status
- `GET /api/v1/health/ready` - Kubernetes readiness probe
- `GET /api/v1/health/live` - Kubernetes liveness probe

### Players
- `GET /api/v1/players/search` - Search with filters (position, team, age, ktc, signal)
- `GET /api/v1/players/{player_id}` - Full player profile
- `GET /api/v1/players/{player_id}/value-history` - KTC value history
- `POST /api/v1/players/compare` - Compare 2-5 players

### Signals
- `GET /api/v1/signals/edge` - All edge signals
- `GET /api/v1/signals/buy-targets` - Undervalued players
- `GET /api/v1/signals/sell-candidates` - Overvalued players
- `GET /api/v1/signals/breakout-candidates` - Young breakout potential
- `GET /api/v1/signals/production-leaders` - 2025 PPG leaders

### Trades
- `POST /api/v1/trades/analyze` - Analyze trade proposal
- `GET /api/v1/trades/targets` - Find trade targets by position/budget

## Running Locally

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

## Configuration

Environment variables (`.env`):
```
NEO4J_URL=https://sparkling-commitment-production.up.railway.app/db/neo4j/tx/commit
NEO4J_USER=neo4j
NEO4J_PASSWORD=dynastyedge2025
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
```

## Neo4j Connection

Uses HTTP Transaction API (not Bolt) since Railway doesn't expose TCP ports externally:

```python
# database.py
async with httpx.AsyncClient() as client:
    response = await client.post(
        NEO4J_URL,
        json={"statements": [{"statement": query, "parameters": params}]},
        auth=(user, password),
    )
```

## Models

### PlayerSummary
```python
class PlayerSummary(BaseModel):
    player_id: str
    name: str
    position: Position | None
    team: str | None
    age: float | None
    ktc_value: int | None
    signal: Signal | None
```

### TradeAnalysis
```python
class TradeAnalysis(BaseModel):
    give_side: TradeSide
    get_side: TradeSide
    ktc_differential: int
    recommendation: str  # ACCEPT, REJECT, FAIR
    confidence: float
    reasoning: str
```

## Deployment

Docker image for Railway:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```
