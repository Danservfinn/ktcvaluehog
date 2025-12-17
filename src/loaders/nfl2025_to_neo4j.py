"""
2025 NFL Season Data to Neo4j ETL
=================================
Loads 2025 NFL season data from nflverse into Neo4j.

Pipeline:
1. Fetch weekly stats using nflreadpy
2. Load into WeeklyStats nodes
3. Calculate and load SeasonStats aggregations
4. Load snap count data
5. Load Next Gen Stats
6. Link to existing Player nodes
7. Create temporal chains

Usage:
    python -m src.loaders.nfl2025_to_neo4j              # Full load
    python -m src.loaders.nfl2025_to_neo4j --weekly     # Weekly stats only
    python -m src.loaders.nfl2025_to_neo4j --snaps      # Snap counts only
    python -m src.loaders.nfl2025_to_neo4j --verify     # Verify data
"""

import os
import logging
from typing import Optional, List, Dict
from datetime import datetime

import pandas as pd
from neo4j import GraphDatabase
from dotenv import load_dotenv

from .nfl2025_loader import NFL2025Loader, NFLREADPY_AVAILABLE
from ..database.nfl2025_schema import (
    NFL2025SchemaManager,
    WEEKLY_STATS_MERGE,
    SEASON_STATS_MERGE,
    SNAP_COUNT_MERGE,
    NGS_STATS_MERGE,
    LINK_WEEKLY_TO_PLAYER,
    LINK_SEASON_TO_PLAYER,
    LINK_SNAPS_TO_PLAYER,
    LINK_WEEK_CHAIN,
)

load_dotenv()
logger = logging.getLogger(__name__)


class NFL2025ToNeo4jETL:
    """
    ETL pipeline for loading 2025 NFL data into Neo4j.

    Integrates with existing Player nodes via player name matching.
    """

    def __init__(self, driver=None):
        """Initialize ETL with optional driver."""
        if driver:
            self.driver = driver
            self._owns_driver = False
        else:
            uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
            user = os.getenv("NEO4J_USER")
            password = os.getenv("NEO4J_PASSWORD")
            auth = (user, password) if user and password else None
            self.driver = GraphDatabase.driver(uri, auth=auth)
            self._owns_driver = True

        if not NFLREADPY_AVAILABLE:
            raise ImportError("nflreadpy is required. Install with: pip install nflreadpy polars")

        self.loader = NFL2025Loader()
        self._player_id_map = None  # Cache for nflverse ID -> sleeper ID mapping

    def close(self):
        """Close driver if owned."""
        if self._owns_driver and self.driver:
            self.driver.close()

    def run_full_etl(
        self,
        weeks: Optional[List[int]] = None,
        include_snaps: bool = True,
        include_ngs: bool = True
    ) -> Dict[str, int]:
        """
        Run complete 2025 data ETL pipeline.

        Args:
            weeks: Optional list of weeks to load (default: all available)
            include_snaps: Whether to load snap count data
            include_ngs: Whether to load Next Gen Stats

        Returns:
            Dict with counts of loaded records
        """
        start_time = datetime.now()
        logger.info("=" * 60)
        logger.info("2025 NFL Season Data ETL")
        logger.info("=" * 60)

        stats = {
            'weekly_stats': 0,
            'season_stats': 0,
            'snap_counts': 0,
            'ngs_stats': 0,
            'player_links': 0,
            'errors': 0
        }

        try:
            # Step 1: Setup schema
            logger.info("Setting up 2025 schema...")
            schema_mgr = NFL2025SchemaManager(self.driver)
            schema_mgr.setup_schema()

            # Step 2: Build player ID mapping
            logger.info("Building player ID mapping...")
            self._build_player_id_map()

            # Step 3: Load weekly stats
            logger.info("Loading weekly stats...")
            stats['weekly_stats'] = self._load_weekly_stats(weeks)

            # Step 4: Calculate and load season stats
            logger.info("Loading season stats...")
            stats['season_stats'] = self._load_season_stats()

            # Step 5: Load snap counts (optional)
            if include_snaps:
                logger.info("Loading snap counts...")
                stats['snap_counts'] = self._load_snap_counts()

            # Step 6: Load NGS (optional)
            if include_ngs:
                logger.info("Loading Next Gen Stats...")
                stats['ngs_stats'] = self._load_ngs_stats()

            # Step 7: Link to Player nodes
            logger.info("Linking to Player nodes...")
            stats['player_links'] = self._link_to_players()

            # Step 8: Create temporal chains
            logger.info("Creating week chains...")
            self._create_week_chains()

            duration = datetime.now() - start_time
            logger.info("=" * 60)
            logger.info("ETL COMPLETE!")
            logger.info(f"Duration: {duration}")
            logger.info(f"Weekly stats: {stats['weekly_stats']:,}")
            logger.info(f"Season stats: {stats['season_stats']:,}")
            logger.info(f"Snap counts: {stats['snap_counts']:,}")
            logger.info(f"NGS records: {stats['ngs_stats']:,}")
            logger.info(f"Player links: {stats['player_links']:,}")
            logger.info("=" * 60)

            return stats

        except Exception as e:
            logger.error(f"ETL failed: {e}")
            stats['errors'] += 1
            raise

    def _build_player_id_map(self):
        """Build mapping from nflverse player_id to sleeper_id."""
        self._player_id_map = {}

        # Get all players with sleeper_id from Neo4j
        with self.driver.session() as session:
            result = session.run("""
                MATCH (p:Player)
                WHERE p.sleeper_id IS NOT NULL
                RETURN p.sleeper_id as sleeper_id, p.name as name
            """)

            neo4j_players = {}
            for record in result:
                name_key = self._normalize_name(record['name'])
                neo4j_players[name_key] = record['sleeper_id']

        # Get 2025 rosters from nflverse
        rosters = self.loader.load_rosters()

        if not rosters.empty:
            for _, row in rosters.iterrows():
                name_key = self._normalize_name(row.get('player_name', ''))
                if name_key in neo4j_players:
                    nflverse_id = row.get('player_id', '')
                    self._player_id_map[nflverse_id] = neo4j_players[name_key]

        logger.info(f"Built player ID map with {len(self._player_id_map)} entries")

    def _normalize_name(self, name: str) -> str:
        """Normalize player name for matching."""
        if not name:
            return ""
        return name.lower().replace("'", "").replace(".", "").replace("-", " ").strip()

    def _load_weekly_stats(self, weeks: Optional[List[int]] = None) -> int:
        """Load weekly player stats into Neo4j."""
        df = self.loader.load_player_stats(weeks=weeks)

        if df.empty:
            logger.warning("No weekly stats available")
            return 0

        count = 0
        with self.driver.session() as session:
            for _, row in df.iterrows():
                try:
                    params = {
                        'player_id': row.get('player_id', ''),
                        'season': int(row.get('season', 2025)),
                        'week': int(row.get('week', 0)),
                        'player_name': row.get('player_display_name', ''),
                        'position': row.get('position', ''),
                        'team': row.get('team', ''),
                        'opponent': row.get('opponent_team', ''),

                        # Passing
                        'completions': self._safe_int(row.get('completions')),
                        'attempts': self._safe_int(row.get('attempts')),
                        'passing_yards': self._safe_float(row.get('passing_yards')),
                        'passing_tds': self._safe_int(row.get('passing_tds')),
                        'interceptions': self._safe_int(row.get('passing_interceptions')),
                        'sacks': self._safe_int(row.get('sacks_suffered')),

                        # Rushing
                        'carries': self._safe_int(row.get('carries')),
                        'rushing_yards': self._safe_float(row.get('rushing_yards')),
                        'rushing_tds': self._safe_int(row.get('rushing_tds')),

                        # Receiving
                        'targets': self._safe_int(row.get('targets')),
                        'receptions': self._safe_int(row.get('receptions')),
                        'receiving_yards': self._safe_float(row.get('receiving_yards')),
                        'receiving_tds': self._safe_int(row.get('receiving_tds')),

                        # Fantasy
                        'fantasy_points': self._safe_float(row.get('fantasy_points')),
                        'fantasy_points_ppr': self._safe_float(row.get('fantasy_points_ppr')),

                        # Advanced
                        'target_share': self._safe_float(row.get('target_share')),
                        'air_yards_share': self._safe_float(row.get('air_yards_share')),
                        'wopr': self._safe_float(row.get('wopr')),
                        'racr': self._safe_float(row.get('racr')),
                    }

                    session.run(WEEKLY_STATS_MERGE, params)
                    count += 1

                except Exception as e:
                    logger.warning(f"Error loading weekly stats for {row.get('player_display_name')}: {e}")

        logger.info(f"Loaded {count} weekly stat records")
        return count

    def _load_season_stats(self) -> int:
        """Load season aggregated stats."""
        df = self.loader.get_season_totals()

        if df.empty:
            logger.warning("No season stats available")
            return 0

        count = 0
        with self.driver.session() as session:
            for _, row in df.iterrows():
                try:
                    params = {
                        'player_id': row.get('player_id', ''),
                        'season': 2025,
                        'player_name': row.get('player', ''),
                        'position': row.get('position', ''),
                        'team': row.get('team', ''),
                        'games': self._safe_int(row.get('games')),

                        # Fantasy totals
                        'total_fantasy_points': self._safe_float(row.get('fantasy_points')),
                        'total_fantasy_points_ppr': self._safe_float(row.get('fantasy_points_ppr')),

                        # Per-game averages
                        'ppg_standard': self._safe_float(row.get('ppg_standard')),
                        'ppg_ppr': self._safe_float(row.get('ppg_ppr')),

                        # Passing
                        'passing_yards': self._safe_float(row.get('passing_yards')),
                        'passing_tds': self._safe_int(row.get('passing_tds')),
                        'interceptions': self._safe_int(row.get('ints')),

                        # Rushing
                        'rushing_yards': self._safe_float(row.get('rushing_yards')),
                        'rushing_tds': self._safe_int(row.get('rushing_tds')),
                        'carries': self._safe_int(row.get('carries')),

                        # Receiving
                        'targets': self._safe_int(row.get('targets')),
                        'receptions': self._safe_int(row.get('receptions')),
                        'receiving_yards': self._safe_float(row.get('receiving_yards')),
                        'receiving_tds': self._safe_int(row.get('receiving_tds')),

                        # Averages
                        'avg_target_share': self._safe_float(row.get('target_share')),
                        'avg_air_yards_share': self._safe_float(row.get('air_yards_share')),
                        'avg_wopr': self._safe_float(row.get('wopr')),
                    }

                    session.run(SEASON_STATS_MERGE, params)
                    count += 1

                except Exception as e:
                    logger.warning(f"Error loading season stats: {e}")

        logger.info(f"Loaded {count} season stat records")
        return count

    def _load_snap_counts(self) -> int:
        """Load snap count data."""
        df = self.loader.load_snap_counts()

        if df.empty:
            logger.warning("No snap count data available")
            return 0

        count = 0
        with self.driver.session() as session:
            for _, row in df.iterrows():
                try:
                    params = {
                        'player_id': row.get('pfr_player_id', row.get('player', '')),
                        'season': 2025,
                        'week': self._safe_int(row.get('week')),
                        'player_name': row.get('player', ''),
                        'position': row.get('position', ''),
                        'team': row.get('team', ''),

                        'offense_snaps': self._safe_int(row.get('offense_snaps')),
                        'offense_pct': self._safe_float(row.get('offense_pct')),
                        'defense_snaps': self._safe_int(row.get('defense_snaps')),
                        'defense_pct': self._safe_float(row.get('defense_pct')),
                        'st_snaps': self._safe_int(row.get('st_snaps')),
                        'st_pct': self._safe_float(row.get('st_pct')),
                    }

                    session.run(SNAP_COUNT_MERGE, params)
                    count += 1

                except Exception as e:
                    logger.warning(f"Error loading snap counts: {e}")

        logger.info(f"Loaded {count} snap count records")
        return count

    def _load_ngs_stats(self) -> int:
        """Load Next Gen Stats."""
        count = 0
        ngs_data = self.loader.load_all_nextgen()

        with self.driver.session() as session:
            for stat_type, df in ngs_data.items():
                if df.empty:
                    continue

                for _, row in df.iterrows():
                    try:
                        # Extract metrics based on stat type
                        metrics = self._extract_ngs_metrics(row, stat_type)

                        params = {
                            'player_id': row.get('player_id', row.get('player_gsis_id', '')),
                            'season': 2025,
                            'week': self._safe_int(row.get('week', 0)),
                            'stat_type': stat_type,
                            'metrics': metrics
                        }

                        session.run(NGS_STATS_MERGE, params)
                        count += 1

                    except Exception as e:
                        logger.warning(f"Error loading NGS {stat_type}: {e}")

        logger.info(f"Loaded {count} NGS records")
        return count

    def _extract_ngs_metrics(self, row: pd.Series, stat_type: str) -> Dict:
        """Extract relevant NGS metrics based on stat type."""
        metrics = {'player_name': row.get('player_display_name', '')}

        if stat_type == 'passing':
            metrics.update({
                'avg_time_to_throw': self._safe_float(row.get('avg_time_to_throw')),
                'avg_completed_air_yards': self._safe_float(row.get('avg_completed_air_yards')),
                'avg_intended_air_yards': self._safe_float(row.get('avg_intended_air_yards')),
                'avg_air_yards_differential': self._safe_float(row.get('avg_air_yards_differential')),
                'aggressiveness': self._safe_float(row.get('aggressiveness')),
                'max_completed_air_distance': self._safe_float(row.get('max_completed_air_distance')),
                'avg_air_yards_to_sticks': self._safe_float(row.get('avg_air_yards_to_sticks')),
                'passer_rating': self._safe_float(row.get('passer_rating')),
                'completion_percentage': self._safe_float(row.get('completion_percentage')),
                'expected_completion_percentage': self._safe_float(row.get('expected_completion_percentage')),
                'completion_percentage_above_expectation': self._safe_float(row.get('completion_percentage_above_expectation')),
            })
        elif stat_type == 'rushing':
            metrics.update({
                'efficiency': self._safe_float(row.get('efficiency')),
                'percent_attempts_gte_eight_defenders': self._safe_float(row.get('percent_attempts_gte_eight_defenders')),
                'avg_time_to_los': self._safe_float(row.get('avg_time_to_los')),
                'rush_attempts': self._safe_int(row.get('rush_attempts')),
                'rush_yards': self._safe_float(row.get('rush_yards')),
                'avg_rush_yards': self._safe_float(row.get('avg_rush_yards')),
                'rush_touchdowns': self._safe_int(row.get('rush_touchdowns')),
            })
        elif stat_type == 'receiving':
            metrics.update({
                'avg_cushion': self._safe_float(row.get('avg_cushion')),
                'avg_separation': self._safe_float(row.get('avg_separation')),
                'avg_intended_air_yards': self._safe_float(row.get('avg_intended_air_yards')),
                'percent_share_of_intended_air_yards': self._safe_float(row.get('percent_share_of_intended_air_yards')),
                'catch_percentage': self._safe_float(row.get('catch_percentage')),
                'receptions': self._safe_int(row.get('receptions')),
                'targets': self._safe_int(row.get('targets')),
                'receiving_yards': self._safe_float(row.get('receiving_yards')),
                'avg_yac': self._safe_float(row.get('avg_yac')),
                'avg_expected_yac': self._safe_float(row.get('avg_expected_yac')),
                'avg_yac_above_expectation': self._safe_float(row.get('avg_yac_above_expectation')),
            })

        return metrics

    def _link_to_players(self) -> int:
        """Link stats nodes to existing Player nodes."""
        count = 0

        with self.driver.session() as session:
            # Link weekly stats
            result = session.run("""
                MATCH (ws:WeeklyStats)
                WHERE NOT exists((ws)<-[:HAD_WEEK]-(:Player))
                MATCH (p:Player)
                WHERE toLower(p.name) = toLower(ws.player_name)
                MERGE (p)-[:HAD_WEEK {season: ws.season, week: ws.week}]->(ws)
                RETURN count(*) as linked
            """)
            count += result.single()['linked']

            # Link season stats
            result = session.run("""
                MATCH (ss:SeasonStats)
                WHERE NOT exists((ss)<-[:HAD_SEASON]-(:Player))
                MATCH (p:Player)
                WHERE toLower(p.name) = toLower(ss.player_name)
                MERGE (p)-[:HAD_SEASON {season: ss.season}]->(ss)
                RETURN count(*) as linked
            """)
            count += result.single()['linked']

            # Link snap counts
            result = session.run("""
                MATCH (sc:SnapCount)
                WHERE NOT exists((sc)<-[:HAD_SNAPS]-(:Player))
                MATCH (p:Player)
                WHERE toLower(p.name) = toLower(sc.player_name)
                MERGE (p)-[:HAD_SNAPS {season: sc.season, week: sc.week}]->(sc)
                RETURN count(*) as linked
            """)
            count += result.single()['linked']

        logger.info(f"Created {count} links to Player nodes")
        return count

    def _create_week_chains(self):
        """Create temporal WEEK_NEXT relationships."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (ws1:WeeklyStats)
                WHERE ws1.season = 2025
                WITH ws1.player_id as pid, collect(ws1) as weeks
                WHERE size(weeks) > 1
                UNWIND range(0, size(weeks)-2) as i
                WITH weeks[i] as curr, weeks[i+1] as next
                WHERE curr.week < next.week
                MERGE (curr)-[:WEEK_NEXT]->(next)
                RETURN count(*) as chains
            """)
            chains = result.single()['chains']
            logger.info(f"Created {chains} week chains")

    def _safe_float(self, val) -> Optional[float]:
        """Safely convert to float."""
        if pd.isna(val) or val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    def _safe_int(self, val) -> Optional[int]:
        """Safely convert to int."""
        if pd.isna(val) or val is None:
            return None
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return None

    def verify_data(self) -> Dict:
        """Verify loaded 2025 data."""
        with self.driver.session() as session:
            queries = {
                'weekly_stats': "MATCH (ws:WeeklyStats {season: 2025}) RETURN count(ws) as count",
                'season_stats': "MATCH (ss:SeasonStats {season: 2025}) RETURN count(ss) as count",
                'snap_counts': "MATCH (sc:SnapCount {season: 2025}) RETURN count(sc) as count",
                'ngs_stats': "MATCH (ngs:NGSStats {season: 2025}) RETURN count(ngs) as count",
                'linked_players': "MATCH (p:Player)-[:HAD_SEASON]->(:SeasonStats {season: 2025}) RETURN count(DISTINCT p) as count",
                'weeks_loaded': "MATCH (ws:WeeklyStats {season: 2025}) RETURN max(ws.week) as count",
            }

            stats = {}
            for name, query in queries.items():
                result = session.run(query)
                stats[name] = result.single()['count']

            return stats


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description='Load 2025 NFL data to Neo4j')
    parser.add_argument('--weekly', action='store_true', help='Load weekly stats only')
    parser.add_argument('--snaps', action='store_true', help='Load snap counts only')
    parser.add_argument('--verify', action='store_true', help='Verify data only')
    parser.add_argument('--weeks', type=int, nargs='+', help='Specific weeks to load')

    args = parser.parse_args()

    etl = NFL2025ToNeo4jETL()

    try:
        if args.verify:
            print("\n2025 Data Verification:")
            print("-" * 40)
            stats = etl.verify_data()
            for key, value in stats.items():
                print(f"  {key}: {value:,}")
        else:
            stats = etl.run_full_etl(
                weeks=args.weeks,
                include_snaps=not args.weekly or args.snaps,
                include_ngs=not args.weekly and not args.snaps
            )
    finally:
        etl.close()
