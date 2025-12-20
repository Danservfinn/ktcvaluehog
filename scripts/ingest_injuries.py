#!/usr/bin/env python3
"""
NFL Injury History Ingestion Script
====================================

Downloads and integrates NFL injury data into the Neo4j graph database.
Creates player injury profiles with historical patterns.

Data Source: nfl_data_py (Pro Football Reference injury reports)

Usage:
    python scripts/ingest_injuries.py                    # All available years
    python scripts/ingest_injuries.py --years 2023 2024  # Specific years
"""

import os
import sys
import ssl
import argparse
import logging
from pathlib import Path
from typing import Dict, List
from datetime import datetime

# Bypass SSL verification for nflverse downloads
ssl._create_default_https_context = ssl._create_unverified_context

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


class InjuryDataIngester:
    """Ingests NFL injury data into Neo4j."""

    def __init__(self):
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER")
        password = os.getenv("NEO4J_PASSWORD")
        auth = (user, password) if user and password else None
        self.driver = GraphDatabase.driver(uri, auth=auth)
        self.data_dir = Path("data/injuries")
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def close(self):
        self.driver.close()

    def download_injury_data(self, years: List[int]) -> pd.DataFrame:
        """Download injury data from nflverse."""
        import nfl_data_py as nfl
        import warnings
        warnings.filterwarnings('ignore')

        logger.info(f"Downloading injury data for years: {years}")

        try:
            df = nfl.import_injuries(years)
            logger.info(f"  Downloaded {len(df):,} injury records")

            # Save locally
            df.to_parquet(self.data_dir / "injuries.parquet", index=False)
            return df
        except Exception as e:
            logger.error(f"  Failed to download: {e}")
            return pd.DataFrame()

    def process_injury_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Process and aggregate injury data for ML features."""
        logger.info("Processing injury data...")

        if df.empty:
            return df

        # Classify injury types
        def classify_injury(injury_str):
            if pd.isna(injury_str):
                return 'unknown'
            injury = injury_str.lower()
            if any(x in injury for x in ['hamstring', 'quad', 'calf', 'groin', 'thigh']):
                return 'soft_tissue_leg'
            elif any(x in injury for x in ['shoulder', 'pec', 'bicep', 'tricep']):
                return 'soft_tissue_upper'
            elif any(x in injury for x in ['knee', 'acl', 'mcl']):
                return 'knee'
            elif any(x in injury for x in ['ankle', 'foot', 'toe']):
                return 'ankle_foot'
            elif any(x in injury for x in ['concussion', 'head']):
                return 'concussion'
            elif any(x in injury for x in ['back', 'neck', 'spine']):
                return 'back_neck'
            elif any(x in injury for x in ['hand', 'wrist', 'finger', 'thumb']):
                return 'hand_wrist'
            elif 'illness' in injury or 'sick' in injury:
                return 'illness'
            else:
                return 'other'

        df['injury_category'] = df['report_primary_injury'].apply(classify_injury)

        # Severity based on status
        def classify_severity(status):
            if pd.isna(status):
                return 'unknown'
            status = status.lower()
            if status == 'out':
                return 'out'
            elif status == 'doubtful':
                return 'doubtful'
            elif status == 'questionable':
                return 'questionable'
            elif status == 'probable':
                return 'probable'
            else:
                return 'unknown'

        df['severity'] = df['report_status'].apply(classify_severity)

        logger.info(f"  Processed {len(df):,} records")
        return df

    def create_injury_report_nodes(self, df: pd.DataFrame) -> int:
        """Create InjuryReport nodes for each injury instance."""
        logger.info("Creating InjuryReport nodes...")

        create_query = """
        UNWIND $records AS record
        MERGE (ir:InjuryReport {
            player_id: record.gsis_id,
            season: record.season,
            week: record.week
        })
        SET ir.player_name = record.full_name,
            ir.team = record.team,
            ir.position = record.position,
            ir.primary_injury = record.primary_injury,
            ir.secondary_injury = record.secondary_injury,
            ir.report_status = record.report_status,
            ir.practice_status = record.practice_status,
            ir.injury_category = record.injury_category,
            ir.severity = record.severity,
            ir.game_type = record.game_type,
            ir.date_modified = record.date_modified,
            ir.loaded_at = datetime()
        """

        records = []
        for _, row in df.iterrows():
            records.append({
                'gsis_id': str(row.get('gsis_id', '')),
                'season': int(row.get('season', 0)),
                'week': int(row.get('week', 0)),
                'full_name': str(row.get('full_name', '')),
                'team': str(row.get('team', '')),
                'position': str(row.get('position', '')),
                'primary_injury': str(row.get('report_primary_injury', '')) if pd.notna(row.get('report_primary_injury')) else None,
                'secondary_injury': str(row.get('report_secondary_injury', '')) if pd.notna(row.get('report_secondary_injury')) else None,
                'report_status': str(row.get('report_status', '')) if pd.notna(row.get('report_status')) else None,
                'practice_status': str(row.get('practice_status', '')) if pd.notna(row.get('practice_status')) else None,
                'injury_category': str(row.get('injury_category', '')),
                'severity': str(row.get('severity', '')),
                'game_type': str(row.get('game_type', '')),
                'date_modified': str(row.get('date_modified', ''))
            })

        batch_size = 1000
        total_created = 0

        with self.driver.session() as session:
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                session.run(create_query, {'records': batch})
                total_created += len(batch)
                if total_created % 5000 == 0:
                    logger.info(f"    Created {total_created:,} nodes...")

        logger.info(f"  Created {total_created:,} InjuryReport nodes")
        return total_created

    def create_player_injury_profiles(self) -> int:
        """Aggregate injuries into player profiles with risk scores."""
        logger.info("Creating PlayerInjuryProfile nodes...")

        profile_query = """
        MATCH (ir:InjuryReport)
        WHERE ir.player_id IS NOT NULL
        WITH ir.player_id as player_id,
             collect(ir) as injuries,
             ir.player_name as player_name,
             ir.position as position

        // Count by category
        WITH player_id, player_name, position, injuries,
             size([i IN injuries WHERE i.injury_category = 'soft_tissue_leg']) as soft_tissue_leg_count,
             size([i IN injuries WHERE i.injury_category = 'soft_tissue_upper']) as soft_tissue_upper_count,
             size([i IN injuries WHERE i.injury_category = 'knee']) as knee_count,
             size([i IN injuries WHERE i.injury_category = 'ankle_foot']) as ankle_foot_count,
             size([i IN injuries WHERE i.injury_category = 'concussion']) as concussion_count,
             size([i IN injuries WHERE i.injury_category = 'back_neck']) as back_neck_count,
             size([i IN injuries WHERE i.severity = 'out']) as games_out,
             size([i IN injuries WHERE i.severity = 'questionable']) as games_questionable,
             size(injuries) as total_injury_reports,
             reduce(minSeason = 9999, i IN injuries | CASE WHEN i.season < minSeason THEN i.season ELSE minSeason END) as first_injury_season,
             reduce(maxSeason = 0, i IN injuries | CASE WHEN i.season > maxSeason THEN i.season ELSE maxSeason END) as last_injury_season

        MERGE (pip:PlayerInjuryProfile {player_id: player_id})
        SET pip.player_name = player_name,
            pip.position = position,
            pip.soft_tissue_leg_count = soft_tissue_leg_count,
            pip.soft_tissue_upper_count = soft_tissue_upper_count,
            pip.knee_injury_count = knee_count,
            pip.ankle_foot_count = ankle_foot_count,
            pip.concussion_count = concussion_count,
            pip.back_neck_count = back_neck_count,
            pip.games_listed_out = games_out,
            pip.games_questionable = games_questionable,
            pip.total_injury_reports = total_injury_reports,
            pip.first_injury_season = first_injury_season,
            pip.last_injury_season = last_injury_season,

            // Risk scores
            pip.soft_tissue_risk = CASE
                WHEN soft_tissue_leg_count + soft_tissue_upper_count >= 5 THEN 'high'
                WHEN soft_tissue_leg_count + soft_tissue_upper_count >= 2 THEN 'medium'
                ELSE 'low' END,
            pip.structural_risk = CASE
                WHEN knee_count >= 2 OR ankle_foot_count >= 3 THEN 'high'
                WHEN knee_count >= 1 OR ankle_foot_count >= 2 THEN 'medium'
                ELSE 'low' END,
            pip.concussion_risk = CASE
                WHEN concussion_count >= 3 THEN 'high'
                WHEN concussion_count >= 1 THEN 'medium'
                ELSE 'low' END,
            pip.overall_injury_risk = CASE
                WHEN games_out >= 10 THEN 'high'
                WHEN games_out >= 5 THEN 'medium'
                ELSE 'low' END,

            pip.updated_at = datetime()

        RETURN count(pip) as profiles_created
        """

        with self.driver.session() as session:
            result = session.run(profile_query)
            count = result.single()['profiles_created']

        logger.info(f"  Created {count:,} PlayerInjuryProfile nodes")
        return count

    def get_injury_stats(self) -> Dict:
        """Get summary statistics."""
        query = """
        MATCH (ir:InjuryReport)
        RETURN count(ir) as total_reports,
               count(DISTINCT ir.player_id) as unique_players,
               min(ir.season) as min_season,
               max(ir.season) as max_season

        UNION ALL

        MATCH (pip:PlayerInjuryProfile)
        WHERE pip.overall_injury_risk = 'high'
        RETURN count(pip) as high_risk_players, 0, 0, 0
        """

        with self.driver.session() as session:
            result = session.run("""
                MATCH (ir:InjuryReport)
                RETURN count(ir) as total_reports,
                       count(DISTINCT ir.player_id) as unique_players,
                       min(ir.season) as min_season,
                       max(ir.season) as max_season
            """)
            stats = dict(result.single())

            result = session.run("""
                MATCH (pip:PlayerInjuryProfile)
                WHERE pip.overall_injury_risk = 'high'
                RETURN count(pip) as high_risk
            """)
            stats['high_risk_players'] = result.single()['high_risk']

        return stats


def main():
    parser = argparse.ArgumentParser(description='Ingest NFL injury data')
    parser.add_argument('--years', nargs='+', type=int,
                       default=list(range(2016, 2025)),
                       help='Years to download (default: 2016-2024)')

    args = parser.parse_args()

    ingester = InjuryDataIngester()

    try:
        # Download data
        df = ingester.download_injury_data(args.years)

        if df.empty:
            logger.error("No data downloaded")
            return

        # Process
        df = ingester.process_injury_data(df)

        # Create nodes
        ingester.create_injury_report_nodes(df)
        ingester.create_player_injury_profiles()

        # Print summary
        stats = ingester.get_injury_stats()
        print("\n" + "=" * 60)
        print("INJURY DATA INGESTION COMPLETE")
        print("=" * 60)
        print(f"Total injury reports: {stats.get('total_reports', 0):,}")
        print(f"Unique players: {stats.get('unique_players', 0):,}")
        print(f"Seasons: {stats.get('min_season', 'N/A')} - {stats.get('max_season', 'N/A')}")
        print(f"High-risk players identified: {stats.get('high_risk_players', 0):,}")

    finally:
        ingester.close()


if __name__ == '__main__':
    main()
