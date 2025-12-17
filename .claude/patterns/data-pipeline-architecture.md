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

# Thoth Platform Architecture

## Overview
Thoth is a modular dynasty fantasy platform with ML-powered valuations, a 14-tool AI agent, and a 12-page dashboard.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    DATA COLLECTION (Twice Daily)                │
│  GitHub Actions → KTC, Sleeper, NFLverse (combine, contracts)   │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FEATURE ENGINEERING (src/features/)          │
│  40+ features: athletic, contract, production, situational      │
│  src/loaders/ → ID resolution, NFLverse enrichment              │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    NEO4J GRAPH DATABASE (src/database/)         │
│  3,700+ players with unified schema                             │
│  Cypher queries via src/database/queries.py                     │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ML VALUATION (src/ml/)                       │
│  Gradient Boosting (R²=0.87) → Edge scoring                     │
│  Model vs KTC = Buy/Sell signals                                │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                           │
│  dashboard/ → 12-page Streamlit app                             │
│  thoth_agent.py → 14-tool CLI agent                             │
└─────────────────────────────────────────────────────────────────┘
```

## Module Structure (`src/`)

| Module | Responsibility |
|--------|----------------|
| `src/loaders/` | Data ingestion (KTC, NFLverse, ID mapping) |
| `src/features/` | Feature engineering (40+ features) |
| `src/database/` | Neo4j client, schema, queries |
| `src/ml/` | Model training and prediction |
| `src/agent/` | Thoth AI tool implementations |
| `src/api/` | External API clients (Sleeper, injuries) |
| `src/validation/` | Backtesting framework |

## Key Patterns

### 1. ML-Powered Edge Scoring
- Train on 40 features → predict `ktc_value`
- Edge = Model Prediction - KTC Market Value
- Signal thresholds: ±7% (buy/sell), ±15% (strong)

### 2. Unified Player Schema
- Single Neo4j node type with all 40+ properties
- ID resolution across KTC, Sleeper, NFL, ESPN, PFF

### 3. Multi-Page Dashboard
- `dashboard/app.py` - Entry point
- `dashboard/pages/` - 10 analysis pages
- `dashboard/components/` - Shared UI (design_system, tooltips)

### 4. Tool-Based Agent
- 14 specialized tools in `src/agent/enhanced_tools.py`
- Claude orchestrates tool selection
- Each tool returns structured data for LLM interpretation
