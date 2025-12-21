#!/usr/bin/env python3
"""
Fix player team data by re-importing from nflverse.

This script updates the 'team' property on Player nodes using
the 'latest_team' field from nflverse data.

Uses HTTP Transaction API for Railway Neo4j compatibility.
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
import nflreadpy as nfl
from dotenv import load_dotenv

load_dotenv()

# Neo4j HTTP connection (Railway)
NEO4J_URL = os.getenv("NEO4J_URL", "https://sparkling-commitment-production.up.railway.app/db/neo4j/tx/commit")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "dynastyedge2025")


def execute_query(query: str, parameters: dict = None) -> list[dict]:
    """Execute a Cypher query via HTTP Transaction API."""
    statement = {"statement": query}
    if parameters:
        statement["parameters"] = parameters

    response = httpx.post(
        NEO4J_URL,
        json={"statements": [statement]},
        auth=(NEO4J_USER, NEO4J_PASSWORD),
        headers={"Content-Type": "application/json"},
        timeout=60.0,
    )
    response.raise_for_status()
    data = response.json()

    # Check for Neo4j errors
    if data.get("errors"):
        error = data["errors"][0]
        raise Exception(f"Neo4j error: {error.get('message', 'Unknown error')}")

    # Parse results into list of dicts
    results = []
    if data.get("results") and data["results"][0].get("data"):
        columns = data["results"][0]["columns"]
        for row_data in data["results"][0]["data"]:
            row = row_data["row"]
            results.append(dict(zip(columns, row)))

    return results


def fetch_nflverse_teams():
    """Fetch current team data from nflverse."""
    print("📊 Fetching player data from nflverse...")
    players = nfl.load_players()
    df = players.to_pandas()

    # Filter to active/reserve status and skill positions
    df = df[df['status'].isin(['ACT', 'RES', 'INA', 'PUP', 'NFI'])]
    df = df[df['position'].isin(['QB', 'RB', 'WR', 'TE'])]

    # Create mapping of gsis_id -> latest_team
    team_map = dict(zip(df['gsis_id'], df['latest_team']))
    print(f"   ✅ Found {len(team_map)} players with team data")
    return team_map


def update_player_teams(team_map, dry_run=False):
    """Update player teams in Neo4j."""
    print(f"\n{'🔍 DRY RUN - ' if dry_run else ''}Updating player teams in Neo4j...")

    # First, check current state
    results = execute_query("""
        MATCH (p:Player)
        WHERE p.gsis_id IS NOT NULL AND p.ktc_value IS NOT NULL
        RETURN p.gsis_id as gsis_id, p.name as name, p.team as current_team
        ORDER BY p.ktc_value DESC
        LIMIT 10
    """)

    print("\n📋 Current teams for top 10 players (before update):")
    for record in results:
        correct_team = team_map.get(record["gsis_id"], "N/A")
        status = "✅" if record["current_team"] == correct_team else "❌"
        print(f"   {status} {record['name']}: {record['current_team']} -> {correct_team}")

    if dry_run:
        print("\n🔍 DRY RUN complete. No changes made.")
        return 0

    # Update teams in batches
    updated = 0
    batch_size = 100
    items = [(gid, team) for gid, team in team_map.items() if team]

    for i in range(0, len(items), batch_size):
        batch = items[i:i+batch_size]
        batch_params = [{"gsis_id": gid, "team": team} for gid, team in batch]

        result = execute_query("""
            UNWIND $batch AS item
            MATCH (p:Player {gsis_id: item.gsis_id})
            SET p.team = item.team
            RETURN count(p) as updated
        """, {"batch": batch_params})

        if result:
            updated += result[0]["updated"]

        if (i // batch_size) % 10 == 0:
            print(f"   Processed {min(i + batch_size, len(items))}/{len(items)} players...")

    print(f"\n✅ Updated {updated} player teams")
    return updated


def verify_updates():
    """Verify the updates were applied correctly."""
    print("\n🔍 Verifying updates...")

    # Check specific players
    results = execute_query("""
        MATCH (p:Player)
        WHERE p.name IN ['Josh Allen', 'Lamar Jackson', 'CeeDee Lamb', 'Ja\\'Marr Chase']
        AND p.position IN ['QB', 'WR']
        RETURN p.name as name, p.position as pos, p.team as team
        ORDER BY p.ktc_value DESC
    """)

    print("📋 Sample verification:")
    expected = {
        "Josh Allen": "BUF",
        "Lamar Jackson": "BAL",
        "CeeDee Lamb": "DAL",
        "Ja'Marr Chase": "CIN"
    }
    for record in results:
        expected_team = expected.get(record['name'], '?')
        status = "✅" if record['team'] == expected_team else "❌"
        print(f"   {status} {record['name']} ({record['pos']}): {record['team']}")

    # Check team distribution
    results = execute_query("""
        MATCH (p:Player)
        WHERE p.ktc_value IS NOT NULL
        RETURN p.team as team, count(p) as count
        ORDER BY count DESC
        LIMIT 15
    """)

    print("\n📊 Team distribution (top 15):")
    for record in results:
        print(f"   {record['team']}: {record['count']} players")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Fix player team data from nflverse")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without updating")
    args = parser.parse_args()

    print("=" * 60)
    print("Fix Player Teams from nflverse")
    print("=" * 60)

    # Fetch nflverse data
    team_map = fetch_nflverse_teams()

    # Update teams
    update_player_teams(team_map, dry_run=args.dry_run)

    # Verify if not dry run
    if not args.dry_run:
        verify_updates()

    print("\n✅ Done!")


if __name__ == "__main__":
    main()
