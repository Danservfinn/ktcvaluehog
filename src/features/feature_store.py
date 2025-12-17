"""Feature store for ML training data.

Manages Parquet-based feature storage optimized for:
- Columnar storage for analytical queries
- Efficient compression
- Fast read times for ML training
- Schema versioning
"""

from pathlib import Path
from typing import List, Dict, Optional, Union
from datetime import datetime
import pandas as pd

try:
    import polars as pl
    POLARS_AVAILABLE = True
except ImportError:
    POLARS_AVAILABLE = False

from ..config import FEATURES_DIR


class FeatureStore:
    """Manage ML feature storage in Parquet format."""

    # Feature set definitions
    FEATURE_SETS = {
        'player_core': [
            'gsis_id', 'name', 'position', 'current_team', 'age',
            'draft_year', 'draft_round', 'draft_pick',
            'forty_time', 'bench_press', 'vertical_jump', 'broad_jump', 'three_cone',
            'height', 'weight'
        ],
        'seasonal_stats': [
            'gsis_id', 'season', 'games_played', 'fantasy_points_ppr', 'ppg',
            'targets', 'receptions', 'receiving_yards', 'receiving_tds',
            'carries', 'rushing_yards', 'rushing_tds',
            'passing_yards', 'passing_tds', 'interceptions',
            'snap_share', 'target_share'
        ],
        'advanced_metrics': [
            'gsis_id', 'season',
            # NextGen
            'avg_separation', 'avg_cushion', 'avg_yac', 'catch_pct', 'cpoe',
            'time_to_throw', 'aggressiveness', 'intended_air_yards',
            'rush_efficiency', 'time_to_los',
            # PFR
            'adot', 'ybc_per_r', 'yac_per_r', 'broken_tackles', 'drop_rate',
            'pressure_rate', 'on_target_pct', 'pocket_time'
        ],
        'ftn_features': [
            'gsis_id', 'season',
            'play_action_rate', 'rpo_rate', 'screen_rate',
            'out_of_pocket_rate', 'throwaway_rate', 'int_worthy_rate',
            'catchable_target_rate', 'contested_rate', 'drop_rate_ftn',
            'created_reception_rate', 'avg_box_defenders', 'avg_blitzers_faced'
        ],
        'graph_features': [
            'gsis_id',
            'qb_quality_score', 'qb_age', 'qb_epa',
            'competition_index', 'value_share', 'num_competitors',
            'team_pass_rate', 'team_plays_per_game', 'team_pass_epa'
        ],
        'valuation': [
            'gsis_id', 'date',
            'ktc_value_sf', 'ktc_value_1qb', 'predicted_ktc',
            'delta_pct', 'edge_signal', 'confidence_score'
        ],
        'chemistry': [
            'receiver_gsis_id', 'qb_gsis_id', 'season',
            'cqi_score', 'trust_score', 'pressure_target_rate',
            'red_zone_target_rate', 'contested_target_rate'
        ],
        'scheme_fit': [
            'gsis_id', 'team_abbr', 'season',
            'fit_score', 'ceiling_boost',
            'scheme_type', 'pass_rate', 'play_action_rate'
        ]
    }

    def __init__(self, features_dir: Path = None):
        self.features_dir = Path(features_dir or FEATURES_DIR)
        self.features_dir.mkdir(parents=True, exist_ok=True)
        self._metadata = {}

    def _get_path(self, name: str, version: str = None) -> Path:
        """Get path for a feature set."""
        if version:
            return self.features_dir / f"{name}_v{version}.parquet"
        return self.features_dir / f"{name}.parquet"

    # =========================================================================
    # Save Operations
    # =========================================================================

    def save(self, df: Union[pd.DataFrame, 'pl.DataFrame'], name: str,
             version: str = None, partition_cols: List[str] = None) -> Path:
        """Save a feature DataFrame to Parquet.

        Args:
            df: DataFrame to save (Pandas or Polars)
            name: Name of the feature set
            version: Optional version string
            partition_cols: Columns to partition by (for large datasets)

        Returns:
            Path to saved file
        """
        # Convert Polars to Pandas if needed
        if POLARS_AVAILABLE and isinstance(df, pl.DataFrame):
            df = df.to_pandas()

        path = self._get_path(name, version)

        if partition_cols:
            df.to_parquet(path, partition_cols=partition_cols, index=False)
        else:
            df.to_parquet(path, index=False)

        # Update metadata
        self._metadata[name] = {
            'path': str(path),
            'rows': len(df),
            'columns': len(df.columns),
            'saved_at': datetime.now().isoformat(),
            'version': version
        }

        print(f"Saved {len(df):,} rows to {path}")
        return path

    def save_training_data(self, df: pd.DataFrame, target_col: str = 'ktc_value_sf',
                           split_ratio: float = 0.8) -> Dict[str, Path]:
        """Save training data with train/test split.

        Args:
            df: Full training DataFrame
            target_col: Name of target column
            split_ratio: Fraction for training set

        Returns:
            Dict with paths to train and test sets
        """
        # Shuffle and split
        df = df.sample(frac=1, random_state=42).reset_index(drop=True)
        split_idx = int(len(df) * split_ratio)

        train_df = df.iloc[:split_idx]
        test_df = df.iloc[split_idx:]

        train_path = self.save(train_df, 'training_data_train')
        test_path = self.save(test_df, 'training_data_test')

        # Save full dataset too
        full_path = self.save(df, 'training_data_full')

        return {
            'train': train_path,
            'test': test_path,
            'full': full_path,
            'train_rows': len(train_df),
            'test_rows': len(test_df),
            'target_col': target_col
        }

    # =========================================================================
    # Load Operations
    # =========================================================================

    def load(self, name: str, version: str = None,
             columns: List[str] = None) -> pd.DataFrame:
        """Load a feature set from Parquet.

        Args:
            name: Name of the feature set
            version: Optional version string
            columns: Specific columns to load (for memory efficiency)

        Returns:
            DataFrame with features
        """
        path = self._get_path(name, version)

        if not path.exists():
            raise FileNotFoundError(f"Feature set not found: {path}")

        if columns:
            return pd.read_parquet(path, columns=columns)
        return pd.read_parquet(path)

    def load_polars(self, name: str, version: str = None,
                    columns: List[str] = None) -> 'pl.DataFrame':
        """Load a feature set as Polars DataFrame (faster for large data).

        Args:
            name: Name of the feature set
            version: Optional version string
            columns: Specific columns to load

        Returns:
            Polars DataFrame with features
        """
        if not POLARS_AVAILABLE:
            raise ImportError("Polars not available. Install with: pip install polars")

        path = self._get_path(name, version)

        if not path.exists():
            raise FileNotFoundError(f"Feature set not found: {path}")

        if columns:
            return pl.read_parquet(path, columns=columns)
        return pl.read_parquet(path)

    def load_training_data(self, split: str = 'train') -> pd.DataFrame:
        """Load training or test data.

        Args:
            split: 'train', 'test', or 'full'

        Returns:
            DataFrame with training data
        """
        return self.load(f'training_data_{split}')

    # =========================================================================
    # Feature Building
    # =========================================================================

    def build_training_dataset(self,
                               player_core: pd.DataFrame,
                               seasonal_stats: pd.DataFrame,
                               advanced_metrics: pd.DataFrame = None,
                               ftn_features: pd.DataFrame = None,
                               graph_features: pd.DataFrame = None,
                               ktc_values: pd.DataFrame = None) -> pd.DataFrame:
        """Build ML-ready training dataset by joining features.

        Args:
            player_core: Core player attributes
            seasonal_stats: Season-level statistics
            advanced_metrics: NextGen/PFR metrics (optional)
            ftn_features: FTN charting features (optional)
            graph_features: Graph-derived features (optional)
            ktc_values: Target variable (KTC values)

        Returns:
            Joined training DataFrame
        """
        # Start with seasonal stats (has player + season)
        df = seasonal_stats.copy()

        # Join player core attributes
        if player_core is not None and len(player_core) > 0:
            player_cols = [c for c in player_core.columns if c not in df.columns or c == 'gsis_id']
            df = df.merge(
                player_core[player_cols],
                on='gsis_id',
                how='left'
            )

        # Join advanced metrics
        if advanced_metrics is not None and len(advanced_metrics) > 0:
            adv_cols = [c for c in advanced_metrics.columns if c not in df.columns or c in ['gsis_id', 'season']]
            df = df.merge(
                advanced_metrics[adv_cols],
                on=['gsis_id', 'season'],
                how='left'
            )

        # Join FTN features
        if ftn_features is not None and len(ftn_features) > 0:
            ftn_cols = [c for c in ftn_features.columns if c not in df.columns or c in ['gsis_id', 'season']]
            df = df.merge(
                ftn_features[ftn_cols],
                on=['gsis_id', 'season'],
                how='left'
            )

        # Join graph features (no season, just player-level)
        if graph_features is not None and len(graph_features) > 0:
            graph_cols = [c for c in graph_features.columns if c not in df.columns or c == 'gsis_id']
            df = df.merge(
                graph_features[graph_cols],
                on='gsis_id',
                how='left'
            )

        # Join KTC target variable
        if ktc_values is not None and len(ktc_values) > 0:
            ktc_cols = ['gsis_id', 'ktc_value_sf', 'ktc_value_1qb']
            available_ktc_cols = [c for c in ktc_cols if c in ktc_values.columns]
            df = df.merge(
                ktc_values[available_ktc_cols],
                on='gsis_id',
                how='inner'  # Only keep players with KTC values
            )

        print(f"Built training dataset: {len(df):,} rows, {len(df.columns)} columns")
        return df

    # =========================================================================
    # Feature Engineering Utilities
    # =========================================================================

    def add_age_curve_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add position-specific age curve features.

        Calculates:
        - years_to_prime: Years until prime window
        - years_in_prime: Years of prime remaining
        - years_to_cliff: Years until steep decline
        - age_score: 0-1 score based on production curve
        """
        from ..config import POSITION_AGE_CURVES

        df = df.copy()

        def calculate_age_features(row):
            pos = row.get('position', 'WR')
            age = row.get('age', 25)

            if pos not in POSITION_AGE_CURVES:
                pos = 'WR'  # Default

            curve = POSITION_AGE_CURVES[pos]
            prime_start = curve['prime_start']
            prime_end = curve['prime_end']
            cliff = curve['cliff']

            years_to_prime = max(0, prime_start - age)
            years_in_prime = max(0, min(prime_end - age, prime_end - prime_start))
            years_to_cliff = max(0, cliff - age)

            # Age score (1.0 during prime, declining after)
            if age < prime_start:
                age_score = 0.7 + 0.3 * (age / prime_start)
            elif age <= prime_end:
                age_score = 1.0
            elif age < cliff:
                age_score = 1.0 - 0.5 * ((age - prime_end) / (cliff - prime_end))
            else:
                age_score = 0.5 * (1 - (age - cliff) / 5)  # Rapid decline after cliff

            return pd.Series({
                'years_to_prime': years_to_prime,
                'years_in_prime': years_in_prime,
                'years_to_cliff': years_to_cliff,
                'age_score': max(0, min(1, age_score))
            })

        age_features = df.apply(calculate_age_features, axis=1)
        return pd.concat([df, age_features], axis=1)

    def add_efficiency_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add efficiency ratio features."""
        df = df.copy()

        # Receiving efficiency
        if 'targets' in df.columns and 'receptions' in df.columns:
            df['catch_rate'] = df['receptions'] / df['targets'].replace(0, 1)
        if 'targets' in df.columns and 'receiving_yards' in df.columns:
            df['yards_per_target'] = df['receiving_yards'] / df['targets'].replace(0, 1)
        if 'receptions' in df.columns and 'receiving_yards' in df.columns:
            df['yards_per_reception'] = df['receiving_yards'] / df['receptions'].replace(0, 1)

        # Rushing efficiency
        if 'carries' in df.columns and 'rushing_yards' in df.columns:
            df['yards_per_carry'] = df['rushing_yards'] / df['carries'].replace(0, 1)

        # Fantasy efficiency
        if 'fantasy_points_ppr' in df.columns:
            if 'targets' in df.columns and 'carries' in df.columns:
                df['opportunities'] = df['targets'] + df['carries']
                df['pts_per_opportunity'] = df['fantasy_points_ppr'] / df['opportunities'].replace(0, 1)

        return df

    def add_rank_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add position-relative rank features."""
        df = df.copy()

        rank_cols = ['fantasy_points_ppr', 'targets', 'receiving_yards', 'rushing_yards', 'ppg']
        available_rank_cols = [c for c in rank_cols if c in df.columns]

        for col in available_rank_cols:
            df[f'{col}_pos_rank'] = df.groupby('position')[col].rank(ascending=False, method='min')
            df[f'{col}_pct'] = df.groupby('position')[col].rank(pct=True)

        return df

    # =========================================================================
    # Metadata and Info
    # =========================================================================

    def list_features(self) -> List[Dict]:
        """List all available feature sets."""
        feature_sets = []
        for path in self.features_dir.glob("*.parquet"):
            try:
                df = pd.read_parquet(path, columns=None)
                feature_sets.append({
                    'name': path.stem,
                    'path': str(path),
                    'rows': len(df),
                    'columns': len(df.columns),
                    'size_mb': path.stat().st_size / (1024 * 1024),
                    'modified': datetime.fromtimestamp(path.stat().st_mtime).isoformat()
                })
            except:
                feature_sets.append({
                    'name': path.stem,
                    'path': str(path),
                    'error': 'Could not read file'
                })

        return feature_sets

    def get_feature_info(self, name: str) -> Dict:
        """Get detailed info about a feature set."""
        path = self._get_path(name)

        if not path.exists():
            return {'error': f'Feature set not found: {name}'}

        df = pd.read_parquet(path)

        return {
            'name': name,
            'path': str(path),
            'rows': len(df),
            'columns': list(df.columns),
            'dtypes': df.dtypes.astype(str).to_dict(),
            'null_counts': df.isnull().sum().to_dict(),
            'memory_mb': df.memory_usage(deep=True).sum() / (1024 * 1024),
            'file_size_mb': path.stat().st_size / (1024 * 1024)
        }

    def delete(self, name: str, version: str = None) -> bool:
        """Delete a feature set file."""
        path = self._get_path(name, version)
        if path.exists():
            path.unlink()
            print(f"Deleted: {path}")
            return True
        return False
