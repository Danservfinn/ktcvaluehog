---
title: KTC Prediction ML Pipeline
link: ktc-prediction-ml-pipeline
type: plans
ontological_relations: []
tags:
- machine-learning
- prediction
- time-series
created_at: 2025-12-17T16:22:54Z
updated_at: 2025-12-17T16:22:54Z
uuid: 0555141d-0481-4fa9-bf52-e1ce832bd422
---

# KTC Value Prediction ML Pipeline

## Goal
Predict future KTC value changes (7-day horizon) using historical snapshots and player features.

## Timeline

| Phase | Status | Target Date |
|-------|--------|-------------|
| Data collection started | Done | Dec 17, 2025 |
| 30 snapshots collected | Pending | ~Jan 16, 2025 |
| Model training ready | Pending | Jan 2025 |

## Data Collection

**Automated via GitHub Actions** (`daily-refresh.yml`)
- Runs twice daily (6 AM, 6 PM ET)
- Archives KTC snapshot to `data/historical/ktc_snapshots/`
- Consolidates to `ktc_all_snapshots.csv`

**Archive script:** `scripts/archive_ktc_snapshot.py`

## Feature Engineering

| Feature Category | Features |
|------------------|----------|
| Value momentum | 1d/3d/7d/14d changes, % changes |
| Trend signals | MA crossover, trend direction, volatility |
| Position context | Rank within position, vs position average |
| Age factors | Years from peak, age bucket |

## Model Architecture

```
Historical Snapshots → Feature Engineering → Gradient Boosting → 7-Day Prediction
         ↓                    ↓                    ↓
   ktc_snapshots/     KTCFeatureEngineer      KTCPredictor
```

**Pipeline file:** `pipelines/ktc_prediction_pipeline.py`

## Usage

```bash
# Check data readiness
python pipelines/ktc_prediction_pipeline.py

# After 30+ snapshots, runs full training
# Outputs predictions to data/predictions/
```

## Expected Outputs

- **Predicted Risers:** Players likely to gain value
- **Predicted Fallers:** Players likely to lose value
- **Feature importance:** What drives value changes

## Future Enhancements

- [ ] Add NFL performance correlation (targets, snap %, injuries)
- [ ] Ensemble with H2O AutoML
- [ ] Real-time dashboard integration
- [ ] Alert system for big predicted moves
