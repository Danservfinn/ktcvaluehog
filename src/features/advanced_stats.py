"""
Advanced Stats Feature Engineering

Pulls and calculates advanced features from NFLverse:
- EPA (Expected Points Added)
- Snap share percentages
- Target share within team
- Air yards share
- Red zone opportunities
- CPOE, RYOE, and other efficiency metrics
"""

import pandas as pd
import numpy as np
import nfl_data_py as nfl
import logging
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AdvancedStatsLoader:
    """Load and calculate advanced stats from NFLverse."""

    CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "features"

    def __init__(self, seasons: List[int] = None):
        self.seasons = seasons or [2022, 2023, 2024, 2025]
        self.cache_dir = self.CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Data caches
        self._pbp_data = None
        self._player_stats = None
        self._snap_counts = None
        self._nextgen_receiving = None
        self._nextgen_rushing = None
        self._nextgen_passing = None
        self._roster_data = None

    def load_play_by_play(self, seasons: List[int] = None) -> pd.DataFrame:
        """Load play-by-play data with EPA."""
        seasons = seasons or self.seasons
        cache_file = self.cache_dir / f"pbp_{'_'.join(map(str, seasons))}.parquet"

        if cache_file.exists():
            logger.info(f"Loading cached PBP data from {cache_file}")
            return pd.read_parquet(cache_file)

        logger.info(f"Loading play-by-play data for {seasons}...")
        try:
            pbp = nfl.import_pbp_data(seasons, downcast=True)
            pbp.to_parquet(cache_file)
            logger.info(f"Loaded {len(pbp)} plays")
            return pbp
        except Exception as e:
            logger.error(f"Failed to load PBP data: {e}")
            return pd.DataFrame()

    def load_player_stats(self, seasons: List[int] = None) -> pd.DataFrame:
        """Load weekly player stats."""
        seasons = seasons or self.seasons
        cache_file = self.cache_dir / f"player_stats_{'_'.join(map(str, seasons))}.parquet"

        if cache_file.exists():
            logger.info(f"Loading cached player stats from {cache_file}")
            return pd.read_parquet(cache_file)

        logger.info(f"Loading player stats for {seasons}...")
        try:
            stats = nfl.import_weekly_data(seasons)
            stats.to_parquet(cache_file)
            logger.info(f"Loaded {len(stats)} weekly stat records")
            return stats
        except Exception as e:
            logger.error(f"Failed to load player stats: {e}")
            return pd.DataFrame()

    def load_snap_counts(self, seasons: List[int] = None) -> pd.DataFrame:
        """Load snap count data."""
        seasons = seasons or self.seasons
        cache_file = self.cache_dir / f"snaps_{'_'.join(map(str, seasons))}.parquet"

        if cache_file.exists():
            logger.info(f"Loading cached snap counts from {cache_file}")
            return pd.read_parquet(cache_file)

        logger.info(f"Loading snap counts for {seasons}...")
        try:
            snaps = nfl.import_snap_counts(seasons)
            snaps.to_parquet(cache_file)
            logger.info(f"Loaded {len(snaps)} snap records")
            return snaps
        except Exception as e:
            logger.error(f"Failed to load snap counts: {e}")
            return pd.DataFrame()

    def load_nextgen_stats(self, stat_type: str, seasons: List[int] = None) -> pd.DataFrame:
        """Load NextGen stats (receiving, rushing, or passing)."""
        seasons = seasons or self.seasons
        cache_file = self.cache_dir / f"nextgen_{stat_type}_{'_'.join(map(str, seasons))}.parquet"

        if cache_file.exists():
            logger.info(f"Loading cached NextGen {stat_type} from {cache_file}")
            return pd.read_parquet(cache_file)

        logger.info(f"Loading NextGen {stat_type} stats for {seasons}...")
        try:
            ngs = nfl.import_ngs_data(stat_type, seasons)
            ngs.to_parquet(cache_file)
            logger.info(f"Loaded {len(ngs)} NextGen records")
            return ngs
        except Exception as e:
            logger.error(f"Failed to load NextGen stats: {e}")
            return pd.DataFrame()

    def load_rosters(self, seasons: List[int] = None) -> pd.DataFrame:
        """Load roster data for player info."""
        seasons = seasons or self.seasons
        cache_file = self.cache_dir / f"rosters_{'_'.join(map(str, seasons))}.parquet"

        if cache_file.exists():
            logger.info(f"Loading cached rosters from {cache_file}")
            return pd.read_parquet(cache_file)

        logger.info(f"Loading rosters for {seasons}...")
        try:
            rosters = nfl.import_seasonal_rosters(seasons)
            rosters.to_parquet(cache_file)
            logger.info(f"Loaded {len(rosters)} roster entries")
            return rosters
        except Exception as e:
            logger.error(f"Failed to load rosters: {e}")
            return pd.DataFrame()


class FeatureEngineer:
    """Calculate advanced features for dynasty model."""

    def __init__(self, seasons: List[int] = None):
        self.loader = AdvancedStatsLoader(seasons)
        self.seasons = seasons or [2022, 2023, 2024, 2025]

    def calculate_epa_features(self) -> pd.DataFrame:
        """Calculate EPA-based features per player."""
        logger.info("Calculating EPA features...")

        pbp = self.loader.load_play_by_play()
        if pbp.empty:
            return pd.DataFrame()

        # Filter to skill position plays
        skill_plays = pbp[
            (pbp['play_type'].isin(['pass', 'run'])) &
            (pbp['epa'].notna())
        ].copy()

        # Receiving EPA
        receiving_epa = skill_plays[
            skill_plays['receiver_player_id'].notna()
        ].groupby(['receiver_player_id', 'season']).agg({
            'epa': ['sum', 'mean', 'count'],
            'yards_gained': 'sum',
            'air_yards': 'sum',
            'yards_after_catch': 'sum'
        }).reset_index()

        receiving_epa.columns = [
            'player_id', 'season', 'receiving_epa_total', 'receiving_epa_per_target',
            'targets', 'receiving_yards', 'total_air_yards', 'total_yac'
        ]

        # Rushing EPA
        rushing_epa = skill_plays[
            skill_plays['rusher_player_id'].notna()
        ].groupby(['rusher_player_id', 'season']).agg({
            'epa': ['sum', 'mean', 'count'],
            'yards_gained': 'sum',
            'rushing_yards': 'sum'
        }).reset_index()

        rushing_epa.columns = [
            'player_id', 'season', 'rushing_epa_total', 'rushing_epa_per_carry',
            'carries', 'rushing_yards_total', 'rushing_yards'
        ]

        # Merge
        epa_features = pd.merge(
            receiving_epa, rushing_epa,
            on=['player_id', 'season'],
            how='outer'
        )

        # Fill NaN with 0
        epa_features = epa_features.fillna(0)

        # Calculate combined metrics
        epa_features['total_epa'] = epa_features['receiving_epa_total'] + epa_features['rushing_epa_total']
        epa_features['total_touches'] = epa_features['targets'] + epa_features['carries']
        epa_features['epa_per_touch'] = np.where(
            epa_features['total_touches'] > 0,
            epa_features['total_epa'] / epa_features['total_touches'],
            0
        )

        logger.info(f"Calculated EPA features for {len(epa_features)} player-seasons")
        return epa_features

    def calculate_opportunity_share(self) -> pd.DataFrame:
        """Calculate target share and opportunity metrics."""
        logger.info("Calculating opportunity share features...")

        stats = self.loader.load_player_stats()
        if stats.empty:
            return pd.DataFrame()

        # Aggregate to season level
        season_stats = stats.groupby(['player_id', 'season']).agg({
            'targets': 'sum',
            'receptions': 'sum',
            'receiving_yards': 'sum',
            'receiving_tds': 'sum',
            'carries': 'sum',
            'rushing_yards': 'sum',
            'rushing_tds': 'sum',
            'fantasy_points_ppr': 'sum',
            'recent_team': 'last'  # Most recent team
        }).reset_index()

        # Calculate team totals for share calculations
        team_totals = stats.groupby(['recent_team', 'season']).agg({
            'targets': 'sum',
            'carries': 'sum',
            'receiving_yards': 'sum',
            'rushing_yards': 'sum'
        }).reset_index()

        team_totals.columns = ['team', 'season', 'team_targets', 'team_carries',
                               'team_receiving_yards', 'team_rushing_yards']

        # Merge
        season_stats = pd.merge(
            season_stats,
            team_totals,
            left_on=['recent_team', 'season'],
            right_on=['team', 'season'],
            how='left'
        )

        # Calculate shares
        season_stats['target_share'] = np.where(
            season_stats['team_targets'] > 0,
            season_stats['targets'] / season_stats['team_targets'],
            0
        )

        season_stats['carry_share'] = np.where(
            season_stats['team_carries'] > 0,
            season_stats['carries'] / season_stats['team_carries'],
            0
        )

        # WOPR (Weighted Opportunity Rating)
        season_stats['wopr'] = (season_stats['target_share'] * 1.5) + (season_stats['carry_share'] * 0.5)

        # Yards per opportunity
        season_stats['total_opportunities'] = season_stats['targets'] + season_stats['carries']
        season_stats['total_yards'] = season_stats['receiving_yards'] + season_stats['rushing_yards']
        season_stats['yards_per_opportunity'] = np.where(
            season_stats['total_opportunities'] > 0,
            season_stats['total_yards'] / season_stats['total_opportunities'],
            0
        )

        logger.info(f"Calculated opportunity features for {len(season_stats)} player-seasons")
        return season_stats

    def calculate_snap_features(self) -> pd.DataFrame:
        """Calculate snap share features."""
        logger.info("Calculating snap share features...")

        snaps = self.loader.load_snap_counts()
        if snaps.empty:
            return pd.DataFrame()

        # Aggregate to season level
        season_snaps = snaps.groupby(['player', 'season']).agg({
            'offense_snaps': 'sum',
            'offense_pct': 'mean',
            'defense_snaps': 'sum',
            'st_snaps': 'sum'
        }).reset_index()

        season_snaps.columns = ['player_name', 'season', 'total_offense_snaps',
                                'avg_snap_pct', 'total_defense_snaps', 'total_st_snaps']

        logger.info(f"Calculated snap features for {len(season_snaps)} player-seasons")
        return season_snaps

    def calculate_nextgen_features(self) -> pd.DataFrame:
        """Calculate NextGen advanced features."""
        logger.info("Calculating NextGen features...")

        # Receiving
        ngs_rec = self.loader.load_nextgen_stats('receiving')
        if not ngs_rec.empty:
            ngs_rec_agg = ngs_rec.groupby(['player_gsis_id', 'season']).agg({
                'avg_separation': 'mean',
                'avg_cushion': 'mean',
                'avg_intended_air_yards': 'mean',
                'avg_yac': 'mean',
                'catch_percentage': 'mean',
                'avg_yac_above_expectation': 'mean'
            }).reset_index()
            ngs_rec_agg.columns = ['player_id', 'season', 'ngs_separation', 'ngs_cushion',
                                   'ngs_air_yards', 'ngs_yac', 'ngs_catch_pct', 'ngs_yac_oe']

        # Rushing
        ngs_rush = self.loader.load_nextgen_stats('rushing')
        if not ngs_rush.empty:
            ngs_rush_agg = ngs_rush.groupby(['player_gsis_id', 'season']).agg({
                'efficiency': 'mean',
                'avg_rush_yards': 'mean',
                'rush_yards_over_expected_per_att': 'mean'
            }).reset_index()
            ngs_rush_agg.columns = ['player_id', 'season', 'ngs_rush_efficiency',
                                    'ngs_avg_rush_yards', 'ngs_ryoe']

        # Passing
        ngs_pass = self.loader.load_nextgen_stats('passing')
        if not ngs_pass.empty:
            ngs_pass_agg = ngs_pass.groupby(['player_gsis_id', 'season']).agg({
                'completion_percentage_above_expectation': 'mean',
                'avg_time_to_throw': 'mean',
                'avg_air_distance': 'mean',
                'passer_rating': 'mean'
            }).reset_index()
            ngs_pass_agg.columns = ['player_id', 'season', 'ngs_cpoe',
                                    'ngs_time_to_throw', 'ngs_air_distance', 'ngs_passer_rating']

        # Merge all NextGen features
        nextgen = ngs_rec_agg if not ngs_rec.empty else pd.DataFrame()

        if not ngs_rush.empty and not nextgen.empty:
            nextgen = pd.merge(nextgen, ngs_rush_agg, on=['player_id', 'season'], how='outer')
        elif not ngs_rush.empty:
            nextgen = ngs_rush_agg

        if not ngs_pass.empty and not nextgen.empty:
            nextgen = pd.merge(nextgen, ngs_pass_agg, on=['player_id', 'season'], how='outer')
        elif not ngs_pass.empty:
            nextgen = ngs_pass_agg

        logger.info(f"Calculated NextGen features for {len(nextgen)} player-seasons")
        return nextgen

    def build_feature_matrix(self, target_season: int = 2024) -> pd.DataFrame:
        """Build complete feature matrix for model training."""
        logger.info(f"Building feature matrix for season {target_season}...")

        # Get all features
        epa = self.calculate_epa_features()
        opportunity = self.calculate_opportunity_share()
        snaps = self.calculate_snap_features()
        nextgen = self.calculate_nextgen_features()

        # Filter to target season or aggregate recent seasons
        if not epa.empty:
            epa = epa[epa['season'] <= target_season]
            # Weight recent seasons more heavily
            epa['season_weight'] = epa['season'].apply(
                lambda x: 1.0 if x == target_season else 0.5 if x == target_season - 1 else 0.25
            )

        # Aggregate with weights
        # For now, just use the most recent season
        features = pd.DataFrame()

        if not epa.empty:
            features = epa[epa['season'] == target_season].copy()

        if not opportunity.empty:
            opp_recent = opportunity[opportunity['season'] == target_season]
            if not features.empty:
                features = pd.merge(features, opp_recent, on=['player_id', 'season'], how='outer')
            else:
                features = opp_recent.copy()

        if not nextgen.empty:
            ngs_recent = nextgen[nextgen['season'] == target_season]
            if not features.empty:
                features = pd.merge(features, ngs_recent, on=['player_id', 'season'], how='outer')

        logger.info(f"Built feature matrix with {len(features)} players and {len(features.columns)} features")
        return features

    def calculate_trajectory_features(self) -> pd.DataFrame:
        """Calculate year-over-year trend features for predicting value changes."""
        logger.info("Calculating trajectory features...")

        stats = self.loader.load_player_stats()
        if stats.empty:
            return pd.DataFrame()

        # Aggregate by player-season
        season_stats = stats.groupby(['player_id', 'player_name', 'season', 'position']).agg({
            'targets': 'sum',
            'receptions': 'sum',
            'receiving_yards': 'sum',
            'carries': 'sum',
            'rushing_yards': 'sum',
            'fantasy_points_ppr': 'sum'
        }).reset_index()

        # Sort by player and season
        season_stats = season_stats.sort_values(['player_id', 'season'])

        # Calculate YoY changes
        for col in ['targets', 'receptions', 'receiving_yards', 'carries', 'rushing_yards', 'fantasy_points_ppr']:
            season_stats[f'{col}_prev'] = season_stats.groupby('player_id')[col].shift(1)
            season_stats[f'{col}_change'] = season_stats[col] - season_stats[f'{col}_prev']
            season_stats[f'{col}_change_pct'] = np.where(
                season_stats[f'{col}_prev'] > 0,
                season_stats[f'{col}_change'] / season_stats[f'{col}_prev'],
                0
            )

        # Calculate breakout indicators
        season_stats['targets_trending_up'] = season_stats['targets_change'] > 20
        season_stats['fpts_trending_up'] = season_stats['fantasy_points_ppr_change'] > 30
        season_stats['breakout_score'] = (
            (season_stats['targets_change_pct'] > 0.2).astype(int) * 2 +
            (season_stats['fantasy_points_ppr_change_pct'] > 0.2).astype(int) * 2 +
            (season_stats['receiving_yards_change'] > 200).astype(int)
        )

        logger.info(f"Calculated trajectory features for {len(season_stats)} player-seasons")
        return season_stats


if __name__ == "__main__":
    # Test feature engineering
    engineer = FeatureEngineer(seasons=[2023, 2024])

    # Build feature matrix
    features = engineer.build_feature_matrix(target_season=2024)
    print(f"\nFeature matrix shape: {features.shape}")
    print(f"Columns: {features.columns.tolist()}")

    # Calculate trajectory features
    trajectory = engineer.calculate_trajectory_features()
    print(f"\nTrajectory features shape: {trajectory.shape}")

    # Show top breakout candidates
    if not trajectory.empty:
        breakouts = trajectory[trajectory['season'] == 2024].nlargest(10, 'breakout_score')
        print("\nTop breakout candidates (2024):")
        print(breakouts[['player_name', 'position', 'fantasy_points_ppr', 'targets_change', 'breakout_score']])
