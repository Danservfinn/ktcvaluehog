---
title: Data Pipeline Architecture
link: data-pipeline-architecture
type: patterns
ontological_relations: []
tags:
- architecture
- neo4j
- data-pipeline
created_at: 2025-12-17T16:14:23Z
updated_at: 2025-12-17T16:14:23Z
uuid: 195655a9-6ab4-4b70-a6cd-b6a1033c37d3
---

# Data Pipeline Architecture

## Overview
Dynasty Edge uses a multi-layer architecture combining graph databases, temporal tracking, and AI agents.

## Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    DATA COLLECTION (Twice Daily)                │
│  GitHub Actions → fetch_ktc_data.py, fetch_sleeper_data.py      │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    NEO4J GRAPH DATABASE                          │
│  Nodes: Player, Team, DraftPick, TemporalSnapshot               │
│  Edges: PLAYS_FOR, TARGETS, HANDOFFS, VALUE_AT                  │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    VALUATION ENGINE                              │
│  valuation_model.py → aging curves + scarcity multipliers       │
│  Edge Score = Our Value - KTC Value (buy/sell signals)          │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AI LAYER                                      │
│  Claude Agent → Conversational analysis                          │
│  AI DS Team → Feature engineering, EDA, ML training             │
└─────────────────────────────────────────────────────────────────┘
```

## Key Patterns

### 1. Temporal Snapshots
- Store player values at each time point in Neo4j
- Query: `MATCH (p:Player)-[r:VALUE_AT]->(s:Snapshot) RETURN p, r, s`
- Enables tracking value changes over time

### 2. Edge Scoring
- Calculate independent valuation using `valuation_model.py`
- Compare to KTC crowdsourced values
- Positive edge = undervalued (BUY), Negative edge = overvalued (SELL)

### 3. Graph Relationships
- QB→WR target connections weighted by target share
- RB→QB handoff relationships
- Team → Player depth chart positions

### 4. Caching Strategy
- Streamlit `@st.cache_data(ttl=300)` for 5-minute data caching
- Neo4j query results cached at application layer
