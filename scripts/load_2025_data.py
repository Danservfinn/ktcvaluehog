#!/usr/bin/env python3
"""
2025 NFL Season Data Pipeline - Load Script
============================================
Master script for loading 2025 NFL season data into Neo4j.

This script runs the complete 2025 pipeline:
1. Setup Neo4j schema for 2025 stats nodes
2. Load weekly player stats from nflverse
3. Load season aggregates
4. Load snap counts
5. Load Next Gen Stats
6. Link to existing Player nodes
7. Calculate production edge scores
8. Update Player nodes with edge metrics

Usage:
    python scripts/load_2025_data.py                    # Full load
    python scripts/load_2025_data.py --schema-only      # Only setup schema
    python scripts/load_2025_data.py --edge-only        # Only calculate edge scores
    python scripts/load_2025_data.py --verify           # Verify existing data
"""

import os
import sys
import argparse
import logging
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_driver():
    """Get Neo4j driver."""
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")

    auth = None
    if user and password:
        auth = (user, password)

    return GraphDatabase.driver(uri, auth=auth)


def setup_schema(driver):
    """Setup Neo4j schema for 2025 stats."""
    logger.info("=" * 60)
    logger.info("STEP 1: Setting up 2025 NFL Schema")
    logger.info("=" * 60)

    from src.database.nfl2025_schema import NFL2025SchemaManager

    schema_manager = NFL2025SchemaManager(driver)
    schema_manager.setup_schema()

    logger.info("Schema setup complete!")


def load_nfl_data(driver, weeks=None, include_snaps=True, include_ngs=True):
    """Load 2025 NFL data into Neo4j."""
    logger.info("=" * 60)
    logger.info("STEP 2: Loading 2025 NFL Data")
    logger.info("=" * 60)

    from src.loaders.nfl2025_to_neo4j import NFL2025ToNeo4jETL

    etl = NFL2025ToNeo4jETL(driver=driver)

    try:
        stats = etl.run_full_etl(
            weeks=weeks,
            include_snaps=include_snaps,
            include_ngs=include_ngs
        )

        logger.info(f"2025 data load complete!")
        logger.info(f"  Weekly stats: {stats['weekly_stats']:,}")
        logger.info(f"  Season stats: {stats['season_stats']:,}")
        logger.info(f"  Snap counts: {stats['snap_counts']:,}")
        logger.info(f"  NGS records: {stats['ngs_stats']:,}")
        logger.info(f"  Player links: {stats['player_links']:,}")

        return stats
    finally:
        # Don't close driver - we didn't create it
        pass


def calculate_edge_scores(driver):
    """Calculate production edge scores."""
    logger.info("=" * 60)
    logger.info("STEP 3: Calculating Production Edge Scores")
    logger.info("=" * 60)

    from src.features.production_edge import ProductionEdgeCalculator

    calc = ProductionEdgeCalculator(driver=driver)

    try:
        count = calc.update_player_edge_scores()
        logger.info(f"Updated edge scores for {count} players")
        return count
    finally:
        # Don't close - we're sharing the driver
        pass


def verify_data(driver):
    """Verify loaded 2025 data."""
    logger.info("=" * 60)
    logger.info("2025 Data Verification")
    logger.info("=" * 60)

    with driver.session() as session:
        queries = [
            ("Weekly Stats", "MATCH (ws:WeeklyStats {season: 2025}) RETURN count(ws) as count"),
            ("Season Stats", "MATCH (ss:SeasonStats {season: 2025}) RETURN count(ss) as count"),
            ("Snap Counts", "MATCH (sc:SnapCount {season: 2025}) RETURN count(sc) as count"),
            ("NGS Stats", "MATCH (ngs:NGSStats {season: 2025}) RETURN count(ngs) as count"),
            ("Players with 2025 Stats", "MATCH (p:Player)-[:HAD_SEASON]->(:SeasonStats {season: 2025}) RETURN count(DISTINCT p) as count"),
            ("Players with Edge Scores", "MATCH (p:Player) WHERE p.production_edge_score IS NOT NULL RETURN count(p) as count"),
            ("Max Week Loaded", "MATCH (ws:WeeklyStats {season: 2025}) RETURN max(ws.week) as count"),
        ]

        print("\nNode Counts:")
        print("-" * 50)
        for name, query in queries:
            result = session.run(query)
            count = result.single()['count']
            print(f"  {name:30} {count:>10,}")

        # Top performers
        print("\n\n2025 Fantasy Leaders (PPG PPR):")
        print("-" * 70)
        result = session.run("""
            MATCH (ss:SeasonStats {season: 2025})
            WHERE ss.games >= 3
            OPTIONAL MATCH (p:Player)
            WHERE toLower(p.name) = toLower(ss.player_name)
            RETURN ss.player_name as name, ss.position as pos, ss.team as team,
                   ss.games as games, round(ss.ppg_ppr, 1) as ppg,
                   p.ktc_value as ktc_value,
                   p.production_edge_score as edge_score,
                   p.production_signal as signal
            ORDER BY ss.ppg_ppr DESC
            LIMIT 15
        """)

        for record in result:
            signal = record['signal'] or 'N/A'
            edge = record['edge_score'] or 0
            ktc = record['ktc_value'] or 0
            print(f"  {record['name']:25} {record['pos']:3} {record['team']:3} "
                  f"G:{record['games']:2} PPG:{record['ppg']:5.1f} "
                  f"KTC:{ktc:>6,} Edge:{edge:+6.1f} {signal}")

        # Top buy targets
        print("\n\n2025 Buy Targets (Positive Edge Score):")
        print("-" * 70)
        result = session.run("""
            MATCH (p:Player)-[:HAD_SEASON]->(ss:SeasonStats {season: 2025})
            WHERE p.production_edge_score >= 15
            RETURN p.name as name, ss.position as pos, ss.team as team,
                   round(ss.ppg_ppr, 1) as ppg,
                   p.ktc_value as ktc_value,
                   round(p.production_edge_score, 1) as edge_score,
                   p.production_signal as signal
            ORDER BY p.production_edge_score DESC
            LIMIT 10
        """)

        for record in result:
            print(f"  {record['name']:25} {record['pos']:3} PPG:{record['ppg']:5.1f} "
                  f"KTC:{record['ktc_value']:>6,} Edge:{record['edge_score']:+6.1f} {record['signal']}")


def run_full_pipeline(driver, weeks=None):
    """Run the complete 2025 data pipeline."""
    start_time = datetime.now()

    logger.info("=" * 70)
    logger.info("2025 NFL SEASON DATA PIPELINE")
    logger.info(f"Started at: {start_time}")
    logger.info("=" * 70)

    try:
        # Step 1: Schema
        setup_schema(driver)

        # Step 2: Load Data
        load_nfl_data(driver, weeks=weeks)

        # Step 3: Edge Scores
        calculate_edge_scores(driver)

        # Verify
        verify_data(driver)

        end_time = datetime.now()
        duration = end_time - start_time

        logger.info("=" * 70)
        logger.info("PIPELINE COMPLETE!")
        logger.info(f"Duration: {duration}")
        logger.info("=" * 70)

    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        raise


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='2025 NFL Season Data Pipeline')
    parser.add_argument('--schema-only', action='store_true', help='Only setup schema')
    parser.add_argument('--data-only', action='store_true', help='Only load data (skip edge calc)')
    parser.add_argument('--edge-only', action='store_true', help='Only calculate edge scores')
    parser.add_argument('--verify', action='store_true', help='Only verify data')
    parser.add_argument('--weeks', type=int, nargs='+', help='Specific weeks to load')
    parser.add_argument('--no-snaps', action='store_true', help='Skip snap count loading')
    parser.add_argument('--no-ngs', action='store_true', help='Skip Next Gen Stats')

    args = parser.parse_args()

    driver = get_driver()

    try:
        if args.schema_only:
            setup_schema(driver)
        elif args.data_only:
            setup_schema(driver)
            load_nfl_data(
                driver,
                weeks=args.weeks,
                include_snaps=not args.no_snaps,
                include_ngs=not args.no_ngs
            )
        elif args.edge_only:
            calculate_edge_scores(driver)
        elif args.verify:
            verify_data(driver)
        else:
            run_full_pipeline(driver, weeks=args.weeks)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
