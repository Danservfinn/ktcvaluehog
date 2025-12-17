"""
Historical NFL Data Neo4j Schema
================================
Schema definitions for storing 26 years (1999-2024) of NFL data.

Node Types:
- HistoricalWeeklyStats: Weekly fantasy stats per player
- HistoricalSeasonStats: Season aggregates per player
- HistoricalSnapCount: Weekly snap counts (2015+)
- HistoricalNGS: Next Gen Stats (2016+)
- CombineResult: NFL Combine metrics
- DraftPick: Draft selection info

Relationships:
- (:Player)-[:HAD_HISTORICAL_WEEK]->(:HistoricalWeeklyStats)
- (:Player)-[:HAD_HISTORICAL_SEASON]->(:HistoricalSeasonStats)
- (:HistoricalSeasonStats)-[:NEXT_SEASON]->(:HistoricalSeasonStats)
- (:Player)-[:COMBINED_AT]->(:CombineResult)
- (:Player)-[:DRAFTED_AS]->(:DraftPick)
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTRAINTS
# =============================================================================

CONSTRAINTS = [
    # Historical weekly stats
    """CREATE CONSTRAINT historical_weekly_unique IF NOT EXISTS
       FOR (h:HistoricalWeeklyStats) REQUIRE (h.player_id, h.season, h.week) IS UNIQUE""",

    # Historical season stats
    """CREATE CONSTRAINT historical_season_unique IF NOT EXISTS
       FOR (h:HistoricalSeasonStats) REQUIRE (h.player_id, h.season) IS UNIQUE""",

    # Historical snap counts
    """CREATE CONSTRAINT historical_snap_unique IF NOT EXISTS
       FOR (h:HistoricalSnapCount) REQUIRE (h.player_id, h.season, h.week) IS UNIQUE""",

    # Historical NGS
    """CREATE CONSTRAINT historical_ngs_unique IF NOT EXISTS
       FOR (h:HistoricalNGS) REQUIRE (h.player_id, h.season, h.week, h.stat_type) IS UNIQUE""",

    # Combine results
    """CREATE CONSTRAINT combine_unique IF NOT EXISTS
       FOR (c:CombineResult) REQUIRE (c.player_id, c.season) IS UNIQUE""",

    # Draft picks
    """CREATE CONSTRAINT draft_pick_unique IF NOT EXISTS
       FOR (d:DraftPick) REQUIRE (d.season, d.round, d.pick) IS UNIQUE""",
]

# =============================================================================
# INDEXES
# =============================================================================

INDEXES = [
    # Historical weekly stats indexes
    "CREATE INDEX hist_weekly_season IF NOT EXISTS FOR (h:HistoricalWeeklyStats) ON (h.season)",
    "CREATE INDEX hist_weekly_player IF NOT EXISTS FOR (h:HistoricalWeeklyStats) ON (h.player_id)",
    "CREATE INDEX hist_weekly_position IF NOT EXISTS FOR (h:HistoricalWeeklyStats) ON (h.position)",
    "CREATE INDEX hist_weekly_team IF NOT EXISTS FOR (h:HistoricalWeeklyStats) ON (h.team)",

    # Historical season stats indexes
    "CREATE INDEX hist_season_season IF NOT EXISTS FOR (h:HistoricalSeasonStats) ON (h.season)",
    "CREATE INDEX hist_season_player IF NOT EXISTS FOR (h:HistoricalSeasonStats) ON (h.player_id)",
    "CREATE INDEX hist_season_position IF NOT EXISTS FOR (h:HistoricalSeasonStats) ON (h.position)",
    "CREATE INDEX hist_season_ppg IF NOT EXISTS FOR (h:HistoricalSeasonStats) ON (h.ppg_ppr)",

    # Snap count indexes
    "CREATE INDEX hist_snap_season IF NOT EXISTS FOR (h:HistoricalSnapCount) ON (h.season)",
    "CREATE INDEX hist_snap_player IF NOT EXISTS FOR (h:HistoricalSnapCount) ON (h.player_id)",

    # NGS indexes
    "CREATE INDEX hist_ngs_season IF NOT EXISTS FOR (h:HistoricalNGS) ON (h.season)",
    "CREATE INDEX hist_ngs_type IF NOT EXISTS FOR (h:HistoricalNGS) ON (h.stat_type)",

    # Combine indexes
    "CREATE INDEX combine_season IF NOT EXISTS FOR (c:CombineResult) ON (c.season)",
    "CREATE INDEX combine_position IF NOT EXISTS FOR (c:CombineResult) ON (c.position)",

    # Draft indexes
    "CREATE INDEX draft_season IF NOT EXISTS FOR (d:DraftPick) ON (d.season)",
    "CREATE INDEX draft_position IF NOT EXISTS FOR (d:DraftPick) ON (d.position)",
]

# =============================================================================
# MERGE QUERIES
# =============================================================================

HISTORICAL_WEEKLY_MERGE = """
MERGE (h:HistoricalWeeklyStats {
    player_id: $player_id,
    season: $season,
    week: $week
})
SET h.player_name = $player_name,
    h.position = $position,
    h.team = $team,
    h.opponent = $opponent,

    // Passing
    h.completions = $completions,
    h.attempts = $attempts,
    h.passing_yards = $passing_yards,
    h.passing_tds = $passing_tds,
    h.interceptions = $interceptions,
    h.sacks = $sacks,

    // Rushing
    h.carries = $carries,
    h.rushing_yards = $rushing_yards,
    h.rushing_tds = $rushing_tds,

    // Receiving
    h.targets = $targets,
    h.receptions = $receptions,
    h.receiving_yards = $receiving_yards,
    h.receiving_tds = $receiving_tds,

    // Fantasy points
    h.fantasy_points = $fantasy_points,
    h.fantasy_points_ppr = $fantasy_points_ppr,

    // Advanced (may be null for older years)
    h.target_share = $target_share,
    h.air_yards_share = $air_yards_share,
    h.wopr = $wopr,

    h.loaded_at = datetime()
"""

HISTORICAL_SEASON_MERGE = """
MERGE (h:HistoricalSeasonStats {
    player_id: $player_id,
    season: $season
})
SET h.player_name = $player_name,
    h.position = $position,
    h.team = $team,
    h.games = $games,

    // Fantasy totals
    h.total_fantasy_points = $total_fantasy_points,
    h.total_fantasy_points_ppr = $total_fantasy_points_ppr,
    h.ppg_std = $ppg_std,
    h.ppg_ppr = $ppg_ppr,

    // Passing totals
    h.passing_yards = $passing_yards,
    h.passing_tds = $passing_tds,
    h.interceptions = $interceptions,

    // Rushing totals
    h.rushing_yards = $rushing_yards,
    h.rushing_tds = $rushing_tds,
    h.carries = $carries,

    // Receiving totals
    h.targets = $targets,
    h.receptions = $receptions,
    h.receiving_yards = $receiving_yards,
    h.receiving_tds = $receiving_tds,

    // Averages
    h.avg_target_share = $avg_target_share,
    h.avg_air_yards_share = $avg_air_yards_share,
    h.avg_wopr = $avg_wopr,

    h.loaded_at = datetime()
"""

HISTORICAL_SNAP_MERGE = """
MERGE (h:HistoricalSnapCount {
    player_id: $player_id,
    season: $season,
    week: $week
})
SET h.player_name = $player_name,
    h.position = $position,
    h.team = $team,
    h.offense_snaps = $offense_snaps,
    h.offense_pct = $offense_pct,
    h.defense_snaps = $defense_snaps,
    h.defense_pct = $defense_pct,
    h.st_snaps = $st_snaps,
    h.st_pct = $st_pct,
    h.loaded_at = datetime()
"""

HISTORICAL_NGS_MERGE = """
MERGE (h:HistoricalNGS {
    player_id: $player_id,
    season: $season,
    week: $week,
    stat_type: $stat_type
})
SET h.player_name = $player_name,
    h.position = $position,
    h.team = $team,
    h.metrics = $metrics,
    h.loaded_at = datetime()
"""

COMBINE_MERGE = """
MERGE (c:CombineResult {
    player_id: $player_id,
    season: $season
})
SET c.player_name = $player_name,
    c.position = $position,
    c.college = $college,
    c.height = $height,
    c.weight = $weight,
    c.forty_yard = $forty_yard,
    c.vertical_jump = $vertical_jump,
    c.broad_jump = $broad_jump,
    c.three_cone = $three_cone,
    c.shuttle = $shuttle,
    c.bench_press = $bench_press,
    c.loaded_at = datetime()
"""

DRAFT_PICK_MERGE = """
MERGE (d:DraftPick {
    season: $season,
    round: $round,
    pick: $pick
})
SET d.overall_pick = $overall_pick,
    d.team = $team,
    d.player_name = $player_name,
    d.position = $position,
    d.college = $college,
    d.player_id = $player_id,
    d.loaded_at = datetime()
"""

# =============================================================================
# RELATIONSHIP QUERIES
# =============================================================================

LINK_HISTORICAL_TO_PLAYER = """
MATCH (h:HistoricalSeasonStats)
WHERE NOT exists((h)<-[:HAD_HISTORICAL_SEASON]-(:Player))
MATCH (p:Player)
WHERE toLower(p.name) = toLower(h.player_name)
MERGE (p)-[:HAD_HISTORICAL_SEASON {season: h.season}]->(h)
RETURN count(*) as linked
"""

CREATE_SEASON_CHAINS = """
MATCH (h1:HistoricalSeasonStats)
MATCH (h2:HistoricalSeasonStats)
WHERE h1.player_id = h2.player_id
  AND h2.season = h1.season + 1
  AND NOT exists((h1)-[:NEXT_SEASON]->(h2))
MERGE (h1)-[:NEXT_SEASON]->(h2)
RETURN count(*) as chains
"""

LINK_COMBINE_TO_PLAYER = """
MATCH (c:CombineResult)
WHERE NOT exists((c)<-[:COMBINED_AT]-(:Player))
MATCH (p:Player)
WHERE toLower(p.name) = toLower(c.player_name)
MERGE (p)-[:COMBINED_AT {season: c.season}]->(c)
RETURN count(*) as linked
"""

LINK_DRAFT_TO_PLAYER = """
MATCH (d:DraftPick)
WHERE NOT exists((d)<-[:DRAFTED_AS]-(:Player))
  AND d.player_name IS NOT NULL
MATCH (p:Player)
WHERE toLower(p.name) = toLower(d.player_name)
MERGE (p)-[:DRAFTED_AS]->(d)
RETURN count(*) as linked
"""


# =============================================================================
# SCHEMA MANAGER
# =============================================================================

class HistoricalSchemaManager:
    """Manage Neo4j schema for historical NFL data."""

    def __init__(self, driver):
        self.driver = driver

    def setup_schema(self):
        """Create all constraints and indexes."""
        logger.info("Setting up historical data schema...")

        with self.driver.session() as session:
            # Create constraints
            for constraint in CONSTRAINTS:
                try:
                    session.run(constraint)
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        logger.warning(f"Constraint warning: {e}")

            # Create indexes
            for index in INDEXES:
                try:
                    session.run(index)
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        logger.warning(f"Index warning: {e}")

        logger.info("Historical schema setup complete")

    def verify_schema(self) -> dict:
        """Verify schema is in place."""
        with self.driver.session() as session:
            # Neo4j 5.x uses SHOW CONSTRAINTS/INDEXES
            try:
                result = session.run("SHOW CONSTRAINTS YIELD name RETURN collect(name) as constraints")
                constraints = result.single()['constraints']
            except Exception:
                constraints = []

            try:
                result = session.run("SHOW INDEXES YIELD name RETURN collect(name) as indexes")
                indexes = result.single()['indexes']
            except Exception:
                indexes = []

            return {
                'constraints': len([c for c in constraints if 'historical' in c.lower() or 'combine' in c.lower() or 'draft' in c.lower()]),
                'indexes': len([i for i in indexes if 'hist' in i.lower() or 'combine' in i.lower() or 'draft' in i.lower()])
            }

    def get_data_counts(self) -> dict:
        """Get counts of historical data nodes."""
        counts = {}
        queries = [
            ('historical_weekly', "MATCH (h:HistoricalWeeklyStats) RETURN count(h) as count"),
            ('historical_season', "MATCH (h:HistoricalSeasonStats) RETURN count(h) as count"),
            ('historical_snaps', "MATCH (h:HistoricalSnapCount) RETURN count(h) as count"),
            ('historical_ngs', "MATCH (h:HistoricalNGS) RETURN count(h) as count"),
            ('combine', "MATCH (c:CombineResult) RETURN count(c) as count"),
            ('draft', "MATCH (d:DraftPick) RETURN count(d) as count"),
            ('season_chains', "MATCH ()-[r:NEXT_SEASON]->() RETURN count(r) as count"),
        ]

        with self.driver.session() as session:
            for name, query in queries:
                result = session.run(query)
                counts[name] = result.single()['count']

        return counts

    def get_year_coverage(self) -> dict:
        """Get year range coverage for each data type."""
        coverage = {}

        queries = [
            ('historical_weekly', "MATCH (h:HistoricalWeeklyStats) RETURN min(h.season) as min_year, max(h.season) as max_year, count(h) as count"),
            ('historical_season', "MATCH (h:HistoricalSeasonStats) RETURN min(h.season) as min_year, max(h.season) as max_year, count(h) as count"),
            ('historical_snaps', "MATCH (h:HistoricalSnapCount) RETURN min(h.season) as min_year, max(h.season) as max_year, count(h) as count"),
            ('historical_ngs', "MATCH (h:HistoricalNGS) RETURN min(h.season) as min_year, max(h.season) as max_year, count(h) as count"),
            ('combine', "MATCH (c:CombineResult) RETURN min(c.season) as min_year, max(c.season) as max_year, count(c) as count"),
            ('draft', "MATCH (d:DraftPick) RETURN min(d.season) as min_year, max(d.season) as max_year, count(d) as count"),
        ]

        with self.driver.session() as session:
            for name, query in queries:
                result = session.run(query)
                record = result.single()
                if record['count'] > 0:
                    coverage[name] = {
                        'min_year': record['min_year'],
                        'max_year': record['max_year'],
                        'count': record['count']
                    }

        return coverage


# =============================================================================
# ML TRAINING DATA QUERIES
# =============================================================================

# Query to build season-over-season training pairs
SEASON_PAIR_QUERY = """
MATCH (curr:HistoricalSeasonStats)-[:NEXT_SEASON]->(next:HistoricalSeasonStats)
WHERE curr.position IN $positions
  AND curr.games >= $min_games
  AND next.games >= $min_games
RETURN curr.player_id as player_id,
       curr.player_name as player_name,
       curr.position as position,
       curr.season as season,
       curr.team as team,
       curr.games as games,
       curr.ppg_ppr as ppg_ppr,
       curr.total_fantasy_points_ppr as total_fpts,
       curr.targets as targets,
       curr.receptions as receptions,
       curr.receiving_yards as rec_yards,
       curr.carries as carries,
       curr.rushing_yards as rush_yards,
       curr.passing_yards as pass_yards,

       // Target: Next season stats
       next.season as next_season,
       next.games as next_games,
       next.ppg_ppr as next_ppg_ppr,
       next.total_fantasy_points_ppr as next_total_fpts
ORDER BY curr.season, curr.ppg_ppr DESC
"""

# Query to get rolling weekly features
WEEKLY_ROLLING_QUERY = """
MATCH (h:HistoricalWeeklyStats)
WHERE h.player_id = $player_id
  AND h.season = $season
  AND h.week <= $week
ORDER BY h.week
WITH collect(h) as weeks
WITH weeks,
     [w IN weeks | w.fantasy_points_ppr] as points,
     [w IN weeks | w.targets] as targets
RETURN size(weeks) as games_to_date,
       reduce(s=0.0, p IN points | s+p) / size(points) as ppg_to_date,
       reduce(s=0.0, p IN points[-3..] | s+p) / size(points[-3..]) as rolling_3wk_ppg,
       reduce(mx=0.0, p IN points | CASE WHEN p > mx THEN p ELSE mx END) as ceiling,
       reduce(mn=100.0, p IN points | CASE WHEN p < mn THEN p ELSE mn END) as floor
"""
