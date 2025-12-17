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

# Thoth - AI-Powered Dynasty Fantasy Football Platform

## Purpose
Maximize KTC (KeepTradeCut) roster value using graph intelligence, ML-powered valuations (R²=0.87), and a 14-tool AI agent.

## Platform Architecture

### Dashboard (12 Pages)
| Page | File | Description |
|------|------|-------------|
| Player Intelligence | `dashboard/pages/1_Player_Analysis.py` | 4-tab analysis: valuation, athletic, situation, history |
| Dynasty Edge Scores | `dashboard/pages/2_Dynasty_Edge_Scores.py` | Buy/sell signals with filtering |
| Trade Analyzer | `dashboard/pages/3_Trade_Analyzer.py` | ML-powered trade evaluation |
| League Analysis | `dashboard/pages/4_League_Analysis.py` | Sleeper integration |
| Market Trends | `dashboard/pages/5_Market_Trends.py` | Value tracking over time |
| Graph Explorer | `dashboard/pages/6_Graph_Explorer.py` | Neo4j visualization |
| AI Chat (Thoth) | `dashboard/pages/7_Chat.py` | Natural language queries |
| Model Insights | `dashboard/pages/8_Model_Insights.py` | ML explainability |
| Athletic Profiles | `dashboard/pages/9_Athletic_Profiles.py` | Combine data |
| Contract Intel | `dashboard/pages/10_Contract_Intelligence.py` | Contract analysis |

### Core Modules (`src/`)
| Module | Purpose |
|--------|---------|
| `src/agent/` | 14-tool Thoth AI agent |
| `src/ml/` | ML training & prediction (R²=0.87) |
| `src/features/` | 40+ feature engineering |
| `src/database/` | Neo4j client & queries |
| `src/loaders/` | KTC, NFLverse, ID resolution |
| `src/api/` | Sleeper, injury, sentiment clients |
| `src/validation/` | Backtesting framework |

### AI Agent
| File | Description |
|------|-------------|
| `thoth_agent.py` | CLI agent with 14 tools |
| `src/agent/enhanced_tools.py` | Tool implementations |

## Data Sources
- **KTC**: KeepTradeCut crowdsourced values
- **Sleeper**: League rosters, standings, picks
- **NFLverse**: Stats, combine, contracts, injuries, snaps

## ML Model
- **Algorithm**: Gradient Boosting (40 features)
- **Performance**: R² = 0.87
- **Features**: Athletic, situational, production, age curves

## Key Directories
- `dashboard/` - Multi-page Streamlit app
- `src/` - Core Python modules
- `pipelines/` - Data pipelines
- `scripts/` - CLI utilities
- `docs/` - Technical documentation
- `data/` - Raw data files
