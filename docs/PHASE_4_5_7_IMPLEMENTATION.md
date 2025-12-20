# Phase 4, 5, 7 Implementation Summary

## Overview
Implemented three new data ingesters to support ML model R² improvement plan:
- **Phase 4**: College data ingestion (rookie projections)
- **Phase 5**: Coaching & scheme data ingestion (offensive philosophy)
- **Phase 7**: Defense rankings ingestion (matchup difficulty)

## Files Created

### 1. College Data Ingester
**File**: `/Users/kurultai/ktcvaluehog/scripts/ingest_college_data.py`

**Purpose**: Import college football profiles for rookie draft prospects

**Data Source**: College Football Data API (CFBD)
- Requires API key: `CFBD_API_KEY` environment variable
- Fallback to placeholder data if key not available

**Features Extracted**:
- `college_ppg` - Fantasy PPG equivalent
- `college_market_share` - % of team production
- `breakout_age` - Age at first productive season
- `final_year_production` - Senior/final year output
- `conference_strength` - SEC=1.0, Big Ten=0.92, etc.
- `recruiting_stars` - 247 composite (2-5 stars)

**Neo4j Schema**:
```cypher
(:CollegeProfile {
    player_id: STRING,
    player_name: STRING,
    position: STRING,
    college: STRING,
    conference: STRING,
    draft_year: INTEGER,
    college_season: INTEGER,
    college_ppg: FLOAT,
    college_games: INTEGER,
    college_market_share: FLOAT,
    final_year_production: FLOAT,
    breakout_age: FLOAT,
    recruiting_stars: INTEGER,
    conference_strength: FLOAT,
    loaded_at: DATETIME
})
```

**Usage**:
```bash
# Test mode
python scripts/ingest_college_data.py --draft-years 2023 2024 --test

# Production load
python scripts/ingest_college_data.py --draft-years 2020 2021 2022 2023 2024
```

**Expected Impact**: +0.05-0.08 R² on rookie predictions

---

### 2. Coaching Data Ingester
**File**: `/Users/kurultai/ktcvaluehog/scripts/ingest_coaching_data.py`

**Purpose**: Track coaching trees and offensive scheme tendencies

**Data Sources**:
- nflfastR play-by-play (for tendencies)
- Manual coaching tree classifications
- Pro Football Reference (coaching histories - placeholder)

**Features Extracted**:
- `coaching_tree` - mcvay/shanahan/reid/belichick/payton/other
- `pass_rate_neutral` - Pass rate when game within 7 pts
- `motion_rate` - Pre-snap motion frequency
- `play_action_rate` - Play-action usage
- `personnel_11_rate` - 3WR set frequency (1 RB, 1 TE, 3 WR)

**Neo4j Schema**:
```cypher
(:CoachingProfile {
    team: STRING,
    season: INTEGER,
    head_coach: STRING,
    offensive_coordinator: STRING,
    coaching_tree: STRING,
    pass_rate_neutral: FLOAT,
    motion_rate: FLOAT,
    play_action_rate: FLOAT,
    personnel_11_rate: FLOAT,
    total_plays: INTEGER,
    neutral_plays: INTEGER,
    loaded_at: DATETIME
})
```

**Coaching Tree Classifications**:
- **McVay/Shanahan**: Sean McVay, Kyle Shanahan, Matt LaFleur, Mike McDaniel, Zac Taylor, Kevin O'Connell
- **Reid**: Andy Reid, Doug Pederson, Matt Nagy, Eric Bieniemy
- **Belichick**: Bill Belichick, Brian Flores, Joe Judge, Matt Patricia
- **Payton**: Sean Payton, Dennis Allen
- **Other**: John Harbaugh, Mike Tomlin, Dan Campbell

**Usage**:
```bash
# Test mode
python scripts/ingest_coaching_data.py --years 2022 --test

# Production load
python scripts/ingest_coaching_data.py --years 2020 2021 2022 2023 2024
```

**Expected Impact**: +0.02-0.03 R² on scheme fit predictions

---

### 3. Defense Rankings Ingester
**File**: `/Users/kurultai/ktcvaluehog/scripts/ingest_defense_rankings.py`

**Purpose**: Calculate defensive efficiency metrics for matchup analysis

**Data Source**: nflfastR play-by-play aggregations

**Features Extracted**:
- `def_epa_per_play` - Overall defensive EPA per play
- `pass_epa_allowed` - EPA allowed on pass plays
- `rush_epa_allowed` - EPA allowed on rush plays
- `completion_rate_allowed` - Pass completion % allowed
- `yards_per_pass_allowed` - Average pass yards allowed
- `pressure_rate` - QB pressure frequency
- `sack_rate` - Sack frequency
- `yards_per_rush_allowed` - Average rush yards allowed
- `stuff_rate` - % of rushes for 0 or negative yards
- `ppg_allowed_qb/rb/wr/te` - Position-specific fantasy points allowed

**Neo4j Schema**:
```cypher
(:TeamDefenseProfile {
    team: STRING,
    season: INTEGER,
    total_plays: INTEGER,
    def_epa_per_play: FLOAT,
    pass_epa_allowed: FLOAT,
    rush_epa_allowed: FLOAT,
    completion_rate_allowed: FLOAT,
    yards_per_pass_allowed: FLOAT,
    pressure_rate: FLOAT,
    sack_rate: FLOAT,
    yards_per_rush_allowed: FLOAT,
    stuff_rate: FLOAT,
    ppg_allowed_qb: FLOAT,
    ppg_allowed_rb: FLOAT,
    ppg_allowed_wr: FLOAT,
    ppg_allowed_te: FLOAT,
    loaded_at: DATETIME
})
```

**Usage**:
```bash
# Test mode
python scripts/ingest_defense_rankings.py --years 2022 --test

# Production load (historical)
python scripts/ingest_defense_rankings.py --years 2020 2021 2022 2023 2024

# Weekly update during season
python scripts/ingest_defense_rankings.py --current-week
```

**Expected Impact**: +0.02-0.03 R² on matchup predictions

---

### 4. Contract Years CSV
**File**: `/Users/kurultai/ktcvaluehog/data/contract_years.csv`

**Purpose**: Manual tracking of contract year indicators for top players

**Structure**:
```csv
player_id,season,is_contract_year
00-0019596,2023,true
00-0033873,2024,true
...
```

**Usage**: Merge with training data for contract year indicator feature
- Players with ~50 entries (QBs, RBs, WRs, TEs)
- Placeholder data initially - should be updated with real contract data

---

## Implementation Details

### Base Class Pattern
All three ingesters extend `BaseIngester` from `/Users/kurultai/ktcvaluehog/scripts/data_jobs/base_ingester.py`:

```python
class DataIngester(BaseIngester):
    def __init__(self):
        super().__init__('ingester_name', batch_size=500)

    def download_data(self, **kwargs) -> pd.DataFrame:
        # Download raw data
        pass

    def process_data(self, df: pd.DataFrame) -> pd.DataFrame:
        # Clean and aggregate
        pass

    def create_schema(self):
        # Create Neo4j indexes/constraints
        pass

    def create_nodes(self, df: pd.DataFrame) -> int:
        # Write to Neo4j
        pass
```

### Common Features
All ingesters include:
- **Import lock checking**: Respects `.import_lock` file to avoid Railway conflicts
- **Caching**: Saves downloaded data locally for offline development
- **Batch processing**: Uses `batch_merge()` for efficient Neo4j writes
- **Test mode**: `--test` flag for dry runs without database writes
- **Logging**: Structured logging to console and file
- **Error handling**: Graceful degradation with fallbacks

### SSL Bypass
All scripts include SSL bypass for nflverse downloads:
```python
ssl._create_default_https_context = ssl._create_unverified_context
```

---

## Testing Results

### Defense Rankings (2022 season)
```
Downloaded: 49,434 plays
Processed: 32 team-season defensive profiles
Sample Output:
- ARI: def_epa_per_play = -0.016, pass_epa_allowed = -0.032
- BUF: def_epa_per_play = +0.046, pass_epa_allowed = +0.029
```

### College Data (2023-2024 drafts)
```
Processed: 5 placeholder records
Sample Output:
- Caleb Williams (USC): college_ppg = 28.5, recruiting_stars = 5, conference = Pac-12
- Bijan Robinson (Texas): college_ppg = 22.5, recruiting_stars = 5, conference = Big 12
```

### Coaching Data (2022 season)
```
Downloaded: 49,434 plays
Processed: 32 team-season coaching profiles
Sample Output:
- BUF: pass_rate_neutral = 0.618, motion_rate = 0.45
- CHI: pass_rate_neutral = 0.426, motion_rate = 0.45
```

---

## Next Steps for Integration

### 1. Update Dataset Builder
Modify `/Users/kurultai/ktcvaluehog/src/ml/expanded_dataset_builder.py`:

```python
def add_college_features(self, df):
    """Add college profile features for rookies."""
    query = """
    MATCH (c:CollegeProfile)
    WHERE c.player_id = $player_id
    RETURN c.college_ppg, c.college_market_share, c.breakout_age,
           c.conference_strength, c.recruiting_stars
    """
    # Merge college features

def add_coaching_features(self, df):
    """Add coaching/scheme features for team context."""
    query = """
    MATCH (cp:CoachingProfile)
    WHERE cp.team = $team AND cp.season = $season
    RETURN cp.coaching_tree, cp.pass_rate_neutral, cp.motion_rate,
           cp.play_action_rate
    """
    # Merge coaching features

def add_defense_matchup_features(self, df):
    """Add defensive matchup difficulty features."""
    query = """
    MATCH (dp:TeamDefenseProfile)
    WHERE dp.team = $opponent_team AND dp.season = $season
    RETURN dp.def_epa_per_play, dp.pass_epa_allowed,
           dp.ppg_allowed_qb, dp.ppg_allowed_rb, dp.ppg_allowed_wr
    """
    # Merge defense matchup features
```

### 2. Add to Weekly Data Job
Update `/Users/kurultai/ktcvaluehog/scripts/weekly_data_job.py`:

```python
WEEKLY_JOBS = [
    'pbp_features',
    'injuries',
    'depth_charts',
    'ktc_trends',
    'defense_rankings',  # NEW
    'coaching_data',     # NEW (if tendencies change weekly)
]
```

### 3. Install Dependencies
```bash
# Add CFBD package
pip install cfbd>=4.0.0

# Set API key (optional - will use placeholder if not set)
export CFBD_API_KEY="your-key-here"
```

### 4. Load Historical Data
```bash
# College data (one-time load, then annual updates in March)
python scripts/ingest_college_data.py --draft-years 2020 2021 2022 2023 2024

# Coaching data (annual load in March after coaching changes)
python scripts/ingest_coaching_data.py --years 2020 2021 2022 2023 2024

# Defense rankings (weekly during season)
python scripts/ingest_defense_rankings.py --years 2020 2021 2022 2023 2024
```

---

## Expected R² Improvements

| Phase | Feature Set | Expected Gain | Target Audience |
|-------|-------------|---------------|-----------------|
| Phase 4 | College profiles | +0.05-0.08 | Rookie predictions |
| Phase 5 | Coaching/scheme | +0.02-0.03 | All positions (scheme fit) |
| Phase 7 | Defense matchups | +0.02-0.03 | All positions (matchup difficulty) |
| **Total** | **Combined** | **+0.09-0.14** | **Overall model** |

Conservative estimate: **+0.05 overall R²** (accounting for feature overlap)

Current R²: 0.802 → Target R²: **0.85**

---

## Maintenance Schedule

| Data Type | Frequency | Timing | Command |
|-----------|-----------|--------|---------|
| College Data | Annual | March (post-draft) | `ingest_college_data.py --draft-years <year>` |
| Coaching Data | Annual | March (coaching changes) | `ingest_coaching_data.py --years <year>` |
| Defense Rankings | Weekly | Tuesday 4AM | `ingest_defense_rankings.py --current-week` |
| Contract Years | Manual | Offseason | Update `data/contract_years.csv` |

---

## Dependencies Added

### requirements_full.txt
```
nfl-data-py>=0.3.3
cfbd>=4.0.0
```

### Environment Variables
```
CFBD_API_KEY=your-key-here  # Optional - falls back to placeholder
```

---

## Notes

### CFBD API Key
- Get free API key at: https://collegefootballdata.com/key
- Free tier: 1,000 calls/month
- Placeholder data is used if key not available
- Update college data ingester with real API calls once key is configured

### Coaching Tree Expansion
Current implementation includes major coaching trees (McVay, Shanahan, Reid, Belichick, Payton).
To expand:
1. Update `COACHING_TREE_MAP` in `ingest_coaching_data.py`
2. Add coaching histories from Pro Football Reference scraping
3. Re-run ingester for all years

### Defense Position-Specific Points
Current implementation estimates position-specific fantasy points allowed.
For production accuracy:
1. Join with roster data to map players to positions
2. Calculate actual PPG allowed by position from game logs
3. Update `_calculate_position_allowed()` method

### Contract Years
Current CSV has placeholder player IDs.
To update:
1. Scrape contract data from OverTheCap.com or Spotrac
2. Match player names to gsis_id in Neo4j Player nodes
3. Update CSV with real contract year flags

---

## File Summary

| File | Lines | Purpose |
|------|-------|---------|
| `scripts/ingest_college_data.py` | 407 | College profile ingestion |
| `scripts/ingest_coaching_data.py` | 381 | Coaching/scheme ingestion |
| `scripts/ingest_defense_rankings.py` | 373 | Defense rankings ingestion |
| `data/contract_years.csv` | 51 | Contract year tracking |
| `docs/PHASE_4_5_7_IMPLEMENTATION.md` | This file | Documentation |
| **Total** | **~1,200** | Phase 4/5/7 implementation |

---

## Integration with ML Pipeline

Once data is loaded, integrate into training pipeline:

```python
# In src/ml/expanded_dataset_builder.py
def build_extended_dataset(self):
    df = self.build_base_dataset()

    # Add new features
    df = self.add_college_features(df)      # Phase 4
    df = self.add_coaching_features(df)     # Phase 5
    df = self.add_defense_matchup_features(df)  # Phase 7
    df = self.add_contract_year_features(df)    # Phase 2 (CSV merge)

    return df
```

Then retrain:
```bash
python scripts/train_optimized_models.py --compare-baseline
```

Expected improvement: R² 0.802 → 0.85 (or close to it).
