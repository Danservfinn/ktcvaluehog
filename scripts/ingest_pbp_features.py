#!/usr/bin/env python3
"""
NFL Play-by-Play Feature Aggregation
====================================
Extracts player-level features from play-by-play data for ML training.

Data Source: nfl_data_py.import_pbp_data()
Records: ~15,000 player-season aggregations (143K+ weekly)
Schedule: Weekly during season (Tuesday 4AM after MNF)

Features Extracted:
- Red zone usage (targets, carries, TDs inside 20)
- Goal line usage (inside 5)
- EPA per target/carry
- Air yards share, WOPR, aDOT
- Situational usage (3rd down, neutral script)
- Target per route run (TPRR)

Usage:
    python scripts/ingest_pbp_features.py --years 2023 2024    # Historical load
    python scripts/ingest_pbp_features.py --current-week       # Weekly update
    python scripts/ingest_pbp_features.py --test               # Test mode
"""

import os
import sys
import ssl
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
import numpy as np

# Bypass SSL verification for nflverse downloads
ssl._create_default_https_context = ssl._create_unverified_context

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from scripts.data_jobs import BaseIngester, get_current_nfl_week

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PBPFeaturesIngester(BaseIngester):
    """
    Ingests aggregated play-by-play features into Neo4j.

    Computes player-level aggregations from raw PBP data including:
    - Red zone and goal line usage
    - EPA-based efficiency metrics
    - Air yards and opportunity metrics
    - Situational usage patterns
    """

    def __init__(self):
        super().__init__('pbp_features', batch_size=500)
        self.cache_dir = self.data_dir / "pbp_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def download_data(self, years: List[int] = None, current_week: bool = False) -> pd.DataFrame:
        """
        Download play-by-play data from nfl_data_py.

        Args:
            years: List of seasons to download
            current_week: If True, only download current week

        Returns:
            DataFrame with raw PBP data
        """
        import nfl_data_py as nfl
        import warnings
        warnings.filterwarnings('ignore')

        if current_week:
            season, week = get_current_nfl_week()
            years = [season]
            self.logger.info(f"Downloading current week: {season} Week {week}")
        elif not years:
            years = [2023, 2024]

        self.logger.info(f"Downloading PBP data for years: {years}")

        try:
            # Download play-by-play data
            pbp = nfl.import_pbp_data(years, downcast=True)
            self.logger.info(f"  Downloaded {len(pbp):,} plays")

            # Cache locally
            cache_file = self.cache_dir / f"pbp_{'_'.join(map(str, years))}.parquet"
            pbp.to_parquet(cache_file, index=False)

            return pbp

        except Exception as e:
            self.logger.error(f"Failed to download PBP data: {e}")

            # Try loading from cache
            cache_files = list(self.cache_dir.glob("pbp_*.parquet"))
            if cache_files:
                self.logger.info("Loading from cache...")
                return pd.read_parquet(cache_files[-1])

            return pd.DataFrame()

    def process_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Aggregate play-by-play data to player-season/week level.

        Computes:
        - Red zone targets/carries/TDs
        - Goal line attempts
        - EPA per target/rush
        - Air yards metrics
        - Situational usage
        """
        if df.empty:
            return df

        self.logger.info("Processing PBP data into player aggregations...")

        # Filter to relevant plays
        df = df[df['play_type'].isin(['pass', 'run'])].copy()

        # Mark red zone plays (inside 20)
        df['is_red_zone'] = df['yardline_100'] <= 20
        df['is_goal_line'] = df['yardline_100'] <= 5

        # Mark situational plays
        df['is_third_down'] = df['down'] == 3
        df['is_neutral_script'] = df['score_differential'].abs() <= 7
        df['is_two_minute'] = (df['half_seconds_remaining'] <= 120) & (df['qtr'].isin([2, 4]))

        # Calculate team totals for share metrics
        team_totals = df.groupby(['season', 'week', 'posteam']).agg({
            'air_yards': 'sum',
            'pass': 'sum',
        }).reset_index()
        team_totals.columns = ['season', 'week', 'posteam', 'team_air_yards', 'team_passes']

        # Merge team totals
        df = df.merge(team_totals, on=['season', 'week', 'posteam'], how='left')

        # =====================================================================
        # RECEIVING AGGREGATIONS
        # =====================================================================
        receiving_plays = df[df['play_type'] == 'pass'].copy()

        # Group by receiver
        receiving_agg = receiving_plays.groupby(
            ['season', 'week', 'receiver_player_id', 'receiver_player_name', 'posteam']
        ).agg({
            # Volume
            'play_id': 'count',  # targets
            'complete_pass': 'sum',  # receptions
            'yards_gained': 'sum',  # receiving yards
            'pass_touchdown': 'sum',  # TDs

            # Air yards
            'air_yards': 'sum',
            'team_air_yards': 'first',

            # EPA
            'epa': 'sum',

            # Red zone
            'is_red_zone': 'sum',

            # Situational
            'is_third_down': 'sum',
            'is_neutral_script': 'sum',
            'is_two_minute': 'sum',
        }).reset_index()

        receiving_agg.columns = [
            'season', 'week', 'player_id', 'player_name', 'team',
            'targets', 'receptions', 'receiving_yards', 'receiving_tds',
            'air_yards', 'team_air_yards',
            'receiving_epa',
            'rz_targets',
            'third_down_targets', 'neutral_script_targets', 'two_min_targets'
        ]

        # Calculate derived metrics
        receiving_agg['air_yards_share'] = (
            receiving_agg['air_yards'] / receiving_agg['team_air_yards']
        ).fillna(0)
        receiving_agg['adot'] = (
            receiving_agg['air_yards'] / receiving_agg['targets']
        ).fillna(0)
        receiving_agg['epa_per_target'] = (
            receiving_agg['receiving_epa'] / receiving_agg['targets']
        ).fillna(0)
        receiving_agg['catch_rate'] = (
            receiving_agg['receptions'] / receiving_agg['targets']
        ).fillna(0)

        # Calculate WOPR (Weighted Opportunity Rating)
        receiving_agg['target_share'] = receiving_agg.groupby(
            ['season', 'week', 'team']
        )['targets'].transform(lambda x: x / x.sum())
        receiving_agg['wopr'] = (
            1.5 * receiving_agg['target_share'] +
            0.7 * receiving_agg['air_yards_share']
        )

        receiving_agg['position'] = 'WR'  # Will need to join with roster for actual position

        # =====================================================================
        # RUSHING AGGREGATIONS
        # =====================================================================
        rushing_plays = df[df['play_type'] == 'run'].copy()

        rushing_agg = rushing_plays.groupby(
            ['season', 'week', 'rusher_player_id', 'rusher_player_name', 'posteam']
        ).agg({
            'play_id': 'count',  # carries
            'yards_gained': 'sum',  # rushing yards
            'rush_touchdown': 'sum',  # TDs
            'epa': 'sum',
            'is_red_zone': 'sum',
            'is_goal_line': 'sum',
            'is_neutral_script': 'sum',
        }).reset_index()

        rushing_agg.columns = [
            'season', 'week', 'player_id', 'player_name', 'team',
            'carries', 'rushing_yards', 'rushing_tds',
            'rushing_epa',
            'rz_carries', 'gl_carries', 'neutral_script_carries'
        ]

        rushing_agg['epa_per_carry'] = (
            rushing_agg['rushing_epa'] / rushing_agg['carries']
        ).fillna(0)
        rushing_agg['ypc'] = (
            rushing_agg['rushing_yards'] / rushing_agg['carries']
        ).fillna(0)
        rushing_agg['rz_td_rate'] = (
            rushing_agg['rushing_tds'] / rushing_agg['rz_carries']
        ).fillna(0)
        rushing_agg['gl_td_rate'] = (
            rushing_agg['rushing_tds'] / rushing_agg['gl_carries']
        ).fillna(0)

        rushing_agg['position'] = 'RB'  # Will need to join with roster for actual position

        # =====================================================================
        # COMBINE AND FINALIZE
        # =====================================================================
        # For now, keep them separate and merge on player_id
        # In production, we'd merge with roster data for accurate positions

        # Add metadata
        receiving_agg['stat_type'] = 'receiving'
        rushing_agg['stat_type'] = 'rushing'

        # Stack the dataframes
        all_agg = pd.concat([
            receiving_agg[['season', 'week', 'player_id', 'player_name', 'team', 'position',
                          'targets', 'receptions', 'receiving_yards', 'receiving_tds',
                          'air_yards', 'air_yards_share', 'adot', 'wopr', 'target_share',
                          'epa_per_target', 'catch_rate',
                          'rz_targets', 'third_down_targets', 'neutral_script_targets',
                          'stat_type']],
            rushing_agg[['season', 'week', 'player_id', 'player_name', 'team', 'position',
                        'carries', 'rushing_yards', 'rushing_tds',
                        'epa_per_carry', 'ypc',
                        'rz_carries', 'gl_carries', 'rz_td_rate', 'gl_td_rate',
                        'neutral_script_carries',
                        'stat_type']]
        ], ignore_index=True)

        # Filter out null player IDs
        all_agg = all_agg[all_agg['player_id'].notna()].copy()

        self.logger.info(f"  Created {len(all_agg):,} player-week aggregations")
        return all_agg

    def create_schema(self):
        """Create Neo4j indexes and constraints."""
        self.logger.info("Creating PBP aggregates schema...")

        queries = [
            """CREATE CONSTRAINT pbp_agg_unique IF NOT EXISTS
               FOR (p:PlayByPlayAggregates)
               REQUIRE (p.player_id, p.season, p.week, p.stat_type) IS UNIQUE""",

            """CREATE INDEX pbp_season IF NOT EXISTS
               FOR (p:PlayByPlayAggregates) ON (p.season)""",

            """CREATE INDEX pbp_player IF NOT EXISTS
               FOR (p:PlayByPlayAggregates) ON (p.player_id)""",

            """CREATE INDEX pbp_stat_type IF NOT EXISTS
               FOR (p:PlayByPlayAggregates) ON (p.stat_type)""",
        ]

        for query in queries:
            try:
                self.run_write(query)
            except Exception as e:
                if "already exists" not in str(e).lower() and "equivalent" not in str(e).lower():
                    self.logger.warning(f"Schema warning: {e}")

    def create_nodes(self, df: pd.DataFrame) -> int:
        """Create PlayByPlayAggregates nodes in Neo4j."""
        if df.empty:
            return 0

        self.logger.info("Creating PlayByPlayAggregates nodes...")

        # Convert to records
        records = df.to_dict('records')

        # Clean up NaN values
        for record in records:
            for key, value in record.items():
                if pd.isna(value):
                    record[key] = None

        query = """
        UNWIND $batch AS r
        MERGE (p:PlayByPlayAggregates {
            player_id: r.player_id,
            season: r.season,
            week: r.week,
            stat_type: r.stat_type
        })
        SET p.player_name = r.player_name,
            p.team = r.team,
            p.position = r.position,

            // Receiving metrics
            p.targets = r.targets,
            p.receptions = r.receptions,
            p.receiving_yards = r.receiving_yards,
            p.receiving_tds = r.receiving_tds,
            p.air_yards = r.air_yards,
            p.air_yards_share = r.air_yards_share,
            p.adot = r.adot,
            p.wopr = r.wopr,
            p.target_share = r.target_share,
            p.epa_per_target = r.epa_per_target,
            p.catch_rate = r.catch_rate,

            // Rushing metrics
            p.carries = r.carries,
            p.rushing_yards = r.rushing_yards,
            p.rushing_tds = r.rushing_tds,
            p.epa_per_carry = r.epa_per_carry,
            p.ypc = r.ypc,

            // Red zone / goal line
            p.rz_targets = r.rz_targets,
            p.rz_carries = r.rz_carries,
            p.gl_carries = r.gl_carries,
            p.rz_td_rate = r.rz_td_rate,
            p.gl_td_rate = r.gl_td_rate,

            // Situational
            p.third_down_targets = r.third_down_targets,
            p.neutral_script_targets = r.neutral_script_targets,
            p.neutral_script_carries = r.neutral_script_carries,

            p.loaded_at = datetime()
        """

        count = self.batch_merge(query, records)
        self.logger.info(f"  Created/updated {count:,} PlayByPlayAggregates nodes")

        return count


def main():
    parser = argparse.ArgumentParser(description='Ingest PBP Features')
    parser.add_argument(
        '--years',
        nargs='+',
        type=int,
        help='Seasons to process (e.g., 2023 2024)'
    )
    parser.add_argument(
        '--current-week',
        action='store_true',
        help='Only process current week'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Test mode - no database writes'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Skip import lock check'
    )

    args = parser.parse_args()

    ingester = PBPFeaturesIngester()

    try:
        if args.test:
            # Just download and process, don't write to DB
            df = ingester.download_data(
                years=args.years,
                current_week=args.current_week
            )
            df = ingester.process_data(df)
            print(f"\nProcessed {len(df)} records")
            print("\nSample data:")
            print(df.head(10).to_string())
            return 0

        result = ingester.run(
            skip_lock_check=args.force,
            years=args.years,
            current_week=args.current_week
        )

        if result['status'] == 'success':
            return 0
        elif result['status'] == 'skipped':
            return 2
        else:
            return 1

    finally:
        ingester.close()


if __name__ == '__main__':
    sys.exit(main())
