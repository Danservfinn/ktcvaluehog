"""
Unified Neo4j Schema for Dynasty Edge
Merges: NEO4J_SCHEMA_V2.md, NOVEL_VALUATION_FRAMEWORK.md, temporal_causality_architecture.md
"""

from neo4j import GraphDatabase
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# =============================================================================
# CONSTRAINTS - Ensure data integrity
# =============================================================================

CONSTRAINTS = [
    # Core entities
    "CREATE CONSTRAINT player_gsis IF NOT EXISTS FOR (p:Player) REQUIRE p.gsis_id IS UNIQUE",
    "CREATE CONSTRAINT team_abbr IF NOT EXISTS FOR (t:Team) REQUIRE t.team_abbr IS UNIQUE",
    "CREATE CONSTRAINT game_id IF NOT EXISTS FOR (g:Game) REQUIRE g.game_id IS UNIQUE",

    # Seasonal aggregates
    "CREATE CONSTRAINT player_season IF NOT EXISTS FOR (ps:PlayerSeason) REQUIRE ps.id IS UNIQUE",
    "CREATE CONSTRAINT team_season IF NOT EXISTS FOR (ts:TeamSeason) REQUIRE ts.id IS UNIQUE",

    # Fantasy
    "CREATE CONSTRAINT fantasy_league IF NOT EXISTS FOR (fl:FantasyLeague) REQUIRE fl.league_id IS UNIQUE",
    "CREATE CONSTRAINT fantasy_team IF NOT EXISTS FOR (ft:FantasyTeam) REQUIRE ft.roster_id IS UNIQUE",

    # Novel Framework nodes
    "CREATE CONSTRAINT career_stage IF NOT EXISTS FOR (cs:CareerStage) REQUIRE cs.stage_id IS UNIQUE",
    "CREATE CONSTRAINT skill_profile IF NOT EXISTS FOR (sp:SkillProfile) REQUIRE sp.profile_id IS UNIQUE",
    "CREATE CONSTRAINT scheme IF NOT EXISTS FOR (s:Scheme) REQUIRE s.scheme_id IS UNIQUE",
    "CREATE CONSTRAINT opportunity_pool IF NOT EXISTS FOR (op:OpportunityPool) REQUIRE op.pool_id IS UNIQUE",
    "CREATE CONSTRAINT ecosystem IF NOT EXISTS FOR (e:OffensiveEcosystem) REQUIRE e.ecosystem_id IS UNIQUE",

    # Temporal tracking
    "CREATE CONSTRAINT snapshot IF NOT EXISTS FOR (sn:Snapshot) REQUIRE sn.snapshot_id IS UNIQUE",
    "CREATE CONSTRAINT correlation IF NOT EXISTS FOR (c:Correlation) REQUIRE c.correlation_id IS UNIQUE",
    "CREATE CONSTRAINT model_config IF NOT EXISTS FOR (mc:ModelConfig) REQUIRE mc.config_id IS UNIQUE",
]

# =============================================================================
# INDEXES - Optimize query performance
# =============================================================================

INDEXES = [
    # Player indexes
    "CREATE INDEX player_position IF NOT EXISTS FOR (p:Player) ON (p.position)",
    "CREATE INDEX player_team IF NOT EXISTS FOR (p:Player) ON (p.current_team)",
    "CREATE INDEX player_ktc IF NOT EXISTS FOR (p:Player) ON (p.ktc_value)",
    "CREATE INDEX player_edge IF NOT EXISTS FOR (p:Player) ON (p.edge_signal)",
    "CREATE INDEX player_name IF NOT EXISTS FOR (p:Player) ON (p.name)",
    "CREATE INDEX player_sleeper IF NOT EXISTS FOR (p:Player) ON (p.sleeper_id)",
    "CREATE INDEX player_age IF NOT EXISTS FOR (p:Player) ON (p.age)",

    # Team indexes
    "CREATE INDEX team_conference IF NOT EXISTS FOR (t:Team) ON (t.conference)",
    "CREATE INDEX team_division IF NOT EXISTS FOR (t:Team) ON (t.division)",

    # Temporal indexes
    "CREATE INDEX snapshot_date IF NOT EXISTS FOR (sn:Snapshot) ON (sn.date)",
    "CREATE INDEX snapshot_player IF NOT EXISTS FOR (sn:Snapshot) ON (sn.gsis_id)",

    # Season indexes
    "CREATE INDEX player_season_season IF NOT EXISTS FOR (ps:PlayerSeason) ON (ps.season)",
    "CREATE INDEX team_season_season IF NOT EXISTS FOR (ts:TeamSeason) ON (ts.season)",

    # Game indexes
    "CREATE INDEX game_season IF NOT EXISTS FOR (g:Game) ON (g.season)",
    "CREATE INDEX game_week IF NOT EXISTS FOR (g:Game) ON (g.week)",
]

# =============================================================================
# NODE TEMPLATES - For documentation and validation
# =============================================================================

NODE_TEMPLATES = {
    "Player": {
        # Identity
        "gsis_id": "STRING (PK)",
        "sleeper_id": "STRING",
        "espn_id": "STRING",
        "pfr_id": "STRING",
        "pff_id": "STRING",
        "name": "STRING",
        "display_name": "STRING",

        # Demographics
        "position": "STRING (QB/RB/WR/TE)",
        "birth_date": "DATE",
        "age": "FLOAT",

        # Physical (from combine)
        "height": "INTEGER (inches)",
        "weight": "INTEGER (lbs)",
        "forty_time": "FLOAT",
        "bench_press": "INTEGER",
        "vertical_jump": "FLOAT",
        "broad_jump": "INTEGER",
        "three_cone": "FLOAT",
        "shuttle": "FLOAT",

        # Draft
        "draft_year": "INTEGER",
        "draft_round": "INTEGER",
        "draft_pick": "INTEGER",
        "draft_team": "STRING",
        "college": "STRING",

        # Current status
        "current_team": "STRING",
        "roster_status": "STRING",
        "depth_chart_position": "INTEGER",
        "jersey_number": "INTEGER",
        "years_exp": "INTEGER",

        # KTC Valuations
        "ktc_value": "INTEGER (SF value)",
        "ktc_value_1qb": "INTEGER",
        "ktc_rank": "INTEGER",
        "ktc_position_rank": "INTEGER",
        "ktc_updated": "DATETIME",

        # ML Predictions
        "predicted_ktc_value": "INTEGER",
        "value_delta": "INTEGER",
        "value_delta_pct": "FLOAT",
        "edge_signal": "STRING (STRONG_BUY/BUY/HOLD/SELL/STRONG_SELL)",
        "confidence_score": "FLOAT",

        # Novel Framework scores
        "chemistry_index": "FLOAT",
        "scheme_fit_score": "FLOAT",
        "opportunity_score": "FLOAT",
        "trajectory_score": "FLOAT",
        "ecosystem_role": "STRING",

        # Composite score
        "dynasty_edge_score": "FLOAT",

        # Career aggregates
        "career_games": "INTEGER",
        "career_fantasy_ppg": "FLOAT",
        "career_epa_per_play": "FLOAT",

        # Metadata
        "updated_at": "DATETIME",
    },

    "PlayerSeason": {
        "id": "STRING (gsis_id_season)",
        "gsis_id": "STRING",
        "season": "INTEGER",
        "games_played": "INTEGER",

        # Fantasy
        "fantasy_points": "FLOAT",
        "fantasy_points_ppr": "FLOAT",
        "fantasy_ppg": "FLOAT",

        # Passing
        "pass_attempts": "INTEGER",
        "completions": "INTEGER",
        "passing_yards": "INTEGER",
        "passing_tds": "INTEGER",
        "interceptions": "INTEGER",
        "passing_epa": "FLOAT",
        "cpoe": "FLOAT",

        # Rushing
        "carries": "INTEGER",
        "rushing_yards": "INTEGER",
        "rushing_tds": "INTEGER",
        "rushing_epa": "FLOAT",
        "yards_per_carry": "FLOAT",

        # Receiving
        "targets": "INTEGER",
        "receptions": "INTEGER",
        "receiving_yards": "INTEGER",
        "receiving_tds": "INTEGER",
        "receiving_epa": "FLOAT",
        "yards_per_reception": "FLOAT",
        "target_share": "FLOAT",
        "air_yards_share": "FLOAT",
        "wopr": "FLOAT",

        # Advanced
        "snap_share": "FLOAT",
        "red_zone_targets": "INTEGER",
        "red_zone_carries": "INTEGER",
    },

    "Team": {
        "team_abbr": "STRING (PK)",
        "team_name": "STRING",
        "team_nick": "STRING",
        "conference": "STRING",
        "division": "STRING",
        "team_color": "STRING",
        "team_color2": "STRING",
        "team_logo": "STRING",
    },

    "TeamSeason": {
        "id": "STRING (team_season)",
        "team_abbr": "STRING",
        "season": "INTEGER",

        # Offense
        "plays_per_game": "FLOAT",
        "pass_rate": "FLOAT",
        "pass_epa": "FLOAT",
        "rush_epa": "FLOAT",
        "total_yards": "INTEGER",
        "points_scored": "INTEGER",

        # Tendencies
        "play_action_rate": "FLOAT",
        "rpo_rate": "FLOAT",
        "screen_rate": "FLOAT",
        "red_zone_pass_rate": "FLOAT",
    },

    "Game": {
        "game_id": "STRING (PK)",
        "season": "INTEGER",
        "week": "INTEGER",
        "game_type": "STRING",
        "home_team": "STRING",
        "away_team": "STRING",
        "home_score": "INTEGER",
        "away_score": "INTEGER",
        "spread": "FLOAT",
        "over_under": "FLOAT",
        "weather": "STRING",
        "stadium": "STRING",
    },

    # Novel Framework nodes
    "CareerStage": {
        "stage_id": "STRING (PK)",
        "position": "STRING",
        "age_bucket": "STRING (22-23, 24-25, etc.)",
        "production_tier": "STRING (Elite/WR1/WR2/WR3/Depth)",
        "situation_tier": "STRING (Great/Good/Average/Poor)",
    },

    "SkillProfile": {
        "profile_id": "STRING (PK)",
        "route_diversity": "FLOAT (0-100)",
        "separation_ability": "FLOAT (0-100)",
        "contested_catch": "FLOAT (0-100)",
        "yac_ability": "FLOAT (0-100)",
        "speed_score": "FLOAT (0-100)",
        "size_score": "FLOAT (0-100)",
    },

    "Scheme": {
        "scheme_id": "STRING (PK)",
        "name": "STRING",
        "family": "STRING (West Coast/Air Raid/Shanahan/etc.)",
        "route_diversity_weight": "FLOAT",
        "separation_weight": "FLOAT",
        "contested_weight": "FLOAT",
        "yac_weight": "FLOAT",
        "speed_weight": "FLOAT",
        "size_weight": "FLOAT",
    },

    "OpportunityPool": {
        "pool_id": "STRING (team_season)",
        "team_abbr": "STRING",
        "season": "INTEGER",
        "total_targets": "INTEGER",
        "total_carries": "INTEGER",
        "total_air_yards": "INTEGER",
        "red_zone_opportunities": "INTEGER",
        "target_elasticity": "FLOAT",
    },

    "OffensiveEcosystem": {
        "ecosystem_id": "STRING (team_season)",
        "team_abbr": "STRING",
        "season": "INTEGER",
        "total_fantasy_points": "FLOAT",
        "point_concentration": "FLOAT (Gini coefficient)",
        "alpha_dependency": "FLOAT",
        "depth_score": "FLOAT",
        "robustness": "FLOAT",
    },

    # Temporal tracking nodes
    "Snapshot": {
        "snapshot_id": "STRING (gsis_id_date)",
        "gsis_id": "STRING",
        "date": "DATE",

        # Values
        "ktc_value": "INTEGER",
        "ktc_delta": "INTEGER",
        "ktc_delta_pct": "FLOAT",

        # Stats at time
        "targets": "INTEGER",
        "targets_per_game": "FLOAT",
        "receptions": "INTEGER",
        "fantasy_ppg": "FLOAT",

        # Usage
        "snap_share": "FLOAT",
        "target_share": "FLOAT",
        "air_yards_share": "FLOAT",

        # Context
        "games_played": "INTEGER",
        "injury_status": "STRING",
    },

    "Correlation": {
        "correlation_id": "STRING (PK)",
        "metric_name": "STRING",
        "position": "STRING",
        "pearson_r": "FLOAT",
        "p_value": "FLOAT",
        "sample_size": "INTEGER",
        "lookback_days": "INTEGER",
        "discovered_date": "DATE",
        "strength": "STRING (Strong/Moderate/Weak/None)",
        "direction": "STRING (Positive/Negative)",
        "current_weight": "FLOAT",
        "suggested_weight": "FLOAT",
    },

    "ModelConfig": {
        "config_id": "STRING (PK)",
        "created_date": "DATETIME",
        "created_by": "STRING",
        "is_active": "BOOLEAN",
        "weights": "MAP",
        "performance_rmse": "FLOAT",
        "performance_r2": "FLOAT",
    },

    # Fantasy league nodes
    "FantasyLeague": {
        "league_id": "STRING (PK)",
        "name": "STRING",
        "platform": "STRING (sleeper)",
        "scoring": "STRING (ppr/half/standard)",
        "roster_size": "INTEGER",
        "num_teams": "INTEGER",
        "superflex": "BOOLEAN",
        "te_premium": "FLOAT",
    },

    "FantasyTeam": {
        "roster_id": "STRING (PK)",
        "league_id": "STRING",
        "owner_id": "STRING",
        "team_name": "STRING",
        "wins": "INTEGER",
        "losses": "INTEGER",
        "points_for": "FLOAT",
        "points_against": "FLOAT",
    },
}

# =============================================================================
# RELATIONSHIP TEMPLATES
# =============================================================================

RELATIONSHIP_TEMPLATES = {
    # Core relationships
    "PLAYS_FOR": {
        "from": "Player",
        "to": "Team",
        "properties": {
            "season": "INTEGER",
            "start_date": "DATE",
            "end_date": "DATE",
        }
    },

    "HAD_SEASON": {
        "from": "Player",
        "to": "PlayerSeason",
        "properties": {}
    },

    "TEAM_HAD_SEASON": {
        "from": "Team",
        "to": "TeamSeason",
        "properties": {}
    },

    "PLAYED_IN": {
        "from": "Player",
        "to": "Game",
        "properties": {
            "fantasy_points": "FLOAT",
            "snaps": "INTEGER",
        }
    },

    # Graph-derived relationships
    "TARGETS_FROM": {
        "from": "Player (WR/TE/RB)",
        "to": "Player (QB)",
        "properties": {
            "season": "INTEGER",
            "targets": "INTEGER",
            "receptions": "INTEGER",
            "yards": "INTEGER",
            "tds": "INTEGER",
            "target_share": "FLOAT",
            "epa_per_target": "FLOAT",
        }
    },

    "COMPETES_WITH": {
        "from": "Player",
        "to": "Player",
        "properties": {
            "season": "INTEGER",
            "same_position": "BOOLEAN",
            "same_team": "BOOLEAN",
        }
    },

    # Novel Framework relationships
    "CHEMISTRY_WITH": {
        "from": "Player (WR/TE)",
        "to": "Player (QB)",
        "properties": {
            "season": "INTEGER",
            "catchable_differential": "FLOAT",
            "trust_score": "FLOAT",
            "depth_preference": "FLOAT",
            "contested_confidence": "FLOAT",
            "chemistry_index": "FLOAT",
            "chemistry_percentile": "INTEGER",
        }
    },

    "CAPTURES_OPPORTUNITY": {
        "from": "Player",
        "to": "OpportunityPool",
        "properties": {
            "target_share": "FLOAT",
            "carry_share": "FLOAT",
            "air_yard_share": "FLOAT",
            "red_zone_share": "FLOAT",
            "opportunity_score": "FLOAT",
        }
    },

    "CANNIBALIZES": {
        "from": "Player",
        "to": "Player",
        "properties": {
            "season": "INTEGER",
            "elasticity": "FLOAT",
            "correlation": "FLOAT",
        }
    },

    "WAS_AT_STAGE": {
        "from": "Player",
        "to": "CareerStage",
        "properties": {
            "season": "INTEGER",
            "fantasy_ppg": "FLOAT",
            "ktc_value": "INTEGER",
        }
    },

    "STAGE_LEADS_TO": {
        "from": "CareerStage",
        "to": "CareerStage",
        "properties": {
            "probability": "FLOAT",
            "avg_seasons": "FLOAT",
            "sample_size": "INTEGER",
        }
    },

    "HAS_PROFILE": {
        "from": "Player",
        "to": "SkillProfile",
        "properties": {
            "season": "INTEGER",
        }
    },

    "RUNS_SCHEME": {
        "from": "Team",
        "to": "Scheme",
        "properties": {
            "season": "INTEGER",
            "coordinator": "STRING",
        }
    },

    "FITS_SCHEME": {
        "from": "SkillProfile",
        "to": "Scheme",
        "properties": {
            "fit_score": "FLOAT",
            "ceiling": "FLOAT",
            "floor": "FLOAT",
        }
    },

    "ROLE_IN_ECOSYSTEM": {
        "from": "Player",
        "to": "OffensiveEcosystem",
        "properties": {
            "role": "STRING (alpha/beta/gamma/specialist)",
            "ecosystem_share": "FLOAT",
            "replaceability": "FLOAT",
            "system_impact": "FLOAT",
        }
    },

    # Temporal relationships
    "HAD_SNAPSHOT": {
        "from": "Player",
        "to": "Snapshot",
        "properties": {}
    },

    "SNAPSHOT_NEXT": {
        "from": "Snapshot",
        "to": "Snapshot",
        "properties": {
            "days_between": "INTEGER",
        }
    },

    "DISCOVERED_CORRELATION": {
        "from": "ModelConfig",
        "to": "Correlation",
        "properties": {
            "weight_applied": "FLOAT",
        }
    },

    # Fantasy relationships
    "OWNS_PLAYER": {
        "from": "FantasyTeam",
        "to": "Player",
        "properties": {
            "acquired_date": "DATE",
            "acquisition_type": "STRING (draft/trade/waiver)",
            "acquisition_cost": "INTEGER",
        }
    },

    "TRADED_FOR": {
        "from": "FantasyTeam",
        "to": "Player",
        "properties": {
            "date": "DATE",
            "gave_up_value": "INTEGER",
            "team_record": "STRING",
        }
    },

    "IN_LEAGUE": {
        "from": "FantasyTeam",
        "to": "FantasyLeague",
        "properties": {}
    },
}


class UnifiedSchemaManager:
    """Manages the unified Neo4j schema."""

    def __init__(self, driver_or_uri, user: Optional[str] = None, password: Optional[str] = None):
        """Initialize with either a driver instance or URI string.

        Args:
            driver_or_uri: Either a Neo4j driver instance or a URI string
            user: Username (only used if URI string provided)
            password: Password (only used if URI string provided)
        """
        if isinstance(driver_or_uri, str):
            # It's a URI, create driver
            if user and password:
                self.driver = GraphDatabase.driver(driver_or_uri, auth=(user, password))
            else:
                self.driver = GraphDatabase.driver(driver_or_uri, auth=None)
            self._owns_driver = True
        else:
            # It's already a driver
            self.driver = driver_or_uri
            self._owns_driver = False

    def close(self):
        if self._owns_driver:
            self.driver.close()

    def create_schema(self):
        """Create all constraints and indexes."""
        with self.driver.session() as session:
            # Create constraints
            logger.info("Creating constraints...")
            for constraint in CONSTRAINTS:
                try:
                    session.run(constraint)
                    logger.debug(f"Created: {constraint[:50]}...")
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        logger.warning(f"Constraint warning: {e}")

            # Create indexes
            logger.info("Creating indexes...")
            for index in INDEXES:
                try:
                    session.run(index)
                    logger.debug(f"Created: {index[:50]}...")
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        logger.warning(f"Index warning: {e}")

        logger.info("Schema creation complete.")

    def get_schema_stats(self) -> dict:
        """Get statistics about the current schema."""
        with self.driver.session() as session:
            stats = {'nodes': {}, 'relationships': {}}

            # Count nodes by label (without APOC)
            for label in NODE_TEMPLATES.keys():
                try:
                    result = session.run(f"MATCH (n:{label}) RETURN count(n) as count")
                    record = result.single()
                    if record:
                        stats['nodes'][label] = record['count']
                except Exception as e:
                    logger.debug(f"Could not count {label}: {e}")

            # Count relationships
            try:
                result = session.run("""
                    MATCH ()-[r]->()
                    RETURN type(r) as type, count(r) as count
                """)
                stats['relationships'] = {r['type']: r['count'] for r in result}
            except Exception as e:
                logger.debug(f"Could not count relationships: {e}")

            return stats

    def validate_schema(self) -> dict:
        """Validate that all expected schema elements exist."""
        with self.driver.session() as session:
            validation = {
                'constraints': {'expected': len(CONSTRAINTS), 'found': 0},
                'indexes': {'expected': len(INDEXES), 'found': 0},
                'issues': []
            }

            # Check constraints
            result = session.run("SHOW CONSTRAINTS")
            validation['constraints']['found'] = len(list(result))

            # Check indexes
            result = session.run("SHOW INDEXES")
            validation['indexes']['found'] = len(list(result))

            # Check for missing node types
            for label in NODE_TEMPLATES.keys():
                result = session.run(f"MATCH (n:{label}) RETURN count(n) as count LIMIT 1")
                # Just checking if query works, not if data exists

            return validation


def initialize_schema(uri: str = "bolt://localhost:7687",
                      user: Optional[str] = None,
                      password: Optional[str] = None) -> UnifiedSchemaManager:
    """Initialize the unified schema."""
    manager = UnifiedSchemaManager(uri, user, password)
    manager.create_schema()
    return manager


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    manager = initialize_schema()
    stats = manager.get_schema_stats()
    print("Schema Stats:", stats)
    manager.close()
