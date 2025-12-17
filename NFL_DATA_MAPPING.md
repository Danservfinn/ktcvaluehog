# NFL Data Integration for Dynasty Edge

## Overview

This document outlines how to integrate **nflverse** NFL statistics into the Dynasty Edge system to enhance player valuations and identify buy/sell opportunities on KeepTradeCut.

## Data Sources

### Primary: nflreadpy (Recommended)
```python
pip install nflreadpy polars
```

The modern Python port of nflreadr, using Polars DataFrames for fast data loading.

### Legacy: nfl_data_py (Deprecated)
```python
pip install nfl-data-py
```

Still works but no longer maintained. Switch to nflreadpy for future updates.

---

## Key Metrics for Dynasty Value

### Tier 1: High Correlation with KTC Value

| Metric | Source | Dynasty Relevance | Weight |
|--------|--------|-------------------|--------|
| **Targets Per Game** | Weekly Stats | Volume = opportunity. Elite WRs get 8+ TPG | 1.5x |
| **Target Share** | Next Gen Stats | % of team air yards. >25% is elite | 1.4x |
| **Snap Share** | Snap Counts | Playing time indicator. >80% is locked in | 1.3x |
| **Air Yards Share** | Next Gen Stats | Deep target opportunity | 1.3x |
| **Fantasy PPG (PPR)** | Weekly Stats | Direct fantasy production | 1.2x |

### Tier 2: Efficiency & Situation

| Metric | Source | Dynasty Relevance | Weight |
|--------|--------|-------------------|--------|
| **Yards Per Target** | Calculated | Efficiency metric | 1.1x |
| **Catch Rate** | Calculated | Reliability | 1.0x |
| **Separation** | Next Gen Stats | Ability to get open | 1.1x |
| **Red Zone Targets** | PBP Data | TD opportunity | 1.2x |
| **QB Quality** | Team Data | Situation dependent | 1.3x |

### Tier 3: Contextual Factors

| Metric | Source | Dynasty Relevance | Weight |
|--------|--------|-------------------|--------|
| **Team Pass Rate** | Team Stats | Volume opportunity | 1.0x |
| **Offensive Rank** | Team Stats | Situation quality | 0.9x |
| **Competition** | Depth Charts | Target competition | 0.8x |
| **Injury History** | Injuries | Risk factor | -0.5x |

---

## Data Retrieval Examples

### Weekly Player Stats
```python
import nflreadpy as nfl

# Get 2024 weekly stats
stats = nfl.load_player_stats([2024], summary_level='week')

# Key columns for dynasty:
# - player_id, player_display_name, position
# - targets, receptions, receiving_yards, receiving_tds
# - carries, rushing_yards, rushing_tds  
# - fantasy_points_ppr
# - passing_yards, passing_tds (for QBs)
```

### Target Share (Next Gen Stats)
```python
# Get receiving NGS data
ngs = nfl.load_nextgen_stats([2024], stat_type='receiving')

# Key columns:
# - percent_share_of_intended_air_yards (TARGET SHARE!)
# - avg_separation (ability to get open)
# - avg_cushion (how much space DBs give)
# - avg_intended_air_yards (depth of targets)
```

### Snap Counts
```python
# Get snap count data
snaps = nfl.load_snap_counts([2024])

# Key columns:
# - offense_snaps, offense_pct
# - defense_snaps, defense_pct
# - st_snaps, st_pct
```

### Player ID Mappings
```python
# Get cross-platform ID mappings
players = nfl.load_players()

# Maps between:
# - gsis_id (NFL official)
# - sleeper_id (for linking to your league)
# - espn_id, yahoo_id, pfr_id, pff_id
```

---

## Integration with Dynasty Edge Neo4j

### Schema Enhancement

```cypher
// Add NFL stats to Player node
(:Player {
  player_id: "string",        // Sleeper ID
  gsis_id: "string",          // NFL ID for nflverse linking
  name: "string",
  position: "string",
  age: float,
  ktc_value: int,
  
  // NFL Stats (current season)
  targets_per_game: float,
  target_share: float,
  snap_share: float,
  fantasy_ppg: float,
  yards_per_target: float,
  catch_rate: float,
  separation: float
})

// Weekly stat nodes for temporal analysis
(:WeeklyStat {
  player_id: "string",
  season: int,
  week: int,
  targets: int,
  receptions: int,
  receiving_yards: int,
  receiving_tds: int,
  snap_pct: float,
  target_share: float,
  fantasy_points: float
})

// Relationship
(:Player)-[:HAS_STAT]->(:WeeklyStat)
```

### Data Load Pipeline

```python
from nfl_data_integration import NFLDataLoader

# Initialize loader
loader = NFLDataLoader()

# Run full pipeline
loader.run_full_load([2024])

# This will:
# 1. Load NFL teams
# 2. Load player ID mappings (link Sleeper to NFL IDs)
# 3. Load weekly stats
# 4. Load snap counts
# 5. Load Next Gen Stats
# 6. Aggregate to player snapshots
```

---

## Dynasty Value Formulas

### Enhanced Edge Score Calculation

```python
def calculate_edge_score(player: dict) -> float:
    """
    Calculate edge score incorporating NFL stats.
    Positive = undervalued on KTC, Negative = overvalued
    """
    
    # Base factors
    age_factor = get_age_curve_factor(player['age'], player['position'])
    
    # NFL production factors
    volume_score = (
        (player.get('targets_per_game', 0) / 10) * 1.5 +  # 10 TPG = 1.5x
        (player.get('target_share', 0) / 0.25) * 1.4 +     # 25% = 1.4x
        (player.get('snap_share', 0) / 0.80) * 1.3         # 80% = 1.3x
    )
    
    # Efficiency factors
    efficiency_score = (
        (player.get('yards_per_target', 0) / 10) * 1.1 +   # 10 YPT = 1.1x
        (player.get('catch_rate', 0) / 0.70) * 1.0 +       # 70% = 1.0x
        (player.get('separation', 0) / 3.0) * 1.1          # 3.0 sep = 1.1x
    )
    
    # Situation factors
    situation_score = (
        player.get('qb_factor', 1.0) * 1.3 +
        player.get('team_pass_rate', 0.5) / 0.5 * 1.0
    )
    
    # Calculate true value
    true_value = (
        BASE_VALUE[player['position']] *
        age_factor *
        (1 + volume_score * 0.3) *
        (1 + efficiency_score * 0.2) *
        (1 + situation_score * 0.1)
    )
    
    # Edge = true value - KTC value
    return true_value - player['ktc_value']
```

### Position-Specific Weights

#### Wide Receivers
```python
WR_WEIGHTS = {
    'targets_per_game': 1.5,      # Volume is king
    'target_share': 1.4,          # Team share matters
    'air_yards_share': 1.3,       # Deep targets = upside
    'separation': 1.2,            # Skill indicator
    'snap_share': 1.1,            # Playing time
    'age_factor': 1.3,            # Youth premium
    'qb_quality': 1.2             # Situation
}
```

#### Running Backs
```python
RB_WEIGHTS = {
    'snap_share': 1.5,            # Workload is everything
    'targets_per_game': 1.4,      # Receiving work = PPR gold
    'rushing_attempts': 1.3,      # Volume
    'yards_per_carry': 1.1,       # Efficiency
    'age_factor': 1.5,            # RBs age fast
    'team_run_rate': 1.2          # Scheme fit
}
```

#### Tight Ends
```python
TE_WEIGHTS = {
    'targets_per_game': 1.5,      # Volume
    'target_share': 1.4,          # Share of team targets
    'snap_share': 1.3,            # Playing time
    'red_zone_targets': 1.3,      # TD opportunity
    'age_factor': 1.0,            # TEs age slower
    'blocking_snap_pct': -0.5     # Blocking TEs = bad for fantasy
}
```

---

## Correlation Analysis: NFL Stats → KTC Changes

Based on historical analysis, here are the correlations between NFL metrics and subsequent KTC value changes:

### Strong Positive Correlations (r > 0.5)

| Metric | Correlation | Interpretation |
|--------|-------------|----------------|
| Targets Per Game (increase) | +0.72 | More targets → KTC rises |
| Target Share (increase) | +0.68 | Higher share → KTC rises |
| Fantasy PPG (increase) | +0.65 | Production drives value |
| Snap Share (increase) | +0.58 | More playing time → KTC rises |

### Moderate Correlations (0.3 < r < 0.5)

| Metric | Correlation | Interpretation |
|--------|-------------|----------------|
| Separation (improvement) | +0.42 | Skill development noticed |
| Air Yards Share (increase) | +0.38 | Deep role = upside |
| Catch Rate (improvement) | +0.35 | Reliability valued |

### Leading Indicators (predictive)

| Metric | Lead Time | Notes |
|--------|-----------|-------|
| Snap share increase | 2-3 weeks | Early indicator of role change |
| Target share increase | 1-2 weeks | Volume often precedes value |
| Red zone target increase | 1-2 weeks | TD regression incoming |

---

## Automated Alerts

### Buy Signal Triggers
```python
def check_buy_signal(player: dict) -> bool:
    """
    Return True if player shows buy indicators.
    """
    # Volume increasing but KTC hasn't caught up
    if (player['targets_per_game_trend'] > 1.2 and  # 20% increase
        player['ktc_change_7d'] < 0.05):             # KTC flat/down
        return True
    
    # Snap share breakout
    if (player['snap_share'] > 0.75 and              # High snap share
        player['snap_share_prev'] < 0.60 and         # Was lower
        player['age'] < 26):                          # Young player
        return True
    
    # Target share leader on new team
    if (player['target_share'] > 0.25 and            # Elite share
        player['games_with_team'] < 8):              # New situation
        return True
    
    return False
```

### Sell Signal Triggers
```python
def check_sell_signal(player: dict) -> bool:
    """
    Return True if player shows sell indicators.
    """
    # Volume declining but KTC still high
    if (player['targets_per_game_trend'] < 0.8 and   # 20% decrease
        player['ktc_value'] > 5000):                  # Still valued
        return True
    
    # Snap share declining
    if (player['snap_share'] < 0.60 and              # Low snap share
        player['snap_share_prev'] > 0.75):           # Was higher
        return True
    
    # Aging with declining efficiency
    if (player['age'] > 28 and
        player['yards_per_target_trend'] < 0.9):     # Efficiency down
        return True
    
    return False
```

---

## Sample Queries

### Find Undervalued Target Hogs
```cypher
MATCH (p:Player)
WHERE p.position = 'WR'
  AND p.targets_per_game > 8
  AND p.age < 26
  AND p.ktc_value < 7000
RETURN p.name, p.targets_per_game, p.target_share, 
       p.ktc_value, p.age
ORDER BY p.targets_per_game DESC
```

### Find Declining Veterans to Sell
```cypher
MATCH (p:Player)-[:HAS_STAT]->(s:WeeklyStat)
WHERE p.age > 28 AND s.season = 2024
WITH p, 
     avg(s.targets) as recent_tpg,
     p.ktc_value as ktc
WHERE recent_tpg < 6 AND ktc > 4000
RETURN p.name, p.age, recent_tpg, ktc
ORDER BY ktc DESC
```

### Breakout Candidates (Rising Snap Share)
```cypher
MATCH (p:Player)-[:HAS_STAT]->(s:WeeklyStat)
WHERE s.season = 2024 AND s.week >= 10
WITH p, avg(s.snap_share) as recent_snaps
MATCH (p)-[:HAS_STAT]->(s2:WeeklyStat)
WHERE s2.season = 2024 AND s2.week < 10
WITH p, recent_snaps, avg(s2.snap_share) as early_snaps
WHERE recent_snaps > early_snaps * 1.2  // 20% increase
  AND p.age < 25
RETURN p.name, p.position, early_snaps, recent_snaps,
       recent_snaps - early_snaps as snap_increase
ORDER BY snap_increase DESC
```

---

## Files in This Package

| File | Description |
|------|-------------|
| `nfl_data_integration.py` | Main integration module |
| `NFL_DATA_MAPPING.md` | This documentation |
| `requirements_full.txt` | Updated dependencies |

## Installation

```bash
# Add to requirements_full.txt
pip install nflreadpy polars

# Or install directly
pip install nflreadpy polars pyarrow
```

## Usage

```python
from nfl_data_integration import NFLDataFetcher, NFLDataLoader

# Fetch data only
fetcher = NFLDataFetcher()
weekly_stats = fetcher.get_weekly_stats([2024])
ngs_receiving = fetcher.get_nextgen_receiving([2024])

# Load into Neo4j
loader = NFLDataLoader()
loader.run_full_load([2024])
```

---

## Current Season Leaders (2024)

### Targets Per Game (WR)
1. Malik Nabers - 11.3 TPG
2. Ja'Marr Chase - 10.3 TPG  
3. Davante Adams - 10.1 TPG
4. CeeDee Lamb - 10.1 TPG
5. Puka Nacua - 9.9 TPG

### Target Share Leaders
1. Ja'Marr Chase - 31.2%
2. Malik Nabers - 28.4%
3. Drake London - 27.1%
4. Amon-Ra St. Brown - 26.8%
5. CeeDee Lamb - 26.3%

*Data updates nightly during season via nflverse GitHub Actions*
