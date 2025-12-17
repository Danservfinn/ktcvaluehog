# Dynasty Edge: Neo4j Graph Database + ML Implementation Proposal

## Executive Summary

This proposal outlines a comprehensive Neo4j graph database schema to integrate NFL data from nflverse, Sleeper fantasy league data, and KeepTradeCut dynasty valuations. The design enables machine learning feature engineering, correlation discovery, and AI agent interactions for dynasty fantasy football analysis.

---

## 1. Data Sources Inventory

### 1.1 NFLverse Data - Complete Inventory

#### Core Player & Team Data
| Dataset | Rows | Cols | Key Fields | ML Value |
|---------|------|------|------------|----------|
| **load_players** | 24,342 | 39 | gsis_id, display_name, position, birth_date, college, height, weight | Player identity |
| **load_teams** | 36 | 16 | team_abbr, team_name, conference, division, colors, logos | Team metadata |
| **load_rosters** | 3,129/season | 36 | team, position, depth_chart, status, jersey_number | Current rosters |
| **load_rosters_weekly** | 46,579/season | 36 | Weekly roster snapshots dating back to 2002 | Roster changes |
| **load_schedules** | 272/season | 46 | game_id, scores, spreads, over/under, weather | Game context |

#### Player Statistics
| Dataset | Rows | Cols | Key Fields | ML Value |
|---------|------|------|------------|----------|
| **load_player_stats** | 15,000+/season | 114 | fantasy_points, EPA, targets, CPOE, WOPR, air_yards | **CORE ML FEATURES** |
| **load_pbp** | 38,000+/season | 372 | EPA, WPA, CPOE, xYAC, completion probability | Granular play-level |
| **load_ff_opportunity** | 4,729/season | 159 | Expected vs actual production, efficiency | **HIGH ML VALUE** |

#### Advanced Analytics
| Dataset | Rows | Cols | Key Fields | ML Value |
|---------|------|------|------------|----------|
| **load_nextgen_stats (passing)** | 614/season | 29 | time_to_throw, air_yards, aggressiveness | QB evaluation |
| **load_nextgen_stats (receiving)** | 1,435/season | 23 | avg_cushion, avg_separation, catch_pct | WR/TE evaluation |
| **load_nextgen_stats (rushing)** | 601/season | 22 | efficiency, 8+_defenders_pct, yards_before_contact | RB evaluation |
| **load_pfr_advstats (pass)** | 697/season | 24 | drops, bad_throws, on_target_pct | Pass quality |
| **load_pfr_advstats (rush)** | 2,359/season | 16 | yards_before_contact, yards_after_contact | Rush quality |
| **load_pfr_advstats (rec)** | 4,453/season | 17 | broken_tackles, yards_after_catch | Receiving quality |
| **load_pfr_advstats (def)** | 7,992/season | 29 | pressures, hurries, tackles | Defensive stats |
| **load_ftn_charting** | 48,031/season | 29 | **PLAY CHARTING** - see below | **VERY HIGH ML VALUE** |

#### FTN Charting Data (High Value)
```
Play Design:          Pass Quality:           QB Context:
├── is_play_action    ├── is_catchable_ball   ├── is_qb_out_of_pocket
├── is_rpo            ├── is_contested_ball   ├── is_qb_fault_sack
├── is_screen_pass    ├── is_drop             ├── qb_location
├── is_trick_play     ├── is_interception_worthy  └── read_thrown
└── is_qb_sneak       └── is_throw_away

Defense Context:
├── n_blitzers
├── n_pass_rushers
└── n_defense_box
```

#### Team-Level Statistics
| Dataset | Rows | Cols | Key Fields | ML Value |
|---------|------|------|------------|----------|
| **load_team_stats** | 570/season | 102 | Team passing, rushing, receiving, defensive aggregates | Team context |
| **load_snap_counts** | 20,928/season | 16 | offense_snaps, offense_pct, defense_snaps | Usage metrics |
| **load_depth_charts** | 323,509 | 12 | position rank, depth chart slot | Opportunity |

#### Historical & Draft Data
| Dataset | Rows | Cols | Key Fields | ML Value |
|---------|------|------|------------|----------|
| **load_draft_picks** | 12,670 | 36 | round, pick, college, age, HOF status | Draft capital |
| **load_combine** | 8,649 | 18 | 40-time, bench, vertical, broad jump, 3-cone | Athletic profile |
| **load_contracts** | 49,340 | 25 | value, APY, guaranteed, years | Financial context |
| **load_trades** | 4,847 | 11 | trade details, picks exchanged | Market behavior |

#### Fantasy & ID Mapping
| Dataset | Rows | Cols | Key Fields | ML Value |
|---------|------|------|------------|----------|
| **load_ff_playerids** | 12,168 | 35 | gsis_id, sleeper_id, espn_id, yahoo_id, pff_id | **ID MAPPING** |
| **load_ff_rankings** | 5,628 | 25 | ECR, expert consensus, ADP | Market sentiment |

#### ESPN Data (Direct Download Required)
| Dataset | Rows | Cols | Key Fields | ML Value |
|---------|------|------|------------|----------|
| **ESPN QBR Season** | 1,511 | 23 | qbr_total, pts_added, epa_total, pass, run, sack | QB evaluation |
| **ESPN QBR Week** | 10,590 | 30 | Weekly QBR breakdown | QB trending |

#### Other
| Dataset | Rows | Cols | Key Fields | ML Value |
|---------|------|------|------------|----------|
| **load_officials** | 2,055/season | 9 | game officials by position | Penalty analysis |
| **load_injuries** | varies | varies | Player injuries (when available) | Availability |
| **load_participation** | varies | varies | Play-by-play participation (2016-2024) | Usage detail |

### Total Data Volume Summary
```
TOTAL UNIQUE DATASETS: 28
TOTAL COLUMNS AVAILABLE: 1,500+
TOTAL ROWS (single season): ~250,000+
HISTORICAL DEPTH: 1999-present (varies by dataset)
```

### 1.2 KeepTradeCut Data
- Player dynasty values (SF and 1QB)
- Position rankings
- Age and rookie status
- Trend data (requires scraping or API)

### 1.3 Sleeper League Data
- Roster compositions
- League settings (SF, TEP, etc.)
- Transaction history
- Draft results
- Standings and matchups

---

## 2. Neo4j Schema Design

### 2.1 Node Types

```cypher
// Core Entities
(:Player {
    // Identity
    gsis_id: STRING,           // Primary NFL ID
    sleeper_id: STRING,        // Sleeper platform ID
    name: STRING,
    display_name: STRING,

    // Demographics
    position: STRING,          // QB, RB, WR, TE
    birth_date: DATE,
    age: FLOAT,
    height: INTEGER,           // inches
    weight: INTEGER,           // pounds
    college: STRING,

    // Draft Info
    draft_year: INTEGER,
    draft_round: INTEGER,
    draft_pick: INTEGER,

    // Combine Metrics
    forty_time: FLOAT,
    bench_press: INTEGER,
    vertical_jump: FLOAT,
    broad_jump: INTEGER,
    three_cone: FLOAT,

    // Current Valuations
    ktc_value: INTEGER,
    ktc_value_1qb: INTEGER,
    ktc_updated: DATETIME,

    // Computed ML Features (updated periodically)
    career_epa_per_play: FLOAT,
    career_fantasy_ppg: FLOAT,
    target_share_avg: FLOAT,
    air_yards_share_avg: FLOAT,
    years_remaining: INTEGER,

    // ML Predictions
    predicted_ktc_value: INTEGER,
    value_delta: INTEGER,        // predicted - actual
    edge_signal: STRING          // BUY, SELL, HOLD
})

(:Team {
    team_abbr: STRING,         // Primary key (e.g., "KC")
    team_name: STRING,
    conference: STRING,
    division: STRING,

    // Current Season
    wins: INTEGER,
    losses: INTEGER,
    playoff_odds: FLOAT,

    // Offensive metrics (aggregated)
    pass_rate: FLOAT,
    neutral_pass_rate: FLOAT,
    plays_per_game: FLOAT
})

(:Game {
    game_id: STRING,           // e.g., "2025_01_KC_BAL"
    season: INTEGER,
    week: INTEGER,
    game_date: DATE,
    game_type: STRING,         // REG, POST

    // Results
    home_score: INTEGER,
    away_score: INTEGER,
    total_points: INTEGER,

    // Context
    spread: FLOAT,
    over_under: FLOAT,
    weather: STRING,
    roof: STRING
})

(:Season {
    season_year: INTEGER,
    week_count: INTEGER,
    current_week: INTEGER
})

(:FantasyLeague {
    league_id: STRING,         // Sleeper league ID
    name: STRING,
    platform: STRING,          // "sleeper"

    // Settings
    scoring_type: STRING,      // PPR, Half-PPR, Standard
    superflex: BOOLEAN,
    te_premium: FLOAT,
    roster_size: INTEGER,

    // Roster Positions
    qb_slots: INTEGER,
    rb_slots: INTEGER,
    wr_slots: INTEGER,
    te_slots: INTEGER,
    flex_slots: INTEGER,
    sf_slots: INTEGER
})

(:FantasyTeam {
    roster_id: STRING,
    owner_id: STRING,
    display_name: STRING,
    team_name: STRING,

    // Standings
    wins: INTEGER,
    losses: INTEGER,
    ties: INTEGER,
    fpts: FLOAT,
    fpts_against: FLOAT,

    // Computed
    roster_value: INTEGER,     // Sum of KTC values
    roster_age_avg: FLOAT
})

(:DraftPick {
    pick_id: STRING,           // e.g., "2025_1_early"
    season: INTEGER,
    round: INTEGER,
    projected_slot: STRING,    // early, mid, late

    ktc_value: INTEGER,
    original_owner_id: STRING
})

(:WeeklyPerformance {
    performance_id: STRING,    // player_id + game_id
    season: INTEGER,
    week: INTEGER,

    // Fantasy Production
    fantasy_points: FLOAT,
    fantasy_points_ppr: FLOAT,

    // Passing
    passing_yards: INTEGER,
    passing_tds: INTEGER,
    passing_interceptions: INTEGER,
    passing_epa: FLOAT,
    cpoe: FLOAT,

    // Rushing
    carries: INTEGER,
    rushing_yards: INTEGER,
    rushing_tds: INTEGER,
    rushing_epa: FLOAT,

    // Receiving
    targets: INTEGER,
    receptions: INTEGER,
    receiving_yards: INTEGER,
    receiving_tds: INTEGER,
    receiving_epa: FLOAT,
    target_share: FLOAT,
    air_yards_share: FLOAT,
    wopr: FLOAT,

    // Usage
    snap_pct: FLOAT,
    route_participation: FLOAT
})

(:Play {
    play_id: STRING,

    // Context
    down: INTEGER,
    ydstogo: INTEGER,
    yardline_100: INTEGER,

    // Outcome
    play_type: STRING,
    yards_gained: INTEGER,

    // Advanced
    epa: FLOAT,
    wpa: FLOAT,
    cpoe: FLOAT,
    xyac_epa: FLOAT,

    // Probability
    cp: FLOAT,                 // Completion probability
    xpass: FLOAT               // Expected pass rate
})

(:Transaction {
    transaction_id: STRING,
    type: STRING,              // trade, add, drop, waiver
    timestamp: DATETIME,

    // For trades
    side_a_players: [STRING],
    side_a_picks: [STRING],
    side_b_players: [STRING],
    side_b_picks: [STRING]
})
```

### 2.2 Relationships

```cypher
// Team Relationships
(:Player)-[:PLAYS_FOR {
    season: INTEGER,
    contract_years: INTEGER,
    contract_value: INTEGER
}]->(:Team)

(:Player)-[:PLAYED_IN {
    snap_count: INTEGER,
    snap_pct: FLOAT,
    targets: INTEGER,
    touches: INTEGER
}]->(:Game)

(:Game)-[:HOME_TEAM]->(:Team)
(:Game)-[:AWAY_TEAM]->(:Team)
(:Game)-[:IN_SEASON]->(:Season)

// Fantasy Relationships
(:FantasyTeam)-[:IN_LEAGUE]->(:FantasyLeague)
(:Player)-[:ROSTERED_BY {
    acquired_date: DATE,
    acquisition_type: STRING   // draft, trade, waiver
}]->(:FantasyTeam)

(:DraftPick)-[:OWNED_BY]->(:FantasyTeam)
(:DraftPick)-[:ORIGINALLY_FROM]->(:FantasyTeam)

// Performance Tracking
(:Player)-[:HAD_PERFORMANCE]->(:WeeklyPerformance)
(:WeeklyPerformance)-[:IN_GAME]->(:Game)
(:WeeklyPerformance)-[:FOR_SEASON]->(:Season)

// Play-Level (optional, high volume)
(:Player)-[:THREW]->(:Play)
(:Player)-[:RECEIVED]->(:Play)
(:Player)-[:RUSHED]->(:Play)
(:Play)-[:IN_GAME]->(:Game)

// Player Relationships (Graph Features for ML)
(:Player)-[:TARGETS_FROM {
    season: INTEGER,
    target_count: INTEGER,
    target_share: FLOAT
}]->(:Player)  // WR/TE -> QB

(:Player)-[:COMPETES_WITH {
    team: STRING,
    position: STRING
}]->(:Player)  // Same position, same team

(:Player)-[:HANDED_OFF_TO {
    season: INTEGER,
    handoff_count: INTEGER
}]->(:Player)  // QB -> RB

(:Player)-[:DRAFTED_BY]->(:Team)
(:Player)-[:COLLEGE_TEAMMATE]->(:Player)

// Transactions
(:Transaction)-[:INVOLVES_PLAYER]->(:Player)
(:Transaction)-[:INVOLVES_PICK]->(:DraftPick)
(:Transaction)-[:FROM_TEAM]->(:FantasyTeam)
(:Transaction)-[:TO_TEAM]->(:FantasyTeam)

// Historical Comparisons
(:Player)-[:SIMILAR_PROFILE {
    similarity_score: FLOAT,
    dimensions: [STRING]       // age, production, draft_capital, etc.
}]->(:Player)
```

### 2.3 Graph Features for ML

The graph structure enables powerful feature engineering:

```cypher
// Feature: QB Quality Score (for WR/TE valuation)
MATCH (receiver:Player)-[:TARGETS_FROM]->(qb:Player)
WHERE receiver.position IN ['WR', 'TE']
RETURN receiver.name,
       qb.name as qb,
       qb.career_epa_per_play as qb_epa,
       qb.age as qb_age,
       CASE WHEN qb.age < 26 THEN 'young_qb_boost' ELSE 'none' END as situation

// Feature: Competition Index
MATCH (p:Player)-[:COMPETES_WITH]-(competitor:Player)
WHERE p.position = 'RB'
RETURN p.name,
       count(competitor) as num_competitors,
       avg(competitor.ktc_value) as avg_competitor_value

// Feature: Target Concentration
MATCH (qb:Player)<-[:TARGETS_FROM]-(receiver:Player)
WHERE qb.position = 'QB'
WITH qb, collect(receiver) as receivers
RETURN qb.name,
       size(receivers) as num_targets,
       [r IN receivers | r.ktc_value][0..3] as top_3_receiver_values

// Feature: Team Offensive Environment
MATCH (p:Player)-[:PLAYS_FOR]->(t:Team)
MATCH (teammate:Player)-[:PLAYS_FOR]->(t)
WHERE teammate.position IN ['QB', 'RB', 'WR', 'TE']
RETURN p.name,
       t.pass_rate,
       t.plays_per_game,
       sum(teammate.ktc_value) as team_offensive_talent
```

---

## 3. AI Data Science Team Integration

### 3.1 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Dynasty Edge AI System                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   Neo4j      │    │   Feature    │    │   H2O ML     │      │
│  │   Graph DB   │───▶│   Store      │───▶│   Agent      │      │
│  │              │    │   (Parquet)  │    │              │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                   │                   │               │
│         │                   │                   │               │
│         ▼                   ▼                   ▼               │
│  ┌──────────────────────────────────────────────────────┐      │
│  │              AI Data Science Team Agents              │      │
│  ├──────────────────────────────────────────────────────┤      │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │      │
│  │  │ EDA Agent   │  │ Feature Eng │  │ ML Training │  │      │
│  │  │ (Correlation│  │ Agent       │  │ Agent (H2O) │  │      │
│  │  │  Discovery) │  │             │  │             │  │      │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  │      │
│  │                                                      │      │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │      │
│  │  │ Data Loader │  │ SQL Agent   │  │ Code Gen    │  │      │
│  │  │ Agent       │  │ (Cypher)    │  │ Agent       │  │      │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  │      │
│  └──────────────────────────────────────────────────────┘      │
│                            │                                    │
│                            ▼                                    │
│  ┌──────────────────────────────────────────────────────┐      │
│  │              Claude AI Chat Interface                 │      │
│  │         (Dynasty Analysis & Recommendations)          │      │
│  └──────────────────────────────────────────────────────┘      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Agent Workflows

#### Workflow 1: KTC Value Prediction Model

```python
from ai_data_science_team.agents import (
    DataLoaderToolsAgent,
    FeatureEngineeringAgent,
    EDAToolsAgent,
    H2OMLAgent
)

# Step 1: Load and prepare data
data_loader = DataLoaderToolsAgent()
player_features = data_loader.invoke("""
    Load player data from Neo4j with these features:
    - age, position, draft_capital
    - career_fantasy_ppg, target_share_avg
    - qb_quality_score (from graph)
    - team_pass_rate, team_plays_per_game
    - competition_index (from graph)
    Target variable: ktc_value
""")

# Step 2: Automated EDA & Correlation Discovery
eda_agent = EDAToolsAgent()
correlations = eda_agent.invoke("""
    Analyze correlations with ktc_value.
    Identify top 20 predictive features.
    Flag multicollinearity issues.
    Generate visualizations.
""")

# Step 3: Feature Engineering
feature_agent = FeatureEngineeringAgent()
ml_ready_data = feature_agent.invoke("""
    Create ML-ready features:
    - Position-adjusted age curves
    - Interaction: age * production
    - Rolling averages (3-week, season)
    - Polynomial features for non-linear relationships
    - One-hot encode categorical variables
""")

# Step 4: Train Models with H2O
h2o_agent = H2OMLAgent()
models = h2o_agent.invoke("""
    Train regression models to predict ktc_value.
    Target: ktc_value
    Features: all engineered features
    Max runtime: 30 minutes
    Return top 5 models with feature importance.
""")
```

#### Workflow 2: Buy/Sell Signal Generation

```python
# Generate signals by comparing predicted vs actual KTC
signals_query = """
MATCH (p:Player)
WHERE p.position IN ['QB', 'RB', 'WR', 'TE']
  AND p.ktc_value > 1000
WITH p,
     p.predicted_ktc_value - p.ktc_value as value_delta,
     (p.predicted_ktc_value - p.ktc_value) / p.ktc_value * 100 as delta_pct
SET p.value_delta = value_delta,
    p.delta_pct = delta_pct,
    p.edge_signal = CASE
        WHEN delta_pct > 15 THEN 'STRONG_BUY'
        WHEN delta_pct > 5 THEN 'BUY'
        WHEN delta_pct < -15 THEN 'STRONG_SELL'
        WHEN delta_pct < -5 THEN 'SELL'
        ELSE 'HOLD'
    END
RETURN p.name, p.position, p.ktc_value, p.predicted_ktc_value,
       p.delta_pct, p.edge_signal
ORDER BY delta_pct DESC
"""
```

### 3.3 Feature Categories for ML

| Category | Features | Source |
|----------|----------|--------|
| **Demographics** | age, height, weight, draft_round, draft_pick | load_players, load_draft_picks |
| **Athletic Profile** | forty_time, bench, vertical, broad_jump, three_cone | load_combine |
| **Production** | fantasy_ppg, yards_per_game, tds_per_game | load_player_stats |
| **Efficiency** | EPA per play, CPOE, yards per target/carry | load_player_stats |
| **Opportunity** | target_share, snap_pct, air_yards_share, WOPR | load_ff_opportunity |
| **Situation (Graph)** | qb_quality, team_pass_rate, competition_index | Neo4j relationships |
| **Financial** | contract_years_remaining, apy, guaranteed | load_contracts |
| **Historical** | career_trajectory, similar_player_outcomes | Neo4j SIMILAR_PROFILE |
| **Market** | ktc_trend_30d, ecr_delta, adp_vs_ktc | load_ff_rankings |

---

## 4. Implementation Plan

### Phase 1: Neo4j Setup & Core Data (Week 1)

```
Tasks:
├── Install Neo4j Desktop / AuraDB
├── Create database schema (constraints, indexes)
├── Build data loaders:
│   ├── load_players → Player nodes
│   ├── load_teams → Team nodes
│   ├── load_rosters → PLAYS_FOR relationships
│   └── KTC scraper → ktc_value properties
├── Create ID mapping table (gsis_id ↔ sleeper_id)
└── Basic validation queries
```

### Phase 2: Full NFLverse Integration (Week 2)

```
Tasks:
├── Weekly stats pipeline:
│   ├── load_player_stats → WeeklyPerformance nodes
│   ├── load_snap_counts → snap_pct updates
│   └── load_ff_opportunity → opportunity metrics
├── Historical data:
│   ├── load_draft_picks → draft info
│   ├── load_combine → athletic profiles
│   └── load_contracts → financial data
├── Game-level data:
│   ├── load_schedules → Game nodes
│   └── load_pbp → Play nodes (optional, heavy)
└── Build refresh cron jobs
```

### Phase 3: Sleeper Integration (Week 3)

```
Tasks:
├── Sleeper API client:
│   ├── GET /league/{league_id}
│   ├── GET /league/{league_id}/rosters
│   ├── GET /league/{league_id}/transactions
│   └── GET /league/{league_id}/drafts
├── Create FantasyLeague, FantasyTeam nodes
├── Create ROSTERED_BY relationships
├── Transaction history loading
└── Real-time roster sync
```

### Phase 4: Graph Feature Engineering (Week 4)

```
Tasks:
├── Create relationship types:
│   ├── TARGETS_FROM (WR/TE → QB)
│   ├── COMPETES_WITH (same position)
│   ├── SIMILAR_PROFILE (historical comps)
│   └── HANDED_OFF_TO (QB → RB)
├── Compute graph-derived features:
│   ├── qb_quality_score
│   ├── competition_index
│   ├── team_offensive_environment
│   └── target_concentration
└── Feature store export (Parquet)
```

### Phase 5: ML Pipeline & Agents (Week 5-6)

```
Tasks:
├── Install ai-data-science-team
├── Configure agents:
│   ├── DataLoaderToolsAgent (Neo4j connection)
│   ├── EDAToolsAgent (correlation discovery)
│   ├── FeatureEngineeringAgent
│   └── H2OMLAgent
├── Train initial KTC prediction model
├── Generate buy/sell signals
├── Build model refresh pipeline
└── Dashboard integration
```

### Phase 6: Chat Integration (Week 7)

```
Tasks:
├── Extend Claude AI agent with Neo4j tools:
│   ├── Query player profiles
│   ├── Compare players
│   ├── Trade analysis
│   └── Explain ML predictions
├── Natural language → Cypher translation
├── Streaming responses with citations
└── Conversation memory (graph-based)
```

---

## 5. File Structure

```
ktcvaluehog/
├── data/
│   ├── raw/                    # Raw downloaded data
│   ├── processed/              # Cleaned data
│   └── features/               # ML feature store (parquet)
├── src/
│   ├── database/
│   │   ├── neo4j_client.py     # Neo4j connection
│   │   ├── schema.py           # Cypher schema definitions
│   │   └── loaders/
│   │       ├── nflverse_loader.py
│   │       ├── ktc_loader.py
│   │       └── sleeper_loader.py
│   ├── features/
│   │   ├── graph_features.py   # Graph-derived features
│   │   ├── time_series.py      # Rolling averages, trends
│   │   └── feature_store.py    # Export to parquet
│   ├── ml/
│   │   ├── agents.py           # AI Data Science Team config
│   │   ├── train_ktc_model.py  # Model training
│   │   └── signals.py          # Buy/sell signal generation
│   ├── api/
│   │   └── sleeper_client.py   # Sleeper API wrapper
│   └── chat/
│       ├── tools.py            # Claude tool definitions
│       └── cypher_translator.py # NL → Cypher
├── pipelines/
│   ├── daily_refresh.py        # Daily data refresh
│   ├── weekly_ml_update.py     # Weekly model retrain
│   └── realtime_sync.py        # Real-time Sleeper sync
├── dashboard.py                # Streamlit app
├── setup_neo4j.py             # Initial setup script
└── requirements.txt
```

---

## 6. Key Cypher Queries

### Player Profile with Graph Context

```cypher
MATCH (p:Player {name: $player_name})
OPTIONAL MATCH (p)-[:PLAYS_FOR]->(team:Team)
OPTIONAL MATCH (p)-[:TARGETS_FROM]->(qb:Player)
OPTIONAL MATCH (p)-[:COMPETES_WITH]-(competitor:Player)
OPTIONAL MATCH (p)-[:ROSTERED_BY]->(fantasy:FantasyTeam)
RETURN p,
       team.team_abbr as nfl_team,
       qb.name as qb_name,
       qb.age as qb_age,
       collect(DISTINCT competitor.name) as competitors,
       fantasy.display_name as fantasy_owner
```

### Trade Value Analysis

```cypher
// Compare two trade packages
WITH $side_a as side_a_names, $side_b as side_b_names
MATCH (a:Player) WHERE a.name IN side_a_names
WITH collect(a) as side_a_players, side_b_names
MATCH (b:Player) WHERE b.name IN side_b_names
WITH side_a_players, collect(b) as side_b_players
RETURN
    [p IN side_a_players | p.name] as side_a,
    reduce(s = 0, p IN side_a_players | s + p.ktc_value) as side_a_value,
    reduce(s = 0, p IN side_a_players | s + p.predicted_ktc_value) as side_a_predicted,
    [p IN side_b_players | p.name] as side_b,
    reduce(s = 0, p IN side_b_players | s + p.ktc_value) as side_b_value,
    reduce(s = 0, p IN side_b_players | s + p.predicted_ktc_value) as side_b_predicted
```

### ML Feature Export

```cypher
MATCH (p:Player)
WHERE p.position IN ['QB', 'RB', 'WR', 'TE']
  AND p.ktc_value > 500
OPTIONAL MATCH (p)-[:TARGETS_FROM]->(qb:Player)
OPTIONAL MATCH (p)-[:PLAYS_FOR]->(t:Team)
OPTIONAL MATCH (p)-[:COMPETES_WITH]-(comp:Player)
WITH p, qb, t, count(comp) as competition_count
RETURN
    p.gsis_id as player_id,
    p.name,
    p.position,
    p.age,
    p.draft_round,
    p.forty_time,
    p.career_fantasy_ppg,
    p.target_share_avg,
    qb.career_epa_per_play as qb_epa,
    qb.age as qb_age,
    t.pass_rate as team_pass_rate,
    competition_count,
    p.ktc_value as target
```

---

## 7. Next Steps

1. **Review this proposal** and provide feedback on scope/priorities
2. **Set up Neo4j** (Desktop or AuraDB cloud)
3. **Add Neo4j credentials** to .env file
4. **Run Phase 1** setup script
5. **Iterate** based on initial results

---

## Appendix: Required Dependencies

```txt
# Neo4j
neo4j>=5.0.0
py2neo>=2021.2.3

# NFLverse
nflreadpy>=0.1.0
polars>=0.20.0
pyarrow>=14.0.0

# AI Data Science Team
ai-data-science-team>=0.1.0
langchain>=0.1.0
h2o>=3.44.0

# Sleeper API
requests>=2.31.0
aiohttp>=3.9.0

# Data Processing
pandas>=2.0.0
numpy>=1.24.0

# Dashboard
streamlit>=1.30.0
plotly>=5.18.0

# ML
scikit-learn>=1.3.0
```
