# Dynasty Edge: Novel Valuation Framework

## The Problem with Current Approaches

Existing dynasty valuation tools suffer from fundamental limitations:

1. **Static Snapshots**: They capture player value at a point in time, not trajectory
2. **Context Blindness**: Age-adjusted curves ignore situation, scheme, and ecosystem
3. **Market Following**: KTC and similar tools are reactive, following hype rather than predicting
4. **Isolation Bias**: Players are valued independently, ignoring interconnected effects
5. **Binary Thinking**: Players are "good" or "bad" rather than "good in context X"

**The opportunity**: Use graph theory to model fantasy football as a dynamic system of interconnected entities, enabling insights impossible with traditional analysis.

---

## Novel Valuation Concepts

### 1. Opportunity Flow Networks

**Concept**: Targets, carries, and air yards are finite resources that "flow" through a team's offense. When one player's share changes, others must adjust.

**Graph Model**:
```
(:Team)-[:HAS_OPPORTUNITY_POOL {
    total_targets: INTEGER,
    total_carries: INTEGER,
    total_air_yards: INTEGER
}]->(:Season)

(:Player)-[:CAPTURES_OPPORTUNITY {
    target_share: FLOAT,
    carry_share: FLOAT,
    air_yards_share: FLOAT,
    red_zone_share: FLOAT
}]->(:OpportunityPool)

(:Player)-[:CANNIBALIZES {
    correlation: FLOAT,        // Negative = one's gain is other's loss
    elasticity: FLOAT          // How much does X move when Y moves
}]->(:Player)
```

**Novel Insight**: Calculate "Opportunity Elasticity" - when Player A's targets increase by 10%, how much do Players B, C, D decrease? This reveals:
- Who is the "protected" receiver (lowest elasticity)
- Who is the "swing" receiver (highest elasticity)
- What happens when Player A leaves (redistribution prediction)

**Cypher Query**:
```cypher
// Find opportunity redistribution when a player leaves
MATCH (leaving:Player {name: "Davante Adams"})-[c:CAPTURES_OPPORTUNITY]->(pool:OpportunityPool)
MATCH (teammate:Player)-[tc:CAPTURES_OPPORTUNITY]->(pool)
MATCH (teammate)-[can:CANNIBALIZES]->(leaving)
WHERE teammate <> leaving
RETURN teammate.name,
       tc.target_share as current_share,
       tc.target_share - (c.target_share * can.elasticity) as projected_share_if_leaves,
       (tc.target_share - (c.target_share * can.elasticity)) - tc.target_share as share_delta
ORDER BY share_delta DESC
```

---

### 2. Career Trajectory Graphs

**Concept**: Every player follows a career "path" through stages. By mapping historical paths, we can predict future trajectories.

**Graph Model**:
```
(:CareerStage {
    position: STRING,
    age_bucket: STRING,         // "22-23", "24-25", etc.
    production_tier: STRING,    // "Elite", "WR1", "WR2", "WR3", "Depth"
    situation_quality: STRING   // "Great", "Good", "Average", "Poor"
})

(:Player)-[:WAS_AT {
    season: INTEGER,
    fantasy_ppg: FLOAT,
    ktc_value: INTEGER
}]->(:CareerStage)

(:CareerStage)-[:TYPICALLY_LEADS_TO {
    probability: FLOAT,
    avg_seasons: FLOAT,
    sample_size: INTEGER
}]->(:CareerStage)
```

**Novel Insight**: "Trajectory Probability Modeling"
- Given a player's current stage, what are the probabilistic paths forward?
- Which historical players followed similar paths? What happened to them?
- What's the "expected career value" (sum of future production weighted by probability)?

**Example**:
```
Malik Nabers (Age 21, WR12, Great Situation)
├── 65% → Elite WR (Age 23-27) → Expected Value: +4000 KTC
├── 25% → WR1 (Age 23-30) → Expected Value: +2000 KTC
├── 8%  → Injury/Decline → Expected Value: -1500 KTC
└── 2%  → Bust → Expected Value: -3000 KTC

Trajectory-Adjusted Value = Current KTC + Σ(probability × expected_delta)
```

---

### 3. Chemistry Quantification Index (CQI)

**Concept**: QB-WR "chemistry" is often discussed but never quantified. Using FTN charting data, we can create a precise chemistry score.

**Components**:
1. **Target Quality Differential**: Catchable ball rate for this WR vs. team average
2. **Trust Score**: Target share in high-leverage situations (3rd down, red zone, 2-minute)
3. **Air Yards Preference**: Does QB target this WR on deeper routes vs. checkdowns?
4. **Contested Confidence**: Willingness to throw contested balls to this WR

**Graph Model**:
```
(:Player)-[:HAS_CHEMISTRY_WITH {
    // Raw metrics
    catchable_rate: FLOAT,
    team_avg_catchable_rate: FLOAT,

    // Derived scores
    target_quality_differential: FLOAT,  // catchable - team_avg
    trust_score: FLOAT,                   // (RZ_share + 3rd_down_share + 2min_share) / 3
    depth_preference: FLOAT,              // Avg air yards vs team avg
    contested_confidence: FLOAT,          // Contested rate × catch rate

    // Composite
    chemistry_index: FLOAT,               // Weighted combination
    chemistry_percentile: INTEGER         // vs all QB-WR pairs
}]->(:Player)
```

**Novel Insight**: Separate "volume" from "quality"
- High volume + high chemistry = True alpha (Ja'Marr Chase + Burrow)
- High volume + low chemistry = Scheme-dependent (could regress)
- Low volume + high chemistry = Breakout candidate (underutilized trust)
- Low volume + low chemistry = Avoid

**Value Adjustment**:
```
Chemistry-Adjusted Value = Base Value × (1 + (CQI - 50) × 0.01)

Example: WR with CQI of 75 (75th percentile chemistry)
Adjustment = 1 + (75 - 50) × 0.01 = 1.25
If base value = 6000, chemistry-adjusted = 7500
```

---

### 4. Scheme Fit Matrix

**Concept**: Players have skill profiles; schemes have requirements. The intersection determines fit.

**Graph Model**:
```
(:SkillProfile {
    route_tree_diversity: FLOAT,      // How many routes can they run?
    separation_ability: FLOAT,         // From NextGen
    contested_catch_ability: FLOAT,    // From PFR
    yac_ability: FLOAT,                // YAC over expected
    speed_score: FLOAT,                // Athletic testing
    size_score: FLOAT                  // Height × weight optimization
})

(:Scheme {
    scheme_id: STRING,
    name: STRING,                       // "West Coast", "Air Raid", "Shanahan", etc.

    // Requirements
    route_diversity_weight: FLOAT,
    separation_weight: FLOAT,
    contested_weight: FLOAT,
    yac_weight: FLOAT,
    speed_weight: FLOAT,
    size_weight: FLOAT
})

(:Player)-[:HAS_PROFILE]->(:SkillProfile)
(:Team)-[:RUNS_SCHEME]->(:Scheme)

(:Player)-[:FITS_SCHEME {
    fit_score: FLOAT,                  // Dot product of profile × requirements
    ceiling_in_scheme: FLOAT,
    floor_in_scheme: FLOAT
}]->(:Scheme)
```

**Novel Insight**: "Counterfactual Valuation"
- What would Player X be worth on Team Y?
- Which free agents/trade targets would maximize value in YOUR team's scheme?
- Which players are "scheme trapped" (great skills, wrong scheme)?

**Query**:
```cypher
// Find undervalued players in wrong schemes
MATCH (p:Player)-[:HAS_PROFILE]->(profile:SkillProfile)
MATCH (p)-[:PLAYS_FOR]->(current_team:Team)-[:RUNS_SCHEME]->(current_scheme:Scheme)
MATCH (p)-[current_fit:FITS_SCHEME]->(current_scheme)
MATCH (better_scheme:Scheme)
WHERE better_scheme <> current_scheme
MATCH (p)-[better_fit:FITS_SCHEME]->(better_scheme)
WITH p, current_fit.fit_score as current,
     better_scheme, better_fit.fit_score as potential,
     better_fit.fit_score - current_fit.fit_score as upside
WHERE upside > 0.2  // 20%+ improvement possible
RETURN p.name, p.ktc_value,
       current_scheme.name as current_scheme,
       current as current_fit,
       better_scheme.name as ideal_scheme,
       potential as ideal_fit,
       upside,
       p.ktc_value * (1 + upside) as scheme_optimized_value
ORDER BY upside DESC
```

---

### 5. Market Momentum & Sentiment Cycles

**Concept**: Player values follow predictable cycles based on recency bias, narrative, and market psychology.

**Graph Model**:
```
(:ValueSnapshot {
    date: DATE,
    ktc_value: INTEGER,
    ecr_rank: INTEGER,
    adp: FLOAT,

    // Sentiment indicators
    reddit_mentions: INTEGER,
    twitter_sentiment: FLOAT,
    expert_buy_pct: FLOAT
})

(:Player)-[:HAD_VALUE]->(:ValueSnapshot)

(:ValueSnapshot)-[:NEXT]->(:ValueSnapshot)

(:Player)-[:IN_CYCLE {
    cycle_phase: STRING,        // "hype", "peak", "disillusionment", "recovery", "plateau"
    days_in_phase: INTEGER,
    momentum: FLOAT             // Rate of change
}]->(:MarketCycle)
```

**Novel Insight**: "Market Timing Signals"
- Players follow a "hype cycle" similar to Gartner's technology cycle
- Buy during "disillusionment trough" (post-hype, pre-recovery)
- Sell during "peak of inflated expectations"

**Cycle Detection Algorithm**:
```python
def detect_market_cycle(value_history):
    """
    Phases:
    1. Discovery (low volume, stable price)
    2. Hype (increasing volume, rising price)
    3. Peak (high volume, price plateau)
    4. Disillusionment (decreasing volume, falling price)
    5. Recovery (stable volume, gradual rise)
    6. Plateau (mature, efficient pricing)
    """
    momentum = calculate_momentum(value_history)
    volume = calculate_discussion_volume(value_history)

    if momentum > 0.1 and volume_increasing:
        return "HYPE"  # Don't buy, consider selling
    elif momentum < -0.1 and volume_decreasing:
        return "DISILLUSIONMENT"  # BUY SIGNAL
    elif momentum > 0 and volume_stable:
        return "RECOVERY"  # Hold or buy
    # ... etc
```

---

### 6. Injury Cascade Modeling

**Concept**: Injuries create cascading effects through the graph - opportunity redistribution, opponent strength changes, fantasy roster impacts.

**Graph Model**:
```
(:InjuryEvent {
    player_id: STRING,
    injury_date: DATE,
    expected_return: DATE,
    severity: STRING             // "minor", "moderate", "major", "career"
})

(:Player)-[:BENEFITS_FROM_INJURY {
    opportunity_gain: FLOAT,
    value_gain_estimate: INTEGER,
    confidence: FLOAT
}]->(:InjuryEvent)

(:Player)-[:HARMED_BY_INJURY {
    opportunity_loss: FLOAT,
    value_loss_estimate: INTEGER
}]->(:InjuryEvent)

(:Team)-[:WEAKENED_BY]->(:InjuryEvent)
(:Team)-[:PLAYS_AGAINST_WEAKENED]->(opponent:Team)-[:WEAKENED_BY]->(:InjuryEvent)
```

**Novel Insight**: "Injury Beta"
- Some players have high "injury beta" - their value swings dramatically based on teammate injuries
- Handcuffs have obvious injury beta, but what about WRs when the RB1 goes down (more passing)?
- Defenses facing injured offenses become more valuable

**Query**:
```cypher
// Find players with highest injury upside
MATCH (backup:Player)-[:COMPETES_WITH]->(starter:Player)
WHERE starter.ktc_value > backup.ktc_value
  AND starter.position = backup.position
WITH backup, starter,
     (starter.ktc_value * 0.7) - backup.ktc_value as value_gap,
     starter.injury_history_score as starter_injury_risk
RETURN backup.name as handcuff,
       backup.ktc_value as current_value,
       starter.name as starter,
       starter.ktc_value as starter_value,
       value_gap as upside_if_injured,
       starter_injury_risk,
       value_gap * starter_injury_risk as expected_injury_value
ORDER BY expected_injury_value DESC
LIMIT 20
```

---

### 7. Positional Ecosystem Modeling

**Concept**: A team's offense is an ecosystem. Model the entire system, not individual players.

**Graph Model**:
```
(:OffensiveEcosystem {
    team: STRING,
    season: INTEGER,

    // System metrics
    total_fantasy_points: FLOAT,
    point_concentration: FLOAT,     // Gini coefficient of fantasy distribution
    alpha_dependency: FLOAT,         // % of production from top player
    depth_score: FLOAT              // Production from players 4+
})

(:Player)-[:ROLE_IN_ECOSYSTEM {
    role: STRING,                   // "alpha", "beta", "gamma", "specialist"
    ecosystem_share: FLOAT,
    replaceability: FLOAT,          // How hard to replace this role?
    system_impact: FLOAT            // How much does system suffer if removed?
}]->(:OffensiveEcosystem)

(:OffensiveEcosystem)-[:SIMILAR_STRUCTURE]->(:OffensiveEcosystem)
```

**Novel Insight**: "System Risk Analysis"
- Some ecosystems are robust (multiple reliable options)
- Some are fragile (one player carries everything)
- Value players in robust ecosystems higher (less variance)
- Identify "system players" who would decline if alpha leaves

**Ecosystem Valuation Adjustment**:
```
Ecosystem-Adjusted Value = Base Value × Ecosystem Multiplier

Where Ecosystem Multiplier =
    (1 + ecosystem_robustness × 0.1) ×   // Robust systems are better
    (1 - alpha_dependency × 0.15) ×       // High dependency = risk
    (1 + depth_score × 0.05)              // Good depth = upside
```

---

### 8. Graph Centrality for Influence Measurement

**Concept**: Use graph algorithms to measure player "importance" beyond raw stats.

**Algorithms**:
1. **PageRank**: Who do winning fantasy teams acquire? (Trade network analysis)
2. **Betweenness Centrality**: Who connects different parts of the value network?
3. **Eigenvector Centrality**: Who is connected to other important players?

**Graph Model**:
```
(:FantasyTeam)-[:TRADED_FOR {
    date: DATE,
    season: INTEGER,
    gave_up_value: INTEGER
}]->(:Player)

(:FantasyTeam)-[:WON_CHAMPIONSHIP {season: INTEGER}]->(:Season)
```

**Novel Insight**: "Winner's Portfolio Analysis"
- Run PageRank on trade network, weighted by team success
- Players frequently acquired by winners have higher "championship equity"
- Different from raw value - captures "winning DNA"

**Query**:
```cypher
// Championship PageRank
CALL gds.pageRank.stream({
    nodeProjection: ['Player', 'FantasyTeam'],
    relationshipProjection: {
        TRADED_FOR: {
            properties: ['championship_weight']
        }
    },
    relationshipWeightProperty: 'championship_weight'
})
YIELD nodeId, score
MATCH (p:Player) WHERE id(p) = nodeId
RETURN p.name, p.ktc_value, score as championship_pagerank
ORDER BY score DESC
LIMIT 50
```

---

## Revised Schema for Novel Insights

Based on these concepts, here are the schema additions needed:

### New Node Types

```cypher
// Career trajectory modeling
(:CareerStage {
    stage_id: STRING,
    position: STRING,
    age_bucket: STRING,
    production_tier: STRING,
    situation_tier: STRING
})

// Skill profiling for scheme fit
(:SkillProfile {
    profile_id: STRING,
    route_diversity: FLOAT,
    separation: FLOAT,
    contested_catch: FLOAT,
    yac_ability: FLOAT,
    speed: FLOAT,
    size: FLOAT
})

// Scheme definitions
(:Scheme {
    scheme_id: STRING,
    name: STRING,
    family: STRING,
    requirements: MAP
})

// Market tracking
(:ValueSnapshot {
    snapshot_id: STRING,
    date: DATE,
    ktc_value: INTEGER,
    ecr: INTEGER,
    momentum: FLOAT
})

// Ecosystem modeling
(:OffensiveEcosystem {
    ecosystem_id: STRING,
    team: STRING,
    season: INTEGER,
    total_points: FLOAT,
    concentration: FLOAT,
    robustness: FLOAT
})

// Opportunity pools
(:OpportunityPool {
    pool_id: STRING,
    team: STRING,
    season: INTEGER,
    total_targets: INTEGER,
    total_carries: INTEGER,
    total_air_yards: INTEGER
})
```

### New Relationships

```cypher
// Opportunity flow
(:Player)-[:CAPTURES_OPPORTUNITY {
    target_share: FLOAT,
    carry_share: FLOAT,
    air_yard_share: FLOAT,
    red_zone_share: FLOAT
}]->(:OpportunityPool)

(:Player)-[:CANNIBALIZES {
    elasticity: FLOAT,
    correlation: FLOAT
}]->(:Player)

// Career trajectories
(:Player)-[:WAS_AT {
    season: INTEGER,
    stats: MAP
}]->(:CareerStage)

(:CareerStage)-[:LEADS_TO {
    probability: FLOAT,
    avg_seasons: FLOAT,
    sample_size: INTEGER
}]->(:CareerStage)

// Chemistry
(:Player)-[:CHEMISTRY_WITH {
    catchable_differential: FLOAT,
    trust_score: FLOAT,
    depth_preference: FLOAT,
    chemistry_index: FLOAT
}]->(:Player)

// Scheme fit
(:Player)-[:HAS_PROFILE]->(:SkillProfile)
(:Team)-[:RUNS_SCHEME]->(:Scheme)
(:SkillProfile)-[:FITS {
    score: FLOAT,
    ceiling: FLOAT,
    floor: FLOAT
}]->(:Scheme)

// Market dynamics
(:Player)-[:HAD_VALUE]->(:ValueSnapshot)
(:ValueSnapshot)-[:NEXT]->(:ValueSnapshot)

// Ecosystem roles
(:Player)-[:ROLE_IN {
    role: STRING,
    share: FLOAT,
    replaceability: FLOAT,
    system_impact: FLOAT
}]->(:OffensiveEcosystem)

// Trade network for PageRank
(:FantasyTeam)-[:ACQUIRED {
    date: DATE,
    cost: INTEGER,
    team_record_at_time: STRING
}]->(:Player)
```

---

## Implementation Priority

### Tier 1: Highest Impact, Most Achievable
1. **Chemistry Quantification Index** - We have FTN data, this is directly computable
2. **Opportunity Flow Analysis** - Can build from existing target/carry data
3. **Scheme Fit Matrix** - Requires skill profiling but achievable

### Tier 2: High Impact, Moderate Effort
4. **Career Trajectory Graphs** - Need historical data aggregation
5. **Ecosystem Modeling** - Complex but valuable
6. **Injury Cascade Modeling** - Need injury data integration

### Tier 3: Novel but Complex
7. **Market Momentum Cycles** - Need KTC historical tracking
8. **Championship PageRank** - Need comprehensive trade history
9. **Counterfactual Valuation** - Most complex, highest ceiling

---

## The "Dynasty Edge Score"

Combining all insights into a single metric:

```
Dynasty Edge Score =
    Base_KTC_Value
    × Career_Trajectory_Multiplier      // Future path probability
    × Chemistry_Adjustment              // QB-WR relationship quality
    × Scheme_Fit_Multiplier             // Current situation optimization
    × Ecosystem_Robustness_Factor       // System reliability
    × Market_Timing_Signal              // Buy low/sell high indicator
    ÷ Injury_Risk_Discount              // Cascade risk exposure
    + Opportunity_Upside_Premium        // Elasticity-based upside
```

This creates a **context-aware, dynamic, graph-enhanced valuation** that captures insights impossible with traditional methods.

---

## What Makes This Truly Novel

1. **Graph-Native Thinking**: We're not just storing data in a graph - we're using graph algorithms (PageRank, centrality, path analysis) to generate insights

2. **System Modeling**: Instead of valuing players in isolation, we model the entire offensive ecosystem and value players within that context

3. **Counterfactual Analysis**: "What would this player be worth in a different situation?" - no existing tool does this

4. **Chemistry Quantification**: Everyone talks about QB-WR chemistry but no one has a rigorous, data-driven metric

5. **Market Psychology**: Applying behavioral finance concepts (hype cycles, momentum) to fantasy markets

6. **Cascade Effects**: Understanding how one change (injury, trade) propagates through the entire system

This framework transforms dynasty fantasy from "who has the most points" to "who will have the most points in context X, given trajectory Y, with chemistry Z."
