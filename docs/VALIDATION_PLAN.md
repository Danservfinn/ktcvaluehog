# Dynasty Value Model Validation Plan

## Executive Summary

This document outlines a comprehensive validation strategy for the Dynasty Edge valuation model, implementing three complementary approaches:

1. **Historical Backtesting** - Prove the model predicts value changes
2. **Dynasty League Integration** - Validate against real manager behavior
3. **Enhanced Features** - Improve predictive power with additional data

---

## Phase 1: Historical Backtesting Architecture

### Objective
Prove the model can predict which players will rise/fall in dynasty value by backtesting against historical data.

### Data Requirements

| Data Type | Source | Time Period |
|-----------|--------|-------------|
| Player Stats | nflreadpy | 2022, 2023, 2024 |
| KTC Values | Wayback Machine / KTC API | Jan 2023, Jan 2024, Dec 2024 |
| NextGen Stats | nflreadpy | 2022, 2023, 2024 |
| Draft Capital | nflreadpy | Historical |

### Methodology

```
Step 1: Gather Data (Jan 2023 snapshot)
- Player stats through 2022 season
- KTC values as of January 2023
- Player ages as of Jan 2023

Step 2: Train Model
- Use 2022 stats + Jan 2023 KTC as training data
- Target: Predict "value change" over next 12 months

Step 3: Make Predictions
- For each player, predict: RISE / STABLE / FALL
- Generate confidence scores

Step 4: Validate (Jan 2024)
- Compare predictions to actual Jan 2024 KTC values
- Calculate directional accuracy
- Measure by position, by value tier

Step 5: Forward Test (Dec 2024)
- Apply same methodology
- Validate predictions against current values
```

### Success Metrics

| Metric | Target | Description |
|--------|--------|-------------|
| Directional Accuracy | >60% | % of rise/fall predictions correct |
| Top Quartile Precision | >70% | Accuracy on highest-confidence picks |
| RMSE Improvement | >20% vs baseline | Better than naive "stay same" model |
| Sharpe-like Ratio | >1.0 | Risk-adjusted prediction quality |

---

## Phase 2: Dynasty League Integration (Sleeper API)

### Objective
Validate model recommendations against real dynasty manager behavior, particularly "sharp" managers who consistently win.

### Sleeper API Endpoints

```python
# Key endpoints
GET /user/{username}                    # Get user ID
GET /user/{user_id}/leagues/nfl/{year}  # Get leagues
GET /league/{league_id}/transactions    # Get trades
GET /league/{league_id}/rosters         # Get rosters
GET /players/nfl                        # Player database
```

### Data Collection Strategy

1. **Identify Expert Leagues**
   - Dynasty Nerds staff leagues
   - High-stakes leagues ($500+ buy-in)
   - Leagues with published trade data

2. **Collect Transaction Data**
   - All trades from 2023-2024
   - Player values at time of trade
   - Manager win rates (identify "sharp" managers)

3. **Analysis Framework**
   ```
   For each trade:
   - Calculate our model's value for each side
   - Determine which manager "won" per our model
   - Track manager's subsequent performance
   - If high-performing managers agree with our model = validation
   ```

### Sharp Manager Identification

```python
sharp_score = (
    0.4 * playoff_rate +           # % of seasons making playoffs
    0.3 * championship_rate +       # % of championships
    0.2 * points_vs_median +        # Consistency
    0.1 * roster_value_growth       # Asset appreciation
)
```

---

## Phase 3: Enhanced Feature Engineering

### New Features from NFLverse

| Feature | Source | Description | Expected Impact |
|---------|--------|-------------|-----------------|
| EPA/play | nflfastR | Expected points added per play | High |
| Snap Share | snap_counts | % of offensive snaps | High |
| Target Share | player_stats | Targets / Team Pass Attempts | High |
| Air Yards Share | nextgen | % of team air yards | Medium |
| Red Zone Targets | play-by-play | High-value opportunities | Medium |
| CPOE | nextgen | Completion % over expected (QB) | Medium |
| RYOE | nextgen | Rushing yards over expected | Medium |
| Route Participation | nextgen | % of routes run | Medium |
| Weighted Opportunity | calculated | Targets + (Carries * 0.5) | High |

### Feature Engineering Code

```python
# Weighted Opportunity Rating (WOPR)
wopr = (target_share * 1.5) + (air_yards_share * 0.7)

# Production Premium (vs replacement)
prod_premium = player_fpts - position_replacement_fpts

# Efficiency Score
efficiency = (epa_per_play * 100) + (yards_per_opportunity * 10)

# Opportunity Trend (YoY change)
opp_trend = current_year_opportunities / prior_year_opportunities

# Age-Adjusted Production
age_adj_prod = production * age_curve_factor[position][age]
```

### Expected Model Improvement

| Current Model | Enhanced Model |
|---------------|----------------|
| R² = 0.999 (overfitting to KTC rank) | R² = 0.85+ (predicting value change) |
| 5 age-based features | 40+ production features |
| Predicts current value | Predicts future value trajectory |

---

## Implementation Order

### Day 1: Data Infrastructure
1. Create historical data loader
2. Set up Sleeper API client
3. Build feature engineering pipeline

### Day 2: Backtesting Framework
1. Gather 2023 historical data
2. Train retrospective model
3. Calculate accuracy metrics

### Day 3: League Integration
1. Connect to Sleeper API
2. Pull trade data
3. Identify sharp managers
4. Compare to model recommendations

### Day 4: Feature Enhancement
1. Add all new features
2. Retrain model
3. Compare performance

### Day 5: Final Validation
1. Run full backtest with enhanced model
2. Generate confidence intervals
3. Document findings

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Historical KTC data unavailable | Use Wayback Machine, interpolate from rankings |
| Sleeper API rate limits | Implement caching, respect rate limits |
| Overfitting to historical data | Use walk-forward validation |
| Small sample size | Bootstrap confidence intervals |

---

## Success Criteria

The validation is successful if:

1. **Backtesting**: >60% directional accuracy on value changes
2. **Sharp Manager Alignment**: >55% agreement with winning managers
3. **Feature Enhancement**: R² improvement of >10% on held-out data
4. **Combined Model**: Generates actionable buy/sell signals with >65% accuracy

---

## File Structure

```
ktcvaluehog/
├── src/
│   ├── validation/
│   │   ├── backtester.py       # Historical backtesting
│   │   ├── sleeper_client.py   # Sleeper API integration
│   │   └── metrics.py          # Validation metrics
│   ├── features/
│   │   ├── epa_features.py     # EPA calculations
│   │   ├── opportunity.py      # Snap/target share
│   │   └── advanced_stats.py   # NextGen integration
│   └── models/
│       └── trajectory_model.py # Value change predictor
├── data/
│   ├── historical/             # Cached historical data
│   ├── sleeper/                # League transaction data
│   └── validation/             # Backtest results
└── docs/
    └── VALIDATION_PLAN.md      # This document
```
