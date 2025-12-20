#!/usr/bin/env python3
"""
KTC Time Series Processing Script
==================================

Processes existing KTCSnapshot data in Neo4j to create time series features
for dynasty value prediction and trend analysis.

Data Source: Existing KTCSnapshot nodes in Neo4j (52K+ records)

Usage:
    python scripts/process_ktc_timeseries.py                # Process all data
    python scripts/process_ktc_timeseries.py --export       # Also export CSV
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from typing import Dict, List
from datetime import datetime, timedelta

import pandas as pd
import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class KTCTimeSeriesProcessor:
    """Processes KTC snapshot data into time series features."""

    def __init__(self):
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER")
        password = os.getenv("NEO4J_PASSWORD")
        auth = (user, password) if user and password else None
        self.driver = GraphDatabase.driver(uri, auth=auth)
        self.data_dir = Path("data/ktc_timeseries")
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def close(self):
        self.driver.close()

    def get_ktc_snapshot_info(self) -> Dict:
        """Get info about existing KTC snapshots."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (k:KTCSnapshot)
                RETURN count(k) as total,
                       count(DISTINCT k.name) as unique_players,
                       min(k.date) as min_date,
                       max(k.date) as max_date,
                       count(DISTINCT k.date) as unique_dates
            """)
            return dict(result.single())

    def extract_timeseries_data(self) -> pd.DataFrame:
        """Extract KTC time series data from Neo4j."""
        logger.info("Extracting KTC time series data...")

        # KTCSnapshot doesn't have position - join with Player or use raw data
        query = """
        MATCH (k:KTCSnapshot)
        WHERE k.ktc_value IS NOT NULL
        OPTIONAL MATCH (p:Player {name: k.name})
        RETURN k.name as player_name,
               k.ktc_id as ktc_id,
               COALESCE(p.position, k.position) as position,
               COALESCE(p.team, k.team) as team,
               k.ktc_value as ktc_value,
               k.date as date
        ORDER BY k.name, k.date
        """

        with self.driver.session() as session:
            result = session.run(query)
            records = [dict(r) for r in result]

        df = pd.DataFrame(records)
        df['date'] = pd.to_datetime(df['date'])
        logger.info(f"  Extracted {len(df):,} records for {df['player_name'].nunique():,} players")
        return df

    def calculate_timeseries_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate time series features for each player."""
        logger.info("Calculating time series features...")

        features_list = []

        for player_name, player_df in df.groupby('player_name'):
            player_df = player_df.sort_values('date')

            if len(player_df) < 3:
                continue

            # Basic info
            latest = player_df.iloc[-1]
            first = player_df.iloc[0]

            features = {
                'player_name': player_name,
                'ktc_id': latest['ktc_id'],
                'position': latest['position'] if pd.notna(latest['position']) else 'UNKNOWN',
                'team': latest['team'] if pd.notna(latest['team']) else 'UNKNOWN',
                'current_ktc': latest['ktc_value'],
                'first_ktc': first['ktc_value'],

                # Time range
                'first_date': first['date'],
                'latest_date': latest['date'],
                'days_tracked': (latest['date'] - first['date']).days,
                'snapshots_count': len(player_df),
            }

            # Value changes
            values = player_df['ktc_value'].values
            features['total_change'] = values[-1] - values[0]
            features['total_change_pct'] = ((values[-1] / values[0]) - 1) * 100 if values[0] > 0 else 0

            # Recent trends (last 30 days, 7 days)
            now = player_df['date'].max()
            last_30 = player_df[player_df['date'] >= now - timedelta(days=30)]
            last_7 = player_df[player_df['date'] >= now - timedelta(days=7)]

            if len(last_30) >= 2:
                features['change_30d'] = last_30['ktc_value'].iloc[-1] - last_30['ktc_value'].iloc[0]
                features['change_30d_pct'] = ((last_30['ktc_value'].iloc[-1] / last_30['ktc_value'].iloc[0]) - 1) * 100 if last_30['ktc_value'].iloc[0] > 0 else 0
            else:
                features['change_30d'] = 0
                features['change_30d_pct'] = 0

            if len(last_7) >= 2:
                features['change_7d'] = last_7['ktc_value'].iloc[-1] - last_7['ktc_value'].iloc[0]
                features['change_7d_pct'] = ((last_7['ktc_value'].iloc[-1] / last_7['ktc_value'].iloc[0]) - 1) * 100 if last_7['ktc_value'].iloc[0] > 0 else 0
            else:
                features['change_7d'] = 0
                features['change_7d_pct'] = 0

            # Volatility
            features['ktc_std'] = player_df['ktc_value'].std()
            features['ktc_min'] = player_df['ktc_value'].min()
            features['ktc_max'] = player_df['ktc_value'].max()
            features['ktc_range'] = features['ktc_max'] - features['ktc_min']

            # Trend direction
            if len(values) >= 5:
                # Simple linear regression slope
                x = np.arange(len(values))
                slope = np.polyfit(x, values, 1)[0]
                features['trend_slope'] = slope
                features['trend_direction'] = 'rising' if slope > 10 else ('falling' if slope < -10 else 'stable')
            else:
                features['trend_slope'] = 0
                features['trend_direction'] = 'insufficient_data'

            # Momentum (recent change vs historical average)
            if len(values) >= 10:
                recent_avg = np.mean(values[-5:])
                historical_avg = np.mean(values[:-5])
                features['momentum'] = recent_avg - historical_avg
                features['momentum_pct'] = ((recent_avg / historical_avg) - 1) * 100 if historical_avg > 0 else 0
            else:
                features['momentum'] = 0
                features['momentum_pct'] = 0

            # Peak and trough
            peak_idx = np.argmax(values)
            trough_idx = np.argmin(values)
            features['days_since_peak'] = (latest['date'] - player_df.iloc[peak_idx]['date']).days
            features['days_since_trough'] = (latest['date'] - player_df.iloc[trough_idx]['date']).days
            features['pct_off_peak'] = ((values[-1] / values[peak_idx]) - 1) * 100 if values[peak_idx] > 0 else 0
            features['pct_above_trough'] = ((values[-1] / values[trough_idx]) - 1) * 100 if values[trough_idx] > 0 else 0

            features_list.append(features)

        features_df = pd.DataFrame(features_list)
        logger.info(f"  Calculated features for {len(features_df):,} players")
        return features_df

    def create_ktc_trend_nodes(self, df: pd.DataFrame) -> int:
        """Create KTCTrend nodes in Neo4j."""
        logger.info("Creating KTCTrend nodes...")

        create_query = """
        UNWIND $records AS record
        MERGE (kt:KTCTrend {ktc_id: record.ktc_id})
        SET kt.player_name = record.player_name,
            kt.position = record.position,
            kt.team = record.team,
            kt.current_ktc = record.current_ktc,
            kt.first_ktc = record.first_ktc,

            // Changes
            kt.total_change = record.total_change,
            kt.total_change_pct = record.total_change_pct,
            kt.change_30d = record.change_30d,
            kt.change_30d_pct = record.change_30d_pct,
            kt.change_7d = record.change_7d,
            kt.change_7d_pct = record.change_7d_pct,

            // Volatility
            kt.ktc_std = record.ktc_std,
            kt.ktc_min = record.ktc_min,
            kt.ktc_max = record.ktc_max,
            kt.ktc_range = record.ktc_range,

            // Trend
            kt.trend_slope = record.trend_slope,
            kt.trend_direction = record.trend_direction,
            kt.momentum = record.momentum,
            kt.momentum_pct = record.momentum_pct,

            // Peak/trough analysis
            kt.days_since_peak = record.days_since_peak,
            kt.days_since_trough = record.days_since_trough,
            kt.pct_off_peak = record.pct_off_peak,
            kt.pct_above_trough = record.pct_above_trough,

            // Metadata
            kt.days_tracked = record.days_tracked,
            kt.snapshots_count = record.snapshots_count,
            kt.first_date = record.first_date,
            kt.latest_date = record.latest_date,
            kt.updated_at = datetime()
        """

        records = []
        for _, row in df.iterrows():
            record = {}
            for col in df.columns:
                val = row[col]
                if pd.isna(val):
                    record[col] = None
                elif isinstance(val, (pd.Timestamp, datetime)):
                    record[col] = str(val.date())
                elif isinstance(val, np.floating):
                    record[col] = float(val)
                elif isinstance(val, np.integer):
                    record[col] = int(val)
                else:
                    record[col] = val
            records.append(record)

        batch_size = 500
        total_created = 0

        with self.driver.session() as session:
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                session.run(create_query, {'records': batch})
                total_created += len(batch)

        logger.info(f"  Created {total_created:,} KTCTrend nodes")
        return total_created

    def identify_buy_sell_signals(self) -> int:
        """Identify buy/sell signals based on KTC trends."""
        logger.info("Identifying buy/sell signals...")

        signal_query = """
        MATCH (kt:KTCTrend)
        WHERE kt.current_ktc IS NOT NULL AND kt.snapshots_count >= 5

        // Calculate signal
        WITH kt,
             CASE
                 // STRONG BUY: Rising trend, gaining momentum, off peak
                 WHEN kt.trend_direction = 'rising'
                      AND kt.momentum_pct > 5
                      AND kt.pct_off_peak < -10
                 THEN 'strong_buy'

                 // BUY: Positive momentum, recovering from trough
                 WHEN kt.momentum_pct > 3
                      AND kt.pct_above_trough > 20
                      AND kt.change_30d_pct > 0
                 THEN 'buy'

                 // STRONG SELL: Falling trend, losing momentum, near peak
                 WHEN kt.trend_direction = 'falling'
                      AND kt.momentum_pct < -5
                      AND kt.days_since_peak < 30
                 THEN 'strong_sell'

                 // SELL: Negative momentum, declining
                 WHEN kt.momentum_pct < -3
                      AND kt.change_30d_pct < -5
                 THEN 'sell'

                 // HOLD: Stable
                 ELSE 'hold'
             END as signal

        SET kt.value_signal = signal,
            kt.signal_updated_at = datetime()

        RETURN signal, count(*) as count
        ORDER BY count DESC
        """

        with self.driver.session() as session:
            result = session.run(signal_query)
            signals = {r['signal']: r['count'] for r in result}

        logger.info(f"  Signal distribution: {signals}")
        return sum(signals.values())

    def get_ktc_stats(self) -> Dict:
        """Get summary statistics."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (kt:KTCTrend)
                RETURN count(kt) as total_players,
                       avg(kt.current_ktc) as avg_ktc,
                       sum(CASE WHEN kt.value_signal = 'strong_buy' THEN 1 ELSE 0 END) as strong_buys,
                       sum(CASE WHEN kt.value_signal = 'buy' THEN 1 ELSE 0 END) as buys,
                       sum(CASE WHEN kt.value_signal = 'hold' THEN 1 ELSE 0 END) as holds,
                       sum(CASE WHEN kt.value_signal = 'sell' THEN 1 ELSE 0 END) as sells,
                       sum(CASE WHEN kt.value_signal = 'strong_sell' THEN 1 ELSE 0 END) as strong_sells
            """)
            return dict(result.single())


def main():
    parser = argparse.ArgumentParser(description='Process KTC time series data')
    parser.add_argument('--export', action='store_true',
                       help='Export features to CSV')

    args = parser.parse_args()

    processor = KTCTimeSeriesProcessor()

    try:
        # Get snapshot info
        info = processor.get_ktc_snapshot_info()
        print("\n" + "=" * 60)
        print("KTC SNAPSHOT DATA AVAILABLE")
        print("=" * 60)
        print(f"Total snapshots: {info.get('total', 0):,}")
        print(f"Unique players: {info.get('unique_players', 0):,}")
        print(f"Date range: {info.get('min_date', 'N/A')} to {info.get('max_date', 'N/A')}")
        print(f"Unique dates: {info.get('unique_dates', 0)}")

        # Extract and process
        df = processor.extract_timeseries_data()
        features_df = processor.calculate_timeseries_features(df)

        # Export if requested
        if args.export:
            export_path = processor.data_dir / "ktc_features.csv"
            features_df.to_csv(export_path, index=False)
            logger.info(f"Exported features to {export_path}")

        # Create nodes
        processor.create_ktc_trend_nodes(features_df)
        processor.identify_buy_sell_signals()

        # Print summary
        stats = processor.get_ktc_stats()
        print("\n" + "=" * 60)
        print("KTC TIME SERIES PROCESSING COMPLETE")
        print("=" * 60)
        print(f"Players with trend data: {stats.get('total_players', 0):,}")
        print(f"Average KTC value: {stats.get('avg_ktc', 0):,.0f}")
        print(f"\nValue Signals:")
        print(f"  Strong Buy:  {stats.get('strong_buys', 0):,}")
        print(f"  Buy:         {stats.get('buys', 0):,}")
        print(f"  Hold:        {stats.get('holds', 0):,}")
        print(f"  Sell:        {stats.get('sells', 0):,}")
        print(f"  Strong Sell: {stats.get('strong_sells', 0):,}")

    finally:
        processor.close()


if __name__ == '__main__':
    main()
