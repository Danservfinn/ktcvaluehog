# Dynasty Edge: Neo4j Schema v2.0

## Design Philosophy

With 28 datasets and 1,500+ columns available, we must be strategic about what goes into the graph database vs. what stays in a feature store (Parquet files).

**Graph DB (Neo4j)**: Relationships, entities, computed features, real-time queries
**Feature Store (Parquet)**: Raw stats, historical aggregates, ML training data

---

## Schema Overview

```
                                    ┌─────────────┐
                                    │   Season    │
                                    └──────┬──────┘
                                           │
                    ┌──────────────────────┼──────────────────────┐
                    │                      │                      │
                    ▼                      ▼                      ▼
             ┌─────────────┐        ┌─────────────┐        ┌─────────────┐
             │    Game     │        │    Team     │        │  DraftClass │
             └──────┬──────┘        └──────┬──────┘        └──────┬──────┘
                    │                      │                      │
                    │              ┌───────┴───────┐              │
                    │              │               │              │
                    ▼              ▼               ▼              ▼
             ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
             │   Player    │◄┤ TeamSeason  │ │  Scheme     │ │  Prospect   │
             └──────┬──────┘ └─────────────┘ └─────────────┘ └─────────────┘
                    │
        ┌───────────┼───────────┬───────────────┐
        │           │           │               │
        ▼           ▼           ▼               ▼
 ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
 │WeeklyStats  │ │ CareerStats │ │FantasyTeam  │ │  Contract   │
 └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
```

---

## Node Definitions

### 1. Player (Central Entity)

```cypher
(:Player {
    // === IDENTITY (from load_players, load_ff_playerids) ===
    gsis_id: STRING,              // Primary key - NFL official ID
    sleeper_id: STRING,           // Sleeper platform ID
    espn_id: STRING,              // ESPN ID
    pfr_id: STRING,               // Pro Football Reference ID
    pff_id: STRING,               // PFF ID

    name: STRING,
    display_name: STRING,
    first_name: STRING,
    last_name: STRING,

    // === DEMOGRAPHICS ===
    position: STRING,             // QB, RB, WR, TE
    birth_date: DATE,
    age: FLOAT,                   // Calculated

    // === PHYSICAL (from load_players, load_combine) ===
    height: INTEGER,              // inches
    weight: INTEGER,              // pounds
    forty_time: FLOAT,
    bench_press: INTEGER,
    vertical_jump: FLOAT,
    broad_jump: INTEGER,
    three_cone: FLOAT,
    shuttle: FLOAT,
    arm_length: FLOAT,
    hand_size: FLOAT,

    // === DRAFT (from load_draft_picks) ===
    draft_year: INTEGER,
    draft_round: INTEGER,
    draft_pick: INTEGER,
    draft_team: STRING,
    college: STRING,

    // === CURRENT STATUS (from load_rosters) ===
    current_team: STRING,
    roster_status: STRING,        // Active, IR, Practice Squad
    depth_chart_position: INTEGER,
    jersey_number: INTEGER,

    // === VALUATIONS (from KTC, calculated) ===
    ktc_value_sf: INTEGER,        // Superflex value
    ktc_value_1qb: INTEGER,       // 1QB value
    ktc_rank_sf: INTEGER,
    ktc_position_rank: INTEGER,
    ktc_updated: DATETIME,

    // === ML PREDICTIONS (calculated) ===
    predicted_ktc_value: INTEGER,
    value_delta: INTEGER,         // predicted - actual
    value_delta_pct: FLOAT,
    edge_signal: STRING,          // STRONG_BUY, BUY, HOLD, SELL, STRONG_SELL
    confidence_score: FLOAT,

    // === CAREER AGGREGATES (calculated from stats) ===
    career_games: INTEGER,
    career_fantasy_ppg: FLOAT,
    career_epa_per_play: FLOAT,

    // Updated timestamp
    updated_at: DATETIME
})
```

### 2. PlayerSeason (Seasonal Aggregates)

```cypher
(:PlayerSeason {
    // === IDENTITY ===
    id: STRING,                   // {gsis_id}_{season}
    gsis_id: STRING,
    season: INTEGER,

    // === BASIC STATS (from load_player_stats) ===
    games_played: INTEGER,
    fantasy_points: FLOAT,
    fantasy_points_ppr: FLOAT,
    fantasy_ppg: FLOAT,

    // === PASSING ===
    pass_attempts: INTEGER,
    completions: INTEGER,
    passing_yards: INTEGER,
    passing_tds: INTEGER,
    interceptions: INTEGER,
    passing_epa: FLOAT,
    cpoe: FLOAT,                  // Completion % over expected

    // === RUSHING ===
    carries: INTEGER,
    rushing_yards: INTEGER,
    rushing_tds: INTEGER,
    rushing_epa: FLOAT,
    yards_per_carry: FLOAT,

    // === RECEIVING ===
    targets: INTEGER,
    receptions: INTEGER,
    receiving_yards: INTEGER,
    receiving_tds: INTEGER,
    receiving_epa: FLOAT,
    target_share: FLOAT,
    air_yards_share: FLOAT,
    wopr: FLOAT,                  // Weighted Opportunity Rating
    racr: FLOAT,                  // Receiver Air Conversion Ratio

    // === OPPORTUNITY (from load_ff_opportunity) ===
    expected_fantasy_points: FLOAT,
    fantasy_points_over_expected: FLOAT,
    route_participation: FLOAT,

    // === NEXTGEN STATS (from load_nextgen_stats) ===
    // Passing
    avg_time_to_throw: FLOAT,
    avg_air_yards: FLOAT,
    aggressiveness: FLOAT,
    // Receiving
    avg_separation: FLOAT,
    avg_cushion: FLOAT,
    catch_pct_over_expected: FLOAT,
    // Rushing
    rush_efficiency: FLOAT,
    stacked_box_pct: FLOAT,
    yards_before_contact: FLOAT,

    // === PFR ADVANCED (from load_pfr_advstats) ===
    drop_rate: FLOAT,
    contested_catch_rate: FLOAT,
    broken_tackles: INTEGER,
    yards_after_contact: FLOAT,
    pressures_allowed: INTEGER,   // For QBs/OL context

    // === FTN CHARTING AGGREGATES (from load_ftn_charting) ===
    play_action_rate: FLOAT,
    rpo_rate: FLOAT,
    screen_rate: FLOAT,
    catchable_target_rate: FLOAT,
    contested_target_rate: FLOAT,
    drop_rate_ftn: FLOAT,
    interception_worthy_rate: FLOAT,
    qb_pocket_time_avg: FLOAT,
    avg_blitzers_faced: FLOAT,
    avg_box_defenders: FLOAT,

    // === USAGE (from load_snap_counts) ===
    total_snaps: INTEGER,
    snap_pct_avg: FLOAT,

    // === ESPN QBR (for QBs) ===
    qbr_total: FLOAT,
    qbr_pts_added: FLOAT
})
```

### 3. Team

```cypher
(:Team {
    // === IDENTITY (from load_teams) ===
    team_abbr: STRING,            // Primary key (KC, BAL, etc.)
    team_name: STRING,
    team_nick: STRING,

    // === ORGANIZATION ===
    conference: STRING,           // AFC, NFC
    division: STRING,             // North, South, East, West

    // === BRANDING ===
    primary_color: STRING,
    secondary_color: STRING,
    logo_url: STRING,

    // Updated
    updated_at: DATETIME
})
```

### 4. TeamSeason (Team Context for ML)

```cypher
(:TeamSeason {
    // === IDENTITY ===
    id: STRING,                   // {team_abbr}_{season}
    team_abbr: STRING,
    season: INTEGER,

    // === RECORD ===
    wins: INTEGER,
    losses: INTEGER,
    ties: INTEGER,
    playoff_seed: INTEGER,

    // === OFFENSIVE TENDENCIES (from load_team_stats, load_pbp aggregates) ===
    pass_rate: FLOAT,
    neutral_pass_rate: FLOAT,     // Pass rate in neutral game scripts
    plays_per_game: FLOAT,
    points_per_game: FLOAT,

    // === PASSING ENVIRONMENT ===
    team_pass_epa: FLOAT,
    team_pass_attempts: INTEGER,
    team_pass_yards: INTEGER,
    team_pass_tds: INTEGER,

    // === RUSHING ENVIRONMENT ===
    team_rush_epa: FLOAT,
    team_rush_attempts: INTEGER,
    team_rush_yards: INTEGER,
    team_rush_tds: INTEGER,

    // === SCHEME (from load_ftn_charting aggregates) ===
    play_action_rate: FLOAT,
    rpo_rate: FLOAT,
    screen_rate: FLOAT,
    shotgun_rate: FLOAT,
    no_huddle_rate: FLOAT,

    // === OFFENSIVE LINE ===
    sacks_allowed: INTEGER,
    pressure_rate: FLOAT,

    // === PACE ===
    seconds_per_play: FLOAT,

    // === ML FEATURES ===
    offensive_rank: INTEGER,      // 1-32
    pass_funnel_score: FLOAT,     // How much team funnels to passing
    rb_committee_score: FLOAT     // RB workload concentration
})
```

### 5. Game

```cypher
(:Game {
    // === IDENTITY (from load_schedules) ===
    game_id: STRING,              // e.g., 2025_01_KC_BAL
    season: INTEGER,
    week: INTEGER,
    game_type: STRING,            // REG, WC, DIV, CON, SB

    // === TIMING ===
    game_date: DATE,
    game_time: STRING,
    day_of_week: STRING,

    // === TEAMS ===
    home_team: STRING,
    away_team: STRING,

    // === RESULTS ===
    home_score: INTEGER,
    away_score: INTEGER,
    total_points: INTEGER,
    winner: STRING,

    // === BETTING (from load_schedules) ===
    spread: FLOAT,
    over_under: FLOAT,

    // === CONDITIONS ===
    location: STRING,
    roof: STRING,                 // dome, outdoors, retractable
    surface: STRING,
    weather: STRING,
    temp: INTEGER,
    wind: INTEGER
})
```

### 6. FantasyLeague

```cypher
(:FantasyLeague {
    // === IDENTITY ===
    league_id: STRING,            // Sleeper league ID
    platform: STRING,             // sleeper
    name: STRING,

    // === SETTINGS ===
    roster_size: INTEGER,
    scoring_type: STRING,         // PPR, HALF_PPR, STD
    superflex: BOOLEAN,
    te_premium: FLOAT,            // 0, 0.5, 1.0, 1.5

    // === ROSTER SLOTS ===
    qb_slots: INTEGER,
    rb_slots: INTEGER,
    wr_slots: INTEGER,
    te_slots: INTEGER,
    flex_slots: INTEGER,
    sf_slots: INTEGER,
    bench_slots: INTEGER,
    ir_slots: INTEGER,

    // === DRAFT ===
    draft_type: STRING,           // snake, auction, linear

    // === STATUS ===
    season: INTEGER,
    status: STRING                // pre_draft, in_season, complete
})
```

### 7. FantasyTeam

```cypher
(:FantasyTeam {
    // === IDENTITY ===
    roster_id: STRING,            // Sleeper roster ID
    owner_id: STRING,
    display_name: STRING,
    team_name: STRING,
    avatar_url: STRING,

    // === STANDINGS ===
    wins: INTEGER,
    losses: INTEGER,
    ties: INTEGER,
    fpts: FLOAT,
    fpts_against: FLOAT,
    playoff_seed: INTEGER,

    // === CALCULATED ===
    roster_value_sf: INTEGER,     // Sum of KTC values (SF)
    roster_value_1qb: INTEGER,    // Sum of KTC values (1QB)
    roster_age_avg: FLOAT,
    roster_age_weighted: FLOAT,   // Weighted by value

    // === WINDOW ===
    contender_score: FLOAT,       // 0-100 contender rating
    rebuild_score: FLOAT          // 0-100 rebuild rating
})
```

### 8. DraftPick

```cypher
(:DraftPick {
    // === IDENTITY ===
    pick_id: STRING,              // {season}_{round}_{original_owner}

    // === DETAILS ===
    season: INTEGER,
    round: INTEGER,
    pick_number: INTEGER,         // If known

    // === PROJECTION ===
    projected_slot: STRING,       // early, mid, late
    projected_pick_range: STRING, // 1-4, 5-8, 9-12

    // === VALUATION ===
    ktc_value: INTEGER,

    // === OWNERSHIP ===
    original_owner_id: STRING,
    current_owner_id: STRING
})
```

### 9. Contract

```cypher
(:Contract {
    // === IDENTITY ===
    contract_id: STRING,          // {gsis_id}_{year_signed}
    gsis_id: STRING,

    // === TERMS (from load_contracts) ===
    year_signed: INTEGER,
    years: INTEGER,
    total_value: INTEGER,
    apy: INTEGER,                 // Average per year
    guaranteed: INTEGER,

    // === CALCULATED ===
    years_remaining: INTEGER,
    cap_hit_current: INTEGER,
    dead_cap: INTEGER,

    // === CONTEXT ===
    apy_rank_position: INTEGER,   // Rank at position
    apy_pct_cap: FLOAT           // APY as % of cap
})
```

### 10. Transaction

```cypher
(:Transaction {
    // === IDENTITY ===
    transaction_id: STRING,

    // === DETAILS ===
    type: STRING,                 // trade, add, drop, waiver
    timestamp: DATETIME,
    season: INTEGER,
    week: INTEGER,

    // === TRADE DETAILS ===
    side_a_value: INTEGER,        // KTC value of side A
    side_b_value: INTEGER,        // KTC value of side B
    value_differential: INTEGER,

    // === STATUS ===
    status: STRING                // completed, pending, vetoed
})
```

---

## Relationships

### Player Relationships

```cypher
// Current team
(:Player)-[:PLAYS_FOR {
    season: INTEGER,
    signed_date: DATE,
    depth_chart_rank: INTEGER
}]->(:Team)

// Seasonal stats (one per season)
(:Player)-[:HAD_SEASON]->(:PlayerSeason)

// Historical teams
(:Player)-[:PLAYED_FOR {
    seasons: [INTEGER],
    games: INTEGER
}]->(:Team)

// Fantasy ownership
(:Player)-[:ROSTERED_BY {
    acquired_date: DATE,
    acquisition_type: STRING,     // draft, trade, waiver, fa
    acquisition_cost: STRING      // pick given up, FAAB, etc.
}]->(:FantasyTeam)

// Contract
(:Player)-[:HAS_CONTRACT]->(:Contract)

// Draft
(:Player)-[:DRAFTED_BY {
    year: INTEGER,
    round: INTEGER,
    pick: INTEGER
}]->(:Team)
```

### Graph Features (ML-Critical Relationships)

```cypher
// QB-Receiver Connection (HIGH ML VALUE)
(:Player)-[:TARGETS_FROM {
    season: INTEGER,
    targets: INTEGER,
    target_share: FLOAT,
    receptions: INTEGER,
    yards: INTEGER,
    tds: INTEGER,
    epa_per_target: FLOAT,

    // FTN Charting aggregates for this pair
    catchable_rate: FLOAT,
    contested_rate: FLOAT,
    air_yards_avg: FLOAT
}]->(:Player)

// Backfield Competition (HIGH ML VALUE)
(:Player)-[:COMPETES_WITH {
    team: STRING,
    season: INTEGER,
    position: STRING,

    // Snap share comparison
    player_snap_share: FLOAT,
    competitor_snap_share: FLOAT,

    // Touch share comparison
    player_touch_share: FLOAT,
    competitor_touch_share: FLOAT
}]->(:Player)

// QB-RB Handoff Relationship
(:Player)-[:HANDS_OFF_TO {
    season: INTEGER,
    carries: INTEGER,
    carry_share: FLOAT,
    rushing_epa: FLOAT,

    // FTN context
    stacked_box_rate: FLOAT,
    play_action_rate: FLOAT
}]->(:Player)

// Historical Player Comparisons (ML similarity)
(:Player)-[:SIMILAR_TO {
    similarity_score: FLOAT,
    comparison_age: INTEGER,      // Age when compared

    // Dimensions used
    athletic_similarity: FLOAT,
    production_similarity: FLOAT,
    draft_capital_similarity: FLOAT,
    usage_similarity: FLOAT,

    // Outcome (for historical comps)
    comp_career_value: INTEGER    // What the comp achieved
}]->(:Player)

// College Connection
(:Player)-[:COLLEGE_TEAMMATE {
    seasons_together: INTEGER,
    college: STRING
}]->(:Player)
```

### Team Relationships

```cypher
// Team season stats
(:Team)-[:HAD_SEASON]->(:TeamSeason)

// Game participation
(:Team)-[:PLAYED_HOME]->(:Game)
(:Team)-[:PLAYED_AWAY]->(:Game)

// Division rivals (for schedule context)
(:Team)-[:DIVISION_RIVAL]->(:Team)
```

### Fantasy Relationships

```cypher
// League membership
(:FantasyTeam)-[:IN_LEAGUE]->(:FantasyLeague)

// Pick ownership
(:DraftPick)-[:OWNED_BY]->(:FantasyTeam)
(:DraftPick)-[:ORIGINALLY_FROM]->(:FantasyTeam)

// Transactions
(:Transaction)-[:INVOLVES_PLAYER]->(:Player)
(:Transaction)-[:INVOLVES_PICK]->(:DraftPick)
(:Transaction)-[:FROM_TEAM]->(:FantasyTeam)
(:Transaction)-[:TO_TEAM]->(:FantasyTeam)
```

### Temporal Relationships

```cypher
// Season progression
(:PlayerSeason)-[:NEXT_SEASON]->(:PlayerSeason)
(:TeamSeason)-[:NEXT_SEASON]->(:TeamSeason)

// Game in season
(:Game)-[:IN_WEEK {week: INTEGER}]->(:TeamSeason)
```

---

## Indexes and Constraints

```cypher
// Unique constraints
CREATE CONSTRAINT player_gsis_id IF NOT EXISTS
  FOR (p:Player) REQUIRE p.gsis_id IS UNIQUE;

CREATE CONSTRAINT player_sleeper_id IF NOT EXISTS
  FOR (p:Player) REQUIRE p.sleeper_id IS UNIQUE;

CREATE CONSTRAINT team_abbr IF NOT EXISTS
  FOR (t:Team) REQUIRE t.team_abbr IS UNIQUE;

CREATE CONSTRAINT game_id IF NOT EXISTS
  FOR (g:Game) REQUIRE g.game_id IS UNIQUE;

CREATE CONSTRAINT fantasy_league_id IF NOT EXISTS
  FOR (fl:FantasyLeague) REQUIRE fl.league_id IS UNIQUE;

CREATE CONSTRAINT fantasy_team_roster_id IF NOT EXISTS
  FOR (ft:FantasyTeam) REQUIRE ft.roster_id IS UNIQUE;

CREATE CONSTRAINT player_season_id IF NOT EXISTS
  FOR (ps:PlayerSeason) REQUIRE ps.id IS UNIQUE;

CREATE CONSTRAINT team_season_id IF NOT EXISTS
  FOR (ts:TeamSeason) REQUIRE ts.id IS UNIQUE;

// Indexes for common queries
CREATE INDEX player_position IF NOT EXISTS FOR (p:Player) ON (p.position);
CREATE INDEX player_team IF NOT EXISTS FOR (p:Player) ON (p.current_team);
CREATE INDEX player_ktc IF NOT EXISTS FOR (p:Player) ON (p.ktc_value_sf);
CREATE INDEX player_edge IF NOT EXISTS FOR (p:Player) ON (p.edge_signal);
CREATE INDEX player_season_season IF NOT EXISTS FOR (ps:PlayerSeason) ON (ps.season);
CREATE INDEX game_season_week IF NOT EXISTS FOR (g:Game) ON (g.season, g.week);
```

---

## Data Flow Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                         DATA INGESTION LAYER                           │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                │
│  │  NFLverse    │  │   Sleeper    │  │     KTC      │                │
│  │  (28 datasets)│  │    API       │  │   Scraper    │                │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                │
│         │                 │                 │                         │
│         └────────────────┼─────────────────┘                         │
│                          ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │                    ID RESOLUTION LAYER                           │ │
│  │         (gsis_id ↔ sleeper_id ↔ espn_id ↔ pfr_id)              │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                          │                                            │
└──────────────────────────┼────────────────────────────────────────────┘
                           │
          ┌────────────────┴────────────────┐
          ▼                                 ▼
┌──────────────────────┐      ┌──────────────────────────────────────┐
│      NEO4J           │      │         FEATURE STORE                │
│   (Graph Database)   │      │      (Parquet Files)                 │
├──────────────────────┤      ├──────────────────────────────────────┤
│ • Player nodes       │      │ • Raw weekly stats                   │
│ • Team nodes         │      │ • Play-by-play data                  │
│ • Relationships      │      │ • Historical aggregates              │
│ • Graph features     │      │ • ML training datasets               │
│ • Real-time queries  │      │ • Time series data                   │
└──────────┬───────────┘      └─────────────────┬────────────────────┘
           │                                     │
           └──────────────┬──────────────────────┘
                          ▼
          ┌─────────────────────────────────────┐
          │        ML PIPELINE                   │
          ├─────────────────────────────────────┤
          │ • Feature engineering               │
          │ • Correlation discovery             │
          │ • H2O model training                │
          │ • Prediction generation             │
          └──────────────────┬──────────────────┘
                             │
                             ▼
          ┌─────────────────────────────────────┐
          │      APPLICATION LAYER              │
          ├─────────────────────────────────────┤
          │ • Streamlit Dashboard               │
          │ • Claude AI Chat                    │
          │ • Buy/Sell Signals                  │
          │ • Trade Analyzer                    │
          └─────────────────────────────────────┘
```

---

## What Goes Where

### Neo4j (Graph Database)
- Player entities with current state
- Team entities
- Fantasy league/team entities
- Relationships (TARGETS_FROM, COMPETES_WITH, etc.)
- Aggregated seasonal stats (PlayerSeason, TeamSeason)
- ML predictions and signals
- Real-time queryable data

### Feature Store (Parquet)
- Raw play-by-play data (372 columns × 38K rows/season)
- Weekly stats detail
- FTN charting raw data
- NextGen stats raw data
- Historical data for ML training
- Time series for trend analysis

### Why This Split?
1. **Neo4j excels at**: Relationship queries, connected data, real-time lookups
2. **Parquet excels at**: Columnar analytics, ML training, large scans
3. **Cost/Performance**: Graph queries are expensive for aggregations; Parquet is cheap for bulk analytics
