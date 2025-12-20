#!/usr/bin/env python3
"""
KTC Snapshot Job - Twice Daily Data Collection
===============================================

Combined script for scheduled KTC data collection:
1. Fetches latest KTC values from API
2. Archives to timestamped CSV (AM/PM)
3. Stores snapshot to Neo4j database
4. Updates KTCTrend nodes

Designed to run twice daily via launchd/cron.

Usage:
    python scripts/ktc_snapshot_job.py           # Run full job
    python scripts/ktc_snapshot_job.py --test    # Test without saving
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime

import requests
import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

# Configuration
DATA_DIR = project_root / "data"
HISTORICAL_DIR = DATA_DIR / "historical" / "ktc_snapshots"
LOG_DIR = project_root / "logs"

# Setup logging
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'ktc_snapshot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def get_driver():
    """Get Neo4j driver."""
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")
    auth = (user, password) if user and password else None
    return GraphDatabase.driver(uri, auth=auth)


def fetch_ktc_data() -> pd.DataFrame:
    """Fetch KTC values from API or local file."""
    logger.info("Fetching KTC data...")

    # Try multiple API endpoints
    api_urls = [
        "https://keeptradecut.com/api/v1/rankings",
        "https://keeptradecut.com/dynasty-rankings/rankings.json",
    ]

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Referer': 'https://keeptradecut.com/dynasty-rankings'
    }

    for api_url in api_urls:
        try:
            params = {'format': 'json', 'sf': '1', 'tep': '0.5'}
            response = requests.get(api_url, headers=headers, params=params, timeout=30)

            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    df = pd.DataFrame(data)
                    logger.info(f"  Retrieved {len(df)} players from API")
                    return df

        except Exception as e:
            logger.debug(f"API {api_url} failed: {e}")
            continue

    # Fallback to local file
    logger.info("  API unavailable, using local ktc_live.json...")
    local_file = DATA_DIR / "ktc_live.json"

    if local_file.exists():
        try:
            with open(local_file, 'r') as f:
                data = json.load(f)
            if isinstance(data, list) and len(data) > 0:
                df = pd.DataFrame(data)
                logger.info(f"  Loaded {len(df)} players from local file")
                return df
        except Exception as e:
            logger.error(f"Failed to load local file: {e}")

    # Try scraped CSV as last resort
    scraped_file = DATA_DIR / "ktc_scraped.csv"
    if scraped_file.exists():
        try:
            df = pd.read_csv(scraped_file)
            logger.info(f"  Loaded {len(df)} players from scraped CSV")
            return df
        except Exception as e:
            logger.error(f"Failed to load scraped CSV: {e}")

    return None


def process_ktc_data(df: pd.DataFrame) -> pd.DataFrame:
    """Process raw KTC data into clean format."""
    if df is None or len(df) == 0:
        return None

    players = []
    for _, row in df.iterrows():
        # Handle multiple data formats
        sf_data = row.get('superflexValues', {})
        if isinstance(sf_data, str):
            try:
                sf_data = eval(sf_data)
            except:
                sf_data = {}

        # Get KTC value from various possible fields
        ktc_value = 0
        if isinstance(sf_data, dict) and 'value' in sf_data:
            ktc_value = sf_data.get('value', 0)
        elif 'ktc_sf' in row:
            ktc_value = row.get('ktc_sf', 0)
        elif 'value' in row:
            ktc_value = row.get('value', 0)
        elif 'superflexValue' in row:
            ktc_value = row.get('superflexValue', 0)

        # Get player ID from various fields
        ktc_id = (row.get('playerID') or row.get('playerid') or
                  row.get('sleeper_id') or row.get('id') or
                  str(hash(row.get('name', row.get('playerName', '')))))

        # Get name from various fields
        name = row.get('name') or row.get('playerName') or row.get('playername', '')

        players.append({
            'ktc_id': str(ktc_id),
            'name': name,
            'position': row.get('position', ''),
            'team': row.get('team', ''),
            'age': row.get('age', 0),
            'ktc_value': int(ktc_value) if ktc_value else 0,
            'ktc_rank': sf_data.get('rank', 0) if isinstance(sf_data, dict) else 0,
            'trend_7d': sf_data.get('overall7DayTrend', 0) if isinstance(sf_data, dict) else 0,
            'positional_rank': sf_data.get('positionalRank', 0) if isinstance(sf_data, dict) else 0,
        })

    return pd.DataFrame(players)


def archive_snapshot(df: pd.DataFrame, test_mode: bool = False) -> str:
    """Archive snapshot to CSV with AM/PM designation."""
    HISTORICAL_DIR.mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    today = now.strftime('%Y%m%d')
    period = 'AM' if now.hour < 12 else 'PM'
    snapshot_file = HISTORICAL_DIR / f"ktc_{today}_{period}.csv"

    if snapshot_file.exists() and not test_mode:
        logger.info(f"Snapshot already exists for {today} {period}")
        return str(snapshot_file)

    # Add metadata
    df = df.copy()
    df['snapshot_date'] = today
    df['snapshot_period'] = period
    df['snapshot_ts'] = now.isoformat()

    if not test_mode:
        df.to_csv(snapshot_file, index=False)
        logger.info(f"Archived {len(df)} players to {snapshot_file}")

        # Update consolidated file
        consolidated = HISTORICAL_DIR / "ktc_all_snapshots.csv"
        if consolidated.exists():
            existing = pd.read_csv(consolidated)
            combined = pd.concat([existing, df], ignore_index=True)
            combined = combined.drop_duplicates(
                subset=['ktc_id', 'snapshot_date', 'snapshot_period'],
                keep='last'
            )
        else:
            combined = df
        combined.to_csv(consolidated, index=False)

    return str(snapshot_file)


def store_to_neo4j(df: pd.DataFrame, test_mode: bool = False):
    """Store snapshot to Neo4j KTCSnapshot nodes."""
    if test_mode:
        logger.info("Test mode - skipping Neo4j storage")
        return

    logger.info("Storing snapshot to Neo4j...")

    driver = get_driver()
    now = datetime.now()
    date_str = now.strftime('%Y-%m-%d')
    period = 'AM' if now.hour < 12 else 'PM'

    with driver.session() as session:
        # Create KTCSnapshot nodes
        records = df.to_dict('records')

        session.run("""
            UNWIND $records AS r
            MERGE (ks:KTCSnapshot {
                ktc_id: r.ktc_id,
                date: $date,
                period: $period
            })
            SET ks.name = r.name,
                ks.position = r.position,
                ks.team = r.team,
                ks.ktc_value = r.ktc_value,
                ks.ktc_rank = r.ktc_rank,
                ks.trend_7d = r.trend_7d,
                ks.positional_rank = r.positional_rank,
                ks.snapshot_ts = datetime()
        """, {'records': records, 'date': date_str, 'period': period})

        # Count snapshots
        result = session.run("""
            MATCH (ks:KTCSnapshot)
            RETURN count(ks) as total,
                   count(DISTINCT ks.date) as days
        """)
        stats = result.single()
        logger.info(f"  Total KTC snapshots: {stats['total']:,} across {stats['days']} days")

    driver.close()


def update_ktc_trends(test_mode: bool = False):
    """Update KTCTrend nodes with latest calculations."""
    if test_mode:
        return

    logger.info("Updating KTCTrend nodes...")

    driver = get_driver()

    with driver.session() as session:
        # Update trends based on recent snapshots
        result = session.run("""
            MATCH (ks:KTCSnapshot)
            WHERE ks.ktc_value > 0
            WITH ks.ktc_id as ktc_id,
                 ks.name as name,
                 ks.position as position,
                 ks.team as team,
                 collect(ks) as snapshots

            WITH ktc_id, name, position, team, snapshots,
                 [s IN snapshots | s.ktc_value] as values,
                 snapshots[0] as latest

            WHERE size(values) >= 2

            WITH ktc_id, name, position, team, values, latest,
                 values[0] as current_val,
                 values[-1] as first_val,
                 reduce(sum = 0, v IN values | sum + v) / size(values) as avg_val

            MERGE (kt:KTCTrend {ktc_id: ktc_id})
            SET kt.player_name = name,
                kt.position = position,
                kt.team = team,
                kt.current_ktc = current_val,
                kt.first_ktc = first_val,
                kt.total_change = current_val - first_val,
                kt.total_change_pct = toFloat(current_val - first_val) / first_val * 100,
                kt.snapshots_count = size(values),
                kt.updated_at = datetime()

            RETURN count(kt) as updated
        """)
        updated = result.single()['updated']
        logger.info(f"  Updated {updated} KTCTrend nodes")

    driver.close()


def print_summary(df: pd.DataFrame):
    """Print summary of fetched data."""
    print("\n" + "=" * 60)
    print("KTC SNAPSHOT SUMMARY")
    print("=" * 60)

    now = datetime.now()
    period = 'AM' if now.hour < 12 else 'PM'
    print(f"Time: {now.strftime('%Y-%m-%d %H:%M')} ({period})")
    print(f"Players: {len(df)}")

    print("\nTop 5 by KTC Value:")
    for _, row in df.nlargest(5, 'ktc_value').iterrows():
        print(f"  {row['name']:<25} ({row['position']}) - {row['ktc_value']:,}")

    print("\nBiggest 7-Day Risers:")
    risers = df[df['trend_7d'] > 0].nlargest(5, 'trend_7d')
    for _, row in risers.iterrows():
        print(f"  {row['name']:<25} +{row['trend_7d']:,}")

    print("\nBiggest 7-Day Fallers:")
    fallers = df[df['trend_7d'] < 0].nsmallest(5, 'trend_7d')
    for _, row in fallers.iterrows():
        print(f"  {row['name']:<25} {row['trend_7d']:,}")


def main():
    parser = argparse.ArgumentParser(description='KTC Snapshot Job')
    parser.add_argument('--test', action='store_true', help='Test mode (no saving)')
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("KTC SNAPSHOT JOB STARTED")
    logger.info(f"Time: {datetime.now().isoformat()}")
    logger.info(f"Mode: {'TEST' if args.test else 'PRODUCTION'}")
    logger.info("=" * 60)

    try:
        # Fetch data
        raw_df = fetch_ktc_data()
        if raw_df is None:
            logger.error("Failed to fetch KTC data")
            return 1

        # Process
        df = process_ktc_data(raw_df)
        if df is None or len(df) == 0:
            logger.error("Failed to process KTC data")
            return 1

        # Archive to CSV
        archive_snapshot(df, test_mode=args.test)

        # Store to Neo4j
        store_to_neo4j(df, test_mode=args.test)

        # Update trends
        update_ktc_trends(test_mode=args.test)

        # Print summary
        print_summary(df)

        # Save live JSON
        if not args.test:
            live_file = DATA_DIR / "ktc_live.json"
            raw_df.to_json(live_file, orient='records', indent=2)
            logger.info(f"Saved live data to {live_file}")

        logger.info("=" * 60)
        logger.info("KTC SNAPSHOT JOB COMPLETED SUCCESSFULLY")
        logger.info("=" * 60)
        return 0

    except Exception as e:
        logger.error(f"Job failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
