"""
Injury Data Client
Fetches injury data from ESPN and NFL APIs.
"""

import requests
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)


class ESPNInjuryClient:
    """
    Fetch injury data from ESPN's public API.

    ESPN provides free injury data without authentication.
    """

    BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
    TIMEOUT = 30

    # ESPN team IDs
    TEAM_IDS = {
        'ARI': 22, 'ATL': 1, 'BAL': 33, 'BUF': 2, 'CAR': 29, 'CHI': 3,
        'CIN': 4, 'CLE': 5, 'DAL': 6, 'DEN': 7, 'DET': 8, 'GB': 9,
        'HOU': 34, 'IND': 11, 'JAX': 30, 'KC': 12, 'LAC': 24, 'LAR': 14,
        'LV': 13, 'MIA': 15, 'MIN': 16, 'NE': 17, 'NO': 18, 'NYG': 19,
        'NYJ': 20, 'PHI': 21, 'PIT': 23, 'SEA': 26, 'SF': 25, 'TB': 27,
        'TEN': 10, 'WAS': 28
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; DynastyEdge/1.0)'
        })

    def _get(self, endpoint: str) -> Any:
        """Make GET request."""
        url = f"{self.BASE_URL}/{endpoint}"
        response = self.session.get(url, timeout=self.TIMEOUT)
        response.raise_for_status()
        return response.json()

    def get_team_injuries(self, team_abbr: str) -> List[Dict]:
        """
        Get injuries for a specific team.

        Args:
            team_abbr: Team abbreviation (e.g., 'KC', 'DAL')

        Returns:
            List of injury dicts
        """
        team_id = self.TEAM_IDS.get(team_abbr.upper())
        if not team_id:
            logger.warning(f"Unknown team: {team_abbr}")
            return []

        try:
            data = self._get(f"teams/{team_id}/injuries")
            injuries = []

            for item in data.get('items', []):
                athlete = item.get('athlete', {})
                injuries.append({
                    'espn_id': athlete.get('id'),
                    'name': athlete.get('displayName'),
                    'position': athlete.get('position', {}).get('abbreviation'),
                    'team': team_abbr.upper(),
                    'status': item.get('status'),
                    'injury_type': item.get('type', {}).get('name'),
                    'injury_detail': item.get('details', {}).get('detail'),
                    'return_date': item.get('details', {}).get('returnDate'),
                    'updated': datetime.now().isoformat()
                })

            return injuries
        except Exception as e:
            logger.error(f"Error fetching injuries for {team_abbr}: {e}")
            return []

    def get_all_injuries(self) -> pd.DataFrame:
        """Get injuries for all NFL teams."""
        all_injuries = []

        for team in self.TEAM_IDS.keys():
            injuries = self.get_team_injuries(team)
            all_injuries.extend(injuries)

        return pd.DataFrame(all_injuries)

    def get_injury_report(self) -> pd.DataFrame:
        """Get formatted injury report."""
        df = self.get_all_injuries()

        if df.empty:
            return df

        # Add severity classification
        def classify_severity(status):
            if not status:
                return 'Unknown'
            status_lower = status.lower()
            if 'out' in status_lower or 'ir' in status_lower:
                return 'Severe'
            elif 'doubtful' in status_lower:
                return 'High'
            elif 'questionable' in status_lower:
                return 'Moderate'
            elif 'probable' in status_lower:
                return 'Low'
            return 'Unknown'

        df['severity'] = df['status'].apply(classify_severity)

        return df


class NFLverseInjuryLoader:
    """
    Load injury data from NFLverse datasets.

    Uses nflreadr for comprehensive historical injury data.
    """

    def __init__(self):
        try:
            import nflreadpy
            self.nflreadpy = nflreadpy
            self._available = True
        except ImportError:
            logger.warning("nflreadpy not available for injury data")
            self._available = False

    def load_injuries(self, season: int = 2024) -> pd.DataFrame:
        """Load injury data for a season."""
        if not self._available:
            return pd.DataFrame()

        try:
            injuries = self.nflreadpy.load_injuries(seasons=[season])
            return injuries
        except Exception as e:
            logger.error(f"Error loading NFLverse injuries: {e}")
            return pd.DataFrame()


class InjuryNeo4jLoader:
    """Load injury data into Neo4j."""

    def __init__(self, driver):
        self.driver = driver
        self.espn_client = ESPNInjuryClient()

    def load_current_injuries(self) -> int:
        """Load current injury data into Neo4j."""
        injuries_df = self.espn_client.get_all_injuries()

        if injuries_df.empty:
            logger.warning("No injury data fetched")
            return 0

        count = 0
        with self.driver.session() as session:
            for _, injury in injuries_df.iterrows():
                # Match player and create injury relationship
                result = session.run("""
                    MATCH (p:Player)
                    WHERE toLower(p.name) = toLower($name)
                       OR (p.current_team = $team AND toLower(p.name) CONTAINS toLower($first_name))

                    // Create or update Injury node
                    MERGE (i:Injury {
                        player_name: $name,
                        injury_type: $type,
                        date: date()
                    })
                    SET i.status = $status,
                        i.detail = $detail,
                        i.severity = $severity,
                        i.return_date = $return_date,
                        i.updated_at = datetime()

                    // Link to player
                    MERGE (p)-[r:HAS_INJURY]->(i)
                    SET r.current = true

                    // Update player injury status
                    SET p.injury_status = $status,
                        p.injury_type = $type,
                        p.injury_history = COALESCE(p.injury_history, 0) + 1

                    RETURN p.name as matched_player
                """, {
                    'name': injury['name'],
                    'first_name': injury['name'].split()[0] if injury['name'] else '',
                    'team': injury['team'],
                    'type': injury.get('injury_type', 'Unknown'),
                    'status': injury.get('status', 'Unknown'),
                    'detail': injury.get('injury_detail', ''),
                    'severity': injury.get('severity', 'Unknown'),
                    'return_date': injury.get('return_date')
                })

                if result.single():
                    count += 1

        logger.info(f"Updated injury data for {count} players")
        return count

    def clear_old_injuries(self):
        """Mark old injuries as resolved."""
        with self.driver.session() as session:
            session.run("""
                MATCH (p:Player)-[r:HAS_INJURY]->(i:Injury)
                WHERE r.current = true
                  AND i.updated_at < datetime() - duration({days: 7})
                SET r.current = false,
                    p.injury_status = 'Healthy',
                    p.injury_type = null
            """)

    def get_injury_impact_analysis(self) -> pd.DataFrame:
        """Analyze impact of injuries on dynasty values."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (p:Player)-[r:HAS_INJURY {current: true}]->(i:Injury)
                WHERE p.ktc_value > 1000

                // Get teammates who might benefit
                OPTIONAL MATCH (p)-[:PLAYS_FOR]->(t:Team)<-[:PLAYS_FOR]-(teammate:Player)
                WHERE teammate.position = p.position
                  AND teammate <> p
                  AND teammate.ktc_value > 500

                RETURN p.name as injured_player,
                       p.position as position,
                       p.ktc_value as ktc_value,
                       i.status as status,
                       i.injury_type as injury_type,
                       i.severity as severity,
                       collect(DISTINCT {
                           name: teammate.name,
                           ktc: teammate.ktc_value,
                           signal: teammate.edge_signal
                       })[0..3] as beneficiaries
                ORDER BY p.ktc_value DESC
            """)
            return pd.DataFrame([dict(r) for r in result])


def run_injury_update(driver) -> Dict[str, Any]:
    """Run complete injury update."""
    loader = InjuryNeo4jLoader(driver)

    # Clear old injuries
    loader.clear_old_injuries()

    # Load current injuries
    count = loader.load_current_injuries()

    # Get impact analysis
    impact = loader.get_injury_impact_analysis()

    return {
        'injuries_updated': count,
        'impact_analysis': impact
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test ESPN client
    client = ESPNInjuryClient()
    injuries = client.get_all_injuries()
    print(f"Fetched {len(injuries)} injuries")
    print(injuries.head())
