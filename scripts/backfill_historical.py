#!/usr/bin/env python3
"""
Historical NFL Data Backfill Script
====================================
Master script for backfilling 26 years (1999-2024) of NFL data into Neo4j
for ML training purposes.

Data Coverage:
- Player Stats: 1999-2024 (26 seasons)
- Snap Counts: 2015-2024 (10 seasons)
- Next Gen Stats: 2016-2024 (9 seasons)
- Combine Results: 2000-2024 (25 seasons)
- Draft Picks: 1999-2024 (26 seasons)

Expected Volume:
- ~450,000 weekly stat records
- ~26,000 season stat records
- ~100,000 snap count records (2015+)
- ~50,000 NGS records (2016+)
- ~7,500 combine records
- ~6,500 draft picks

Usage:
    python scripts/backfill_historical.py                    # Full backfill
    python scripts/backfill_historical.py --schema-only      # Only setup schema
    python scripts/backfill_historical.py --stats-only       # Only player stats
    python scripts/backfill_historical.py --years 2020-2024  # Specific year range
    python scripts/backfill_historical.py --verify           # Verify existing data
    python scripts/backfill_historical.py --link             # Only link relationships
"""

import os
import sys
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(project_root / 'logs' / 'historical_backfill.log')
    ]
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


def parse_year_range(year_str: str) -> Tuple[int, int]:
    """Parse year range string like '2020-2024' into tuple."""
    if '-' in year_str:
        parts = year_str.split('-')
        return int(parts[0]), int(parts[1])
    else:
        year = int(year_str)
        return year, year


def setup_schema(driver):
    """Setup Neo4j schema for historical data."""
    logger.info("=" * 70)
    logger.info("STEP 1: Setting up Historical Data Schema")
    logger.info("=" * 70)

    from src.database.historical_schema import HistoricalSchemaManager

    schema_manager = HistoricalSchemaManager(driver)
    schema_manager.setup_schema()

    # Verify
    verification = schema_manager.verify_schema()
    logger.info(f"Schema verification: {verification['constraints']} constraints, {verification['indexes']} indexes")


def load_player_stats(driver, start_year: int = 1999, end_year: int = 2024):
    """Load historical player stats."""
    logger.info("=" * 70)
    logger.info(f"STEP 2: Loading Player Stats ({start_year}-{end_year})")
    logger.info("=" * 70)

    from src.loaders.historical_nfl_loader import HistoricalNFLLoader
    from src.database.historical_schema import (
        HISTORICAL_WEEKLY_MERGE,
        HISTORICAL_SEASON_MERGE
    )

    loader = HistoricalNFLLoader()

    # Load weekly stats
    logger.info("Loading weekly player stats from nflverse...")
    weekly_df = loader.load_player_stats_range(start_year, end_year)

    if weekly_df.empty:
        logger.warning("No weekly stats loaded!")
        return 0, 0

    logger.info(f"Loaded {len(weekly_df):,} weekly stat records")

    # Load into Neo4j
    weekly_count = 0
    with driver.session() as session:
        # Batch insert for efficiency
        batch_size = 1000
        for i in range(0, len(weekly_df), batch_size):
            batch = weekly_df.iloc[i:i+batch_size]

            for _, row in batch.iterrows():
                try:
                    session.run(HISTORICAL_WEEKLY_MERGE, {
                        'player_id': row.get('player_id'),
                        'season': int(row.get('season', 0)),
                        'week': int(row.get('week', 0)),
                        'player_name': row.get('player_name'),
                        'position': row.get('position'),
                        'team': row.get('recent_team'),
                        'opponent': row.get('opponent_team'),
                        'completions': row.get('completions'),
                        'attempts': row.get('attempts'),
                        'passing_yards': row.get('passing_yards'),
                        'passing_tds': row.get('passing_tds'),
                        'interceptions': row.get('interceptions'),
                        'sacks': row.get('sacks'),
                        'carries': row.get('carries'),
                        'rushing_yards': row.get('rushing_yards'),
                        'rushing_tds': row.get('rushing_tds'),
                        'targets': row.get('targets'),
                        'receptions': row.get('receptions'),
                        'receiving_yards': row.get('receiving_yards'),
                        'receiving_tds': row.get('receiving_tds'),
                        'fantasy_points': row.get('fantasy_points'),
                        'fantasy_points_ppr': row.get('fantasy_points_ppr'),
                        'target_share': row.get('target_share'),
                        'air_yards_share': row.get('air_yards_share'),
                        'wopr': row.get('wopr'),
                    })
                    weekly_count += 1
                except Exception as e:
                    logger.debug(f"Error loading weekly stat: {e}")

            if (i + batch_size) % 10000 == 0:
                logger.info(f"  Processed {i + batch_size:,} weekly records...")

    logger.info(f"Loaded {weekly_count:,} weekly stats into Neo4j")

    # Compute and load season totals
    logger.info("Computing season aggregates...")
    season_df = loader.compute_season_totals(weekly_df)
    logger.info(f"Computed {len(season_df):,} season records")

    season_count = 0
    with driver.session() as session:
        for _, row in season_df.iterrows():
            try:
                session.run(HISTORICAL_SEASON_MERGE, {
                    'player_id': row.get('player_id'),
                    'season': int(row.get('season', 0)),
                    'player_name': row.get('player_name'),
                    'position': row.get('position'),
                    'team': row.get('team'),
                    'games': int(row.get('games', 0)),
                    'total_fantasy_points': row.get('total_fantasy_points'),
                    'total_fantasy_points_ppr': row.get('total_fantasy_points_ppr'),
                    'ppg_std': row.get('ppg_std'),
                    'ppg_ppr': row.get('ppg_ppr'),
                    'passing_yards': row.get('passing_yards'),
                    'passing_tds': row.get('passing_tds'),
                    'interceptions': row.get('interceptions'),
                    'rushing_yards': row.get('rushing_yards'),
                    'rushing_tds': row.get('rushing_tds'),
                    'carries': row.get('carries'),
                    'targets': row.get('targets'),
                    'receptions': row.get('receptions'),
                    'receiving_yards': row.get('receiving_yards'),
                    'receiving_tds': row.get('receiving_tds'),
                    'avg_target_share': row.get('avg_target_share'),
                    'avg_air_yards_share': row.get('avg_air_yards_share'),
                    'avg_wopr': row.get('avg_wopr'),
                })
                season_count += 1
            except Exception as e:
                logger.debug(f"Error loading season stat: {e}")

    logger.info(f"Loaded {season_count:,} season stats into Neo4j")

    return weekly_count, season_count


def load_snap_counts(driver, start_year: int = 2015, end_year: int = 2024):
    """Load historical snap counts (2015+)."""
    logger.info("=" * 70)
    logger.info(f"STEP 3: Loading Snap Counts ({start_year}-{end_year})")
    logger.info("=" * 70)

    # Snap counts only available from 2015
    actual_start = max(start_year, 2015)
    if actual_start > end_year:
        logger.info("Snap counts only available from 2015 - skipping")
        return 0

    from src.loaders.historical_nfl_loader import HistoricalNFLLoader
    from src.database.historical_schema import HISTORICAL_SNAP_MERGE

    loader = HistoricalNFLLoader()
    snap_df = loader.load_snap_counts_range(actual_start, end_year)

    if snap_df.empty:
        logger.warning("No snap counts loaded!")
        return 0

    logger.info(f"Loaded {len(snap_df):,} snap count records")

    snap_count = 0
    with driver.session() as session:
        batch_size = 1000
        for i in range(0, len(snap_df), batch_size):
            batch = snap_df.iloc[i:i+batch_size]

            for _, row in batch.iterrows():
                try:
                    session.run(HISTORICAL_SNAP_MERGE, {
                        'player_id': row.get('player') or row.get('pfr_player_id'),
                        'season': int(row.get('season', 0)),
                        'week': int(row.get('week', 0)),
                        'player_name': row.get('player'),
                        'position': row.get('position'),
                        'team': row.get('team'),
                        'offense_snaps': row.get('offense_snaps'),
                        'offense_pct': row.get('offense_pct'),
                        'defense_snaps': row.get('defense_snaps'),
                        'defense_pct': row.get('defense_pct'),
                        'st_snaps': row.get('st_snaps'),
                        'st_pct': row.get('st_pct'),
                    })
                    snap_count += 1
                except Exception as e:
                    logger.debug(f"Error loading snap count: {e}")

            if (i + batch_size) % 10000 == 0:
                logger.info(f"  Processed {i + batch_size:,} snap records...")

    logger.info(f"Loaded {snap_count:,} snap counts into Neo4j")
    return snap_count


def load_ngs_stats(driver, start_year: int = 2016, end_year: int = 2024):
    """Load historical Next Gen Stats (2016+)."""
    logger.info("=" * 70)
    logger.info(f"STEP 4: Loading Next Gen Stats ({start_year}-{end_year})")
    logger.info("=" * 70)

    # NGS only available from 2016
    actual_start = max(start_year, 2016)
    if actual_start > end_year:
        logger.info("NGS only available from 2016 - skipping")
        return 0

    from src.loaders.historical_nfl_loader import HistoricalNFLLoader
    from src.database.historical_schema import HISTORICAL_NGS_MERGE

    loader = HistoricalNFLLoader()
    ngs_dict = loader.load_ngs_range(actual_start, end_year)

    # ngs_dict is a dict with keys: 'passing', 'rushing', 'receiving'
    if not ngs_dict or all(df.empty for df in ngs_dict.values()):
        logger.warning("No NGS data loaded!")
        return 0

    total_records = sum(len(df) for df in ngs_dict.values())
    logger.info(f"Loaded {total_records:,} total NGS records")

    ngs_count = 0
    with driver.session() as session:
        for stat_type, ngs_df in ngs_dict.items():
            if ngs_df.empty:
                continue

            logger.info(f"  Loading {stat_type} NGS ({len(ngs_df):,} records)...")

            for _, row in ngs_df.iterrows():
                try:
                    # Build metrics dict from NGS columns
                    metrics = {}
                    exclude_cols = ['player_gsis_id', 'player_id', 'season', 'week',
                                   'player_display_name', 'player_name', 'position',
                                   'team_abbr', 'team', 'ngs_year']
                    ngs_cols = [c for c in row.index if c not in exclude_cols]
                    for col in ngs_cols:
                        val = row.get(col)
                        if val is not None and not (isinstance(val, float) and pd.isna(val)):
                            metrics[col] = val

                    session.run(HISTORICAL_NGS_MERGE, {
                        'player_id': row.get('player_gsis_id') or row.get('player_id'),
                        'season': int(row.get('season', 0)),
                        'week': int(row.get('week', 0)),
                        'stat_type': stat_type,
                        'player_name': row.get('player_display_name') or row.get('player_name'),
                        'position': row.get('position'),
                        'team': row.get('team_abbr') or row.get('team'),
                        'metrics': str(metrics),  # Store as JSON string
                    })
                    ngs_count += 1
                except Exception as e:
                    logger.debug(f"Error loading NGS: {e}")

    logger.info(f"Loaded {ngs_count:,} NGS records into Neo4j")
    return ngs_count


def load_combine_data(driver, start_year: int = 2000, end_year: int = 2024):
    """Load NFL Combine results."""
    logger.info("=" * 70)
    logger.info(f"STEP 5: Loading Combine Data ({start_year}-{end_year})")
    logger.info("=" * 70)

    actual_start = max(start_year, 2000)

    from src.loaders.historical_nfl_loader import HistoricalNFLLoader
    from src.database.historical_schema import COMBINE_MERGE

    loader = HistoricalNFLLoader()
    combine_df = loader.load_combine_all()

    if combine_df.empty:
        logger.warning("No combine data loaded!")
        return 0

    # Filter to year range
    combine_df = combine_df[
        (combine_df['season'] >= actual_start) &
        (combine_df['season'] <= end_year)
    ]

    logger.info(f"Loaded {len(combine_df):,} combine records")

    combine_count = 0
    with driver.session() as session:
        for _, row in combine_df.iterrows():
            try:
                session.run(COMBINE_MERGE, {
                    'player_id': row.get('pfr_id') or row.get('player_id'),
                    'season': int(row.get('season', 0)),
                    'player_name': row.get('player_name'),
                    'position': row.get('pos'),
                    'college': row.get('school'),
                    'height': row.get('ht'),
                    'weight': row.get('wt'),
                    'forty_yard': row.get('forty'),
                    'vertical_jump': row.get('vertical'),
                    'broad_jump': row.get('broad_jump'),
                    'three_cone': row.get('cone'),
                    'shuttle': row.get('shuttle'),
                    'bench_press': row.get('bench'),
                })
                combine_count += 1
            except Exception as e:
                logger.debug(f"Error loading combine: {e}")

    logger.info(f"Loaded {combine_count:,} combine records into Neo4j")
    return combine_count


def load_draft_data(driver, start_year: int = 1999, end_year: int = 2024):
    """Load NFL Draft picks."""
    logger.info("=" * 70)
    logger.info(f"STEP 6: Loading Draft Data ({start_year}-{end_year})")
    logger.info("=" * 70)

    from src.loaders.historical_nfl_loader import HistoricalNFLLoader
    from src.database.historical_schema import DRAFT_PICK_MERGE

    loader = HistoricalNFLLoader()
    draft_df = loader.load_draft_picks_range(start_year, end_year)

    if draft_df.empty:
        logger.warning("No draft data loaded!")
        return 0

    logger.info(f"Loaded {len(draft_df):,} draft records")

    draft_count = 0
    with driver.session() as session:
        for _, row in draft_df.iterrows():
            try:
                session.run(DRAFT_PICK_MERGE, {
                    'season': int(row.get('season', 0)),
                    'round': int(row.get('round', 0)),
                    'pick': int(row.get('pick', 0)),
                    'overall_pick': int(row.get('overall', 0)) if row.get('overall') else None,
                    'team': row.get('team'),
                    'player_name': row.get('pfr_player_name') or row.get('player_name'),
                    'position': row.get('position'),
                    'college': row.get('college'),
                    'player_id': row.get('pfr_player_id'),
                })
                draft_count += 1
            except Exception as e:
                logger.debug(f"Error loading draft: {e}")

    logger.info(f"Loaded {draft_count:,} draft picks into Neo4j")
    return draft_count


def create_relationships(driver):
    """Create relationships between historical nodes and Player nodes."""
    logger.info("=" * 70)
    logger.info("STEP 7: Creating Relationships")
    logger.info("=" * 70)

    from src.database.historical_schema import (
        LINK_HISTORICAL_TO_PLAYER,
        CREATE_SEASON_CHAINS,
        LINK_COMBINE_TO_PLAYER,
        LINK_DRAFT_TO_PLAYER
    )

    with driver.session() as session:
        # Link historical seasons to players
        logger.info("Linking historical seasons to players...")
        result = session.run(LINK_HISTORICAL_TO_PLAYER)
        linked = result.single()['linked']
        logger.info(f"  Linked {linked:,} historical seasons to players")

        # Create season chains
        logger.info("Creating season chains...")
        result = session.run(CREATE_SEASON_CHAINS)
        chains = result.single()['chains']
        logger.info(f"  Created {chains:,} season chain relationships")

        # Link combine to players
        logger.info("Linking combine results to players...")
        result = session.run(LINK_COMBINE_TO_PLAYER)
        linked = result.single()['linked']
        logger.info(f"  Linked {linked:,} combine results to players")

        # Link draft to players
        logger.info("Linking draft picks to players...")
        result = session.run(LINK_DRAFT_TO_PLAYER)
        linked = result.single()['linked']
        logger.info(f"  Linked {linked:,} draft picks to players")


def verify_data(driver):
    """Verify loaded historical data."""
    logger.info("=" * 70)
    logger.info("Historical Data Verification")
    logger.info("=" * 70)

    from src.database.historical_schema import HistoricalSchemaManager

    schema_manager = HistoricalSchemaManager(driver)

    # Get counts
    counts = schema_manager.get_data_counts()
    print("\nNode Counts:")
    print("-" * 50)
    for name, count in counts.items():
        print(f"  {name:25} {count:>12,}")

    # Get year coverage
    coverage = schema_manager.get_year_coverage()
    print("\n\nYear Coverage:")
    print("-" * 50)
    for name, info in coverage.items():
        print(f"  {name:25} {info['min_year']}-{info['max_year']} ({info['count']:,} records)")

    # Sample season chain verification
    with driver.session() as session:
        result = session.run("""
            MATCH path = (h1:HistoricalSeasonStats)-[:NEXT_SEASON*3..5]->(h2:HistoricalSeasonStats)
            WHERE h1.position IN ['QB', 'RB', 'WR', 'TE']
            WITH h1, length(path) as chain_length
            RETURN h1.player_name as player, h1.position as pos,
                   h1.season as start_season, chain_length
            ORDER BY chain_length DESC
            LIMIT 10
        """)

        print("\n\nLongest Career Chains (Season-over-Season Data):")
        print("-" * 70)
        for record in result:
            print(f"  {record['player']:25} {record['pos']:3} "
                  f"Starting {record['start_season']} - {record['chain_length']} consecutive seasons")


def run_full_backfill(driver, start_year: int = 1999, end_year: int = 2024):
    """Run the complete historical backfill."""
    start_time = datetime.now()

    logger.info("=" * 70)
    logger.info("HISTORICAL NFL DATA BACKFILL")
    logger.info(f"Years: {start_year}-{end_year}")
    logger.info(f"Started at: {start_time}")
    logger.info("=" * 70)

    stats = {}

    try:
        # Step 1: Schema
        setup_schema(driver)

        # Step 2: Player Stats
        weekly, season = load_player_stats(driver, start_year, end_year)
        stats['weekly_stats'] = weekly
        stats['season_stats'] = season

        # Step 3: Snap Counts
        stats['snap_counts'] = load_snap_counts(driver, start_year, end_year)

        # Step 4: NGS
        stats['ngs_stats'] = load_ngs_stats(driver, start_year, end_year)

        # Step 5: Combine
        stats['combine'] = load_combine_data(driver, start_year, end_year)

        # Step 6: Draft
        stats['draft'] = load_draft_data(driver, start_year, end_year)

        # Step 7: Relationships
        create_relationships(driver)

        # Verify
        verify_data(driver)

        end_time = datetime.now()
        duration = end_time - start_time

        logger.info("=" * 70)
        logger.info("BACKFILL COMPLETE!")
        logger.info(f"Duration: {duration}")
        logger.info("=" * 70)
        logger.info("Summary:")
        for key, value in stats.items():
            logger.info(f"  {key}: {value:,}")

        return stats

    except Exception as e:
        logger.error(f"Backfill failed: {e}")
        raise


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Historical NFL Data Backfill')
    parser.add_argument('--schema-only', action='store_true', help='Only setup schema')
    parser.add_argument('--stats-only', action='store_true', help='Only load player stats')
    parser.add_argument('--snaps-only', action='store_true', help='Only load snap counts')
    parser.add_argument('--ngs-only', action='store_true', help='Only load NGS data')
    parser.add_argument('--combine-only', action='store_true', help='Only load combine data')
    parser.add_argument('--draft-only', action='store_true', help='Only load draft data')
    parser.add_argument('--link', action='store_true', help='Only create relationships')
    parser.add_argument('--verify', action='store_true', help='Only verify data')
    parser.add_argument('--years', type=str, default='1999-2024',
                       help='Year range (e.g., 2020-2024)')

    args = parser.parse_args()

    # Ensure logs directory exists
    logs_dir = project_root / 'logs'
    logs_dir.mkdir(exist_ok=True)

    # Parse year range
    start_year, end_year = parse_year_range(args.years)

    driver = get_driver()

    try:
        if args.schema_only:
            setup_schema(driver)
        elif args.stats_only:
            setup_schema(driver)
            load_player_stats(driver, start_year, end_year)
        elif args.snaps_only:
            load_snap_counts(driver, start_year, end_year)
        elif args.ngs_only:
            load_ngs_stats(driver, start_year, end_year)
        elif args.combine_only:
            load_combine_data(driver, start_year, end_year)
        elif args.draft_only:
            load_draft_data(driver, start_year, end_year)
        elif args.link:
            create_relationships(driver)
        elif args.verify:
            verify_data(driver)
        else:
            run_full_backfill(driver, start_year, end_year)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
