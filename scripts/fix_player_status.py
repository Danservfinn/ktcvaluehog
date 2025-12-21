#!/usr/bin/env python3
"""
Fix player status data and clean up duplicates.

1. Import status field from nflverse (ACT, RET, etc.)
2. Mark retired players as inactive
3. Clean up duplicate records without gsis_id
"""

import httpx
import nflreadpy as nfl
from datetime import datetime

# Neo4j HTTP connection (Railway)
NEO4J_URL = "https://sparkling-commitment-production.up.railway.app/db/neo4j/tx/commit"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "dynastyedge2025"


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
        timeout=120.0,
    )
    response.raise_for_status()
    data = response.json()

    if data.get("errors"):
        error = data["errors"][0]
        raise Exception(f"Neo4j error: {error.get('message', 'Unknown error')}")

    results = []
    if data.get("results") and data["results"][0].get("data"):
        columns = data["results"][0]["columns"]
        for row_data in data["results"][0]["data"]:
            results.append(dict(zip(columns, row_data["row"])))

    return results


def fetch_nflverse_status():
    """Fetch player status from nflverse."""
    print("📊 Fetching player status from nflverse...")
    players = nfl.load_players()
    df = players.to_pandas()

    # Known retired players (nflverse data may be stale)
    KNOWN_RETIRED = {
        '00-0022942': 'Philip Rivers',      # Retired Jan 2021
        '00-0019596': 'Tom Brady',          # Retired Feb 2023
        '00-0023997': 'Ben Roethlisberger', # Retired Jan 2022
        '00-0022924': 'Drew Brees',         # Retired Mar 2021
        '00-0027793': 'Andrew Luck',        # Retired Aug 2019
        '00-0031381': 'Rob Gronkowski',     # Retired Jun 2022
        '00-0026498': 'Larry Fitzgerald',   # Retired unofficially
        '00-0026143': 'Antonio Brown',      # Effectively retired
    }

    # Create mapping of gsis_id -> (status, latest_team, is_active)
    # Determine is_active based on:
    # - Known retired → retired
    # - status = 'RET' → retired
    # - last_season < 2023 → likely retired/inactive
    # - status in ['ACT', 'RES', 'PUP', 'NFI'] AND last_season >= 2023 → active
    status_map = {}
    for _, row in df.iterrows():
        gsis_id = row.get('gsis_id')
        if gsis_id:
            status = row.get('status')
            last_season = row.get('last_season')

            # Determine if truly active
            if gsis_id in KNOWN_RETIRED:
                is_active = False
                status = 'RET'  # Override status
            elif status == 'RET':
                is_active = False
            elif last_season and last_season < 2023:
                # Haven't played since 2022 or earlier - likely retired
                is_active = False
            elif status in ['ACT', 'RES', 'PUP', 'NFI', 'INA']:
                is_active = True
            else:
                is_active = False

            status_map[gsis_id] = {
                'status': status,
                'team': row.get('latest_team'),
                'last_season': last_season,
                'is_active': is_active,
            }

    # Count active vs inactive
    active_count = sum(1 for v in status_map.values() if v['is_active'])
    print(f"   ✅ Found {len(status_map)} players ({active_count} active, {len(status_map) - active_count} inactive)")
    return status_map


def update_player_status(status_map, dry_run=False):
    """Update player status in Neo4j."""
    print(f"\n{'🔍 DRY RUN - ' if dry_run else ''}Updating player status...")

    # Check current state
    results = execute_query("""
        MATCH (p:Player)
        WHERE p.name IN ['Philip Rivers', 'Tom Brady', 'Ben Roethlisberger']
        RETURN p.name as name, p.gsis_id as gsis_id, p.status as status, p.team as team
    """)

    print("\n📋 Retired players before update:")
    for r in results:
        info = status_map.get(r['gsis_id'], {})
        is_active = info.get('is_active', 'N/A')
        last_season = info.get('last_season', 'N/A')
        print(f"   {r['name']}: is_active={is_active} (last_season={last_season})")

    if dry_run:
        print("\n🔍 DRY RUN complete. No changes made.")
        return 0

    # Update status in batches
    updated = 0
    batch_size = 100
    items = [(gid, info['status'], info.get('is_active', False))
             for gid, info in status_map.items() if info.get('status')]

    for i in range(0, len(items), batch_size):
        batch = items[i:i+batch_size]
        batch_params = [{"gsis_id": gid, "status": status, "is_active": is_active}
                        for gid, status, is_active in batch]

        result = execute_query("""
            UNWIND $batch AS item
            MATCH (p:Player {gsis_id: item.gsis_id})
            SET p.status = item.status,
                p.is_active = item.is_active
            RETURN count(p) as updated
        """, {"batch": batch_params})

        if result:
            updated += result[0]["updated"]

        if (i // batch_size) % 10 == 0:
            print(f"   Processed {min(i + batch_size, len(items))}/{len(items)} players...")

    print(f"\n✅ Updated {updated} player statuses")
    return updated


def clean_duplicate_players(dry_run=False):
    """Remove duplicate players without gsis_id."""
    print(f"\n{'🔍 DRY RUN - ' if dry_run else ''}Cleaning duplicate players...")

    # Find duplicates without gsis_id
    dupes = execute_query("""
        MATCH (p:Player)
        WHERE p.gsis_id IS NULL AND p.ktc_value IS NOT NULL
        RETURN p.name as name, count(*) as cnt
        ORDER BY cnt DESC
        LIMIT 20
    """)

    print("\n📋 Players without gsis_id (duplicates):")
    for d in dupes:
        print(f"   {d['name']}: {d['cnt']} records")

    if dry_run:
        print("\n🔍 DRY RUN complete. No deletions made.")
        return 0

    # Delete duplicates - keep players that have a gsis_id
    # For players without gsis_id, delete all but one
    result = execute_query("""
        MATCH (p:Player)
        WHERE p.gsis_id IS NULL
        WITH p.name as name, collect(p) as dupes
        WHERE size(dupes) > 1
        UNWIND tail(dupes) as dupe
        DETACH DELETE dupe
        RETURN count(*) as deleted
    """)

    deleted = result[0]["deleted"] if result else 0
    print(f"\n✅ Deleted {deleted} duplicate records")
    return deleted


def fix_metchie_team():
    """Fix John Metchie team assignment."""
    print("\n🔧 Fixing John Metchie team...")

    # John Metchie III plays for Houston Texans
    result = execute_query("""
        MATCH (p:Player)
        WHERE p.name CONTAINS 'Metchie'
        SET p.team = 'HOU'
        RETURN p.name as name, p.team as team
    """)

    for r in result:
        print(f"   Fixed: {r['name']} -> {r['team']}")


def verify_fixes():
    """Verify the fixes were applied."""
    print("\n🔍 Verifying fixes...")

    # Check retired players
    results = execute_query("""
        MATCH (p:Player)
        WHERE p.name IN ['Philip Rivers', 'Tom Brady', 'Ben Roethlisberger']
        RETURN p.name as name, p.status as status, p.is_active as is_active, p.team as team
    """)

    print("\n📋 Retired players status:")
    for r in results:
        status = "✅" if r['is_active'] == False else "❌"
        print(f"   {status} {r['name']}: status={r['status']}, is_active={r['is_active']}")

    # Check Metchie
    results = execute_query("""
        MATCH (p:Player)
        WHERE p.name CONTAINS 'Metchie'
        RETURN p.name as name, p.team as team, p.gsis_id as id
    """)

    print("\n📋 John Metchie records:")
    for r in results:
        print(f"   {r['name']}: team={r['team']}, id={r['id']}")

    # Count remaining duplicates
    results = execute_query("""
        MATCH (p:Player)
        WHERE p.gsis_id IS NULL AND p.ktc_value IS NOT NULL
        RETURN count(p) as orphans
    """)

    orphans = results[0]["orphans"] if results else 0
    print(f"\n📊 Remaining players without gsis_id: {orphans}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Fix player status and duplicates")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without updating")
    args = parser.parse_args()

    print("=" * 60)
    print("Fix Player Status and Duplicates")
    print("=" * 60)

    # Fetch nflverse status
    status_map = fetch_nflverse_status()

    # Update status
    update_player_status(status_map, dry_run=args.dry_run)

    # Clean duplicates
    clean_duplicate_players(dry_run=args.dry_run)

    # Fix Metchie
    if not args.dry_run:
        fix_metchie_team()

    # Verify
    if not args.dry_run:
        verify_fixes()

    print("\n✅ Done!")


if __name__ == "__main__":
    main()
