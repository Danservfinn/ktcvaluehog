"""
NFL Betting Data Ingestion Script
=================================
Loads historical NFL betting data into Neo4j for ML predictions.

Data Sources:
1. FiveThirtyEight NFL Elo (1920-2023): Win probabilities, Elo ratings
2. Spreadspoke (1966-2017): Spreads, over/under, weather

Usage:
    python scripts/ingest_betting_data.py              # Load all data
    python scripts/ingest_betting_data.py --elo-only   # Load only Elo data
    python scripts/ingest_betting_data.py --betting-only  # Load only betting data
    python scripts/ingest_betting_data.py --verify     # Verify loaded data
"""

import os
import sys
import logging
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List

import pandas as pd
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.neo4j_client import Neo4jClient

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Data directory
DATA_DIR = Path(__file__).parent.parent / "data" / "betting"

# Team abbreviation mappings (538 uses old abbreviations)
TEAM_ABBR_MAP = {
    # 538 abbreviations to modern
    'OAK': 'LV',    # Oakland -> Las Vegas
    'SD': 'LAC',    # San Diego -> LA Chargers
    'STL': 'LAR',   # St. Louis -> LA Rams
    'SL': 'LAR',    # Alternative St. Louis
    'LAR': 'LAR',   # Keep LA Rams
    'WAS': 'WAS',   # Washington (keep)
    'WSH': 'WAS',   # Alternative Washington
    # Historical teams (keep as-is for historical queries)
    'BOS': 'NE',    # Boston Patriots -> New England
    'BAL': 'IND',   # Baltimore Colts -> Indianapolis (pre-1984)
    # Modern team mappings
}

# Full team name to abbreviation (for spreadspoke)
TEAM_NAME_TO_ABBR = {
    'Arizona Cardinals': 'ARI',
    'Atlanta Falcons': 'ATL',
    'Baltimore Ravens': 'BAL',
    'Baltimore Colts': 'IND',  # Historical
    'Buffalo Bills': 'BUF',
    'Carolina Panthers': 'CAR',
    'Chicago Bears': 'CHI',
    'Cincinnati Bengals': 'CIN',
    'Cleveland Browns': 'CLE',
    'Dallas Cowboys': 'DAL',
    'Denver Broncos': 'DEN',
    'Detroit Lions': 'DET',
    'Green Bay Packers': 'GB',
    'Houston Texans': 'HOU',
    'Houston Oilers': 'TEN',  # Historical
    'Indianapolis Colts': 'IND',
    'Jacksonville Jaguars': 'JAX',
    'Kansas City Chiefs': 'KC',
    'Las Vegas Raiders': 'LV',
    'Los Angeles Chargers': 'LAC',
    'Los Angeles Raiders': 'LV',  # Historical
    'Los Angeles Rams': 'LAR',
    'Miami Dolphins': 'MIA',
    'Minnesota Vikings': 'MIN',
    'New England Patriots': 'NE',
    'New Orleans Saints': 'NO',
    'New York Giants': 'NYG',
    'New York Jets': 'NYJ',
    'Oakland Raiders': 'LV',  # Historical
    'Philadelphia Eagles': 'PHI',
    'Phoenix Cardinals': 'ARI',  # Historical
    'Pittsburgh Steelers': 'PIT',
    'San Diego Chargers': 'LAC',  # Historical
    'San Francisco 49ers': 'SF',
    'Seattle Seahawks': 'SEA',
    'St. Louis Cardinals': 'ARI',  # Historical
    'St. Louis Rams': 'LAR',  # Historical
    'Tampa Bay Buccaneers': 'TB',
    'Tennessee Titans': 'TEN',
    'Tennessee Oilers': 'TEN',  # Historical
    'Washington Redskins': 'WAS',  # Historical
    'Washington Football Team': 'WAS',
    'Washington Commanders': 'WAS',
}


class BettingDataETL:
    """ETL pipeline for NFL betting data into Neo4j."""

    def __init__(self):
        self.client = Neo4jClient()
        self.stats = {
            'elo_games': 0,
            'betting_games': 0,
            'game_nodes_created': 0,
            'game_nodes_updated': 0,
            'errors': 0
        }

    def setup_schema(self):
        """Create indexes and constraints for betting data."""
        logger.info("Setting up betting data schema...")

        queries = [
            # Game node constraint
            "CREATE CONSTRAINT game_id IF NOT EXISTS FOR (g:Game) REQUIRE g.game_id IS UNIQUE",
            # Indexes for common queries
            "CREATE INDEX game_season IF NOT EXISTS FOR (g:Game) ON (g.season)",
            "CREATE INDEX game_week IF NOT EXISTS FOR (g:Game) ON (g.week)",
            "CREATE INDEX game_home_team IF NOT EXISTS FOR (g:Game) ON (g.home_team)",
            "CREATE INDEX game_away_team IF NOT EXISTS FOR (g:Game) ON (g.away_team)",
            "CREATE INDEX game_spread IF NOT EXISTS FOR (g:Game) ON (g.spread_favorite)",
        ]

        for query in queries:
            try:
                self.client.run_write(query)
            except Exception as e:
                if "already exists" not in str(e).lower() and "equivalent" not in str(e).lower():
                    logger.warning(f"Schema setup warning: {e}")

    def load_elo_data(self) -> int:
        """Load FiveThirtyEight Elo data into Neo4j."""
        elo_file = DATA_DIR / "nfl_games_538.csv"

        if not elo_file.exists():
            logger.warning(f"Elo file not found: {elo_file}")
            return 0

        logger.info(f"Loading Elo data from {elo_file}")
        df = pd.read_csv(elo_file)
        logger.info(f"Loaded {len(df)} Elo game records")

        count = 0
        batch = []

        for _, row in df.iterrows():
            try:
                # Parse date and create game_id
                date = row['date']
                season = int(row['season'])
                home_team = self._normalize_team(str(row['team1']))
                away_team = self._normalize_team(str(row['team2']))

                # Create unique game_id: YYYY_WW_AWAY_HOME format
                # Since 538 doesn't have week, derive from date
                game_id = f"{date}_{away_team}_{home_team}"

                game_data = {
                    'game_id': game_id,
                    'game_date': date,
                    'season': season,
                    'home_team': home_team,
                    'away_team': away_team,
                    'neutral_site': bool(row.get('neutral', 0)),
                    'playoff': bool(row.get('playoff', 0)),
                    # Elo ratings
                    'home_elo_pre': self._safe_float(row.get('elo1')),
                    'away_elo_pre': self._safe_float(row.get('elo2')),
                    'elo_win_prob_home': self._safe_float(row.get('elo_prob1')),
                    # Scores
                    'home_score': self._safe_int(row.get('score1')),
                    'away_score': self._safe_int(row.get('score2')),
                    # Derived
                    'total_points': (self._safe_int(row.get('score1')) or 0) + (self._safe_int(row.get('score2')) or 0),
                }

                # Determine winner
                if game_data['home_score'] is not None and game_data['away_score'] is not None:
                    if game_data['home_score'] > game_data['away_score']:
                        game_data['winner'] = home_team
                    elif game_data['away_score'] > game_data['home_score']:
                        game_data['winner'] = away_team
                    else:
                        game_data['winner'] = 'TIE'

                batch.append(game_data)

                # Batch insert every 500 records
                if len(batch) >= 500:
                    count += self._batch_merge_games(batch)
                    batch = []

            except Exception as e:
                logger.warning(f"Error processing Elo row: {e}")
                self.stats['errors'] += 1

        # Insert remaining
        if batch:
            count += self._batch_merge_games(batch)

        self.stats['elo_games'] = count
        logger.info(f"Loaded {count} Elo game records")
        return count

    def load_betting_data(self) -> int:
        """Load spreadspoke betting data into Neo4j."""
        betting_file = DATA_DIR / "spreadspoke_scores.csv"

        if not betting_file.exists():
            logger.warning(f"Betting file not found: {betting_file}")
            return 0

        logger.info(f"Loading betting data from {betting_file}")
        df = pd.read_csv(betting_file)
        logger.info(f"Loaded {len(df)} betting game records")

        count = 0
        batch = []

        for _, row in df.iterrows():
            try:
                # Parse data
                date_str = str(row.get('schedule_date', ''))
                season = self._safe_int(row.get('schedule_season'))
                week = str(row.get('schedule_week', ''))

                home_team_name = str(row.get('team_home', ''))
                away_team_name = str(row.get('team_away', ''))

                home_team = self._team_name_to_abbr(home_team_name)
                away_team = self._team_name_to_abbr(away_team_name)

                if not home_team or not away_team:
                    continue

                # Create game_id
                game_id = f"{date_str}_{away_team}_{home_team}"

                game_data = {
                    'game_id': game_id,
                    'game_date': date_str,
                    'season': season,
                    'week': week,
                    'home_team': home_team,
                    'away_team': away_team,
                    'stadium': str(row.get('stadium', '')),
                    'neutral_site': str(row.get('stadium_neutral', '')).upper() == 'TRUE',
                    'playoff': str(row.get('schedule_playoff', '')).upper() == 'TRUE',
                    # Betting data
                    'favorite_team': self._team_name_to_abbr(str(row.get('team_favorite_id', ''))),
                    'spread_favorite': self._safe_float(row.get('spread_favorite')),
                    'over_under_line': self._safe_float(row.get('over_under_line')),
                    # Weather
                    'weather_temperature': self._safe_float(row.get('weather_temperature')),
                    'weather_wind_mph': self._safe_float(row.get('weather_wind_mph')),
                    'weather_humidity': self._safe_float(row.get('weather_humidity')),
                    'weather_detail': str(row.get('weather_detail', '')),
                    # Scores
                    'home_score': self._safe_int(row.get('score_home')),
                    'away_score': self._safe_int(row.get('score_away')),
                }

                # Calculate derived betting outcomes
                home_score = game_data['home_score']
                away_score = game_data['away_score']

                if home_score is not None and away_score is not None:
                    game_data['total_points'] = home_score + away_score

                    # Determine winner
                    if home_score > away_score:
                        game_data['winner'] = home_team
                    elif away_score > home_score:
                        game_data['winner'] = away_team
                    else:
                        game_data['winner'] = 'TIE'

                    # Calculate spread result
                    spread = game_data['spread_favorite']
                    favorite = game_data['favorite_team']

                    if spread is not None and favorite:
                        score_diff = home_score - away_score
                        if favorite == home_team:
                            # Home team is favorite, spread is negative
                            actual_margin = score_diff  # positive = home won
                            covered = actual_margin > abs(spread)
                            game_data['spread_result'] = 'COVER' if covered else ('PUSH' if actual_margin == abs(spread) else 'NO_COVER')
                            game_data['ats_margin'] = actual_margin + spread  # margin vs spread
                        elif favorite == away_team:
                            # Away team is favorite
                            actual_margin = away_score - home_score
                            covered = actual_margin > abs(spread)
                            game_data['spread_result'] = 'COVER' if covered else ('PUSH' if actual_margin == abs(spread) else 'NO_COVER')
                            game_data['ats_margin'] = actual_margin + spread

                    # Calculate over/under result
                    ou_line = game_data['over_under_line']
                    if ou_line is not None:
                        total = game_data['total_points']
                        if total > ou_line:
                            game_data['over_under_result'] = 'OVER'
                        elif total < ou_line:
                            game_data['over_under_result'] = 'UNDER'
                        else:
                            game_data['over_under_result'] = 'PUSH'
                        game_data['ou_margin'] = total - ou_line

                batch.append(game_data)

                if len(batch) >= 500:
                    count += self._batch_merge_games(batch)
                    batch = []

            except Exception as e:
                logger.warning(f"Error processing betting row: {e}")
                self.stats['errors'] += 1

        if batch:
            count += self._batch_merge_games(batch)

        self.stats['betting_games'] = count
        logger.info(f"Loaded {count} betting game records")
        return count

    def _batch_merge_games(self, batch: List[Dict]) -> int:
        """Batch merge game nodes into Neo4j."""
        if not batch:
            return 0

        query = """
        UNWIND $batch as game
        MERGE (g:Game {game_id: game.game_id})
        SET g.game_date = game.game_date,
            g.season = game.season,
            g.week = coalesce(game.week, g.week),
            g.home_team = game.home_team,
            g.away_team = game.away_team,
            g.stadium = coalesce(game.stadium, g.stadium),
            g.neutral_site = game.neutral_site,
            g.playoff = game.playoff,
            g.home_score = game.home_score,
            g.away_score = game.away_score,
            g.total_points = game.total_points,
            g.winner = game.winner,
            // Elo data
            g.home_elo_pre = coalesce(game.home_elo_pre, g.home_elo_pre),
            g.away_elo_pre = coalesce(game.away_elo_pre, g.away_elo_pre),
            g.elo_win_prob_home = coalesce(game.elo_win_prob_home, g.elo_win_prob_home),
            // Betting data
            g.favorite_team = coalesce(game.favorite_team, g.favorite_team),
            g.spread_favorite = coalesce(game.spread_favorite, g.spread_favorite),
            g.over_under_line = coalesce(game.over_under_line, g.over_under_line),
            g.spread_result = coalesce(game.spread_result, g.spread_result),
            g.over_under_result = coalesce(game.over_under_result, g.over_under_result),
            g.ats_margin = coalesce(game.ats_margin, g.ats_margin),
            g.ou_margin = coalesce(game.ou_margin, g.ou_margin),
            // Weather
            g.weather_temperature = coalesce(game.weather_temperature, g.weather_temperature),
            g.weather_wind_mph = coalesce(game.weather_wind_mph, g.weather_wind_mph),
            g.weather_humidity = coalesce(game.weather_humidity, g.weather_humidity),
            g.weather_detail = coalesce(game.weather_detail, g.weather_detail),
            g.updated_at = datetime()
        RETURN count(g) as merged
        """

        try:
            result = self.client.run_query(query, {'batch': batch})
            return len(batch)
        except Exception as e:
            logger.error(f"Error batch merging games: {e}")
            self.stats['errors'] += 1
            return 0

    def link_games_to_teams(self):
        """Create relationships between Game nodes and Team nodes."""
        logger.info("Linking games to teams...")

        # Link home games
        home_query = """
        MATCH (g:Game)
        WHERE g.home_team IS NOT NULL
        MATCH (t:Team {team_abbr: g.home_team})
        MERGE (t)-[r:PLAYED_HOME]->(g)
        SET r.season = g.season
        RETURN count(r) as links
        """

        # Link away games
        away_query = """
        MATCH (g:Game)
        WHERE g.away_team IS NOT NULL
        MATCH (t:Team {team_abbr: g.away_team})
        MERGE (t)-[r:PLAYED_AWAY]->(g)
        SET r.season = g.season
        RETURN count(r) as links
        """

        try:
            home_result = self.client.run_query(home_query)
            away_result = self.client.run_query(away_query)
            home_links = home_result[0]['links'] if home_result else 0
            away_links = away_result[0]['links'] if away_result else 0
            logger.info(f"Created {home_links} home game links and {away_links} away game links")
        except Exception as e:
            logger.warning(f"Error linking games to teams: {e}")

    def verify_data(self) -> Dict:
        """Verify loaded betting data."""
        queries = {
            'total_games': "MATCH (g:Game) RETURN count(g) as count",
            'games_with_elo': "MATCH (g:Game) WHERE g.home_elo_pre IS NOT NULL RETURN count(g) as count",
            'games_with_spread': "MATCH (g:Game) WHERE g.spread_favorite IS NOT NULL RETURN count(g) as count",
            'games_with_ou': "MATCH (g:Game) WHERE g.over_under_line IS NOT NULL RETURN count(g) as count",
            'seasons_covered': "MATCH (g:Game) RETURN min(g.season) as min_season, max(g.season) as max_season",
            'recent_games': "MATCH (g:Game) WHERE g.season >= 2010 RETURN count(g) as count",
        }

        stats = {}
        for name, query in queries.items():
            try:
                result = self.client.run_query(query)
                if result:
                    if name == 'seasons_covered':
                        stats['min_season'] = result[0].get('min_season')
                        stats['max_season'] = result[0].get('max_season')
                    else:
                        stats[name] = result[0].get('count', 0)
            except Exception as e:
                stats[name] = f"Error: {e}"

        return stats

    def _normalize_team(self, abbr: str) -> str:
        """Normalize team abbreviation to modern version."""
        if not abbr:
            return ''
        abbr = abbr.upper().strip()
        return TEAM_ABBR_MAP.get(abbr, abbr)

    def _team_name_to_abbr(self, name: str) -> str:
        """Convert team full name to abbreviation."""
        if not name:
            return ''
        name = name.strip()
        return TEAM_NAME_TO_ABBR.get(name, name if len(name) <= 4 else '')

    def _safe_float(self, val) -> Optional[float]:
        """Safely convert to float."""
        if pd.isna(val) or val is None or val == '':
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    def _safe_int(self, val) -> Optional[int]:
        """Safely convert to int."""
        if pd.isna(val) or val is None or val == '':
            return None
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return None

    def run_full_etl(self) -> Dict:
        """Run complete betting data ETL."""
        start_time = datetime.now()
        logger.info("=" * 60)
        logger.info("NFL BETTING DATA ETL")
        logger.info("=" * 60)

        # Setup schema
        self.setup_schema()

        # Load data sources
        self.load_elo_data()
        self.load_betting_data()

        # Create relationships
        self.link_games_to_teams()

        duration = datetime.now() - start_time

        logger.info("=" * 60)
        logger.info("ETL COMPLETE")
        logger.info(f"Duration: {duration}")
        logger.info(f"Elo games loaded: {self.stats['elo_games']:,}")
        logger.info(f"Betting games loaded: {self.stats['betting_games']:,}")
        logger.info(f"Errors: {self.stats['errors']}")
        logger.info("=" * 60)

        return self.stats

    def close(self):
        """Close database connection."""
        if self.client:
            self.client.close()


def download_data():
    """Download betting datasets if not present."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    elo_file = DATA_DIR / "nfl_games_538.csv"
    betting_file = DATA_DIR / "spreadspoke_scores.csv"

    import urllib.request

    if not elo_file.exists():
        logger.info("Downloading FiveThirtyEight Elo data...")
        url = "https://raw.githubusercontent.com/fivethirtyeight/nfl-elo-game/master/data/nfl_games.csv"
        urllib.request.urlretrieve(url, elo_file)
        logger.info(f"Downloaded Elo data to {elo_file}")

    if not betting_file.exists():
        logger.info("Downloading Spreadspoke betting data...")
        url = "https://raw.githubusercontent.com/slieb74/NFL-Betting-Data/master/spreadspoke_scores.csv"
        try:
            urllib.request.urlretrieve(url, betting_file)
            # Fix line endings
            with open(betting_file, 'r') as f:
                content = f.read().replace('\r', '\n')
            with open(betting_file, 'w') as f:
                f.write(content)
            logger.info(f"Downloaded betting data to {betting_file}")
        except Exception as e:
            logger.warning(f"Could not download betting data: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Load NFL betting data into Neo4j')
    parser.add_argument('--elo-only', action='store_true', help='Load only Elo data')
    parser.add_argument('--betting-only', action='store_true', help='Load only betting data')
    parser.add_argument('--verify', action='store_true', help='Verify loaded data')
    parser.add_argument('--download', action='store_true', help='Download data files')

    args = parser.parse_args()

    if args.download:
        download_data()
        sys.exit(0)

    etl = BettingDataETL()

    try:
        if args.verify:
            print("\nBetting Data Verification:")
            print("-" * 40)
            stats = etl.verify_data()
            for key, value in stats.items():
                print(f"  {key}: {value:,}" if isinstance(value, int) else f"  {key}: {value}")
        elif args.elo_only:
            etl.setup_schema()
            etl.load_elo_data()
        elif args.betting_only:
            etl.setup_schema()
            etl.load_betting_data()
        else:
            etl.run_full_etl()
    finally:
        etl.close()
