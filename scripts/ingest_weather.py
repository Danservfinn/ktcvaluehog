#!/usr/bin/env python3
"""
NFL Weather Data Ingestion Script
=================================

Downloads and integrates NFL game weather data into the Neo4j graph database.

Data Sources:
- ThompsonJamesBliss/WeatherData (2000-2020): https://github.com/ThompsonJamesBliss/WeatherData
- nflfastR play-by-play data (includes weather string field)

Usage:
    python scripts/ingest_weather.py                    # Download and ingest
    python scripts/ingest_weather.py --update-only     # Update existing games
"""

import os
import sys
import argparse
import logging
import requests
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class WeatherDataIngester:
    """Ingests NFL game weather data into Neo4j."""

    # GitHub raw URLs for weather data
    WEATHER_DATA_URL = "https://raw.githubusercontent.com/ThompsonJamesBliss/WeatherData/master/data/games_weather.csv"
    STADIUM_DATA_URL = "https://raw.githubusercontent.com/ThompsonJamesBliss/WeatherData/master/data/stadium_coordinates.csv"
    GAME_DATA_URL = "https://raw.githubusercontent.com/ThompsonJamesBliss/WeatherData/master/data/games.csv"

    def __init__(self):
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER")
        password = os.getenv("NEO4J_PASSWORD")
        auth = (user, password) if user and password else None
        self.driver = GraphDatabase.driver(uri, auth=auth)
        self.data_dir = Path("data/weather")
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def close(self):
        self.driver.close()

    def download_weather_data(self) -> Dict[str, pd.DataFrame]:
        """Download weather data from GitHub."""
        import io
        import ssl
        import urllib.request

        logger.info("Downloading weather data from GitHub...")

        dfs = {}

        # Create SSL context that doesn't verify certificates (for development)
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        def download_csv(url: str, name: str) -> Optional[pd.DataFrame]:
            try:
                logger.info(f"  Downloading {name}...")
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, context=ssl_context) as response:
                    content = response.read().decode('utf-8')
                    df = pd.read_csv(io.StringIO(content))
                    logger.info(f"    Downloaded {len(df):,} records")
                    return df
            except Exception as e:
                logger.error(f"    Failed to download {name}: {e}")
                return None

        # Download each file
        weather_df = download_csv(self.WEATHER_DATA_URL, "games_weather.csv")
        if weather_df is not None:
            weather_df.to_csv(self.data_dir / "games_weather.csv", index=False)
            dfs['weather'] = weather_df

        stadium_df = download_csv(self.STADIUM_DATA_URL, "stadium_coordinates.csv")
        if stadium_df is not None:
            stadium_df.to_csv(self.data_dir / "stadium_coordinates.csv", index=False)
            dfs['stadium'] = stadium_df

        game_df = download_csv(self.GAME_DATA_URL, "games.csv")
        if game_df is not None:
            game_df.to_csv(self.data_dir / "games.csv", index=False)
            dfs['game'] = game_df

        return dfs

    def load_local_data(self) -> Dict[str, pd.DataFrame]:
        """Load weather data from local files."""
        dfs = {}

        weather_path = self.data_dir / "weather.csv"
        stadium_path = self.data_dir / "stadium.csv"
        game_path = self.data_dir / "game.csv"

        if weather_path.exists():
            dfs['weather'] = pd.read_csv(weather_path)
        if stadium_path.exists():
            dfs['stadium'] = pd.read_csv(stadium_path)
        if game_path.exists():
            dfs['game'] = pd.read_csv(game_path)

        return dfs

    def process_weather_data(self, dfs: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Merge and process weather data for Neo4j ingestion."""
        logger.info("Processing weather data...")

        if 'weather' not in dfs or 'game' not in dfs or 'stadium' not in dfs:
            raise ValueError("Missing required dataframes")

        weather_df = dfs['weather']
        game_df = dfs['game']
        stadium_df = dfs['stadium']

        # Rename columns to standard names
        game_df = game_df.rename(columns={
            'Season': 'season',
            'StadiumName': 'stadium'
        })

        stadium_df = stadium_df.rename(columns={
            'StadiumName': 'stadium',
            'HomeTeam': 'home_team',
            'RoofType': 'roof_type'
        })

        weather_df = weather_df.rename(columns={
            'Temperature': 'temperature',
            'Humidity': 'humidity',
            'WindSpeed': 'wind_speed',
            'WindDirection': 'wind_direction',
            'Precipitation': 'precipitation',
            'EstimatedCondition': 'condition'
        })

        # Merge game and stadium info
        merged = game_df.merge(stadium_df, on='stadium', how='left')

        # Aggregate weather per game (use mean for numeric values)
        weather_agg = weather_df.groupby('game_id').agg({
            'temperature': 'mean',
            'humidity': 'mean',
            'wind_speed': 'mean',
            'wind_direction': 'mean',
            'precipitation': 'sum',
            'condition': 'first'
        }).reset_index()

        merged = merged.merge(weather_agg, on='game_id', how='left')

        # Calculate derived features
        merged['is_dome'] = merged['roof_type'].str.lower().isin(['indoor', 'dome', 'retractable']).astype(int)
        merged['is_cold'] = (merged['temperature'] < 40).astype(int)
        merged['is_windy'] = (merged['wind_speed'] > 15).astype(int)
        merged['has_precipitation'] = (merged['precipitation'] > 0).astype(int)

        logger.info(f"  Processed {len(merged):,} game-weather records")
        return merged

    def create_weather_nodes(self, df: pd.DataFrame) -> int:
        """Create GameWeather nodes in Neo4j."""
        logger.info("Creating GameWeather nodes in Neo4j...")

        create_query = """
        UNWIND $records AS record
        MERGE (gw:GameWeather {game_id: record.game_id})
        SET gw.season = record.season,
            gw.stadium = record.stadium,
            gw.home_team = record.home_team,
            gw.temperature = record.temperature,
            gw.humidity = record.humidity,
            gw.wind_speed = record.wind_speed,
            gw.wind_direction = record.wind_direction,
            gw.precipitation = record.precipitation,
            gw.condition = record.condition,
            gw.is_dome = record.is_dome,
            gw.is_cold = record.is_cold,
            gw.is_windy = record.is_windy,
            gw.has_precipitation = record.has_precipitation,
            gw.roof_type = record.roof_type,
            gw.loaded_at = datetime()
        """

        # Prepare records
        records = []
        for _, row in df.iterrows():
            record = {
                'game_id': str(row.get('game_id', '')),
                'season': int(row.get('season', 0)) if pd.notna(row.get('season')) else None,
                'stadium': str(row.get('stadium', '')),
                'home_team': str(row.get('home_team', '')) if pd.notna(row.get('home_team')) else None,
                'temperature': float(row.get('temperature')) if pd.notna(row.get('temperature')) else None,
                'humidity': float(row.get('humidity')) if pd.notna(row.get('humidity')) else None,
                'wind_speed': float(row.get('wind_speed')) if pd.notna(row.get('wind_speed')) else None,
                'wind_direction': float(row.get('wind_direction')) if pd.notna(row.get('wind_direction')) else None,
                'precipitation': float(row.get('precipitation')) if pd.notna(row.get('precipitation')) else None,
                'condition': str(row.get('condition', '')) if pd.notna(row.get('condition')) else None,
                'is_dome': int(row.get('is_dome', 0)),
                'is_cold': int(row.get('is_cold', 0)),
                'is_windy': int(row.get('is_windy', 0)),
                'has_precipitation': int(row.get('has_precipitation', 0)),
                'roof_type': str(row.get('roof_type', '')) if pd.notna(row.get('roof_type')) else None
            }
            records.append(record)

        # Batch insert
        batch_size = 500
        total_created = 0

        with self.driver.session() as session:
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                session.run(create_query, {'records': batch})
                total_created += len(batch)
                if (i + batch_size) % 1000 == 0:
                    logger.info(f"    Created {total_created:,} nodes...")

        logger.info(f"  Created {total_created:,} GameWeather nodes")
        return total_created

    def create_team_weather_aggregations(self) -> None:
        """Create team-season weather aggregations for ML features."""
        logger.info("Creating team-season weather aggregations...")

        # This would link GameWeather to teams based on schedule
        # For now, we'll create aggregations that can be joined later
        agg_query = """
        MATCH (gw:GameWeather)
        WHERE gw.season IS NOT NULL
        WITH gw.season as season,
             avg(gw.temperature) as avg_temp,
             avg(gw.wind_speed) as avg_wind,
             sum(gw.is_cold) as cold_games,
             sum(gw.is_dome) as dome_games,
             sum(gw.has_precipitation) as precip_games,
             count(*) as total_games
        MERGE (sa:SeasonWeatherAgg {season: season})
        SET sa.avg_temperature = avg_temp,
            sa.avg_wind_speed = avg_wind,
            sa.cold_game_count = cold_games,
            sa.dome_game_count = dome_games,
            sa.precipitation_game_count = precip_games,
            sa.total_games = total_games,
            sa.cold_game_rate = toFloat(cold_games) / total_games,
            sa.dome_game_rate = toFloat(dome_games) / total_games
        """

        with self.driver.session() as session:
            session.run(agg_query)

        logger.info("  Created season weather aggregations")

    def get_weather_stats(self) -> Dict:
        """Get summary statistics of weather data in Neo4j."""
        query = """
        MATCH (gw:GameWeather)
        RETURN count(gw) as total_games,
               min(gw.season) as min_season,
               max(gw.season) as max_season,
               avg(gw.temperature) as avg_temp,
               sum(gw.is_dome) as dome_games,
               sum(gw.is_cold) as cold_games,
               sum(gw.is_windy) as windy_games,
               sum(gw.has_precipitation) as precip_games
        """

        with self.driver.session() as session:
            result = session.run(query)
            record = result.single()
            return dict(record) if record else {}


def main():
    parser = argparse.ArgumentParser(description='Ingest NFL weather data')
    parser.add_argument('--update-only', action='store_true',
                       help='Only update existing games, skip download')
    parser.add_argument('--local', action='store_true',
                       help='Use local data files instead of downloading')

    args = parser.parse_args()

    ingester = WeatherDataIngester()

    try:
        # Download or load data
        if args.local:
            logger.info("Loading local weather data...")
            dfs = ingester.load_local_data()
        else:
            dfs = ingester.download_weather_data()

        if not dfs:
            logger.error("No data available")
            return

        # Process data
        processed_df = ingester.process_weather_data(dfs)

        # Create nodes in Neo4j
        ingester.create_weather_nodes(processed_df)

        # Create aggregations
        ingester.create_team_weather_aggregations()

        # Print summary
        stats = ingester.get_weather_stats()
        print("\n" + "=" * 60)
        print("WEATHER DATA INGESTION COMPLETE")
        print("=" * 60)
        print(f"Total games: {stats.get('total_games', 0):,}")
        print(f"Seasons: {stats.get('min_season', 'N/A')} - {stats.get('max_season', 'N/A')}")
        print(f"Average temperature: {stats.get('avg_temp', 0):.1f}F")
        print(f"Dome games: {stats.get('dome_games', 0):,}")
        print(f"Cold games (<40F): {stats.get('cold_games', 0):,}")
        print(f"Windy games (>15mph): {stats.get('windy_games', 0):,}")
        print(f"Precipitation games: {stats.get('precip_games', 0):,}")

    finally:
        ingester.close()


if __name__ == '__main__':
    main()
