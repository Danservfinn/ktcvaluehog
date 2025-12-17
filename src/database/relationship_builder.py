"""
Graph Relationship Builder for Dynasty Edge
From: NEO4J_ML_IMPLEMENTATION_PROPOSAL.md and IMPLEMENTATION_PLAN_V2.md

Creates all Neo4j relationships needed for ML feature engineering:
- TARGETS_FROM: WR/TE → QB targeting relationship
- COMPETES_WITH: Same-position teammates
- PLAYS_FOR: Player → Team
- HAD_SEASON: Player → PlayerSeason
- HAD_SNAPSHOT: Player → Snapshot (temporal tracking)
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)


class RelationshipBuilder:
    """Builds all graph relationships from data."""

    def __init__(self, driver):
        self.driver = driver

    def build_all_relationships(self, season: int = 2025):
        """Build all relationships for a season."""
        logger.info(f"Building all relationships for season {season}...")

        results = {}

        # Core relationships
        results['plays_for'] = self.create_plays_for_relationships(season)
        results['targets_from'] = self.create_targets_from_relationships(season)
        results['competes_with'] = self.create_competes_with_relationships(season)
        results['handed_off_to'] = self.create_handed_off_to_relationships(season)

        logger.info(f"Relationship building complete: {results}")
        return results

    def create_plays_for_relationships(self, season: int = 2025) -> int:
        """Create PLAYS_FOR relationships from roster data."""
        query = """
        MATCH (p:Player)
        WHERE p.current_team IS NOT NULL
        MATCH (t:Team {team_abbr: p.current_team})
        MERGE (p)-[r:PLAYS_FOR]->(t)
        SET r.season = $season,
            r.updated_at = datetime()
        RETURN count(r) as count
        """
        with self.driver.session() as session:
            result = session.run(query, {'season': season})
            count = result.single()['count']
            logger.info(f"Created {count} PLAYS_FOR relationships")
            return count

    def create_targets_from_relationships(self, season: int = 2025) -> int:
        """Create TARGETS_FROM relationships (WR/TE → QB).

        Uses play-by-play data to aggregate QB-receiver connections.
        """
        # First, try from play-by-play aggregated data
        query = """
        // Find QB-receiver connections within same team
        MATCH (qb:Player {position: 'QB'})-[:PLAYS_FOR]->(t:Team)
        MATCH (rec:Player)-[:PLAYS_FOR]->(t)
        WHERE rec.position IN ['WR', 'TE']
          AND rec.targets IS NOT NULL
          AND rec.targets > 0

        // Create relationship with target metrics
        MERGE (rec)-[r:TARGETS_FROM]->(qb)
        SET r.season = $season,
            r.targets = rec.targets,
            r.receptions = rec.receptions,
            r.receiving_yards = rec.receiving_yards,
            r.receiving_tds = rec.receiving_tds,
            r.target_share = CASE
                WHEN qb.pass_attempts > 0
                THEN toFloat(rec.targets) / qb.pass_attempts
                ELSE 0
            END,
            r.catch_rate = CASE
                WHEN rec.targets > 0
                THEN toFloat(rec.receptions) / rec.targets
                ELSE 0
            END,
            r.yards_per_target = CASE
                WHEN rec.targets > 0
                THEN toFloat(rec.receiving_yards) / rec.targets
                ELSE 0
            END
        RETURN count(r) as count
        """
        with self.driver.session() as session:
            result = session.run(query, {'season': season})
            count = result.single()['count']
            logger.info(f"Created {count} TARGETS_FROM relationships")
            return count

    def create_competes_with_relationships(self, season: int = 2025) -> int:
        """Create COMPETES_WITH relationships (same-position teammates)."""
        query = """
        MATCH (p1:Player)-[:PLAYS_FOR]->(t:Team)
        MATCH (p2:Player)-[:PLAYS_FOR]->(t)
        WHERE p1.position = p2.position
          AND p1.position IN ['RB', 'WR', 'TE']
          AND p1.gsis_id < p2.gsis_id  // Avoid duplicates
          AND p1.ktc_value > 500 AND p2.ktc_value > 500  // Only relevant players
        MERGE (p1)-[r:COMPETES_WITH]-(p2)
        SET r.season = $season,
            r.team = t.team_abbr,
            r.position = p1.position,
            r.value_ratio = toFloat(p1.ktc_value) / p2.ktc_value
        RETURN count(r) as count
        """
        with self.driver.session() as session:
            result = session.run(query, {'season': season})
            count = result.single()['count']
            logger.info(f"Created {count} COMPETES_WITH relationships")
            return count

    def create_handed_off_to_relationships(self, season: int = 2025) -> int:
        """Create HANDED_OFF_TO relationships (QB → RB)."""
        query = """
        MATCH (qb:Player {position: 'QB'})-[:PLAYS_FOR]->(t:Team)
        MATCH (rb:Player {position: 'RB'})-[:PLAYS_FOR]->(t)
        WHERE rb.carries IS NOT NULL AND rb.carries > 0
        MERGE (qb)-[r:HANDED_OFF_TO]->(rb)
        SET r.season = $season,
            r.carries = rb.carries,
            r.rushing_yards = rb.rushing_yards,
            r.rushing_tds = rb.rushing_tds,
            r.carry_share = CASE
                WHEN qb.pass_attempts IS NOT NULL AND (qb.pass_attempts + rb.carries) > 0
                THEN toFloat(rb.carries) / (qb.pass_attempts + rb.carries)
                ELSE 0
            END
        RETURN count(r) as count
        """
        with self.driver.session() as session:
            result = session.run(query, {'season': season})
            count = result.single()['count']
            logger.info(f"Created {count} HANDED_OFF_TO relationships")
            return count

    def create_similar_profile_relationships(self, max_comparisons: int = 10) -> int:
        """Create SIMILAR_PROFILE relationships based on player attributes.

        Uses age, position, draft capital, and production to find comparable players.
        """
        query = """
        MATCH (p1:Player)
        WHERE p1.position IN ['QB', 'RB', 'WR', 'TE']
          AND p1.ktc_value > 2000
          AND p1.age IS NOT NULL

        // Find similar players
        MATCH (p2:Player)
        WHERE p2.position = p1.position
          AND p2.gsis_id <> p1.gsis_id
          AND p2.age IS NOT NULL
          AND p2.ktc_value > 1000

        // Calculate similarity score
        WITH p1, p2,
             // Age similarity (within 2 years = 1.0, decreases after)
             1.0 / (1.0 + abs(p1.age - p2.age)) as age_sim,
             // Draft capital similarity
             CASE
                 WHEN p1.draft_round IS NOT NULL AND p2.draft_round IS NOT NULL
                 THEN 1.0 / (1.0 + abs(p1.draft_round - p2.draft_round))
                 ELSE 0.5
             END as draft_sim,
             // Value similarity
             1.0 / (1.0 + abs(p1.ktc_value - p2.ktc_value) / 1000.0) as value_sim

        WITH p1, p2,
             0.3 * age_sim + 0.3 * draft_sim + 0.4 * value_sim as similarity
        WHERE similarity > 0.5

        ORDER BY p1.gsis_id, similarity DESC

        // Keep only top N similar players per player
        WITH p1, collect({player: p2, sim: similarity})[0..$max] as top_similar
        UNWIND top_similar as sim
        WITH p1, sim.player as p2, sim.sim as similarity_score

        MERGE (p1)-[r:SIMILAR_PROFILE]->(p2)
        SET r.similarity_score = similarity_score,
            r.dimensions = ['age', 'draft_capital', 'value']

        RETURN count(r) as count
        """
        with self.driver.session() as session:
            result = session.run(query, {'max': max_comparisons})
            count = result.single()['count']
            logger.info(f"Created {count} SIMILAR_PROFILE relationships")
            return count

    def create_team_season_relationships(self, season: int = 2025) -> int:
        """Create HAD_SEASON relationships between Team and TeamSeason."""
        query = """
        MATCH (t:Team)
        WHERE t.team_abbr IS NOT NULL
        MERGE (ts:TeamSeason {team_abbr: t.team_abbr, season: $season})
        MERGE (t)-[r:HAD_SEASON]->(ts)
        SET ts.updated_at = datetime()
        RETURN count(r) as count
        """
        with self.driver.session() as session:
            result = session.run(query, {'season': season})
            count = result.single()['count']
            logger.info(f"Created {count} HAD_SEASON relationships")
            return count

    def create_player_season_relationships(self, season: int = 2025) -> int:
        """Create HAD_SEASON relationships between Player and PlayerSeason."""
        query = """
        MATCH (p:Player)
        WHERE p.position IN ['QB', 'RB', 'WR', 'TE']
          AND p.ktc_value > 500
          AND p.gsis_id IS NOT NULL
        MERGE (ps:PlayerSeason {gsis_id: p.gsis_id, season: $season})
        MERGE (p)-[r:HAD_SEASON]->(ps)
        SET ps.ktc_value = p.ktc_value,
            ps.fantasy_points = p.fantasy_points_season,
            ps.updated_at = datetime()
        RETURN count(r) as count
        """
        with self.driver.session() as session:
            result = session.run(query, {'season': season})
            count = result.single()['count']
            logger.info(f"Created {count} player HAD_SEASON relationships")
            return count


class TargetingRelationshipBuilder:
    """Specialized builder for QB-receiver targeting relationships using PBP data."""

    def __init__(self, driver):
        self.driver = driver

    def build_from_pbp(self, pbp_df: pd.DataFrame, season: int = 2025) -> int:
        """Build TARGETS_FROM relationships from play-by-play data."""
        if pbp_df.empty:
            logger.warning("Empty PBP data, skipping targeting relationships")
            return 0

        # Aggregate QB-receiver connections
        pass_plays = pbp_df[pbp_df['pass_attempt'] == 1].copy()

        if pass_plays.empty:
            return 0

        aggregated = pass_plays.groupby(
            ['passer_player_id', 'receiver_player_id']
        ).agg({
            'play_id': 'count',
            'complete_pass': 'sum',
            'yards_gained': 'sum',
            'touchdown': 'sum',
            'epa': 'mean',
            'air_yards': 'mean'
        }).reset_index()

        aggregated.columns = ['qb_id', 'rec_id', 'targets', 'receptions',
                              'yards', 'tds', 'epa_per_target', 'avg_air_yards']

        # Filter to significant connections
        aggregated = aggregated[aggregated['targets'] >= 5]

        count = 0
        with self.driver.session() as session:
            for _, row in aggregated.iterrows():
                if pd.isna(row['qb_id']) or pd.isna(row['rec_id']):
                    continue

                try:
                    session.run("""
                        MATCH (qb:Player {gsis_id: $qb_id})
                        MATCH (rec:Player {gsis_id: $rec_id})
                        MERGE (rec)-[r:TARGETS_FROM]->(qb)
                        SET r.season = $season,
                            r.targets = $targets,
                            r.receptions = $receptions,
                            r.receiving_yards = $yards,
                            r.receiving_tds = $tds,
                            r.epa_per_target = $epa,
                            r.avg_air_yards = $air_yards,
                            r.catch_rate = toFloat($receptions) / $targets
                    """, {
                        'qb_id': row['qb_id'],
                        'rec_id': row['rec_id'],
                        'season': season,
                        'targets': int(row['targets']),
                        'receptions': int(row['receptions']),
                        'yards': int(row['yards']),
                        'tds': int(row['tds']),
                        'epa': float(row['epa_per_target']) if pd.notna(row['epa_per_target']) else 0,
                        'air_yards': float(row['avg_air_yards']) if pd.notna(row['avg_air_yards']) else 0
                    })
                    count += 1
                except Exception as e:
                    logger.warning(f"Failed to create targeting relationship: {e}")

        logger.info(f"Created {count} TARGETS_FROM relationships from PBP")
        return count


class ChemistryRelationshipBuilder:
    """Builds QB-receiver chemistry relationships from FTN charting data."""

    def __init__(self, driver):
        self.driver = driver

    def build_from_ftn(self, ftn_df: pd.DataFrame, season: int = 2025) -> int:
        """Build CHEMISTRY_WITH relationships from FTN charting data."""
        if ftn_df.empty:
            logger.warning("Empty FTN data, skipping chemistry relationships")
            return 0

        # Aggregate receiver metrics
        pass_plays = ftn_df[ftn_df['pass_attempt'] == 1].copy()

        if pass_plays.empty:
            return 0

        # Receiver-level aggregates
        receiver_stats = pass_plays.groupby(
            ['passer_player_id', 'receiver_player_id']
        ).agg({
            'play_id': 'count',
            'is_catchable_ball': 'mean',
            'is_contested_ball': 'mean',
            'is_drop': 'mean',
            'n_blitzers': 'mean',
        }).reset_index()

        # Team averages for comparison
        team_avgs = pass_plays.groupby('passer_player_id').agg({
            'is_catchable_ball': 'mean'
        }).reset_index()
        team_avgs.columns = ['passer_player_id', 'team_avg_catchable']

        # Merge
        receiver_stats = receiver_stats.merge(team_avgs, on='passer_player_id', how='left')

        # Calculate chemistry components
        receiver_stats['target_quality_diff'] = (
            receiver_stats['is_catchable_ball'] - receiver_stats['team_avg_catchable']
        )

        # Trust score placeholder (would need red zone, 3rd down data)
        receiver_stats['trust_score'] = receiver_stats['is_catchable_ball'] * 0.8

        # Calculate CQI
        receiver_stats['cqi_score'] = (
            0.3 * (50 + receiver_stats['target_quality_diff'] * 100) +
            0.25 * receiver_stats['trust_score'] * 100 +
            0.25 * 50 +  # depth placeholder
            0.20 * (1 - receiver_stats['is_drop']) * 100
        )

        # Filter to significant connections
        receiver_stats = receiver_stats[receiver_stats['play_id'] >= 10]

        count = 0
        with self.driver.session() as session:
            for _, row in receiver_stats.iterrows():
                if pd.isna(row['passer_player_id']) or pd.isna(row['receiver_player_id']):
                    continue

                try:
                    session.run("""
                        MATCH (qb:Player {gsis_id: $qb_id})
                        MATCH (rec:Player {gsis_id: $rec_id})
                        MERGE (rec)-[c:CHEMISTRY_WITH]->(qb)
                        SET c.season = $season,
                            c.catchable_rate = $catchable_rate,
                            c.contested_rate = $contested_rate,
                            c.drop_rate = $drop_rate,
                            c.target_quality_differential = $tq_diff,
                            c.trust_score = $trust,
                            c.cqi_score = $cqi
                    """, {
                        'qb_id': row['passer_player_id'],
                        'rec_id': row['receiver_player_id'],
                        'season': season,
                        'catchable_rate': float(row['is_catchable_ball']) if pd.notna(row['is_catchable_ball']) else 0.7,
                        'contested_rate': float(row['is_contested_ball']) if pd.notna(row['is_contested_ball']) else 0.15,
                        'drop_rate': float(row['is_drop']) if pd.notna(row['is_drop']) else 0.05,
                        'tq_diff': float(row['target_quality_diff']) if pd.notna(row['target_quality_diff']) else 0,
                        'trust': float(row['trust_score']) if pd.notna(row['trust_score']) else 0.5,
                        'cqi': float(row['cqi_score']) if pd.notna(row['cqi_score']) else 50
                    })
                    count += 1
                except Exception as e:
                    logger.warning(f"Failed to create chemistry relationship: {e}")

        logger.info(f"Created {count} CHEMISTRY_WITH relationships from FTN")
        return count


class TrajectoryRelationshipBuilder:
    """Builds career trajectory relationships."""

    def __init__(self, driver):
        self.driver = driver

    def build_historical_trajectories(self, historical_stats: pd.DataFrame) -> int:
        """Build WAS_AT_STAGE relationships from historical data."""
        if historical_stats.empty:
            return 0

        count = 0
        with self.driver.session() as session:
            # For each player-season, assign to career stage
            for _, row in historical_stats.iterrows():
                if pd.isna(row.get('gsis_id')) or pd.isna(row.get('season')):
                    continue

                try:
                    session.run("""
                        MATCH (p:Player {gsis_id: $gsis_id})
                        WITH p,
                             CASE p.position
                                 WHEN 'RB' THEN
                                     CASE
                                         WHEN $age <= 22 THEN '21-22'
                                         WHEN $age <= 24 THEN '23-24'
                                         WHEN $age <= 26 THEN '25-26'
                                         WHEN $age <= 28 THEN '27-28'
                                         ELSE '29+'
                                     END
                                 WHEN 'WR' THEN
                                     CASE
                                         WHEN $age <= 23 THEN '21-23'
                                         WHEN $age <= 26 THEN '24-26'
                                         WHEN $age <= 29 THEN '27-29'
                                         WHEN $age <= 32 THEN '30-32'
                                         ELSE '33+'
                                     END
                                 ELSE
                                     CASE
                                         WHEN $age <= 24 THEN '21-24'
                                         WHEN $age <= 27 THEN '25-27'
                                         WHEN $age <= 30 THEN '28-30'
                                         WHEN $age <= 33 THEN '31-33'
                                         ELSE '34+'
                                     END
                             END as age_bucket,
                             CASE
                                 WHEN $fantasy_ppg >= 18 THEN 'Elite'
                                 WHEN $fantasy_ppg >= 14 THEN 'Tier1'
                                 WHEN $fantasy_ppg >= 10 THEN 'Tier2'
                                 WHEN $fantasy_ppg >= 6 THEN 'Tier3'
                                 ELSE 'Depth'
                             END as production_tier

                        MATCH (cs:CareerStage {
                            position: p.position,
                            age_bucket: age_bucket,
                            production_tier: production_tier
                        })
                        MERGE (p)-[r:WAS_AT_STAGE]->(cs)
                        SET r.season = $season,
                            r.fantasy_ppg = $fantasy_ppg,
                            r.ktc_value = $ktc_value
                    """, {
                        'gsis_id': row['gsis_id'],
                        'season': int(row['season']),
                        'age': int(row.get('age', 25)),
                        'fantasy_ppg': float(row.get('fantasy_ppg', 0)),
                        'ktc_value': int(row.get('ktc_value', 0)) if pd.notna(row.get('ktc_value')) else 0
                    })
                    count += 1
                except Exception as e:
                    logger.warning(f"Failed to create trajectory relationship: {e}")

        logger.info(f"Created {count} WAS_AT_STAGE relationships")
        return count

    def calculate_transition_probabilities(self) -> int:
        """Calculate and store transition probabilities between career stages."""
        query = """
        // Find all season-to-season transitions
        MATCH (p:Player)-[r1:WAS_AT_STAGE]->(cs1:CareerStage)
        MATCH (p)-[r2:WAS_AT_STAGE]->(cs2:CareerStage)
        WHERE r2.season = r1.season + 1

        // Count transitions
        WITH cs1, cs2, count(*) as transitions

        // Get total transitions from cs1
        WITH cs1, cs2, transitions
        MATCH (p2:Player)-[r:WAS_AT_STAGE]->(cs1)
        WITH cs1, cs2, transitions, count(DISTINCT r) as total_from

        // Create TYPICALLY_LEADS_TO relationship
        MERGE (cs1)-[t:TYPICALLY_LEADS_TO]->(cs2)
        SET t.transitions = transitions,
            t.probability = toFloat(transitions) / total_from,
            t.sample_size = transitions

        RETURN count(t) as count
        """
        with self.driver.session() as session:
            result = session.run(query)
            count = result.single()['count']
            logger.info(f"Calculated {count} career transition probabilities")
            return count


class MasterRelationshipBuilder:
    """Master class for building all relationships."""

    def __init__(self, driver):
        self.driver = driver
        self.core_builder = RelationshipBuilder(driver)
        self.targeting_builder = TargetingRelationshipBuilder(driver)
        self.chemistry_builder = ChemistryRelationshipBuilder(driver)
        self.trajectory_builder = TrajectoryRelationshipBuilder(driver)

    def build_all(self, season: int = 2025,
                  pbp_df: pd.DataFrame = None,
                  ftn_df: pd.DataFrame = None,
                  historical_df: pd.DataFrame = None) -> Dict[str, int]:
        """Build all relationships."""
        results = {}

        logger.info("Building all graph relationships...")

        # Core relationships
        results.update(self.core_builder.build_all_relationships(season))

        # PBP-based targeting (if available)
        if pbp_df is not None and not pbp_df.empty:
            results['targets_from_pbp'] = self.targeting_builder.build_from_pbp(pbp_df, season)

        # FTN-based chemistry (if available)
        if ftn_df is not None and not ftn_df.empty:
            results['chemistry'] = self.chemistry_builder.build_from_ftn(ftn_df, season)

        # Historical trajectory (if available)
        if historical_df is not None and not historical_df.empty:
            results['trajectories'] = self.trajectory_builder.build_historical_trajectories(historical_df)
            results['transitions'] = self.trajectory_builder.calculate_transition_probabilities()

        # Similar profiles
        results['similar_profiles'] = self.core_builder.create_similar_profile_relationships()

        # Season relationships
        results['team_seasons'] = self.core_builder.create_team_season_relationships(season)
        results['player_seasons'] = self.core_builder.create_player_season_relationships(season)

        logger.info(f"Relationship building complete: {sum(results.values())} total relationships")
        return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from neo4j import GraphDatabase

    # Test with local Neo4j
    driver = GraphDatabase.driver("bolt://localhost:7687", auth=None)

    builder = MasterRelationshipBuilder(driver)
    results = builder.build_all(season=2025)

    print("\nRelationship Build Results:")
    for key, count in results.items():
        print(f"  {key}: {count}")

    driver.close()
