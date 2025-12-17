"""
Neo4j Schema for 2025 NFL Season Data
=====================================
Defines node types and relationships for tracking
current season production data from nflverse.

Node Types:
- WeeklyStats: Per-game player statistics
- SeasonStats: Aggregated season totals
- SnapCount: Playing time/snap data
- NGSStats: Next Gen Stats advanced metrics

Relationships:
- Player -[:HAD_WEEK {season, week}]-> WeeklyStats
- Player -[:HAD_SEASON {season}]-> SeasonStats
- Player -[:HAD_SNAPS {season, week}]-> SnapCount
- Player -[:HAD_NGS {season, stat_type}]-> NGSStats
- WeeklyStats -[:WEEK_NEXT]-> WeeklyStats (temporal chain)
"""

import logging
from typing import Optional, Dict, List
from datetime import datetime

logger = logging.getLogger(__name__)


class NFL2025SchemaManager:
    """
    Manage Neo4j schema for 2025 NFL season data.

    Extends existing Player nodes with production relationships.
    """

    def __init__(self, driver):
        """Initialize with Neo4j driver."""
        self.driver = driver

    def setup_schema(self):
        """Setup complete 2025 NFL schema."""
        logger.info("Setting up 2025 NFL schema...")

        self._create_constraints()
        self._create_indexes()

        logger.info("2025 NFL schema setup complete!")

    def _create_constraints(self):
        """Create uniqueness constraints."""
        constraints = [
            # WeeklyStats unique per player-season-week
            """
            CREATE CONSTRAINT weekly_stats_unique IF NOT EXISTS
            FOR (ws:WeeklyStats)
            REQUIRE (ws.player_id, ws.season, ws.week) IS UNIQUE
            """,

            # SeasonStats unique per player-season
            """
            CREATE CONSTRAINT season_stats_unique IF NOT EXISTS
            FOR (ss:SeasonStats)
            REQUIRE (ss.player_id, ss.season) IS UNIQUE
            """,

            # SnapCount unique per player-season-week
            """
            CREATE CONSTRAINT snap_count_unique IF NOT EXISTS
            FOR (sc:SnapCount)
            REQUIRE (sc.player_id, sc.season, sc.week) IS UNIQUE
            """,

            # NGSStats unique per player-season-week-type
            """
            CREATE CONSTRAINT ngs_stats_unique IF NOT EXISTS
            FOR (ngs:NGSStats)
            REQUIRE (ngs.player_id, ngs.season, ngs.week, ngs.stat_type) IS UNIQUE
            """,
        ]

        with self.driver.session() as session:
            for constraint in constraints:
                try:
                    session.run(constraint)
                except Exception as e:
                    # Constraint may already exist
                    if "already exists" not in str(e).lower():
                        logger.warning(f"Constraint issue: {e}")

    def _create_indexes(self):
        """Create performance indexes."""
        indexes = [
            # WeeklyStats indexes
            "CREATE INDEX weekly_stats_season IF NOT EXISTS FOR (ws:WeeklyStats) ON (ws.season)",
            "CREATE INDEX weekly_stats_week IF NOT EXISTS FOR (ws:WeeklyStats) ON (ws.week)",
            "CREATE INDEX weekly_stats_position IF NOT EXISTS FOR (ws:WeeklyStats) ON (ws.position)",
            "CREATE INDEX weekly_stats_team IF NOT EXISTS FOR (ws:WeeklyStats) ON (ws.team)",
            "CREATE INDEX weekly_stats_fantasy_ppr IF NOT EXISTS FOR (ws:WeeklyStats) ON (ws.fantasy_points_ppr)",

            # SeasonStats indexes
            "CREATE INDEX season_stats_season IF NOT EXISTS FOR (ss:SeasonStats) ON (ss.season)",
            "CREATE INDEX season_stats_position IF NOT EXISTS FOR (ss:SeasonStats) ON (ss.position)",
            "CREATE INDEX season_stats_team IF NOT EXISTS FOR (ss:SeasonStats) ON (ss.team)",
            "CREATE INDEX season_stats_ppg IF NOT EXISTS FOR (ss:SeasonStats) ON (ss.ppg_ppr)",

            # SnapCount indexes
            "CREATE INDEX snap_count_season IF NOT EXISTS FOR (sc:SnapCount) ON (sc.season)",
            "CREATE INDEX snap_count_week IF NOT EXISTS FOR (sc:SnapCount) ON (sc.week)",
            "CREATE INDEX snap_count_pct IF NOT EXISTS FOR (sc:SnapCount) ON (sc.offense_pct)",

            # NGSStats indexes
            "CREATE INDEX ngs_stats_season IF NOT EXISTS FOR (ngs:NGSStats) ON (ngs.season)",
            "CREATE INDEX ngs_stats_type IF NOT EXISTS FOR (ngs:NGSStats) ON (ngs.stat_type)",
        ]

        with self.driver.session() as session:
            for index in indexes:
                try:
                    session.run(index)
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        logger.warning(f"Index issue: {e}")

    def get_schema_info(self) -> Dict:
        """Get current schema statistics."""
        with self.driver.session() as session:
            queries = {
                'weekly_stats': "MATCH (ws:WeeklyStats) RETURN count(ws) as count",
                'season_stats': "MATCH (ss:SeasonStats) RETURN count(ss) as count",
                'snap_counts': "MATCH (sc:SnapCount) RETURN count(sc) as count",
                'ngs_stats': "MATCH (ngs:NGSStats) RETURN count(ngs) as count",
                'player_week_links': "MATCH (:Player)-[r:HAD_WEEK]->(:WeeklyStats) RETURN count(r) as count",
                'player_season_links': "MATCH (:Player)-[r:HAD_SEASON]->(:SeasonStats) RETURN count(r) as count",
            }

            stats = {}
            for name, query in queries.items():
                result = session.run(query)
                stats[name] = result.single()['count']

            return stats


# =============================================================================
# CYPHER QUERIES FOR DATA LOADING
# =============================================================================

WEEKLY_STATS_MERGE = """
MERGE (ws:WeeklyStats {
    player_id: $player_id,
    season: $season,
    week: $week
})
SET ws += {
    player_name: $player_name,
    position: $position,
    team: $team,
    opponent: $opponent,

    // Passing
    completions: $completions,
    attempts: $attempts,
    passing_yards: $passing_yards,
    passing_tds: $passing_tds,
    interceptions: $interceptions,
    sacks: $sacks,

    // Rushing
    carries: $carries,
    rushing_yards: $rushing_yards,
    rushing_tds: $rushing_tds,

    // Receiving
    targets: $targets,
    receptions: $receptions,
    receiving_yards: $receiving_yards,
    receiving_tds: $receiving_tds,

    // Fantasy
    fantasy_points: $fantasy_points,
    fantasy_points_ppr: $fantasy_points_ppr,

    // Advanced (if available)
    target_share: $target_share,
    air_yards_share: $air_yards_share,
    wopr: $wopr,
    racr: $racr,

    updated_at: datetime()
}
RETURN ws
"""

SEASON_STATS_MERGE = """
MERGE (ss:SeasonStats {
    player_id: $player_id,
    season: $season
})
SET ss += {
    player_name: $player_name,
    position: $position,
    team: $team,
    games: $games,

    // Totals
    total_fantasy_points: $total_fantasy_points,
    total_fantasy_points_ppr: $total_fantasy_points_ppr,

    // Per-game averages
    ppg_standard: $ppg_standard,
    ppg_ppr: $ppg_ppr,

    // Passing totals
    passing_yards: $passing_yards,
    passing_tds: $passing_tds,
    interceptions: $interceptions,

    // Rushing totals
    rushing_yards: $rushing_yards,
    rushing_tds: $rushing_tds,
    carries: $carries,

    // Receiving totals
    targets: $targets,
    receptions: $receptions,
    receiving_yards: $receiving_yards,
    receiving_tds: $receiving_tds,

    // Averages (if available)
    avg_target_share: $avg_target_share,
    avg_air_yards_share: $avg_air_yards_share,
    avg_wopr: $avg_wopr,

    updated_at: datetime()
}
RETURN ss
"""

SNAP_COUNT_MERGE = """
MERGE (sc:SnapCount {
    player_id: $player_id,
    season: $season,
    week: $week
})
SET sc += {
    player_name: $player_name,
    position: $position,
    team: $team,

    offense_snaps: $offense_snaps,
    offense_pct: $offense_pct,
    defense_snaps: $defense_snaps,
    defense_pct: $defense_pct,
    st_snaps: $st_snaps,
    st_pct: $st_pct,

    updated_at: datetime()
}
RETURN sc
"""

NGS_STATS_MERGE = """
MERGE (ngs:NGSStats {
    player_id: $player_id,
    season: $season,
    week: $week,
    stat_type: $stat_type
})
SET ngs += $metrics
SET ngs.updated_at = datetime()
RETURN ngs
"""

# Link to Player node
LINK_WEEKLY_TO_PLAYER = """
MATCH (p:Player {sleeper_id: $sleeper_id})
MATCH (ws:WeeklyStats {player_id: $player_id, season: $season, week: $week})
MERGE (p)-[r:HAD_WEEK {season: $season, week: $week}]->(ws)
RETURN p.full_name, ws.week
"""

LINK_SEASON_TO_PLAYER = """
MATCH (p:Player {sleeper_id: $sleeper_id})
MATCH (ss:SeasonStats {player_id: $player_id, season: $season})
MERGE (p)-[r:HAD_SEASON {season: $season}]->(ss)
RETURN p.full_name, ss.season
"""

LINK_SNAPS_TO_PLAYER = """
MATCH (p:Player {sleeper_id: $sleeper_id})
MATCH (sc:SnapCount {player_id: $player_id, season: $season, week: $week})
MERGE (p)-[r:HAD_SNAPS {season: $season, week: $week}]->(sc)
RETURN p.full_name, sc.week
"""

# Temporal chain for weekly progression
LINK_WEEK_CHAIN = """
MATCH (ws1:WeeklyStats {player_id: $player_id, season: $season, week: $week1})
MATCH (ws2:WeeklyStats {player_id: $player_id, season: $season, week: $week2})
WHERE ws1 <> ws2
MERGE (ws1)-[r:WEEK_NEXT]->(ws2)
RETURN ws1.week, ws2.week
"""


# =============================================================================
# QUERY TEMPLATES FOR ANALYSIS
# =============================================================================

# Get player's 2025 weekly performance
GET_PLAYER_WEEKLY_STATS = """
MATCH (p:Player)-[:HAD_WEEK]->(ws:WeeklyStats)
WHERE p.full_name =~ $name_pattern AND ws.season = 2025
RETURN ws.week as week, ws.opponent as opponent,
       ws.fantasy_points_ppr as points,
       ws.targets as targets, ws.receptions as receptions,
       ws.receiving_yards as rec_yards, ws.receiving_tds as rec_tds,
       ws.carries as carries, ws.rushing_yards as rush_yards, ws.rushing_tds as rush_tds
ORDER BY ws.week
"""

# Get 2025 production leaders
GET_2025_LEADERS = """
MATCH (ss:SeasonStats {season: 2025})
WHERE ss.position = $position
RETURN ss.player_name as player, ss.team as team,
       ss.games as games, ss.ppg_ppr as ppg,
       ss.total_fantasy_points_ppr as total_points,
       ss.targets as targets, ss.receptions as receptions,
       ss.receiving_yards as rec_yards
ORDER BY ss.ppg_ppr DESC
LIMIT $limit
"""

# Compare 2025 production to KTC value
GET_PRODUCTION_VS_VALUE = """
MATCH (p:Player)-[:HAD_SEASON]->(ss:SeasonStats {season: 2025})
WHERE p.ktc_sf_value IS NOT NULL AND ss.ppg_ppr IS NOT NULL
RETURN p.full_name as player, p.position as position,
       p.ktc_sf_value as ktc_value,
       ss.ppg_ppr as ppg_2025, ss.games as games,
       ss.total_fantasy_points_ppr as total_points,
       (ss.ppg_ppr * 1000 / p.ktc_sf_value) as production_efficiency
ORDER BY production_efficiency DESC
LIMIT $limit
"""

# Find players with rising snap counts
GET_SNAP_TRENDS = """
MATCH (p:Player)-[:HAD_SNAPS]->(sc:SnapCount)
WHERE sc.season = 2025 AND sc.position IN ['RB', 'WR', 'TE']
WITH p, collect({week: sc.week, pct: sc.offense_pct}) as snaps
WHERE size(snaps) >= 3
WITH p, snaps,
     [s IN snaps WHERE s.week <= 4 | s.pct] as early,
     [s IN snaps WHERE s.week > 4 | s.pct] as late
WHERE size(early) > 0 AND size(late) > 0
WITH p,
     reduce(sum = 0.0, x IN early | sum + x) / size(early) as early_avg,
     reduce(sum = 0.0, x IN late | sum + x) / size(late) as late_avg
WHERE late_avg > early_avg + 10
RETURN p.full_name as player, p.position as position, p.team as team,
       round(early_avg, 1) as early_snap_pct, round(late_avg, 1) as late_snap_pct,
       round(late_avg - early_avg, 1) as snap_increase
ORDER BY snap_increase DESC
LIMIT $limit
"""

# Weekly fantasy point trend
GET_FANTASY_TREND = """
MATCH (p:Player)-[:HAD_WEEK]->(ws:WeeklyStats)
WHERE p.full_name =~ $name_pattern AND ws.season = 2025
WITH p, ws ORDER BY ws.week
WITH p, collect(ws.fantasy_points_ppr) as points, collect(ws.week) as weeks
WHERE size(points) >= 4
WITH p, points, weeks,
     [i IN range(0, size(points)/2 - 1) | points[i]] as first_half,
     [i IN range(size(points)/2, size(points) - 1) | points[i]] as second_half
RETURN p.full_name as player, p.position as position,
       points as weekly_points,
       round(reduce(s=0.0, x IN first_half | s+x)/size(first_half), 1) as first_half_ppg,
       round(reduce(s=0.0, x IN second_half | s+x)/size(second_half), 1) as second_half_ppg
"""


# =============================================================================
# CLI TESTING
# =============================================================================

if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    from neo4j import GraphDatabase

    load_dotenv()

    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")

    auth = (user, password) if user and password else None
    driver = GraphDatabase.driver(uri, auth=auth)

    try:
        schema_mgr = NFL2025SchemaManager(driver)
        schema_mgr.setup_schema()

        print("\nSchema Info:")
        print("-" * 40)
        info = schema_mgr.get_schema_info()
        for key, value in info.items():
            print(f"  {key}: {value:,}")
    finally:
        driver.close()
