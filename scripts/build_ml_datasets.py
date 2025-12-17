#!/usr/bin/env python3
"""
ML Training Dataset Builder Script
===================================
Build ML training datasets from historical NFL data.

Prerequisites:
- Historical data must be loaded first (run backfill_historical.py)

Usage:
    python scripts/build_ml_datasets.py                    # Build all datasets
    python scripts/build_ml_datasets.py --season-only      # Only season projection
    python scripts/build_ml_datasets.py --weekly-only      # Only weekly prediction
    python scripts/build_ml_datasets.py --breakout-only    # Only breakout probability
    python scripts/build_ml_datasets.py --output data/ml   # Custom output dir
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


def verify_historical_data(driver) -> bool:
    """Verify historical data exists before building datasets."""
    with driver.session() as session:
        result = session.run("""
            MATCH (h:HistoricalSeasonStats)
            RETURN count(h) as count,
                   min(h.season) as min_year,
                   max(h.season) as max_year
        """)
        record = result.single()

        if record['count'] == 0:
            logger.error("No historical data found! Run backfill_historical.py first.")
            return False

        logger.info(f"Found {record['count']:,} historical season records ({record['min_year']}-{record['max_year']})")
        return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Build ML Training Datasets')
    parser.add_argument('--season-only', action='store_true', help='Only build season projection dataset')
    parser.add_argument('--weekly-only', action='store_true', help='Only build weekly prediction dataset')
    parser.add_argument('--breakout-only', action='store_true', help='Only build breakout probability dataset')
    parser.add_argument('--output', type=str, default='data/ml_training', help='Output directory')
    parser.add_argument('--format', type=str, choices=['parquet', 'csv'], default='parquet', help='Output format')

    args = parser.parse_args()

    driver = get_driver()

    try:
        # Verify data exists
        if not verify_historical_data(driver):
            sys.exit(1)

        from src.ml.training_dataset_builder import TrainingDatasetBuilder

        builder = TrainingDatasetBuilder(driver)
        output_path = Path(args.output)
        output_path.mkdir(parents=True, exist_ok=True)

        start_time = datetime.now()

        if args.season_only:
            logger.info("Building Season Projection Dataset...")
            df = builder.build_season_projection_dataset()
            builder.export_dataset(df, str(output_path / f'season_projection.{args.format}'))
            logger.info(f"Built {len(df):,} rows")

        elif args.weekly_only:
            logger.info("Building Weekly Prediction Dataset...")
            df = builder.build_weekly_prediction_dataset()
            builder.export_dataset(df, str(output_path / f'weekly_prediction.{args.format}'))
            logger.info(f"Built {len(df):,} rows")

        elif args.breakout_only:
            logger.info("Building Breakout Probability Dataset...")
            df = builder.build_breakout_dataset()
            builder.export_dataset(df, str(output_path / f'breakout_probability.{args.format}'))
            logger.info(f"Built {len(df):,} rows")

        else:
            # Build all datasets
            from src.ml.training_dataset_builder import build_all_datasets
            stats = build_all_datasets(driver, str(output_path))

            logger.info("\nDataset Sizes:")
            for name, count in stats.items():
                logger.info(f"  {name}: {count:,} rows")

        duration = datetime.now() - start_time
        logger.info(f"\nCompleted in {duration}")

    finally:
        driver.close()


if __name__ == "__main__":
    main()
