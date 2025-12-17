---
title: ML Valuation Model
link: ml-valuation-model
type: code_index
ontological_relations: []
tags:
- machine-learning
- valuation
- gradient-boosting
created_at: 2025-12-17T16:40:04Z
updated_at: 2025-12-17T16:40:04Z
uuid: b628c986-bc6b-4251-97a0-d4735beef99e
---

# ML Valuation Model

## Overview
Gradient Boosting model trained on 40+ features to predict dynasty player values. Compares predictions to KTC market values to identify buy/sell opportunities.

## Performance
- **R²**: 0.87 (87% of variance explained)
- **Target**: `ktc_value` (Superflex)

## Files
- `src/ml/train.py` - Training pipeline (H2O AutoML or sklearn)
- `src/ml/predict.py` - Inference and edge scoring
- `data/models/` - Saved model artifacts

## Top Feature Importance

| Rank | Feature | Importance |
|------|---------|------------|
| 1 | Contract Guaranteed | 100% |
| 2 | Contract Total | 55% |
| 3 | Total Snaps | 21% |
| 4 | Snap Percentage | 19% |
| 5 | APY Percentile | 16% |
| 6 | ADOT | 15% |
| 7 | Draft Value | 12% |
| 8 | Snap Trend | 9% |

## Feature Categories (40+)

| Category | Examples |
|----------|----------|
| Contract | guaranteed, total, apy_percentile |
| Production | snaps, snap_pct, targets, receptions |
| Athletic | forty, vertical, broad_jump, speed_score |
| Situational | draft_round, draft_pick, years_exp |
| Age | age, years_from_peak, age_bucket |

## Usage

```python
from src.ml.train import DynastyMLTrainer
from src.ml.predict import DynastyPredictor

# Train
trainer = DynastyMLTrainer()
trainer.train(features_df, target='ktc_value')

# Predict
predictor = DynastyPredictor()
predictions = predictor.predict(player_features)
edge_scores = predictor.calculate_edge(predictions, ktc_values)
```

## Training Options

- **Primary**: H2O AutoML (requires `pip install h2o`)
- **Fallback**: scikit-learn GradientBoostingRegressor
