"""
Neo4j Schema Extensions for College Football Data Pipeline.

Adds nodes and relationships for:
- College prospects (pre-NFL draft)
- College teams and conferences
- College statistics by season
- NFL Combine results
- Devy value snapshots (time-series)
- Knowledge base insights (agent learnings)

This extends the existing unified_schema.py without modifying core nodes.
"""

import os
import logging
from typing import Dict, List, Optional
from neo4j import GraphDatabase
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class CollegeSchemaManager:
    """Manages Neo4j schema extensions for college football data."""

    # =========================================================================
    # CONSTRAINT DEFINITIONS
    # =========================================================================

    CONSTRAINTS = [
        # Prospect (college player before NFL draft)
        ("prospect_id_unique", "Prospect", "prospect_id"),

        # College team
        ("college_team_id_unique", "CollegeTeam", "team_id"),

        # College conference
        ("conference_id_unique", "Conference", "conference_id"),

        # College season stats
        ("college_stats_id_unique", "CollegeStats", "stats_id"),

        # Combine result (one per player per year)
        ("combine_id_unique", "CombineResult", "combine_id"),

        # Devy value snapshot (time-series)
        ("devy_snapshot_id_unique", "DevySnapshot", "snapshot_id"),

        # Knowledge base insight
        ("insight_id_unique", "Insight", "insight_id"),

        # Draft class
        ("draft_class_unique", "DraftClass", "class_id"),
    ]

    # =========================================================================
    # INDEX DEFINITIONS
    # =========================================================================

    INDEXES = [
        # Prospect lookups
        ("prospect_name_idx", "Prospect", ["name"]),
        ("prospect_position_idx", "Prospect", ["position"]),
        ("prospect_college_idx", "Prospect", ["college_team_id"]),
        ("prospect_eligibility_idx", "Prospect", ["eligibility_year"]),
        ("prospect_stars_idx", "Prospect", ["recruiting_stars"]),
        ("prospect_score_idx", "Prospect", ["prospect_score"]),

        # College team lookups
        ("college_team_name_idx", "CollegeTeam", ["name"]),
        ("college_team_conference_idx", "CollegeTeam", ["conference"]),

        # College stats
        ("college_stats_season_idx", "CollegeStats", ["season"]),

        # Combine lookups
        ("combine_year_idx", "CombineResult", ["combine_year"]),
        ("combine_forty_idx", "CombineResult", ["forty_yard"]),
        ("combine_ras_idx", "CombineResult", ["ras_score"]),

        # Devy snapshot lookups
        ("devy_date_idx", "DevySnapshot", ["date"]),
        ("devy_value_idx", "DevySnapshot", ["ktc_devy_value"]),

        # Insight lookups
        ("insight_type_idx", "Insight", ["insight_type"]),
        ("insight_confidence_idx", "Insight", ["confidence"]),
        ("insight_created_idx", "Insight", ["created_date"]),
    ]

    # =========================================================================
    # NODE PROPERTY SCHEMAS (for documentation)
    # =========================================================================

    NODE_SCHEMAS = {
        "Prospect": {
            "description": "College football player before NFL draft",
            "properties": {
                "prospect_id": "Unique identifier (composite of name + college + year)",
                "name": "Player full name",
                "position": "Fantasy position (QB, RB, WR, TE)",
                "height": "Height in inches",
                "weight": "Weight in pounds",
                "college_team_id": "Reference to CollegeTeam node",
                "recruiting_stars": "247Sports star rating (2-5)",
                "recruiting_rank": "National recruiting rank",
                "composite_rating": "247 composite rating (0.0-1.0)",
                "eligibility_year": "Expected draft eligibility year",
                "hometown_state": "Home state abbreviation",
                "is_drafted": "Whether player has been drafted",
                "nfl_player_id": "Links to Player node after draft (gsis_id)",

                # Calculated features
                "dominator_rating": "% of team receiving production",
                "breakout_age": "Age at first 20% dominator season",
                "market_share_yards": "% of team total yards",
                "market_share_tds": "% of team total TDs",
                "speed_score": "Weight-adjusted 40 time score",
                "burst_score": "Combined vertical + broad jump",
                "agility_score": "Combined 3-cone + shuttle",
                "prospect_score": "Overall prospect grade (0-100)",

                # Metadata
                "created_at": "Node creation timestamp",
                "updated_at": "Last update timestamp"
            }
        },

        "CollegeTeam": {
            "description": "FBS college football team",
            "properties": {
                "team_id": "Unique team identifier",
                "name": "Team name (e.g., 'Ohio State')",
                "mascot": "Team mascot",
                "conference": "Conference name",
                "division": "Conference division (if applicable)",
                "sp_plus_rating": "SP+ team rating (Bill Connelly)",
                "talent_composite": "Team talent composite rating",
                "recruiting_rank": "Annual recruiting class rank",
                "offensive_scheme": "Offensive system (Air Raid, Pro Style, etc.)",
                "head_coach": "Current head coach name",
                "colors": "Team colors",
                "logo_url": "Team logo URL"
            }
        },

        "Conference": {
            "description": "FBS conference",
            "properties": {
                "conference_id": "Unique conference identifier",
                "name": "Conference name",
                "abbreviation": "Short name (e.g., 'SEC')",
                "tier": "Competition tier (P5, G5, Independent)",
                "competition_adjustment": "Stats adjustment factor"
            }
        },

        "CollegeStats": {
            "description": "College player statistics for one season",
            "properties": {
                "stats_id": "Unique identifier (prospect_id + season)",
                "season": "Season year",
                "games": "Games played",

                # Passing (QB)
                "pass_attempts": "Pass attempts",
                "pass_completions": "Completions",
                "pass_yards": "Passing yards",
                "pass_tds": "Passing touchdowns",
                "interceptions": "Interceptions thrown",
                "completion_pct": "Completion percentage",
                "yards_per_attempt": "Yards per pass attempt",
                "adj_yards_per_attempt": "Adjusted YPA (AY/A)",
                "qbr": "ESPN QBR (if available)",

                # Rushing (RB/QB)
                "rush_attempts": "Rush attempts",
                "rush_yards": "Rushing yards",
                "rush_tds": "Rushing touchdowns",
                "yards_per_carry": "Yards per carry",

                # Receiving (WR/TE/RB)
                "receptions": "Receptions",
                "receiving_yards": "Receiving yards",
                "receiving_tds": "Receiving touchdowns",
                "targets": "Targets",
                "yards_per_reception": "Yards per catch",
                "catch_rate": "Catch rate (receptions/targets)",

                # Advanced metrics
                "market_share_yards": "% of team's total yards",
                "market_share_tds": "% of team's total TDs",
                "dominator_rating": "(rec_yards + rec_tds*20) / team_total",
                "yards_per_team_pass": "Efficiency in passing game",
                "target_share": "% of team targets",
                "snap_share": "% of offensive snaps (if available)",

                # Context
                "team_pass_yards": "Team total passing yards",
                "team_rush_yards": "Team total rushing yards",
                "team_total_tds": "Team total touchdowns"
            }
        },

        "CombineResult": {
            "description": "NFL Combine performance data",
            "properties": {
                "combine_id": "Unique identifier (name + year)",
                "combine_year": "Combine year",

                # Athletic testing
                "forty_yard": "40-yard dash time (seconds)",
                "ten_yard_split": "10-yard split time",
                "bench_press": "Bench press reps at 225 lbs",
                "vertical_jump": "Vertical jump (inches)",
                "broad_jump": "Broad jump (inches)",
                "three_cone": "3-cone drill time (seconds)",
                "shuttle": "20-yard shuttle time (seconds)",

                # Measurements
                "height": "Height in inches",
                "weight": "Weight in pounds",
                "hand_size": "Hand size (inches)",
                "arm_length": "Arm length (inches)",
                "wingspan": "Wingspan (inches)",

                # Calculated scores
                "speed_score": "(Weight * 200) / (40 Time ^ 4)",
                "burst_score": "Vertical + (Broad Jump / 12)",
                "agility_score": "20 - (3-Cone + Shuttle) / 2",
                "ras_score": "Relative Athletic Score (0-10)"
            }
        },

        "DevySnapshot": {
            "description": "Point-in-time KTC devy value snapshot",
            "properties": {
                "snapshot_id": "Unique identifier (prospect_id + date)",
                "date": "Snapshot date",
                "ktc_devy_value": "KeepTradeCut devy value",
                "ktc_devy_rank": "Overall devy rank",
                "position_rank": "Position rank in devy",
                "superflex_value": "Superflex format value",
                "one_qb_value": "1QB format value",
                "two_qb_value": "2QB format value"
            }
        },

        "Insight": {
            "description": "Knowledge base entry - discovered correlation or pattern",
            "properties": {
                "insight_id": "Unique identifier",
                "created_date": "When insight was discovered",
                "insight_type": "CORRELATION, PATTERN, WEIGHT_ADJUSTMENT, BUY_SIGNAL, SELL_SIGNAL",
                "description": "Human-readable description",
                "confidence": "Confidence level (0.0-1.0)",
                "supporting_data": "JSON blob with evidence/statistics",
                "position": "Position this insight applies to (or ALL)",
                "applied": "Whether insight has been applied to weights",
                "applied_date": "When insight was applied"
            }
        },

        "DraftClass": {
            "description": "NFL Draft class for a given year",
            "properties": {
                "class_id": "Unique identifier (year)",
                "year": "Draft year",
                "total_picks": "Total picks in draft",
                "fantasy_relevant_picks": "QB/RB/WR/TE picks"
            }
        }
    }

    # =========================================================================
    # RELATIONSHIP DEFINITIONS
    # =========================================================================

    RELATIONSHIPS = {
        # Prospect relationships
        "PLAYED_FOR": {
            "from": "Prospect",
            "to": "CollegeTeam",
            "properties": ["seasons", "start_year", "end_year"]
        },
        "HAS_COLLEGE_STATS": {
            "from": "Prospect",
            "to": "CollegeStats",
            "properties": []
        },
        "HAS_COMBINE": {
            "from": "Prospect",
            "to": "CombineResult",
            "properties": []
        },
        "HAS_DEVY_VALUE": {
            "from": "Prospect",
            "to": "DevySnapshot",
            "properties": []
        },
        "BECAME_NFL_PLAYER": {
            "from": "Prospect",
            "to": "Player",
            "properties": ["draft_round", "draft_pick", "draft_year", "nfl_team"]
        },

        # Player (NFL) relationships to college
        "COLLEGE_PROFILE": {
            "from": "Player",
            "to": "Prospect",
            "properties": []
        },

        # College team relationships
        "IN_CONFERENCE": {
            "from": "CollegeTeam",
            "to": "Conference",
            "properties": ["joined_year"]
        },
        "PRODUCED_PROSPECT": {
            "from": "CollegeTeam",
            "to": "Prospect",
            "properties": []
        },

        # Draft relationships
        "IN_DRAFT_CLASS": {
            "from": "Prospect",
            "to": "DraftClass",
            "properties": ["round", "pick", "nfl_team"]
        },

        # Insight relationships
        "INSIGHT_RELATES_TO": {
            "from": "Insight",
            "to": "Player",
            "properties": []
        },
        "INSIGHT_DERIVED_FROM": {
            "from": "Insight",
            "to": "CollegeStats",
            "properties": []
        },

        # Devy temporal chain
        "DEVY_NEXT": {
            "from": "DevySnapshot",
            "to": "DevySnapshot",
            "properties": ["value_change", "rank_change"]
        }
    }

    def __init__(self, uri: str = None, user: str = None, password: str = None):
        """Initialize schema manager with Neo4j connection."""
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or os.getenv("NEO4J_USER")
        self.password = password or os.getenv("NEO4J_PASSWORD")

        # Handle auth - support both authenticated and unauthenticated connections
        if self.user and self.password:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        else:
            self.driver = GraphDatabase.driver(self.uri, auth=None)

    def close(self):
        """Close the Neo4j driver."""
        self.driver.close()

    # =========================================================================
    # SCHEMA CREATION
    # =========================================================================

    def create_constraints(self) -> Dict[str, bool]:
        """Create all uniqueness constraints for college nodes."""
        results = {}

        with self.driver.session() as session:
            for name, label, prop in self.CONSTRAINTS:
                try:
                    session.run(f"""
                        CREATE CONSTRAINT {name} IF NOT EXISTS
                        FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE
                    """)
                    results[name] = True
                    logger.info(f"Created constraint: {name}")
                except Exception as e:
                    results[name] = False
                    logger.warning(f"Failed to create constraint {name}: {e}")

        return results

    def create_indexes(self) -> Dict[str, bool]:
        """Create all indexes for college nodes."""
        results = {}

        with self.driver.session() as session:
            for name, label, props in self.INDEXES:
                try:
                    prop_list = ", ".join([f"n.{p}" for p in props])
                    session.run(f"""
                        CREATE INDEX {name} IF NOT EXISTS
                        FOR (n:{label}) ON ({prop_list})
                    """)
                    results[name] = True
                    logger.info(f"Created index: {name}")
                except Exception as e:
                    results[name] = False
                    logger.warning(f"Failed to create index {name}: {e}")

        return results

    def create_schema(self) -> Dict[str, Dict]:
        """Create complete college football schema (constraints + indexes)."""
        logger.info("Creating college football schema extensions...")

        results = {
            "constraints": self.create_constraints(),
            "indexes": self.create_indexes()
        }

        # Summary
        constraints_ok = sum(results["constraints"].values())
        indexes_ok = sum(results["indexes"].values())

        logger.info(f"Schema creation complete: {constraints_ok}/{len(self.CONSTRAINTS)} constraints, "
                   f"{indexes_ok}/{len(self.INDEXES)} indexes")

        return results

    # =========================================================================
    # SCHEMA VALIDATION
    # =========================================================================

    def validate_schema(self) -> Dict[str, bool]:
        """Validate that all schema elements exist."""
        validation = {
            "constraints": {},
            "indexes": {},
            "valid": True
        }

        with self.driver.session() as session:
            # Check constraints
            result = session.run("SHOW CONSTRAINTS")
            existing_constraints = {r["name"] for r in result}

            for name, _, _ in self.CONSTRAINTS:
                exists = name in existing_constraints
                validation["constraints"][name] = exists
                if not exists:
                    validation["valid"] = False

            # Check indexes
            result = session.run("SHOW INDEXES")
            existing_indexes = {r["name"] for r in result}

            for name, _, _ in self.INDEXES:
                exists = name in existing_indexes
                validation["indexes"][name] = exists
                if not exists:
                    validation["valid"] = False

        return validation

    def get_schema_stats(self) -> Dict[str, int]:
        """Get statistics about college football data in the graph."""
        stats = {}

        queries = {
            "prospects": "MATCH (n:Prospect) RETURN count(n) as count",
            "college_teams": "MATCH (n:CollegeTeam) RETURN count(n) as count",
            "college_stats": "MATCH (n:CollegeStats) RETURN count(n) as count",
            "combine_results": "MATCH (n:CombineResult) RETURN count(n) as count",
            "devy_snapshots": "MATCH (n:DevySnapshot) RETURN count(n) as count",
            "insights": "MATCH (n:Insight) RETURN count(n) as count",
            "prospect_to_nfl_links": "MATCH (:Prospect)-[:BECAME_NFL_PLAYER]->(:Player) RETURN count(*) as count",
            "drafted_prospects": "MATCH (p:Prospect) WHERE p.is_drafted = true RETURN count(p) as count"
        }

        with self.driver.session() as session:
            for name, query in queries.items():
                try:
                    result = session.run(query)
                    stats[name] = result.single()["count"]
                except Exception as e:
                    stats[name] = -1
                    logger.warning(f"Failed to get stat {name}: {e}")

        return stats

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def drop_college_data(self, confirm: bool = False):
        """
        Drop all college football data (use with caution!).

        Args:
            confirm: Must be True to actually execute
        """
        if not confirm:
            logger.warning("drop_college_data called without confirm=True. No action taken.")
            return

        labels_to_drop = [
            "Prospect", "CollegeTeam", "Conference", "CollegeStats",
            "CombineResult", "DevySnapshot", "Insight", "DraftClass"
        ]

        with self.driver.session() as session:
            for label in labels_to_drop:
                try:
                    session.run(f"MATCH (n:{label}) DETACH DELETE n")
                    logger.info(f"Deleted all {label} nodes")
                except Exception as e:
                    logger.error(f"Failed to delete {label}: {e}")

    def get_schema_documentation(self) -> str:
        """Generate markdown documentation for the schema."""
        doc = "# College Football Schema Documentation\n\n"

        doc += "## Node Types\n\n"
        for label, schema in self.NODE_SCHEMAS.items():
            doc += f"### {label}\n"
            doc += f"{schema['description']}\n\n"
            doc += "| Property | Description |\n"
            doc += "|----------|-------------|\n"
            for prop, desc in schema['properties'].items():
                doc += f"| `{prop}` | {desc} |\n"
            doc += "\n"

        doc += "## Relationships\n\n"
        doc += "| Relationship | From | To | Properties |\n"
        doc += "|--------------|------|----|-----------|\n"
        for rel_name, rel_def in self.RELATIONSHIPS.items():
            props = ", ".join(rel_def['properties']) or "none"
            doc += f"| `{rel_name}` | {rel_def['from']} | {rel_def['to']} | {props} |\n"

        return doc


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    manager = CollegeSchemaManager()

    print("\n=== Creating College Football Schema ===")
    results = manager.create_schema()

    print("\n=== Schema Validation ===")
    validation = manager.validate_schema()
    print(f"Schema valid: {validation['valid']}")

    print("\n=== Schema Statistics ===")
    stats = manager.get_schema_stats()
    for name, count in stats.items():
        print(f"  {name}: {count}")

    manager.close()
