# Neural Network Data Catalog

## Overview

This catalog documents all data available in the Neo4j graph database for neural network training systems. As of December 2024, the database contains **750K+ nodes** across 21 entity types.

---

## Data Summary

| Category | Node Types | Total Records | Key Use Case |
|----------|------------|---------------|--------------|
| **Performance Stats** | 4 | 490,047 | Historical production data |
| **Athletic/Draft** | 2 | 13,516 | Player physical profiles |
| **Valuations** | 2 | 52,305 | Dynasty market values |
| **Situational** | 4 | 78,427 | Context factors (weather, injury, role) |
| **Game/Betting** | 1 | 28,940 | Game context, Elo ratings, spreads |
| **Aggregations** | 6 | 7,676 | Pre-computed features |
| **Entity** | 2 | 25,344 | Core entities (Player, Team) |

**Total: ~750,000 nodes**

---

## Performance Statistics

### 1. HistoricalSeasonStats
**Records:** 14,182 | **Years:** 1999-2023 | **Granularity:** Player-Season

| Property | Type | Description | ML Relevance |
|----------|------|-------------|--------------|
| player_id | STRING | GSIS identifier | Join key |
| season | INTEGER | NFL season year | Temporal feature |
| position | STRING | QB/RB/WR/TE | Stratification |
| team | STRING | Team abbreviation | Context |
| games | INTEGER | Games played | Volume indicator |
| passing_yards | INTEGER | Season passing yards | QB production |
| passing_tds | INTEGER | Season passing TDs | QB production |
| rushing_yards | INTEGER | Season rushing yards | RB/QB production |
| rushing_tds | INTEGER | Season rushing TDs | RB/QB production |
| carries | INTEGER | Season carries | RB volume |
| receiving_yards | INTEGER | Season receiving yards | WR/TE/RB production |
| receiving_tds | INTEGER | Season receiving TDs | WR/TE/RB production |
| receptions | INTEGER | Season receptions | WR/TE/RB volume |
| targets | INTEGER | Season targets | WR/TE opportunity |
| ppg_ppr | FLOAT | PPR points per game | Reference |
| ppg_std | FLOAT | Standard points per game | Reference |
| **ppg_half_ppr** | FLOAT | **0.5 PPR points per game** | **Primary target variable** |

### 2. HistoricalWeeklyStats
**Records:** 143,593 | **Years:** 1999-2024 | **Granularity:** Player-Week

| Property | Type | Description | ML Relevance |
|----------|------|-------------|--------------|
| player_id | STRING | GSIS identifier | Join key |
| player_name | STRING | Full name | Display |
| season | INTEGER | NFL season | Temporal |
| week | INTEGER | Week number | Temporal |
| position | STRING | Position | Stratification |
| team | STRING | Team | Context |
| opponent | STRING | Opponent team | Matchup feature |
| fantasy_points | FLOAT | Standard scoring | Reference |
| fantasy_points_ppr | FLOAT | PPR scoring | Reference |
| **fantasy_points_half_ppr** | FLOAT | **0.5 PPR scoring** | **Primary weekly target** |
| passing_yards | INTEGER | Week passing yards | Production |
| passing_tds | INTEGER | Week passing TDs | Production |
| completions | INTEGER | Completions | Efficiency |
| attempts | INTEGER | Pass attempts | Volume |
| rushing_yards | INTEGER | Week rushing yards | Production |
| rushing_tds | INTEGER | Week rushing TDs | Production |
| carries | INTEGER | Week carries | Volume |
| receiving_yards | INTEGER | Week receiving yards | Production |
| receiving_tds | INTEGER | Week receiving TDs | Production |
| receptions | INTEGER | Week receptions | Volume |
| targets | INTEGER | Week targets | Opportunity |
| target_share | FLOAT | Team target share | Usage rate |
| air_yards_share | FLOAT | Team air yards share | Downfield usage |

### 3. HistoricalSnapCount
**Records:** 249,455 | **Years:** 2015-2024 | **Granularity:** Player-Week

| Property | Type | Description | ML Relevance |
|----------|------|-------------|--------------|
| player_id | STRING | GSIS identifier | Join key |
| player_name | STRING | Full name | Display |
| season | INTEGER | NFL season | Temporal |
| week | INTEGER | Week number | Temporal |
| position | STRING | Position | Stratification |
| team | STRING | Team | Context |
| offense_snaps | INTEGER | Offensive snaps | Volume |
| offense_pct | FLOAT | Offensive snap % | **Key feature** - playing time |
| defense_snaps | INTEGER | Defensive snaps | Special teams |
| defense_pct | FLOAT | Defensive snap % | Role indicator |
| st_snaps | INTEGER | Special teams snaps | Role indicator |
| st_pct | FLOAT | ST snap % | Role indicator |

### 4. HistoricalNGS (Next Gen Stats)
**Records:** 24,068 | **Years:** 2016-2024 | **Granularity:** Player-Season

| Property | Type | Description | ML Relevance |
|----------|------|-------------|--------------|
| player_id | STRING | GSIS identifier | Join key |
| player_name | STRING | Full name | Display |
| season | INTEGER | NFL season | Temporal |
| week | INTEGER | 0 = season total | Aggregation level |
| team | STRING | Team | Context |
| stat_type | STRING | passing/rushing/receiving | Position-specific |
| metrics | JSON STRING | Detailed NGS metrics | **Rich features** |

**NGS Metrics (nested in JSON):**

*Passing:*
- avg_time_to_throw, avg_completed_air_yards, avg_intended_air_yards
- avg_air_yards_differential, aggressiveness, max_completed_air_distance
- avg_air_yards_to_sticks, passer_rating, completion_percentage
- expected_completion_percentage, completion_percentage_above_expectation

*Rushing:*
- efficiency, percent_attempts_gte_eight_defenders
- avg_time_to_los, rush_attempts, rush_yards, rush_touchdowns
- avg_rush_yards, expected_rush_yards

*Receiving:*
- avg_cushion, avg_separation, avg_intended_air_yards
- percent_share_of_intended_air_yards, catch_percentage
- avg_yac, avg_expected_yac, avg_yac_above_expectation

---

## Athletic & Draft Data

### 5. CombineResult
**Records:** 6,876 | **Years:** 2000-2024 | **Granularity:** Player

| Property | Type | Description | ML Relevance |
|----------|------|-------------|--------------|
| player_id | STRING | GSIS identifier | Join key |
| player_name | STRING | Full name | Display |
| season | INTEGER | Draft year | Temporal |
| position | STRING | Position | Stratification |
| college | STRING | College | Background |
| height | INTEGER | Height (inches) | Physical profile |
| weight | INTEGER | Weight (lbs) | Physical profile |
| forty_yard | FLOAT | 40-yard dash (sec) | **Speed metric** |
| bench_press | INTEGER | Bench press reps | Strength |
| vertical_jump | FLOAT | Vertical (inches) | Explosiveness |
| broad_jump | INTEGER | Broad jump (inches) | Explosiveness |
| three_cone | FLOAT | 3-cone drill (sec) | Agility |
| shuttle | FLOAT | 20-yard shuttle (sec) | Agility |

### 6. DraftPick
**Records:** 6,640 | **Years:** 2000-2024 | **Granularity:** Player

| Property | Type | Description | ML Relevance |
|----------|------|-------------|--------------|
| player_id | STRING | GSIS identifier | Join key |
| player_name | STRING | Full name | Display |
| season | INTEGER | Draft year | Career start |
| round | INTEGER | Draft round (1-7) | **Draft capital** |
| pick | INTEGER | Overall pick number | **Draft capital** |
| team | STRING | Drafting team | Context |
| position | STRING | Position | Stratification |
| college | STRING | College | Background |

---

## Valuation Data

### 7. KTCSnapshot
**Records:** 52,013 | **Years:** 2025 (daily) | **Granularity:** Player-Date

| Property | Type | Description | ML Relevance |
|----------|------|-------------|--------------|
| ktc_id | STRING | KTC identifier | Join key |
| name | STRING | Player name | Display |
| position | STRING | Position | Stratification |
| team | STRING | Team | Context |
| date | STRING | Snapshot date | Temporal |
| ktc_value | INTEGER | Dynasty value (0-10000) | **Target variable** |

### 8. KTCTrend
**Records:** 292 | **Coverage:** Current | **Granularity:** Player

| Property | Type | Description | ML Relevance |
|----------|------|-------------|--------------|
| ktc_id | STRING | KTC identifier | Join key |
| player_name | STRING | Player name | Display |
| position | STRING | Position | Stratification |
| team | STRING | Team | Context |
| current_ktc | INTEGER | Current value | Target |
| first_ktc | INTEGER | First recorded value | Baseline |
| total_change | INTEGER | Value change | Momentum |
| total_change_pct | FLOAT | % change | Momentum |
| change_30d | INTEGER | 30-day change | Recent trend |
| change_30d_pct | FLOAT | 30-day % change | Recent trend |
| change_7d | INTEGER | 7-day change | Short-term |
| change_7d_pct | FLOAT | 7-day % change | Short-term |
| ktc_std | FLOAT | Value std deviation | Volatility |
| ktc_min | INTEGER | Historical minimum | Range |
| ktc_max | INTEGER | Historical maximum | Range |
| ktc_range | INTEGER | Max - Min | Volatility |
| trend_slope | FLOAT | Linear regression slope | Direction |
| trend_direction | STRING | rising/falling/stable | Classification |
| momentum | FLOAT | Recent vs historical avg | Momentum signal |
| momentum_pct | FLOAT | Momentum % | Momentum signal |
| days_since_peak | INTEGER | Days from peak value | Timing |
| days_since_trough | INTEGER | Days from trough | Timing |
| pct_off_peak | FLOAT | Current vs peak % | Relative position |
| pct_above_trough | FLOAT | Current vs trough % | Relative position |
| value_signal | STRING | strong_buy/buy/hold/sell/strong_sell | **Signal** |
| days_tracked | INTEGER | Tracking duration | Data quality |
| snapshots_count | INTEGER | Number of observations | Data quality |

---

## Situational Data

### 9. GameWeather
**Records:** 5,593 | **Years:** 2000-2020 | **Granularity:** Game

| Property | Type | Description | ML Relevance |
|----------|------|-------------|--------------|
| game_id | STRING | Game identifier | Join key |
| season | INTEGER | NFL season | Temporal |
| stadium | STRING | Stadium name | Location |
| home_team | STRING | Home team | Context |
| roof_type | STRING | dome/outdoor/retractable | Venue type |
| temperature | FLOAT | Temperature (F) | **Weather feature** |
| humidity | FLOAT | Humidity % | Weather feature |
| wind_speed | FLOAT | Wind (mph) | **Weather feature** |
| wind_direction | FLOAT | Wind direction (degrees) | Weather feature |
| precipitation | FLOAT | Precipitation (inches) | Weather feature |
| condition | STRING | Weather description | Weather feature |
| is_dome | INTEGER | 1 = dome game | Binary feature |
| is_cold | INTEGER | 1 = temp < 40F | Binary feature |
| is_windy | INTEGER | 1 = wind > 15mph | Binary feature |
| has_precipitation | INTEGER | 1 = rain/snow | Binary feature |

### 10. InjuryReport
**Records:** 49,484 | **Years:** 2016-2024 | **Granularity:** Player-Week

| Property | Type | Description | ML Relevance |
|----------|------|-------------|--------------|
| player_id | STRING | GSIS identifier | Join key |
| player_name | STRING | Full name | Display |
| season | INTEGER | NFL season | Temporal |
| week | INTEGER | Week number | Temporal |
| team | STRING | Team | Context |
| position | STRING | Position | Stratification |
| injury_category | STRING | soft_tissue_leg/knee/concussion/etc | **Injury type** |
| severity | STRING | out/doubtful/questionable/probable | **Severity** |
| practice_status | STRING | Practice participation | Recovery indicator |
| game_type | STRING | Regular/playoff | Context |

### 11. PlayerInjuryProfile
**Records:** 4,254 | **Coverage:** Aggregated | **Granularity:** Player

| Property | Type | Description | ML Relevance |
|----------|------|-------------|--------------|
| player_id | STRING | GSIS identifier | Join key |
| player_name | STRING | Full name | Display |
| position | STRING | Position | Stratification |
| soft_tissue_leg_count | INTEGER | Hamstring/quad/calf injuries | **Injury history** |
| soft_tissue_upper_count | INTEGER | Shoulder/pec injuries | Injury history |
| knee_injury_count | INTEGER | Knee injuries | Injury history |
| ankle_foot_count | INTEGER | Ankle/foot injuries | Injury history |
| concussion_count | INTEGER | Concussion count | **Critical metric** |
| back_neck_count | INTEGER | Back/neck injuries | Injury history |
| games_listed_out | INTEGER | Total games OUT | **Availability** |
| games_questionable | INTEGER | Games questionable | Durability |
| total_injury_reports | INTEGER | Total injury reports | Injury prone indicator |
| soft_tissue_risk | STRING | low/medium/high | **Risk score** |
| structural_risk | STRING | low/medium/high | Risk score |
| concussion_risk | STRING | low/medium/high | Risk score |
| overall_injury_risk | STRING | low/medium/high | **Composite risk** |
| first_injury_season | INTEGER | First injury year | Career injury timeline |
| last_injury_season | INTEGER | Most recent injury | Recency |

### 12. DepthChartEntry
**Records:** 18,496 | **Years:** 2023-2024 | **Granularity:** Player-Week

| Property | Type | Description | ML Relevance |
|----------|------|-------------|--------------|
| player_id | STRING | GSIS identifier | Join key |
| player_name | STRING | Full name | Display |
| season | INTEGER | NFL season | Temporal |
| week | INTEGER | Week number | Temporal |
| team | STRING | Team | Context |
| position | STRING | Position | Stratification |
| depth_team | INTEGER | 1=starter, 2=backup, etc | **Depth position** |
| formation | STRING | Formation name | Scheme context |
| role | STRING | starter/backup/third_string/depth | **Role classification** |
| formation_role | STRING | slot/outside/inline_te/etc | **Usage type** |
| jersey_number | INTEGER | Jersey number | Identifier |

### 13. PlayerRoleProfile
**Records:** 699 | **Coverage:** Aggregated | **Granularity:** Player

| Property | Type | Description | ML Relevance |
|----------|------|-------------|--------------|
| player_id | STRING | GSIS identifier | Join key |
| player_name | STRING | Full name | Display |
| position | STRING | Position | Stratification |
| starter_weeks | INTEGER | Weeks as starter | Role stability |
| backup_weeks | INTEGER | Weeks as backup | Role stability |
| total_depth_chart_weeks | INTEGER | Total weeks tracked | Data quality |
| starter_rate | FLOAT | Starter weeks / total | **Starter probability** |
| slot_weeks | INTEGER | Weeks in slot (WR) | Alignment |
| outside_weeks | INTEGER | Weeks outside (WR) | Alignment |
| alignment | STRING | slot_primary/outside_primary/versatile | **WR alignment** |
| primary_role | STRING | established_starter/starter_backup_mix/etc | **Role classification** |
| first_season | INTEGER | First season tracked | Timeline |
| last_season | INTEGER | Last season tracked | Timeline |

---

## Game & Betting Data

### 14. Game
**Records:** 28,940 | **Years:** 1920-2024 | **Granularity:** Game

| Property | Type | Description | ML Relevance |
|----------|------|-------------|--------------|
| game_id | STRING | Game identifier | Primary key |
| season | INTEGER | NFL season | Temporal |
| week | INTEGER | Week number | Temporal |
| game_type | STRING | REG/POST | Context |
| gameday | STRING | Game date | Temporal |
| home_team | STRING | Home team | Context |
| away_team | STRING | Away team | Context |
| home_score | INTEGER | Home final score | Outcome |
| away_score | INTEGER | Away final score | Outcome |
| result | INTEGER | Home margin | Outcome |
| total | INTEGER | Total points | Outcome |
| overtime | INTEGER | 1 = went to OT | Game feature |
| div_game | INTEGER | 1 = divisional | Context |
| roof | STRING | Venue roof type | Context |
| surface | STRING | Playing surface | Context |
| stadium | STRING | Stadium name | Context |

**Betting Data (538 Elo + Spreadspoke):**

| Property | Type | Description | ML Relevance |
|----------|------|-------------|--------------|
| home_elo_pre | FLOAT | Home Elo rating (pre-game) | **Team strength** |
| away_elo_pre | FLOAT | Away Elo rating (pre-game) | **Team strength** |
| elo_win_prob_home | FLOAT | Elo-based win probability | **Expected outcome** |
| spread_line | FLOAT | Vegas point spread | **Market expectation** |
| over_under_line | FLOAT | Total points line | **Game pace expectation** |
| home_elo_post | FLOAT | Home Elo (post-game) | Rating change |
| away_elo_post | FLOAT | Away Elo (post-game) | Rating change |

**Coverage Statistics:**
- Games with Elo data: 16,810 (1920-2020)
- Games with spread data: 9,665
- Games with O/U data: 9,593

---

## Entity Nodes

### 15. Player
**Records:** 25,312 | **Granularity:** Player (unique)

| Property | Type | Description | ML Relevance |
|----------|------|-------------|--------------|
| gsis_id | STRING | GSIS identifier | Primary key |
| name | STRING | Full name | Display |
| display_name | STRING | Display name | Display |
| position | STRING | Position | Stratification |
| height | INTEGER | Height (inches) | Physical |
| weight | INTEGER | Weight (lbs) | Physical |

### 16. Team
**Records:** 32 | **Granularity:** NFL Team

### 17. TeamSeason
**Records:** 36 | **Granularity:** Team-Season

---

## Aggregation Nodes

### 18. WeeklyStats / SeasonStats / SnapCount / NGSStats
Duplicate/current-season versions of historical data.

### 19. CareerStage
**Records:** 480 | Career phase classifications.

### 20. SeasonWeatherAgg
**Records:** 21 | Season-level weather aggregations.

### 21. Scheme
**Records:** 5 | Offensive scheme classifications.

---

## Feature Engineering Recommendations

### High-Value Features for Dynasty Value Prediction

**Scoring Standard: 0.5 PPR (Half-Point Per Reception)**
- Passing: 0.04 pts/yard, 4 pts/TD, -2 pts/INT
- Rushing: 0.1 pts/yard, 6 pts/TD
- Receiving: 0.1 pts/yard, 6 pts/TD, **0.5 pts/reception**

**From HistoricalSeasonStats:**
- `ppg_half_ppr` (Y-1, Y-2, Y-3 seasons) - **Primary production metric**
- Season-over-season deltas
- Games played trends

**From HistoricalSnapCount:**
- `offense_pct` trends (snap share trajectory)
- Week-over-week snap volatility
- End-of-season snap share vs start

**From HistoricalNGS:**
- Passing: `completion_percentage_above_expectation`, `aggressiveness`
- Rushing: `efficiency`, `avg_rush_yards`
- Receiving: `avg_separation`, `avg_yac_above_expectation`

**From CombineResult:**
- Position-adjusted athletic percentiles
- Speed score (weight * 200 / forty^4)
- Burst score (vertical + broad_jump)

**From DraftPick:**
- Draft capital (inverse of pick number)
- Round as categorical

**From PlayerInjuryProfile:**
- `overall_injury_risk`
- `games_listed_out` (career total)
- Soft tissue injury count

**From PlayerRoleProfile:**
- `starter_rate`
- `primary_role` encoding
- WR `alignment`

**From KTCTrend:**
- `momentum_pct`
- `trend_direction`
- `pct_off_peak`

**From GameWeather (aggregated to player-season):**
- Home games in dome vs outdoor
- Cold game exposure
- Wind game exposure

---

## Data Quality Notes

| Data Source | Coverage | Missing Data Issues |
|-------------|----------|---------------------|
| HistoricalSeasonStats | 1999-2023 | Complete for fantasy-relevant players |
| HistoricalWeeklyStats | 1999-2024 | Complete |
| HistoricalSnapCount | 2015-2024 | Good coverage, some early years sparse |
| HistoricalNGS | 2016-2024 | Only available from 2016 |
| CombineResult | 2000-2024 | ~70% of drafted players have data |
| DraftPick | 2000-2024 | Complete for drafted players |
| KTCSnapshot | June-Dec 2025 | Daily snapshots available |
| GameWeather | 2000-2020 | Ends in 2020, needs update |
| InjuryReport | 2016-2024 | Good coverage |
| DepthChartEntry | 2023-2024 | Recent only |
| Game (betting) | 1920-2020 | Elo: 16,810 games; Spread: 9,665 games |

---

## Neural Network Viability Assessment

### Sample Size Summary by Granularity

| Approach | Samples | NN Viable? | Notes |
|----------|---------|------------|-------|
| **Weekly-level** | 143,593 | ✅ **YES** | Strongest option - well above 20K threshold |
| **Game-level (with betting)** | 28,940 | ✅ **YES** | Good for game context models |
| **Player-week combinations** | ~15,000/season | ✅ **YES** | Multi-season pooling recommended |
| **Season-level** | ~2,500 | ⚠️ **Marginal** | GBM likely outperforms NN |
| **KTC value prediction** | 292 | ❌ **No** | Too few samples for NN |

### Verdict: YES - Neural Networks Are Now Viable

With **143,593 weekly player records** and **28,940 games** (16,810 with Elo data), you have sufficient data for effective neural network training.

**Recommended Architecture:**
1. **Weekly Fantasy Prediction (LSTM/Transformer)**
   - Input: Player sequence (past N weeks) + game context + betting lines
   - Features: snap%, targets, weather, injury status, Elo differential, spread, O/U
   - Target: Weekly fantasy points (0.5 PPR)
   - Expected improvement over GBM: 5-15% on volatile players

2. **Multi-Task Learning (Production + Value)**
   - Shared encoder for player embeddings
   - Task heads: PPG prediction, injury risk, value classification
   - Leverage all 750K nodes for representation learning

3. **Graph Neural Network (Advanced)**
   - Player→Team→Game relationships
   - Propagate Elo strength through team connections
   - Learn positional value curves from graph structure

### Why Betting Data Matters

| Feature | ML Value |
|---------|----------|
| `elo_win_prob_home` | Team strength differential - correlates with game script |
| `spread_line` | Market expectation of margin - affects play calling |
| `over_under_line` | Total points expectation - predicts pace and passing volume |
| Elo changes | Team trajectory signals - improvement vs decline |

---

## Recommended Training Dataset Construction

### Option 1: Weekly Fantasy Prediction (Best for NN)
- **Samples:** 143,593 player-week records
- **Features:** 50+ (player stats, snap%, injury, weather, Elo, spread, O/U)
- **Target:** Weekly fantasy points (0.5 PPR)
- **Model:** LSTM, Transformer, or TabNet
- **Expected performance:** MAE ~4-5 pts, outperforms GBM on variance

### Option 2: Season-Level Production (GBM Preferred)
- **Samples:** ~2,500 player-season pairs
- **Features:** 93+ engineered features
- **Target:** Next-season PPG (0.5 PPR)
- **Model:** GBM (R² ~0.62-0.68)
- **Note:** NN won't significantly outperform GBM at this sample size

### Option 3: Dynasty Value Prediction
- **Samples:** 52,013 KTC snapshots + historical performance
- **Features:** Production trends, age, injury history, KTC momentum
- **Target:** KTC value or value_signal classification
- **Model:** Gradient boosting or ensemble

---

## Quick Start Queries

### Get Player Training Features
```cypher
MATCH (p:Player {gsis_id: $player_id})
OPTIONAL MATCH (s:HistoricalSeasonStats {player_id: p.gsis_id})
OPTIONAL MATCH (c:CombineResult {player_id: p.gsis_id})
OPTIONAL MATCH (d:DraftPick {player_id: p.gsis_id})
OPTIONAL MATCH (ip:PlayerInjuryProfile {player_id: p.gsis_id})
OPTIONAL MATCH (rp:PlayerRoleProfile {player_id: p.gsis_id})
OPTIONAL MATCH (kt:KTCTrend {player_name: p.name})
RETURN p, collect(s), c, d, ip, rp, kt
```

### Get High-Risk Injury Players
```cypher
MATCH (pip:PlayerInjuryProfile)
WHERE pip.overall_injury_risk = 'high'
RETURN pip.player_name, pip.position, pip.games_listed_out
ORDER BY pip.games_listed_out DESC
```

### Get Buy Signals
```cypher
MATCH (kt:KTCTrend)
WHERE kt.value_signal IN ['strong_buy', 'buy']
RETURN kt.player_name, kt.current_ktc, kt.momentum_pct, kt.value_signal
ORDER BY kt.momentum_pct DESC
```

---

*Last Updated: December 2024*
*Total Records: ~750,000 nodes*
