#!/usr/bin/env python3
"""
NFL Depth Charts Ingestion Script
==================================

Downloads and integrates NFL depth chart data into the Neo4j graph database.
Creates player role profiles and competition analysis.

Data Source: nfl_data_py (ESPN depth charts)

Usage:
    python scripts/ingest_depth_charts.py                    # All available years
    python scripts/ingest_depth_charts.py --years 2023 2024  # Specific years
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


class DepthChartIngester:
    """Ingests NFL depth chart data into Neo4j."""

    def __init__(self):
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER")
        password = os.getenv("NEO4J_PASSWORD")
        auth = (user, password) if user and password else None
        self.driver = GraphDatabase.driver(uri, auth=auth)
        self.data_dir = Path("data/depth_charts")
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def close(self):
        self.driver.close()

    def download_depth_chart_data(self, years: List[int]) -> pd.DataFrame:
        """Download depth chart data from nflverse."""
        import nfl_data_py as nfl
        import warnings
        warnings.filterwarnings('ignore')

        logger.info(f"Downloading depth chart data for years: {years}")

        try:
            df = nfl.import_depth_charts(years)
            logger.info(f"  Downloaded {len(df):,} depth chart records")

            # Save locally
            df.to_parquet(self.data_dir / "depth_charts.parquet", index=False)
            return df
        except Exception as e:
            logger.error(f"  Failed to download: {e}")
            return pd.DataFrame()

    def process_depth_chart_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Process depth chart data for analysis."""
        logger.info("Processing depth chart data...")

        if df.empty:
            return df

        # Filter to fantasy-relevant positions
        fantasy_positions = ['QB', 'RB', 'FB', 'WR', 'TE']
        df = df[df['position'].isin(fantasy_positions)].copy()

        # Add role classification
        def classify_role(row):
            depth = row.get('depth_team', 99)
            pos = row.get('position', '')

            if depth == 1:
                return 'starter'
            elif depth == 2:
                return 'backup'
            elif depth == 3:
                return 'third_string'
            else:
                return 'depth'

        df['role'] = df.apply(classify_role, axis=1)

        # Add formation context
        def get_formation_role(row):
            formation = str(row.get('formation', '')).lower()
            position = row.get('position', '')

            if 'slot' in formation:
                return 'slot'
            elif 'outside' in formation or 'flanker' in formation or 'split' in formation:
                return 'outside'
            elif position == 'TE' and 'inline' in formation:
                return 'inline_te'
            elif position == 'TE':
                return 'receiving_te'
            elif position == 'RB' and '3rd' in formation:
                return 'third_down_back'
            elif position == 'FB':
                return 'fullback'
            else:
                return 'standard'

        df['formation_role'] = df.apply(get_formation_role, axis=1)

        logger.info(f"  Processed {len(df):,} fantasy-relevant records")
        return df

    def create_depth_chart_nodes(self, df: pd.DataFrame) -> int:
        """Create DepthChartEntry nodes."""
        logger.info("Creating DepthChartEntry nodes...")

        create_query = """
        UNWIND $records AS record
        MERGE (dc:DepthChartEntry {
            player_id: record.gsis_id,
            team: record.team,
            season: record.season,
            week: record.week,
            position: record.position
        })
        SET dc.player_name = record.full_name,
            dc.depth_team = record.depth_team,
            dc.formation = record.formation,
            dc.role = record.role,
            dc.formation_role = record.formation_role,
            dc.jersey_number = record.jersey_number,
            dc.loaded_at = datetime()
        """

        records = []
        for _, row in df.iterrows():
            records.append({
                'gsis_id': str(row.get('gsis_id', '')) if pd.notna(row.get('gsis_id')) else '',
                'team': str(row.get('team', '')),
                'season': int(row.get('season', 0)) if pd.notna(row.get('season')) else 0,
                'week': int(row.get('week', 0)) if pd.notna(row.get('week')) else 0,
                'position': str(row.get('position', '')),
                'full_name': str(row.get('full_name', '')),
                'depth_team': int(row.get('depth_team', 99)) if pd.notna(row.get('depth_team')) else 99,
                'formation': str(row.get('formation', '')) if pd.notna(row.get('formation')) else '',
                'role': str(row.get('role', '')),
                'formation_role': str(row.get('formation_role', '')),
                'jersey_number': int(row.get('jersey_number', 0)) if pd.notna(row.get('jersey_number')) else None
            })

        batch_size = 2000
        total_created = 0

        with self.driver.session() as session:
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                session.run(create_query, {'records': batch})
                total_created += len(batch)
                if total_created % 10000 == 0:
                    logger.info(f"    Created {total_created:,} nodes...")

        logger.info(f"  Created {total_created:,} DepthChartEntry nodes")
        return total_created

    def create_player_role_profiles(self) -> int:
        """Create aggregated player role profiles."""
        logger.info("Creating PlayerRoleProfile nodes...")

        profile_query = """
        MATCH (dc:DepthChartEntry)
        WHERE dc.player_id IS NOT NULL AND dc.player_id <> ''
        WITH dc.player_id as player_id,
             dc.player_name as player_name,
             dc.position as position,
             collect(dc) as entries

        // Calculate role metrics
        WITH player_id, player_name, position, entries,
             size([e IN entries WHERE e.role = 'starter']) as starter_weeks,
             size([e IN entries WHERE e.role = 'backup']) as backup_weeks,
             size(entries) as total_weeks,
             size([e IN entries WHERE e.formation_role = 'slot']) as slot_weeks,
             size([e IN entries WHERE e.formation_role = 'outside']) as outside_weeks,
             reduce(minSeason = 9999, e IN entries | CASE WHEN e.season < minSeason THEN e.season ELSE minSeason END) as first_season,
             reduce(maxSeason = 0, e IN entries | CASE WHEN e.season > maxSeason THEN e.season ELSE maxSeason END) as last_season

        WHERE total_weeks >= 3  // Minimum data threshold

        MERGE (prp:PlayerRoleProfile {player_id: player_id})
        SET prp.player_name = player_name,
            prp.position = position,
            prp.starter_weeks = starter_weeks,
            prp.backup_weeks = backup_weeks,
            prp.total_depth_chart_weeks = total_weeks,
            prp.starter_rate = toFloat(starter_weeks) / total_weeks,
            prp.slot_weeks = slot_weeks,
            prp.outside_weeks = outside_weeks,
            prp.first_season = first_season,
            prp.last_season = last_season,

            // Role classification
            prp.primary_role = CASE
                WHEN toFloat(starter_weeks) / total_weeks >= 0.7 THEN 'established_starter'
                WHEN toFloat(starter_weeks) / total_weeks >= 0.4 THEN 'starter_backup_mix'
                WHEN toFloat(backup_weeks) / total_weeks >= 0.7 THEN 'primary_backup'
                ELSE 'depth' END,

            // WR alignment (if WR)
            prp.alignment = CASE
                WHEN position <> 'WR' THEN null
                WHEN slot_weeks > outside_weeks THEN 'slot_primary'
                WHEN outside_weeks > slot_weeks THEN 'outside_primary'
                ELSE 'versatile' END,

            prp.updated_at = datetime()

        RETURN count(prp) as profiles_created
        """

        with self.driver.session() as session:
            result = session.run(profile_query)
            count = result.single()['profiles_created']

        logger.info(f"  Created {count:,} PlayerRoleProfile nodes")
        return count

    def create_position_competition_analysis(self) -> int:
        """Create team position competition analysis."""
        logger.info("Creating PositionCompetition analysis...")

        competition_query = """
        MATCH (dc:DepthChartEntry)
        WHERE dc.season = 2024 AND dc.week >= 1
        WITH dc.team as team, dc.position as position, dc.season as season,
             collect(DISTINCT dc.player_id) as players,
             collect(dc) as entries

        // Get starter stability
        WITH team, position, season, players,
             size(players) as player_count,
             size([e IN entries WHERE e.role = 'starter']) as starter_entries,
             size([e IN entries | e.week]) as total_entries

        WHERE position IN ['QB', 'RB', 'WR', 'TE'] AND player_count >= 2

        MERGE (pc:PositionCompetition {team: team, position: position, season: season})
        SET pc.players_rostered = player_count,
            pc.competition_level = CASE
                WHEN player_count >= 4 THEN 'high'
                WHEN player_count >= 3 THEN 'medium'
                ELSE 'low' END,
            pc.updated_at = datetime()

        RETURN count(pc) as analyses_created
        """

        with self.driver.session() as session:
            result = session.run(competition_query)
            count = result.single()['analyses_created']

        logger.info(f"  Created {count:,} PositionCompetition analyses")
        return count

    def get_depth_chart_stats(self) -> Dict:
        """Get summary statistics."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (dc:DepthChartEntry)
                RETURN count(dc) as total_entries,
                       count(DISTINCT dc.player_id) as unique_players,
                       count(DISTINCT dc.team) as teams,
                       min(dc.season) as min_season,
                       max(dc.season) as max_season
            """)
            stats = dict(result.single())

            result = session.run("""
                MATCH (prp:PlayerRoleProfile)
                WHERE prp.primary_role = 'established_starter'
                RETURN count(prp) as established_starters
            """)
            stats['established_starters'] = result.single()['established_starters']

        return stats


def main():
    parser = argparse.ArgumentParser(description='Ingest NFL depth chart data')
    parser.add_argument('--years', nargs='+', type=int,
                       default=list(range(2020, 2025)),
                       help='Years to download (default: 2020-2024)')

    args = parser.parse_args()

    ingester = DepthChartIngester()

    try:
        # Download data
        df = ingester.download_depth_chart_data(args.years)

        if df.empty:
            logger.error("No data downloaded")
            return

        # Process
        df = ingester.process_depth_chart_data(df)

        # Create nodes
        ingester.create_depth_chart_nodes(df)
        ingester.create_player_role_profiles()
        ingester.create_position_competition_analysis()

        # Print summary
        stats = ingester.get_depth_chart_stats()
        print("\n" + "=" * 60)
        print("DEPTH CHART DATA INGESTION COMPLETE")
        print("=" * 60)
        print(f"Total depth chart entries: {stats.get('total_entries', 0):,}")
        print(f"Unique players: {stats.get('unique_players', 0):,}")
        print(f"Teams: {stats.get('teams', 0)}")
        print(f"Seasons: {stats.get('min_season', 'N/A')} - {stats.get('max_season', 'N/A')}")
        print(f"Established starters identified: {stats.get('established_starters', 0):,}")

    finally:
        ingester.close()


if __name__ == '__main__':
    main()
