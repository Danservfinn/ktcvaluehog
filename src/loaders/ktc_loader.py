"""
KTC (KeepTradeCut) Value Loader
Fetches dynasty player values from keeptradecut.com and loads into Neo4j.
"""

import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

import requests
import pandas as pd

logger = logging.getLogger(__name__)


class KTCLoader:
    """Load KTC dynasty values into Neo4j."""

    KTC_API_URL = "https://keeptradecut.com/api/v1/rankings"

    def __init__(self, driver, cache_dir: Path = None):
        """
        Initialize KTC loader.

        Args:
            driver: Neo4j driver instance
            cache_dir: Directory to cache KTC data
        """
        self.driver = driver
        self.cache_dir = Path(cache_dir or "data/raw/ktc")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def fetch_ktc_values(self, superflex: bool = True) -> Optional[pd.DataFrame]:
        """
        Fetch current KTC values from API.

        Args:
            superflex: If True, fetch superflex values

        Returns:
            DataFrame with player values
        """
        logger.info("Fetching KTC values from API...")

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Referer': 'https://keeptradecut.com/dynasty-rankings'
        }

        params = {
            'format': 'json',
            'sf': '1' if superflex else '0',
            'tep': '0.5'
        }

        try:
            response = requests.get(
                self.KTC_API_URL,
                headers=headers,
                params=params,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    df = pd.DataFrame(data)
                    logger.info(f"Retrieved {len(df)} players from KTC API")

                    # Cache the data
                    cache_file = self.cache_dir / f"ktc_{'sf' if superflex else '1qb'}_{datetime.now().strftime('%Y%m%d')}.csv"
                    df.to_csv(cache_file, index=False)

                    return df

            logger.warning(f"KTC API returned status {response.status_code}")

        except Exception as e:
            logger.warning(f"Error fetching KTC data: {e}")

        # Try to load from cache
        return self._load_from_cache(superflex)

    def _load_from_cache(self, superflex: bool = True) -> Optional[pd.DataFrame]:
        """Load most recent cached KTC data."""
        prefix = 'ktc_sf' if superflex else 'ktc_1qb'
        cache_files = sorted(self.cache_dir.glob(f"{prefix}_*.csv"), reverse=True)

        if cache_files:
            logger.info(f"Loading cached KTC data from {cache_files[0]}")
            return pd.read_csv(cache_files[0])

        return None

    def load_ktc_values(self, superflex: bool = True) -> int:
        """
        Load KTC values into Neo4j Player nodes.

        Args:
            superflex: If True, use superflex values

        Returns:
            Number of players updated
        """
        df = self.fetch_ktc_values(superflex)

        if df is None or len(df) == 0:
            logger.warning("No KTC data available")
            return 0

        # Standardize column names
        column_mapping = {
            'playerName': 'name',
            'player_name': 'name',
            'firstName': 'first_name',
            'lastName': 'last_name',
            'position': 'position',
            'team': 'team',
            'value': 'ktc_value',
            'superflexValue': 'sf_value',
            'oneQBValue': 'oneqb_value',
            'age': 'age',
            'sleeperId': 'sleeper_id'
        }

        df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})

        # Combine name if split
        if 'first_name' in df.columns and 'last_name' in df.columns and 'name' not in df.columns:
            df['name'] = df['first_name'].astype(str) + ' ' + df['last_name'].astype(str)

        # Determine value column
        value_col = 'sf_value' if superflex and 'sf_value' in df.columns else 'ktc_value'
        if value_col not in df.columns:
            value_col = 'value' if 'value' in df.columns else None

        if value_col is None:
            logger.error("No value column found in KTC data")
            return 0

        count = 0
        with self.driver.session() as session:
            for _, row in df.iterrows():
                name = row.get('name')
                if pd.isna(name):
                    continue

                value = row.get(value_col, 0)
                if pd.isna(value):
                    value = 0

                # Try to match by sleeper_id first, then name
                sleeper_id = row.get('sleeper_id')
                age = row.get('age')

                if pd.notna(sleeper_id):
                    result = session.run("""
                        MATCH (p:Player)
                        WHERE p.sleeper_id = $sleeper_id OR toLower(p.name) = toLower($name)
                        SET p.ktc_value = $value,
                            p.ktc_updated = datetime()
                        RETURN count(p) as updated
                    """, {
                        'sleeper_id': str(sleeper_id),
                        'name': name,
                        'value': int(value)
                    })
                else:
                    result = session.run("""
                        MATCH (p:Player)
                        WHERE toLower(p.name) = toLower($name)
                        SET p.ktc_value = $value,
                            p.ktc_updated = datetime()
                        RETURN count(p) as updated
                    """, {
                        'name': name,
                        'value': int(value)
                    })

                record = result.single()
                if record and record['updated'] > 0:
                    count += 1

                # Also set age if available
                if pd.notna(age):
                    session.run("""
                        MATCH (p:Player)
                        WHERE toLower(p.name) = toLower($name)
                        SET p.age = $age
                    """, {'name': name, 'age': float(age)})

        logger.info(f"Updated KTC values for {count} players")
        return count

    def get_value_distribution(self) -> Dict[str, Any]:
        """Get KTC value distribution stats from Neo4j."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (p:Player)
                WHERE p.ktc_value > 0 AND p.position IN ['QB', 'RB', 'WR', 'TE']
                RETURN p.position as position,
                       count(p) as count,
                       avg(p.ktc_value) as avg_value,
                       max(p.ktc_value) as max_value,
                       min(p.ktc_value) as min_value
                ORDER BY position
            """)
            return {r['position']: dict(r) for r in result}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    from neo4j import GraphDatabase

    driver = GraphDatabase.driver("bolt://localhost:7687", auth=None)

    loader = KTCLoader(driver)
    count = loader.load_ktc_values(superflex=True)

    print(f"\nUpdated {count} players")
    print("\nValue distribution:")
    print(loader.get_value_distribution())

    driver.close()
