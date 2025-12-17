"""
2025 NFL Season Data Loader
============================
Fetches current 2025 season data from nflverse using nflreadpy.

Key data sources:
- Player stats (weekly/season)
- Rosters (current/weekly)
- Snap counts
- Next Gen Stats
- Play-by-play (optional - large)

Note: nflreadpy uses Polars by default. Use .to_pandas() to convert.
"""

import logging
from typing import Optional, List, Dict
from datetime import datetime

import pandas as pd

try:
    import nflreadpy as nfl
    NFLREADPY_AVAILABLE = True
except ImportError:
    NFLREADPY_AVAILABLE = False
    print("Warning: nflreadpy not available. Install with: pip install nflreadpy")

logger = logging.getLogger(__name__)


class NFL2025Loader:
    """
    Load 2025 NFL season data from nflverse via nflreadpy.

    Key methods:
    - load_player_stats(): Weekly player statistics
    - load_rosters(): Current roster data
    - load_snap_counts(): Playing time data
    - load_nextgen_stats(): Advanced analytics
    - get_season_totals(): Aggregated season stats
    - get_recent_trend(): Recent performance trends
    """

    FANTASY_POSITIONS = ['QB', 'RB', 'WR', 'TE']
    SEASON = 2025

    def __init__(self):
        """Initialize the 2025 NFL loader."""
        if not NFLREADPY_AVAILABLE:
            raise ImportError("nflreadpy is required. Install with: pip install nflreadpy polars")

        self.season = self.SEASON
        self._cache = {}

    def _to_pandas(self, data) -> pd.DataFrame:
        """Convert Polars DataFrame to Pandas if needed."""
        if hasattr(data, 'to_pandas'):
            return data.to_pandas()
        return data

    # =========================================================================
    # PLAYER STATS
    # =========================================================================

    def load_player_stats(
        self,
        weeks: Optional[List[int]] = None,
        positions: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Load 2025 weekly player statistics.

        Returns DataFrame with columns:
        - player_id, player_display_name, position, team
        - week, season_type, opponent_team
        - Passing: completions, attempts, passing_yards, passing_tds, interceptions
        - Rushing: carries, rushing_yards, rushing_tds
        - Receiving: targets, receptions, receiving_yards, receiving_tds
        - Fantasy: fantasy_points, fantasy_points_ppr
        - Advanced: target_share, air_yards_share, wopr, racr

        Args:
            weeks: Optional list of weeks to filter
            positions: Optional list of positions to filter (default: QB, RB, WR, TE)

        Returns:
            DataFrame with weekly player stats
        """
        logger.info(f"Loading 2025 player stats...")

        try:
            stats = nfl.load_player_stats([self.season])
            df = self._to_pandas(stats)

            # Filter to fantasy positions
            positions = positions or self.FANTASY_POSITIONS
            if 'position' in df.columns:
                df = df[df['position'].isin(positions)]

            # Filter to specific weeks
            if weeks and 'week' in df.columns:
                df = df[df['week'].isin(weeks)]

            logger.info(f"Loaded {len(df)} stat rows")
            return df

        except Exception as e:
            logger.error(f"Failed to load player stats: {e}")
            return pd.DataFrame()

    def load_player_stats_seasonal(self, positions: Optional[List[str]] = None) -> pd.DataFrame:
        """Load season-aggregated player stats."""
        try:
            stats = nfl.load_player_stats([self.season], summary_level='reg')
            df = self._to_pandas(stats)

            positions = positions or self.FANTASY_POSITIONS
            if 'position' in df.columns:
                df = df[df['position'].isin(positions)]

            return df
        except Exception as e:
            logger.error(f"Failed to load seasonal stats: {e}")
            return pd.DataFrame()

    # =========================================================================
    # ROSTERS
    # =========================================================================

    def load_rosters(self) -> pd.DataFrame:
        """
        Load current 2025 rosters.

        Returns DataFrame with:
        - player_id, player_name, full_name
        - position, team, jersey_number
        - height, weight, age, years_exp
        - college, status, headshot_url
        """
        logger.info("Loading 2025 rosters...")

        try:
            rosters = nfl.load_rosters([self.season])
            df = self._to_pandas(rosters)
            logger.info(f"Loaded {len(df)} roster entries")
            return df
        except Exception as e:
            logger.error(f"Failed to load rosters: {e}")
            return pd.DataFrame()

    def load_rosters_weekly(self) -> pd.DataFrame:
        """Load weekly roster snapshots for tracking changes."""
        try:
            rosters = nfl.load_rosters_weekly([self.season])
            return self._to_pandas(rosters)
        except Exception as e:
            logger.warning(f"Weekly rosters not available: {e}")
            return pd.DataFrame()

    # =========================================================================
    # SNAP COUNTS
    # =========================================================================

    def load_snap_counts(self) -> pd.DataFrame:
        """
        Load snap count data for 2025.

        Returns DataFrame with:
        - player, team, position, week
        - offense_snaps, offense_pct
        - defense_snaps, defense_pct
        - st_snaps, st_pct
        """
        logger.info("Loading 2025 snap counts...")

        try:
            snaps = nfl.load_snap_counts([self.season])
            df = self._to_pandas(snaps)
            logger.info(f"Loaded {len(df)} snap count records")
            return df
        except Exception as e:
            logger.warning(f"Snap counts error: {e}")
            return pd.DataFrame()

    # =========================================================================
    # NEXT GEN STATS
    # =========================================================================

    def load_nextgen_stats(self, stat_type: str = 'receiving') -> pd.DataFrame:
        """
        Load NFL Next Gen Stats for 2025.

        Args:
            stat_type: 'passing', 'rushing', or 'receiving'

        Returns:
            DataFrame with NGS metrics (separation, cushion, time_to_throw, etc.)
        """
        logger.info(f"Loading 2025 NGS {stat_type}...")

        try:
            ngs = nfl.load_nextgen_stats([self.season], stat_type=stat_type)
            df = self._to_pandas(ngs)
            logger.info(f"Loaded {len(df)} NGS records")
            return df
        except Exception as e:
            logger.warning(f"NGS error: {e}")
            return pd.DataFrame()

    def load_all_nextgen(self) -> Dict[str, pd.DataFrame]:
        """Load all NGS stat types."""
        return {
            'passing': self.load_nextgen_stats('passing'),
            'receiving': self.load_nextgen_stats('receiving'),
            'rushing': self.load_nextgen_stats('rushing')
        }

    # =========================================================================
    # PLAY-BY-PLAY (Optional - Large)
    # =========================================================================

    def load_pbp(self, weeks: Optional[List[int]] = None) -> pd.DataFrame:
        """
        Load play-by-play data (WARNING: Large dataset).

        Args:
            weeks: Optional list of weeks to filter

        Returns:
            DataFrame with ~300+ columns per play
        """
        logger.info("Loading 2025 play-by-play (this may take a while)...")

        try:
            pbp = nfl.load_pbp([self.season])
            df = self._to_pandas(pbp)

            if weeks and 'week' in df.columns:
                df = df[df['week'].isin(weeks)]

            logger.info(f"Loaded {len(df)} plays")
            return df
        except Exception as e:
            logger.error(f"PBP error: {e}")
            return pd.DataFrame()

    # =========================================================================
    # AGGREGATIONS
    # =========================================================================

    def get_season_totals(self, positions: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Calculate season totals from weekly data.

        Returns aggregated stats per player with:
        - games played, total fantasy points
        - per-game averages (PPG)
        - efficiency metrics
        """
        df = self.load_player_stats(positions=positions)

        if df.empty:
            return pd.DataFrame()

        # Only aggregate columns that exist
        agg_dict = {
            'week': 'count',  # games played
        }

        # Add columns only if they exist
        optional_sum_cols = [
            'fantasy_points_ppr', 'fantasy_points',
            'passing_yards', 'passing_tds', 'passing_interceptions',
            'rushing_yards', 'rushing_tds', 'carries',
            'targets', 'receptions', 'receiving_yards', 'receiving_tds',
        ]
        for col in optional_sum_cols:
            if col in df.columns:
                agg_dict[col] = 'sum'

        # Add optional columns if they exist
        optional_cols = ['target_share', 'air_yards_share', 'wopr']
        for col in optional_cols:
            if col in df.columns:
                agg_dict[col] = 'mean'

        # Group and aggregate
        group_cols = ['player_id', 'player_display_name', 'position', 'team']
        group_cols = [c for c in group_cols if c in df.columns]

        if not group_cols:
            return pd.DataFrame()

        totals = df.groupby(group_cols).agg(agg_dict).reset_index()

        # Rename columns
        rename_map = {
            'week': 'games',
            'player_display_name': 'player',
        }
        if 'passing_interceptions' in totals.columns:
            rename_map['passing_interceptions'] = 'ints'
        totals = totals.rename(columns=rename_map)

        # Calculate per-game averages
        if 'fantasy_points_ppr' in totals.columns and 'games' in totals.columns:
            totals['ppg_ppr'] = totals['fantasy_points_ppr'] / totals['games']
            totals['ppg_standard'] = totals['fantasy_points'] / totals['games']

        return totals.sort_values('fantasy_points_ppr', ascending=False)

    def get_recent_trend(self, player_id: str, weeks: int = 4) -> Dict:
        """
        Calculate recent performance trend for a player.

        Args:
            player_id: Player's unique ID
            weeks: Number of recent weeks to analyze

        Returns:
            Dict with trend data (recent_ppg, prior_ppg, pct_change, trend)
        """
        df = self.load_player_stats()

        if df.empty or 'player_id' not in df.columns:
            return {"trend": "INSUFFICIENT_DATA"}

        player_df = df[df['player_id'] == player_id].sort_values('week', ascending=False)

        if len(player_df) < 2:
            return {"trend": "INSUFFICIENT_DATA"}

        recent = player_df.head(weeks)
        older = player_df.iloc[weeks:weeks*2] if len(player_df) > weeks else pd.DataFrame()

        recent_ppg = recent['fantasy_points_ppr'].mean()
        older_ppg = older['fantasy_points_ppr'].mean() if len(older) > 0 else recent_ppg

        pct_change = ((recent_ppg - older_ppg) / older_ppg * 100) if older_ppg > 0 else 0

        if pct_change > 10:
            trend = "RISING"
        elif pct_change < -10:
            trend = "FALLING"
        else:
            trend = "STABLE"

        return {
            "player_id": player_id,
            "recent_ppg": round(recent_ppg, 2),
            "prior_ppg": round(older_ppg, 2),
            "pct_change": round(pct_change, 1),
            "trend": trend,
            "weeks_analyzed": len(recent)
        }

    def get_trending_players(self, weeks: int = 4, min_change: float = 15) -> pd.DataFrame:
        """
        Find players with significant recent performance changes.

        Args:
            weeks: Number of weeks for recent vs prior comparison
            min_change: Minimum % change to include

        Returns:
            DataFrame with trending players
        """
        df = self.load_player_stats()

        if df.empty:
            return pd.DataFrame()

        # Group by player
        players = df.groupby('player_id')

        trends = []
        for player_id, player_df in players:
            player_df = player_df.sort_values('week', ascending=False)

            if len(player_df) < weeks * 2:
                continue

            recent = player_df.head(weeks)
            prior = player_df.iloc[weeks:weeks*2]

            recent_ppg = recent['fantasy_points_ppr'].mean()
            prior_ppg = prior['fantasy_points_ppr'].mean()

            if prior_ppg == 0:
                continue

            pct_change = ((recent_ppg - prior_ppg) / prior_ppg) * 100

            if abs(pct_change) >= min_change:
                trends.append({
                    'player_id': player_id,
                    'player': player_df.iloc[0].get('player_display_name', ''),
                    'position': player_df.iloc[0].get('position', ''),
                    'team': player_df.iloc[0].get('recent_team', ''),
                    'recent_ppg': round(recent_ppg, 1),
                    'prior_ppg': round(prior_ppg, 1),
                    'pct_change': round(pct_change, 1),
                    'trend': 'RISING' if pct_change > 0 else 'FALLING'
                })

        return pd.DataFrame(trends).sort_values('pct_change', ascending=False)

    # =========================================================================
    # POSITION-SPECIFIC LEADERS
    # =========================================================================

    def get_position_leaders(self, position: str, stat: str = 'fantasy_points_ppr', limit: int = 20) -> pd.DataFrame:
        """
        Get leaders for a specific position and stat.

        Args:
            position: QB, RB, WR, or TE
            stat: Stat to rank by (default: fantasy_points_ppr)
            limit: Number of players to return
        """
        totals = self.get_season_totals(positions=[position])

        if totals.empty or stat not in totals.columns:
            return pd.DataFrame()

        return totals.nlargest(limit, stat)


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    loader = NFL2025Loader()

    print("\n" + "="*60)
    print("2025 NFL Season Data Loader")
    print("="*60)

    # Test loading
    print("\nLoading season totals...")
    totals = loader.get_season_totals()

    if not totals.empty:
        print(f"\nLoaded {len(totals)} players with 2025 stats")

        print("\nTop 20 Fantasy Performers (PPR):")
        print("-"*60)
        cols = ['player', 'position', 'team', 'games', 'fantasy_points_ppr', 'ppg_ppr']
        cols = [c for c in cols if c in totals.columns]
        print(totals.head(20)[cols].to_string(index=False))

        print("\nPosition Leaders:")
        print("-"*60)
        for pos in ['QB', 'RB', 'WR', 'TE']:
            leaders = loader.get_position_leaders(pos, limit=5)
            if not leaders.empty:
                print(f"\n{pos} Top 5:")
                print(leaders[['player', 'team', 'games', 'ppg_ppr']].to_string(index=False))

        print("\nTrending Players (Last 4 Weeks):")
        print("-"*60)
        trends = loader.get_trending_players()
        if not trends.empty:
            print(trends.head(15).to_string(index=False))
    else:
        print("No 2025 data available yet")
