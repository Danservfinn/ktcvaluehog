---
title: Valuation Model Functions
link: valuation-model-functions
type: code_index
ontological_relations: []
tags:
- valuation
- aging-curves
- python
created_at: 2025-12-17T16:14:57Z
updated_at: 2025-12-17T16:14:57Z
uuid: 6bf30c68-bf3d-4801-988d-0afe040fa530
---

# Valuation Model Functions

## File: `valuation_model.py`

Generates independent dynasty player valuations to compare against KTC crowdsourced values.

## Configuration Constants

```python
LEAGUE_SETTINGS = {
    'scoring': 'PPR',
    'superflex': True,
    'te_premium': 0.5,
    'roster_size': 28,
    'num_teams': 10
}

SCARCITY_MULTIPLIER = {
    'QB': 1.8,   # Superflex boost
    'RB': 1.0,   # Baseline
    'WR': 1.0,   # Baseline
    'TE': 1.35   # TE premium
}

DISCOUNT_RATE = 0.85  # Annual future value discount
```

## Key Functions

### `get_aging_factor(position: str, age: float) -> float`
Returns aging curve multiplier (0.0-1.0) based on position and age.

**Peak Ages by Position:**
| Position | Peak | Decline Start | Steep Decline |
|----------|------|---------------|---------------|
| QB | 0-28 | 31+ | 34+ |
| RB | 0-24 | 25+ | 27+ |
| WR | 0-26 | 28+ | 30+ |
| TE | 0-27 | 30+ | 32+ |

### Edge Score Calculation
```python
edge_score = our_valuation - ktc_value
# Positive = BUY signal (undervalued)
# Negative = SELL signal (overvalued)
```

## Usage Example
```python
from valuation_model import calculate_player_value

value = calculate_player_value(
    player_name="Ja'Marr Chase",
    position="WR",
    age=24,
    production_score=95
)
```
