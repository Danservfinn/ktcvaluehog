#!/usr/bin/env python3
"""Dynasty Edge - Initial Data Load Pipeline.

Loads all data sources into Neo4j and creates the feature store.

Usage:
    python pipelines/initial_load.py
    python pipelines/initial_load.py --seasons 2024 2025
    python pipelines/initial_load.py --skip-neo4j
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import CURRENT_SEASON, HISTORICAL_SEASONS, FEATURES_DIR
from src.loaders.nflverse_loader import NFLverseLoader
from src.loaders.id_resolver import IDResolver
from src.features.feature_store import FeatureStore
from src.features.ftn_features import aggregate_ftn_features, join_ftn_to_stats
from src.database.neo4j_client import Neo4jClient
from src.database.schema import create_schema, NODE_TEMPLATES, RELATIONSHIP_TEMPLATES
from src.api.sleeper_client import SleeperClient


def load_nflverse_data(loader: NFLverseLoader, seasons: list) -> dict:
    """Load all NFLverse data."""
    print("\n" + "=" * 70)
    print("PHASE 1: Loading NFLverse Data")
    print("=" * 70)

    data = {}

    # Core data
    print("\n[1/8] Loading core player data...")
    data['players'] = loader.load_players()
    print(f"       Loaded {len(data['players']):,} players")

    print("\n[2/8] Loading player ID mappings...")
    data['player_ids'] = loader.load_ff_playerids()
    print(f"       Loaded {len(data['player_ids']):,} ID mappings")

    print("\n[3/8] Loading rosters...")
    data['rosters'] = loader.load_rosters(seasons)
    print(f"       Loaded {len(data['rosters']):,} roster entries")

    # Statistics
    print("\n[4/8] Loading player statistics...")
    data['player_stats'] = loader.load_player_stats(seasons, 'week')
    print(f"       Loaded {len(data['player_stats']):,} player-week records")

    print("\n[5/8] Loading teams...")
    data['teams'] = loader.load_teams()
    print(f"       Loaded {len(data['teams']):,} teams")

    # Historical data
    print("\n[6/8] Loading draft history...")
    data['draft_picks'] = loader.load_draft_picks()
    print(f"       Loaded {len(data['draft_picks']):,} draft picks")

    print("\n[7/8] Loading combine data...")
    data['combine'] = loader.load_combine()
    print(f"       Loaded {len(data['combine']):,} combine records")

    print("\n[8/8] Loading schedules...")
    data['schedules'] = loader.load_schedules(seasons)
    print(f"       Loaded {len(data['schedules']):,} games")

    return data


def load_advanced_analytics(loader: NFLverseLoader, seasons: list) -> dict:
    """Load advanced analytics data."""
    print("\n" + "=" * 70)
    print("PHASE 2: Loading Advanced Analytics")
    print("=" * 70)

    data = {}

    print("\n[1/4] Loading Next Gen Stats (passing)...")
    try:
        data['ngs_passing'] = loader.load_nextgen_stats(seasons, 'passing')
        print(f"       Loaded {len(data['ngs_passing']):,} records")
    except Exception as e:
        print(f"       Warning: {e}")
        data['ngs_passing'] = None

    print("\n[2/4] Loading Next Gen Stats (receiving)...")
    try:
        data['ngs_receiving'] = loader.load_nextgen_stats(seasons, 'receiving')
        print(f"       Loaded {len(data['ngs_receiving']):,} records")
    except Exception as e:
        print(f"       Warning: {e}")
        data['ngs_receiving'] = None

    print("\n[3/4] Loading PFR advanced stats...")
    try:
        data['pfr_rec'] = loader.load_pfr_advstats(seasons, 'rec')
        print(f"       Loaded {len(data['pfr_rec']):,} receiving records")
    except Exception as e:
        print(f"       Warning: {e}")
        data['pfr_rec'] = None

    print("\n[4/4] Loading FTN charting data...")
    try:
        data['ftn'] = loader.load_ftn_charting(seasons)
        print(f"       Loaded {len(data['ftn']):,} charting records")
    except Exception as e:
        print(f"       Warning: {e}")
        data['ftn'] = None

    return data


def load_to_neo4j(client: Neo4jClient, data: dict, advanced: dict) -> None:
    """Load data into Neo4j graph database."""
    print("\n" + "=" * 70)
    print("PHASE 3: Loading into Neo4j")
    print("=" * 70)

    # Create schema
    print("\n[1/6] Creating schema...")
    schema_result = create_schema(client)
    print(f"       Created {schema_result['created']} constraints/indexes")
    if schema_result['errors']:
        for err in schema_result['errors'][:3]:
            print(f"       Warning: {err}")

    # Load teams
    print("\n[2/6] Loading teams...")
    teams_loaded = 0
    for _, team in data['teams'].iterrows():
        try:
            client.run_write("""
                MERGE (t:Team {team_abbr: $abbr})
                SET t.team_name = $name,
                    t.team_nick = $nick,
                    t.conference = $conf,
                    t.division = $div
            """, {
                'abbr': team.get('team_abbr'),
                'name': team.get('team_name'),
                'nick': team.get('team_nick'),
                'conf': team.get('team_conf'),
                'div': team.get('team_division')
            })
            teams_loaded += 1
        except Exception as e:
            continue
    print(f"       Loaded {teams_loaded} teams")

    # Load players
    print("\n[3/6] Loading players...")
    players_loaded = 0
    players_df = data['players']
    combine_df = data['combine']

    # Merge combine data
    if 'pfr_id' in players_df.columns and len(combine_df) > 0:
        players_df = players_df.merge(
            combine_df[['pfr_id', 'forty', 'bench', 'vertical', 'broad_jump', 'three_cone']],
            on='pfr_id',
            how='left'
        )

    # Filter to skill positions
    skill_positions = ['QB', 'RB', 'WR', 'TE']
    players_df = players_df[players_df['position'].isin(skill_positions)]

    for _, player in players_df.iterrows():
        gsis_id = player.get('gsis_id')
        if not gsis_id or str(gsis_id) == 'nan':
            continue

        try:
            client.run_write("""
                MERGE (p:Player {gsis_id: $gsis_id})
                SET p.name = $name,
                    p.display_name = $display_name,
                    p.position = $position,
                    p.current_team = $team,
                    p.birth_date = $birth_date,
                    p.height = $height,
                    p.weight = $weight,
                    p.college = $college,
                    p.forty_time = $forty,
                    p.vertical_jump = $vertical,
                    p.updated_at = datetime()
            """, {
                'gsis_id': str(gsis_id),
                'name': player.get('display_name', player.get('name')),
                'display_name': player.get('display_name'),
                'position': player.get('position'),
                'team': player.get('team'),
                'birth_date': str(player.get('birth_date')) if player.get('birth_date') else None,
                'height': int(player['height']) if player.get('height') and str(player.get('height')) != 'nan' else None,
                'weight': int(player['weight']) if player.get('weight') and str(player.get('weight')) != 'nan' else None,
                'college': player.get('college'),
                'forty': float(player['forty']) if player.get('forty') and str(player.get('forty')) != 'nan' else None,
                'vertical': float(player['vertical']) if player.get('vertical') and str(player.get('vertical')) != 'nan' else None
            })
            players_loaded += 1
        except Exception as e:
            continue

    print(f"       Loaded {players_loaded} players")

    # Create PLAYS_FOR relationships
    print("\n[4/6] Creating team relationships...")
    try:
        result = client.run_query("""
            MATCH (p:Player), (t:Team)
            WHERE p.current_team = t.team_abbr
            MERGE (p)-[r:PLAYS_FOR]->(t)
            SET r.season = 2025
            RETURN count(r) as count
        """)
        rel_count = result[0]['count'] if result else 0
        print(f"       Created {rel_count} PLAYS_FOR relationships")
    except Exception as e:
        print(f"       Warning: {e}")

    # Create COMPETES_WITH relationships
    print("\n[5/6] Creating competition relationships...")
    try:
        result = client.run_query("""
            MATCH (p1:Player)-[:PLAYS_FOR]->(t:Team)<-[:PLAYS_FOR]-(p2:Player)
            WHERE p1.position = p2.position
              AND p1.gsis_id < p2.gsis_id
              AND p1.position IN ['RB', 'WR', 'TE']
            MERGE (p1)-[r:COMPETES_WITH]->(p2)
            SET r.team_abbr = t.team_abbr,
                r.season = 2025,
                r.position = p1.position
            RETURN count(r) as count
        """)
        rel_count = result[0]['count'] if result else 0
        print(f"       Created {rel_count} COMPETES_WITH relationships")
    except Exception as e:
        print(f"       Warning: {e}")

    # Create TARGETS_FROM relationships
    print("\n[6/6] Creating target relationships...")
    try:
        result = client.run_query("""
            MATCH (rec:Player)-[:PLAYS_FOR]->(t:Team)<-[:PLAYS_FOR]-(qb:Player)
            WHERE rec.position IN ['WR', 'TE']
              AND qb.position = 'QB'
            MERGE (rec)-[r:TARGETS_FROM]->(qb)
            SET r.team_abbr = t.team_abbr,
                r.season = 2025
            RETURN count(r) as count
        """)
        rel_count = result[0]['count'] if result else 0
        print(f"       Created {rel_count} TARGETS_FROM relationships")
    except Exception as e:
        print(f"       Warning: {e}")


def build_feature_store(data: dict, advanced: dict, store: FeatureStore) -> None:
    """Build and save feature store."""
    print("\n" + "=" * 70)
    print("PHASE 4: Building Feature Store")
    print("=" * 70)

    import pandas as pd

    # Save raw player data
    print("\n[1/5] Saving player core features...")
    players_df = data['players']
    if 'position' in players_df.columns:
        players_df = players_df[players_df['position'].isin(['QB', 'RB', 'WR', 'TE'])]
    store.save(players_df, 'player_core')

    # Save player stats
    print("\n[2/5] Saving player statistics...")
    stats_df = data['player_stats']
    if 'position' in stats_df.columns:
        stats_df = stats_df[stats_df['position'].isin(['QB', 'RB', 'WR', 'TE'])]
    store.save(stats_df, 'player_stats_weekly')

    # Aggregate to season level
    print("\n[3/5] Aggregating season statistics...")
    if len(stats_df) > 0:
        agg_cols = {
            'fantasy_points_ppr': 'sum',
            'targets': 'sum',
            'receptions': 'sum',
            'receiving_yards': 'sum',
            'receiving_tds': 'sum',
            'carries': 'sum',
            'rushing_yards': 'sum',
            'rushing_tds': 'sum',
            'passing_yards': 'sum',
            'passing_tds': 'sum',
            'week': 'count'
        }
        available_agg = {k: v for k, v in agg_cols.items() if k in stats_df.columns}

        group_cols = ['player_id', 'season']
        if 'player_display_name' in stats_df.columns:
            available_agg['player_display_name'] = 'first'
        if 'position' in stats_df.columns:
            available_agg['position'] = 'first'

        season_stats = stats_df.groupby(group_cols).agg(available_agg).reset_index()
        season_stats = season_stats.rename(columns={'week': 'games_played'})

        if 'fantasy_points_ppr' in season_stats.columns and 'games_played' in season_stats.columns:
            season_stats['ppg'] = season_stats['fantasy_points_ppr'] / season_stats['games_played']

        store.save(season_stats, 'player_stats_season')

    # Process FTN features if available
    print("\n[4/5] Processing FTN features...")
    if advanced.get('ftn') is not None and len(advanced['ftn']) > 0:
        ftn_features = aggregate_ftn_features(advanced['ftn'])
        for ftn_type, ftn_df in ftn_features.items():
            if len(ftn_df) > 0:
                store.save(ftn_df, f'ftn_features_{ftn_type}')
                print(f"       Saved {len(ftn_df)} FTN {ftn_type} records")
    else:
        print("       FTN data not available")

    # Save ID mappings
    print("\n[5/5] Saving ID mappings...")
    store.save(data['player_ids'], 'player_id_mappings')

    print("\nFeature store build complete.")


def load_sleeper_data(client: SleeperClient, neo4j_client: Neo4jClient = None) -> dict:
    """Load Sleeper league data."""
    print("\n" + "=" * 70)
    print("PHASE 5: Loading Sleeper Data")
    print("=" * 70)

    if not client.league_id:
        print("No Sleeper league ID configured. Skipping.")
        return {}

    data = {}

    print("\n[1/3] Loading league info...")
    try:
        data['league'] = client.get_league()
        print(f"       League: {data['league'].get('name')}")
    except Exception as e:
        print(f"       Warning: {e}")
        return data

    print("\n[2/3] Loading rosters...")
    try:
        data['rosters'] = client.rosters_to_dataframe()
        print(f"       Loaded {len(data['rosters'])} rostered players")
    except Exception as e:
        print(f"       Warning: {e}")

    print("\n[3/3] Loading traded picks...")
    try:
        data['traded_picks'] = client.get_traded_picks()
        print(f"       Loaded {len(data['traded_picks'])} traded picks")
    except Exception as e:
        print(f"       Warning: {e}")

    return data


def main():
    parser = argparse.ArgumentParser(description='Dynasty Edge Initial Data Load')
    parser.add_argument('--seasons', nargs='+', type=int, default=[CURRENT_SEASON],
                        help='Seasons to load (default: current season)')
    parser.add_argument('--skip-neo4j', action='store_true',
                        help='Skip Neo4j loading')
    parser.add_argument('--skip-sleeper', action='store_true',
                        help='Skip Sleeper data')
    parser.add_argument('--skip-advanced', action='store_true',
                        help='Skip advanced analytics (NGS, PFR, FTN)')

    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("DYNASTY EDGE - INITIAL DATA LOAD")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Seasons: {args.seasons}")
    print("=" * 70)

    # Initialize components
    loader = NFLverseLoader()
    store = FeatureStore()

    # Load NFLverse data
    data = load_nflverse_data(loader, args.seasons)

    # Load advanced analytics
    advanced = {}
    if not args.skip_advanced:
        advanced = load_advanced_analytics(loader, args.seasons)

    # Load to Neo4j
    if not args.skip_neo4j:
        try:
            neo4j_client = Neo4jClient()
            if neo4j_client.verify_connection():
                load_to_neo4j(neo4j_client, data, advanced)
                neo4j_client.close()
            else:
                print("\nNeo4j connection failed. Skipping database load.")
        except Exception as e:
            print(f"\nNeo4j error: {e}")
            print("Skipping database load.")

    # Build feature store
    build_feature_store(data, advanced, store)

    # Load Sleeper data
    if not args.skip_sleeper:
        try:
            sleeper = SleeperClient()
            sleeper_data = load_sleeper_data(sleeper)
        except Exception as e:
            print(f"\nSleeper error: {e}")

    # Print summary
    print("\n" + "=" * 70)
    print("LOAD COMPLETE")
    print("=" * 70)

    print("\nFeature files created:")
    for f in store.list_features():
        print(f"  - {f['name']}: {f.get('rows', 'N/A'):,} rows, {f.get('size_mb', 0):.1f} MB")

    print("\nNext steps:")
    print("  1. Run 'python pipelines/daily_refresh.py' for updates")
    print("  2. Run 'python dashboard.py' to start the dashboard")
    print("  3. Run 'python dynasty_agent.py' for AI analysis")


if __name__ == "__main__":
    main()
