"""
KTC Devy (KeepTradeCut) Value Loader
Fetches devy prospect values from keeptradecut.com for college players.

Devy = "developmental" players - college prospects not yet in the NFL.
These values are crucial for dynasty devy leagues and rookie draft prep.
"""

import os
import re
import json
import logging
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any
from urllib.parse import urljoin

import requests
import pandas as pd
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class KTCDevyLoader:
    """
    Load KTC devy values for college prospects.

    Supports:
    - Current devy rankings (API + scraping fallback)
    - Historical value snapshots
    - Time-series tracking
    """

    # API and web endpoints
    KTC_DEVY_API_URL = "https://keeptradecut.com/api/v1/devy/rankings"
    KTC_DEVY_WEB_URL = "https://keeptradecut.com/devy-rankings"
    KTC_DEVY_PLAYER_URL = "https://keeptradecut.com/devy/players/"

    # Request headers
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/html',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://keeptradecut.com/devy-rankings'
    }

    # Fantasy positions to track
    FANTASY_POSITIONS = ["QB", "RB", "WR", "TE"]

    def __init__(self, driver=None, cache_dir: Path = None):
        """
        Initialize KTC Devy loader.

        Args:
            driver: Neo4j driver instance (optional, for direct loading)
            cache_dir: Directory to cache devy data
        """
        self.driver = driver
        self.cache_dir = Path(cache_dir or "data/raw/ktc_devy")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Historical snapshots directory
        self.snapshots_dir = Path("data/historical/devy_snapshots")
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)

        self._session = requests.Session()
        self._session.headers.update(self.HEADERS)

    def fetch_devy_rankings(
        self,
        superflex: bool = True,
        format_type: str = "sf"
    ) -> Optional[pd.DataFrame]:
        """
        Fetch current devy rankings from KTC.

        Tries API first, falls back to web scraping if API fails.

        Args:
            superflex: If True, fetch superflex values
            format_type: "sf" (superflex), "1qb", or "2qb"

        Returns:
            DataFrame with devy prospect values
        """
        logger.info(f"Fetching KTC devy rankings (format={format_type})...")

        # Try API first
        df = self._fetch_via_api(superflex)

        # Fallback to scraping if API fails
        if df is None or df.empty:
            logger.info("API failed, falling back to web scraping...")
            df = self._fetch_via_scraping(superflex)

        if df is not None and not df.empty:
            # Add metadata
            df["fetched_at"] = datetime.now().isoformat()
            df["format"] = format_type

            # Cache the data
            self._cache_data(df, format_type)

            # Save as snapshot
            self._save_snapshot(df, format_type)

            logger.info(f"Retrieved {len(df)} devy prospects")
            return df

        # Try loading from cache
        logger.warning("Live fetch failed, trying cache...")
        return self._load_from_cache(format_type)

    def _fetch_via_api(self, superflex: bool = True) -> Optional[pd.DataFrame]:
        """Attempt to fetch devy rankings via KTC API."""
        params = {
            'format': 'json',
            'sf': '1' if superflex else '0'
        }

        try:
            response = self._session.get(
                self.KTC_DEVY_API_URL,
                params=params,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    df = pd.DataFrame(data)
                    logger.info(f"API returned {len(df)} prospects")
                    return self._normalize_api_response(df)

            logger.warning(f"Devy API returned status {response.status_code}")

        except Exception as e:
            logger.warning(f"Devy API error: {e}")

        return None

    def _fetch_via_scraping(self, superflex: bool = True) -> Optional[pd.DataFrame]:
        """
        Fetch devy rankings by scraping the web page.

        This is a fallback when the API is unavailable.
        """
        url = f"{self.KTC_DEVY_WEB_URL}?format={'sf' if superflex else '1qb'}"

        try:
            response = self._session.get(url, timeout=30)

            if response.status_code != 200:
                logger.warning(f"Web scrape returned status {response.status_code}")
                return None

            soup = BeautifulSoup(response.text, 'html.parser')
            players = []

            # Look for player data in page
            # KTC uses JavaScript rendering, so we'll look for embedded JSON data
            scripts = soup.find_all('script')

            for script in scripts:
                if script.string and 'window.__NEXT_DATA__' in script.string:
                    # Extract Next.js page data
                    json_match = re.search(r'window\.__NEXT_DATA__\s*=\s*({.+?});', script.string)
                    if json_match:
                        try:
                            page_data = json.loads(json_match.group(1))
                            props = page_data.get('props', {}).get('pageProps', {})

                            # Extract player rankings from page props
                            rankings = props.get('rankings', [])
                            if rankings:
                                return pd.DataFrame(rankings)

                        except json.JSONDecodeError:
                            pass

            # Alternative: look for ranking table rows
            ranking_rows = soup.select('.ranking-row, .player-row, [class*="ranking"]')

            for row in ranking_rows:
                try:
                    player = self._parse_ranking_row(row)
                    if player:
                        players.append(player)
                except Exception as e:
                    logger.debug(f"Error parsing row: {e}")

            if players:
                return pd.DataFrame(players)

            logger.warning("Could not extract player data from page")

        except Exception as e:
            logger.error(f"Web scraping error: {e}")

        return None

    def _parse_ranking_row(self, row) -> Optional[Dict]:
        """Parse a single ranking row from HTML."""
        player = {}

        # Try to extract common fields
        name_elem = row.select_one('.player-name, [class*="name"]')
        if name_elem:
            player['name'] = name_elem.get_text(strip=True)

        position_elem = row.select_one('.position, [class*="pos"]')
        if position_elem:
            player['position'] = position_elem.get_text(strip=True)

        team_elem = row.select_one('.team, .college, [class*="team"]')
        if team_elem:
            player['college'] = team_elem.get_text(strip=True)

        value_elem = row.select_one('.value, [class*="value"]')
        if value_elem:
            value_text = value_elem.get_text(strip=True)
            try:
                player['value'] = int(value_text.replace(',', ''))
            except ValueError:
                pass

        rank_elem = row.select_one('.rank, [class*="rank"]')
        if rank_elem:
            rank_text = rank_elem.get_text(strip=True)
            try:
                player['rank'] = int(rank_text)
            except ValueError:
                pass

        # Get player link for ID extraction
        link = row.select_one('a[href*="/devy/players/"]')
        if link:
            href = link.get('href', '')
            player['href'] = href

            # Extract KTC ID from URL
            match = re.search(r'/players/([^/]+)-(\d+)', href)
            if match:
                player['ktc_id'] = match.group(2)
                player['slug'] = match.group(1)

        # Only return if we got essential fields
        if player.get('name') and (player.get('value') or player.get('rank')):
            return player

        return None

    def _normalize_api_response(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize API response to consistent schema."""
        # Map API field names to our schema
        column_mapping = {
            'playerName': 'name',
            'player_name': 'name',
            'value': 'ktc_devy_value',
            'ktcValue': 'ktc_devy_value',
            'rank': 'ktc_devy_rank',
            'overallRank': 'ktc_devy_rank',
            'position': 'position',
            'pos': 'position',
            'team': 'college',
            'school': 'college',
            'college': 'college',
            'playerId': 'ktc_id',
            'playerID': 'ktc_id',
            'id': 'ktc_id',
        }

        # Rename columns that exist
        rename_map = {k: v for k, v in column_mapping.items() if k in df.columns}
        df = df.rename(columns=rename_map)

        # Ensure value column exists
        if 'ktc_devy_value' not in df.columns:
            if 'value' in df.columns:
                df['ktc_devy_value'] = df['value']

        # Ensure rank column exists
        if 'ktc_devy_rank' not in df.columns:
            if 'rank' in df.columns:
                df['ktc_devy_rank'] = df['rank']
            else:
                df['ktc_devy_rank'] = range(1, len(df) + 1)

        # Filter to fantasy-relevant positions
        if 'position' in df.columns:
            df = df[df['position'].isin(self.FANTASY_POSITIONS)]

        return df

    def _cache_data(self, df: pd.DataFrame, format_type: str):
        """Cache fetched data to disk."""
        date_str = datetime.now().strftime('%Y%m%d')
        cache_file = self.cache_dir / f"devy_{format_type}_{date_str}.csv"
        df.to_csv(cache_file, index=False)
        logger.info(f"Cached devy data to {cache_file}")

    def _save_snapshot(self, df: pd.DataFrame, format_type: str):
        """Save as historical snapshot for time-series analysis."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        snapshot_file = self.snapshots_dir / f"devy_{format_type}_{timestamp}.csv"
        df.to_csv(snapshot_file, index=False)
        logger.info(f"Saved devy snapshot to {snapshot_file}")

    def _load_from_cache(self, format_type: str) -> Optional[pd.DataFrame]:
        """Load most recent cached devy data."""
        cache_files = sorted(
            self.cache_dir.glob(f"devy_{format_type}_*.csv"),
            reverse=True
        )

        if cache_files:
            logger.info(f"Loading cached devy data from {cache_files[0]}")
            return pd.read_csv(cache_files[0])

        return None

    # =========================================================================
    # NEO4J LOADING
    # =========================================================================

    def load_devy_values_to_neo4j(
        self,
        df: pd.DataFrame = None,
        superflex: bool = True
    ) -> int:
        """
        Load devy values into Neo4j as DevySnapshot nodes.

        Args:
            df: DataFrame with devy values (fetches if None)
            superflex: Format type if fetching

        Returns:
            Number of nodes created/updated
        """
        if self.driver is None:
            raise ValueError("Neo4j driver required for loading")

        if df is None:
            df = self.fetch_devy_rankings(superflex=superflex)

        if df is None or df.empty:
            logger.warning("No devy data to load")
            return 0

        snapshot_date = datetime.now().strftime('%Y-%m-%d')
        loaded_count = 0

        with self.driver.session() as session:
            for _, row in df.iterrows():
                try:
                    # Generate IDs
                    name = row.get('name', '')
                    prospect_id = self._generate_prospect_id(name, row.get('college', ''))
                    snapshot_id = f"{prospect_id}_{snapshot_date}"

                    # Create/update Prospect node
                    session.run("""
                        MERGE (p:Prospect {name: $name})
                        ON CREATE SET
                            p.prospect_id = $prospect_id,
                            p.position = $position,
                            p.college = $college,
                            p.created_at = datetime()
                        ON MATCH SET
                            p.position = coalesce($position, p.position),
                            p.college = coalesce($college, p.college)
                        SET p.updated_at = datetime()
                    """, {
                        'name': name,
                        'prospect_id': prospect_id,
                        'position': row.get('position'),
                        'college': row.get('college')
                    })

                    # Create DevySnapshot node
                    session.run("""
                        MERGE (d:DevySnapshot {snapshot_id: $snapshot_id})
                        SET d.date = date($date),
                            d.ktc_devy_value = $value,
                            d.ktc_devy_rank = $rank,
                            d.position_rank = $pos_rank,
                            d.updated_at = datetime()

                        WITH d
                        MATCH (p:Prospect {name: $name})
                        MERGE (p)-[:HAS_DEVY_VALUE]->(d)
                    """, {
                        'snapshot_id': snapshot_id,
                        'name': name,
                        'date': snapshot_date,
                        'value': row.get('ktc_devy_value'),
                        'rank': row.get('ktc_devy_rank'),
                        'pos_rank': row.get('position_rank')
                    })

                    loaded_count += 1

                except Exception as e:
                    logger.warning(f"Error loading prospect {row.get('name')}: {e}")

        logger.info(f"Loaded {loaded_count} devy values to Neo4j")
        return loaded_count

    def link_devy_snapshots_temporal(self):
        """Create DEVY_NEXT relationships between consecutive snapshots."""
        if self.driver is None:
            raise ValueError("Neo4j driver required")

        with self.driver.session() as session:
            result = session.run("""
                MATCH (p:Prospect)-[:HAS_DEVY_VALUE]->(d1:DevySnapshot)
                MATCH (p)-[:HAS_DEVY_VALUE]->(d2:DevySnapshot)
                WHERE d1.date < d2.date
                  AND NOT exists((d1)-[:DEVY_NEXT]->(d2))
                  AND NOT exists((d1)-[:DEVY_NEXT]->(:DevySnapshot)-[:DEVY_NEXT*]->(d2))
                WITH d1, d2,
                     d2.ktc_devy_value - d1.ktc_devy_value as value_change,
                     d2.ktc_devy_rank - d1.ktc_devy_rank as rank_change
                ORDER BY d1.date
                WITH d1, collect({d2: d2, value_change: value_change, rank_change: rank_change})[0] as next_data
                MERGE (d1)-[r:DEVY_NEXT]->(next_data.d2)
                SET r.value_change = next_data.value_change,
                    r.rank_change = next_data.rank_change
                RETURN count(*) as links_created
            """)

            count = result.single()["links_created"]
            logger.info(f"Created {count} temporal links between devy snapshots")
            return count

    def _generate_prospect_id(self, name: str, college: str) -> str:
        """Generate a unique prospect ID."""
        import hashlib
        combined = f"{name.lower()}_{college.lower() if college else 'unknown'}"
        return hashlib.md5(combined.encode()).hexdigest()[:12]

    # =========================================================================
    # HISTORICAL DATA
    # =========================================================================

    def get_historical_snapshots(
        self,
        prospect_name: str = None,
        start_date: str = None,
        end_date: str = None
    ) -> pd.DataFrame:
        """
        Load historical devy snapshots from saved files.

        Args:
            prospect_name: Filter by prospect name
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            DataFrame with historical values
        """
        all_snapshots = []

        for snapshot_file in sorted(self.snapshots_dir.glob("devy_*.csv")):
            try:
                df = pd.read_csv(snapshot_file)

                # Extract date from filename
                match = re.search(r'devy_\w+_(\d{8})', snapshot_file.name)
                if match:
                    file_date = datetime.strptime(match.group(1), '%Y%m%d').strftime('%Y-%m-%d')
                    df['snapshot_date'] = file_date

                    # Date filtering
                    if start_date and file_date < start_date:
                        continue
                    if end_date and file_date > end_date:
                        continue

                all_snapshots.append(df)

            except Exception as e:
                logger.warning(f"Error reading {snapshot_file}: {e}")

        if not all_snapshots:
            return pd.DataFrame()

        combined = pd.concat(all_snapshots, ignore_index=True)

        # Name filtering
        if prospect_name:
            combined = combined[
                combined['name'].str.lower().str.contains(prospect_name.lower())
            ]

        return combined.sort_values(['name', 'snapshot_date'])

    def get_value_history(self, prospect_name: str) -> pd.DataFrame:
        """
        Get value history for a specific prospect.

        Returns DataFrame with date and value columns for charting.
        """
        history = self.get_historical_snapshots(prospect_name=prospect_name)

        if history.empty:
            return history

        return history[['snapshot_date', 'name', 'ktc_devy_value', 'ktc_devy_rank']].drop_duplicates()


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    loader = KTCDevyLoader()

    print("\n=== Fetching KTC Devy Rankings ===")
    df = loader.fetch_devy_rankings(superflex=True)

    if df is not None and not df.empty:
        print(f"\nFetched {len(df)} devy prospects")
        print("\nTop 10 Devy Prospects:")
        cols = ['name', 'position', 'college', 'ktc_devy_value', 'ktc_devy_rank']
        display_cols = [c for c in cols if c in df.columns]
        print(df[display_cols].head(10).to_string(index=False))

        # Show position breakdown
        if 'position' in df.columns:
            print("\nPosition Breakdown:")
            print(df['position'].value_counts())
    else:
        print("Failed to fetch devy rankings")
