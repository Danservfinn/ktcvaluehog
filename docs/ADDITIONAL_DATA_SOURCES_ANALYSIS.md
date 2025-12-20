# Additional Data Sources for Neural Network Learning

## Executive Summary

This analysis examines potential data sources that could significantly improve neural network model performance for fantasy football prediction. With our current expanded dataset of 2,444 samples and 93 features, additional data could help us reach the 10K-20K sample threshold where neural networks begin outperforming gradient boosting models.

**Status Update (December 2024):** Weather, Injury History, Depth Charts, and KTC Time Series have been successfully implemented and integrated into Neo4j.

---

## Current Data Inventory

### Core Data (Neo4j)
| Source | Records | Coverage | Years |
|--------|---------|----------|-------|
| HistoricalSeasonStats | 14,182 | Base training data | 1999-2023 |
| HistoricalWeeklyStats | 143,593 | Weekly game logs | 1999-2024 |
| HistoricalSnapCount | 249,455 | Snap participation | 2015-2024 |
| HistoricalNGS | 24,068 | Next Gen Stats | 2016-2024 |
| CombineResult | 6,876 | Athletic testing | 2000-2024 |
| DraftPick | 6,640 | Draft capital | 2000-2024 |
| KTCSnapshot | 52,013 | Dynasty values | 2019-2024 |

### Newly Integrated Data (December 2024)
| Source | Records | Coverage | Years | Script |
|--------|---------|----------|-------|--------|
| GameWeather | 5,593 | Game conditions | 2000-2020 | `scripts/ingest_weather.py` |
| InjuryReport | 49,484 | Injury history | 2016-2024 | `scripts/ingest_injuries.py` |
| PlayerInjuryProfile | 4,254 | Aggregated risk | 2016-2024 | `scripts/ingest_injuries.py` |
| DepthChartEntry | 18,496 | Depth charts | 2023-2024 | `scripts/ingest_depth_charts.py` |
| PlayerRoleProfile | 699 | Role analysis | 2023-2024 | `scripts/ingest_depth_charts.py` |
| KTCTrend | 292 | Value signals | Current | `scripts/process_ktc_timeseries.py` |

### Current Integrated Dataset
- **2,444 samples** (consecutive season pairs with 6+ games)
- **93 features** including snap trends, NGS metrics, combine data
- **90.9% snap coverage**, 74.7% athletic scores, 68% combine data

---

## Data Sources Status

### 1. Weather Data ✅ IMPLEMENTED

**Status:** Integrated into Neo4j (December 2024)
**Script:** `scripts/ingest_weather.py`
**Records:** 5,593 games (2000-2020)
**Source:** ThompsonJamesBliss/WeatherData GitHub repository

**Why It Matters:**
- Dome teams vs outdoor teams have different performance profiles
- Cold/wind games dramatically reduce passing efficiency
- Snow/rain games increase rushing opportunities
- Weather is predictive of game script and player usage

**Neo4j Schema (GameWeather):**
```cypher
(:GameWeather {
    game_id: STRING,
    season: INTEGER,
    stadium: STRING,
    home_team: STRING,
    temperature: FLOAT,
    humidity: FLOAT,
    wind_speed: FLOAT,
    wind_direction: FLOAT,
    precipitation: FLOAT,
    condition: STRING,
    is_dome: INTEGER,       // Binary: dome game
    is_cold: INTEGER,       // Binary: temp < 40F
    is_windy: INTEGER,      // Binary: wind > 15mph
    has_precipitation: INTEGER,
    roof_type: STRING,
    loaded_at: DATETIME
})
```

**Stats After Ingestion:**
- Dome games: 1,457
- Cold games (<40F): 929
- Windy games (>15mph): calculated

**Usage Example:**
```cypher
MATCH (gw:GameWeather)
WHERE gw.is_cold = 1 AND gw.home_team = 'GB'
RETURN gw.season, count(*) as cold_games
ORDER BY gw.season
```

---

### 2. Injury History Data ✅ IMPLEMENTED

**Status:** Integrated into Neo4j (December 2024)
**Script:** `scripts/ingest_injuries.py`
**Records:** 49,484 injury reports, 4,254 player profiles
**Source:** nfl_data_py (Pro Football Reference injury reports)
**Years:** 2016-2024

**Why It Matters:**
- Injury history is the #1 predictor of future injuries
- Players with chronic injuries have different career curves
- DNP patterns indicate coaching confidence
- Recovery time varies by injury type

**Neo4j Schema (InjuryReport):**
```cypher
(:InjuryReport {
    player_id: STRING,
    player_name: STRING,
    team: STRING,
    position: STRING,
    season: INTEGER,
    week: INTEGER,
    primary_injury: STRING,
    secondary_injury: STRING,
    report_status: STRING,        // out, doubtful, questionable, probable
    practice_status: STRING,
    injury_category: STRING,      // soft_tissue_leg, knee, concussion, etc.
    severity: STRING,             // out, doubtful, questionable, probable
    game_type: STRING,
    loaded_at: DATETIME
})
```

**Neo4j Schema (PlayerInjuryProfile):**
```cypher
(:PlayerInjuryProfile {
    player_id: STRING,
    player_name: STRING,
    position: STRING,

    // Injury counts by category
    soft_tissue_leg_count: INTEGER,
    soft_tissue_upper_count: INTEGER,
    knee_injury_count: INTEGER,
    ankle_foot_count: INTEGER,
    concussion_count: INTEGER,
    back_neck_count: INTEGER,

    // Severity metrics
    games_listed_out: INTEGER,
    games_questionable: INTEGER,
    total_injury_reports: INTEGER,

    // Risk scores (low/medium/high)
    soft_tissue_risk: STRING,
    structural_risk: STRING,
    concussion_risk: STRING,
    overall_injury_risk: STRING,

    first_injury_season: INTEGER,
    last_injury_season: INTEGER,
    updated_at: DATETIME
})
```

**Stats After Ingestion:**
- High-risk players: 95
- Medium-risk players: 465
- Unique players tracked: 4,254

**Usage Example:**
```cypher
MATCH (pip:PlayerInjuryProfile)
WHERE pip.overall_injury_risk = 'high' AND pip.position = 'RB'
RETURN pip.player_name, pip.games_listed_out, pip.soft_tissue_leg_count
ORDER BY pip.games_listed_out DESC
LIMIT 20
```

---

### 3. Depth Chart Data ✅ IMPLEMENTED

**Status:** Integrated into Neo4j (December 2024)
**Script:** `scripts/ingest_depth_charts.py`
**Records:** 18,496 entries, 699 player profiles
**Source:** nfl_data_py (ESPN depth charts)
**Years:** 2023-2024

**Why It Matters:**
- Depth chart position indicates playing time opportunity
- Role classification (starter/backup) impacts projections
- Formation roles (slot/outside WR) affect usage
- Competition analysis within position groups

**Neo4j Schema (DepthChartEntry):**
```cypher
(:DepthChartEntry {
    player_id: STRING,
    player_name: STRING,
    team: STRING,
    season: INTEGER,
    week: INTEGER,
    position: STRING,
    depth_team: INTEGER,          // 1=starter, 2=backup, etc.
    formation: STRING,
    role: STRING,                 // starter, backup, third_string, depth
    formation_role: STRING,       // slot, outside, inline_te, etc.
    jersey_number: INTEGER,
    loaded_at: DATETIME
})
```

**Neo4j Schema (PlayerRoleProfile):**
```cypher
(:PlayerRoleProfile {
    player_id: STRING,
    player_name: STRING,
    position: STRING,

    // Role metrics
    starter_weeks: INTEGER,
    backup_weeks: INTEGER,
    total_depth_chart_weeks: INTEGER,
    starter_rate: FLOAT,          // 0-1 scale

    // WR alignment
    slot_weeks: INTEGER,
    outside_weeks: INTEGER,
    alignment: STRING,            // slot_primary, outside_primary, versatile

    // Classification
    primary_role: STRING,         // established_starter, starter_backup_mix, etc.

    first_season: INTEGER,
    last_season: INTEGER,
    updated_at: DATETIME
})
```

**Usage Example:**
```cypher
MATCH (prp:PlayerRoleProfile)
WHERE prp.position = 'WR' AND prp.alignment = 'slot_primary'
RETURN prp.player_name, prp.starter_rate, prp.slot_weeks
ORDER BY prp.starter_rate DESC
LIMIT 20
```

---

### 4. KTC Time Series Analysis ✅ IMPLEMENTED

**Status:** Integrated into Neo4j (December 2024)
**Script:** `scripts/process_ktc_timeseries.py`
**Records:** 292 players with trend data
**Source:** Existing KTCSnapshot data (52K records)
**Coverage:** June 2025 - December 2025 (180 unique dates)

**Why It Matters:**
- Value momentum indicates market sentiment
- Trend direction helps identify buy/sell opportunities
- Peak/trough analysis reveals value cycles
- Automated signal generation for dynasty decisions

**Neo4j Schema (KTCTrend):**
```cypher
(:KTCTrend {
    ktc_id: STRING,
    player_name: STRING,
    position: STRING,
    team: STRING,

    // Current state
    current_ktc: INTEGER,
    first_ktc: INTEGER,

    // Changes
    total_change: INTEGER,
    total_change_pct: FLOAT,
    change_30d: INTEGER,
    change_30d_pct: FLOAT,
    change_7d: INTEGER,
    change_7d_pct: FLOAT,

    // Volatility
    ktc_std: FLOAT,
    ktc_min: INTEGER,
    ktc_max: INTEGER,
    ktc_range: INTEGER,

    // Trend analysis
    trend_slope: FLOAT,
    trend_direction: STRING,      // rising, falling, stable
    momentum: FLOAT,
    momentum_pct: FLOAT,

    // Peak/trough analysis
    days_since_peak: INTEGER,
    days_since_trough: INTEGER,
    pct_off_peak: FLOAT,
    pct_above_trough: FLOAT,

    // Signal
    value_signal: STRING,         // strong_buy, buy, hold, sell, strong_sell
    signal_updated_at: DATETIME,

    // Metadata
    days_tracked: INTEGER,
    snapshots_count: INTEGER,
    updated_at: DATETIME
})
```

**Signal Distribution:**
- Strong Buy: 17 players (rising trend + momentum + off peak)
- Buy: 25 players (positive momentum + recovering)
- Hold: 123 players (stable)
- Sell: 127 players (negative momentum + declining)
- Strong Sell: 0 players

**Usage Example:**
```cypher
MATCH (kt:KTCTrend)
WHERE kt.value_signal = 'strong_buy'
RETURN kt.player_name, kt.current_ktc, kt.momentum_pct, kt.pct_off_peak
ORDER BY kt.momentum_pct DESC
```

---

### 5. Contract/Salary Data (NOT YET IMPLEMENTED)

**Why It Matters:**
- Contract year players often have elevated production
- Guaranteed money indicates team commitment
- Free agents have uncertain situations
- Dead cap indicates job security

**Data Sources:**
| Source | Format | Historical | Cost |
|--------|--------|------------|------|
| Spotrac | HTML scrape | 2011+ | Free |
| Over The Cap | API/scrape | 2011+ | Free |
| ESPN Contract Data | JSON | Current | Free |

**Key Features to Extract:**
```
Contract Features:
- is_contract_year (binary)
- years_remaining
- guaranteed_remaining
- dead_cap_hit
- cap_percentage_of_position
- extension_expected (prediction)
- free_agent_year

Financial Context:
- position_rank_by_apy
- team_cap_space
- team_positional_spending_rank
```

**Expected Impact:**
- +3-5% accuracy for contract year prediction
- Better free agent projection
- Improved KTC value correlation

---

### 4. Play-by-Play Data (High Impact for NN)

**Why It Matters:**
- Weekly stats miss crucial context (garbage time, etc.)
- Route running and target distribution matter
- Situational usage (red zone, 3rd down) is predictive
- Neural networks can learn patterns humans miss

**Data Sources:**
| Source | Format | Records | Cost |
|--------|--------|---------|------|
| nflfastR | R package/CSV | 2M+ plays | Free |
| NFL API | JSON | 2009+ | Free |
| Pro Football Focus | API | 2006+ | $$$$ |

**Key Features to Extract:**
```
Usage Patterns:
- target_share_redzone
- target_share_2min_drill
- rush_share_goal_line
- air_yards_per_route_run
- slot_snap_rate
- motion_rate
- avg_depth_of_target

Efficiency Metrics:
- first_down_conversion_rate
- contested_catch_rate
- broken_tackle_rate
- yards_after_contact
- epa_per_play
```

**Expected Impact:**
- +5-10% model improvement (largest potential)
- Better breakout detection
- Improved role clarity features

---

### 5. Team Offensive Scheme Data (Medium Impact)

**Why It Matters:**
- Scheme fit predicts player usage
- Coaching changes impact player values
- Play calling tendencies are predictive
- Personnel groupings matter

**Data Sources:**
| Source | Format | Historical |
|--------|--------|------------|
| Sharp Football Stats | HTML | 2016+ |
| Football Outsiders | HTML | 2003+ |
| The Athletic | Articles | Manual |
| PFF Scheme Data | API | Paid |

**Key Features to Extract:**
```
Team Tendencies:
- pass_rate_neutral_script
- play_action_rate
- shotgun_rate
- personnel_11_rate (3WR)
- personnel_12_rate (2TE)
- run_to_pass_ratio
- avg_time_of_possession

Scheme Classification:
- offense_style (air_raid/west_coast/power_run/zone_run)
- preferred_rb_type (speed/power/receiving)
- te_usage_type (inline/flex/big_slot)
```

**Expected Impact:**
- +2-3% accuracy for situation-dependent players
- Better role projection for new team players

---

### 6. Vegas Odds & Betting Lines (Medium Impact)

**Why It Matters:**
- Implied totals predict game environment
- Spread indicates expected game flow
- Props capture market intelligence
- Futures signal perceived team strength

**Data Sources:**
| Source | Format | Historical | Cost |
|--------|--------|------------|------|
| The-Odds-API | JSON | Limited | Free tier |
| DraftKings/FanDuel | Scrape | Current | Free |
| Historical odds DB | Various | 2003+ | Mixed |

**Key Features to Extract:**
```
Game-Level:
- implied_team_total
- spread
- over_under
- moneyline_implied_prob

Season-Level Aggregations:
- avg_implied_total_home
- avg_implied_total_away
- games_as_favorite
- avg_spread_when_favorite
```

**Expected Impact:**
- +1-3% weekly prediction accuracy
- Better game script anticipation

---

### 7. Social Media/News Sentiment (Experimental)

**Why It Matters:**
- Beat reporter intel is often predictive
- Injury updates hit Twitter first
- Training camp buzz predicts breakouts
- Fantasy community sentiment affects KTC

**Data Sources:**
| Source | Format | API Cost |
|--------|--------|----------|
| Twitter/X API | JSON | $$$ |
| Reddit API | JSON | Free |
| News APIs | JSON | Free tier |

**Key Features to Extract:**
```
- beat_reporter_sentiment_score
- training_camp_buzz_score
- injury_uncertainty_score
- hype_index (vs production)
- fantasy_community_sentiment
```

**Expected Impact:**
- +1-2% for breakout/bust prediction
- Better early-season projections
- Improved KTC value tracking

---

## Priority Ranking

### ✅ Phase 1: COMPLETED (December 2024)
| Source | Status | Records | Impact |
|--------|--------|---------|--------|
| Weather Data | ✅ Done | 5,593 games | Game environment context |
| Injury History | ✅ Done | 49,484 reports | Risk profiling |
| Depth Charts | ✅ Done | 18,496 entries | Role analysis |
| KTC Time Series | ✅ Done | 292 trends | Buy/sell signals |

### 🔄 Phase 2: Next Priority
1. **Contract Data** - Free, improves KTC model significantly
2. **Play-by-Play Data** - Largest potential, needs aggregation pipeline
3. **Team Scheme Data** - Manual classification needed

### 📋 Phase 3: Future/Experimental
4. **Vegas Odds** - Data availability varies
5. **Social Sentiment** - Noisy, expensive, experimental

---

## Data Volume Analysis

### Current State
- Base: 2,444 samples
- With year expansion (2010-2023): ~4,000 samples

### After Adding Sources
| Addition | New Samples | Cumulative |
|----------|-------------|------------|
| Extended year range | +1,500 | 3,944 |
| Weekly-level training | +15,000 | 18,944 |
| Play-by-play features | +0 (enriches) | 18,944 |
| Weather/contract | +0 (enriches) | 18,944 |

**Key Insight**: To reach 20K+ samples needed for effective neural networks:
1. Extend year range back to 2010 (NGS limits to 2016)
2. Consider weekly-level prediction task
3. Add synthetic data augmentation

---

## Implementation Status

### ✅ Completed Scripts (December 2024)
| Script | Source | Command |
|--------|--------|---------|
| `scripts/ingest_weather.py` | GitHub ThompsonJamesBliss | `python scripts/ingest_weather.py` |
| `scripts/ingest_injuries.py` | nfl_data_py | `python scripts/ingest_injuries.py --years 2016 2024` |
| `scripts/ingest_depth_charts.py` | nfl_data_py | `python scripts/ingest_depth_charts.py --years 2023 2024` |
| `scripts/process_ktc_timeseries.py` | Existing KTCSnapshot | `python scripts/process_ktc_timeseries.py` |

### 🔄 Next Actions
1. **Contract Data Scraper**
   ```python
   # Create scripts/ingest_contracts.py
   # Target: Player contract details from Spotrac
   # Include: APY, guaranteed, years remaining
   ```

2. **Play-by-Play Aggregations**
   ```python
   # Create scripts/ingest_pbp_features.py
   # Target: Red zone usage, situational stats
   # Source: nflfastR via nfl_data_py
   ```

### Model Training Impact
With current 2,444 samples + enriched features:
- GBM: Expected R² improvement from 0.622 to 0.65-0.68
- Neural Network: May become competitive with GBM

With 20K+ samples (weekly-level or extended):
- Neural Network: Expected to outperform GBM
- Multi-task learning becomes viable
- Attention mechanisms can capture patterns

---

## Conclusion

### Completed High-Impact Sources ✅
1. **Weather data** - 5,593 games with temperature, wind, dome status
2. **Injury history** - 49,484 reports with risk profiling for 4,254 players
3. **Depth charts** - 18,496 entries with role classification for 699 players
4. **KTC trends** - 292 players with buy/sell signals based on momentum

### Remaining Priorities
1. **Contract data** - Critical for KTC model, improves value prediction
2. **Play-by-play aggregations** - Largest potential for model improvement

### Neural Network Path Forward
For neural network viability, the key bottleneck is sample size. Consider:
- Weekly-level prediction (15K+ samples available)
- Data augmentation techniques
- Transfer learning from larger sports datasets

The current 2,444 samples with 93 features + new enrichment data is sufficient for enhanced GBM, but neural networks will require either:
- 10x more samples, or
- Pre-trained embeddings from related tasks
