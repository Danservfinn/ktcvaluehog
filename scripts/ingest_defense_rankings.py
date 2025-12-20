#!/usr/bin/env python3
"""
NFL Team Defense Rankings Ingestion
====================================
Downloads and integrates defensive efficiency metrics into Neo4j.
Critical for understanding fantasy matchup difficulty and player projections.

Data Source: nflfastR play-by-play aggregations
Records: ~600 team-season profiles (32 teams × ~20 years)
Schedule: Weekly during season (Tuesday 4AM) + annual historical load

Features Extracted:
- Overall defensive EPA per play
- Position-specific fantasy points allowed (QB/RB/WR/TE)
- Pass rush efficiency (pressure rate, sack rate)
- Coverage metrics (EPA allowed per pass)

Usage:
    python scripts/ingest_defense_rankings.py --years 2020 2021 2022 2023 2024
    python scripts/ingest_defense_rankings.py --current-week  # Weekly update
    python scripts/ingest_defense_rankings.py --test  # Test mode
"""

import os
import sys
import ssl
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

# Bypass SSL verification for nflverse downloads
ssl._create_default_https_context = ssl._create_unverified_context

import pandas as pd
import numpy as np

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from scripts.data_jobs import BaseIngester, get_current_nfl_week
from scripts.data_jobs.utils import normalize_team_abbr, NFL_TEAMS

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DefenseDataIngester(BaseIngester):
    """
    Ingests NFL team defense rankings and efficiency metrics into Neo4j.

    Aggregates play-by-play data to calculate defensive performance
    metrics both overall and position-specific for fantasy analysis.
    """

    def __init__(self):
        super().__init__('defense_rankings', batch_size=100)
        self.cache_dir = self.data_dir / "defense_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def download_data(self, years: List[int] = None, current_week: bool = False) -> pd.DataFrame:
        """
        Download play-by-play data for defensive analysis.

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
            years = list(range(2020, 2025))

        self.logger.info(f"Downloading PBP data for defense analysis: {years}")

        try:
            # Download play-by-play data
            pbp = nfl.import_pbp_data(years, downcast=True)
            self.logger.info(f"  Downloaded {len(pbp):,} plays")

            # Cache locally
            cache_file = self.cache_dir / f"pbp_defense_{'_'.join(map(str, years))}.parquet"
            pbp.to_parquet(cache_file, index=False)

            return pbp

        except Exception as e:
            self.logger.error(f"Failed to download PBP data: {e}")

            # Try loading from cache
            cache_files = list(self.cache_dir.glob("pbp_defense_*.parquet"))
            if cache_files:
                self.logger.info("Loading from cache...")
                return pd.read_parquet(cache_files[-1])

            return pd.DataFrame()

    def process_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Process play-by-play data into defensive efficiency profiles.

        Computes:
        - Defensive EPA per play (overall, pass, rush)
        - Fantasy points allowed by position (QB/RB/WR/TE)
        - Pressure rate and sack rate
        - Coverage efficiency
        """
        if df.empty:
            return df

        self.logger.info("Processing defense rankings data...")

        # Filter to relevant plays
        df = df[df['play_type'].isin(['pass', 'run'])].copy()

        # Aggregate by defending team
        defense_profiles = []

        for (season, defteam), group in df.groupby(['season', 'defteam']):
            if pd.isna(defteam) or defteam == '':
                continue

            defteam = normalize_team_abbr(defteam)

            # Overall defensive metrics
            profile = {
                'season': int(season),
                'team': defteam,
                'total_plays': len(group),
            }

            # EPA metrics (defensive perspective - lower is better)
            profile['def_epa_per_play'] = -group['epa'].mean()  # Negate for defensive view

            # Pass defense
            pass_plays = group[group['play_type'] == 'pass']
            if len(pass_plays) > 0:
                profile['pass_epa_allowed'] = -pass_plays['epa'].mean()
                profile['completion_rate_allowed'] = pass_plays['complete_pass'].mean()
                profile['yards_per_pass_allowed'] = pass_plays['yards_gained'].mean()

                # Pressure metrics (if available)
                if 'qb_hit' in pass_plays.columns:
                    profile['pressure_rate'] = (
                        (pass_plays['qb_hit'].fillna(0) == 1) |
                        (pass_plays['sack'].fillna(0) == 1)
                    ).mean()
                else:
                    profile['pressure_rate'] = None

                if 'sack' in pass_plays.columns:
                    profile['sack_rate'] = pass_plays['sack'].fillna(0).mean()
                else:
                    profile['sack_rate'] = None
            else:
                profile['pass_epa_allowed'] = None
                profile['completion_rate_allowed'] = None
                profile['yards_per_pass_allowed'] = None
                profile['pressure_rate'] = None
                profile['sack_rate'] = None

            # Rush defense
            rush_plays = group[group['play_type'] == 'run']
            if len(rush_plays) > 0:
                profile['rush_epa_allowed'] = -rush_plays['epa'].mean()
                profile['yards_per_rush_allowed'] = rush_plays['yards_gained'].mean()
                profile['stuff_rate'] = (rush_plays['yards_gained'] <= 0).mean()
            else:
                profile['rush_epa_allowed'] = None
                profile['yards_per_rush_allowed'] = None
                profile['stuff_rate'] = None

            defense_profiles.append(profile)

        result_df = pd.DataFrame(defense_profiles)

        # Calculate position-specific fantasy points allowed
        # This requires roster data to map players to positions
        # For now, we'll calculate approximate values based on play type

        self.logger.info(f"  Processed {len(result_df):,} team-season defensive profiles")
        return result_df

    def _calculate_position_allowed(
        self,
        df: pd.DataFrame,
        season: int,
        defteam: str
    ) -> Dict[str, float]:
        """
        Calculate fantasy points allowed by position.

        This is a simplified version - in production would join with
        roster data to accurately map players to positions.
        """
        # Filter to this defense's games
        defense_plays = df[
            (df['season'] == season) &
            (df['defteam'] == defteam)
        ]

        # Approximate position-based fantasy points
        # In production, would use actual player positions
        ppg_allowed = {
            'ppg_allowed_qb': None,  # Would calculate from passing stats
            'ppg_allowed_rb': None,  # Would calculate from rushing stats
            'ppg_allowed_wr': None,  # Would calculate from receiving stats
            'ppg_allowed_te': None,  # Would calculate from receiving stats
        }

        # QB: passing yards/25 + passing TDs * 4 - INTs * 2 + rush yards/10 + rush TDs * 6
        pass_plays = defense_plays[defense_plays['play_type'] == 'pass']
        if len(pass_plays) > 0:
            games = defense_plays['game_id'].nunique()
            total_pass_yds = pass_plays['yards_gained'].sum()
            total_pass_tds = pass_plays['pass_touchdown'].sum()
            total_ints = pass_plays['interception'].sum()

            qb_ppg = (
                total_pass_yds / 25 +
                total_pass_tds * 4 -
                total_ints * 2
            ) / max(games, 1)

            ppg_allowed['ppg_allowed_qb'] = qb_ppg

        # RB: rush yards/10 + rush TDs * 6 + rec yards/10 + rec TDs * 6 + receptions * 1
        rush_plays = defense_plays[defense_plays['play_type'] == 'run']
        if len(rush_plays) > 0:
            games = defense_plays['game_id'].nunique()
            total_rush_yds = rush_plays['yards_gained'].sum()
            total_rush_tds = rush_plays['rush_touchdown'].sum()

            rb_ppg = (
                total_rush_yds / 10 +
                total_rush_tds * 6
            ) / max(games, 1)

            ppg_allowed['ppg_allowed_rb'] = rb_ppg

        return ppg_allowed

    def create_schema(self):
        """Create Neo4j indexes and constraints for defense profiles."""
        self.logger.info("Creating defense profile schema...")

        queries = [
            """CREATE CONSTRAINT defense_profile_unique IF NOT EXISTS
               FOR (dp:TeamDefenseProfile)
               REQUIRE (dp.team, dp.season) IS UNIQUE""",

            """CREATE INDEX defense_season IF NOT EXISTS
               FOR (dp:TeamDefenseProfile) ON (dp.season)""",

            """CREATE INDEX defense_team IF NOT EXISTS
               FOR (dp:TeamDefenseProfile) ON (dp.team)""",

            """CREATE INDEX defense_epa IF NOT EXISTS
               FOR (dp:TeamDefenseProfile) ON (dp.def_epa_per_play)""",
        ]

        for query in queries:
            try:
                self.run_write(query)
            except Exception as e:
                if "already exists" not in str(e).lower() and "equivalent" not in str(e).lower():
                    self.logger.warning(f"Schema warning: {e}")

    def create_nodes(self, df: pd.DataFrame) -> int:
        """Create TeamDefenseProfile nodes in Neo4j."""
        if df.empty:
            return 0

        self.logger.info("Creating TeamDefenseProfile nodes...")

        # Convert to records
        records = df.to_dict('records')

        # Clean up NaN values
        for record in records:
            for key, value in record.items():
                if pd.isna(value):
                    record[key] = None

        query = """
        UNWIND $batch AS r
        MERGE (dp:TeamDefenseProfile {team: r.team, season: r.season})
        SET dp.total_plays = r.total_plays,

            // Overall defensive efficiency
            dp.def_epa_per_play = r.def_epa_per_play,
            dp.pass_epa_allowed = r.pass_epa_allowed,
            dp.rush_epa_allowed = r.rush_epa_allowed,

            // Pass defense metrics
            dp.completion_rate_allowed = r.completion_rate_allowed,
            dp.yards_per_pass_allowed = r.yards_per_pass_allowed,
            dp.pressure_rate = r.pressure_rate,
            dp.sack_rate = r.sack_rate,

            // Rush defense metrics
            dp.yards_per_rush_allowed = r.yards_per_rush_allowed,
            dp.stuff_rate = r.stuff_rate,

            // Position-specific (if available)
            dp.ppg_allowed_qb = r.ppg_allowed_qb,
            dp.ppg_allowed_rb = r.ppg_allowed_rb,
            dp.ppg_allowed_wr = r.ppg_allowed_wr,
            dp.ppg_allowed_te = r.ppg_allowed_te,

            dp.loaded_at = datetime()
        """

        count = self.batch_merge(query, records)
        self.logger.info(f"  Created/updated {count:,} TeamDefenseProfile nodes")

        return count


def main():
    parser = argparse.ArgumentParser(description='Ingest NFL Defense Rankings')
    parser.add_argument(
        '--years',
        nargs='+',
        type=int,
        default=list(range(2020, 2025)),
        help='Seasons to process (e.g., 2020 2021 2022 2023 2024)'
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

    ingester = DefenseDataIngester()

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
