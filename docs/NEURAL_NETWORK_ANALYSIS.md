# Neural Network Analysis for Fantasy Football Prediction

## Executive Summary

This document analyzes neural network approaches for predicting fantasy football production and dynasty trade values using the Thoth platform's data.

### Key Finding
**With 6,088 training samples, well-regularized Gradient Boosting (R²=0.622) matches or outperforms neural networks.** Neural networks require significantly more data to capture complex patterns effectively.

---

## Data Overview

| Dataset | Samples | Features | Years |
|---------|---------|----------|-------|
| Season Projection | 6,088 | 88 | 1999-2023 |
| Weekly Stats | 51,649 | 15 | 2019-2024 |
| Breakout Labels | 3,933 | 88 | 1999-2023 |

### Player Career Distribution
- 1 season: 444 players (27%)
- 2-3 seasons: 547 players (33%)
- 4-6 seasons: 428 players (26%)
- 7+ seasons: 252 players (15%)

---

## Architectures Tested

### 1. Simple Feedforward Network (FFN)
```
Input(25) → Dense(128) → ReLU → BN → Dropout(0.3) → Dense(64) → ReLU → Output(1)
+ Position Embedding(4 → 8)
```
**Result: R² = 0.545** (below GBM baseline)

### 2. Deep FFN with Residual Connections
```
Input → Projection(256) → [ResBlock(256)]×2 → Dense(64) → Output
```
**Result: R² = 0.617** (close to GBM)

### 3. Attention-Weighted Features
```
Input → Attention(softmax) → Weighted Input → Dense Layers → Output
```
**Result: R² = 0.607** (below GBM)

### 4. Position-Specific Networks
```
4 separate networks, one per position (QB/RB/WR/TE)
```
**Result: R² = -0.097** (failed - insufficient samples per position)

### 5. Multi-Task Learning (PPG + Change)
```
Shared Backbone → [PPG Head, Change Head]
Loss = L_ppg + 0.5 * L_change
```
**Result: R² = 0.609** (competitive but not better)

### 6. GBM + Residual NN Ensemble
```
Final = GBM_pred + 0.3 * NN_residual_pred
```
**Result: R² = 0.622** ✅ (slight improvement)

---

## Performance Comparison

| Model | Test R² | vs Baseline |
|-------|---------|-------------|
| **GBM + Residual NN** | **0.6221** | **+0.0001** |
| GBM Baseline | 0.6220 | - |
| Optimized Ensemble | 0.6194 | -0.0026 |
| Deep FFN | 0.6172 | -0.0048 |
| Multi-Task NN | 0.6086 | -0.0134 |
| Attention FFN | 0.6073 | -0.0147 |
| Simple FFN | 0.5449 | -0.0771 |

---

## Why Neural Networks Underperform

### 1. **Data Volume**
- 6K samples is small for deep learning
- Rule of thumb: need 10-100× parameters in samples
- Our models have ~50K parameters but only 6K samples

### 2. **Feature Quality**
- Handcrafted features (ppg_ppr, career_ppg) already capture most signal
- Neural networks excel at learning features from raw data
- Our features are already highly predictive (ppg_ppr correlation = 0.77)

### 3. **Problem Structure**
- Fantasy production is inherently noisy (~38% unexplained variance)
- Injuries, coaching changes, trades are unpredictable
- GBM's regularization handles noise well

### 4. **Sequence Length**
- Most players have ≤3 seasons of data
- Insufficient for LSTM/Transformer to learn trajectory patterns
- Career modeling needs longer sequences

---

## When Neural Networks Would Help

### More Data (10K+ samples)
- Combine multiple data sources
- Include weekly-level data for training
- Augment with synthetic data

### Raw Data Input
- Instead of aggregated features, use:
  - Play-by-play data
  - Game logs
  - Combine measurements (raw)
- Let NN learn feature representations

### Multi-Modal Learning
```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Season Stats   │     │  Weekly Trends  │     │  Athletic Data  │
│    Encoder      │     │    Encoder      │     │    Encoder      │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │     Fusion Layer        │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   Multi-Task Heads      │
                    │  [PPG] [KTC] [Breakout] │
                    └─────────────────────────┘
```

### Transfer Learning
- Pre-train on larger sports datasets
- Fine-tune on fantasy-specific data
- Use language models for player news sentiment

---

## Recommended Approach

### Current (6K samples): Use GBM
```python
GradientBoostingRegressor(
    n_estimators=100,
    max_depth=3,
    learning_rate=0.05,
    subsample=0.7,
    min_samples_split=20
)
```

### With More Data (20K+): Ensemble
```python
# GBM for main prediction
gbm_pred = gbm.predict(X)

# NN for residuals (captures non-linear patterns GBM misses)
nn_residual = nn.predict(X)

# Ensemble
final_pred = gbm_pred + 0.3 * nn_residual
```

### With Much More Data (100K+): Full Neural Network
```python
# Multi-task Transformer
model = TransformerMultiTask(
    d_model=128,
    n_heads=8,
    n_layers=4,
    tasks=['ppg', 'ktc', 'breakout']
)
```

---

## KTC Value Prediction Considerations

### Current Approach
KTC values are predicted using a separate model with contract data as primary driver.

### Neural Network Opportunity
KTC values have:
- More training samples (can use all historical KTC)
- Non-linear relationships with production
- Market dynamics (hype, age perception)

**Potential Architecture:**
```
Player Stats + Age + Contract + Draft Capital → Embedding
                                                    ↓
                                              LSTM(career history)
                                                    ↓
                                              Attention(recent performance weight)
                                                    ↓
                                              KTC Prediction
```

---

## Implementation Recommendations

### Short-term (Current Data)
1. Keep GBM as primary model (R²=0.622)
2. Use GBM + NN ensemble for marginal gains
3. Focus on feature engineering over architecture

### Medium-term (Expand Data)
1. Collect weekly-level training data
2. Add historical KTC values for time series
3. Implement multi-task learning

### Long-term (Full Neural)
1. Build play-by-play feature extraction
2. Implement transformer architecture
3. Pre-train on NFL statistics, fine-tune for fantasy

---

## Files Created

| File | Purpose |
|------|---------|
| `src/ml/neural_network_models.py` | PyTorch implementations |
| `docs/NEURAL_NETWORK_ANALYSIS.md` | This document |

---

## Conclusion

Neural networks are **not currently recommended** as the primary model due to limited training data. The well-regularized GBM achieves R²=0.622, which represents approximately 62% of explainable variance in next-season fantasy production.

The **GBM + Residual NN ensemble** offers marginal improvement and could be valuable if:
- We need uncertainty estimates
- We want to capture residual non-linear patterns
- We plan to expand to multi-task learning

**Future work** should focus on expanding the dataset through weekly-level data and historical KTC values before investing heavily in neural network architecture improvements.
