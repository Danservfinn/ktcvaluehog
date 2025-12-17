---
title: Thoth AI Agent
link: thoth-ai-agent
type: code_index
ontological_relations: []
tags:
- agent
- ai
- tools
created_at: 2025-12-17T16:39:25Z
updated_at: 2025-12-17T16:39:25Z
uuid: 6d9c130d-b9d2-407c-b6d4-d46ee63ab2ff
---

# Thoth AI Agent

## Overview
Named after the Egyptian god of knowledge, Thoth is a 14-tool AI agent powered by Claude and Neo4j for dynasty fantasy football analysis.

## Files
- `thoth_agent.py` - CLI entry point
- `src/agent/enhanced_tools.py` - Tool implementations

## Usage
```bash
python thoth_agent.py
```

## 14 Available Tools

| Tool | Purpose |
|------|---------|
| `get_player_profile` | Full player analysis with all 40 features |
| `search_players` | Find players by position, team, age, value |
| `get_edge_report` | Top buy/sell signals by position |
| `compare_players` | Head-to-head player comparison |
| `find_trade_targets` | Find targets within value range |
| `analyze_roster` | Evaluate a roster's strengths/weaknesses |
| `assess_injury_risk` | Player injury history and risk score |
| `find_undervalued_athletes` | Elite combine scores + low KTC |
| `find_contract_mismatches` | NFL salary vs dynasty value gaps |
| `get_playing_time_breakout` | Rising snap share players |
| `explain_recommendation` | Detailed reasoning for any player |
| `explain_methodology` | How the ML model works |
| `get_model_predictions` | Raw model predictions |
| `cypher_query` | Direct Neo4j queries |

## Signal Thresholds

| Signal | Model vs KTC Gap |
|--------|------------------|
| STRONG_BUY | >+15% |
| BUY | +7% to +15% |
| HOLD | -7% to +7% |
| SELL | -7% to -15% |
| STRONG_SELL | <-15% |

## Example Queries

```
"Who are the best buy-low WRs under 25?"
"Compare Ja'Marr Chase and Justin Jefferson"
"Find breakout candidates based on snap share"
"Explain why the model likes Drake London"
```
