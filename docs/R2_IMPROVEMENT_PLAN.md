# R² Improvement Plan for Fantasy Production Model

## Current State (UPDATED 2024-12-17)
- **Previous R²:** 0.65
- **Current R²:** 0.8789 ✅
- **Target R²:** 0.75+ (EXCEEDED)
- **Training Samples:** 6,088
- **Features:** 73 (after leakage removal)
- **RMSE:** 1.98 PPG
- **MAE:** 1.52 PPG

### Improvement Achieved: +0.23 R²

## Methods to Pursue (Priority Order)

### 1. Feature Engineering (Expected +0.03-0.05 R²)

**A. Add Weighted Recent Performance**
- Last 4 games weighted average (more recent = higher weight)
- Last 8 games momentum score
- Week-over-week variance in performance

**B. Add Opportunity Trajectory**
- Snap count trend (increasing/decreasing)
- Target share trend
- Touch share trend
- Red zone opportunity growth

**C. Add Contextual Features**
- Team offensive ranking (points scored)
- QB change indicator
- Offensive coordinator change
- Division strength (opponent quality)

**D. Add Age-Position Curves**
- Position-specific age curves (WR peaks later than RB)
- Years to expected peak
- Years past expected peak

**E. Add Injury Context**
- Games missed previous season
- Injury type (soft tissue vs structural)
- Recovery trajectory

### 2. Position-Specific Models (Expected +0.02-0.04 R²)

Train separate models for QB, RB, WR, TE because:
- Different feature importances per position
- Different aging curves
- Different variance profiles

### 3. Ensemble Methods (Expected +0.03-0.05 R²)

Combine predictions from:
- Neural Network (current)
- Gradient Boosting (LightGBM)
- Random Forest
- Ridge Regression

Weighted ensemble or stacking typically outperforms single models.

### 4. Sequence Modeling with LSTM (Expected +0.02-0.04 R²)

Use player career trajectory:
- Input: Last N seasons of stats
- Capture career arc patterns
- Learn breakout vs decline signals

### 5. Hyperparameter Optimization (Expected +0.01-0.02 R²)

Grid search over:
- Learning rate: [1e-4, 5e-4, 1e-3, 5e-3]
- Hidden layers: [2, 3, 4]
- Hidden dim: [64, 128, 256, 512]
- Dropout: [0.1, 0.2, 0.3, 0.4]
- Batch size: [32, 64, 128]

### 6. Data Augmentation (Expected +0.01-0.03 R²)

- Add synthetic samples for underrepresented cases
- Use weekly data aggregated differently
- Cross-validation with time-based splits

### 7. Target Engineering (Expected +0.01-0.02 R²)

- Log transform target (reduce impact of outliers)
- Predict rank instead of raw PPG
- Multi-task: predict PPG + games played

## Implementation Order

1. **Phase 1: Quick Wins (Today)**
   - Add weighted recent performance features
   - Implement position-specific models
   - Add ensemble with LightGBM

2. **Phase 2: Architecture (Tomorrow)**
   - Implement LSTM sequence model
   - Hyperparameter grid search

3. **Phase 3: Data Enhancement (Next)**
   - Add contextual features from Neo4j
   - Integrate injury/depth chart data

## Success Metrics

| Metric | Baseline | Target | Achieved | Status |
|--------|----------|--------|----------|--------|
| Overall R² | 0.65 | 0.75 | **0.8789** | ✅ |
| QB R² | ~0.60 | 0.70 | 0.5620 | ⚠️ |
| RB R² | ~0.55 | 0.68 | **0.8152** | ✅ |
| WR R² | ~0.65 | 0.75 | **0.8649** | ✅ |
| TE R² | ~0.55 | 0.70 | **0.8230** | ✅ |
| RMSE | 2.98 | <2.5 | **1.98** | ✅ |

---

## Implementation Results (2024-12-17)

### What Worked

1. **Ensemble Methods (+0.15 R²)**
   - Combined NN + GBM + RF + Ridge
   - Best weights: NN=0.20, GBM=0.50, RF=0.10, Ridge=0.20
   - GBM was the strongest individual model (0.8763)

2. **Betting Data Integration (+0.02-0.03 R²)**
   - Added team Elo ratings from Neo4j Game nodes
   - Integrated 538 Elo data (192 team-season records)
   - Team O/U lines for 2,202 matches

3. **Time-Based Split (Critical Fix)**
   - Train on seasons < 2022, test on 2022+
   - Prevents temporal leakage across player careers

4. **Data Leakage Removal (Critical Fix)**
   - Removed `ppg_change`, `ppg_change_pct` (derived from target)
   - Removed all `next_*` columns
   - This was causing artificially inflated R² (~1.0)

### Position-Specific Analysis

- **QB (0.56)**: Hardest position to predict due to high variance in performance
- **WR (0.86)**: Best position - consistent role players, clearer usage patterns
- **RB (0.82)**: Good prediction - workload is predictable
- **TE (0.82)**: Strong model - role stability helps

### Model Files Saved
- `data/models/ensemble_model.pt` - PyTorch ensemble metadata
- `data/models/ensemble_gbm.pkl` - Gradient Boosting model
- `data/models/ensemble_rf.pkl` - Random Forest model
- `data/models/ensemble_ridge.pkl` - Ridge regression model

### Next Steps
1. Install LightGBM for potentially better GBM performance
2. Add more contextual features (QB change indicator, schedule strength)
3. Consider LSTM for career trajectory modeling
4. Focus on improving QB model (currently underperforming)
