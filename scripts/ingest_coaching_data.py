#!/usr/bin/env python3
"""
NFL Coaching & Scheme Data Ingestion
====================================
Downloads and integrates coaching profiles and scheme data into Neo4j.
Important for understanding offensive philosophy and player utilization patterns.

Data Sources:
- Pro Football Reference (coaching histories)
- nflfastR play-by-play (tendencies, personnel usage)
- Manual coaching tree classifications

Records: ~600 team-season profiles (32 teams × ~20 years)
Schedule: Annual update in March (coaching changes) + preseason (scheme analysis)

Features Extracted:
- Coaching tree lineage (McVay/Shanahan/Reid/etc.)
- Pass rate in neutral game script
- Pre-snap motion frequency
- Play-action usage
- Personnel grouping tendencies

Usage:
    python scripts/ingest_coaching_data.py --years 2020 2021 2022 2023 2024
    python scripts/ingest_coaching_data.py --test  # Test mode
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
from scripts.data_jobs import BaseIngester
from scripts.data_jobs.utils import normalize_team_abbr, NFL_TEAMS

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Coaching tree classifications (manually curated)
# This would be expanded with more comprehensive data in production
COACHING_TREE_MAP = {
    # McVay/Shanahan tree (pass-heavy, play-action, outside zone)
    'Sean McVay': 'mcvay',
    'Kyle Shanahan': 'shanahan',
    'Matt LaFleur': 'shanahan',
    'Mike McDaniel': 'shanahan',
    'Zac Taylor': 'mcvay',
    'Kevin O\'Connell': 'mcvay',
    'Raheem Morris': 'mcvay',

    # Andy Reid tree (creative passing, motion, TE usage)
    'Andy Reid': 'reid',
    'Doug Pederson': 'reid',
    'Matt Nagy': 'reid',
    'Eric Bieniemy': 'reid',

    # Bill Belichick tree (run-heavy, defense-first)
    'Bill Belichick': 'belichick',
    'Brian Flores': 'belichick',
    'Joe Judge': 'belichick',
    'Matt Patricia': 'belichick',

    # Sean Payton tree (balanced, dome-oriented)
    'Sean Payton': 'payton',
    'Dennis Allen': 'payton',

    # Others
    'John Harbaugh': 'other',
    'Mike Tomlin': 'other',
    'Dan Campbell': 'other',
}


class CoachingDataIngester(BaseIngester):
    """
    Ingests NFL coaching profiles and scheme data into Neo4j.

    Combines coaching histories with play-by-play derived tendencies
    to create comprehensive coaching profiles for each team-season.
    """

    def __init__(self):
        super().__init__('coaching_data', batch_size=100)
        self.cache_dir = self.data_dir / "coaching_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def download_data(self, years: List[int] = None) -> pd.DataFrame:
        """
        Download coaching and scheme tendency data.

        Args:
            years: List of seasons to fetch

        Returns:
            DataFrame with team-season coaching profiles
        """
        if not years:
            years = list(range(2020, 2025))

        self.logger.info(f"Downloading coaching data for years: {years}")

        try:
            import nfl_data_py as nfl
            import warnings
            warnings.filterwarnings('ignore')

            # Download play-by-play data to derive scheme tendencies
            self.logger.info("  Downloading PBP data for scheme analysis...")
            pbp = nfl.import_pbp_data(years, downcast=True)
            self.logger.info(f"  Downloaded {len(pbp):,} plays")

            # Cache PBP data
            cache_file = self.cache_dir / f"pbp_coaching_{'_'.join(map(str, years))}.parquet"
            pbp.to_parquet(cache_file, index=False)

            return pbp

        except Exception as e:
            self.logger.error(f"Failed to download PBP data: {e}")

            # Try loading from cache
            cache_files = list(self.cache_dir.glob("pbp_coaching_*.parquet"))
            if cache_files:
                self.logger.info("Loading from cache...")
                return pd.read_parquet(cache_files[-1])

            # Fallback to placeholder
            return self._create_placeholder_data(years)

    def _create_placeholder_data(self, years: List[int]) -> pd.DataFrame:
        """Create placeholder coaching data for testing."""
        self.logger.info("Creating placeholder coaching data...")

        data = []
        for year in years:
            for team in NFL_TEAMS[:5]:  # Just a few teams for testing
                data.append({
                    'season': year,
                    'team': team,
                    'head_coach': 'Test Coach',
                    'offensive_coordinator': 'Test OC',
                    'pass_rate_neutral': 0.58,
                    'motion_rate': 0.45,
                    'play_action_rate': 0.25,
                    'personnel_11_rate': 0.60,
                })

        return pd.DataFrame(data)

    def process_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Process play-by-play data into coaching/scheme profiles.

        Computes:
        - Pass rate in neutral situations (score within 7, 1st-3rd quarter)
        - Pre-snap motion frequency
        - Play-action rate
        - Personnel grouping tendencies (11, 12, 21, etc.)
        """
        if df.empty:
            return df

        self.logger.info("Processing coaching/scheme data...")

        # Check if this is already processed or raw PBP
        if 'play_type' not in df.columns:
            # Already processed, return as-is
            return df

        # Filter to relevant plays
        df = df[df['play_type'].isin(['pass', 'run'])].copy()

        # Define neutral game script
        df['is_neutral'] = (
            (df['score_differential'].abs() <= 7) &
            (df['qtr'].isin([1, 2, 3])) &
            (df['down'].isin([1, 2, 3]))
        )

        # Aggregate by team-season
        team_season_agg = []

        for (season, team), group in df.groupby(['season', 'posteam']):
            if pd.isna(team) or team == '':
                continue

            team = normalize_team_abbr(team)

            # Filter to neutral situations
            neutral_plays = group[group['is_neutral']]

            if len(neutral_plays) == 0:
                continue

            # Calculate tendencies
            profile = {
                'season': int(season),
                'team': team,

                # Pass rate in neutral script
                'pass_rate_neutral': (
                    neutral_plays['play_type'] == 'pass'
                ).mean(),

                # Motion rate (if available)
                'motion_rate': (
                    group['motion'].fillna(0).mean()
                    if 'motion' in group.columns else 0.45  # Default estimate
                ),

                # Play-action rate (if available)
                'play_action_rate': (
                    group['play_action'].fillna(0).mean()
                    if 'play_action' in group.columns else 0.25  # Default estimate
                ),

                # Personnel grouping (11 personnel = 1 RB, 1 TE, 3 WR)
                'personnel_11_rate': (
                    (group['personnel'].fillna('').str.contains('1 RB, 1 TE')).mean()
                    if 'personnel' in group.columns else 0.60  # Default estimate
                ),

                # Total plays for context
                'total_plays': len(group),
                'neutral_plays': len(neutral_plays),
            }

            team_season_agg.append(profile)

        result_df = pd.DataFrame(team_season_agg)

        # Add coaching metadata (would be scraped from PFR in production)
        result_df['head_coach'] = result_df.apply(
            lambda x: self._get_head_coach(x['team'], x['season']), axis=1
        )
        result_df['offensive_coordinator'] = 'Unknown'  # Would be populated from data

        # Add coaching tree classification
        result_df['coaching_tree'] = result_df['head_coach'].map(
            lambda x: COACHING_TREE_MAP.get(x, 'other')
        )

        self.logger.info(f"  Processed {len(result_df):,} team-season profiles")
        return result_df

    def _get_head_coach(self, team: str, season: int) -> str:
        """
        Get head coach for team-season.

        This is a simplified lookup - in production would use scraped data
        from Pro Football Reference or similar source.
        """
        # Placeholder data for recent well-known coaches
        coach_map = {
            ('KC', 2020): 'Andy Reid', ('KC', 2021): 'Andy Reid',
            ('KC', 2022): 'Andy Reid', ('KC', 2023): 'Andy Reid',
            ('KC', 2024): 'Andy Reid',

            ('LAR', 2020): 'Sean McVay', ('LAR', 2021): 'Sean McVay',
            ('LAR', 2022): 'Sean McVay', ('LAR', 2023): 'Sean McVay',
            ('LAR', 2024): 'Sean McVay',

            ('SF', 2020): 'Kyle Shanahan', ('SF', 2021): 'Kyle Shanahan',
            ('SF', 2022): 'Kyle Shanahan', ('SF', 2023): 'Kyle Shanahan',
            ('SF', 2024): 'Kyle Shanahan',

            ('MIA', 2022): 'Mike McDaniel', ('MIA', 2023): 'Mike McDaniel',
            ('MIA', 2024): 'Mike McDaniel',

            ('MIN', 2022): 'Kevin O\'Connell', ('MIN', 2023): 'Kevin O\'Connell',
            ('MIN', 2024): 'Kevin O\'Connell',

            ('GB', 2019): 'Matt LaFleur', ('GB', 2020): 'Matt LaFleur',
            ('GB', 2021): 'Matt LaFleur', ('GB', 2022): 'Matt LaFleur',
            ('GB', 2023): 'Matt LaFleur', ('GB', 2024): 'Matt LaFleur',
        }

        return coach_map.get((team, season), 'Unknown')

    def create_schema(self):
        """Create Neo4j indexes and constraints for coaching profiles."""
        self.logger.info("Creating coaching profile schema...")

        queries = [
            """CREATE CONSTRAINT coaching_profile_unique IF NOT EXISTS
               FOR (cp:CoachingProfile)
               REQUIRE (cp.team, cp.season) IS UNIQUE""",

            """CREATE INDEX coaching_season IF NOT EXISTS
               FOR (cp:CoachingProfile) ON (cp.season)""",

            """CREATE INDEX coaching_team IF NOT EXISTS
               FOR (cp:CoachingProfile) ON (cp.team)""",

            """CREATE INDEX coaching_tree IF NOT EXISTS
               FOR (cp:CoachingProfile) ON (cp.coaching_tree)""",

            """CREATE INDEX coaching_head_coach IF NOT EXISTS
               FOR (cp:CoachingProfile) ON (cp.head_coach)""",
        ]

        for query in queries:
            try:
                self.run_write(query)
            except Exception as e:
                if "already exists" not in str(e).lower() and "equivalent" not in str(e).lower():
                    self.logger.warning(f"Schema warning: {e}")

    def create_nodes(self, df: pd.DataFrame) -> int:
        """Create CoachingProfile nodes in Neo4j."""
        if df.empty:
            return 0

        self.logger.info("Creating CoachingProfile nodes...")

        # Convert to records
        records = df.to_dict('records')

        # Clean up NaN values
        for record in records:
            for key, value in record.items():
                if pd.isna(value):
                    record[key] = None

        query = """
        UNWIND $batch AS r
        MERGE (cp:CoachingProfile {team: r.team, season: r.season})
        SET cp.head_coach = r.head_coach,
            cp.offensive_coordinator = r.offensive_coordinator,
            cp.coaching_tree = r.coaching_tree,

            // Scheme tendencies
            cp.pass_rate_neutral = r.pass_rate_neutral,
            cp.motion_rate = r.motion_rate,
            cp.play_action_rate = r.play_action_rate,
            cp.personnel_11_rate = r.personnel_11_rate,

            // Context
            cp.total_plays = r.total_plays,
            cp.neutral_plays = r.neutral_plays,

            cp.loaded_at = datetime()
        """

        count = self.batch_merge(query, records)
        self.logger.info(f"  Created/updated {count:,} CoachingProfile nodes")

        return count


def main():
    parser = argparse.ArgumentParser(description='Ingest NFL Coaching Data')
    parser.add_argument(
        '--years',
        nargs='+',
        type=int,
        default=list(range(2020, 2025)),
        help='Seasons to process (e.g., 2020 2021 2022 2023 2024)'
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

    ingester = CoachingDataIngester()

    try:
        if args.test:
            # Just download and process, don't write to DB
            df = ingester.download_data(years=args.years)
            df = ingester.process_data(df)
            print(f"\nProcessed {len(df)} records")
            print("\nSample data:")
            print(df.head(10).to_string())
            return 0

        result = ingester.run(
            skip_lock_check=args.force,
            years=args.years
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
