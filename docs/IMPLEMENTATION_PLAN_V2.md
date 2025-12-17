# Dynasty Edge: Implementation Plan v2.0

## Overview

This plan integrates all 28 NFLverse datasets with Sleeper and KTC data into a hybrid Neo4j + Parquet architecture optimized for ML and AI agent interactions.

---

## Phase 0: Foundation Setup (Days 1-2)

### 0.1 Environment Setup

```bash
# Install Neo4j
brew install neo4j  # or Docker: docker run neo4j

# Python dependencies
pip install neo4j py2neo nflreadpy polars pyarrow
pip install ai-data-science-team h2o langchain anthropic
pip install pandas numpy scikit-learn
```

### 0.2 Directory Structure

```
ktcvaluehog/
├── data/
│   ├── raw/                      # Downloaded data cache
│   │   ├── nflverse/
│   │   ├── sleeper/
│   │   └── ktc/
│   ├── features/                 # ML feature store (Parquet)
│   │   ├── player_features.parquet
│   │   ├── weekly_stats.parquet
│   │   ├── ftn_aggregates.parquet
│   │   └── training_data.parquet
│   └── models/                   # Trained models
├── src/
│   ├── database/
│   │   ├── __init__.py
│   │   ├── neo4j_client.py       # Connection management
│   │   ├── schema.py             # Cypher schema
│   │   └── queries.py            # Common queries
│   ├── loaders/
│   │   ├── __init__.py
│   │   ├── base_loader.py        # Abstract base
│   │   ├── nflverse_loader.py    # All 28 datasets
│   │   ├── sleeper_loader.py     # Sleeper API
│   │   ├── ktc_loader.py         # KTC scraping
│   │   └── espn_loader.py        # ESPN QBR (direct)
│   ├── features/
│   │   ├── __init__.py
│   │   ├── graph_features.py     # Neo4j-derived features
│   │   ├── stat_aggregates.py    # Statistical aggregations
│   │   ├── ftn_features.py       # FTN charting features
│   │   └── feature_store.py      # Parquet management
│   ├── ml/
│   │   ├── __init__.py
│   │   ├── agents.py             # AI Data Science Team
│   │   ├── train.py              # Model training
│   │   ├── predict.py            # Inference
│   │   └── signals.py            # Buy/Sell generation
│   └── api/
│       ├── __init__.py
│       └── sleeper_client.py     # Sleeper API wrapper
├── pipelines/
│   ├── initial_load.py           # First-time data load
│   ├── daily_refresh.py          # Daily updates
│   └── weekly_ml.py              # Weekly model retrain
├── dashboard.py
└── requirements.txt
```

### 0.3 Configuration

```python
# config.py
from pathlib import Path

# Neo4j
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "your-password"

# Paths
DATA_DIR = Path("data")
RAW_DIR = DATA_DIR / "raw"
FEATURES_DIR = DATA_DIR / "features"
MODELS_DIR = DATA_DIR / "models"

# NFLverse settings
HISTORICAL_SEASONS = range(2020, 2026)  # 6 seasons
CURRENT_SEASON = 2025

# Sleeper
SLEEPER_LEAGUE_ID = "your-league-id"
```

---

## Phase 1: Data Ingestion Infrastructure (Days 3-5)

### 1.1 NFLverse Loader

```python
# src/loaders/nflverse_loader.py

import nflreadpy as nfl
import polars as pl
from pathlib import Path
from typing import List, Optional
import ssl

class NFLverseLoader:
    """Load all 28 NFLverse datasets."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        # Bypass SSL for direct downloads
        ssl._create_default_https_context = ssl._create_unverified_context

    # === CORE PLAYER DATA ===

    def load_players(self) -> pl.DataFrame:
        """Master player database with all IDs."""
        return nfl.load_players()

    def load_ff_playerids(self) -> pl.DataFrame:
        """Cross-platform ID mapping (gsis, sleeper, espn, etc.)."""
        return nfl.load_ff_playerids()

    def load_rosters(self, seasons: List[int]) -> pl.DataFrame:
        """Current season rosters."""
        return nfl.load_rosters(seasons)

    def load_rosters_weekly(self, seasons: List[int]) -> pl.DataFrame:
        """Weekly roster snapshots."""
        return nfl.load_rosters_weekly(seasons)

    # === STATISTICS ===

    def load_player_stats(self, seasons: List[int]) -> pl.DataFrame:
        """Weekly player statistics (114 columns)."""
        return nfl.load_player_stats(seasons, summary_level='week')

    def load_team_stats(self, seasons: List[int]) -> pl.DataFrame:
        """Team-level aggregates (102 columns)."""
        return nfl.load_team_stats(seasons)

    # === ADVANCED ANALYTICS ===

    def load_nextgen_stats(self, seasons: List[int]) -> dict:
        """NextGen stats for passing, receiving, rushing."""
        return {
            'passing': nfl.load_nextgen_stats(seasons, stat_type='passing'),
            'receiving': nfl.load_nextgen_stats(seasons, stat_type='receiving'),
            'rushing': nfl.load_nextgen_stats(seasons, stat_type='rushing')
        }

    def load_pfr_advstats(self, seasons: List[int]) -> dict:
        """PFR advanced stats for pass, rush, rec, def."""
        return {
            'pass': nfl.load_pfr_advstats(seasons, stat_type='pass'),
            'rush': nfl.load_pfr_advstats(seasons, stat_type='rush'),
            'rec': nfl.load_pfr_advstats(seasons, stat_type='rec'),
            'def': nfl.load_pfr_advstats(seasons, stat_type='def')
        }

    def load_ftn_charting(self, seasons: List[int]) -> pl.DataFrame:
        """FTN play charting data (29 columns)."""
        return nfl.load_ftn_charting(seasons)

    def load_ff_opportunity(self, seasons: List[int]) -> pl.DataFrame:
        """Fantasy opportunity metrics (159 columns)."""
        return nfl.load_ff_opportunity(seasons)

    # === CONTEXT DATA ===

    def load_teams(self) -> pl.DataFrame:
        """NFL teams metadata."""
        return nfl.load_teams()

    def load_schedules(self, seasons: List[int]) -> pl.DataFrame:
        """Game schedules with results."""
        return nfl.load_schedules(seasons)

    def load_snap_counts(self, seasons: List[int]) -> pl.DataFrame:
        """Player snap counts."""
        return nfl.load_snap_counts(seasons)

    def load_depth_charts(self, seasons: List[int]) -> pl.DataFrame:
        """Team depth charts."""
        return nfl.load_depth_charts(seasons)

    # === HISTORICAL DATA ===

    def load_draft_picks(self) -> pl.DataFrame:
        """Historical draft picks."""
        return nfl.load_draft_picks()

    def load_combine(self) -> pl.DataFrame:
        """NFL Combine results."""
        return nfl.load_combine()

    def load_contracts(self) -> pl.DataFrame:
        """Player contracts."""
        return nfl.load_contracts()

    def load_trades(self) -> pl.DataFrame:
        """NFL trades history."""
        return nfl.load_trades()

    # === PLAY-BY-PLAY (Optional - Heavy) ===

    def load_pbp(self, seasons: List[int]) -> pl.DataFrame:
        """Play-by-play data (372 columns)."""
        return nfl.load_pbp(seasons)

    # === FANTASY ===

    def load_ff_rankings(self) -> pl.DataFrame:
        """Expert consensus rankings."""
        return nfl.load_ff_rankings()

    # === ESPN DATA (Direct Download) ===

    def load_espn_qbr(self) -> dict:
        """ESPN QBR data (not in nflreadpy)."""
        import pandas as pd
        base_url = "https://github.com/nflverse/nflverse-data/releases/download/espn_data"
        return {
            'season': pd.read_parquet(f"{base_url}/qbr_season_level.parquet"),
            'week': pd.read_parquet(f"{base_url}/qbr_week_level.parquet")
        }

    # === MISC ===

    def load_officials(self, seasons: List[int]) -> pl.DataFrame:
        """Game officials."""
        return nfl.load_officials(seasons)
```

### 1.2 ID Resolution System

```python
# src/loaders/id_resolver.py

import polars as pl
from typing import Optional

class IDResolver:
    """Resolve player IDs across platforms."""

    def __init__(self, playerids_df: pl.DataFrame):
        self.mapping = playerids_df.to_pandas().set_index('gsis_id')

    def gsis_to_sleeper(self, gsis_id: str) -> Optional[str]:
        try:
            return self.mapping.loc[gsis_id, 'sleeper_id']
        except KeyError:
            return None

    def sleeper_to_gsis(self, sleeper_id: str) -> Optional[str]:
        match = self.mapping[self.mapping['sleeper_id'] == sleeper_id]
        return match.index[0] if len(match) > 0 else None

    def get_all_ids(self, gsis_id: str) -> dict:
        try:
            row = self.mapping.loc[gsis_id]
            return {
                'gsis_id': gsis_id,
                'sleeper_id': row.get('sleeper_id'),
                'espn_id': row.get('espn_id'),
                'pfr_id': row.get('pfr_id'),
                'pff_id': row.get('pff_id'),
                'yahoo_id': row.get('yahoo_id')
            }
        except KeyError:
            return {'gsis_id': gsis_id}
```

---

## Phase 2: Neo4j Schema & Core Nodes (Days 6-8)

### 2.1 Schema Creation

```python
# src/database/schema.py

SCHEMA_QUERIES = [
    # Constraints
    "CREATE CONSTRAINT player_gsis IF NOT EXISTS FOR (p:Player) REQUIRE p.gsis_id IS UNIQUE",
    "CREATE CONSTRAINT team_abbr IF NOT EXISTS FOR (t:Team) REQUIRE t.team_abbr IS UNIQUE",
    "CREATE CONSTRAINT game_id IF NOT EXISTS FOR (g:Game) REQUIRE g.game_id IS UNIQUE",
    "CREATE CONSTRAINT player_season IF NOT EXISTS FOR (ps:PlayerSeason) REQUIRE ps.id IS UNIQUE",
    "CREATE CONSTRAINT team_season IF NOT EXISTS FOR (ts:TeamSeason) REQUIRE ts.id IS UNIQUE",
    "CREATE CONSTRAINT fantasy_league IF NOT EXISTS FOR (fl:FantasyLeague) REQUIRE fl.league_id IS UNIQUE",
    "CREATE CONSTRAINT fantasy_team IF NOT EXISTS FOR (ft:FantasyTeam) REQUIRE ft.roster_id IS UNIQUE",

    # Indexes
    "CREATE INDEX player_position IF NOT EXISTS FOR (p:Player) ON (p.position)",
    "CREATE INDEX player_team IF NOT EXISTS FOR (p:Player) ON (p.current_team)",
    "CREATE INDEX player_ktc IF NOT EXISTS FOR (p:Player) ON (p.ktc_value_sf)",
    "CREATE INDEX player_edge IF NOT EXISTS FOR (p:Player) ON (p.edge_signal)",
    "CREATE INDEX player_name IF NOT EXISTS FOR (p:Player) ON (p.name)",
]

def create_schema(driver):
    with driver.session() as session:
        for query in SCHEMA_QUERIES:
            try:
                session.run(query)
            except Exception as e:
                print(f"Schema warning: {e}")
```

### 2.2 Node Loaders

```python
# src/database/neo4j_loader.py

from neo4j import GraphDatabase
import pandas as pd
from datetime import datetime

class Neo4jLoader:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def load_players(self, players_df: pd.DataFrame, combine_df: pd.DataFrame,
                     draft_df: pd.DataFrame, contracts_df: pd.DataFrame):
        """Load Player nodes with all attributes."""

        # Merge data sources
        merged = players_df.merge(
            combine_df[['pfr_id', 'forty', 'bench', 'vertical', 'broad_jump', 'three_cone']],
            on='pfr_id', how='left'
        ).merge(
            draft_df[['gsis_id', 'round', 'pick', 'season']].rename(
                columns={'round': 'draft_round', 'pick': 'draft_pick', 'season': 'draft_year'}
            ),
            on='gsis_id', how='left'
        )

        with self.driver.session() as session:
            for _, row in merged.iterrows():
                if pd.isna(row.get('gsis_id')):
                    continue

                session.run("""
                    MERGE (p:Player {gsis_id: $gsis_id})
                    SET p.name = $name,
                        p.display_name = $display_name,
                        p.position = $position,
                        p.birth_date = date($birth_date),
                        p.height = $height,
                        p.weight = $weight,
                        p.college = $college,
                        p.draft_year = $draft_year,
                        p.draft_round = $draft_round,
                        p.draft_pick = $draft_pick,
                        p.forty_time = $forty_time,
                        p.bench_press = $bench_press,
                        p.vertical_jump = $vertical_jump,
                        p.broad_jump = $broad_jump,
                        p.three_cone = $three_cone,
                        p.updated_at = datetime()
                """, {
                    'gsis_id': row['gsis_id'],
                    'name': row.get('display_name', row.get('name')),
                    'display_name': row.get('display_name'),
                    'position': row.get('position'),
                    'birth_date': str(row['birth_date']) if pd.notna(row.get('birth_date')) else None,
                    'height': int(row['height']) if pd.notna(row.get('height')) else None,
                    'weight': int(row['weight']) if pd.notna(row.get('weight')) else None,
                    'college': row.get('college'),
                    'draft_year': int(row['draft_year']) if pd.notna(row.get('draft_year')) else None,
                    'draft_round': int(row['draft_round']) if pd.notna(row.get('draft_round')) else None,
                    'draft_pick': int(row['draft_pick']) if pd.notna(row.get('draft_pick')) else None,
                    'forty_time': float(row['forty']) if pd.notna(row.get('forty')) else None,
                    'bench_press': int(row['bench']) if pd.notna(row.get('bench')) else None,
                    'vertical_jump': float(row['vertical']) if pd.notna(row.get('vertical')) else None,
                    'broad_jump': int(row['broad_jump']) if pd.notna(row.get('broad_jump')) else None,
                    'three_cone': float(row['three_cone']) if pd.notna(row.get('three_cone')) else None
                })

    def load_player_seasons(self, stats_df: pd.DataFrame, ngs_df: dict,
                            pfr_df: dict, ftn_df: pd.DataFrame):
        """Load PlayerSeason nodes with aggregated stats."""
        # Aggregate weekly stats to season level
        # Include FTN charting aggregates
        # Include NextGen stats
        # Include PFR advanced stats
        pass  # Implementation details

    def create_targets_from_relationships(self, pbp_df: pd.DataFrame):
        """Create TARGETS_FROM relationships from play-by-play data."""
        # Aggregate QB -> WR/TE target connections
        targets = pbp_df[pbp_df['pass_attempt'] == 1].groupby(
            ['passer_player_id', 'receiver_player_id', 'season']
        ).agg({
            'play_id': 'count',
            'complete_pass': 'sum',
            'yards_gained': 'sum',
            'touchdown': 'sum',
            'epa': 'mean'
        }).reset_index()

        with self.driver.session() as session:
            for _, row in targets.iterrows():
                session.run("""
                    MATCH (qb:Player {gsis_id: $qb_id})
                    MATCH (rec:Player {gsis_id: $rec_id})
                    MERGE (rec)-[r:TARGETS_FROM]->(qb)
                    SET r.season = $season,
                        r.targets = $targets,
                        r.receptions = $receptions,
                        r.yards = $yards,
                        r.tds = $tds,
                        r.epa_per_target = $epa
                """, {
                    'qb_id': row['passer_player_id'],
                    'rec_id': row['receiver_player_id'],
                    'season': int(row['season']),
                    'targets': int(row['play_id']),
                    'receptions': int(row['complete_pass']),
                    'yards': int(row['yards_gained']),
                    'tds': int(row['touchdown']),
                    'epa': float(row['epa'])
                })
```

---

## Phase 3: Feature Engineering (Days 9-12)

### 3.1 FTN Charting Feature Aggregation

```python
# src/features/ftn_features.py

import polars as pl

def aggregate_ftn_features(ftn_df: pl.DataFrame, player_stats_df: pl.DataFrame) -> pl.DataFrame:
    """Aggregate FTN charting data to player-season level."""

    # Join FTN charting to player stats via play IDs
    # This requires joining on game_id + play_id

    # QB features
    qb_features = ftn_df.group_by(['passer_player_id', 'season']).agg([
        pl.col('is_play_action').mean().alias('play_action_rate'),
        pl.col('is_rpo').mean().alias('rpo_rate'),
        pl.col('is_screen_pass').mean().alias('screen_rate'),
        pl.col('is_qb_out_of_pocket').mean().alias('out_of_pocket_rate'),
        pl.col('is_throw_away').mean().alias('throwaway_rate'),
        pl.col('is_interception_worthy').mean().alias('int_worthy_rate'),
        pl.col('n_blitzers').mean().alias('avg_blitzers_faced'),
        pl.col('n_pass_rushers').mean().alias('avg_pass_rushers'),
    ])

    # Receiver features
    rec_features = ftn_df.group_by(['receiver_player_id', 'season']).agg([
        pl.col('is_catchable_ball').mean().alias('catchable_target_rate'),
        pl.col('is_contested_ball').mean().alias('contested_rate'),
        pl.col('is_drop').mean().alias('drop_rate_ftn'),
        pl.col('is_created_reception').mean().alias('created_reception_rate'),
    ])

    # RB features
    rb_features = ftn_df.filter(pl.col('is_rush') == True).group_by(
        ['rusher_player_id', 'season']
    ).agg([
        pl.col('n_defense_box').mean().alias('avg_box_defenders'),
    ])

    return {
        'qb': qb_features,
        'rec': rec_features,
        'rb': rb_features
    }
```

### 3.2 Graph Feature Extraction

```python
# src/features/graph_features.py

def extract_graph_features(driver) -> dict:
    """Extract ML features from Neo4j graph structure."""

    with driver.session() as session:
        # QB Quality Score for WR/TE
        qb_quality = session.run("""
            MATCH (rec:Player)-[t:TARGETS_FROM]->(qb:Player)
            WHERE rec.position IN ['WR', 'TE']
            WITH rec, qb, t,
                 qb.career_epa_per_play as qb_epa,
                 qb.age as qb_age,
                 CASE
                     WHEN qb.age < 26 THEN 1.1
                     WHEN qb.age > 32 THEN 0.9
                     ELSE 1.0
                 END as qb_age_factor
            RETURN rec.gsis_id as player_id,
                   qb.name as qb_name,
                   qb_epa,
                   qb_age,
                   qb_age_factor,
                   t.target_share as target_share
        """).data()

        # Competition Index
        competition = session.run("""
            MATCH (p:Player)-[c:COMPETES_WITH]-(comp:Player)
            WHERE p.position IN ['RB', 'WR', 'TE']
            WITH p, count(comp) as num_competitors,
                 avg(comp.ktc_value_sf) as avg_comp_value,
                 sum(comp.ktc_value_sf) as total_comp_value
            RETURN p.gsis_id as player_id,
                   num_competitors,
                   avg_comp_value,
                   total_comp_value,
                   p.ktc_value_sf / (p.ktc_value_sf + total_comp_value) as value_share
        """).data()

        # Team Offensive Environment
        team_context = session.run("""
            MATCH (p:Player)-[:PLAYS_FOR]->(t:Team)
            MATCH (t)<-[:HAD_SEASON]-(ts:TeamSeason {season: 2025})
            RETURN p.gsis_id as player_id,
                   ts.pass_rate,
                   ts.plays_per_game,
                   ts.team_pass_epa,
                   ts.play_action_rate as team_pa_rate
        """).data()

        return {
            'qb_quality': pd.DataFrame(qb_quality),
            'competition': pd.DataFrame(competition),
            'team_context': pd.DataFrame(team_context)
        }
```

### 3.3 Feature Store Builder

```python
# src/features/feature_store.py

import polars as pl
from pathlib import Path

class FeatureStore:
    """Manage ML feature storage in Parquet format."""

    def __init__(self, features_dir: Path):
        self.features_dir = features_dir
        self.features_dir.mkdir(parents=True, exist_ok=True)

    def build_training_dataset(self,
                                player_stats: pl.DataFrame,
                                ftn_features: dict,
                                ngs_features: dict,
                                graph_features: dict,
                                ktc_values: pl.DataFrame) -> pl.DataFrame:
        """Build ML-ready training dataset."""

        # Start with player stats
        df = player_stats

        # Join FTN features
        df = df.join(ftn_features['qb'], on=['player_id', 'season'], how='left')
        df = df.join(ftn_features['rec'], on=['player_id', 'season'], how='left')
        df = df.join(ftn_features['rb'], on=['player_id', 'season'], how='left')

        # Join NextGen features
        for stat_type, ngs_df in ngs_features.items():
            df = df.join(ngs_df, on=['player_id', 'season'], how='left', suffix=f'_ngs_{stat_type}')

        # Join graph features
        df = df.join(pl.from_pandas(graph_features['qb_quality']), on='player_id', how='left')
        df = df.join(pl.from_pandas(graph_features['competition']), on='player_id', how='left')
        df = df.join(pl.from_pandas(graph_features['team_context']), on='player_id', how='left')

        # Join KTC target variable
        df = df.join(ktc_values, on='player_id', how='inner')

        return df

    def save(self, df: pl.DataFrame, name: str):
        path = self.features_dir / f"{name}.parquet"
        df.write_parquet(path)
        print(f"Saved {len(df)} rows to {path}")

    def load(self, name: str) -> pl.DataFrame:
        path = self.features_dir / f"{name}.parquet"
        return pl.read_parquet(path)
```

---

## Phase 4: ML Pipeline with AI Data Science Team (Days 13-17)

### 4.1 Agent Configuration

```python
# src/ml/agents.py

from ai_data_science_team.agents import (
    DataLoaderToolsAgent,
    FeatureEngineeringAgent,
    EDAToolsAgent
)
from ai_data_science_team.ml_agents import H2OMLAgent

class DynastyMLAgents:
    """AI Data Science Team agents for dynasty analysis."""

    def __init__(self, openai_api_key: str):
        self.data_loader = DataLoaderToolsAgent(api_key=openai_api_key)
        self.feature_eng = FeatureEngineeringAgent(api_key=openai_api_key)
        self.eda = EDAToolsAgent(api_key=openai_api_key)
        self.h2o_ml = H2OMLAgent(api_key=openai_api_key)

    def discover_correlations(self, df, target='ktc_value_sf'):
        """Use EDA agent to find what drives KTC values."""
        return self.eda.invoke(f"""
            Analyze this dynasty fantasy football dataset.
            Target variable: {target}

            Tasks:
            1. Calculate correlations with target for all numeric features
            2. Identify top 20 most predictive features
            3. Check for multicollinearity (features correlated >0.8 with each other)
            4. Generate correlation heatmap for top features
            5. Identify any surprising correlations

            Focus on features that would help predict player dynasty value.
        """, df)

    def engineer_features(self, df):
        """Use Feature Engineering agent to create ML-ready features."""
        return self.feature_eng.invoke(f"""
            Engineer features for predicting dynasty fantasy football value.

            Create these feature types:
            1. Age curves by position (RB peaks early, QB/WR later)
            2. Interaction features (age * production, draft_capital * production)
            3. Efficiency metrics (fantasy_points / opportunities)
            4. Rolling averages (if weekly data available)
            5. Rank-based features within position groups
            6. Polynomial features for non-linear relationships

            Handle missing values appropriately.
            Return the transformed dataframe.
        """, df)

    def train_ktc_model(self, df, target='ktc_value_sf', max_runtime_secs=1800):
        """Use H2O agent to train KTC prediction models."""
        return self.h2o_ml.invoke(f"""
            Train regression models to predict {target}.

            Requirements:
            - Use all available features
            - Max runtime: {max_runtime_secs} seconds
            - Try multiple algorithms (GBM, XGBoost, Deep Learning, Stacked Ensemble)
            - Use 5-fold cross-validation
            - Return top 5 models with performance metrics
            - Return feature importance from best model

            The target is dynasty fantasy football value (higher = more valuable player).
        """, df)
```

### 4.2 Training Pipeline

```python
# src/ml/train.py

import h2o
from h2o.automl import H2OAutoML
import pandas as pd

def train_ktc_model(training_df: pd.DataFrame,
                    target: str = 'ktc_value_sf',
                    max_runtime_secs: int = 3600):
    """Train H2O AutoML model for KTC prediction."""

    # Initialize H2O
    h2o.init()

    # Convert to H2O frame
    hf = h2o.H2OFrame(training_df)

    # Set target and features
    y = target
    x = [col for col in hf.columns if col not in [y, 'player_id', 'name', 'gsis_id']]

    # Split data
    train, valid, test = hf.split_frame(ratios=[0.7, 0.15], seed=42)

    # Run AutoML
    aml = H2OAutoML(
        max_runtime_secs=max_runtime_secs,
        max_models=50,
        seed=42,
        sort_metric='RMSE',
        exclude_algos=['DeepLearning'],  # Optional: exclude slow algos
        nfolds=5
    )

    aml.train(x=x, y=y, training_frame=train, validation_frame=valid)

    # Get leaderboard
    lb = aml.leaderboard.as_data_frame()
    print("Top 5 Models:")
    print(lb.head(5))

    # Get best model
    best = aml.leader

    # Feature importance
    if hasattr(best, 'varimp'):
        importance = best.varimp(use_pandas=True)
        print("\nTop 20 Features:")
        print(importance.head(20))

    # Test performance
    perf = best.model_performance(test)
    print(f"\nTest RMSE: {perf.rmse()}")
    print(f"Test R²: {perf.r2()}")

    # Save model
    model_path = h2o.save_model(best, path='data/models', force=True)
    print(f"Model saved to: {model_path}")

    return best, lb, importance
```

---

## Phase 5: Prediction & Signals (Days 18-20)

### 5.1 Generate Predictions

```python
# src/ml/predict.py

def generate_predictions(model, features_df: pd.DataFrame) -> pd.DataFrame:
    """Generate KTC predictions for all players."""

    hf = h2o.H2OFrame(features_df)
    predictions = model.predict(hf).as_data_frame()

    results = features_df[['gsis_id', 'name', 'position', 'ktc_value_sf']].copy()
    results['predicted_ktc'] = predictions['predict']
    results['value_delta'] = results['predicted_ktc'] - results['ktc_value_sf']
    results['delta_pct'] = (results['value_delta'] / results['ktc_value_sf'] * 100).round(1)

    return results
```

### 5.2 Generate Buy/Sell Signals

```python
# src/ml/signals.py

def generate_signals(predictions_df: pd.DataFrame) -> pd.DataFrame:
    """Generate buy/sell signals based on predictions."""

    df = predictions_df.copy()

    # Signal thresholds
    df['edge_signal'] = df['delta_pct'].apply(lambda x:
        'STRONG_BUY' if x > 20 else
        'BUY' if x > 10 else
        'STRONG_SELL' if x < -20 else
        'SELL' if x < -10 else
        'HOLD'
    )

    # Confidence based on prediction stability (would need ensemble)
    df['confidence'] = abs(df['delta_pct']).clip(0, 100) / 100

    return df

def update_neo4j_predictions(driver, signals_df: pd.DataFrame):
    """Update Player nodes with ML predictions."""

    with driver.session() as session:
        for _, row in signals_df.iterrows():
            session.run("""
                MATCH (p:Player {gsis_id: $gsis_id})
                SET p.predicted_ktc_value = $predicted,
                    p.value_delta = $delta,
                    p.value_delta_pct = $delta_pct,
                    p.edge_signal = $signal,
                    p.confidence_score = $confidence,
                    p.prediction_updated = datetime()
            """, {
                'gsis_id': row['gsis_id'],
                'predicted': int(row['predicted_ktc']),
                'delta': int(row['value_delta']),
                'delta_pct': float(row['delta_pct']),
                'signal': row['edge_signal'],
                'confidence': float(row['confidence'])
            })
```

---

## Phase 6: Sleeper & Dashboard Integration (Days 21-25)

### 6.1 Sleeper API Integration

```python
# src/api/sleeper_client.py

import requests
from typing import List, Dict

class SleeperClient:
    BASE_URL = "https://api.sleeper.app/v1"

    def __init__(self, league_id: str):
        self.league_id = league_id

    def get_league(self) -> Dict:
        return requests.get(f"{self.BASE_URL}/league/{self.league_id}").json()

    def get_rosters(self) -> List[Dict]:
        return requests.get(f"{self.BASE_URL}/league/{self.league_id}/rosters").json()

    def get_users(self) -> List[Dict]:
        return requests.get(f"{self.BASE_URL}/league/{self.league_id}/users").json()

    def get_transactions(self, week: int) -> List[Dict]:
        return requests.get(
            f"{self.BASE_URL}/league/{self.league_id}/transactions/{week}"
        ).json()

    def get_drafts(self) -> List[Dict]:
        return requests.get(f"{self.BASE_URL}/league/{self.league_id}/drafts").json()
```

### 6.2 Dashboard Updates

Update dashboard.py to query Neo4j for ML-enhanced features:
- Buy/Sell signals page
- Player comparison with graph context
- Trade analyzer with predicted values
- AI chat with graph-aware responses

---

## Timeline Summary

| Phase | Days | Deliverables |
|-------|------|--------------|
| **0. Foundation** | 1-2 | Environment, directory structure, config |
| **1. Data Ingestion** | 3-5 | NFLverse loader (28 datasets), ID resolver |
| **2. Neo4j Schema** | 6-8 | Schema, Player/Team/Season nodes |
| **3. Feature Engineering** | 9-12 | FTN features, graph features, feature store |
| **4. ML Pipeline** | 13-17 | AI agents, H2O training, model artifacts |
| **5. Predictions** | 18-20 | Predictions, signals, Neo4j updates |
| **6. Integration** | 21-25 | Sleeper sync, dashboard updates, AI chat |

**Total: ~25 days**

---

## Success Metrics

1. **Data Coverage**: All 28 NFLverse datasets loaded and queryable
2. **Graph Features**: TARGETS_FROM, COMPETES_WITH relationships populated
3. **ML Performance**: KTC prediction R² > 0.7, RMSE < 1000
4. **Signal Accuracy**: 60%+ of BUY signals outperform market over 3 months
5. **Query Performance**: Graph queries < 100ms, feature generation < 5s
6. **Dashboard**: Real-time signals, trade analyzer with ML predictions
