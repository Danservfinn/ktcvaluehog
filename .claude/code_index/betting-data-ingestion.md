---
title: NFL Betting Data Ingestion
link: betting-data-ingestion
type: code_index
ontological_relations: []
tags:
- betting
- data-pipeline
- neo4j
- ml
created_at: 2025-12-17T00:00:00Z
updated_at: 2025-12-17T00:00:00Z
uuid: b2c3d4e5-f6a7-8901-bcde-f23456789012
---

# NFL Betting Data Ingestion

## File
`scripts/ingest_betting_data.py`

## Purpose
Imports historical NFL betting data into Neo4j for ML predictions and analysis.

## Data Sources

### FiveThirtyEight Elo
- **File**: `data/betting/nfl_games_538.csv`
- **Games**: 16,810 (1920-2020)
- **Fields**: Elo ratings, win probabilities, scores

### Spreadspoke/Kaggle
- **File**: `data/betting/spreadspoke_scores.csv`
- **Games**: 14,358 (1966-2025)
- **Fields**: Spreads, over/under, weather, stadium

## Schema

### Game Node Updates
```cypher
MERGE (g:Game {game_id: $game_id})
SET g.spread_favorite = $spread_favorite,
    g.spread_line = $spread_line,
    g.over_under_line = $over_under_line,
    g.elo_home = $elo_home,
    g.elo_away = $elo_away,
    g.elo_home_prob = $elo_home_prob,
    g.spread_result = $spread_result,
    g.over_under_result = $over_under_result
```

## Derived Fields
- `spread_result`: "COVERED", "PUSHED", or "MISSED"
- `over_under_result`: "OVER", "PUSH", or "UNDER"
- `ats_margin`: Actual margin vs spread

## Usage

```bash
# Full import
python scripts/ingest_betting_data.py

# The script automatically:
# 1. Downloads FiveThirtyEight Elo data
# 2. Loads Spreadspoke betting lines
# 3. Normalizes team names
# 4. Merges into Neo4j Game nodes
```

## Statistics (after import)
- Total games: 36,957
- Games with spreads: 16,534
- Games with O/U: 16,417
- Games with Elo: 16,810

## Related Files
- `data/betting/nfl_teams.csv` - Team name normalization
- `scripts/export_neo4j.py` - Export for deployment
