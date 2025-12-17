"""
Knowledge Base System for Dynasty Insights
==========================================
Stores, discovers, and retrieves analytical insights for Thoth.

Types of Insights:
- Statistical correlations (e.g., "Dominator rating >30% correlates with NFL success")
- Market patterns (e.g., "WRs typically see value spike after 100-yard games")
- Player archetypes (e.g., "Elite 40-time + high target share = breakout profile")
- Historical trends (e.g., "RB values drop 15% after age 27")

Insights are stored in Neo4j for graph-based querying and retrieval.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import hashlib

from neo4j import GraphDatabase
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class InsightEngine:
    """
    Discover, store, and retrieve dynasty fantasy insights.

    Insights are stored as Neo4j nodes with:
    - Type (correlation, pattern, archetype, trend)
    - Confidence score (0-100)
    - Evidence (data supporting the insight)
    - Tags for retrieval
    - Creation/validation dates
    """

    INSIGHT_TYPES = [
        "correlation",  # Statistical relationship
        "pattern",      # Repeating market behavior
        "archetype",    # Player profile pattern
        "trend",        # Time-based movement
        "prediction",   # Forward-looking insight
        "comparison",   # Cross-player analysis
        "rule"          # Derived trading rule
    ]

    def __init__(self, driver):
        """
        Initialize insight engine.

        Args:
            driver: Neo4j driver instance
        """
        self.driver = driver
        self._ensure_constraints()

    def _ensure_constraints(self):
        """Ensure Neo4j constraints exist."""
        with self.driver.session() as session:
            session.run("""
                CREATE CONSTRAINT insight_id_unique IF NOT EXISTS
                FOR (i:Insight) REQUIRE i.insight_id IS UNIQUE
            """)

    # =========================================================================
    # INSIGHT STORAGE
    # =========================================================================

    def store_insight(
        self,
        insight_type: str,
        title: str,
        description: str,
        confidence: float,
        evidence: Dict = None,
        tags: List[str] = None,
        related_players: List[str] = None,
        related_prospects: List[str] = None
    ) -> str:
        """
        Store a new insight in the knowledge base.

        Args:
            insight_type: Type of insight (correlation, pattern, etc.)
            title: Short title for the insight
            description: Detailed description
            confidence: Confidence score (0-100)
            evidence: Supporting data/statistics
            tags: Searchable tags
            related_players: NFL player names this applies to
            related_prospects: College prospect names this applies to

        Returns:
            Insight ID
        """
        if insight_type not in self.INSIGHT_TYPES:
            raise ValueError(f"Invalid insight type. Use one of: {self.INSIGHT_TYPES}")

        # Generate unique ID
        insight_id = self._generate_insight_id(title, insight_type)

        with self.driver.session() as session:
            # Create insight node
            session.run("""
                MERGE (i:Insight {insight_id: $insight_id})
                SET i.type = $type,
                    i.title = $title,
                    i.description = $description,
                    i.confidence = $confidence,
                    i.evidence = $evidence,
                    i.tags = $tags,
                    i.created_at = datetime(),
                    i.validated_at = datetime(),
                    i.validation_count = 1,
                    i.is_active = true
            """, {
                'insight_id': insight_id,
                'type': insight_type,
                'title': title,
                'description': description,
                'confidence': confidence,
                'evidence': json.dumps(evidence) if evidence else None,
                'tags': tags or []
            })

            # Link to related players
            if related_players:
                for player_name in related_players:
                    session.run("""
                        MATCH (i:Insight {insight_id: $insight_id})
                        MATCH (p:Player)
                        WHERE toLower(p.name) CONTAINS toLower($player_name)
                        MERGE (i)-[:APPLIES_TO]->(p)
                    """, {'insight_id': insight_id, 'player_name': player_name})

            # Link to related prospects
            if related_prospects:
                for prospect_name in related_prospects:
                    session.run("""
                        MATCH (i:Insight {insight_id: $insight_id})
                        MATCH (p:Prospect)
                        WHERE toLower(p.name) CONTAINS toLower($prospect_name)
                        MERGE (i)-[:APPLIES_TO]->(p)
                    """, {'insight_id': insight_id, 'prospect_name': prospect_name})

        logger.info(f"Stored insight: {title} [{insight_type}] (confidence: {confidence})")
        return insight_id

    def validate_insight(self, insight_id: str, new_confidence: float = None):
        """
        Validate an existing insight (increases validation count).

        Args:
            insight_id: ID of insight to validate
            new_confidence: Optional updated confidence score
        """
        with self.driver.session() as session:
            update_clause = "i.validation_count = i.validation_count + 1"
            if new_confidence is not None:
                update_clause += f", i.confidence = {new_confidence}"

            session.run(f"""
                MATCH (i:Insight {{insight_id: $insight_id}})
                SET {update_clause}, i.validated_at = datetime()
            """, {'insight_id': insight_id})

    def invalidate_insight(self, insight_id: str, reason: str = None):
        """
        Mark an insight as invalid/outdated.

        Args:
            insight_id: ID of insight to invalidate
            reason: Reason for invalidation
        """
        with self.driver.session() as session:
            session.run("""
                MATCH (i:Insight {insight_id: $insight_id})
                SET i.is_active = false,
                    i.invalidated_at = datetime(),
                    i.invalidation_reason = $reason
            """, {'insight_id': insight_id, 'reason': reason})

    # =========================================================================
    # INSIGHT RETRIEVAL
    # =========================================================================

    def get_insights(
        self,
        insight_type: str = None,
        tags: List[str] = None,
        min_confidence: float = 50,
        player_name: str = None,
        prospect_name: str = None,
        limit: int = 20
    ) -> List[Dict]:
        """
        Retrieve insights from the knowledge base.

        Args:
            insight_type: Filter by type
            tags: Filter by tags (any match)
            min_confidence: Minimum confidence threshold
            player_name: Get insights for a specific player
            prospect_name: Get insights for a specific prospect
            limit: Maximum results

        Returns:
            List of insight dictionaries
        """
        conditions = ["i.is_active = true", f"i.confidence >= {min_confidence}"]
        params = {}

        if insight_type:
            conditions.append("i.type = $type")
            params['type'] = insight_type

        if tags:
            conditions.append("any(tag IN $tags WHERE tag IN i.tags)")
            params['tags'] = tags

        where_clause = " AND ".join(conditions)

        # Base query
        if player_name:
            query = f"""
                MATCH (p:Player)<-[:APPLIES_TO]-(i:Insight)
                WHERE toLower(p.name) CONTAINS toLower($player_name)
                  AND {where_clause}
                RETURN i.insight_id as id, i.type as type, i.title as title,
                       i.description as description, i.confidence as confidence,
                       i.evidence as evidence, i.tags as tags,
                       i.validation_count as validations
                ORDER BY i.confidence DESC, i.validation_count DESC
                LIMIT {limit}
            """
            params['player_name'] = player_name
        elif prospect_name:
            query = f"""
                MATCH (p:Prospect)<-[:APPLIES_TO]-(i:Insight)
                WHERE toLower(p.name) CONTAINS toLower($prospect_name)
                  AND {where_clause}
                RETURN i.insight_id as id, i.type as type, i.title as title,
                       i.description as description, i.confidence as confidence,
                       i.evidence as evidence, i.tags as tags,
                       i.validation_count as validations
                ORDER BY i.confidence DESC, i.validation_count DESC
                LIMIT {limit}
            """
            params['prospect_name'] = prospect_name
        else:
            query = f"""
                MATCH (i:Insight)
                WHERE {where_clause}
                RETURN i.insight_id as id, i.type as type, i.title as title,
                       i.description as description, i.confidence as confidence,
                       i.evidence as evidence, i.tags as tags,
                       i.validation_count as validations
                ORDER BY i.confidence DESC, i.validation_count DESC
                LIMIT {limit}
            """

        with self.driver.session() as session:
            result = session.run(query, params)
            insights = []
            for record in result:
                insight = dict(record)
                if insight.get('evidence'):
                    try:
                        insight['evidence'] = json.loads(insight['evidence'])
                    except json.JSONDecodeError:
                        pass
                insights.append(insight)

            return insights

    def get_relevant_insights(self, context: str, limit: int = 5) -> List[Dict]:
        """
        Get insights relevant to a given context/query.

        Uses keyword matching against titles, descriptions, and tags.

        Args:
            context: Query or context string
            limit: Maximum results

        Returns:
            List of relevant insights
        """
        # Extract keywords
        keywords = self._extract_keywords(context)

        if not keywords:
            return []

        # Build OR conditions for keyword matching
        keyword_conditions = []
        for kw in keywords:
            keyword_conditions.append(
                f"(toLower(i.title) CONTAINS '{kw.lower()}' OR "
                f"toLower(i.description) CONTAINS '{kw.lower()}' OR "
                f"any(tag IN i.tags WHERE toLower(tag) CONTAINS '{kw.lower()}'))"
            )

        where_clause = " OR ".join(keyword_conditions)

        query = f"""
            MATCH (i:Insight)
            WHERE i.is_active = true
              AND ({where_clause})
            RETURN i.insight_id as id, i.type as type, i.title as title,
                   i.description as description, i.confidence as confidence,
                   i.tags as tags
            ORDER BY i.confidence DESC
            LIMIT {limit}
        """

        with self.driver.session() as session:
            result = session.run(query)
            return [dict(r) for r in result]

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract relevant keywords from text."""
        # Position terms
        positions = ['QB', 'RB', 'WR', 'TE', 'quarterback', 'running back', 'receiver', 'tight end']

        # Value terms
        value_terms = ['buy', 'sell', 'hold', 'undervalued', 'overvalued', 'value', 'price']

        # Analytics terms
        analytics = ['dominator', 'breakout', 'speed', 'athletic', 'snap', 'target', 'production']

        # Age/profile terms
        profile_terms = ['young', 'old', 'rebuild', 'contend', 'prospect', 'rookie', 'veteran']

        all_keywords = positions + value_terms + analytics + profile_terms

        # Find matches
        text_lower = text.lower()
        found = [kw for kw in all_keywords if kw.lower() in text_lower]

        # Also extract potential player names (2+ words starting with capital)
        import re
        potential_names = re.findall(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+', text)
        found.extend(potential_names)

        return list(set(found))

    # =========================================================================
    # INSIGHT DISCOVERY
    # =========================================================================

    def discover_correlations(self) -> List[Dict]:
        """
        Automatically discover correlations in the data.

        Returns:
            List of discovered correlation insights
        """
        discovered = []

        with self.driver.session() as session:
            # Discover WR dominator -> KTC correlation
            result = session.run("""
                MATCH (p:Prospect)-[:BECAME_NFL_PLAYER]->(pl:Player)
                WHERE p.peak_dominator_rating IS NOT NULL
                  AND pl.ktc_value IS NOT NULL
                RETURN avg(CASE WHEN p.peak_dominator_rating > 30 THEN pl.ktc_value ELSE null END) as high_dom_avg,
                       avg(CASE WHEN p.peak_dominator_rating <= 30 THEN pl.ktc_value ELSE null END) as low_dom_avg,
                       count(CASE WHEN p.peak_dominator_rating > 30 THEN 1 END) as high_dom_count,
                       count(CASE WHEN p.peak_dominator_rating <= 30 THEN 1 END) as low_dom_count
            """)

            record = result.single()
            if record and record['high_dom_avg'] and record['low_dom_avg']:
                diff_pct = ((record['high_dom_avg'] - record['low_dom_avg']) / record['low_dom_avg']) * 100
                if diff_pct > 20:
                    discovered.append({
                        'type': 'correlation',
                        'title': 'High Dominator Rating Correlates with NFL Value',
                        'description': f"Prospects with >30% dominator rating average {diff_pct:.1f}% higher NFL KTC values",
                        'confidence': min(90, 50 + record['high_dom_count']),
                        'evidence': {
                            'high_dom_avg_ktc': record['high_dom_avg'],
                            'low_dom_avg_ktc': record['low_dom_avg'],
                            'sample_size': record['high_dom_count'] + record['low_dom_count']
                        },
                        'tags': ['dominator', 'WR', 'correlation', 'value']
                    })

            # Discover breakout age correlation
            result = session.run("""
                MATCH (p:Prospect)-[:BECAME_NFL_PLAYER]->(pl:Player)
                WHERE p.breakout_age IS NOT NULL
                  AND pl.ktc_value IS NOT NULL
                RETURN avg(CASE WHEN p.breakout_age < 20 THEN pl.ktc_value ELSE null END) as early_avg,
                       avg(CASE WHEN p.breakout_age >= 20 THEN pl.ktc_value ELSE null END) as late_avg,
                       count(CASE WHEN p.breakout_age < 20 THEN 1 END) as early_count
            """)

            record = result.single()
            if record and record['early_avg'] and record['late_avg']:
                diff_pct = ((record['early_avg'] - record['late_avg']) / record['late_avg']) * 100
                if diff_pct > 15:
                    discovered.append({
                        'type': 'correlation',
                        'title': 'Early Breakout Age Premium',
                        'description': f"Prospects breaking out before age 20 average {diff_pct:.1f}% higher NFL values",
                        'confidence': min(85, 50 + record['early_count']),
                        'evidence': {
                            'early_breakout_avg': record['early_avg'],
                            'late_breakout_avg': record['late_avg'],
                            'early_sample': record['early_count']
                        },
                        'tags': ['breakout', 'age', 'correlation', 'value']
                    })

            # Discover recruiting star correlation
            result = session.run("""
                MATCH (p:Prospect)-[:BECAME_NFL_PLAYER]->(pl:Player)
                WHERE p.stars IS NOT NULL
                  AND pl.ktc_value IS NOT NULL
                RETURN p.stars as stars,
                       avg(pl.ktc_value) as avg_ktc,
                       count(*) as count
                ORDER BY p.stars
            """)

            star_data = {r['stars']: {'avg': r['avg_ktc'], 'count': r['count']} for r in result}
            if 5 in star_data and 3 in star_data:
                five_star = star_data[5]['avg']
                three_star = star_data[3]['avg']
                diff_pct = ((five_star - three_star) / three_star) * 100

                discovered.append({
                    'type': 'correlation',
                    'title': 'Recruiting Star Rating Value Impact',
                    'description': f"5-star recruits average {diff_pct:.1f}% higher NFL KTC value than 3-stars",
                    'confidence': 80,
                    'evidence': star_data,
                    'tags': ['recruiting', 'stars', 'correlation', 'draft']
                })

        return discovered

    def run_discovery_cycle(self) -> int:
        """
        Run a full insight discovery cycle and store new insights.

        Returns:
            Number of new insights stored
        """
        discovered = self.discover_correlations()
        stored_count = 0

        for insight in discovered:
            try:
                self.store_insight(
                    insight_type=insight['type'],
                    title=insight['title'],
                    description=insight['description'],
                    confidence=insight['confidence'],
                    evidence=insight.get('evidence'),
                    tags=insight.get('tags', [])
                )
                stored_count += 1
            except Exception as e:
                logger.warning(f"Failed to store insight '{insight['title']}': {e}")

        logger.info(f"Discovery cycle complete: {stored_count} insights stored")
        return stored_count

    # =========================================================================
    # UTILITIES
    # =========================================================================

    def _generate_insight_id(self, title: str, insight_type: str) -> str:
        """Generate unique insight ID."""
        combined = f"{title.lower()}_{insight_type}"
        return hashlib.md5(combined.encode()).hexdigest()[:16]

    def get_insight_stats(self) -> Dict:
        """Get statistics about stored insights."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (i:Insight)
                RETURN i.type as type,
                       count(*) as total,
                       sum(CASE WHEN i.is_active THEN 1 ELSE 0 END) as active,
                       avg(i.confidence) as avg_confidence
                ORDER BY total DESC
            """)

            return {
                'by_type': [dict(r) for r in result],
                'total': session.run("MATCH (i:Insight) RETURN count(i) as count").single()['count']
            }


# =============================================================================
# PREBUILT INSIGHTS
# =============================================================================

CORE_DYNASTY_INSIGHTS = [
    {
        'type': 'rule',
        'title': 'Contract Guaranteed Money is #1 Predictor',
        'description': 'NFL guaranteed money has 100% feature importance in value prediction. Teams vote with dollars.',
        'confidence': 95,
        'tags': ['contract', 'value', 'model', 'fundamental']
    },
    {
        'type': 'rule',
        'title': 'RB Age Cliff at 28',
        'description': 'Running back values decline sharply after age 28. Sell window is 26-27 for peak return.',
        'confidence': 90,
        'tags': ['RB', 'age', 'sell', 'fundamental']
    },
    {
        'type': 'rule',
        'title': 'Target Share > Raw Targets',
        'description': 'Target share percentage is more predictive than raw target counts for WR value.',
        'confidence': 85,
        'tags': ['WR', 'targets', 'efficiency', 'fundamental']
    },
    {
        'type': 'archetype',
        'title': 'Elite WR Prospect Profile',
        'description': 'Dominator >30% + breakout age <20 + 4-5 star recruit = elite NFL projection',
        'confidence': 85,
        'tags': ['WR', 'prospect', 'profile', 'dominator', 'breakout']
    },
    {
        'type': 'archetype',
        'title': 'Athletic Freak RB Profile',
        'description': 'Speed score >105 + 4.45 forty or better + rising snap share = breakout candidate',
        'confidence': 80,
        'tags': ['RB', 'athletic', 'profile', 'speed', 'breakout']
    },
    {
        'type': 'pattern',
        'title': 'Snap Trend Precedes Value',
        'description': 'Rising snap share often precedes KTC value increases by 2-4 weeks',
        'confidence': 75,
        'tags': ['snaps', 'value', 'timing', 'trend']
    },
    {
        'type': 'pattern',
        'title': 'Post-Injury Value Dip',
        'description': 'Players coming off major injury often see 20-30% value dip, creating buy windows',
        'confidence': 70,
        'tags': ['injury', 'buy', 'value', 'pattern']
    },
    {
        'type': 'trend',
        'title': 'Year 2 QB Premium',
        'description': 'QBs typically see peak value in year 2-3 as potential is realized but age is still young',
        'confidence': 75,
        'tags': ['QB', 'age', 'value', 'trend']
    }
]


def seed_core_insights(driver):
    """Seed the knowledge base with core dynasty insights."""
    engine = InsightEngine(driver)

    for insight in CORE_DYNASTY_INSIGHTS:
        try:
            engine.store_insight(
                insight_type=insight['type'],
                title=insight['title'],
                description=insight['description'],
                confidence=insight['confidence'],
                tags=insight.get('tags', [])
            )
        except Exception as e:
            logger.warning(f"Failed to seed insight '{insight['title']}': {e}")

    logger.info(f"Seeded {len(CORE_DYNASTY_INSIGHTS)} core insights")


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        auth=None
    )

    engine = InsightEngine(driver)

    print("\n=== Insight Engine Demo ===\n")

    # Seed core insights
    print("Seeding core insights...")
    seed_core_insights(driver)

    # Run discovery
    print("\nRunning discovery cycle...")
    discovered = engine.run_discovery_cycle()
    print(f"Discovered {discovered} new insights")

    # Get stats
    print("\nInsight Statistics:")
    stats = engine.get_insight_stats()
    print(f"Total insights: {stats['total']}")
    for type_stat in stats['by_type']:
        print(f"  {type_stat['type']}: {type_stat['total']} (avg conf: {type_stat['avg_confidence']:.1f})")

    # Get relevant insights for a query
    print("\nRelevant insights for 'young WR with high dominator':")
    relevant = engine.get_relevant_insights("young WR with high dominator", limit=3)
    for insight in relevant:
        print(f"  - [{insight['type']}] {insight['title']} (conf: {insight['confidence']})")

    driver.close()
