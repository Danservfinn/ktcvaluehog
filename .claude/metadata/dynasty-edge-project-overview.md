---
title: Dynasty Edge Project Overview
link: dynasty-edge-project-overview
type: metadata
ontological_relations: []
tags:
- dynasty
- fantasy-football
- ktc
created_at: 2025-12-17T16:13:54Z
updated_at: 2025-12-17T16:13:54Z
uuid: 183a9104-1aab-4e3c-831f-f7da99405e7f
---

# Dynasty Edge - AI-Powered Dynasty Fantasy Football Platform

## Purpose
Maximize KTC (KeepTradeCut) roster value using graph intelligence, temporal causality tracking, and automated AI analysis.

## Core Components

| Component | File | Description |
|-----------|------|-------------|
| Dashboard | `dashboard.py` | Streamlit web UI with player rankings, trade analyzer, roster analysis |
| Valuation Model | `valuation_model.py` | Independent player valuations with aging curves and scarcity multipliers |
| Neo4j Integration | `setup_neo4j.py` | Graph database for player relationships and temporal snapshots |
| Claude AI Agent | `dynasty_agent_enhanced.py` | Conversational interface for analysis |
| NFL Data | `nfl_data_integration.py` | Integration with nflverse for stats |
| AI DS Team | `ai_ds_team_integration.py` | Feature engineering, EDA, and ML agents |

## Data Sources
- **KTC**: KeepTradeCut crowdsourced player values
- **Sleeper**: League rosters, standings, draft picks via API
- **NFLverse**: Weekly stats, snap counts, Next Gen Stats

## League Settings (Lucid Losers)
- 10-team Superflex PPR
- TE Premium (+0.5 PPR)
- 28-player rosters

## Key Directories
- `data/` - Raw CSV data files
- `scripts/` - Data fetching scripts
- `pipelines/` - Data processing pipelines
- `src/` - Source modules
