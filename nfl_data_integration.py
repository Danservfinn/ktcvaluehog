#!/usr/bin/env python3
"""
Dynasty Edge - NFL Data Integration (nflverse)

Pulls comprehensive NFL statistics from nflverse repositories and integrates
them into the Dynasty Edge Neo4j database for enhanced player analysis.

Data Sources:
- nflreadpy: Modern Python port of nflreadr (recommended)
- nfl_data_py: Legacy library (deprecated but still works)

Key Data Available:
- Play-by-play data (since 1999)
- Weekly/seasonal player stats
- Snap counts and target share
- Next Gen Stats (since 2016)
- Pro Football Reference advanced stats
- Player ID mappings across platforms

Installation:
    pip install nflreadpy polars  # New library (uses Polars)
    # OR
    pip install nfl-data-py       # Legacy library (uses Pandas)
"""

import os
from datetime import datetime
from typing import Optional, List, Dict, Any
import pandas as pd
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

# Try to import nflreadpy (new), fall back to nfl_data_py (legacy)
NFLREADPY_AVAILABLE = False
NFL_DATA_PY_AVAILABLE = False

try:
    import nflreadpy as nfl
    NFLREADPY_AVAILABLE = True
    print("✅ Using nflreadpy (recommended)")
except ImportError:
    try:
        import nfl_data_py as nfl
        NFL_DATA_PY_AVAILABLE = True
        print("⚠️  Using nfl_data_py (deprecated - consider switching to nflreadpy)")
    except ImportError:
        print("❌ No NFL data library available. Install with:")
        print("   pip install nflreadpy polars  # Recommended")
        print("   pip install nfl-data-py       # Legacy")

# Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")


class NFLDataFetcher:
    """
    Fetches NFL data from nflverse repositories.
    Works with both nflreadpy (new) and nfl_data_py (legacy).
    """
    
    def __init__(self):
        self.using_nflreadpy = NFLREADPY_AVAILABLE
        self.current_season = self._get_current_season()
        print(f"📅 Current NFL season: {self.current_season}")
    
    def _get_current_season(self) -> int:
        """Determine current NFL season."""
        now = datetime.now()
        # NFL season starts in September
        if now.month >= 9:
            return now.year
        return now.year - 1
    
    def _to_pandas(self, data) -> pd.DataFrame:
        """Convert Polars DataFrame to Pandas if needed."""
        if hasattr(data, 'to_pandas'):
            return data.to_pandas()
        return data
    
    # =========================================================================
    # PLAYER STATISTICS
    # =========================================================================
    
    def get_weekly_stats(self, seasons: List[int] = None) -> pd.DataFrame:
        """
        Get weekly player statistics.
        
        Includes: completions, attempts, passing_yards, passing_tds, interceptions,
                  carries, rushing_yards, rushing_tds, targets, receptions, 
                  receiving_yards, receiving_tds, fantasy_points, etc.
        """
        seasons = seasons or [self.current_season]
        
        if self.using_nflreadpy:
            data = nfl.load_player_stats(seasons=seasons, summary_level='week')
            return self._to_pandas(data)
        else:
            return nfl.import_weekly_data(seasons)
    
    def get_seasonal_stats(self, seasons: List[int] = None) -> pd.DataFrame:
        """
        Get season-aggregated player statistics.
        
        Includes market share stats: target_share, air_yards_share, wopr,
        dominator_rating, receiving_yards_share, etc.
        """
        seasons = seasons or [self.current_season]
        
        if self.using_nflreadpy:
            data = nfl.load_player_stats(seasons=seasons, summary_level='reg')
            return self._to_pandas(data)
        else:
            return nfl.import_seasonal_data(seasons)
    
    # =========================================================================
    # SNAP COUNTS & USAGE
    # =========================================================================
    
    def get_snap_counts(self, seasons: List[int] = None) -> pd.DataFrame:
        """
        Get snap count data from Pro Football Reference.
        
        Includes: offense_snaps, offense_pct, defense_snaps, defense_pct,
                  st_snaps, st_pct
        
        Available since 2012.
        """
        seasons = seasons or [self.current_season]
        
        if self.using_nflreadpy:
            data = nfl.load_snap_counts(seasons=seasons)
            return self._to_pandas(data)
        else:
            return nfl.import_snap_counts(seasons)
    
    # =========================================================================
    # NEXT GEN STATS (Advanced Metrics)
    # =========================================================================
    
    def get_nextgen_passing(self, seasons: List[int] = None) -> pd.DataFrame:
        """
        Get Next Gen Stats for passing.
        
        Includes: avg_time_to_throw, avg_completed_air_yards, avg_intended_air_yards,
                  avg_air_yards_differential, aggressiveness, max_completed_air_distance,
                  avg_air_yards_to_sticks, attempts, pass_yards, pass_touchdowns,
                  interceptions, passer_rating, completions, completion_percentage,
                  expected_completion_percentage, completion_percentage_above_expectation
        
        Available since 2016.
        """
        seasons = seasons or [self.current_season]
        
        if self.using_nflreadpy:
            data = nfl.load_nextgen_stats(seasons=seasons, stat_type='passing')
            return self._to_pandas(data)
        else:
            return nfl.import_ngs_data('passing', seasons)
    
    def get_nextgen_receiving(self, seasons: List[int] = None) -> pd.DataFrame:
        """
        Get Next Gen Stats for receiving.
        
        Includes: avg_cushion, avg_separation, avg_intended_air_yards, 
                  percent_share_of_intended_air_yards, receptions, targets,
                  catch_percentage, yards, rec_touchdowns, avg_yac,
                  avg_expected_yac, avg_yac_above_expectation
        
        Available since 2016.
        """
        seasons = seasons or [self.current_season]
        
        if self.using_nflreadpy:
            data = nfl.load_nextgen_stats(seasons=seasons, stat_type='receiving')
            return self._to_pandas(data)
        else:
            return nfl.import_ngs_data('receiving', seasons)
    
    def get_nextgen_rushing(self, seasons: List[int] = None) -> pd.DataFrame:
        """
        Get Next Gen Stats for rushing.
        
        Includes: efficiency, percent_attempts_gte_eight_defenders, 
                  avg_time_to_los, rush_attempts, rush_yards, 
                  expected_rush_yards, rush_yards_over_expected,
                  avg_rush_yards, rush_touchdowns
        
        Available since 2016.
        """
        seasons = seasons or [self.current_season]
        
        if self.using_nflreadpy:
            data = nfl.load_nextgen_stats(seasons=seasons, stat_type='rushing')
            return self._to_pandas(data)
        else:
            return nfl.import_ngs_data('rushing', seasons)
    
    # =========================================================================
    # PRO FOOTBALL REFERENCE ADVANCED STATS
    # =========================================================================
    
    def get_pfr_passing(self, seasons: List[int] = None) -> pd.DataFrame:
        """
        Get PFR advanced passing stats.
        
        Includes: times_blitzed, times_hurried, times_hit, times_pressured,
                  pressure_pct, batted_balls, on_tgt_throws, bad_throws,
                  drop_pct, pocket_time
        
        Available since 2018.
        """
        seasons = seasons or [self.current_season]
        
        if self.using_nflreadpy:
            data = nfl.load_pfr_advstats(seasons=seasons, stat_type='pass', summary_level='week')
            return self._to_pandas(data)
        else:
            return nfl.import_weekly_pfr('pass', seasons)
    
    def get_pfr_receiving(self, seasons: List[int] = None) -> pd.DataFrame:
        """
        Get PFR advanced receiving stats.
        
        Includes: targets, rec, yds, td, first_downs, ybc, ybc_per_r,
                  yac, yac_per_r, adot, broken_tackles, rec_per_broken_tackle,
                  drops, drop_pct, target_share, air_yards_share, 
                  weighted_opportunity_rating
        
        Available since 2018.
        """
        seasons = seasons or [self.current_season]
        
        if self.using_nflreadpy:
            data = nfl.load_pfr_advstats(seasons=seasons, stat_type='rec', summary_level='week')
            return self._to_pandas(data)
        else:
            return nfl.import_weekly_pfr('rec', seasons)
    
    def get_pfr_rushing(self, seasons: List[int] = None) -> pd.DataFrame:
        """
        Get PFR advanced rushing stats.
        
        Includes: att, yds, td, first_downs, ybc, ybc_per_att,
                  yac, yac_per_att, broken_tackles, att_per_broken_tackle
        
        Available since 2018.
        """
        seasons = seasons or [self.current_season]
        
        if self.using_nflreadpy:
            data = nfl.load_pfr_advstats(seasons=seasons, stat_type='rush', summary_level='week')
            return self._to_pandas(data)
        else:
            return nfl.import_weekly_pfr('rush', seasons)
    
    # =========================================================================
    # ROSTERS & PLAYER INFO
    # =========================================================================
    
    def get_rosters(self, seasons: List[int] = None) -> pd.DataFrame:
        """
        Get NFL rosters.
        
        Includes: player_id, player_name, position, team, jersey_number,
                  status, height, weight, birth_date, college, gsis_id,
                  espn_id, sportradar_id, yahoo_id, rotowire_id, pff_id
        """
        seasons = seasons or [self.current_season]
        
        if self.using_nflreadpy:
            data = nfl.load_rosters(seasons=seasons)
            return self._to_pandas(data)
        else:
            return nfl.import_seasonal_rosters(seasons)
    
    def get_player_ids(self) -> pd.DataFrame:
        """
        Get player ID mappings across platforms.
        
        Maps IDs between: gsis_id, espn_id, yahoo_id, fleaflicker_id,
                          sleeper_id, rotowire_id, sportradar_id, pfr_id,
                          fantasy_data_id, mfl_id
        """
        if self.using_nflreadpy:
            data = nfl.load_players()
            return self._to_pandas(data)
        else:
            return nfl.import_ids()
    
    # =========================================================================
    # TEAM & SCHEDULE DATA
    # =========================================================================
    
    def get_schedules(self, seasons: List[int] = None) -> pd.DataFrame:
        """Get NFL schedules and game results."""
        seasons = seasons or [self.current_season]
        
        if self.using_nflreadpy:
            data = nfl.load_schedules(seasons=seasons)
            return self._to_pandas(data)
        else:
            return nfl.import_schedules(seasons)
    
    def get_team_info(self) -> pd.DataFrame:
        """Get team information (colors, logos, abbreviations)."""
        if self.using_nflreadpy:
            data = nfl.load_teams()
            return self._to_pandas(data)
        else:
            return nfl.import_team_desc()
    
    # =========================================================================
    # FANTASY-SPECIFIC DATA
    # =========================================================================
    
    def get_fantasy_rankings(self) -> pd.DataFrame:
        """Get fantasy football rankings/projections."""
        if self.using_nflreadpy:
            data = nfl.load_ff_rankings()
            return self._to_pandas(data)
        else:
            # Not available in legacy library
            return pd.DataFrame()
    
    # =========================================================================
    # AGGREGATED DATA FOR DYNASTY
    # =========================================================================
    
    def get_dynasty_metrics(self, seasons: List[int] = None) -> pd.DataFrame:
        """
        Aggregate key metrics relevant for dynasty fantasy football.
        
        Returns combined data with:
        - Weekly stats (targets, receptions, yards, TDs)
        - Snap percentages
        - Target share and air yards share
        - Fantasy points
        """
        seasons = seasons or [self.current_season]
        
        print(f"📊 Fetching dynasty metrics for seasons: {seasons}")
        
        # Get weekly stats
        weekly = self.get_weekly_stats(seasons)
        
        # Get snap counts
        try:
            snaps = self.get_snap_counts(seasons)
        except Exception as e:
            print(f"  ⚠️ Could not fetch snap counts: {e}")
            snaps = None
        
        # Get Next Gen receiving stats for target share
        try:
            ngs_rec = self.get_nextgen_receiving(seasons)
        except Exception as e:
            print(f"  ⚠️ Could not fetch Next Gen Stats: {e}")
            ngs_rec = None
        
        # Merge data
        result = weekly.copy()
        
        if snaps is not None and len(snaps) > 0:
            # Merge on player_id and week
            merge_cols = ['player_id', 'season', 'week']
            snap_cols = ['offense_pct', 'defense_pct'] if 'offense_pct' in snaps.columns else []
            if snap_cols:
                result = result.merge(
                    snaps[merge_cols + snap_cols],
                    on=merge_cols,
                    how='left'
                )
        
        if ngs_rec is not None and len(ngs_rec) > 0:
            # Merge target share from NGS
            merge_cols = ['player_id', 'season', 'week']
            ngs_cols = ['percent_share_of_intended_air_yards', 'avg_separation', 'avg_cushion']
            available_cols = [c for c in ngs_cols if c in ngs_rec.columns]
            if available_cols:
                result = result.merge(
                    ngs_rec[merge_cols + available_cols],
                    on=merge_cols,
                    how='left'
                )
        
        print(f"✅ Retrieved {len(result)} player-week records")
        return result


class NFLDataLoader:
    """
    Loads NFL data into the Dynasty Edge Neo4j database.
    """
    
    def __init__(self, uri: str = NEO4J_URI, user: str = NEO4J_USER, password: str = NEO4J_PASSWORD):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.fetcher = NFLDataFetcher()
        print(f"✅ Connected to Neo4j at {uri}")
    
    def close(self):
        self.driver.close()
    
    # =========================================================================
    # LOAD NFL TEAMS
    # =========================================================================
    
    def load_teams(self):
        """Load NFL team data into Neo4j."""
        teams = self.fetcher.get_team_info()
        
        with self.driver.session() as session:
            for _, team in teams.iterrows():
                session.run("""
                    MERGE (t:NFLTeam {team_abbr: $abbr})
                    SET t.team_name = $name,
                        t.team_nick = $nick,
                        t.team_conf = $conf,
                        t.team_division = $div,
                        t.team_color = $color,
                        t.team_color2 = $color2
                """, {
                    'abbr': team.get('team_abbr'),
                    'name': team.get('team_name'),
                    'nick': team.get('team_nick'),
                    'conf': team.get('team_conf'),
                    'div': team.get('team_division'),
                    'color': team.get('team_color'),
                    'color2': team.get('team_color2')
                })
        
        print(f"✅ Loaded {len(teams)} NFL teams")
    
    # =========================================================================
    # LOAD PLAYER ID MAPPINGS
    # =========================================================================
    
    def load_player_ids(self):
        """Load player ID mappings to link with Sleeper/KTC data."""
        ids = self.fetcher.get_player_ids()
        
        # Filter to relevant positions
        if 'position' in ids.columns:
            ids = ids[ids['position'].isin(['QB', 'RB', 'WR', 'TE'])]
        
        with self.driver.session() as session:
            for _, player in ids.iterrows():
                # Update existing players or create new ones
                session.run("""
                    MERGE (p:Player {gsis_id: $gsis_id})
                    SET p.espn_id = $espn_id,
                        p.yahoo_id = $yahoo_id,
                        p.sleeper_id = $sleeper_id,
                        p.pfr_id = $pfr_id,
                        p.rotowire_id = $rotowire_id,
                        p.sportradar_id = $sportradar_id
                """, {
                    'gsis_id': player.get('gsis_id'),
                    'espn_id': player.get('espn_id'),
                    'yahoo_id': player.get('yahoo_id'),
                    'sleeper_id': player.get('sleeper_id'),
                    'pfr_id': player.get('pfr_id'),
                    'rotowire_id': player.get('rotowire_id'),
                    'sportradar_id': player.get('sportradar_id')
                })
        
        print(f"✅ Loaded ID mappings for {len(ids)} players")
    
    # =========================================================================
    # LOAD WEEKLY STATS
    # =========================================================================
    
    def load_weekly_stats(self, seasons: List[int] = None):
        """
        Load weekly player statistics into Neo4j.
        Creates WeeklyStat nodes linked to Players.
        """
        stats = self.fetcher.get_weekly_stats(seasons)
        
        # Filter to skill positions
        if 'position' in stats.columns:
            stats = stats[stats['position'].isin(['QB', 'RB', 'WR', 'TE'])]
        
        count = 0
        with self.driver.session() as session:
            for _, row in stats.iterrows():
                try:
                    session.run("""
                        // Find or create player
                        MERGE (p:Player {gsis_id: $player_id})
                        SET p.name = coalesce(p.name, $player_name),
                            p.position = coalesce(p.position, $position)
                        
                        // Create weekly stat node
                        MERGE (s:WeeklyStat {
                            player_id: $player_id,
                            season: $season,
                            week: $week
                        })
                        SET s.completions = $completions,
                            s.attempts = $attempts,
                            s.passing_yards = $passing_yards,
                            s.passing_tds = $passing_tds,
                            s.interceptions = $interceptions,
                            s.carries = $carries,
                            s.rushing_yards = $rushing_yards,
                            s.rushing_tds = $rushing_tds,
                            s.targets = $targets,
                            s.receptions = $receptions,
                            s.receiving_yards = $receiving_yards,
                            s.receiving_tds = $receiving_tds,
                            s.fantasy_points_ppr = $fantasy_points_ppr
                        
                        // Link player to stat
                        MERGE (p)-[:HAS_STAT]->(s)
                    """, {
                        'player_id': row.get('player_id'),
                        'player_name': row.get('player_display_name', row.get('player_name')),
                        'position': row.get('position'),
                        'season': int(row.get('season', 0)),
                        'week': int(row.get('week', 0)),
                        'completions': row.get('completions'),
                        'attempts': row.get('attempts'),
                        'passing_yards': row.get('passing_yards'),
                        'passing_tds': row.get('passing_tds'),
                        'interceptions': row.get('interceptions'),
                        'carries': row.get('carries'),
                        'rushing_yards': row.get('rushing_yards'),
                        'rushing_tds': row.get('rushing_tds'),
                        'targets': row.get('targets'),
                        'receptions': row.get('receptions'),
                        'receiving_yards': row.get('receiving_yards'),
                        'receiving_tds': row.get('receiving_tds'),
                        'fantasy_points_ppr': row.get('fantasy_points_ppr')
                    })
                    count += 1
                except Exception as e:
                    continue
        
        print(f"✅ Loaded {count} weekly stat records")
    
    # =========================================================================
    # LOAD SNAP COUNTS
    # =========================================================================
    
    def load_snap_counts(self, seasons: List[int] = None):
        """Load snap count data into Neo4j."""
        snaps = self.fetcher.get_snap_counts(seasons)
        
        count = 0
        with self.driver.session() as session:
            for _, row in snaps.iterrows():
                try:
                    session.run("""
                        MATCH (s:WeeklyStat {
                            player_id: $player_id,
                            season: $season,
                            week: $week
                        })
                        SET s.offense_snaps = $offense_snaps,
                            s.offense_pct = $offense_pct,
                            s.snap_share = $offense_pct
                    """, {
                        'player_id': row.get('pfr_player_id', row.get('player_id')),
                        'season': int(row.get('season', 0)),
                        'week': int(row.get('week', 0)),
                        'offense_snaps': row.get('offense_snaps'),
                        'offense_pct': row.get('offense_pct')
                    })
                    count += 1
                except Exception as e:
                    continue
        
        print(f"✅ Updated {count} records with snap count data")
    
    # =========================================================================
    # LOAD NEXT GEN STATS
    # =========================================================================
    
    def load_nextgen_receiving(self, seasons: List[int] = None):
        """Load Next Gen Stats receiving data."""
        ngs = self.fetcher.get_nextgen_receiving(seasons)
        
        count = 0
        with self.driver.session() as session:
            for _, row in ngs.iterrows():
                try:
                    session.run("""
                        MATCH (s:WeeklyStat {
                            player_id: $player_id,
                            season: $season,
                            week: $week
                        })
                        SET s.target_share = $target_share,
                            s.air_yards_share = $air_yards_share,
                            s.avg_separation = $avg_separation,
                            s.avg_cushion = $avg_cushion,
                            s.avg_yac = $avg_yac,
                            s.catch_pct = $catch_pct
                    """, {
                        'player_id': row.get('player_gsis_id', row.get('player_id')),
                        'season': int(row.get('season', 0)),
                        'week': int(row.get('week', 0)),
                        'target_share': row.get('percent_share_of_intended_air_yards'),
                        'air_yards_share': row.get('percent_share_of_intended_air_yards'),
                        'avg_separation': row.get('avg_separation'),
                        'avg_cushion': row.get('avg_cushion'),
                        'avg_yac': row.get('avg_yac'),
                        'catch_pct': row.get('catch_percentage')
                    })
                    count += 1
                except Exception as e:
                    continue
        
        print(f"✅ Updated {count} records with Next Gen Stats")
    
    # =========================================================================
    # AGGREGATE TO PLAYER SNAPSHOTS
    # =========================================================================
    
    def aggregate_to_snapshots(self, season: int = None):
        """
        Aggregate weekly stats into player Snapshot nodes for temporal analysis.
        Calculates per-game averages from weekly data.
        """
        season = season or self.fetcher.current_season
        
        with self.driver.session() as session:
            # Calculate season averages and create/update snapshots
            result = session.run("""
                MATCH (p:Player)-[:HAS_STAT]->(s:WeeklyStat)
                WHERE s.season = $season
                WITH p, 
                     count(s) as games_played,
                     avg(s.targets) as targets_per_game,
                     avg(s.receptions) as rec_per_game,
                     avg(s.receiving_yards) as rec_yards_per_game,
                     avg(s.fantasy_points_ppr) as ppg,
                     avg(s.snap_share) as avg_snap_share,
                     avg(s.target_share) as avg_target_share,
                     sum(s.targets) as total_targets,
                     sum(s.receptions) as total_receptions
                WHERE games_played >= 1
                
                // Create or update snapshot with NFL stats
                MERGE (snap:Snapshot {
                    player_id: p.player_id,
                    date: date()
                })
                SET snap.nfl_games_played = games_played,
                    snap.nfl_targets_per_game = targets_per_game,
                    snap.nfl_rec_per_game = rec_per_game,
                    snap.nfl_rec_yards_per_game = rec_yards_per_game,
                    snap.nfl_ppg = ppg,
                    snap.nfl_snap_share = avg_snap_share,
                    snap.nfl_target_share = avg_target_share,
                    snap.nfl_total_targets = total_targets,
                    snap.nfl_total_receptions = total_receptions
                
                RETURN count(snap) as updated
            """, {'season': season})
            
            record = result.single()
            count = record['updated'] if record else 0
        
        print(f"✅ Updated {count} player snapshots with NFL stats")
    
    # =========================================================================
    # FULL LOAD PIPELINE
    # =========================================================================
    
    def run_full_load(self, seasons: List[int] = None):
        """Run the complete NFL data load pipeline."""
        seasons = seasons or [self.fetcher.current_season]
        
        print("\n" + "=" * 70)
        print(f"🏈 NFL DATA LOAD PIPELINE")
        print(f"   Seasons: {seasons}")
        print("=" * 70 + "\n")
        
        # Step 1: Load teams
        print("📍 Step 1/6: Loading NFL teams...")
        try:
            self.load_teams()
        except Exception as e:
            print(f"  ⚠️ Failed: {e}")
        
        # Step 2: Load player IDs
        print("\n📍 Step 2/6: Loading player ID mappings...")
        try:
            self.load_player_ids()
        except Exception as e:
            print(f"  ⚠️ Failed: {e}")
        
        # Step 3: Load weekly stats
        print("\n📍 Step 3/6: Loading weekly statistics...")
        try:
            self.load_weekly_stats(seasons)
        except Exception as e:
            print(f"  ⚠️ Failed: {e}")
        
        # Step 4: Load snap counts
        print("\n📍 Step 4/6: Loading snap counts...")
        try:
            self.load_snap_counts(seasons)
        except Exception as e:
            print(f"  ⚠️ Failed: {e}")
        
        # Step 5: Load Next Gen Stats
        print("\n📍 Step 5/6: Loading Next Gen Stats...")
        try:
            self.load_nextgen_receiving(seasons)
        except Exception as e:
            print(f"  ⚠️ Failed: {e}")
        
        # Step 6: Aggregate to snapshots
        print("\n📍 Step 6/6: Aggregating to player snapshots...")
        try:
            for season in seasons:
                self.aggregate_to_snapshots(season)
        except Exception as e:
            print(f"  ⚠️ Failed: {e}")
        
        print("\n" + "=" * 70)
        print("✅ NFL DATA LOAD COMPLETE")
        print("=" * 70)


# =============================================================================
# DYNASTY-SPECIFIC QUERIES
# =============================================================================

def get_target_leaders(driver, season: int, min_games: int = 5) -> pd.DataFrame:
    """Get WRs/TEs ranked by targets per game."""
    with driver.session() as session:
        result = session.run("""
            MATCH (p:Player)-[:HAS_STAT]->(s:WeeklyStat)
            WHERE s.season = $season AND p.position IN ['WR', 'TE']
            WITH p, count(s) as games, avg(s.targets) as tpg, sum(s.targets) as total
            WHERE games >= $min_games
            RETURN p.name as player, p.position as pos, p.team as team,
                   games, round(tpg, 1) as targets_per_game, total as total_targets
            ORDER BY tpg DESC
            LIMIT 50
        """, {'season': season, 'min_games': min_games})
        
        return pd.DataFrame([dict(r) for r in result])


def get_target_share_leaders(driver, season: int) -> pd.DataFrame:
    """Get players ranked by target share."""
    with driver.session() as session:
        result = session.run("""
            MATCH (p:Player)-[:HAS_STAT]->(s:WeeklyStat)
            WHERE s.season = $season 
              AND p.position IN ['WR', 'TE']
              AND s.target_share IS NOT NULL
            WITH p, avg(s.target_share) as avg_share, count(s) as games
            WHERE games >= 5
            RETURN p.name as player, p.position as pos,
                   round(avg_share * 100, 1) as target_share_pct, games
            ORDER BY avg_share DESC
            LIMIT 30
        """, {'season': season})
        
        return pd.DataFrame([dict(r) for r in result])


def get_efficiency_metrics(driver, season: int, position: str = 'WR') -> pd.DataFrame:
    """Get efficiency metrics (yards per target, catch rate)."""
    with driver.session() as session:
        result = session.run("""
            MATCH (p:Player)-[:HAS_STAT]->(s:WeeklyStat)
            WHERE s.season = $season AND p.position = $position
            WITH p, 
                 sum(s.targets) as targets,
                 sum(s.receptions) as receptions,
                 sum(s.receiving_yards) as yards,
                 count(s) as games
            WHERE targets >= 30
            RETURN p.name as player,
                   games,
                   targets,
                   receptions,
                   yards,
                   round(toFloat(receptions) / targets * 100, 1) as catch_rate,
                   round(toFloat(yards) / targets, 1) as yards_per_target
            ORDER BY yards_per_target DESC
            LIMIT 30
        """, {'season': season, 'position': position})
        
        return pd.DataFrame([dict(r) for r in result])


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Run NFL data integration."""
    print("\n" + "=" * 70)
    print("🏈 DYNASTY EDGE - NFL Data Integration (nflverse)")
    print("=" * 70 + "\n")
    
    if not NFLREADPY_AVAILABLE and not NFL_DATA_PY_AVAILABLE:
        print("❌ No NFL data library available!")
        print("\nInstall with:")
        print("  pip install nflreadpy polars  # Recommended")
        print("  pip install nfl-data-py       # Legacy")
        return
    
    # Test data fetching
    fetcher = NFLDataFetcher()
    
    print("\n📊 Testing data fetch (2024 season)...")
    
    try:
        weekly = fetcher.get_weekly_stats([2024])
        print(f"  Weekly stats: {len(weekly)} records")
        print(f"  Columns: {list(weekly.columns)[:10]}...")
    except Exception as e:
        print(f"  ⚠️ Weekly stats failed: {e}")
    
    try:
        snaps = fetcher.get_snap_counts([2024])
        print(f"  Snap counts: {len(snaps)} records")
    except Exception as e:
        print(f"  ⚠️ Snap counts failed: {e}")
    
    try:
        ngs = fetcher.get_nextgen_receiving([2024])
        print(f"  Next Gen Stats (receiving): {len(ngs)} records")
    except Exception as e:
        print(f"  ⚠️ Next Gen Stats failed: {e}")
    
    # If Neo4j is available, run full load
    try:
        loader = NFLDataLoader()
        
        print("\n📥 Running full load to Neo4j...")
        loader.run_full_load([2024])
        
        loader.close()
    except Exception as e:
        print(f"\n⚠️ Neo4j load skipped: {e}")
        print("   (This is expected if Neo4j is not running)")


if __name__ == "__main__":
    main()
