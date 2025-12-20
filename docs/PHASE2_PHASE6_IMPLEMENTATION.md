# Phase 2 & 6 Implementation - R² Improvement Plan

**Date:** 2024-12-19
**Baseline R²:** 0.80 (RMSE: 2.47 PPG)
**Target R²:** 0.84+ (Expected gain: +0.04-0.10)

## Overview

This document describes the implementation of Phase 2 (Feature Engineering) and Phase 6 (Neural Network Improvements) from the R² Improvement Plan. These enhancements build upon the existing stacked ensemble model to improve predictive accuracy.

## Phase 2: Feature Engineering from Existing Data

Phase 2 adds advanced feature engineering using data already in Neo4j, without requiring new external data sources. Expected R² gain: **+0.03-0.05**.

### 2.0: Dual-Threat QB Indicators

**Location:** `src/ml/expanded_dataset_builder.py::engineer_features()`

**Features Added:**
- `dual_threat_indicator`: Rushing yards as % of total yards (passing + rushing)
- `rushing_share_of_tds`: Rushing TDs as % of total TDs
- `int_rate`: Interception rate per ~10 pass attempts

**Impact:**
- Captures QB rushing contribution (Jalen Hurts, Lamar Jackson, Josh Allen)
- Differentiates dual-threat vs pocket passers
- Expected R² gain: +0.01-0.02

**Example:**
```python
# Lamar Jackson (2023): 3,678 pass yds, 821 rush yds
dual_threat_indicator = 821 / (3678 + 821) = 0.182  # 18.2% rushing

# Tom Brady (2020): 4,633 pass yds, 6 rush yds
dual_threat_indicator = 6 / (4633 + 6) = 0.0013  # 0.13% rushing
```

### 2.1: Defense/Schedule Strength Features

**Location:** `src/ml/expanded_dataset_builder.py::add_schedule_strength_features()`

**Features Added:**
- `avg_opponent_elo`: Average opponent Elo rating from Game nodes
- `favorable_matchup_pct`: % of games vs defenses with Elo < 1500
- `tough_matchup_pct`: % of games vs defenses with Elo > 1550
- `schedule_strength_score`: Normalized score (-5 to +5 range)

**Impact:**
- Accounts for strength of schedule
- Players facing weak defenses should perform better
- Expected R² gain: +0.01-0.02

**Implementation:**
```python
# Query Game nodes for team's schedule
# For each player-team-season, calculate:
avg_elo = mean(opponent_elo for all games)
favorable_pct = count(opponent_elo < 1500) / total_games
tough_pct = count(opponent_elo > 1550) / total_games
```

### 2.2: QB Stability Features (Leakage-Safe)

**Location:** `src/ml/expanded_dataset_builder.py::add_qb_stability_features()`

**Features Added (Non-QBs only):**
- `qb_stable`: Boolean indicator if starting QB remained same year-over-year
- `qb_quality_delta`: Change in QB's PPG performance (season-1 vs season-2)

**Impact:**
- WR/RB/TE performance highly dependent on QB stability
- QB change = new chemistry, different offense
- Expected R² gain: +0.01-0.02

**Leakage Prevention:**
- Only uses PRIOR season data (knowable at prediction time)
- Compares season-1 vs season-2 QB for current season prediction
- Does not use "next season" QB information

**Example:**
```python
# Davante Adams (2022 -> 2023)
# GB: Aaron Rodgers (2022)
# LV: Derek Carr (2023)
qb_stable = 0  # QB changed
qb_quality_delta = Carr_PPG - Rodgers_PPG  # Quality change
```

### 2.3: Competition Metrics

**Location:** `src/ml/expanded_dataset_builder.py::add_competition_features()`

**Features Added:**

**For RBs:**
- `rb_committee_score`: Herfindahl index of carry distribution (0-100)
  - Higher score = more committee backfield
  - Lower score = bellcow back

**For WRs:**
- `wr_target_concentration`: Herfindahl index of target distribution
  - Higher = targets concentrated among fewer WRs
  - Lower = targets spread evenly
- `alpha_wr_indicator`: Is player the WR1 on the team? (0 or 1)

**Impact:**
- RBs in committees score lower than bellcows
- Alpha WRs outperform WR2/WR3
- Expected R² gain: +0.01-0.02

**Herfindahl Index:**
```python
# For RB committee score:
shares = [rb.carries / total_carries for rb in team_rbs]
herfindahl = sum(share^2 for share in shares)
committee_score = (1 - herfindahl) * 100

# Example:
# Bellcow: [0.80, 0.15, 0.05] -> H=0.665 -> committee=33.5
# Committee: [0.40, 0.35, 0.25] -> H=0.385 -> committee=61.5
```

### Pipeline Integration

All Phase 2 methods are integrated into `build_expanded_dataset()` pipeline:

```python
# Step 17: Phase 2.1 - Add schedule strength features
df = self.add_schedule_strength_features(df)

# Step 18: Phase 2.2 - Add QB stability features
df = self.add_qb_stability_features(df)

# Step 19: Phase 2.3 - Add competition features
df = self.add_competition_features(df)

# Step 23: Engineer features (includes Phase 2.0)
df = self.engineer_features(df)
```

## Phase 6: Neural Network Improvements

Phase 6 implements advanced neural network architectures to capture complex non-linear patterns. Expected R² gain: **+0.04-0.07**.

### 6.1: Multi-Head Feature Attention NN

**Location:** `src/ml/neural_network_models.py::MultiHeadFeatureAttentionNN`

**Architecture:**
```
Input (100 features)
├─> Attention Head 1 -> Weighted Features
├─> Attention Head 2 -> Weighted Features
├─> Attention Head 3 -> Weighted Features
└─> Attention Head 4 -> Weighted Features
     ↓
Head Combiner (400 -> 256)
     ↓
Position Embedding (16) -> Projection (256)
     ↓ (Residual Connection)
Backbone (256 -> 128 -> 64)
     ↓
Output (1)
```

**Key Features:**
- 4 attention heads learn different feature importance patterns
- Each head applies softmax attention to input features
- Heads are concatenated and combined via learned projection
- Position embedding added via residual connection
- Expected R² gain: +0.01-0.02

**Parameters:** ~244K (vs 128K for single-head FeatureAttentionNN)

**Usage:**
```python
from src.ml.neural_network_models import NeuralNetworkTrainer

trainer = NeuralNetworkTrainer(
    model_type='multihead_attention',
    n_heads=4,
    hidden_dims=[256, 128, 64]
)
trainer.fit(df)
```

### 6.2: Position-Specific Output Heads NN

**Location:** `src/ml/neural_network_models.py::PositionAwareNN`

**Architecture:**
```
Input + Position Embedding
     ↓
Shared Backbone (256 -> 128)
     ↓
     ├─> QB Head (128 -> 64 -> 32 -> 1)
     ├─> RB Head (128 -> 64 -> 32 -> 1)
     ├─> WR Head (128 -> 64 -> 32 -> 1)
     └─> TE Head (128 -> 64 -> 32 -> 1)
```

**Key Features:**
- Shared backbone learns common patterns across all positions
- Position-specific heads capture unique dynamics:
  - QB: Passing efficiency, rushing contribution
  - RB: Workload, committee effects
  - WR: Target share, QB stability
  - TE: Target competition, red zone usage
- Router selects appropriate head based on player position
- Expected R² gain: +0.02-0.03 (highest expected gain)

**Parameters:** ~105K (efficient architecture)

**Rationale:**
Different positions have fundamentally different predictive patterns:
- RB aging curve peaks at 25, cliff at 28
- WR aging curve peaks at 27, cliff at 31
- QB aging curve peaks at 30, cliff at 38
- Feature importance varies (e.g., targets matter for WR/TE, not QB/RB)

**Usage:**
```python
trainer = NeuralNetworkTrainer(
    model_type='position_aware',
    backbone_dims=[256, 128],
    head_hidden_dim=64
)
trainer.fit(df)
```

### 6.3: Career Trajectory LSTM (Experimental)

**Location:** `src/ml/neural_network_models.py::CareerTrajectoryLSTM`

**Architecture:**
```
Career Sequence (5 seasons x 100 features)
     ↓
3-Layer Bidirectional LSTM (hidden=128)
     ↓
Temporal Attention (optional)
  - Learns which past seasons matter most
  - Weighted sum of LSTM outputs
     ↓
Position Embedding
     ↓
Dense Layers (256 -> 128 -> 64 -> 1)
```

**Key Features:**
- Processes up to 5 previous seasons as a sequence
- Bidirectional LSTM captures career trajectory patterns
- Optional temporal attention weighs recent vs distant seasons
- Learns career arc patterns (breakout, decline, consistency)
- Expected R² gain: +0.01-0.02

**Parameters:** ~1.09M (largest model, use for large datasets)

**Use Cases:**
- Identifying breakout candidates (consistent upward trajectory)
- Predicting decline (downward trend + age)
- Career consistency patterns

**Usage:**
```python
trainer = NeuralNetworkTrainer(
    model_type='career_trajectory',
    hidden_dim=128,
    n_layers=3,
    use_attention=True
)
trainer.fit(df)  # Requires player_id and season columns
```

### Model Comparison

| Model | Parameters | Expected R² Gain | Best For |
|-------|------------|------------------|----------|
| FeatureAttentionNN (Baseline) | 128K | 0.80 baseline | General purpose |
| MultiHeadFeatureAttentionNN | 244K | +0.01-0.02 | Feature interpretability |
| PositionAwareNN | 105K | +0.02-0.03 | Position-specific patterns |
| CareerTrajectoryLSTM | 1.09M | +0.01-0.02 | Career arc modeling |

## Testing & Validation

All implementations have been verified with comprehensive tests:

```bash
python scripts/test_phase2_phase6_implementations.py
```

**Test Results:**
- ✓ All Phase 2 methods integrate into pipeline
- ✓ All Phase 6 architectures instantiate correctly
- ✓ Forward passes produce valid outputs
- ✓ Position routing works for PositionAwareNN
- ✓ Attention mechanisms store interpretable weights

## Training New Models

### Step 1: Rebuild Dataset

```bash
# Connect to Railway Neo4j (includes Phase 2 features)
export NEO4J_URI="bolt://sparkling-commitment-production.up.railway.app:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="dynastyedge2025"

# Build expanded dataset with Phase 2 features
python -m src.ml.expanded_dataset_builder

# Output: data/ml_training/expanded_season_projection.parquet
```

Expected new features:
- 3 dual-threat QB indicators
- 4 schedule strength features
- 2 QB stability features
- 3 competition metrics
- **Total: ~180 features** (up from 168)

### Step 2: Train Individual Models

```bash
# Train Multi-Head Attention model
python -c "
from src.ml.neural_network_models import NeuralNetworkTrainer
import pandas as pd

df = pd.read_parquet('data/ml_training/expanded_season_projection.parquet')
trainer = NeuralNetworkTrainer(model_type='multihead_attention')
trainer.fit(df, epochs=100)
trainer.save('data/models/multihead_attention.pt')
"

# Train Position-Aware model
python -c "
from src.ml.neural_network_models import NeuralNetworkTrainer
import pandas as pd

df = pd.read_parquet('data/ml_training/expanded_season_projection.parquet')
trainer = NeuralNetworkTrainer(model_type='position_aware')
trainer.fit(df, epochs=100)
trainer.save('data/models/position_aware.pt')
"
```

### Step 3: Integrate with Ensemble

Update `scripts/train_optimized_models.py` to include new models in stacking ensemble:

```python
# Add to component models
multihead_nn = train_multihead_attention(X_train, y_train)
position_nn = train_position_aware(X_train, y_train)

# Update stacking ensemble
stacking_meta = RidgeCV(alphas=[0.1, 1.0, 10.0], cv=5)
stacking_ensemble = StackingRegressor(
    estimators=[
        ('nn', nn_model),
        ('multihead_nn', multihead_nn),
        ('position_nn', position_nn),
        ('gbm', gbm_model),
        ('rf', rf_model),
        ('ridge', ridge_model)
    ],
    final_estimator=stacking_meta,
    cv=5
)
```

## Expected Performance

### Feature Impact (Phase 2)

| Feature Set | Expected R² Gain | Confidence |
|-------------|------------------|------------|
| Dual-Threat QB | +0.01-0.02 | High (for QB position) |
| Schedule Strength | +0.01-0.02 | Medium (noisy data) |
| QB Stability | +0.01-0.02 | High (for WR/TE/RB) |
| Competition Metrics | +0.01-0.02 | High (for RB/WR) |
| **Total Phase 2** | **+0.03-0.05** | **Medium-High** |

### Model Impact (Phase 6)

| Model | Expected R² Gain | Confidence |
|-------|------------------|------------|
| Multi-Head Attention | +0.01-0.02 | Medium |
| Position-Aware | +0.02-0.03 | High |
| Career Trajectory | +0.01-0.02 | Medium (requires sequences) |
| **Total Phase 6** | **+0.04-0.07** | **Medium-High** |

### Combined Impact

**Conservative Estimate:** +0.05 R² (0.80 -> 0.85)
**Optimistic Estimate:** +0.10 R² (0.80 -> 0.90)
**Expected Result:** +0.07 R² (0.80 -> 0.87)

## Position-Specific Improvements

Current baseline (R² by position):
- QB: 0.59
- RB: 0.78
- WR: 0.77
- TE: 0.72

Expected improvements:

| Position | Current R² | Target R² | Key Improvements |
|----------|-----------|-----------|------------------|
| QB | 0.59 | 0.65-0.70 | Dual-threat indicators, position-aware head |
| RB | 0.78 | 0.82-0.85 | Committee score, position-aware head |
| WR | 0.77 | 0.82-0.85 | QB stability, alpha WR indicator, position-aware head |
| TE | 0.72 | 0.77-0.80 | QB stability, competition metrics, position-aware head |

## Monitoring & Evaluation

### Metrics to Track

1. **Overall Performance:**
   - R² score (target: 0.85+)
   - RMSE (target: <2.3 PPG)
   - MAE (target: <1.8 PPG)

2. **Position-Specific:**
   - QB R² (target: 0.65+)
   - RB R² (target: 0.82+)
   - WR R² (target: 0.82+)
   - TE R² (target: 0.77+)

3. **Feature Importance:**
   - Top 10 features from Multi-Head Attention
   - Position-specific feature importance
   - Competition metric impact (RB committee, alpha WR)

4. **Model Comparison:**
   - Component model R² scores
   - Ensemble stacking weights
   - Position-aware head performance by position

### Validation Strategy

1. **Temporal Split:** Train on 1999-2022, test on 2023
2. **Cross-Validation:** 5-fold CV for hyperparameter tuning
3. **Position Stratification:** Ensure all positions represented in folds
4. **Holdout Set:** Reserve 2024 data for final validation

## Troubleshooting

### Phase 2 Issues

**Issue:** No schedule strength data found
**Cause:** Game nodes missing Elo ratings
**Fix:** Run `scripts/ingest_betting_data.py` to populate Elo

**Issue:** QB stability features all NaN
**Cause:** Missing historical QB data
**Fix:** Ensure HistoricalSeasonStats has QB data for all seasons

**Issue:** Competition features sparse
**Cause:** Team-season combinations missing
**Fix:** Expected - only RBs have committee score, only WRs have target concentration

### Phase 6 Issues

**Issue:** CUDA out of memory
**Cause:** Large model (Career Trajectory LSTM)
**Fix:** Reduce batch size or use smaller hidden_dim

**Issue:** Position-Aware NN slow training
**Cause:** Per-sample routing logic
**Fix:** Expected - trade-off for position-specific modeling

**Issue:** Multi-Head Attention overfitting
**Cause:** Too many parameters
**Fix:** Increase dropout (0.15 -> 0.25), reduce n_heads (4 -> 2)

## References

- R² Improvement Plan: `/Users/kurultai/ktcvaluehog/docs/R2_IMPROVEMENT_PLAN.md`
- Expanded Dataset Builder: `/Users/kurultai/ktcvaluehog/src/ml/expanded_dataset_builder.py`
- Neural Network Models: `/Users/kurultai/ktcvaluehog/src/ml/neural_network_models.py`
- Test Script: `/Users/kurultai/ktcvaluehog/scripts/test_phase2_phase6_implementations.py`

## Changelog

**2024-12-19:**
- Implemented Phase 2.0: Dual-Threat QB Indicators
- Implemented Phase 2.1: Schedule Strength Features
- Implemented Phase 2.2: QB Stability Features (leakage-safe)
- Implemented Phase 2.3: Competition Metrics
- Implemented Phase 6.1: Multi-Head Feature Attention NN
- Implemented Phase 6.2: Position-Specific Output Heads NN
- Implemented Phase 6.3: Career Trajectory LSTM
- All methods integrated into pipeline
- Comprehensive test suite passing
- Documentation complete
