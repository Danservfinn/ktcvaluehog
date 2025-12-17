"""
Historical NFL Data Loader (1999-2024)
======================================
Loads 26 years of NFL data from nflverse for ML training.

Data Sources:
- Player Stats: 1999-2024 (weekly fantasy points, passing/rushing/receiving)
- Rosters: 1999-2024 (player metadata, teams)
- Snap Counts: 2015-2024 (usage/opportunity)
- Next Gen Stats: 2016-2024 (efficiency metrics)
- Combine: 2000-2024 (athletic profiles)
- Play-by-Play: 1999-2024 (optional, for advanced features)

This creates the most comprehensive dynasty fantasy ML training dataset available.
"""

import logging
from typing import Optional, List, Dict, Tuple
from datetime import datetime
import time

import pandas as pd
import numpy as np

try:
    import nflreadpy as nfl
    NFLREADPY_AVAILABLE = True
except ImportError:
    NFLREADPY_AVAILABLE = False
    print("Warning: nflreadpy not available. Install with: pip install nflreadpy polars")

logger = logging.getLogger(__name__)


class HistoricalNFLLoader:
    """
    Load historical NFL data (1999-2024) from nflverse.

    Data Tiers:
    - Tier 1 (1999-2024): Core stats, rosters, combine
    - Tier 2 (2015-2024): + Snap counts
    - Tier 3 (2016-2024): + Next Gen Stats
    """

    # Year ranges for different data types
    STATS_START_YEAR = 1999
    SNAP_START_YEAR = 2015
    NGS_START_YEAR = 2016
    COMBINE_START_YEAR = 2000
    CURRENT_YEAR = 2024  # Most recent complete season

    FANTASY_POSITIONS = ['QB', 'RB', 'WR', 'TE']

    def __init__(self):
        """Initialize the historical loader."""
        if not NFLREADPY_AVAILABLE:
            raise ImportError("nflreadpy is required. Install with: pip install nflreadpy polars")

    def _to_pandas(self, data) -> pd.DataFrame:
        """Convert Polars DataFrame to Pandas if needed."""
        if hasattr(data, 'to_pandas'):
            return data.to_pandas()
        return data

    # =========================================================================
    # PLAYER STATS (1999-2024)
    # =========================================================================

    def load_player_stats_range(
        self,
        start_year: int = None,
        end_year: int = None,
        positions: Optional[List[str]] = None,
        chunk_size: int = 5
    ) -> pd.DataFrame:
        """
        Load player stats for a range of years.

        Args:
            start_year: First year to load (default: 1999)
            end_year: Last year to load (default: 2024)
            positions: Filter to positions (default: QB, RB, WR, TE)
            chunk_size: Years to load at once (for memory management)

        Returns:
            DataFrame with all weekly player stats
        """
        start_year = start_year or self.STATS_START_YEAR
        end_year = end_year or self.CURRENT_YEAR
        positions = positions or self.FANTASY_POSITIONS

        logger.info(f"Loading player stats {start_year}-{end_year}...")

        all_stats = []
        years = list(range(start_year, end_year + 1))

        # Load in chunks to manage memory
        for i in range(0, len(years), chunk_size):
            chunk_years = years[i:i + chunk_size]
            logger.info(f"  Loading years {chunk_years[0]}-{chunk_years[-1]}...")

            try:
                stats = nfl.load_player_stats(chunk_years)
                df = self._to_pandas(stats)

                # Filter to fantasy positions
                if 'position' in df.columns:
                    df = df[df['position'].isin(positions)]

                all_stats.append(df)

                # Small delay to be nice to the API
                time.sleep(0.5)

            except Exception as e:
                logger.error(f"Error loading stats for {chunk_years}: {e}")

        if not all_stats:
            return pd.DataFrame()

        combined = pd.concat(all_stats, ignore_index=True)
        logger.info(f"Loaded {len(combined):,} total stat records")

        return combined

    def load_player_stats_single_year(self, year: int) -> pd.DataFrame:
        """Load player stats for a single year."""
        try:
            stats = nfl.load_player_stats([year])
            df = self._to_pandas(stats)

            if 'position' in df.columns:
                df = df[df['position'].isin(self.FANTASY_POSITIONS)]

            return df
        except Exception as e:
            logger.error(f"Error loading stats for {year}: {e}")
            return pd.DataFrame()

    # =========================================================================
    # ROSTERS (1999-2024)
    # =========================================================================

    def load_rosters_range(
        self,
        start_year: int = None,
        end_year: int = None
    ) -> pd.DataFrame:
        """Load roster data for a range of years."""
        start_year = start_year or self.STATS_START_YEAR
        end_year = end_year or self.CURRENT_YEAR

        logger.info(f"Loading rosters {start_year}-{end_year}...")

        all_rosters = []

        for year in range(start_year, end_year + 1):
            try:
                rosters = nfl.load_rosters([year])
                df = self._to_pandas(rosters)
                df['roster_year'] = year
                all_rosters.append(df)
            except Exception as e:
                logger.warning(f"Error loading rosters for {year}: {e}")

        if not all_rosters:
            return pd.DataFrame()

        combined = pd.concat(all_rosters, ignore_index=True)
        logger.info(f"Loaded {len(combined):,} roster records")

        return combined

    # =========================================================================
    # SNAP COUNTS (2015-2024)
    # =========================================================================

    def load_snap_counts_range(
        self,
        start_year: int = None,
        end_year: int = None
    ) -> pd.DataFrame:
        """Load snap count data (available 2015+)."""
        start_year = max(start_year or self.SNAP_START_YEAR, self.SNAP_START_YEAR)
        end_year = end_year or self.CURRENT_YEAR

        if start_year < self.SNAP_START_YEAR:
            logger.warning(f"Snap counts only available from {self.SNAP_START_YEAR}")
            start_year = self.SNAP_START_YEAR

        logger.info(f"Loading snap counts {start_year}-{end_year}...")

        all_snaps = []

        for year in range(start_year, end_year + 1):
            try:
                snaps = nfl.load_snap_counts([year])
                df = self._to_pandas(snaps)
                if not df.empty:
                    df['snap_year'] = year
                    all_snaps.append(df)
            except Exception as e:
                logger.warning(f"Error loading snap counts for {year}: {e}")

        if not all_snaps:
            return pd.DataFrame()

        combined = pd.concat(all_snaps, ignore_index=True)
        logger.info(f"Loaded {len(combined):,} snap count records")

        return combined

    # =========================================================================
    # NEXT GEN STATS (2016-2024)
    # =========================================================================

    def load_ngs_range(
        self,
        start_year: int = None,
        end_year: int = None,
        stat_types: List[str] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        Load Next Gen Stats (available 2016+).

        Returns dict with keys: 'passing', 'rushing', 'receiving'
        """
        start_year = max(start_year or self.NGS_START_YEAR, self.NGS_START_YEAR)
        end_year = end_year or self.CURRENT_YEAR
        stat_types = stat_types or ['passing', 'rushing', 'receiving']

        if start_year < self.NGS_START_YEAR:
            logger.warning(f"NGS only available from {self.NGS_START_YEAR}")
            start_year = self.NGS_START_YEAR

        logger.info(f"Loading NGS {start_year}-{end_year}...")

        results = {st: [] for st in stat_types}

        for year in range(start_year, end_year + 1):
            for stat_type in stat_types:
                try:
                    ngs = nfl.load_nextgen_stats([year], stat_type=stat_type)
                    df = self._to_pandas(ngs)
                    if not df.empty:
                        df['ngs_year'] = year
                        results[stat_type].append(df)
                except Exception as e:
                    logger.warning(f"Error loading NGS {stat_type} for {year}: {e}")

        # Combine each stat type
        combined = {}
        for stat_type, dfs in results.items():
            if dfs:
                combined[stat_type] = pd.concat(dfs, ignore_index=True)
                logger.info(f"  {stat_type}: {len(combined[stat_type]):,} records")
            else:
                combined[stat_type] = pd.DataFrame()

        return combined

    # =========================================================================
    # COMBINE DATA (2000-2024)
    # =========================================================================

    def load_combine_all(self) -> pd.DataFrame:
        """Load all combine data (2000-present)."""
        logger.info("Loading combine data...")

        try:
            combine = nfl.load_combine()
            df = self._to_pandas(combine)
            logger.info(f"Loaded {len(df):,} combine records")
            return df
        except Exception as e:
            logger.error(f"Error loading combine data: {e}")
            return pd.DataFrame()

    # =========================================================================
    # DRAFT DATA
    # =========================================================================

    def load_draft_picks_range(
        self,
        start_year: int = None,
        end_year: int = None
    ) -> pd.DataFrame:
        """Load draft pick data."""
        start_year = start_year or self.STATS_START_YEAR
        end_year = end_year or self.CURRENT_YEAR

        logger.info(f"Loading draft picks {start_year}-{end_year}...")

        try:
            years = list(range(start_year, end_year + 1))
            draft = nfl.load_draft_picks(years)
            df = self._to_pandas(draft)
            logger.info(f"Loaded {len(df):,} draft pick records")
            return df
        except Exception as e:
            logger.error(f"Error loading draft picks: {e}")
            return pd.DataFrame()

    # =========================================================================
    # SEASON AGGREGATION
    # =========================================================================

    def compute_season_totals(self, weekly_stats: pd.DataFrame) -> pd.DataFrame:
        """
        Compute season totals from weekly stats.

        Returns DataFrame with one row per player-season.
        """
        if weekly_stats.empty:
            return pd.DataFrame()

        logger.info("Computing season totals...")

        # Columns to sum
        sum_cols = [
            'completions', 'attempts', 'passing_yards', 'passing_tds',
            'carries', 'rushing_yards', 'rushing_tds',
            'targets', 'receptions', 'receiving_yards', 'receiving_tds',
            'fantasy_points', 'fantasy_points_ppr'
        ]
        sum_cols = [c for c in sum_cols if c in weekly_stats.columns]

        # Columns to average
        avg_cols = ['target_share', 'air_yards_share', 'wopr']
        avg_cols = [c for c in avg_cols if c in weekly_stats.columns]

        # Group columns
        group_cols = ['player_id', 'player_display_name', 'position', 'season']
        group_cols = [c for c in group_cols if c in weekly_stats.columns]

        if not group_cols:
            return pd.DataFrame()

        # Build aggregation dict
        agg_dict = {'week': 'count'}  # games played
        for col in sum_cols:
            agg_dict[col] = 'sum'
        for col in avg_cols:
            agg_dict[col] = 'mean'

        # Get most common team
        if 'recent_team' in weekly_stats.columns:
            team_col = 'recent_team'
        elif 'team' in weekly_stats.columns:
            team_col = 'team'
        else:
            team_col = None

        # Group and aggregate
        totals = weekly_stats.groupby(group_cols).agg(agg_dict).reset_index()
        totals = totals.rename(columns={'week': 'games'})

        # Calculate PPG
        if 'fantasy_points_ppr' in totals.columns:
            totals['ppg_ppr'] = totals['fantasy_points_ppr'] / totals['games']
        if 'fantasy_points' in totals.columns:
            totals['ppg_std'] = totals['fantasy_points'] / totals['games']

        # Add team (most common)
        if team_col:
            team_mode = weekly_stats.groupby(group_cols)[team_col].agg(
                lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else None
            ).reset_index()
            team_mode.columns = group_cols + ['team']
            totals = totals.merge(team_mode, on=group_cols, how='left')

        logger.info(f"Computed {len(totals):,} season totals")

        return totals

    # =========================================================================
    # FULL DATA LOAD
    # =========================================================================

    def load_all_historical_data(
        self,
        start_year: int = None,
        end_year: int = None,
        include_snaps: bool = True,
        include_ngs: bool = True,
        include_combine: bool = True,
        include_draft: bool = True
    ) -> Dict[str, pd.DataFrame]:
        """
        Load all available historical data.

        Returns dict with:
        - 'weekly_stats': Weekly player stats (1999+)
        - 'season_stats': Season aggregated stats
        - 'rosters': Player rosters (1999+)
        - 'snap_counts': Snap data (2015+)
        - 'ngs_passing': NGS passing (2016+)
        - 'ngs_rushing': NGS rushing (2016+)
        - 'ngs_receiving': NGS receiving (2016+)
        - 'combine': Combine data (2000+)
        - 'draft': Draft picks
        """
        start_year = start_year or self.STATS_START_YEAR
        end_year = end_year or self.CURRENT_YEAR

        start_time = datetime.now()
        logger.info("=" * 60)
        logger.info(f"LOADING HISTORICAL NFL DATA ({start_year}-{end_year})")
        logger.info("=" * 60)

        data = {}

        # Core data (always load)
        data['weekly_stats'] = self.load_player_stats_range(start_year, end_year)
        data['season_stats'] = self.compute_season_totals(data['weekly_stats'])
        data['rosters'] = self.load_rosters_range(start_year, end_year)

        # Optional: Snap counts (2015+)
        if include_snaps:
            data['snap_counts'] = self.load_snap_counts_range(
                max(start_year, self.SNAP_START_YEAR), end_year
            )

        # Optional: NGS (2016+)
        if include_ngs:
            ngs = self.load_ngs_range(
                max(start_year, self.NGS_START_YEAR), end_year
            )
            data['ngs_passing'] = ngs.get('passing', pd.DataFrame())
            data['ngs_rushing'] = ngs.get('rushing', pd.DataFrame())
            data['ngs_receiving'] = ngs.get('receiving', pd.DataFrame())

        # Optional: Combine
        if include_combine:
            data['combine'] = self.load_combine_all()

        # Optional: Draft
        if include_draft:
            data['draft'] = self.load_draft_picks_range(start_year, end_year)

        duration = datetime.now() - start_time

        logger.info("=" * 60)
        logger.info("HISTORICAL DATA LOAD COMPLETE")
        logger.info(f"Duration: {duration}")
        for key, df in data.items():
            if isinstance(df, pd.DataFrame) and not df.empty:
                logger.info(f"  {key}: {len(df):,} records")
        logger.info("=" * 60)

        return data

    # =========================================================================
    # DATA QUALITY CHECKS
    # =========================================================================

    def get_data_coverage_report(self, data: Dict[str, pd.DataFrame]) -> Dict:
        """Generate report of data coverage by year."""
        report = {}

        # Weekly stats coverage
        if 'weekly_stats' in data and not data['weekly_stats'].empty:
            df = data['weekly_stats']
            if 'season' in df.columns:
                yearly = df.groupby('season').size()
                report['weekly_stats'] = {
                    'years': list(yearly.index),
                    'min_year': int(yearly.index.min()),
                    'max_year': int(yearly.index.max()),
                    'total_records': len(df),
                    'records_by_year': yearly.to_dict()
                }

        # Season stats coverage
        if 'season_stats' in data and not data['season_stats'].empty:
            df = data['season_stats']
            if 'season' in df.columns:
                yearly = df.groupby('season').size()
                report['season_stats'] = {
                    'years': list(yearly.index),
                    'total_records': len(df),
                    'avg_players_per_year': yearly.mean()
                }

        # Snap counts coverage
        if 'snap_counts' in data and not data['snap_counts'].empty:
            df = data['snap_counts']
            year_col = 'snap_year' if 'snap_year' in df.columns else 'season'
            if year_col in df.columns:
                yearly = df.groupby(year_col).size()
                report['snap_counts'] = {
                    'years': list(yearly.index),
                    'min_year': int(yearly.index.min()),
                    'max_year': int(yearly.index.max()),
                    'total_records': len(df)
                }

        # NGS coverage
        for ngs_type in ['ngs_passing', 'ngs_rushing', 'ngs_receiving']:
            if ngs_type in data and not data[ngs_type].empty:
                df = data[ngs_type]
                year_col = 'ngs_year' if 'ngs_year' in df.columns else 'season'
                if year_col in df.columns:
                    yearly = df.groupby(year_col).size()
                    report[ngs_type] = {
                        'years': list(yearly.index),
                        'min_year': int(yearly.index.min()),
                        'max_year': int(yearly.index.max()),
                        'total_records': len(df)
                    }

        return report


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description='Load historical NFL data')
    parser.add_argument('--start', type=int, default=1999, help='Start year')
    parser.add_argument('--end', type=int, default=2024, help='End year')
    parser.add_argument('--stats-only', action='store_true', help='Only load player stats')
    parser.add_argument('--test', action='store_true', help='Quick test with 2 years')

    args = parser.parse_args()

    loader = HistoricalNFLLoader()

    if args.test:
        # Quick test
        print("\nQuick test - loading 2023-2024 stats only...")
        stats = loader.load_player_stats_range(2023, 2024)
        print(f"Loaded {len(stats):,} records")
        print(f"Seasons: {stats['season'].unique()}")
        print(f"Positions: {stats['position'].unique()}")
    elif args.stats_only:
        stats = loader.load_player_stats_range(args.start, args.end)
        season_totals = loader.compute_season_totals(stats)
        print(f"\nWeekly stats: {len(stats):,}")
        print(f"Season totals: {len(season_totals):,}")
    else:
        data = loader.load_all_historical_data(args.start, args.end)
        report = loader.get_data_coverage_report(data)
        print("\nData Coverage Report:")
        for key, info in report.items():
            print(f"\n{key}:")
            for k, v in info.items():
                print(f"  {k}: {v}")
