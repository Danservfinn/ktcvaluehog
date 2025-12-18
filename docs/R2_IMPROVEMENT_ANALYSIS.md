# R² Improvement Analysis: From 0.80 to 0.90+

## Current State (December 2025)

### Performance Metrics
| Metric | Value |
|--------|-------|
| Ensemble R² | 0.801 |
| RMSE | 2.47 PPG |
| MAE | 1.92 PPG |
| Training Samples | 9,414 |
| Test Samples | 1,182 (2023) |
| Features | 168 |

### Component Model Performance
| Model | R² | Notes |
|-------|-----|-------|
| LightGBM | 0.803 | Best component |
| Random Forest | 0.765 | |
| Ridge | 0.707 | |
| Neural Network | 0.695 | **Underperforming** |
| Stacked Ensemble | 0.801 | Barely improves on GBM |

### Position-Specific R²
| Position | R² | Issue |
|----------|-----|-------|
| QB | 0.59 | **Very low** - hardest to predict |
| RB | 0.78 | Good |
| WR | 0.77 | Good |
| TE | 0.72 | Decent |

### Key Observations
1. **GBM ≈ Ensemble**: Stacking barely helps → base models highly correlated
2. **QB problem**: 0.59 R² is unacceptable, needs position-specific approach
3. **NN underperforming**: 0.695 vs 0.803 for GBM - architecture or data issue
4. **ID matching gap**: Only 379/1883 players matched to Neo4j (20%)

---

## Improvement Strategies

### 1. MORE DATA (Highest Impact)

#### A. Weekly-Level Predictions ⭐⭐⭐ HIGH PRIORITY
```
Current: Season → Season (10K samples)
Proposed: Week → Week (170K+ samples)
```
- **Data**: HistoricalWeeklyStats has 143,593 records
- **Benefit**: 17x more training samples per player-season
- **Features needed**: Matchup data, snap counts, weather
- **Challenges**: Higher variance, need matchup features
- **Expected R² gain**: +0.05-0.10

#### B. College Data (for rookies)
- **Source**: CFBD API (free)
- **Features**:
  - College PPG, yards
  - Conference strength
  - Breakout age
  - Combine-adjusted athletic scores
- **Benefit**: Better rookie projections (currently ~60% of production variance unexplained)
- **Implementation**: Already planned as `CollegeProfile` node
- **Expected R² gain**: +0.02-0.03 (primarily for young players)

#### C. Contract/Salary Data
- **Source**: Spotrac, OverTheCap (scraping required)
- **Features**:
  - Guaranteed money remaining
  - Contract year flag
  - Cap hit percentage
  - Years remaining
- **Hypothesis**: Contract year players have different motivation
- **Expected R² gain**: +0.01-0.02

#### D. Strength of Schedule
- **Source**: Derive from team Elo/rankings
- **Features**:
  - SoS faced (past season)
  - SoS upcoming (next season)
  - Avg defense rank faced
  - Variance in opponent quality
- **Expected R² gain**: +0.01-0.02

#### E. Teammate Effects (Graph Features) ⭐⭐ MEDIUM PRIORITY
- **Source**: Neo4j relationships
- **Features**:
  - QB quality score (for WR/RB/TE)
  - Target competition (other WRs on team)
  - RB committee score
  - OL quality rating
- **Benefit**: Team context is currently underutilized
- **Expected R² gain**: +0.02-0.03

---

### 2. FEATURE ENGINEERING

#### A. Graph-Based Features (Leverage Neo4j)
```cypher
// PageRank within team offense
CALL gds.pageRank.stream('team-offense-graph')
YIELD nodeId, score

// Similarity to successful players
MATCH (p1:Player), (p2:Player)
WHERE p2.career_ppg > 15
RETURN gds.alpha.similarity.cosine(p1.features, p2.features)
```
- Centrality scores
- Career trajectory similarity
- Team composition metrics
- **Expected R² gain**: +0.02-0.03

#### B. Rolling Windows
- **Current**: Some YoY features
- **Proposed**:
  - 3-game rolling PPG
  - 5-game rolling targets
  - Half-season splits (current vs previous)
  - Momentum indicators
- **Expected R² gain**: +0.01-0.02

#### C. Matchup-Adjusted Stats ⭐⭐ MEDIUM PRIORITY
```python
# Normalize by opponent quality
adj_ppg = raw_ppg * (league_avg_def / opponent_def_rating)
adj_targets = raw_targets * (32 / opponent_pass_def_rank)
```
- **Expected R² gain**: +0.02-0.03

#### D. Age Curve Residuals
```python
# Fit position-specific curve
expected_ppg = age_curve(position, age)
age_residual = actual_ppg - expected_ppg  # "Over/underperforming age"
```
- Better than raw age
- Captures trajectory direction
- **Expected R² gain**: +0.01

#### E. Career Trajectory Features
- Breakout season detector
- Peak detection (has player peaked?)
- Improvement/decline rate
- Years since peak
- **Expected R² gain**: +0.01-0.02

#### F. Clustering-Based Features
```python
# Cluster by usage profile
from sklearn.cluster import KMeans
clusters = KMeans(n_clusters=5).fit(usage_features)
player_archetype = clusters.predict(player_features)
# Archetypes: slot WR, deep threat, possession, gadget, etc.
```
- **Expected R² gain**: +0.01

---

### 3. MODEL ARCHITECTURE

#### A. Position-Specific Models ⭐⭐⭐ HIGH PRIORITY
```python
# Current
model.fit(all_positions)  # Single model

# Proposed
qb_model.fit(qb_data)  # QB-specific features matter
rb_model.fit(rb_data)  # Carries, snap% more important
wr_model.fit(wr_data)  # Targets, routes run
te_model.fit(te_data)  # Blocking%, inline vs slot
```
- **Benefit**: Feature importance differs by position
- **Challenge**: Smaller sample sizes
- **Solution**: Transfer learning from all-position model
- **Expected R² gain**: +0.03-0.05 (especially QB)

#### B. XGBoost/CatBoost Comparison
- LightGBM is good but worth comparing
- CatBoost handles categoricals natively
- XGBoost may be more robust
- Quick experiment, low effort
- **Expected R² gain**: +0.00-0.02

#### C. Neural Network Improvements ⭐⭐ MEDIUM PRIORITY
```python
# Current: Simple FFN
# Issues: R² = 0.695, well below GBM

# Proposed improvements:
# 1. Deeper network with residual connections
# 2. Better regularization (dropout, weight decay)
# 3. Batch normalization
# 4. Learning rate scheduling with warmup
# 5. Focal loss for hard examples
```
- NN should be competitive with GBM
- Current underperformance suggests architecture issue
- **Expected R² gain**: +0.05-0.08 for NN component

#### D. Multi-Task Learning
```python
# Predict multiple targets simultaneously
targets = ['next_ppg_ppr', 'next_games_played', 'next_total_points']
model = MultiTaskNet(shared_layers, task_heads)
```
- Games played prediction captures injury risk
- Shared representations improve generalization
- **Expected R² gain**: +0.01-0.02

#### E. Quantile Regression
```python
# Instead of E[y|x], predict quantiles
model.fit(X, y, quantiles=[0.1, 0.5, 0.9])
floor = model.predict(X, quantile=0.1)
ceiling = model.predict(X, quantile=0.9)
```
- Better uncertainty quantification
- Floor/ceiling directly from model
- **Expected R² gain**: Neutral (different objective)

---

### 4. TARGET VARIABLE IMPROVEMENTS

#### A. Log-Transform ⭐⭐⭐ HIGH PRIORITY
```python
# Current
y = df['next_ppg_ppr']

# Proposed
y = np.log1p(df['next_ppg_ppr'])
# Or Box-Cox transform
```
- PPG is right-skewed (many low, few high)
- Log stabilizes variance
- Helps with elite player predictions
- **Expected R² gain**: +0.01-0.02

#### B. Rank-Based Target
```python
# Predict positional rank instead of raw PPG
y = df.groupby(['season', 'position'])['ppg'].rank(ascending=False)
```
- More stable across eras
- Then convert rank back to expected PPG
- **Expected R² gain**: +0.01-0.02

#### C. Relative Performance
```python
# Predict relative to position average
position_avg = df.groupby(['season', 'position'])['ppg'].mean()
y = df['ppg'] - position_avg  # PPG above/below average
```
- Removes era effects
- More consistent across time
- **Expected R² gain**: +0.01

---

### 5. TRAINING STRATEGY

#### A. Era-Stratified CV
```python
# Current: Simple time split
# Proposed: Stratified by era
from sklearn.model_selection import GroupKFold
eras = (df['season'] - 1999) // 5  # 5-year eras
cv = GroupKFold(n_splits=5).split(X, y, groups=eras)
```
- Each fold sees multiple eras
- Better generalization estimate
- **Expected R² gain**: Better evaluation, not prediction

#### B. Feature Selection ⭐⭐ MEDIUM PRIORITY
```python
# 168 features may include noise
from sklearn.feature_selection import RFECV
selector = RFECV(estimator, cv=5, scoring='r2')
selector.fit(X, y)
# Keep top 50-80 features
```
- Reduce overfitting
- Faster training
- **Expected R² gain**: +0.01-0.02

#### C. Ensemble Diversity
```python
# Current ensemble: NN + GBM + RF + Ridge
# All tree/linear based - similar errors

# Add diverse models:
models = [
    KNeighborsRegressor(n_neighbors=20),
    GaussianProcessRegressor(kernel=RBF()),
    SVR(kernel='rbf'),
    # Plus existing models
]
```
- Diversity improves ensemble
- **Expected R² gain**: +0.01-0.02

#### D. Progressive Training
```python
# Start with recent data
model.fit(recent_data)  # 2016+, high coverage
# Fine-tune with older data
model.fit(all_data, weights=time_decay)
```
- Learn recent patterns first
- Then generalize to older eras
- **Expected R² gain**: +0.01

---

### 6. DATA QUALITY

#### A. Better ID Mapping ⭐⭐⭐ HIGH PRIORITY
```
Current: 379/1883 players matched (20%)
Target: 800+ players matched (40%+)
```
- Missing 80% of predictions
- Need fuzzy name matching
- Cross-reference multiple ID systems
- **Expected impact**: 2x prediction coverage

#### B. Handle Missing Data Better
```python
# Current
df.fillna(0)

# Proposed
# Option 1: Missing indicator
df['snap_pct_missing'] = df['snap_pct'].isna()
df['snap_pct'].fillna(df['snap_pct'].median())

# Option 2: Multiple imputation
from sklearn.impute import IterativeImputer
imputer = IterativeImputer()
df_imputed = imputer.fit_transform(df)
```
- 0 is informative for some features, not others
- **Expected R² gain**: +0.01

#### C. Outlier Handling
```python
# Identify injury-shortened seasons
outliers = df[df['games'] < 6]

# Options:
# 1. Remove from training
# 2. Down-weight
# 3. Add 'injury_season' flag
# 4. Adjust stats to per-game and keep
```
- **Expected R² gain**: +0.01

---

## Priority Roadmap

### Phase 1: Quick Wins (1-2 days)
| Task | Expected R² Gain | Effort |
|------|-----------------|--------|
| Log-transform target | +0.01-0.02 | Low |
| Position-specific models | +0.03-0.05 | Medium |
| Better ID matching | Coverage 2x | Medium |
| Feature selection (168→50) | +0.01-0.02 | Low |
| XGBoost comparison | +0.00-0.02 | Low |
| **Phase 1 Total** | **+0.05-0.11** | |

### Phase 2: Medium Effort (1 week)
| Task | Expected R² Gain | Effort |
|------|-----------------|--------|
| Improve NN architecture | +0.05-0.08 (component) | Medium |
| Matchup-adjusted features | +0.02-0.03 | Medium |
| Graph-based features | +0.02-0.03 | Medium |
| Rolling window features | +0.01-0.02 | Low |
| **Phase 2 Total** | **+0.05-0.10** | |

### Phase 3: Major Investment (2-4 weeks)
| Task | Expected R² Gain | Effort |
|------|-----------------|--------|
| Weekly prediction model | +0.05-0.10 | High |
| College data integration | +0.02-0.03 | High |
| Multi-task learning | +0.01-0.02 | Medium |
| Quantile regression | Uncertainty | Medium |
| **Phase 3 Total** | **+0.08-0.15** | |

---

## Theoretical R² Ceiling

### Why 0.80 may be near-optimal for season prediction:

1. **Inherent randomness**: Injuries, game scripts, coaching changes
2. **Regression to mean**: Elite seasons often followed by decline
3. **Breakout unpredictability**: Can't perfectly predict breakouts
4. **Sample size**: ~1,200 test samples limits precision

### Realistic targets:
- **0.85**: Achievable with position-specific models + better features
- **0.88**: Possible with weekly data + major feature engineering
- **0.90+**: Would require fundamental approach change (e.g., weekly predictions)

### Position-specific targets:
| Position | Current | Target | Path |
|----------|---------|--------|------|
| QB | 0.59 | 0.75 | Position-specific model, scheme features |
| RB | 0.78 | 0.85 | Workload features, committee detection |
| WR | 0.77 | 0.85 | Target share, route running data |
| TE | 0.72 | 0.80 | Role classification, blocking data |

---

## Recommended Next Steps

### Immediate (This Week)
1. **Train position-specific GBM models** - biggest QB improvement
2. **Log-transform target** - quick, measurable
3. **Fix ID matching** - double prediction coverage
4. **Try XGBoost** - may outperform LightGBM

### Next Sprint
5. **Feature selection** - reduce to top 50-80
6. **Improve NN** - should match GBM performance
7. **Add matchup-adjusted features**
8. **Graph-based teammate effects**

### Future
9. **Weekly prediction model** - 17x data, different approach
10. **College data for rookies**
11. **Contract/salary data**

---

## Appendix: Feature Importance (Current Model)

Top 20 features by importance (LightGBM):
```
1. ppg_ppr                     0.142
2. ppg_ppr_lag1                0.098
3. snap_pct                    0.067
4. targets                     0.054
5. receptions                  0.048
6. age                         0.043
7. years_exp                   0.038
8. ppg_ppr_percentile          0.035
9. receiving_yards             0.032
10. ppg_ppr_zscore             0.029
11. rushing_yards              0.027
12. career_ppg                 0.024
13. ktc_value                  0.022
14. carries                    0.019
15. receiving_tds              0.018
16. games                      0.016
17. rushing_tds                0.015
18. draft_round                0.014
19. yoy_ppg_change             0.013
20. target_share               0.012
```

Note: Many features have low importance - candidates for removal.
