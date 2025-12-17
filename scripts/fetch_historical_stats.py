"""
Fetch historical NFL stats from nflverse and store in Neo4j.
Creates WeeklyStats and SeasonStats nodes linked to Player nodes.
"""

import pandas as pd
import numpy as np
from neo4j import GraphDatabase
from datetime import datetime
import warnings
import ssl
import urllib.request
import io
import os

warnings.filterwarnings('ignore')

# Fix SSL certificate verification issues on macOS
ssl._create_default_https_context = ssl._create_unverified_context

# nflverse data URLs
NFLVERSE_BASE = "https://github.com/nflverse/nflverse-data/releases/download"
PLAYER_STATS_URL = f"{NFLVERSE_BASE}/player_stats/player_stats.parquet"
WEEKLY_STATS_URL_TEMPLATE = f"{NFLVERSE_BASE}/player_stats/player_stats_{{year}}.parquet"

# Local cache directory
CACHE_DIR = "/Users/kurultai/ktcvaluehog/data/nflverse"

def get_driver():
    """Get Neo4j driver."""
    return GraphDatabase.driver("bolt://localhost:7687", auth=None)


def download_file(url: str, local_path: str) -> str:
    """Download file with SSL bypass."""
    import requests
    try:
        response = requests.get(url, verify=False, timeout=60)
        response.raise_for_status()
        with open(local_path, 'wb') as f:
            f.write(response.content)
        return local_path
    except Exception as e:
        print(f"  Download error: {e}")
        return None


def fetch_player_stats(years: list = None) -> pd.DataFrame:
    """Fetch player stats from nflverse."""
    print("Fetching player stats from nflverse...")

    os.makedirs(CACHE_DIR, exist_ok=True)

    # Try to download and read parquet files
    dfs = []
    for year in years or range(2019, 2026):
        local_path = f"{CACHE_DIR}/player_stats_{year}.parquet"

        # Check if cached
        if os.path.exists(local_path):
            print(f"  Using cached {year}...")
            try:
                year_df = pd.read_parquet(local_path)
                dfs.append(year_df)
                print(f"    Loaded {len(year_df):,} records")
                continue
            except:
                pass

        # Download
        url = WEEKLY_STATS_URL_TEMPLATE.format(year=year)
        print(f"  Downloading {year}...")
        try:
            import requests
            response = requests.get(url, verify=False, timeout=120)
            if response.status_code == 200:
                with open(local_path, 'wb') as f:
                    f.write(response.content)
                year_df = pd.read_parquet(local_path)
                dfs.append(year_df)
                print(f"    Downloaded {len(year_df):,} records")
            else:
                print(f"    HTTP {response.status_code} - skipping")
        except Exception as e:
            print(f"    Error: {e}")

    if not dfs:
        raise Exception("No stats data could be fetched")

    df = pd.concat(dfs, ignore_index=True)

    # Filter to skill positions
    if 'position' in df.columns:
        df = df[df['position'].isin(['QB', 'RB', 'WR', 'TE'])].copy()

    print(f"Total: {len(df):,} skill position records")
    return df


def create_weekly_stats(driver, df: pd.DataFrame):
    """Create WeeklyStats nodes in Neo4j."""
    print("\nCreating WeeklyStats nodes...")

    # Group by player and week
    weekly_cols = [
        'player_id', 'player_name', 'position', 'season', 'week', 'season_type',
        'completions', 'attempts', 'passing_yards', 'passing_tds', 'interceptions',
        'carries', 'rushing_yards', 'rushing_tds',
        'receptions', 'targets', 'receiving_yards', 'receiving_tds',
        'fantasy_points', 'fantasy_points_ppr'
    ]

    # Filter to available columns
    available_cols = [c for c in weekly_cols if c in df.columns]
    weekly_df = df[available_cols].copy()

    # Calculate additional metrics
    if 'attempts' in weekly_df.columns and 'completions' in weekly_df.columns:
        weekly_df['completion_pct'] = (weekly_df['completions'] / weekly_df['attempts'].replace(0, np.nan) * 100).fillna(0)

    if 'targets' in weekly_df.columns and 'receptions' in weekly_df.columns:
        weekly_df['catch_rate'] = (weekly_df['receptions'] / weekly_df['targets'].replace(0, np.nan) * 100).fillna(0)

    if 'carries' in weekly_df.columns and 'rushing_yards' in weekly_df.columns:
        weekly_df['yards_per_carry'] = (weekly_df['rushing_yards'] / weekly_df['carries'].replace(0, np.nan)).fillna(0)

    # Fill NaN with 0 for numeric columns
    numeric_cols = weekly_df.select_dtypes(include=[np.number]).columns
    weekly_df[numeric_cols] = weekly_df[numeric_cols].fillna(0)

    with driver.session() as session:
        # Create constraint if not exists
        try:
            session.run("CREATE CONSTRAINT weekly_stats_unique IF NOT EXISTS FOR (w:WeeklyStats) REQUIRE (w.player_id, w.season, w.week) IS UNIQUE")
        except:
            pass

        batch_size = 500
        records = weekly_df.to_dict('records')

        for i in range(0, len(records), batch_size):
            batch = records[i:i+batch_size]

            session.run("""
                UNWIND $batch AS row
                MERGE (w:WeeklyStats {
                    player_id: row.player_id,
                    season: toInteger(row.season),
                    week: toInteger(row.week)
                })
                SET w.player_name = row.player_name,
                    w.position = row.position,
                    w.season_type = row.season_type,
                    w.completions = toFloat(row.completions),
                    w.attempts = toFloat(row.attempts),
                    w.passing_yards = toFloat(row.passing_yards),
                    w.passing_tds = toFloat(row.passing_tds),
                    w.interceptions = toFloat(row.interceptions),
                    w.carries = toFloat(row.carries),
                    w.rushing_yards = toFloat(row.rushing_yards),
                    w.rushing_tds = toFloat(row.rushing_tds),
                    w.receptions = toFloat(row.receptions),
                    w.targets = toFloat(row.targets),
                    w.receiving_yards = toFloat(row.receiving_yards),
                    w.receiving_tds = toFloat(row.receiving_tds),
                    w.fantasy_points = toFloat(row.fantasy_points),
                    w.fantasy_points_ppr = toFloat(row.fantasy_points_ppr),
                    w.completion_pct = toFloat(row.completion_pct),
                    w.catch_rate = toFloat(row.catch_rate),
                    w.yards_per_carry = toFloat(row.yards_per_carry),
                    w.updated_at = datetime()

                WITH w, row
                MATCH (p:Player)
                WHERE p.gsis_id = row.player_id OR p.name = row.player_name
                MERGE (p)-[:HAS_WEEKLY_STATS]->(w)
            """, {'batch': batch})

            print(f"  Processed {min(i+batch_size, len(records)):,}/{len(records):,} weekly records")

    print(f"Created {len(records):,} WeeklyStats nodes")


def create_season_stats(driver, df: pd.DataFrame):
    """Create SeasonStats nodes by aggregating weekly data."""
    print("\nCreating SeasonStats nodes...")

    # Aggregate by player and season
    agg_funcs = {
        'player_name': 'first',
        'position': 'first',
        'week': 'count',  # games played
        'completions': 'sum',
        'attempts': 'sum',
        'passing_yards': 'sum',
        'passing_tds': 'sum',
        'interceptions': 'sum',
        'carries': 'sum',
        'rushing_yards': 'sum',
        'rushing_tds': 'sum',
        'receptions': 'sum',
        'targets': 'sum',
        'receiving_yards': 'sum',
        'receiving_tds': 'sum',
        'fantasy_points': 'sum',
        'fantasy_points_ppr': 'sum'
    }

    # Filter to available columns
    available_aggs = {k: v for k, v in agg_funcs.items() if k in df.columns}

    season_df = df.groupby(['player_id', 'season']).agg(available_aggs).reset_index()
    season_df = season_df.rename(columns={'week': 'games_played'})

    # Calculate rate stats
    if 'attempts' in season_df.columns and 'completions' in season_df.columns:
        season_df['completion_pct'] = (season_df['completions'] / season_df['attempts'].replace(0, np.nan) * 100).fillna(0)

    if 'targets' in season_df.columns and 'receptions' in season_df.columns:
        season_df['catch_rate'] = (season_df['receptions'] / season_df['targets'].replace(0, np.nan) * 100).fillna(0)

    if 'carries' in season_df.columns and 'rushing_yards' in season_df.columns:
        season_df['yards_per_carry'] = (season_df['rushing_yards'] / season_df['carries'].replace(0, np.nan)).fillna(0)

    if 'targets' in season_df.columns and 'receiving_yards' in season_df.columns:
        season_df['yards_per_target'] = (season_df['receiving_yards'] / season_df['targets'].replace(0, np.nan)).fillna(0)

    if 'fantasy_points_ppr' in season_df.columns and 'games_played' in season_df.columns:
        season_df['ppg'] = (season_df['fantasy_points_ppr'] / season_df['games_played'].replace(0, np.nan)).fillna(0)

    # Fill NaN
    numeric_cols = season_df.select_dtypes(include=[np.number]).columns
    season_df[numeric_cols] = season_df[numeric_cols].fillna(0)

    with driver.session() as session:
        # Create constraint
        try:
            session.run("CREATE CONSTRAINT season_stats_unique IF NOT EXISTS FOR (s:SeasonStats) REQUIRE (s.player_id, s.season) IS UNIQUE")
        except:
            pass

        batch_size = 500
        records = season_df.to_dict('records')

        for i in range(0, len(records), batch_size):
            batch = records[i:i+batch_size]

            session.run("""
                UNWIND $batch AS row
                MERGE (s:SeasonStats {
                    player_id: row.player_id,
                    season: toInteger(row.season)
                })
                SET s.player_name = row.player_name,
                    s.position = row.position,
                    s.games_played = toInteger(row.games_played),
                    s.completions = toFloat(row.completions),
                    s.attempts = toFloat(row.attempts),
                    s.passing_yards = toFloat(row.passing_yards),
                    s.passing_tds = toFloat(row.passing_tds),
                    s.interceptions = toFloat(row.interceptions),
                    s.carries = toFloat(row.carries),
                    s.rushing_yards = toFloat(row.rushing_yards),
                    s.rushing_tds = toFloat(row.rushing_tds),
                    s.receptions = toFloat(row.receptions),
                    s.targets = toFloat(row.targets),
                    s.receiving_yards = toFloat(row.receiving_yards),
                    s.receiving_tds = toFloat(row.receiving_tds),
                    s.fantasy_points = toFloat(row.fantasy_points),
                    s.fantasy_points_ppr = toFloat(row.fantasy_points_ppr),
                    s.completion_pct = toFloat(row.completion_pct),
                    s.catch_rate = toFloat(row.catch_rate),
                    s.yards_per_carry = toFloat(row.yards_per_carry),
                    s.yards_per_target = toFloat(row.yards_per_target),
                    s.ppg = toFloat(row.ppg),
                    s.updated_at = datetime()

                WITH s, row
                MATCH (p:Player)
                WHERE p.gsis_id = row.player_id OR p.name = row.player_name
                MERGE (p)-[:HAS_SEASON_STATS]->(s)
            """, {'batch': batch})

            print(f"  Processed {min(i+batch_size, len(records)):,}/{len(records):,} season records")

    print(f"Created {len(records):,} SeasonStats nodes")


def create_career_stats(driver):
    """Create career totals from season stats."""
    print("\nCalculating career stats...")

    with driver.session() as session:
        # Aggregate all seasons into career stats on Player node
        session.run("""
            MATCH (p:Player)-[:HAS_SEASON_STATS]->(s:SeasonStats)
            WITH p,
                 sum(s.games_played) as career_games,
                 sum(s.fantasy_points_ppr) as career_fpts_ppr,
                 sum(s.passing_yards) as career_passing_yards,
                 sum(s.passing_tds) as career_passing_tds,
                 sum(s.rushing_yards) as career_rushing_yards,
                 sum(s.rushing_tds) as career_rushing_tds,
                 sum(s.receiving_yards) as career_receiving_yards,
                 sum(s.receiving_tds) as career_receiving_tds,
                 sum(s.receptions) as career_receptions,
                 count(s) as seasons_played
            SET p.career_games = career_games,
                p.career_fpts_ppr = career_fpts_ppr,
                p.career_passing_yards = career_passing_yards,
                p.career_passing_tds = career_passing_tds,
                p.career_rushing_yards = career_rushing_yards,
                p.career_rushing_tds = career_rushing_tds,
                p.career_receiving_yards = career_receiving_yards,
                p.career_receiving_tds = career_receiving_tds,
                p.career_receptions = career_receptions,
                p.seasons_played = seasons_played,
                p.career_ppg = CASE WHEN career_games > 0 THEN career_fpts_ppr / career_games ELSE 0 END
        """)

    print("Career stats updated on Player nodes")


def main():
    """Main entry point."""
    print("=" * 60)
    print("NFLVERSE HISTORICAL STATS LOADER")
    print(f"Started: {datetime.now()}")
    print("=" * 60)

    driver = get_driver()

    try:
        # Fetch stats for all available years (2010-2024)
        years = list(range(2010, 2025))
        df = fetch_player_stats(years)

        # Create nodes
        create_weekly_stats(driver, df)
        create_season_stats(driver, df)
        create_career_stats(driver)

        print("\n" + "=" * 60)
        print("LOAD COMPLETE")
        print("=" * 60)

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
    finally:
        driver.close()


if __name__ == "__main__":
    main()
