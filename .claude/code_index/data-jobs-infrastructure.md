---
type: code_index
tags:
  - data-pipeline
  - automation
  - neo4j
  - nfl-data
created: 2024-12-18
---

# Data Jobs Infrastructure

## Overview

Unified data ingestion framework for Dynasty Edge that provides:
- Abstract base class for consistent ingester patterns
- Job orchestration with logging and error handling
- Weekly automated data refresh via macOS launchd
- Import lock mechanism for Railway sync safety

## Directory Structure

```
scripts/
├── data_jobs/
│   ├── __init__.py           # Package exports
│   ├── base_ingester.py      # Abstract base class
│   ├── job_runner.py         # Multi-job orchestration
│   └── utils.py              # NFL utilities
├── weekly_data_job.py        # Weekly job orchestrator
├── ingest_pbp_features.py    # Play-by-play aggregations
└── install_weekly_scheduler.sh  # launchd installer

config/
├── com.thoth.ktc-snapshot.plist   # Daily KTC (6AM/6PM)
└── com.thoth.weekly-data.plist    # Weekly data (Tue 4AM)
```

## Base Ingester Class

All data ingesters inherit from `BaseIngester` which provides:

```python
from scripts.data_jobs import BaseIngester

class MyIngester(BaseIngester):
    def __init__(self):
        super().__init__('my_ingester', batch_size=500)

    def download_data(self, **kwargs) -> pd.DataFrame:
        # Download from source
        pass

    def process_data(self, df: pd.DataFrame) -> pd.DataFrame:
        # Clean and transform
        pass

    def create_schema(self):
        # Neo4j indexes/constraints
        pass

    def create_nodes(self, df: pd.DataFrame) -> int:
        # Batch MERGE to Neo4j
        return self.batch_merge(query, records)
```

### Key Features

- **Lazy Neo4j connection**: Driver only initialized when needed
- **Batch processing**: `batch_merge()` for efficient large inserts
- **Import lock checking**: Respects `data/.import_lock` file
- **Logging**: Console + file logging with job-specific files
- **Statistics tracking**: Records processed, nodes created, errors

## Job Runner

Orchestrates multiple ingestion jobs:

```python
from scripts.data_jobs import JobRunner

runner = JobRunner('weekly_data')
result = runner.run_jobs([
    {'name': 'pbp', 'script': 'scripts/ingest_pbp.py', 'timeout': 600},
    {'name': 'injuries', 'script': 'scripts/ingest_injuries.py'},
])
```

### Features

- Sequential execution with dependency handling
- Timeout enforcement
- Status persistence to `logs/{runner}_status.json`
- Import lock checking before run

## Weekly Data Pipeline

Runs every Tuesday at 4AM (after Monday Night Football):

| Order | Job | Timeout | Description |
|-------|-----|---------|-------------|
| 1 | `pbp_features` | 10 min | EPA, red zone, air yards |
| 2 | `injuries` | 3 min | Injury reports |
| 3 | `depth_charts` | 3 min | Depth positions |
| 4 | `ktc_trends` | 2 min | Value trend recalc |

## Play-by-Play Features

The `ingest_pbp_features.py` script extracts player-level aggregations:

### Receiving Metrics
- `targets`, `receptions`, `receiving_yards`, `receiving_tds`
- `air_yards`, `air_yards_share`, `adot`
- `wopr` (Weighted Opportunity Rating)
- `target_share`, `epa_per_target`, `catch_rate`
- `rz_targets`, `third_down_targets`

### Rushing Metrics
- `carries`, `rushing_yards`, `rushing_tds`
- `epa_per_carry`, `ypc`
- `rz_carries`, `gl_carries`
- `rz_td_rate`, `gl_td_rate`

### Neo4j Schema

```cypher
(:PlayByPlayAggregates {
    player_id: STRING,
    season: INTEGER,
    week: INTEGER,
    stat_type: STRING,  // 'receiving' or 'rushing'

    // Receiving
    targets, receptions, receiving_yards, receiving_tds,
    air_yards, air_yards_share, adot, wopr, target_share,
    epa_per_target, catch_rate,

    // Rushing
    carries, rushing_yards, rushing_tds,
    epa_per_carry, ypc,

    // Red zone
    rz_targets, rz_carries, gl_carries,
    rz_td_rate, gl_td_rate,

    // Situational
    third_down_targets, neutral_script_targets,

    loaded_at: DATETIME
})
```

## Utilities

### NFL Week Detection
```python
from scripts.data_jobs import get_current_nfl_week, is_nfl_season

season, week = get_current_nfl_week()  # (2024, 15)
if is_nfl_season():  # True during Sep-Feb
    run_weekly_jobs()
```

### Import Lock
```python
from scripts.data_jobs import check_import_lock, create_import_lock

if check_import_lock():
    print("Railway import in progress, skipping")

create_import_lock("Railway database sync")
```

### Team Normalization
```python
from scripts.data_jobs.utils import normalize_team_abbr

normalize_team_abbr('OAK')  # -> 'LV'
normalize_team_abbr('SD')   # -> 'LAC'
```

## Commands

```bash
# Weekly job
python scripts/weekly_data_job.py              # Run all
python scripts/weekly_data_job.py --job pbp    # Run one
python scripts/weekly_data_job.py --dry-run    # Preview
python scripts/weekly_data_job.py --status     # Last run

# PBP features
python scripts/ingest_pbp_features.py --years 2024
python scripts/ingest_pbp_features.py --current-week
python scripts/ingest_pbp_features.py --test

# Scheduler
./scripts/install_weekly_scheduler.sh
launchctl list | grep thoth
launchctl start com.thoth.weekly-data
```

## Related Files

- Implementation plan: `.claude/plans/data-sources-implementation.md`
- Data catalog: `docs/DATA_CATALOG.md`
- Additional sources analysis: `docs/ADDITIONAL_DATA_SOURCES_V2.md`
