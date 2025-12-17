"""
Fetch historical KTC values from KeepTradeCut.
Based on methodology from: https://github.com/jrioross/dynasty_fantasy_football_ktc

Data sources:
1. KTC dynasty rankings page (BeautifulSoup scraping)
2. KTC player pages for historical value charts
3. Daily snapshots stored in Neo4j

The jrioross repo doesn't store the actual data files in GitHub
(they're gitignored), so we replicate their scraping methodology.
"""

import requests
import pandas as pd
import numpy as np
from neo4j import GraphDatabase
from datetime import datetime, timedelta
import time
import json
import os
import re
import warnings
warnings.filterwarnings('ignore')

# Disable SSL warnings for scraping
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    print("Warning: BeautifulSoup not installed. Run: pip install beautifulsoup4")


CACHE_DIR = "/Users/kurultai/ktcvaluehog/data/ktc_history"
os.makedirs(CACHE_DIR, exist_ok=True)


def get_driver():
    """Get Neo4j driver."""
    return GraphDatabase.driver("bolt://localhost:7687", auth=None)


def fetch_ktc_rankings_bs4():
    """
    Fetch current KTC rankings using BeautifulSoup scraping.
    Based on jrioross/dynasty_fantasy_football_ktc methodology.
    """
    if not BS4_AVAILABLE:
        print("   ⚠️ BeautifulSoup not available, falling back to API method")
        return fetch_ktc_rankings_api()

    print("\n📊 Fetching KTC rankings (BeautifulSoup method)...")

    # URL from jrioross repo - includes all skill positions in superflex format
    base_url = "https://keeptradecut.com/dynasty-rankings"
    params = "?page={}&filters=QB|WR|RB|TE|RDP&format=2"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }

    all_players = []
    page = 0

    while True:
        url = base_url + params.format(page)

        try:
            response = requests.get(url, headers=headers, timeout=30, verify=False)

            if response.status_code != 200:
                break

            soup = BeautifulSoup(response.content, 'html.parser')
            player_divs = soup.find_all('div', class_='onePlayer')

            if not player_divs:
                break

            for div in player_divs:
                try:
                    # Rank
                    rank_elem = div.find('p', class_='rank-number')
                    rank = int(rank_elem.text.strip()) if rank_elem else None

                    # Player name and href
                    name_link = div.find('a')
                    name = name_link.text.strip() if name_link else None
                    href = name_link.get('href', '') if name_link else ''

                    # Extract player ID from href
                    # Format: /dynasty-rankings/players/player-name-365
                    # The number at the end is the ktc_id
                    ktc_id = None
                    if href:
                        # Try to extract number at end of URL
                        match = re.search(r'-(\d+)$', href)
                        if match:
                            ktc_id = int(match.group(1))
                        else:
                            # Fallback: try to find any number
                            match = re.search(r'/(\d+)/', href)
                            if match:
                                ktc_id = int(match.group(1))

                    # Position rank
                    pos_elem = div.find('p', class_='position')
                    pos_rank = pos_elem.text.strip() if pos_elem else None
                    position = pos_rank[:2] if pos_rank else None

                    # Team
                    team_elem = div.find('span', class_='player-team')
                    team = team_elem.text.strip() if team_elem else None

                    # Age
                    info_div = div.find('div', class_='player-info')
                    if info_div:
                        age_spans = info_div.find_all('span')
                        age = None
                        for span in age_spans:
                            if not span.get('class'):
                                age_text = span.text.strip()
                                if 'years old' in age_text.lower():
                                    age_match = re.search(r'(\d+\.?\d*)', age_text)
                                    if age_match:
                                        age = float(age_match.group(1))
                                        break
                    else:
                        age = None

                    # Value
                    value_elem = div.find('div', class_='value')
                    value = None
                    if value_elem:
                        value_text = value_elem.text.strip().replace(',', '')
                        if value_text.isdigit():
                            value = int(value_text)

                    if name and value:
                        all_players.append({
                            'ktc_id': ktc_id,
                            'name': name,
                            'position': position,
                            'team': team,
                            'age': age,
                            'ktc_value': value,
                            'rank': rank,
                            'position_rank': pos_rank,
                            'href': href,
                        })

                except Exception as e:
                    continue

            print(f"   Page {page}: Found {len(player_divs)} players")
            page += 1
            time.sleep(0.5)  # Rate limiting

            if page > 20:  # Safety limit
                break

        except Exception as e:
            print(f"   Error on page {page}: {e}")
            break

    if all_players:
        df = pd.DataFrame(all_players)
        print(f"   ✅ Scraped {len(df)} players total")
        return df

    return None


def fetch_ktc_rankings_api():
    """
    Fetch current KTC rankings from the API (fallback method).
    """
    print("\n📊 Fetching KTC rankings (API method)...")

    url = "https://keeptradecut.com/api/v1/players?format=json"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'application/json',
    }

    try:
        response = requests.get(url, headers=headers, timeout=30, verify=False)

        if response.status_code == 200:
            data = response.json()

            players = []
            for p in data:
                players.append({
                    'ktc_id': p.get('playerID'),
                    'name': p.get('playerName'),
                    'position': p.get('position'),
                    'team': p.get('team'),
                    'ktc_value': p.get('superflexValue', 0) or p.get('value', 0),
                    'ktc_value_1qb': p.get('oneQBValue', 0),
                    'age': p.get('age'),
                    'rank': p.get('superflexRank') or p.get('rank'),
                })

            df = pd.DataFrame(players)
            print(f"   ✅ Fetched {len(df)} players from KTC API")
            return df
        else:
            print(f"   ❌ KTC API returned status {response.status_code}")
            return None

    except Exception as e:
        print(f"   ❌ Error fetching KTC: {e}")
        return None


def fetch_ktc_rankings():
    """Fetch KTC rankings using best available method."""
    # Try BeautifulSoup method first (more reliable)
    df = fetch_ktc_rankings_bs4()
    if df is not None and not df.empty:
        return df
    # Fallback to API
    return fetch_ktc_rankings_api()


def fetch_player_history_from_page(ktc_id: int, player_name: str, href: str = None):
    """
    Fetch historical values for a specific player by scraping their KTC page.
    The player page embeds historical data in JSON format: {"d":"YYMMDD","v":value}
    """
    if not BS4_AVAILABLE:
        return None

    # Construct player URL
    if href:
        url = f"https://keeptradecut.com{href}"
    else:
        # Try to construct URL from name
        slug = player_name.lower().replace(' ', '-').replace("'", "").replace(".", "")
        url = f"https://keeptradecut.com/dynasty-rankings/players/{slug}-{ktc_id}"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    }

    try:
        response = requests.get(url, headers=headers, timeout=15, verify=False)

        if response.status_code != 200:
            return None

        html = response.text
        history = []

        # Method 1: Look for history array in JSON data
        # Format: "history":[{"d":"YYMMDD","v":value},...]
        history_match = re.search(r'"history"\s*:\s*(\[[^\]]+\])', html)
        if history_match:
            try:
                history_str = history_match.group(1)
                data = json.loads(history_str)
                for entry in data:
                    if isinstance(entry, dict) and 'd' in entry and 'v' in entry:
                        # Convert YYMMDD to YYYY-MM-DD
                        date_str = str(entry['d'])
                        if len(date_str) == 6:
                            year = '20' + date_str[:2]
                            month = date_str[2:4]
                            day = date_str[4:6]
                            formatted_date = f"{year}-{month}-{day}"
                            history.append({
                                'date': formatted_date,
                                'value': entry['v'],
                                'value_1qb': 0,
                            })
            except json.JSONDecodeError:
                pass

        # Method 2: Fallback - extract individual d/v patterns if Method 1 failed
        if not history:
            matches = re.findall(r'\{"d":"(\d{6})","v":(\d+)\}', html[:50000])
            if matches:
                for date_str, value in matches:
                    year = '20' + date_str[:2]
                    month = date_str[2:4]
                    day = date_str[4:6]
                    formatted_date = f"{year}-{month}-{day}"
                    history.append({
                        'date': formatted_date,
                        'value': int(value),
                        'value_1qb': 0,
                    })

        return history if history else None

    except Exception as e:
        return None


def fetch_player_history(ktc_id: int, player_name: str, href: str = None):
    """
    Fetch historical values for a specific player from KTC.
    Tries multiple methods: API first, then page scraping.
    Returns list of {date, value} dicts.
    """
    # Try the player page scraping first
    history = fetch_player_history_from_page(ktc_id, player_name, href)
    if history:
        return history

    # Fallback to API
    url = f"https://keeptradecut.com/api/v1/players/{ktc_id}/history"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'application/json',
    }

    try:
        response = requests.get(url, headers=headers, timeout=15, verify=False)

        if response.status_code == 200:
            data = response.json()
            history = []

            for entry in data:
                history.append({
                    'date': entry.get('date'),
                    'value': entry.get('superflexValue') or entry.get('value', 0),
                    'value_1qb': entry.get('oneQBValue', 0),
                })

            return history
        else:
            return None

    except Exception as e:
        return None


def create_historical_snapshots(driver):
    """
    Create/update KTCSnapshot nodes for historical value tracking.
    """
    print("\n📸 Creating historical KTC snapshots...")

    # Fetch current rankings
    current_df = fetch_ktc_rankings()

    if current_df is None or current_df.empty:
        print("   ❌ No current data to snapshot")
        return

    today = datetime.now().strftime('%Y-%m-%d')

    # Filter out records without ktc_id
    current_df = current_df[current_df['ktc_id'].notna()].copy()
    current_df['ktc_id'] = current_df['ktc_id'].astype(int)

    # Ensure ktc_value_1qb exists
    if 'ktc_value_1qb' not in current_df.columns:
        current_df['ktc_value_1qb'] = None

    with driver.session() as session:
        # Create constraint if not exists
        try:
            session.run("""
                CREATE CONSTRAINT ktc_snapshot_unique IF NOT EXISTS
                FOR (s:KTCSnapshot) REQUIRE (s.ktc_id, s.date) IS UNIQUE
            """)
        except:
            pass

        # Batch insert snapshots
        records = current_df.to_dict('records')

        session.run("""
            UNWIND $records as r
            MERGE (s:KTCSnapshot {ktc_id: r.ktc_id, date: $today})
            SET s.name = r.name,
                s.position = r.position,
                s.team = r.team,
                s.ktc_value = r.ktc_value,
                s.ktc_value_1qb = r.ktc_value_1qb,
                s.rank = r.rank,
                s.created_at = datetime()
        """, {'records': records, 'today': today})

        print(f"   ✅ Created {len(records)} snapshots for {today}")

        # First, update Player nodes with ktc_id from scraped data
        session.run("""
            UNWIND $records as r
            MATCH (p:Player)
            WHERE toLower(p.name) = toLower(r.name)
              AND p.position = r.position
            SET p.ktc_id = r.ktc_id
        """, {'records': records})

        # Link snapshots to Player nodes by name match
        session.run("""
            MATCH (s:KTCSnapshot)
            WHERE NOT EXISTS((s)-[:SNAPSHOT_OF]->())
            MATCH (p:Player)
            WHERE (toLower(p.name) = toLower(s.name) AND p.position = s.position)
               OR p.ktc_id = s.ktc_id
            MERGE (s)-[:SNAPSHOT_OF]->(p)
        """)

        # Count linked
        result = session.run("""
            MATCH (s:KTCSnapshot)-[:SNAPSHOT_OF]->(p:Player)
            WHERE s.date = $today
            RETURN count(s) as linked
        """, {'today': today})
        linked = result.single()['linked']
        print(f"   ✅ Linked {linked} snapshots to Player nodes")


def fetch_top_player_histories(driver, limit=200):
    """
    Fetch historical value data for top players from KTC API.
    This gives us point-in-time historical data.
    """
    print(f"\n📜 Fetching historical values for top {limit} players...")

    with driver.session() as session:
        # Get top players by KTC value (include those with ktc_id now updated)
        result = session.run("""
            MATCH (p:Player)
            WHERE p.position IN ['QB', 'RB', 'WR', 'TE']
              AND p.ktc_value > 500
            RETURN p.ktc_id as ktc_id, p.name as name, p.ktc_value as value
            ORDER BY p.ktc_value DESC
            LIMIT $limit
        """, {'limit': limit})

        players = [dict(r) for r in result]

    print(f"   Found {len(players)} players to fetch history for")

    all_history = []

    for i, player in enumerate(players):
        ktc_id = player['ktc_id']
        name = player['name']

        # Skip if no ktc_id (can't fetch history without it)
        if ktc_id is None:
            continue

        history = fetch_player_history(ktc_id, name)

        if history:
            for entry in history:
                all_history.append({
                    'ktc_id': ktc_id,
                    'name': name,
                    'date': entry.get('date'),
                    'ktc_value': entry.get('value', 0),
                    'ktc_value_1qb': entry.get('value_1qb', 0),
                })

        if (i + 1) % 25 == 0:
            print(f"   Processed {i+1}/{len(players)} players...")
            time.sleep(0.5)  # Rate limiting

    if all_history:
        df = pd.DataFrame(all_history)

        # Save to cache
        cache_file = f"{CACHE_DIR}/ktc_history_{datetime.now().strftime('%Y%m%d')}.csv"
        df.to_csv(cache_file, index=False)
        print(f"   ✅ Saved {len(df)} historical records to {cache_file}")

        return df

    return None


def load_historical_data_to_neo4j(driver, df: pd.DataFrame = None):
    """
    Load historical KTC data into Neo4j as KTCSnapshot nodes.
    """
    print("\n💾 Loading historical data to Neo4j...")

    if df is None:
        # Try to load from cache
        cache_files = sorted([f for f in os.listdir(CACHE_DIR) if f.startswith('ktc_history_')])
        if cache_files:
            latest = cache_files[-1]
            df = pd.read_csv(f"{CACHE_DIR}/{latest}")
            print(f"   Loaded {len(df)} records from cache: {latest}")
        else:
            print("   ❌ No historical data available")
            return

    # Parse dates
    df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')

    with driver.session() as session:
        # Batch insert
        records = df.to_dict('records')
        batch_size = 1000

        for i in range(0, len(records), batch_size):
            batch = records[i:i+batch_size]

            session.run("""
                UNWIND $batch as r
                MERGE (s:KTCSnapshot {ktc_id: r.ktc_id, date: r.date})
                SET s.name = r.name,
                    s.ktc_value = r.ktc_value,
                    s.ktc_value_1qb = r.ktc_value_1qb

                WITH s, r
                MATCH (p:Player)
                WHERE p.ktc_id = r.ktc_id
                MERGE (s)-[:SNAPSHOT_OF]->(p)
            """, {'batch': batch})

            print(f"   Processed {min(i+batch_size, len(records))}/{len(records)} records")

        # Count total snapshots
        result = session.run("MATCH (s:KTCSnapshot) RETURN count(s) as count")
        total = result.single()['count']
        print(f"   ✅ Total KTCSnapshot nodes: {total}")


def calculate_value_changes(driver):
    """
    Calculate value changes over different time periods.
    Updates Player nodes with:
    - ktc_change_30d, ktc_change_90d, ktc_change_1yr
    - ktc_pct_change_30d, ktc_pct_change_90d, ktc_pct_change_1yr
    """
    print("\n📈 Calculating value changes...")

    today = datetime.now()
    date_30d = (today - timedelta(days=30)).strftime('%Y-%m-%d')
    date_90d = (today - timedelta(days=90)).strftime('%Y-%m-%d')
    date_1yr = (today - timedelta(days=365)).strftime('%Y-%m-%d')

    with driver.session() as session:
        # Get value changes for each player
        result = session.run("""
            MATCH (p:Player)
            WHERE p.position IN ['QB', 'RB', 'WR', 'TE'] AND p.ktc_value > 0

            OPTIONAL MATCH (s30:KTCSnapshot)-[:SNAPSHOT_OF]->(p)
            WHERE s30.date >= $date_30d
            WITH p, min(s30.ktc_value) as val_30d_ago

            OPTIONAL MATCH (s90:KTCSnapshot)-[:SNAPSHOT_OF]->(p)
            WHERE s90.date >= $date_90d AND s90.date < $date_30d
            WITH p, val_30d_ago, min(s90.ktc_value) as val_90d_ago

            OPTIONAL MATCH (s1y:KTCSnapshot)-[:SNAPSHOT_OF]->(p)
            WHERE s1y.date >= $date_1yr AND s1y.date < $date_90d
            WITH p, val_30d_ago, val_90d_ago, min(s1y.ktc_value) as val_1yr_ago

            WHERE val_30d_ago IS NOT NULL OR val_90d_ago IS NOT NULL OR val_1yr_ago IS NOT NULL

            SET p.ktc_value_30d_ago = val_30d_ago,
                p.ktc_value_90d_ago = val_90d_ago,
                p.ktc_value_1yr_ago = val_1yr_ago,
                p.ktc_change_30d = CASE WHEN val_30d_ago IS NOT NULL
                                        THEN p.ktc_value - val_30d_ago ELSE null END,
                p.ktc_change_90d = CASE WHEN val_90d_ago IS NOT NULL
                                        THEN p.ktc_value - val_90d_ago ELSE null END,
                p.ktc_change_1yr = CASE WHEN val_1yr_ago IS NOT NULL
                                        THEN p.ktc_value - val_1yr_ago ELSE null END,
                p.ktc_pct_change_30d = CASE WHEN val_30d_ago > 0
                                            THEN (p.ktc_value - val_30d_ago) * 100.0 / val_30d_ago ELSE null END,
                p.ktc_pct_change_90d = CASE WHEN val_90d_ago > 0
                                            THEN (p.ktc_value - val_90d_ago) * 100.0 / val_90d_ago ELSE null END,
                p.ktc_pct_change_1yr = CASE WHEN val_1yr_ago > 0
                                            THEN (p.ktc_value - val_1yr_ago) * 100.0 / val_1yr_ago ELSE null END

            RETURN count(p) as updated
        """, {'date_30d': date_30d, 'date_90d': date_90d, 'date_1yr': date_1yr})

        updated = result.single()['updated']
        print(f"   ✅ Updated {updated} players with value change data")

        # Show biggest risers
        result = session.run("""
            MATCH (p:Player)
            WHERE p.ktc_pct_change_90d IS NOT NULL AND p.ktc_value > 1000
            RETURN p.name, p.position, p.ktc_value, p.ktc_pct_change_90d
            ORDER BY p.ktc_pct_change_90d DESC
            LIMIT 5
        """)

        print("\n   Top Value Risers (90d):")
        for r in result:
            print(f"      {r['p.name']} ({r['p.position']}): {r['p.ktc_pct_change_90d']:+.1f}%")


def verify_historical_data(driver):
    """Verify historical data availability."""
    print("\n🔍 Verifying historical data...")

    with driver.session() as session:
        # Count snapshots by date range
        result = session.run("""
            MATCH (s:KTCSnapshot)
            RETURN min(s.date) as earliest, max(s.date) as latest, count(s) as total,
                   count(DISTINCT s.date) as unique_dates
        """)
        r = result.single()

        print(f"   Snapshot date range: {r['earliest']} to {r['latest']}")
        print(f"   Total snapshots: {r['total']}")
        print(f"   Unique dates: {r['unique_dates']}")

        # Count players with historical data
        result = session.run("""
            MATCH (p:Player)
            WHERE p.ktc_change_90d IS NOT NULL
            RETURN count(p) as with_history
        """)
        with_history = result.single()['with_history']
        print(f"   Players with 90d change data: {with_history}")


def main():
    """Main entry point."""
    print("=" * 70)
    print("KTC HISTORICAL DATA PIPELINE")
    print(f"Started: {datetime.now()}")
    print("=" * 70)

    driver = get_driver()

    try:
        # 1. Create today's snapshot
        create_historical_snapshots(driver)

        # 2. Fetch historical data from KTC API for top players
        history_df = fetch_top_player_histories(driver, limit=300)

        # 3. Load historical data to Neo4j
        if history_df is not None:
            load_historical_data_to_neo4j(driver, history_df)

        # 4. Calculate value changes
        calculate_value_changes(driver)

        # 5. Verify
        verify_historical_data(driver)

        print("\n" + "=" * 70)
        print("HISTORICAL DATA PIPELINE COMPLETE")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        driver.close()


if __name__ == "__main__":
    main()
