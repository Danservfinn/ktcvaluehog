# Additional Data Sources for Neural Network Enhancement (v2)

## Executive Summary

This analysis identifies **high-impact data sources** to improve neural network model performance for dynasty fantasy football prediction. Current state: 750K+ nodes, 6K season-level samples, R²=0.622 with GBM.

**Goal**: Reach 20K+ effective training samples where neural networks begin outperforming gradient boosting.

---

## Current Data Inventory

### Implemented (December 2024)
| Source | Records | Years | Status |
|--------|---------|-------|--------|
| HistoricalSeasonStats | 14,182 | 1999-2023 | ✅ Core |
| HistoricalWeeklyStats | 143,593 | 1999-2024 | ✅ Core |
| HistoricalSnapCount | 249,455 | 2015-2024 | ✅ Core |
| HistoricalNGS | 24,068 | 2016-2024 | ✅ Core |
| CombineResult | 6,876 | 2000-2024 | ✅ Core |
| DraftPick | 6,640 | 2000-2024 | ✅ Core |
| KTCSnapshot | 52,013 | 2025 | ✅ Core |
| GameWeather | 5,593 | 2000-2020 | ✅ Implemented |
| InjuryReport | 49,484 | 2016-2024 | ✅ Implemented |
| DepthChartEntry | 18,496 | 2023-2024 | ✅ Implemented |
| Game (Betting) | 28,940 | 1920-2024 | ✅ Implemented |
| KTCTrend | 292 | Current | ✅ Implemented |

**Total: ~750,000 nodes**

---

## Priority 1: Play-by-Play Aggregations (HIGHEST IMPACT)

### Why This Is Critical
- **2M+ plays** available back to 1999
- Enables extraction of **situational usage metrics** that weekly stats miss
- **EPA/WPA models** provide context-adjusted efficiency
- **Red zone data** is the #1 predictor of touchdown upside

### Data Source
- **nfl_data_py** (Python) or **nflfastR** (R)
- Both access the same underlying nflverse data
- Note: nfl_data_py was archived Sep 2025; **nflreadpy** is the successor

### Key Features to Extract

```python
# Player-Level Aggregations (per season/week)
{
    # Red Zone Usage (Inside 20)
    "rz_targets": int,           # Red zone targets
    "rz_receptions": int,        # Red zone catches
    "rz_rush_attempts": int,     # Red zone carries
    "rz_touches": int,           # Total RZ touches
    "rz_td_rate": float,         # TDs per RZ opportunity

    # Goal Line (Inside 5)
    "gl_rush_attempts": int,     # Goal line carries
    "gl_td_rate": float,         # Conversion rate

    # Situational Usage
    "third_down_target_share": float,   # 3rd down targets / team 3rd down passes
    "two_min_targets": int,             # 2-minute drill targets
    "garbage_time_pts": float,          # Points in 10+ point deficit
    "neutral_script_touches": float,    # Usage when game within 7 pts

    # Efficiency Metrics
    "epa_per_target": float,     # Expected Points Added per target
    "epa_per_rush": float,       # EPA per carry
    "cpoe_targeted": float,      # Completion % over expected on targets
    "yac_epa": float,            # Yards after catch EPA
    "wopr": float,               # Weighted Opportunity Rating

    # Route Running (receivers)
    "routes_run": int,           # Total routes
    "target_per_route": float,   # TPRR - elite metric
    "adot": float,               # Average depth of target
    "air_yards_share": float,    # Team air yards percentage
    "slot_rate": float,          # % routes from slot

    # Rushing Efficiency
    "yards_before_contact": float,
    "yards_after_contact": float,
    "broken_tackles": int,
    "stuff_rate": float,         # % runs for <=0 yards
}
```

### Implementation Script
```bash
# Create: scripts/ingest_pbp_features.py
# Source: nfl_data_py.import_pbp_data()
# Target: ~15,000 player-season aggregations

python scripts/ingest_pbp_features.py --years 2016 2024
```

### Expected Impact
- **+5-10% model improvement** on weekly predictions
- **+3-5% improvement** on breakout detection
- Enables weekly-level neural network training (15K+ samples)

### Neo4j Schema
```cypher
(:PlayByPlayAggregates {
    player_id: STRING,
    season: INTEGER,
    week: INTEGER,           # 0 = season total

    # Red Zone
    rz_targets: INTEGER,
    rz_receptions: INTEGER,
    rz_rush_attempts: INTEGER,
    rz_td_rate: FLOAT,

    # Goal Line
    gl_rush_attempts: INTEGER,
    gl_td_rate: FLOAT,

    # Efficiency
    epa_per_target: FLOAT,
    epa_per_rush: FLOAT,
    wopr: FLOAT,
    target_per_route: FLOAT,
    adot: FLOAT,
    air_yards_share: FLOAT,

    # Situational
    third_down_target_share: FLOAT,
    neutral_script_touches: INTEGER,
    garbage_time_pct: FLOAT,

    loaded_at: DATETIME
})
```

---

## Priority 2: College Football Data (ROOKIE PREDICTION)

### Why This Matters
- **Rookie projection** is the weakest part of current models
- College production patterns predict NFL success
- Can identify "prospect profile" clusters
- CFBD API provides structured access

### Data Source
- **College Football Data API** (collegefootballdata.com)
- Free tier: 1,000 calls/month
- Python package: `cfbd`

### Key Features to Extract

```python
# Prospect Profile (per player)
{
    # Production
    "college_ppg": float,              # Points per game (projected to NFL scoring)
    "college_ypc": float,              # Yards per carry (RB)
    "college_ypr": float,              # Yards per reception
    "college_td_rate": float,          # TDs per touch

    # Dominance Metrics
    "market_share_college": float,     # % of team production
    "breakout_age": float,             # Age at first productive season
    "final_year_production": float,    # Senior/final year output

    # Context
    "conference_strength": float,      # SEC/Big Ten = premium
    "team_win_pct": float,             # Good teams = less garbage time
    "qb_quality_rating": float,        # Quality of QB throwing to WR/TE

    # Recruiting
    "recruiting_stars": int,           # 247 composite (2-5 stars)
    "recruiting_rank_position": int,   # Position rank in class

    # Transfer Portal
    "transfer_count": int,             # Number of transfers
    "played_multiple_schools": bool,
}
```

### Implementation Script
```bash
# Create: scripts/ingest_college_data.py
# Source: CFBD API via cfbd package
# Target: ~3,000 prospect profiles (drafted players 2015-2024)

python scripts/ingest_college_data.py --draft-years 2015 2024
```

### Expected Impact
- **+8-12% improvement** on rookie projections specifically
- Better "bust probability" predictions
- Identifies late-round breakout candidates

### Neo4j Schema
```cypher
(:CollegeProfile {
    player_id: STRING,
    college: STRING,
    conference: STRING,

    # Production
    college_ppg: FLOAT,
    college_games: INTEGER,
    college_total_yards: INTEGER,
    college_tds: INTEGER,
    college_market_share: FLOAT,

    # Age/Timing
    breakout_age: FLOAT,
    final_year_ppg: FLOAT,
    years_played: INTEGER,

    # Recruiting
    recruiting_stars: INTEGER,
    recruiting_rank: INTEGER,

    # Context
    conference_strength: FLOAT,
    team_win_pct: FLOAT,

    loaded_at: DATETIME
})
```

---

## Priority 3: Contract/Salary Data (KTC CORRELATION)

### Why This Matters
- **Contract year players** produce at elevated rates (+10-15%)
- **Guaranteed money** indicates team commitment
- **Cap percentage** reflects market value
- Strong predictor of **dynasty trade value**

### Data Sources
- **Spotrac** (spotrac.com/nfl) - Most comprehensive
- **Over The Cap** (overthecap.com) - Good for cap analysis
- **No free API** - requires web scraping

### Key Features to Extract

```python
# Contract Features (per player-season)
{
    # Contract Status
    "is_contract_year": bool,          # Final year of deal
    "years_remaining": int,            # Years left on contract
    "is_rookie_deal": bool,            # On rookie contract
    "extension_signed": bool,          # Recently extended

    # Financial
    "apy": float,                      # Average per year salary
    "guaranteed_remaining": float,     # Guaranteed $ left
    "dead_cap": float,                 # Dead cap if cut
    "cap_hit": float,                  # Current year cap hit
    "cap_pct_of_team": float,          # % of team's total cap

    # Positional Context
    "position_apy_rank": int,          # Rank at position
    "position_apy_percentile": float,  # Percentile at position

    # Team Context
    "team_cap_space": float,           # Team cap room
    "team_position_investment": float, # Team $ at this position

    # Derived
    "contract_value_score": float,     # APY / expected production
    "extension_likelihood": float,     # Probability of extension
}
```

### Implementation Approach
```python
# Option 1: BeautifulSoup scraping (recommended)
# scripts/ingest_contracts.py

from bs4 import BeautifulSoup
import requests

def scrape_spotrac_contracts(team: str):
    url = f"https://www.spotrac.com/nfl/{team}/cap/"
    # Parse contract tables...
```

### Expected Impact
- **+5-8% improvement** on KTC value prediction
- Better "sell high" identification for contract year players
- Improved free agent landing spot projections

### Neo4j Schema
```cypher
(:PlayerContract {
    player_id: STRING,
    season: INTEGER,

    # Contract Details
    apy: FLOAT,
    total_value: FLOAT,
    years_total: INTEGER,
    years_remaining: INTEGER,
    guaranteed_total: FLOAT,
    guaranteed_remaining: FLOAT,

    # Cap Impact
    cap_hit: FLOAT,
    dead_cap: FLOAT,
    cap_pct_of_team: FLOAT,

    # Status
    is_contract_year: BOOLEAN,
    is_rookie_deal: BOOLEAN,
    free_agent_year: INTEGER,

    # Positional
    position_apy_rank: INTEGER,
    position_apy_percentile: FLOAT,

    loaded_at: DATETIME
})
```

---

## Priority 4: Defensive Matchup Data (WEEKLY PROJECTION)

### Why This Matters
- **25-30% of weekly variance** is opponent-driven
- Pass-funnel vs run-funnel defenses affect usage
- Position-specific matchup grades predict ceiling games

### Data Sources
- **nflfastR** - EPA allowed, success rate
- **Pro Football Reference** - Traditional stats
- **Football Outsiders/FTN** - DVOA (paid)

### Key Features to Extract

```python
# Defense Profile (per team-season)
{
    # Overall Efficiency
    "def_epa_per_play": float,         # EPA allowed
    "def_success_rate": float,         # Success rate allowed
    "def_dvoa": float,                 # DVOA ranking (if available)

    # Pass Defense
    "pass_epa_allowed": float,         # EPA on pass plays
    "pressure_rate": float,            # Sack + pressure %
    "coverage_epa": float,             # Coverage efficiency
    "deep_pass_rate_allowed": float,   # 20+ yard completions

    # Rush Defense
    "rush_epa_allowed": float,         # EPA on run plays
    "stuff_rate": float,               # % of runs stuffed
    "yards_before_contact_allowed": float,

    # Positional Weakness (fantasy gold)
    "ppg_allowed_qb": float,           # Fantasy PPG allowed to QBs
    "ppg_allowed_rb": float,           # PPG allowed to RBs
    "ppg_allowed_wr": float,           # PPG allowed to WRs
    "ppg_allowed_te": float,           # PPG allowed to TEs

    # Game Script Tendency
    "opponent_pass_rate_induced": float,  # Do teams pass more vs them?
    "avg_game_script": float,              # Typical lead/deficit faced
}
```

### Implementation Script
```bash
# Create: scripts/ingest_defense_rankings.py
# Source: nfl_data_py play-by-play aggregations
# Target: ~640 team-season profiles (32 teams × 20 years)

python scripts/ingest_defense_rankings.py --years 2010 2024
```

### Expected Impact
- **+3-5% improvement** on weekly projections
- Better start/sit recommendations
- Improved ceiling/floor estimates

---

## Priority 5: Coaching Data (SCHEME FIT)

### Why This Matters
- **"McShanahan" coaching tree** produces 53% of fantasy league-winners
- Offensive coordinator tendencies are highly predictive
- Scheme changes dramatically affect player values

### Key Research Finding
The Sean McVay coaching tree (LaFleur, O'Connell, Taylor, Waldron, Brown) + Ben Johnson have dominated fantasy production due to:
- High motion rates
- Play-action usage
- Heavy/condensed formations

### Data Structure

```python
# Coaching Profile (per team-season)
{
    # Personnel
    "head_coach": str,
    "offensive_coordinator": str,
    "play_caller": str,                # Who calls plays

    # Coaching Tree
    "coaching_tree": str,              # mcvay/shanahan/reid/other
    "oc_years_experience": int,
    "oc_prev_team_success": float,     # Previous offense ranking

    # Scheme Tendencies
    "pass_rate_neutral": float,        # Pass rate in neutral game script
    "play_action_rate": float,         # % of passes with PA
    "motion_rate": float,              # Pre-snap motion %
    "shotgun_rate": float,             # % snaps in shotgun
    "personnel_11_rate": float,        # 3WR personnel
    "personnel_12_rate": float,        # 2TE personnel
    "personnel_21_rate": float,        # 2RB personnel

    # Historical Production
    "avg_qb_fantasy_ppg": float,       # Historical QB production
    "avg_rb_fantasy_ppg": float,       # Historical RB production
    "avg_wr_fantasy_ppg": float,       # Historical WR production
    "avg_te_fantasy_ppg": float,       # Historical TE production

    # Volatility
    "rb_committee_likelihood": float,  # Probability of RBBC
    "wr1_target_share_historical": float,
}
```

### Implementation Approach
This requires semi-manual data compilation:
1. Scrape coaching histories from Pro Football Reference
2. Manually tag coaching trees
3. Import personnel/scheme data from nflfastR

### Expected Impact
- **+2-4% improvement** on new-team player projections
- Better rookie landing spot evaluation
- Improved trade deadline analysis

---

## Priority 6: Advanced Receiving Metrics (FTN DATA)

### Data Source
- **FTN Data** - Included in nflverse since 2022
- Manual charting within 48 hours of games
- Available via `nfl_data_py.import_ftn_charting()`

### Key Features

```python
# FTN Charting Data (per player-week)
{
    "press_rate": float,               # % of routes vs press coverage
    "zone_vs_man_targets": dict,       # Targets by coverage type
    "first_read_rate": float,          # % as QB's first read
    "contested_catch_rate": float,     # Catches vs tight coverage
    "separation_at_catch": float,      # Yards of separation
    "time_to_throw_on_targets": float, # QB time to throw when targeted
}
```

### Availability
- 2022-present only
- ~3 seasons of data
- Useful for recent player evaluation

---

## Neural Network Architecture Recommendations

### With New Data Sources (20K+ samples)

```
┌──────────────────────────────────────────────────────────────────┐
│                    MULTI-MODAL INPUT LAYER                        │
├──────────────────┬──────────────────┬──────────────────┬─────────┤
│  Season Stats    │   PBP Features   │  College Data    │Contract │
│  (Encoder A)     │   (Encoder B)    │  (Encoder C)     │(Enc D)  │
└────────┬─────────┴────────┬─────────┴────────┬─────────┴────┬────┘
         │                  │                  │              │
         └──────────────────┼──────────────────┼──────────────┘
                            │
              ┌─────────────▼─────────────┐
              │      FUSION LAYER          │
              │   (Cross-Attention)        │
              └─────────────┬─────────────┘
                            │
         ┌──────────────────┼──────────────────┐
         │                  │                  │
    ┌────▼────┐       ┌────▼────┐       ┌────▼────┐
    │  PPG    │       │  KTC    │       │Breakout │
    │  Head   │       │  Head   │       │  Head   │
    └─────────┘       └─────────┘       └─────────┘
```

### Sample Size Projections

| Data Addition | New Samples | Running Total | NN Viable? |
|---------------|-------------|---------------|------------|
| Current season-level | 6,088 | 6,088 | ❌ GBM better |
| + Weekly aggregations | +15,000 | 21,088 | ⚠️ Marginal |
| + PBP features | +0 (enriches) | 21,088 | ✅ Yes |
| + College data | +3,000 rookies | 24,088 | ✅ Yes |
| + Multi-year weekly | +45,000 | 69,088 | ✅ Transformers viable |

---

## Implementation Roadmap

### Phase 1: Q1 2025 (Highest ROI)
| Task | Script | Records | Priority |
|------|--------|---------|----------|
| PBP Aggregations | `scripts/ingest_pbp_features.py` | ~15,000 | 🔴 Critical |
| Weekly-level training data | `scripts/build_weekly_dataset.py` | ~45,000 | 🔴 Critical |

### Phase 2: Q2 2025 (High Value)
| Task | Script | Records | Priority |
|------|--------|---------|----------|
| College Data | `scripts/ingest_college_data.py` | ~3,000 | 🟠 High |
| Contract Data | `scripts/ingest_contracts.py` | ~2,500/yr | 🟠 High |
| Defense Rankings | `scripts/ingest_defense_rankings.py` | ~640 | 🟡 Medium |

### Phase 3: Q3 2025 (Enhancement)
| Task | Script | Records | Priority |
|------|--------|---------|----------|
| Coaching Data | `scripts/ingest_coaching.py` | ~300 | 🟡 Medium |
| FTN Charting | `scripts/ingest_ftn_data.py` | ~5,000 | 🟢 Low |

---

## Expected Model Performance

### Current State
- GBM R² = 0.622
- Neural Network R² = 0.617 (underperforms)

### After Phase 1 (PBP + Weekly Data)
- GBM R² = 0.65-0.68 (enriched features)
- Neural Network R² = 0.66-0.70 (sufficient samples)
- Weekly prediction MAE: 4-5 points

### After Phase 2 (Full Enhancement)
- Multi-task NN R² = 0.70-0.75
- Rookie projection improvement: +8-12%
- KTC prediction correlation: +5-8%

---

## Data Source Links

### Free/Open Source
- [nflverse/nfl_data_py](https://github.com/nflverse/nfl_data_py) - Python NFL data
- [nflreadpy](https://nflreadpy.nflverse.com/) - Successor to nfl_data_py
- [nflfastR](https://nflfastr.com/) - R package with EPA/WPA models
- [College Football Data API](https://api.collegefootballdata.com/) - CFBD
- [FiveThirtyEight NFL Elo](https://github.com/fivethirtyeight/nfl-elo-game) - Historical Elo

### Scraping Required
- [Spotrac](https://www.spotrac.com/nfl) - Contract data
- [Over The Cap](https://overthecap.com/) - Cap analysis
- [Pro Football Reference](https://www.pro-football-reference.com/) - Historical stats

### Paid Options (Future)
- [PFF](https://www.pff.com/) - Grades, advanced metrics
- [SportsRadar](https://sportradar.com/) - Official NFL data partner
- [Football Outsiders/FTN](https://ftnfantasy.com/) - DVOA

---

## Conclusion

The **highest-impact addition** is play-by-play aggregated features, which:
1. Provides red zone/situational context that weekly stats miss
2. Enables weekly-level training (15K+ samples → NN viable)
3. Offers EPA-based efficiency metrics

**Recommended immediate action**: Create `scripts/ingest_pbp_features.py` to extract aggregated play-by-play features from nfl_data_py.

---

*Last Updated: December 2024*
