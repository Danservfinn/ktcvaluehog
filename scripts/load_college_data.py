#!/usr/bin/env python3
"""
College Football Data Pipeline - Initial Load Script
=====================================================
Master script for loading all college football data into Neo4j.

This script runs the complete pipeline:
1. Setup Neo4j schema for college nodes
2. Load CFBD data (recruiting, stats, teams, draft)
3. Load KTC devy values
4. Calculate prospect features
5. Seed knowledge base with core insights
6. Run insight discovery

Usage:
    python scripts/load_college_data.py                    # Full load
    python scripts/load_college_data.py --schema-only      # Only setup schema
    python scripts/load_college_data.py --devy-only        # Only load devy values
    python scripts/load_college_data.py --verify           # Verify existing data
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
    """Setup Neo4j schema for college nodes."""
    logger.info("="*60)
    logger.info("STEP 1: Setting up Neo4j Schema")
    logger.info("="*60)

    from src.database.college_schema import CollegeSchemaManager

    schema_manager = CollegeSchemaManager(driver)
    schema_manager.setup_schema()

    logger.info("Schema setup complete!")


def load_cfbd_data(driver, years: list = None):
    """Load CFBD data into Neo4j."""
    logger.info("="*60)
    logger.info("STEP 2: Loading CFBD Data")
    logger.info("="*60)

    from src.loaders.college_to_neo4j import CollegeToNeo4jETL

    if years is None:
        years = list(range(2018, 2026))

    etl = CollegeToNeo4jETL()

    try:
        stats = etl.run_full_etl(
            recruiting_years=years,
            stats_years=years[:-1],  # Stats lag by 1 year
            draft_years=years,
            include_devy=False,  # Loaded separately
            include_combine=True
        )

        logger.info(f"CFBD load complete!")
        logger.info(f"  Prospects: {stats['prospects_created']}")
        logger.info(f"  Teams: {stats['teams_created']}")
        logger.info(f"  Stats records: {stats['stats_created']}")
        logger.info(f"  Combine results: {stats['combine_created']}")
        logger.info(f"  Draft links: {stats['draft_links']}")

        return stats
    finally:
        etl.close()


def load_devy_values(driver):
    """Load KTC devy values."""
    logger.info("="*60)
    logger.info("STEP 3: Loading KTC Devy Values")
    logger.info("="*60)

    from src.loaders.ktc_devy_loader import KTCDevyLoader

    loader = KTCDevyLoader(driver=driver)

    df = loader.fetch_devy_rankings(superflex=True)

    if df is not None and not df.empty:
        count = loader.load_devy_values_to_neo4j(df, superflex=True)
        loader.link_devy_snapshots_temporal()

        logger.info(f"Loaded {count} devy values")
        return count
    else:
        logger.warning("Failed to fetch devy values")
        return 0


def calculate_features(driver):
    """Calculate prospect features."""
    logger.info("="*60)
    logger.info("STEP 4: Calculating Prospect Features")
    logger.info("="*60)

    from src.features.college_features import CollegeFeatureEngineer

    engineer = CollegeFeatureEngineer(driver=driver)
    engineer.update_prospect_features()

    logger.info("Feature calculation complete!")


def seed_insights(driver):
    """Seed knowledge base with core insights."""
    logger.info("="*60)
    logger.info("STEP 5: Seeding Knowledge Base")
    logger.info("="*60)

    from src.knowledge.insight_engine import InsightEngine, seed_core_insights

    seed_core_insights(driver)

    # Run discovery
    engine = InsightEngine(driver)
    count = engine.run_discovery_cycle()

    logger.info(f"Seeded insights and discovered {count} additional insights")


def verify_data(driver):
    """Verify loaded data."""
    logger.info("="*60)
    logger.info("Data Verification")
    logger.info("="*60)

    with driver.session() as session:
        queries = [
            ("Prospects", "MATCH (p:Prospect) RETURN count(p) as count"),
            ("College Teams", "MATCH (t:CollegeTeam) RETURN count(t) as count"),
            ("Conferences", "MATCH (c:Conference) RETURN count(c) as count"),
            ("College Stats", "MATCH (s:CollegeStats) RETURN count(s) as count"),
            ("Combine Results", "MATCH (c:CombineResult) RETURN count(c) as count"),
            ("Devy Snapshots", "MATCH (d:DevySnapshot) RETURN count(d) as count"),
            ("Insights", "MATCH (i:Insight) RETURN count(i) as count"),
            ("Prospect-NFL Links", "MATCH (:Prospect)-[r:BECAME_NFL_PLAYER]->(:Player) RETURN count(r) as count"),
        ]

        print("\nNode Counts:")
        print("-" * 40)
        for name, query in queries:
            result = session.run(query)
            count = result.single()['count']
            print(f"  {name:20} {count:>10,}")

        # Sample prospects
        print("\n\nTop 10 Prospects by KTC Value:")
        print("-" * 60)
        result = session.run("""
            MATCH (p:Prospect)
            OPTIONAL MATCH (p)-[:HAS_DEVY_VALUE]->(d:DevySnapshot)
            WITH p, d ORDER BY d.date DESC
            WITH p, collect(d)[0] as latest_devy
            WHERE latest_devy IS NOT NULL
            RETURN p.name as name, p.position as pos, p.college as college,
                   latest_devy.ktc_devy_value as ktc_value
            ORDER BY ktc_value DESC
            LIMIT 10
        """)

        for record in result:
            print(f"  {record['name']:25} {record['pos']:3} {record['college']:15} {record['ktc_value']:>6}")

        # Check for prospects with features
        print("\n\nTop 10 Prospects by Prospect Score:")
        print("-" * 60)
        result = session.run("""
            MATCH (p:Prospect)
            WHERE p.prospect_score IS NOT NULL
            RETURN p.name as name, p.position as pos, p.college as college,
                   round(p.prospect_score, 1) as score,
                   round(p.peak_dominator_rating, 1) as dominator
            ORDER BY p.prospect_score DESC
            LIMIT 10
        """)

        for record in result:
            print(f"  {record['name']:25} {record['pos']:3} Score:{record['score']:5} Dom:{record['dominator'] or 'N/A'}")


def run_full_pipeline(driver, years: list = None):
    """Run the complete data pipeline."""
    start_time = datetime.now()

    logger.info("="*70)
    logger.info("COLLEGE FOOTBALL DATA PIPELINE")
    logger.info(f"Started at: {start_time}")
    logger.info("="*70)

    try:
        # Step 1: Schema
        setup_schema(driver)

        # Step 2: CFBD Data
        load_cfbd_data(driver, years)

        # Step 3: Devy Values
        load_devy_values(driver)

        # Step 4: Features
        calculate_features(driver)

        # Step 5: Insights
        seed_insights(driver)

        # Verify
        verify_data(driver)

        end_time = datetime.now()
        duration = end_time - start_time

        logger.info("="*70)
        logger.info("PIPELINE COMPLETE!")
        logger.info(f"Duration: {duration}")
        logger.info("="*70)

    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        raise


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='College Football Data Pipeline')
    parser.add_argument('--schema-only', action='store_true', help='Only setup schema')
    parser.add_argument('--devy-only', action='store_true', help='Only load devy values')
    parser.add_argument('--cfbd-only', action='store_true', help='Only load CFBD data')
    parser.add_argument('--features-only', action='store_true', help='Only calculate features')
    parser.add_argument('--insights-only', action='store_true', help='Only seed insights')
    parser.add_argument('--verify', action='store_true', help='Only verify data')
    parser.add_argument('--years', type=int, nargs='+', help='Years to load (default: 2018-2025)')

    args = parser.parse_args()

    driver = get_driver()

    try:
        if args.schema_only:
            setup_schema(driver)
        elif args.devy_only:
            load_devy_values(driver)
        elif args.cfbd_only:
            load_cfbd_data(driver, args.years)
        elif args.features_only:
            calculate_features(driver)
        elif args.insights_only:
            seed_insights(driver)
        elif args.verify:
            verify_data(driver)
        else:
            run_full_pipeline(driver, args.years)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
