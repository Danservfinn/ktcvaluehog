"""NFLverse data loader for all 28 datasets.

This loader provides access to comprehensive NFL data from nflverse repositories:
- Core player data (players, rosters, IDs)
- Statistics (player stats, team stats)
- Advanced analytics (NextGen, PFR, FTN charting)
- Context data (schedules, snap counts, depth charts)
- Historical data (draft picks, combine, contracts, trades)
- Fantasy data (rankings, opportunity metrics)

Data Sources:
- nflreadpy: Modern Python interface to nflverse
- Direct parquet downloads for datasets not in nflreadpy
"""

import ssl
from pathlib import Path
from typing import List, Dict, Optional, Union
from datetime import datetime
import pandas as pd

try:
    import polars as pl
    POLARS_AVAILABLE = True
except ImportError:
    POLARS_AVAILABLE = False

try:
    import nflreadpy as nfl
    NFLREADPY_AVAILABLE = True
except ImportError:
    NFLREADPY_AVAILABLE = False
    print("Warning: nflreadpy not available. Install with: pip install nflreadpy")

from ..config import RAW_DIR, HISTORICAL_SEASONS, CURRENT_SEASON


class NFLverseLoader:
    """Load all 28 NFLverse datasets with caching."""

    def __init__(self, cache_dir: Path = None):
        self.cache_dir = cache_dir or RAW_DIR / "nflverse"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Bypass SSL for direct downloads
        ssl._create_default_https_context = ssl._create_unverified_context

        if not NFLREADPY_AVAILABLE:
            raise ImportError("nflreadpy is required. Install with: pip install nflreadpy polars")

    def _to_pandas(self, data) -> pd.DataFrame:
        """Convert Polars DataFrame to Pandas if needed."""
        if hasattr(data, 'to_pandas'):
            return data.to_pandas()
        return data

    def _get_seasons(self, seasons: List[int] = None) -> List[int]:
        """Get seasons list with defaults."""
        return seasons or [CURRENT_SEASON]

    # =========================================================================
    # CORE PLAYER DATA (4 datasets)
    # =========================================================================

    def load_players(self) -> pd.DataFrame:
        """Master player database with all attributes.

        Contains: gsis_id, display_name, position, team, birth_date,
                  height, weight, college, status, years_exp, etc.

        Returns:
            DataFrame with ~5000 active/recent players
        """
        data = nfl.load_players()
        return self._to_pandas(data)

    def load_ff_playerids(self) -> pd.DataFrame:
        """Cross-platform player ID mapping.

        Maps IDs between: gsis_id, sleeper_id, espn_id, yahoo_id,
                          fleaflicker_id, rotowire_id, sportradar_id,
                          pfr_id, pff_id, fantasy_data_id, mfl_id

        Essential for joining data across platforms.

        Returns:
            DataFrame with player ID mappings
        """
        data = nfl.load_ff_playerids()
        return self._to_pandas(data)

    def load_rosters(self, seasons: List[int] = None) -> pd.DataFrame:
        """Current season rosters.

        Contains: player_id, player_name, position, team,
                  jersey_number, status, height, weight

        Args:
            seasons: List of seasons to load

        Returns:
            DataFrame with roster data
        """
        seasons = self._get_seasons(seasons)
        data = nfl.load_rosters(seasons)
        return self._to_pandas(data)

    def load_rosters_weekly(self, seasons: List[int] = None) -> pd.DataFrame:
        """Weekly roster snapshots for tracking mid-season moves.

        More granular than load_rosters - shows roster changes week by week.

        Args:
            seasons: List of seasons to load

        Returns:
            DataFrame with weekly roster data
        """
        seasons = self._get_seasons(seasons)
        data = nfl.load_rosters_weekly(seasons)
        return self._to_pandas(data)

    # =========================================================================
    # STATISTICS (3 datasets)
    # =========================================================================

    def load_player_stats(self, seasons: List[int] = None,
                          summary_level: str = 'week') -> pd.DataFrame:
        """Weekly or seasonal player statistics.

        Contains 114 columns including:
        - Passing: completions, attempts, yards, tds, interceptions, sacks, epa
        - Rushing: carries, yards, tds, fumbles, epa
        - Receiving: targets, receptions, yards, tds, yac, epa
        - Fantasy: fantasy_points, fantasy_points_ppr

        Args:
            seasons: List of seasons to load
            summary_level: 'week' for weekly, 'reg' for regular season totals

        Returns:
            DataFrame with player statistics
        """
        seasons = self._get_seasons(seasons)
        data = nfl.load_player_stats(seasons, summary_level=summary_level)
        return self._to_pandas(data)

    def load_team_stats(self, seasons: List[int] = None) -> pd.DataFrame:
        """Team-level offensive/defensive statistics.

        Contains 102 columns including pass/rush rates, efficiency metrics,
        EPA, explosive play rates, etc.

        Args:
            seasons: List of seasons to load

        Returns:
            DataFrame with team statistics
        """
        seasons = self._get_seasons(seasons)
        # team_stats may need direct download
        try:
            data = nfl.load_team_stats(seasons)
            return self._to_pandas(data)
        except:
            # Fallback to direct parquet download
            base_url = "https://github.com/nflverse/nflverse-data/releases/download/weekly_player_stats"
            return pd.read_parquet(f"{base_url}/team_stats_{seasons[0]}.parquet")

    def load_pbp(self, seasons: List[int] = None) -> pd.DataFrame:
        """Play-by-play data (372 columns).

        WARNING: This is a very large dataset. Consider filtering or using
        load_ftn_charting() for play-level analysis.

        Contains detailed information for every play including:
        - Pre-snap: formation, personnel, defenders in box
        - Play result: yards gained, EPA, WPA, CPOE
        - Player involvement: passer, rusher, receiver IDs

        Args:
            seasons: List of seasons to load

        Returns:
            DataFrame with play-by-play data
        """
        seasons = self._get_seasons(seasons)
        data = nfl.load_pbp(seasons)
        return self._to_pandas(data)

    # =========================================================================
    # ADVANCED ANALYTICS (5 datasets)
    # =========================================================================

    def load_nextgen_stats(self, seasons: List[int] = None,
                           stat_type: str = 'passing') -> pd.DataFrame:
        """NFL Next Gen Stats.

        Available stat_types:
        - 'passing': time_to_throw, air_yards, aggressiveness, CPOE
        - 'receiving': separation, cushion, yac, intended_air_yards
        - 'rushing': time_to_los, efficiency, 8+_defenders_rate

        Args:
            seasons: List of seasons to load
            stat_type: 'passing', 'receiving', or 'rushing'

        Returns:
            DataFrame with Next Gen Stats
        """
        seasons = self._get_seasons(seasons)
        data = nfl.load_nextgen_stats(seasons, stat_type=stat_type)
        return self._to_pandas(data)

    def load_pfr_advstats(self, seasons: List[int] = None,
                          stat_type: str = 'pass',
                          summary_level: str = 'week') -> pd.DataFrame:
        """Pro Football Reference advanced stats.

        Available stat_types:
        - 'pass': pressure rate, on-target throws, bad throws, pocket time
        - 'rush': yards before contact, broken tackles
        - 'rec': ADOT, YAC, broken tackles, drop rate, target share
        - 'def': pass rush stats, coverage stats

        Args:
            seasons: List of seasons to load
            stat_type: 'pass', 'rush', 'rec', or 'def'
            summary_level: 'week' or 'season'

        Returns:
            DataFrame with PFR advanced stats
        """
        seasons = self._get_seasons(seasons)
        data = nfl.load_pfr_advstats(seasons, stat_type=stat_type, summary_level=summary_level)
        return self._to_pandas(data)

    def load_ftn_charting(self, seasons: List[int] = None) -> pd.DataFrame:
        """FTN play charting data (29 columns).

        HIGH VALUE for dynasty analysis! Contains:
        - is_play_action, is_rpo, is_screen_pass
        - is_qb_out_of_pocket, is_throw_away
        - is_interception_worthy, is_catchable_ball
        - is_contested_ball, is_drop, is_created_reception
        - n_blitzers, n_pass_rushers, n_defense_box

        Args:
            seasons: List of seasons to load

        Returns:
            DataFrame with FTN charting data
        """
        seasons = self._get_seasons(seasons)
        data = nfl.load_ftn_charting(seasons)
        return self._to_pandas(data)

    def load_ff_opportunity(self, seasons: List[int] = None,
                            stat_type: str = 'weekly') -> pd.DataFrame:
        """Fantasy opportunity metrics (159 columns).

        Contains expected fantasy points, opportunity scores,
        and efficiency metrics.

        Args:
            seasons: List of seasons to load
            stat_type: 'weekly' or other

        Returns:
            DataFrame with fantasy opportunity data
        """
        seasons = self._get_seasons(seasons)
        data = nfl.load_ff_opportunity(seasons, stat_type=stat_type)
        return self._to_pandas(data)

    def load_espn_qbr(self) -> Dict[str, pd.DataFrame]:
        """ESPN QBR data (not in nflreadpy, direct download).

        Returns season and weekly QBR metrics.

        Returns:
            Dict with 'season' and 'week' DataFrames
        """
        base_url = "https://github.com/nflverse/nflverse-data/releases/download/espn_data"
        return {
            'season': pd.read_parquet(f"{base_url}/qbr_season_level.parquet"),
            'week': pd.read_parquet(f"{base_url}/qbr_week_level.parquet")
        }

    # =========================================================================
    # CONTEXT DATA (5 datasets)
    # =========================================================================

    def load_teams(self) -> pd.DataFrame:
        """NFL teams metadata.

        Contains: team_abbr, team_name, team_nick, conference, division,
                  team_color, team_color2, team_logo_wikipedia

        Returns:
            DataFrame with team information
        """
        data = nfl.load_teams()
        return self._to_pandas(data)

    def load_schedules(self, seasons: List[int] = None) -> pd.DataFrame:
        """Game schedules with results.

        Contains: game_id, season, week, home_team, away_team,
                  home_score, away_score, spread_line, total_line

        Args:
            seasons: List of seasons to load

        Returns:
            DataFrame with schedule data
        """
        seasons = self._get_seasons(seasons)
        data = nfl.load_schedules(seasons)
        return self._to_pandas(data)

    def load_snap_counts(self, seasons: List[int] = None) -> pd.DataFrame:
        """Player snap counts from PFR.

        Contains: offense_snaps, offense_pct, defense_snaps, defense_pct,
                  st_snaps, st_pct

        Available since 2012.

        Args:
            seasons: List of seasons to load

        Returns:
            DataFrame with snap count data
        """
        seasons = self._get_seasons(seasons)
        data = nfl.load_snap_counts(seasons)
        return self._to_pandas(data)

    def load_depth_charts(self, seasons: List[int] = None) -> pd.DataFrame:
        """Team depth charts.

        Contains position depth for each team by week.

        Args:
            seasons: List of seasons to load

        Returns:
            DataFrame with depth chart data
        """
        seasons = self._get_seasons(seasons)
        data = nfl.load_depth_charts(seasons)
        return self._to_pandas(data)

    def load_officials(self, seasons: List[int] = None) -> pd.DataFrame:
        """Game officials data.

        Contains referee assignments for each game.

        Args:
            seasons: List of seasons to load

        Returns:
            DataFrame with officials data
        """
        seasons = self._get_seasons(seasons)
        data = nfl.load_officials(seasons)
        return self._to_pandas(data)

    # =========================================================================
    # HISTORICAL DATA (4 datasets)
    # =========================================================================

    def load_draft_picks(self) -> pd.DataFrame:
        """Historical NFL draft picks.

        Contains: season, round, pick, team, player_name, position,
                  college, pfr_player_id, age

        Returns:
            DataFrame with all historical draft picks
        """
        data = nfl.load_draft_picks()
        return self._to_pandas(data)

    def load_combine(self) -> pd.DataFrame:
        """NFL Scouting Combine results.

        Contains: player_name, pos, forty, bench, vertical, broad_jump,
                  three_cone, shuttle, ht, wt, pfr_id

        Returns:
            DataFrame with combine data
        """
        data = nfl.load_combine()
        return self._to_pandas(data)

    def load_contracts(self) -> pd.DataFrame:
        """Player contracts from OverTheCap.

        Contains: player, position, team, year_signed, years, value,
                  apy, guaranteed, apy_cap_pct, inflated_value

        Returns:
            DataFrame with contract data
        """
        data = nfl.load_contracts()
        return self._to_pandas(data)

    def load_trades(self) -> pd.DataFrame:
        """NFL trades history.

        Contains trade details including teams involved, assets exchanged.

        Returns:
            DataFrame with trade data
        """
        data = nfl.load_trades()
        return self._to_pandas(data)

    # =========================================================================
    # FANTASY DATA (3 datasets)
    # =========================================================================

    def load_ff_rankings(self) -> pd.DataFrame:
        """Expert consensus fantasy rankings.

        Contains aggregate rankings from multiple analysts.

        Returns:
            DataFrame with fantasy rankings
        """
        data = nfl.load_ff_rankings()
        return self._to_pandas(data)

    def load_injuries(self, seasons: List[int] = None) -> pd.DataFrame:
        """Player injury reports.

        Contains: week, team, player, position, report_primary_injury,
                  report_secondary_injury, report_status

        Args:
            seasons: List of seasons to load

        Returns:
            DataFrame with injury data
        """
        seasons = self._get_seasons(seasons)
        data = nfl.load_injuries(seasons)
        return self._to_pandas(data)

    def load_participation(self, seasons: List[int] = None) -> pd.DataFrame:
        """Play participation data.

        Shows which players were on field for each play.

        Args:
            seasons: List of seasons to load

        Returns:
            DataFrame with participation data
        """
        seasons = self._get_seasons(seasons)
        data = nfl.load_participation(seasons)
        return self._to_pandas(data)

    # =========================================================================
    # CONVENIENCE METHODS
    # =========================================================================

    def load_all_nextgen(self, seasons: List[int] = None) -> Dict[str, pd.DataFrame]:
        """Load all Next Gen Stats types."""
        seasons = self._get_seasons(seasons)
        return {
            'passing': self.load_nextgen_stats(seasons, 'passing'),
            'receiving': self.load_nextgen_stats(seasons, 'receiving'),
            'rushing': self.load_nextgen_stats(seasons, 'rushing')
        }

    def load_all_pfr(self, seasons: List[int] = None) -> Dict[str, pd.DataFrame]:
        """Load all PFR advanced stats types."""
        seasons = self._get_seasons(seasons)
        return {
            'pass': self.load_pfr_advstats(seasons, 'pass'),
            'rush': self.load_pfr_advstats(seasons, 'rush'),
            'rec': self.load_pfr_advstats(seasons, 'rec'),
            'def': self.load_pfr_advstats(seasons, 'def')
        }

    def load_dynasty_core(self, seasons: List[int] = None) -> Dict[str, pd.DataFrame]:
        """Load core datasets needed for dynasty analysis.

        Returns combined dict of essential data.
        """
        seasons = self._get_seasons(seasons)

        print(f"Loading dynasty core data for seasons: {seasons}")

        data = {}

        print("  Loading players...")
        data['players'] = self.load_players()

        print("  Loading player IDs...")
        data['player_ids'] = self.load_ff_playerids()

        print("  Loading rosters...")
        data['rosters'] = self.load_rosters(seasons)

        print("  Loading player stats...")
        data['player_stats'] = self.load_player_stats(seasons, 'week')

        print("  Loading snap counts...")
        try:
            data['snap_counts'] = self.load_snap_counts(seasons)
        except Exception as e:
            print(f"    Warning: Could not load snap counts: {e}")
            data['snap_counts'] = pd.DataFrame()

        print("  Loading teams...")
        data['teams'] = self.load_teams()

        print("  Loading schedules...")
        data['schedules'] = self.load_schedules(seasons)

        print("  Loading draft picks...")
        data['draft_picks'] = self.load_draft_picks()

        print("  Loading combine...")
        data['combine'] = self.load_combine()

        print("  Loading contracts...")
        try:
            data['contracts'] = self.load_contracts()
        except Exception as e:
            print(f"    Warning: Could not load contracts: {e}")
            data['contracts'] = pd.DataFrame()

        print("Done loading core data.")
        return data

    def load_advanced_analytics(self, seasons: List[int] = None) -> Dict[str, pd.DataFrame]:
        """Load all advanced analytics datasets."""
        seasons = self._get_seasons(seasons)

        print(f"Loading advanced analytics for seasons: {seasons}")

        data = {}

        print("  Loading Next Gen Stats...")
        data['ngs'] = self.load_all_nextgen(seasons)

        print("  Loading PFR advanced stats...")
        data['pfr'] = self.load_all_pfr(seasons)

        print("  Loading FTN charting...")
        try:
            data['ftn'] = self.load_ftn_charting(seasons)
        except Exception as e:
            print(f"    Warning: Could not load FTN charting: {e}")
            data['ftn'] = pd.DataFrame()

        print("  Loading fantasy opportunity...")
        try:
            data['ff_opportunity'] = self.load_ff_opportunity(seasons)
        except Exception as e:
            print(f"    Warning: Could not load fantasy opportunity: {e}")
            data['ff_opportunity'] = pd.DataFrame()

        print("  Loading ESPN QBR...")
        try:
            data['espn_qbr'] = self.load_espn_qbr()
        except Exception as e:
            print(f"    Warning: Could not load ESPN QBR: {e}")
            data['espn_qbr'] = {'season': pd.DataFrame(), 'week': pd.DataFrame()}

        print("Done loading advanced analytics.")
        return data

    def get_data_summary(self) -> Dict[str, Dict]:
        """Get summary of available data without loading full datasets."""
        summary = {}

        datasets = [
            ('players', lambda: self.load_players()),
            ('player_ids', lambda: self.load_ff_playerids()),
            ('teams', lambda: self.load_teams()),
            ('draft_picks', lambda: self.load_draft_picks()),
            ('combine', lambda: self.load_combine()),
        ]

        for name, loader in datasets:
            try:
                df = loader()
                summary[name] = {
                    'rows': len(df),
                    'columns': len(df.columns),
                    'column_names': list(df.columns)[:10]
                }
            except Exception as e:
                summary[name] = {'error': str(e)}

        return summary
