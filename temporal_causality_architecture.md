# Dynasty Edge: Temporal Causality Architecture
## Addendum to Main Architecture Document

**Purpose:** Track how specific data points drive KTC value changes over time, enabling Claude to discover correlations and dynamically reweight the valuation model.

---

## The Problem with Static Snapshots

The initial architecture captures **current state** only:
```
(:Player {ktc_value: 9808, targets_per_game: 6.2})
```

But you can't answer: *"Did KTC rise because targets increased, or because of hype?"*

To answer causal questions, we need **temporal data**:
```
(:Player)-[:HAD_SNAPSHOT]->(:Snapshot {date: 2024-12-01, ktc: 9200, tpg: 5.8})
(:Player)-[:HAD_SNAPSHOT]->(:Snapshot {date: 2024-12-08, ktc: 9500, tpg: 6.1})
(:Player)-[:HAD_SNAPSHOT]->(:Snapshot {date: 2024-12-15, ktc: 9808, tpg: 6.2})
```

Now we can see: KTC +608 correlates with targets +0.4/game.

---

## Enhanced Data Model

### New Node Types

```cypher
// TEMPORAL SNAPSHOTS - Capture player state at each refresh
(:Snapshot {
    snapshot_id: STRING,        // player_id + date
    date: DATE,
    
    // Valuations
    ktc_value: INTEGER,
    ktc_delta: INTEGER,         // Change from previous snapshot
    ktc_delta_pct: FLOAT,
    
    // Volume metrics
    targets: INTEGER,           // Season total
    targets_per_game: FLOAT,
    receptions: INTEGER,
    rec_per_game: FLOAT,
    
    // Efficiency metrics
    yards_per_target: FLOAT,
    yards_per_reception: FLOAT,
    td_rate: FLOAT,
    
    // Usage metrics
    snap_share: FLOAT,
    target_share: FLOAT,
    air_yards_share: FLOAT,
    red_zone_targets: INTEGER,
    
    // Context metrics
    games_played: INTEGER,
    qb_change: BOOLEAN,         // Did QB change since last snapshot?
    injury_status: STRING,
    
    // Calculated
    ppg: FLOAT,                 // Fantasy points per game
    ppg_delta: FLOAT
})

// CORRELATIONS - Discovered relationships between metrics and KTC
(:Correlation {
    correlation_id: STRING,
    metric_name: STRING,        // e.g., "targets_per_game"
    position: STRING,           // QB, RB, WR, TE, or ALL
    
    // Statistical measures
    pearson_r: FLOAT,           // Correlation coefficient (-1 to 1)
    p_value: FLOAT,             // Statistical significance
    sample_size: INTEGER,
    
    // Time context
    lookback_days: INTEGER,     // How far back we looked
    discovered_date: DATE,
    
    // Interpretation
    strength: STRING,           // Strong, Moderate, Weak, None
    direction: STRING,          // Positive, Negative
    confidence: STRING,         // High, Medium, Low
    
    // Usage
    current_weight: FLOAT,      // How much we weight this in model
    suggested_weight: FLOAT,    // AI-suggested weight
    notes: STRING               // Claude's interpretation
})

// MODEL WEIGHTS - Current valuation model configuration
(:ModelConfig {
    config_id: STRING,          // "active" or version number
    created_date: DATETIME,
    created_by: STRING,         // "system" or "claude_suggestion"
    
    // Weight values (0.0 to 2.0, where 1.0 = neutral)
    w_age: FLOAT,
    w_targets_per_game: FLOAT,
    w_snap_share: FLOAT,
    w_target_share: FLOAT,
    w_qb_age: FLOAT,
    w_team_pass_volume: FLOAT,
    w_injury_history: FLOAT,
    w_competition: FLOAT,
    w_rookie_premium: FLOAT,
    
    // Meta
    backtest_accuracy: FLOAT,   // How well this config predicted KTC changes
    active: BOOLEAN
})

// WEIGHT HISTORY - Track weight changes over time
(:WeightChange {
    change_id: STRING,
    date: DATETIME,
    metric_name: STRING,
    old_weight: FLOAT,
    new_weight: FLOAT,
    reason: STRING,             // Why the change was made
    suggested_by: STRING,       // "claude", "user", "auto"
    correlation_id: STRING      // Link to supporting correlation
})

// PREDICTIONS - Track model predictions vs actual outcomes
(:Prediction {
    prediction_id: STRING,
    player_id: STRING,
    predicted_date: DATE,
    target_date: DATE,          // When we expect to evaluate
    
    predicted_ktc_delta: INTEGER,
    predicted_ktc_delta_pct: FLOAT,
    
    actual_ktc_delta: INTEGER,  // Filled in later
    actual_ktc_delta_pct: FLOAT,
    
    prediction_error: FLOAT,    // Actual - Predicted
    model_config_id: STRING,    // Which weights were used
    
    reasoning: STRING           // Claude's explanation
})
```

### New Relationships

```cypher
// Temporal relationships
(:Player)-[:HAD_SNAPSHOT {sequence: INTEGER}]->(:Snapshot)
(:Snapshot)-[:PREVIOUS]->(:Snapshot)  // Linked list of snapshots

// Correlation relationships  
(:Correlation)-[:APPLIES_TO]->(:Player)  // Position-specific correlations
(:Correlation)-[:DISCOVERED_FROM]->(:Snapshot)  // Evidence

// Model relationships
(:ModelConfig)-[:USES_WEIGHT]->(:Correlation)
(:WeightChange)-[:UPDATED]->(:ModelConfig)
(:WeightChange)-[:BASED_ON]->(:Correlation)

// Prediction tracking
(:Prediction)-[:PREDICTED_FOR]->(:Player)
(:Prediction)-[:USED_CONFIG]->(:ModelConfig)
```

---

## Temporal Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TEMPORAL DATA PIPELINE                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  TWICE DAILY REFRESH                                                         │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                                                                         │ │
│  │  1. Fetch current data (KTC, stats, injuries)                          │ │
│  │                         │                                               │ │
│  │                         ▼                                               │ │
│  │  2. Create new Snapshot nodes for each player                          │ │
│  │     - Calculate deltas from previous snapshot                          │ │
│  │     - Link to previous snapshot with [:PREVIOUS]                       │ │
│  │                         │                                               │ │
│  │                         ▼                                               │ │
│  │  3. Update Player node with current values                             │ │
│  │                         │                                               │ │
│  │                         ▼                                               │ │
│  │  4. Run correlation analysis (weekly)                                  │ │
│  │     - Correlate metric deltas with KTC deltas                          │ │
│  │     - Create/update Correlation nodes                                  │ │
│  │                         │                                               │ │
│  │                         ▼                                               │ │
│  │  5. Evaluate past predictions                                          │ │
│  │     - Fill in actual outcomes                                          │ │
│  │     - Calculate model accuracy                                         │ │
│  │                                                                         │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  WEEKLY ANALYSIS (Claude-driven)                                            │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                                                                         │ │
│  │  1. Claude reviews new correlations                                    │ │
│  │     "Targets per game has r=0.72 correlation with KTC for WRs"        │ │
│  │                         │                                               │ │
│  │                         ▼                                               │ │
│  │  2. Claude suggests weight adjustments                                 │ │
│  │     "Increase w_targets_per_game from 1.0 to 1.3 for WRs"             │ │
│  │                         │                                               │ │
│  │                         ▼                                               │ │
│  │  3. Backtest proposed weights                                          │ │
│  │     "New weights would have predicted KTC changes 15% better"         │ │
│  │                         │                                               │ │
│  │                         ▼                                               │ │
│  │  4. Apply weights (with user approval)                                 │ │
│  │     - Create new ModelConfig                                           │ │
│  │     - Log WeightChange                                                 │ │
│  │                                                                         │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Example: Tracking Target Share → KTC Correlation

### Step 1: Collect Temporal Data

```cypher
// Query: Get last 30 days of snapshots for WRs
MATCH (p:Player {position: 'WR'})-[:HAD_SNAPSHOT]->(s:Snapshot)
WHERE s.date > date() - duration('P30D')
RETURN p.name, s.date, s.ktc_value, s.ktc_delta, 
       s.targets_per_game, s.target_share
ORDER BY p.name, s.date
```

Sample output:
```
| name           | date       | ktc   | ktc_delta | tpg  | target_share |
|----------------|------------|-------|-----------|------|--------------|
| Drake London   | 2024-12-01 | 6800  | null      | 7.2  | 0.24         |
| Drake London   | 2024-12-08 | 6950  | +150      | 7.8  | 0.26         |
| Drake London   | 2024-12-15 | 7062  | +112      | 8.1  | 0.27         |
```

### Step 2: Calculate Correlation

```python
# In the correlation analysis script
import pandas as pd
from scipy import stats

def calculate_metric_correlation(metric_name: str, position: str, lookback_days: int = 30):
    """Calculate correlation between a metric's change and KTC change."""
    
    query = f"""
    MATCH (p:Player {{position: '{position}'}})-[:HAD_SNAPSHOT]->(s:Snapshot)
    WHERE s.date > date() - duration('P{lookback_days}D')
    WITH p, s ORDER BY s.date
    WITH p, collect(s) as snapshots
    WHERE size(snapshots) >= 2
    UNWIND range(1, size(snapshots)-1) as i
    WITH p, snapshots[i-1] as prev, snapshots[i] as curr
    RETURN p.name as player,
           curr.{metric_name} - prev.{metric_name} as metric_delta,
           curr.ktc_delta as ktc_delta
    """
    
    results = neo4j_client.run_query(query)
    df = pd.DataFrame(results)
    
    # Calculate Pearson correlation
    r, p_value = stats.pearsonr(df['metric_delta'], df['ktc_delta'])
    
    return {
        'metric': metric_name,
        'position': position,
        'pearson_r': round(r, 3),
        'p_value': round(p_value, 4),
        'sample_size': len(df),
        'strength': 'Strong' if abs(r) > 0.7 else 'Moderate' if abs(r) > 0.4 else 'Weak',
        'direction': 'Positive' if r > 0 else 'Negative'
    }
```

### Step 3: Store Correlation

```cypher
// Create or update correlation node
MERGE (c:Correlation {metric_name: 'targets_per_game', position: 'WR'})
SET c.pearson_r = 0.72,
    c.p_value = 0.001,
    c.sample_size = 150,
    c.lookback_days = 30,
    c.discovered_date = date(),
    c.strength = 'Strong',
    c.direction = 'Positive',
    c.confidence = 'High',
    c.current_weight = 1.0,
    c.suggested_weight = 1.3,
    c.notes = 'Strong positive correlation: WR KTC tends to rise when targets increase'
```

### Step 4: Claude Analyzes and Suggests

```
You: "What correlations have you found between player metrics and KTC changes?"

Claude: Let me query the correlation data.

[Executes cypher_query to get correlations]

I've analyzed 30 days of data across 150 WR snapshots. Here are the strongest 
correlations I found:

**WR Metrics → KTC Value Changes:**

| Metric            | Correlation | Strength | Current Weight | Suggested |
|-------------------|-------------|----------|----------------|-----------|
| targets_per_game  | r = 0.72    | Strong   | 1.0            | 1.3       |
| target_share      | r = 0.68    | Moderate | 1.0            | 1.2       |
| snap_share        | r = 0.45    | Moderate | 1.0            | 1.1       |
| yards_per_target  | r = 0.31    | Weak     | 1.0            | 1.0       |

**Key Insight:** KTC voters heavily weight volume metrics (targets) over 
efficiency metrics (yards per target). This creates an opportunity:

- **Undervalued:** Efficient WRs with lower target counts
- **Overvalued:** High-volume WRs with poor efficiency

**Recommendation:** Increase weight on targets_per_game from 1.0 to 1.3 in 
our model. This better matches how KTC actually moves, helping us predict 
value changes more accurately.

Would you like me to backtest this weight change?
```

### Step 5: Backtest and Apply

```
You: "Yes, backtest the suggested weights"

Claude: [Runs backtest tool]

**Backtest Results (Last 30 Days):**

| Metric                    | Old Weights | New Weights |
|---------------------------|-------------|-------------|
| Mean Absolute Error       | 312 KTC pts | 245 KTC pts |
| Prediction Accuracy (±5%) | 62%         | 74%         |
| Directional Accuracy      | 71%         | 83%         |

The new weights would have predicted KTC movements 21% more accurately.

**Top Improvements:**
- Drake London: Predicted +250, Actual +262 (was predicting +180)
- Jayden Higgins: Predicted +180, Actual +195 (was predicting +90)

**Recommendation:** Apply the new weights. This will help us:
1. Better predict which players' KTC will rise
2. Identify buy opportunities before the market catches up
3. Sell players whose KTC is about to drop

Apply these weights? (You can always revert)
```

---

## New Agent Tools

```python
TEMPORAL_TOOLS = [
    {
        "name": "get_player_history",
        "description": """Get historical snapshots for a player showing how their 
        metrics and KTC value have changed over time.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "player_name": {"type": "string"},
                "days": {"type": "integer", "description": "Number of days of history (default 30)"}
            },
            "required": ["player_name"]
        }
    },
    {
        "name": "get_correlations",
        "description": """Get discovered correlations between player metrics and KTC 
        value changes. Use to understand what drives KTC movements.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "position": {"type": "string", "enum": ["QB", "RB", "WR", "TE", "ALL"]},
                "min_strength": {"type": "string", "enum": ["Strong", "Moderate", "Weak"]}
            }
        }
    },
    {
        "name": "run_correlation_analysis",
        "description": """Analyze correlation between a specific metric and KTC changes.
        Creates or updates a Correlation node with the results.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "metric_name": {"type": "string", "description": "e.g., 'targets_per_game', 'snap_share'"},
                "position": {"type": "string"},
                "lookback_days": {"type": "integer"}
            },
            "required": ["metric_name", "position"]
        }
    },
    {
        "name": "suggest_weight_change",
        "description": """Suggest a change to a model weight based on correlation analysis.
        Records the suggestion for user review.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "metric_name": {"type": "string"},
                "current_weight": {"type": "number"},
                "suggested_weight": {"type": "number"},
                "reasoning": {"type": "string"}
            },
            "required": ["metric_name", "suggested_weight", "reasoning"]
        }
    },
    {
        "name": "backtest_weights",
        "description": """Backtest a set of model weights against historical data to see
        how well they would have predicted KTC changes.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "weights": {
                    "type": "object",
                    "description": "Dictionary of metric_name: weight pairs"
                },
                "lookback_days": {"type": "integer"}
            },
            "required": ["weights"]
        }
    },
    {
        "name": "apply_weights",
        "description": """Apply a new set of model weights. Creates a new ModelConfig 
        and logs the change history.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "weights": {"type": "object"},
                "reason": {"type": "string"}
            },
            "required": ["weights", "reason"]
        }
    },
    {
        "name": "get_model_accuracy",
        "description": """Get accuracy metrics for the current model weights based on
        recent predictions vs actual outcomes.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Evaluation period"}
            }
        }
    },
    {
        "name": "predict_ktc_change",
        "description": """Predict how a player's KTC value will change based on current
        metrics and model weights. Records prediction for later evaluation.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "player_name": {"type": "string"},
                "horizon_days": {"type": "integer", "description": "Days ahead to predict"}
            },
            "required": ["player_name"]
        }
    }
]
```

---

## Cypher Queries for Temporal Analysis

```cypher
// 1. Get player's KTC trajectory over time
MATCH (p:Player {name: 'Drake London'})-[:HAD_SNAPSHOT]->(s:Snapshot)
RETURN s.date, s.ktc_value, s.ktc_delta, s.targets_per_game, s.target_share
ORDER BY s.date DESC
LIMIT 10

// 2. Find players whose KTC rose most when targets increased
MATCH (p:Player {position: 'WR'})-[:HAD_SNAPSHOT]->(s:Snapshot)
WHERE s.date > date() - duration('P14D')
WITH p, s ORDER BY s.date
WITH p, collect(s) as snaps
WHERE size(snaps) >= 2
WITH p, snaps[-1] as latest, snaps[-2] as previous
WHERE latest.targets_per_game > previous.targets_per_game
  AND latest.ktc_delta > 100
RETURN p.name, 
       latest.targets_per_game - previous.targets_per_game as tpg_increase,
       latest.ktc_delta as ktc_increase
ORDER BY ktc_increase DESC

// 3. Find correlations that predict KTC movement
MATCH (c:Correlation)
WHERE c.strength IN ['Strong', 'Moderate']
  AND c.p_value < 0.05
RETURN c.metric_name, c.position, c.pearson_r, c.strength,
       c.current_weight, c.suggested_weight
ORDER BY abs(c.pearson_r) DESC

// 4. Compare model predictions vs actual outcomes
MATCH (pred:Prediction)-[:PREDICTED_FOR]->(p:Player)
WHERE pred.target_date <= date()
  AND pred.actual_ktc_delta IS NOT NULL
RETURN p.name, 
       pred.predicted_ktc_delta,
       pred.actual_ktc_delta,
       pred.prediction_error,
       pred.reasoning
ORDER BY abs(pred.prediction_error) DESC
LIMIT 20

// 5. Track weight changes over time
MATCH (wc:WeightChange)
RETURN wc.date, wc.metric_name, wc.old_weight, wc.new_weight, wc.reason
ORDER BY wc.date DESC

// 6. Find players with metric improvements not yet reflected in KTC
MATCH (p:Player)-[:HAD_SNAPSHOT]->(s:Snapshot)
WHERE s.date > date() - duration('P7D')
WITH p, s ORDER BY s.date DESC
WITH p, collect(s)[0] as latest, collect(s)[1] as previous
WHERE latest.targets_per_game > previous.targets_per_game * 1.15  // 15% increase
  AND latest.ktc_delta < 50  // KTC hasn't moved much
RETURN p.name, p.position,
       previous.targets_per_game as old_tpg,
       latest.targets_per_game as new_tpg,
       latest.ktc_value,
       'Targets up, KTC flat - potential buy' as signal
```

---

## Sample Conversation Flow

```
You: "I want to understand what's driving KTC value changes for WRs"

Claude: I'll analyze the temporal data to find correlations between 
WR metrics and their KTC movements.

[Runs correlation analysis for multiple metrics]

Here's what I found from the last 30 days of data (847 WR snapshots):

**Metrics Most Correlated with KTC Changes:**

1. **Targets per Game** (r = 0.72, p < 0.001) - STRONG
   - Every +1 target/game correlates with +180 KTC points
   - This is the #1 driver of WR value movement

2. **Target Share** (r = 0.68, p < 0.001) - MODERATE-STRONG
   - Gaining 5% target share → ~+250 KTC
   - Market rewards target volume heavily

3. **Snap Share** (r = 0.45, p < 0.01) - MODERATE
   - Playing more snaps helps, but less than targets

4. **Yards per Target** (r = 0.18, p = 0.08) - WEAK
   - Efficiency barely matters to KTC voters!

**Key Insight:** KTC is essentially a "volume index." Efficient players 
with moderate targets are systematically undervalued.

**Actionable Finding:**
Your Drake London (8.1 tpg, 27% target share) has seen +262 KTC in 2 weeks.
My model predicted +250 based on his target increase. This confirms our 
correlation is accurate.

Would you like me to:
1. Adjust weights to better predict KTC movements?
2. Find WRs with rising targets whose KTC hasn't caught up yet?
3. Identify your players whose KTC might drop (target share declining)?
```

---

## Updated Implementation Roadmap

### Additional Phase: Temporal Foundation (Week 3-4)

- [ ] Modify data pipeline to create Snapshot nodes
- [ ] Implement delta calculation on each refresh
- [ ] Create [:PREVIOUS] relationship linking
- [ ] Build correlation analysis module
- [ ] Create Correlation node storage

### Additional Phase: Learning Loop (Week 9-10)

- [ ] Implement backtest engine
- [ ] Create ModelConfig versioning
- [ ] Build weight change logging
- [ ] Add prediction tracking
- [ ] Create accuracy evaluation

---

## Storage Considerations

With twice-daily snapshots:
- ~500 players × 2 snapshots/day × 365 days = **365,000 snapshots/year**
- Neo4j handles this easily (free tier supports 200K nodes)
- Consider archiving snapshots older than 90 days to separate storage

**Recommendation:** Keep 90 days in Neo4j for active analysis, archive older data to CSV/Parquet for long-term backtesting.
