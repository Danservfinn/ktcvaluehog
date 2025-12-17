---
title: KTC Archiving Script
link: ktc-archiving-script
type: code_index
ontological_relations: []
tags:
- archiving
- data-collection
- python
created_at: 2025-12-17T16:24:39Z
updated_at: 2025-12-17T16:24:39Z
uuid: 088da025-5b36-4cb1-a3d0-5f6ca9e8f289
---

# KTC Archiving Script

## File: `scripts/archive_ktc_snapshot.py`

Archives daily KTC values for future ML time-series training.

## Purpose
Collects historical KTC snapshots needed for the prediction pipeline. Requires 30+ daily snapshots before ML training can begin.

## Output Files

| File | Location | Description |
|------|----------|-------------|
| Daily snapshot | `data/historical/ktc_snapshots/ktc_YYYYMMDD.csv` | Single day's values |
| Consolidated | `data/historical/ktc_snapshots/ktc_all_snapshots.csv` | All snapshots combined |

## Fields Extracted

```python
{
    'player_id': int,      # KTC player ID
    'name': str,           # Player name
    'position': str,       # QB/RB/WR/TE
    'team': str,           # NFL team
    'age': float,          # Current age
    'sf_value': int,       # Superflex value (0-9999)
    'trend_7d': int,       # 7-day trend indicator
    'snapshot_date': str,  # YYYYMMDD
    'snapshot_ts': str     # ISO timestamp
}
```

## Usage

```bash
# Manual run
python scripts/archive_ktc_snapshot.py

# Automated via GitHub Actions (daily-refresh.yml)
# Runs twice daily after KTC fetch
```

## Key Functions

- `archive_from_json()` - Primary: parses `ktc_live.json`
- `archive_from_csv()` - Fallback: parses `ktc_scraped.csv`
- `extract_superflex_value()` - Extracts value from nested JSON

## Integration

Called by `.github/workflows/daily-refresh.yml` after `fetch_ktc_data.py`
