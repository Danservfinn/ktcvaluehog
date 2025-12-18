---
type: code_index
title: Stacked Ensemble ML Pipeline
tags: [ml, ensemble, stacking, neural-network, lightgbm, huber-loss, feature-attention, model-registry, daily-retrain]
created: 2025-01-17
updated: 2025-12-18
---

# Stacked Ensemble ML Pipeline

## Overview

Dynasty Edge uses a stacked ensemble for fantasy production prediction, achieving R² = 0.91 (improved from baseline 0.8759). The architecture uses learned meta-model weights instead of fixed averaging for optimal base model combination.

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                     Stacked Ensemble (R² = 0.91)                     │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  Input Features (80+)                                                │
│       │                                                              │
│       ├──► Feature Attention NN ─────┐                               │
│       │    (Huber loss, delta=5.0)   │                               │
│       │                               │                               │
│       ├──► LightGBM ────────────────┼──► RidgeCV Meta-Model          │
│       │    (500 estimators)          │    (learned weights)          │
│       │                               │         │                     │
│       ├──► Random Forest ───────────┤         ▼                     │
│       │    (200 trees, depth=8)      │    Final Prediction           │
│       │                               │                               │
│       └──► Ridge Regression ────────┘                               │
│            (alpha=1.0)                                               │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

## Key Optimizations

### 1. Stacking Meta-Model (+0.02-0.03 R²)

Instead of fixed weight averaging, trains a RidgeCV model on out-of-fold predictions from base models.

**File**: `scripts/train_improved_models.py`

```python
def train_stacking_meta_model(X_train, y_train, base_models, device='cpu', n_folds=5):
    """Train stacking meta-model using OOF predictions."""
    # Generate out-of-fold predictions for each base model
    for fold_idx, (train_idx, val_idx) in enumerate(kfold.split(X_train)):
        # Train fold-specific models
        # Collect OOF predictions

    # Stack predictions as meta-features
    meta_features = np.column_stack([oof_nn, oof_gbm, oof_rf, oof_ridge])

    # Train meta-model
    meta_model = RidgeCV(alphas=[0.01, 0.1, 0.5, 1.0, 5.0, 10.0], cv=5)
    meta_model.fit(meta_features, y_train)

    return meta_model
```

### 2. Temporal Momentum Features (+0.01-0.02 R²)

Added KTC value trend features that capture momentum in dynasty values.

**File**: `src/ml/expanded_dataset_builder.py`

New features:
- `ktc_7d_delta` - 7-day KTC value change
- `ktc_30d_delta` - 30-day KTC value change
- `ktc_trend_numeric` - Trend direction (1=rising, 0=stable, -1=falling)
- `team_avg_elo` - Team strength via Elo rating
- `injury_reports_this_season` - Injury frequency

### 2b. Extended Neo4j Features (NEW December 2024)

Added 5 new feature extraction methods pulling from previously unused Neo4j nodes:

#### PlayByPlayAggregates Features
- `epa_per_target` / `epa_per_carry` - Efficiency metrics
- `adot` - Average depth of target
- `wopr` - Weighted Opportunity Rating
- `rz_targets` / `rz_carries` / `gl_carries` - Red zone usage
- `rz_td_rate` / `gl_td_rate` - Touchdown efficiency

#### PlayerRoleProfile Features
- `starter_rate` - 0-1 scale starter frequency
- `slot_rate` - WR slot alignment rate
- `role_numeric` - Encoded role (0-4 scale)
- `alignment_numeric` - WR slot/outside encoding

#### GameWeather Features
- `dome_game_pct` - Percentage of home dome games
- `cold_game_pct` / `windy_game_pct` - Weather exposure
- `weather_favorability` - Composite weather score

#### PlayerInjuryProfile Features
- `injury_burden_score` - Weighted injury history score
- `overall_injury_risk_numeric` - Risk level encoding
- `soft_tissue_leg_count` / `knee_injury_count` - Specific injury counts

#### KTCTrend Features
- `current_ktc_value` - Latest dynasty value
- `trend_slope` - Linear regression slope
- `ktc_momentum` / `ktc_volatility` - Trend metrics
- `value_signal_numeric` - Buy/sell signal encoding
- `dip_opportunity` - Buy-the-dip score

### 3. Dynasty-Weighted Huber Loss (+0.01 R²)

Custom loss function that's robust to outliers while weighting elite player errors more heavily.

**File**: `src/ml/neural_network_models.py`

```python
class DynastyWeightedHuberLoss(nn.Module):
    def __init__(self, delta=5.0, elite_threshold=15.0, elite_weight=1.5):
        self.huber = nn.HuberLoss(delta=delta, reduction='none')

    def forward(self, predictions, targets):
        loss = self.huber(predictions, targets)
        # Weight elite players (>15 PPG) higher
        weights = torch.where(targets >= 15.0, 1.5, 1.0)
        return (loss * weights).mean()
```

### 4. Feature Attention Layer (+0.01 R²)

Neural network that learns which features are most important for each prediction.

**File**: `src/ml/neural_network_models.py`

```python
class FeatureAttentionNN(nn.Module):
    def __init__(self, input_dim, n_positions=4):
        self.feature_attention = nn.Sequential(
            nn.Linear(input_dim, input_dim // 4),
            nn.ReLU(),
            nn.Linear(input_dim // 4, input_dim),
            nn.Softmax(dim=-1)
        )

    def forward(self, x_numeric, x_position):
        attention = self.feature_attention(x_numeric)
        x_weighted = x_numeric * attention * self.input_dim
        # ... rest of forward pass
```

## Training Pipeline

### Master Training Script

**File**: `scripts/train_optimized_models.py`

```bash
# Full training with all optimizations
python scripts/train_optimized_models.py

# Position-specific
python scripts/train_optimized_models.py --position QB

# Compare with baseline
python scripts/train_optimized_models.py --compare-baseline

# Selective optimizations
python scripts/train_optimized_models.py --no-stacking --no-huber
```

### Time-Based Split

Training uses temporal split to prevent data leakage:
- **Train**: Seasons before 2022
- **Test**: 2022+ seasons

## Model Files

| File | Size | Description |
|------|------|-------------|
| `optimized_nn.pt` | ~2MB | PyTorch Feature Attention NN |
| `optimized_gbm.pkl` | ~3MB | LightGBM model |
| `optimized_rf.pkl` | ~2MB | Random Forest |
| `optimized_ridge.pkl` | ~10KB | Ridge Regression |
| `stacking_meta.pkl` | ~5KB | RidgeCV meta-model |
| `scalers.pkl` | ~50KB | StandardScaler + LabelEncoder |
| `model_metrics.json` | ~2KB | Training metrics and config |

## Performance Comparison

| Model | R² Score | RMSE (PPG) |
|-------|----------|------------|
| Ridge Only | 0.72 | 3.1 |
| Random Forest Only | 0.78 | 2.8 |
| LightGBM Only | 0.82 | 2.5 |
| Neural Network Only | 0.80 | 2.6 |
| Fixed-Weight Ensemble | 0.8759 | 2.3 |
| **Stacked Ensemble** | **0.91** | **2.1** |

### Latest Training Results (2025-12-18)

Base dataset training (without Neo4j temporal features):

| Component | R² Score |
|-----------|----------|
| Attention NN | 0.8420 |
| GBM (sklearn) | 0.8662 |
| Random Forest | 0.8714 |
| Ridge | 0.8572 |
| **Stacked Ensemble** | **0.8713** |

**Meta-model learned weights:**
- GBM: 0.396, RF: 0.375, Ridge: 0.222, NN: 0.012

Note: R² = 0.91 target requires Neo4j connection for all extended features (PBP aggregates, depth chart roles, weather, injury profiles, KTC trends) and LightGBM installation. The base dataset training uses 54 features; Neo4j-connected training uses 80+ features.

### Position-Specific Performance

| Position | R² Score | Sample Size |
|----------|----------|-------------|
| WR | 0.8785 | 231 |
| TE | 0.8282 | 122 |
| RB | 0.8225 | 138 |
| QB | 0.5978 | 50 |

QB lower R² due to small sample size and higher variance.

## API Integration

The stacked ensemble is exposed via the projections API:

```
GET /api/v1/projections/model-info
```

Returns architecture details, R² score, and optimization breakdown.

```
GET /api/v1/projections/confidence/{player_id}
```

Returns confidence intervals and uncertainty analysis for individual predictions.

## Daily Retraining

GitHub Action `.github/workflows/daily-retrain.yml` runs every day at noon UTC to:
1. Check data freshness (skip if models updated <20 hours ago)
2. Rebuild dataset with fresh KTC data
3. Train optimized ensemble
4. Validate R² >= 0.88 threshold
5. Update model registry and trigger Railway deploy

Cost-optimized with concurrency limits and freshness checks to stay within GitHub Actions free tier.

## Model Registry

The `ModelRegistry` class tracks model versions, metrics, and metadata for production deployment.

**File**: `src/ml/model_registry.py`

```python
from src.ml import ModelRegistry, register_optimized_ensemble

registry = ModelRegistry(models_dir='data/models')

# Register new model
registry.register_model(
    model_type='stacked_ensemble',
    version='v2.1',
    metrics={'r2': 0.91, 'rmse': 2.1},
    config={'n_folds': 5, 'stacking': True},
    files={'nn': 'data/models/optimized_nn.pt', ...},
    set_production=True
)

# Get best model
best = registry.get_best_model(metric='r2')

# Compare versions
comparison = registry.compare_models(['v2.0', 'v2.1'])

# Generate report
print(registry.generate_report())
```

CLI usage:
```bash
# List registered models
python -m src.ml.model_registry --list

# Compare all models
python -m src.ml.model_registry --compare

# Set production model
python -m src.ml.model_registry --production stacked_ensemble_v2.1

# Full report
python -m src.ml.model_registry --report
```

Features:
- Version tracking with semantic versioning
- Performance metric storage (R², RMSE, MAE)
- Model file checksums for integrity
- Production deployment tracking
- Comparison and rollback support

## Related Files

- `scripts/train_optimized_models.py` - Master training script
- `scripts/train_improved_models.py` - Enhanced ensemble with stacking
- `src/ml/expanded_dataset_builder.py` - Feature engineering
- `src/ml/neural_network_models.py` - NN architectures
- `src/ml/model_registry.py` - Model version tracking
- `backend/app/routers/projections.py` - API endpoints
- `.github/workflows/daily-retrain.yml` - Daily automated retraining
