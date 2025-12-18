# Data Sources Implementation Plan

## Status: PLANNING

## Context

- **Railway Import Status**: Database is currently being imported to Railway - DO NOT INTERRUPT
- **Current Scheduler**: macOS launchd with plist files (KTC runs twice daily at 6AM/6PM)
- **Script Pattern**: Existing ingest scripts use `nfl_data_py`, `Neo4jClient`, batch MERGE operations
- **Target**: 20K+ training samples to enable neural network viability

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        DATA INGESTION PIPELINE                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   WEEKLY (In-Season: Sep-Jan)                                           │
│   ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐     │
│   │  PBP Features    │  │  Injuries        │  │  Depth Charts    │     │
│   │  (Tue 4AM)       │  │  (Wed 4AM)       │  │  (Thu 4AM)       │     │
│   └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘     │
│            │                     │                     │                 │
│            └─────────────────────┼─────────────────────┘                 │
│                                  ▼                                       │
│   DAILY                  ┌──────────────────┐                           │
│   ┌──────────────────┐   │   Neo4j          │                           │
│   │  KTC Snapshots   │──▶│   (Railway)      │                           │
│   │  (6AM/6PM)       │   │                  │                           │
│   └──────────────────┘   └────────┬─────────┘                           │
│                                   │                                      │
│   SEASONAL                        │                                      │
│   ┌──────────────────┐            │                                      │
│   │  Contracts       │────────────┤  (Pre-Season: Aug)                  │
│   │  College Data    │────────────┤  (Pre-Draft: Mar-Apr)               │
│   │  Defense Stats   │────────────┘  (Post-Season: Feb)                 │
│   └──────────────────┘                                                   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 0: Pre-Implementation Setup (BEFORE Railway import completes)

### 0.1 Create Base Infrastructure

**Files to Create:**
```
scripts/
├── data_jobs/
│   ├── __init__.py
│   ├── base_ingester.py      # Abstract base class
│   ├── job_runner.py         # Unified job runner with logging
│   └── utils.py              # Shared utilities
├── ingest_pbp_features.py    # Play-by-play aggregations
├── ingest_college_data.py    # CFBD API integration
├── ingest_contracts.py       # Spotrac scraping
├── ingest_defense_rankings.py # Team defense profiles
├── weekly_data_job.py        # Combined weekly job
└── seasonal_data_job.py      # Combined seasonal job

config/
├── com.thoth.ktc-snapshot.plist       # (existing)
├── com.thoth.weekly-data.plist        # NEW: Weekly data job
└── com.thoth.seasonal-data.plist      # NEW: Seasonal data job
```

### 0.2 Base Ingester Class

```python
# scripts/data_jobs/base_ingester.py
"""Base class for all data ingesters with common patterns."""

from abc import ABC, abstractmethod
from pathlib import Path
from datetime import datetime
import logging

class BaseIngester(ABC):
    """Base class providing common ingestion patterns."""

    def __init__(self, name: str, use_railway: bool = True):
        self.name = name
        self.use_railway = use_railway
        self.logger = logging.getLogger(name)
        self.stats = {'created': 0, 'updated': 0, 'errors': 0}

    @abstractmethod
    def download_data(self, **kwargs) -> pd.DataFrame:
        """Download data from source."""
        pass

    @abstractmethod
    def process_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Process and clean data."""
        pass

    @abstractmethod
    def create_nodes(self, df: pd.DataFrame) -> int:
        """Create/update Neo4j nodes."""
        pass

    def run(self, **kwargs) -> dict:
        """Execute full ETL pipeline."""
        start = datetime.now()
        try:
            df = self.download_data(**kwargs)
            df = self.process_data(df)
            count = self.create_nodes(df)
            return {
                'status': 'success',
                'records': count,
                'duration': (datetime.now() - start).seconds
            }
        except Exception as e:
            self.logger.error(f"Job failed: {e}")
            return {'status': 'failed', 'error': str(e)}
```

---

## Phase 1: Play-by-Play Aggregations (CRITICAL PATH)

### Priority: 🔴 HIGHEST
### Timeline: Week 1-2
### Dependencies: None (uses existing nfl_data_py)

### 1.1 Script: `scripts/ingest_pbp_features.py`

```python
"""
NFL Play-by-Play Feature Aggregation
====================================
Extracts player-level features from play-by-play data.

Data Source: nfl_data_py.import_pbp_data()
Records: ~15,000 player-season aggregations
Schedule: Weekly during season (Tuesday 4AM)

Usage:
    python scripts/ingest_pbp_features.py --years 2023 2024
    python scripts/ingest_pbp_features.py --current-week
"""

# Key aggregations to compute:
AGGREGATIONS = {
    # Red Zone (inside 20)
    'rz_targets': 'sum(targets where yardline <= 20)',
    'rz_carries': 'sum(carries where yardline <= 20)',
    'rz_td_rate': 'tds / rz_opportunities',

    # Goal Line (inside 5)
    'gl_carries': 'sum(carries where yardline <= 5)',
    'gl_td_rate': 'tds / gl_opportunities',

    # EPA metrics (already in pbp data)
    'epa_per_target': 'mean(epa where play_type == pass)',
    'epa_per_carry': 'mean(epa where play_type == rush)',

    # Air yards
    'air_yards_share': 'player_air_yards / team_air_yards',
    'adot': 'air_yards / targets',
    'wopr': '1.5 * target_share + 0.7 * air_yards_share',

    # Situational
    'third_down_targets': 'targets on 3rd down',
    'two_min_targets': 'targets in 2-minute drill',
    'neutral_script_touches': 'touches when |score_diff| <= 7',
}
```

### 1.2 Neo4j Schema

```cypher
// Index and constraint
CREATE CONSTRAINT pbp_agg_unique IF NOT EXISTS
FOR (p:PlayByPlayAggregates) REQUIRE (p.player_id, p.season, p.week) IS UNIQUE;

CREATE INDEX pbp_season IF NOT EXISTS FOR (p:PlayByPlayAggregates) ON (p.season);
CREATE INDEX pbp_position IF NOT EXISTS FOR (p:PlayByPlayAggregates) ON (p.position);

// Node structure
(:PlayByPlayAggregates {
    player_id: STRING,
    player_name: STRING,
    position: STRING,
    team: STRING,
    season: INTEGER,
    week: INTEGER,              // 0 = season total

    // Red Zone
    rz_targets: INTEGER,
    rz_receptions: INTEGER,
    rz_carries: INTEGER,
    rz_tds: INTEGER,
    rz_td_rate: FLOAT,

    // Goal Line
    gl_carries: INTEGER,
    gl_tds: INTEGER,
    gl_td_rate: FLOAT,

    // EPA/Efficiency
    epa_per_target: FLOAT,
    epa_per_carry: FLOAT,
    cpoe: FLOAT,

    // Air Yards
    air_yards: INTEGER,
    air_yards_share: FLOAT,
    adot: FLOAT,
    wopr: FLOAT,
    target_per_route: FLOAT,

    // Situational
    third_down_targets: INTEGER,
    neutral_script_touches: INTEGER,
    garbage_time_pct: FLOAT,

    loaded_at: DATETIME
})
```

### 1.3 Update Schedule

| Period | Frequency | Time | Notes |
|--------|-----------|------|-------|
| In-Season | Weekly | Tuesday 4:00 AM | After Monday Night Football |
| Off-Season | None | - | Historical data stable |

---

## Phase 2: Weekly Data Job Consolidation

### Priority: 🔴 HIGH
### Timeline: Week 2-3
### Dependencies: Phase 1 complete

### 2.1 Combined Weekly Job: `scripts/weekly_data_job.py`

```python
"""
Weekly Data Consolidation Job
=============================
Runs all weekly data ingestion in correct order.

Schedule: Tuesday 4:00 AM (during NFL season)
Duration: ~15-20 minutes

Components:
1. Play-by-Play Aggregations (Week N-1 data)
2. Injury Reports (Latest injury designations)
3. Depth Charts (Latest depth chart positions)
4. KTC Trend Update (Recalculate trends)
"""

from pathlib import Path
import subprocess
from datetime import datetime
import logging

JOBS = [
    {
        'name': 'pbp_features',
        'script': 'scripts/ingest_pbp_features.py',
        'args': ['--current-week'],
        'timeout': 600,  # 10 min
    },
    {
        'name': 'injuries',
        'script': 'scripts/ingest_injuries.py',
        'args': ['--current-week'],
        'timeout': 120,  # 2 min
    },
    {
        'name': 'depth_charts',
        'script': 'scripts/ingest_depth_charts.py',
        'args': ['--current-week'],
        'timeout': 120,  # 2 min
    },
    {
        'name': 'ktc_trends',
        'script': 'scripts/process_ktc_timeseries.py',
        'args': [],
        'timeout': 60,  # 1 min
    },
]

def run_weekly_jobs():
    """Execute all weekly jobs in sequence."""
    results = {}
    for job in JOBS:
        try:
            result = subprocess.run(
                ['python', job['script']] + job['args'],
                timeout=job['timeout'],
                capture_output=True
            )
            results[job['name']] = 'success' if result.returncode == 0 else 'failed'
        except Exception as e:
            results[job['name']] = f'error: {e}'
    return results
```

### 2.2 Launchd Configuration

```xml
<!-- config/com.thoth.weekly-data.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" ...>
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.thoth.weekly-data</string>

    <key>ProgramArguments</key>
    <array>
        <string>/Library/Frameworks/Python.framework/Versions/3.13/bin/python3</string>
        <string>/Users/kurultai/ktcvaluehog/scripts/weekly_data_job.py</string>
    </array>

    <key>WorkingDirectory</key>
    <string>/Users/kurultai/ktcvaluehog</string>

    <!-- Run Tuesday at 4:00 AM during NFL season -->
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key>
        <integer>2</integer>  <!-- Tuesday -->
        <key>Hour</key>
        <integer>4</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>

    <key>StandardOutPath</key>
    <string>/Users/kurultai/ktcvaluehog/logs/weekly_data_stdout.log</string>

    <key>StandardErrorPath</key>
    <string>/Users/kurultai/ktcvaluehog/logs/weekly_data_stderr.log</string>
</dict>
</plist>
```

---

## Phase 3: College Football Data

### Priority: 🟠 HIGH
### Timeline: Week 3-4
### Dependencies: CFBD API key required

### 3.1 Script: `scripts/ingest_college_data.py`

```python
"""
College Football Data Ingestion
================================
Fetches college statistics for NFL draft prospects.

Data Source: College Football Data API (collegefootballdata.com)
API Limit: 1,000 calls/month (free tier)
Records: ~3,000 prospect profiles

Schedule:
- One-time historical load (all drafted players 2015-2024)
- Seasonal update (March, pre-draft)

Usage:
    python scripts/ingest_college_data.py --draft-years 2015 2024
    python scripts/ingest_college_data.py --upcoming-draft
"""

# API rate limiting strategy:
# - Cache all API responses locally
# - Batch player lookups efficiently
# - ~300 players/draft class × 10 years = 3,000 total
# - With caching, fits in free tier
```

### 3.2 Neo4j Schema

```cypher
(:CollegeProfile {
    player_id: STRING,
    college: STRING,
    conference: STRING,

    // Production
    college_games: INTEGER,
    college_yards: INTEGER,
    college_tds: INTEGER,
    college_ppg: FLOAT,           // Projected to fantasy scoring
    college_market_share: FLOAT,  // % of team production

    // Context
    breakout_age: FLOAT,
    final_year_ppg: FLOAT,
    conference_strength: FLOAT,

    // Recruiting (if available)
    recruiting_stars: INTEGER,
    recruiting_rank: INTEGER,

    loaded_at: DATETIME
})

// Relationship to Player node
MATCH (p:Player), (cp:CollegeProfile)
WHERE p.gsis_id = cp.player_id
MERGE (p)-[:HAS_COLLEGE_PROFILE]->(cp)
```

---

## Phase 4: Contract Data

### Priority: 🟠 HIGH
### Timeline: Week 4-5
### Dependencies: Web scraping setup, ethical considerations

### 4.1 Script: `scripts/ingest_contracts.py`

```python
"""
NFL Contract Data Ingestion
===========================
Scrapes player contract information from Spotrac.

Data Source: Spotrac (spotrac.com/nfl)
Method: BeautifulSoup web scraping
Records: ~2,500 player contracts

Schedule: Pre-season (August), weekly during FA period

IMPORTANT:
- Respect robots.txt and rate limits
- Cache responses to minimize requests
- Consider ToS implications

Usage:
    python scripts/ingest_contracts.py --all-teams
    python scripts/ingest_contracts.py --team DAL
"""

# Scraping strategy:
# - Rate limit: 1 request per 3 seconds
# - Cache responses for 24 hours
# - Parse team cap pages: spotrac.com/nfl/{team}/cap/
```

### 4.2 Neo4j Schema

```cypher
(:PlayerContract {
    player_id: STRING,
    season: INTEGER,

    // Contract
    apy: FLOAT,
    total_value: FLOAT,
    years_total: INTEGER,
    years_remaining: INTEGER,
    guaranteed_remaining: FLOAT,

    // Cap
    cap_hit: FLOAT,
    dead_cap: FLOAT,

    // Status
    is_contract_year: BOOLEAN,
    is_rookie_deal: BOOLEAN,
    free_agent_year: INTEGER,

    // Ranking
    position_apy_rank: INTEGER,

    loaded_at: DATETIME
})
```

---

## Phase 5: Defense Rankings

### Priority: 🟡 MEDIUM
### Timeline: Week 5-6
### Dependencies: PBP data (Phase 1)

### 5.1 Script: `scripts/ingest_defense_rankings.py`

```python
"""
Team Defense Rankings
=====================
Computes defensive efficiency metrics from PBP data.

Data Source: Derived from nfl_data_py play-by-play
Records: ~640 team-season profiles (32 teams × 20 years)

Schedule: Weekly during season, post-season final update

Usage:
    python scripts/ingest_defense_rankings.py --years 2020 2024
    python scripts/ingest_defense_rankings.py --current-season
"""

# Computed from PBP:
# - EPA allowed per play
# - Pass/Rush EPA splits
# - Fantasy points allowed by position
```

### 5.2 Neo4j Schema

```cypher
(:TeamDefenseProfile {
    team: STRING,
    season: INTEGER,
    week: INTEGER,  // 0 = season total

    // Efficiency
    def_epa_per_play: FLOAT,
    def_success_rate: FLOAT,

    // Splits
    pass_epa_allowed: FLOAT,
    rush_epa_allowed: FLOAT,

    // Fantasy impact
    ppg_allowed_qb: FLOAT,
    ppg_allowed_rb: FLOAT,
    ppg_allowed_wr: FLOAT,
    ppg_allowed_te: FLOAT,

    loaded_at: DATETIME
})
```

---

## Implementation Schedule

### Pre-Railway Completion (Current)
| Task | Status | Notes |
|------|--------|-------|
| Create base infrastructure | 🔲 Pending | Can do now |
| Write PBP feature script | 🔲 Pending | Can do now, test locally |
| Design Neo4j schemas | 🔲 Pending | Can do now |
| Create launchd configs | 🔲 Pending | Can do now |

### Post-Railway Completion (After import finishes)
| Week | Phase | Task |
|------|-------|------|
| 1 | Setup | Install launchd agents, verify Railway connectivity |
| 1-2 | Phase 1 | Deploy PBP features ingester, run historical load |
| 2-3 | Phase 2 | Deploy weekly job consolidation |
| 3-4 | Phase 3 | Deploy college data ingester |
| 4-5 | Phase 4 | Deploy contract data ingester |
| 5-6 | Phase 5 | Deploy defense rankings |
| 6 | Verify | End-to-end testing, monitoring setup |

---

## Railway Sync Strategy

### Option A: Direct to Railway (Recommended)
```
Local Script → Railway Neo4j (bolt://)
```
- Scripts connect directly to Railway
- Real-time updates
- Requires stable network

### Option B: Local + Sync
```
Local Script → Local Neo4j → Export → Railway Import
```
- Scripts run against local
- Periodic sync to Railway
- More complex, but resilient

### Recommendation: Option A
- Simpler architecture
- Already have Railway credentials
- Use `NEO4J_URI` env var to switch environments

```python
# In .env
NEO4J_URI=bolt://sparkling-commitment-production.up.railway.app:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=dynastyedge2025
```

---

## Monitoring & Alerting

### Log Files
```
logs/
├── ktc_snapshot.log         # Existing
├── weekly_data.log          # NEW
├── pbp_features.log         # NEW
├── college_data.log         # NEW
├── contracts.log            # NEW
├── defense_rankings.log     # NEW
└── job_summary.log          # Combined status
```

### Health Check Script
```python
# scripts/check_data_freshness.py
"""
Check that all data sources are up-to-date.
Alert if any source is stale.
"""

FRESHNESS_THRESHOLDS = {
    'KTCSnapshot': timedelta(hours=24),
    'PlayByPlayAggregates': timedelta(days=7),
    'InjuryReport': timedelta(days=7),
    'DepthChartEntry': timedelta(days=7),
}
```

---

## Risk Mitigation

### Railway Import in Progress
- **Risk**: Running ingest scripts during import could cause conflicts
- **Mitigation**: All new scripts check for `IMPORT_IN_PROGRESS` flag
- **Implementation**: Create marker file `data/.import_lock`

```python
# In base_ingester.py
IMPORT_LOCK = Path("data/.import_lock")

def check_import_lock(self):
    if IMPORT_LOCK.exists():
        self.logger.warning("Import in progress, skipping job")
        return True
    return False
```

### API Rate Limits
- **CFBD**: 1,000 calls/month → Cache aggressively
- **KTC**: Unknown limits → Already handling gracefully
- **Spotrac**: Unknown → Rate limit to 1 req/3 sec

### Data Quality
- All scripts log to persistent files
- Weekly summary email (future enhancement)
- Validation queries after each load

---

## Files Created

### Infrastructure (DONE)
| File | Status | Description |
|------|--------|-------------|
| `scripts/data_jobs/__init__.py` | ✅ Done | Package init |
| `scripts/data_jobs/base_ingester.py` | ✅ Done | Abstract base class |
| `scripts/data_jobs/utils.py` | ✅ Done | Common utilities |
| `scripts/data_jobs/job_runner.py` | ✅ Done | Job orchestration |
| `scripts/ingest_pbp_features.py` | ✅ Done | PBP aggregation ingester |
| `scripts/weekly_data_job.py` | ✅ Done | Weekly job orchestrator |
| `scripts/install_weekly_scheduler.sh` | ✅ Done | launchd installer |
| `config/com.thoth.weekly-data.plist` | ✅ Done | launchd config |

### Requires Modification
| File | Change Needed |
|------|---------------|
| `scripts/ingest_injuries.py` | Add `--current-week` flag support |
| `scripts/ingest_depth_charts.py` | Add `--current-week` flag support |

### Still Needed (After Railway Import)
| File | Priority | Description |
|------|----------|-------------|
| `scripts/ingest_college_data.py` | 🟠 High | CFBD API integration |
| `scripts/ingest_contracts.py` | 🟠 High | Spotrac scraping |
| `scripts/ingest_defense_rankings.py` | 🟡 Medium | Team defense profiles |
| `scripts/seasonal_data_job.py` | 🟡 Medium | Pre-season job runner |
| `scripts/check_data_freshness.py` | 🟢 Low | Data monitoring |

---

## Success Criteria

| Metric | Current | Target |
|--------|---------|--------|
| Training samples | 6,088 | 20,000+ |
| Weekly data freshness | N/A | < 7 days |
| KTC data freshness | < 24 hours | < 24 hours |
| Job success rate | N/A | > 95% |
| Model R² | 0.622 | 0.70+ |

---

## Next Steps

1. **Wait for Railway import to complete** (check status)
2. Create base infrastructure (can start now)
3. Implement PBP features script first (highest ROI)
4. Test locally before enabling Railway sync
5. Deploy weekly scheduler after validation
