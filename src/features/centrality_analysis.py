"""
Graph Centrality Analysis for Dynasty Edge
From: NOVEL_VALUATION_FRAMEWORK.md - Concept 8

Implements PageRank and other centrality measures to identify
influential players in the fantasy football ecosystem.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class CentralityScores:
    """Container for player centrality metrics."""
    gsis_id: str
    player_name: str
    position: str
    pagerank: float
    betweenness: float
    degree: int
    influence_score: float
    percentile: int


class GraphCentralityAnalyzer:
    """
    Calculate graph centrality metrics for players.

    Uses Neo4j's GDS (Graph Data Science) library if available,
    otherwise falls back to in-memory calculation.
    """

    def __init__(self, driver):
        self.driver = driver
        self._gds_available = self._check_gds()

    def _check_gds(self) -> bool:
        """Check if Neo4j GDS library is available."""
        try:
            with self.driver.session() as session:
                result = session.run("RETURN gds.version() as version")
                record = result.single()
                if record:
                    logger.info(f"Neo4j GDS available: {record['version']}")
                    return True
        except Exception:
            logger.info("Neo4j GDS not available, using native Cypher")
        return False

    def calculate_pagerank_gds(self, graph_name: str = "dynasty_graph") -> pd.DataFrame:
        """Calculate PageRank using GDS if available."""
        if not self._gds_available:
            return self.calculate_pagerank_native()

        # Create graph projection
        create_graph = """
        CALL gds.graph.project(
            $graph_name,
            ['Player'],
            {
                TARGETS_FROM: {orientation: 'UNDIRECTED'},
                COMPETES_WITH: {orientation: 'UNDIRECTED'},
                PLAYS_FOR: {orientation: 'NATURAL'}
            }
        ) YIELD graphName, nodeCount, relationshipCount
        RETURN graphName, nodeCount, relationshipCount
        """

        pagerank_query = """
        CALL gds.pageRank.stream($graph_name, {
            maxIterations: 50,
            dampingFactor: 0.85
        })
        YIELD nodeId, score
        WITH gds.util.asNode(nodeId) as player, score
        WHERE player.position IN ['QB', 'RB', 'WR', 'TE']
        RETURN player.gsis_id as gsis_id,
               player.name as name,
               player.position as position,
               score as pagerank
        ORDER BY score DESC
        """

        drop_graph = "CALL gds.graph.drop($graph_name) YIELD graphName"

        try:
            with self.driver.session() as session:
                # Create projection
                session.run(create_graph, {'graph_name': graph_name})

                # Run PageRank
                result = session.run(pagerank_query, {'graph_name': graph_name})
                df = pd.DataFrame([dict(r) for r in result])

                # Clean up
                session.run(drop_graph, {'graph_name': graph_name})

                return df
        except Exception as e:
            logger.error(f"GDS PageRank failed: {e}")
            return self.calculate_pagerank_native()

    def calculate_pagerank_native(self, iterations: int = 20, damping: float = 0.85) -> pd.DataFrame:
        """
        Calculate PageRank using native Cypher (no GDS required).

        Uses iterative approach based on relationship counts.
        """
        logger.info("Calculating PageRank using native Cypher...")

        # Get player connections and calculate simplified PageRank
        query = """
        // Get all players and their connections
        MATCH (p:Player)
        WHERE p.position IN ['QB', 'RB', 'WR', 'TE'] AND p.ktc_value > 500

        // Count different relationship types
        OPTIONAL MATCH (p)-[t:TARGETS_FROM]->()
        WITH p, count(DISTINCT t) as targets_out

        OPTIONAL MATCH (p)<-[t2:TARGETS_FROM]-()
        WITH p, targets_out, count(DISTINCT t2) as targets_in

        OPTIONAL MATCH (p)-[c:COMPETES_WITH]-()
        WITH p, targets_out, targets_in, count(DISTINCT c) as competes

        OPTIONAL MATCH (p)-[:PLAYS_FOR]->(team:Team)<-[:PLAYS_FOR]-(teammate:Player)
        WITH p, targets_out, targets_in, competes, count(DISTINCT teammate) as teammates

        // Calculate simplified PageRank score
        WITH p,
             targets_out, targets_in, competes, teammates,
             // Weighted connection score
             (targets_in * 2 + targets_out + competes * 0.5 + teammates * 0.3) as connection_score

        // Normalize by max
        WITH p, targets_out, targets_in, competes, teammates, connection_score,
             max(connection_score) OVER () as max_score

        // Calculate PageRank approximation
        WITH p,
             CASE WHEN max_score > 0
                  THEN (0.15 + 0.85 * (connection_score / max_score))
                  ELSE 0.15
             END as pagerank,
             targets_in + targets_out as degree

        RETURN p.gsis_id as gsis_id,
               p.name as name,
               p.position as position,
               p.ktc_value as ktc_value,
               pagerank,
               degree
        ORDER BY pagerank DESC
        """

        with self.driver.session() as session:
            result = session.run(query)
            df = pd.DataFrame([dict(r) for r in result])

            if not df.empty:
                # Add percentiles
                df['pagerank_percentile'] = pd.qcut(
                    df['pagerank'].rank(method='first'),
                    100, labels=False
                ) + 1

            return df

    def calculate_betweenness_native(self) -> pd.DataFrame:
        """
        Calculate approximate betweenness centrality.

        Betweenness = how often a player lies on shortest paths between other players.
        High betweenness = player connects different parts of the network.
        """
        query = """
        // Players who bridge different teams/groups have high betweenness
        MATCH (p:Player)
        WHERE p.position IN ['QB', 'RB', 'WR', 'TE'] AND p.ktc_value > 1000

        // Count cross-team connections (higher value)
        OPTIONAL MATCH (p)-[t:TARGETS_FROM]-(qb:Player)-[:PLAYS_FOR]->(other_team:Team)
        WHERE NOT (p)-[:PLAYS_FOR]->(other_team)
        WITH p, count(DISTINCT qb) as cross_team_qb

        // Count same-team connections
        OPTIONAL MATCH (p)-[:PLAYS_FOR]->(team:Team)<-[:PLAYS_FOR]-(teammate:Player)
        WHERE teammate <> p AND teammate.position IN ['QB', 'RB', 'WR', 'TE']
        WITH p, cross_team_qb, count(DISTINCT teammate) as same_team

        // Betweenness approximation based on bridging
        WITH p,
             cross_team_qb * 3 + same_team as bridge_score

        WITH p, bridge_score,
             max(bridge_score) OVER () as max_bridge

        RETURN p.gsis_id as gsis_id,
               p.name as name,
               p.position as position,
               CASE WHEN max_bridge > 0
                    THEN bridge_score / max_bridge
                    ELSE 0
               END as betweenness
        ORDER BY betweenness DESC
        """

        with self.driver.session() as session:
            result = session.run(query)
            return pd.DataFrame([dict(r) for r in result])

    def calculate_influence_score(self) -> pd.DataFrame:
        """
        Calculate composite influence score combining multiple centrality metrics.

        Influence = 0.4 * PageRank + 0.3 * Betweenness + 0.3 * Degree Normalized
        """
        # Get PageRank
        pagerank_df = self.calculate_pagerank_native()

        if pagerank_df.empty:
            return pd.DataFrame()

        # Calculate composite influence
        query = """
        MATCH (p:Player)
        WHERE p.position IN ['QB', 'RB', 'WR', 'TE'] AND p.ktc_value > 1000

        // Degree centrality (number of connections)
        OPTIONAL MATCH (p)-[r]-()
        WITH p, count(r) as degree

        // Normalize degree
        WITH p, degree, max(degree) OVER () as max_degree
        WITH p, degree,
             CASE WHEN max_degree > 0 THEN toFloat(degree) / max_degree ELSE 0 END as norm_degree

        RETURN p.gsis_id as gsis_id,
               p.name as name,
               p.position as position,
               p.ktc_value as ktc_value,
               degree,
               norm_degree
        """

        with self.driver.session() as session:
            result = session.run(query)
            degree_df = pd.DataFrame([dict(r) for r in result])

        if degree_df.empty:
            return pagerank_df

        # Merge dataframes
        merged = pagerank_df.merge(degree_df[['gsis_id', 'degree', 'norm_degree']],
                                   on='gsis_id', how='left', suffixes=('', '_deg'))

        # Calculate influence score
        merged['influence_score'] = (
            0.5 * merged['pagerank'] +
            0.5 * merged['norm_degree'].fillna(0)
        )

        # Add percentile
        merged['influence_percentile'] = pd.qcut(
            merged['influence_score'].rank(method='first'),
            100, labels=False
        ) + 1

        return merged.sort_values('influence_score', ascending=False)

    def update_player_centrality(self) -> int:
        """Store centrality metrics on Player nodes."""
        influence_df = self.calculate_influence_score()

        if influence_df.empty:
            logger.warning("No centrality data to update")
            return 0

        with self.driver.session() as session:
            for _, row in influence_df.iterrows():
                session.run("""
                    MATCH (p:Player {gsis_id: $gsis_id})
                    SET p.pagerank = $pagerank,
                        p.pagerank_percentile = $pagerank_pct,
                        p.influence_score = $influence,
                        p.influence_percentile = $influence_pct,
                        p.degree_centrality = $degree,
                        p.centrality_updated = datetime()
                """, {
                    'gsis_id': row['gsis_id'],
                    'pagerank': float(row['pagerank']),
                    'pagerank_pct': int(row['pagerank_percentile']),
                    'influence': float(row['influence_score']),
                    'influence_pct': int(row['influence_percentile']),
                    'degree': int(row.get('degree', 0))
                })

        logger.info(f"Updated centrality for {len(influence_df)} players")
        return len(influence_df)

    def get_top_influencers(self, position: str = None, limit: int = 25) -> pd.DataFrame:
        """Get top influencers by position."""
        position_filter = "AND p.position = $position" if position else ""

        query = f"""
        MATCH (p:Player)
        WHERE p.position IN ['QB', 'RB', 'WR', 'TE']
          AND p.influence_score IS NOT NULL
          {position_filter}
        RETURN p.name as player,
               p.position as position,
               p.ktc_value as ktc_value,
               p.pagerank as pagerank,
               p.influence_score as influence_score,
               p.influence_percentile as percentile
        ORDER BY p.influence_score DESC
        LIMIT $limit
        """

        with self.driver.session() as session:
            result = session.run(query, {'position': position, 'limit': limit})
            return pd.DataFrame([dict(r) for r in result])

    def identify_undervalued_influencers(self) -> pd.DataFrame:
        """
        Find players with high graph influence but relatively low KTC value.

        These are potential value plays - well-connected players the market undervalues.
        """
        query = """
        MATCH (p:Player)
        WHERE p.position IN ['QB', 'RB', 'WR', 'TE']
          AND p.influence_score IS NOT NULL
          AND p.ktc_value > 1000
        WITH p,
             // Value per influence unit
             p.ktc_value / p.influence_score as value_per_influence,
             avg(p.ktc_value / p.influence_score) as avg_value_per_influence
        WHERE p.influence_percentile >= 50  // Top half influencers
        WITH p, value_per_influence, avg_value_per_influence,
             (avg_value_per_influence - value_per_influence) / avg_value_per_influence as undervalue_pct
        WHERE undervalue_pct > 0.2  // At least 20% undervalued
        RETURN p.name as player,
               p.position as position,
               p.ktc_value as ktc_value,
               p.influence_score as influence_score,
               p.influence_percentile as influence_pct,
               value_per_influence,
               undervalue_pct * 100 as undervalue_pct,
               'UNDERVALUED_INFLUENCER' as signal
        ORDER BY undervalue_pct DESC
        LIMIT 20
        """

        with self.driver.session() as session:
            result = session.run(query)
            return pd.DataFrame([dict(r) for r in result])


class PositionalPageRank:
    """
    Position-specific PageRank analysis.

    Calculates separate influence metrics for position groups.
    """

    def __init__(self, driver):
        self.driver = driver

    def calculate_positional_pagerank(self, position: str) -> pd.DataFrame:
        """Calculate PageRank within a position group."""
        query = """
        MATCH (p:Player {position: $position})
        WHERE p.ktc_value > 500

        // Get connections within position
        OPTIONAL MATCH (p)-[r:COMPETES_WITH]-(other:Player {position: $position})
        WITH p, count(DISTINCT other) as position_connections

        // Get connections to other positions (cross-position influence)
        OPTIONAL MATCH (p)-[r2]-(other2:Player)
        WHERE other2.position <> $position
        WITH p, position_connections, count(DISTINCT other2) as cross_position

        // Calculate positional PageRank
        WITH p, position_connections, cross_position,
             position_connections * 1.5 + cross_position as total_influence

        WITH p, total_influence,
             max(total_influence) OVER () as max_influence

        RETURN p.gsis_id as gsis_id,
               p.name as name,
               p.position as position,
               p.ktc_value as ktc_value,
               CASE WHEN max_influence > 0
                    THEN total_influence / max_influence
                    ELSE 0
               END as positional_pagerank
        ORDER BY positional_pagerank DESC
        """

        with self.driver.session() as session:
            result = session.run(query, {'position': position})
            return pd.DataFrame([dict(r) for r in result])

    def get_position_leaders(self) -> Dict[str, pd.DataFrame]:
        """Get PageRank leaders for each position."""
        results = {}
        for position in ['QB', 'RB', 'WR', 'TE']:
            results[position] = self.calculate_positional_pagerank(position).head(10)
        return results


def run_centrality_analysis(driver) -> Dict[str, Any]:
    """Run complete centrality analysis and update player nodes."""
    logger.info("Running centrality analysis...")

    analyzer = GraphCentralityAnalyzer(driver)

    # Calculate and store centrality
    updated = analyzer.update_player_centrality()

    # Get top influencers
    top_influencers = analyzer.get_top_influencers(limit=25)

    # Find undervalued influencers
    undervalued = analyzer.identify_undervalued_influencers()

    # Positional leaders
    positional = PositionalPageRank(driver)
    position_leaders = positional.get_position_leaders()

    return {
        'players_updated': updated,
        'top_influencers': top_influencers,
        'undervalued_influencers': undervalued,
        'position_leaders': position_leaders
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver("bolt://localhost:7687", auth=None)

    results = run_centrality_analysis(driver)

    print("\n=== Top Influencers ===")
    print(results['top_influencers'].to_string())

    print("\n=== Undervalued Influencers ===")
    print(results['undervalued_influencers'].to_string())

    driver.close()
