"""Sleeper API client for fantasy league data.

Sleeper API: https://docs.sleeper.app/

No authentication required for public endpoints.
All fantasy league data is accessible with just a league_id.
"""

import requests
from typing import List, Dict, Any, Optional
from functools import lru_cache
import pandas as pd
from datetime import datetime

from ..config import SLEEPER_LEAGUE_ID


class SleeperClient:
    """Client for Sleeper fantasy football API."""

    BASE_URL = "https://api.sleeper.app/v1"
    TIMEOUT = 30

    def __init__(self, league_id: str = None):
        """Initialize Sleeper client.

        Args:
            league_id: Sleeper league ID. If not provided, uses env variable.
        """
        self.league_id = league_id or SLEEPER_LEAGUE_ID
        self._players_cache = None
        self._players_cache_time = None

    def _get(self, endpoint: str) -> Any:
        """Make GET request to Sleeper API."""
        url = f"{self.BASE_URL}/{endpoint}"
        response = requests.get(url, timeout=self.TIMEOUT)
        response.raise_for_status()
        return response.json()

    # =========================================================================
    # League Data
    # =========================================================================

    def get_league(self) -> Dict:
        """Get league settings and info.

        Returns:
            Dict with league settings (scoring, roster positions, etc.)
        """
        return self._get(f"league/{self.league_id}")

    def get_rosters(self) -> List[Dict]:
        """Get all rosters in the league.

        Returns:
            List of roster dicts with player_ids, settings, etc.
        """
        return self._get(f"league/{self.league_id}/rosters")

    def get_users(self) -> List[Dict]:
        """Get all users in the league.

        Returns:
            List of user dicts with display_name, avatar, etc.
        """
        return self._get(f"league/{self.league_id}/users")

    def get_matchups(self, week: int) -> List[Dict]:
        """Get matchups for a specific week.

        Args:
            week: Week number (1-18 for regular season)

        Returns:
            List of matchup dicts with points, starters, etc.
        """
        return self._get(f"league/{self.league_id}/matchups/{week}")

    def get_transactions(self, week: int) -> List[Dict]:
        """Get transactions for a specific week.

        Includes trades, waivers, free agent adds.

        Args:
            week: Week number

        Returns:
            List of transaction dicts
        """
        return self._get(f"league/{self.league_id}/transactions/{week}")

    def get_traded_picks(self) -> List[Dict]:
        """Get all traded draft picks in the league.

        Returns:
            List of traded pick dicts with owner_id, previous_owner_id, etc.
        """
        return self._get(f"league/{self.league_id}/traded_picks")

    def get_drafts(self) -> List[Dict]:
        """Get draft information for the league.

        Returns:
            List of draft dicts
        """
        return self._get(f"league/{self.league_id}/drafts")

    def get_draft_picks(self, draft_id: str) -> List[Dict]:
        """Get all picks from a specific draft.

        Args:
            draft_id: Sleeper draft ID

        Returns:
            List of draft pick dicts
        """
        return self._get(f"draft/{draft_id}/picks")

    # =========================================================================
    # Player Data
    # =========================================================================

    def get_players(self, force_refresh: bool = False) -> Dict[str, Dict]:
        """Get all NFL players from Sleeper.

        This is a large request (~9MB). Results are cached for 24 hours.

        Args:
            force_refresh: Force refresh of cached data

        Returns:
            Dict mapping player_id to player info
        """
        now = datetime.now()

        # Check cache
        if not force_refresh and self._players_cache is not None:
            cache_age = (now - self._players_cache_time).total_seconds()
            if cache_age < 86400:  # 24 hours
                return self._players_cache

        # Fetch fresh data
        self._players_cache = self._get("players/nfl")
        self._players_cache_time = now

        return self._players_cache

    def get_player(self, player_id: str) -> Optional[Dict]:
        """Get a specific player by Sleeper ID.

        Args:
            player_id: Sleeper player ID

        Returns:
            Player dict or None if not found
        """
        players = self.get_players()
        return players.get(player_id)

    def search_player(self, name: str, position: str = None) -> List[Dict]:
        """Search for players by name.

        Args:
            name: Player name (partial match)
            position: Optional position filter

        Returns:
            List of matching players
        """
        players = self.get_players()
        name_lower = name.lower()

        matches = []
        for pid, player in players.items():
            full_name = f"{player.get('first_name', '')} {player.get('last_name', '')}".lower()
            if name_lower in full_name:
                if position is None or player.get('position') == position:
                    player['player_id'] = pid
                    matches.append(player)

        return sorted(matches, key=lambda x: x.get('search_rank', 9999))[:20]

    # =========================================================================
    # Trending Data
    # =========================================================================

    def get_trending_players(self, sport: str = "nfl", type: str = "add",
                              hours: int = 24, limit: int = 25) -> List[Dict]:
        """Get trending players (adds or drops).

        Args:
            sport: Sport ('nfl')
            type: 'add' or 'drop'
            hours: Lookback period (default 24)
            limit: Max players to return

        Returns:
            List of trending player dicts with player_id and count
        """
        return self._get(f"players/{sport}/trending/{type}?lookback_hours={hours}&limit={limit}")

    # =========================================================================
    # User Data
    # =========================================================================

    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Get user info by username.

        Args:
            username: Sleeper username

        Returns:
            User dict or None
        """
        try:
            return self._get(f"user/{username}")
        except:
            return None

    def get_user_leagues(self, user_id: str, sport: str = "nfl",
                          season: int = 2025) -> List[Dict]:
        """Get all leagues for a user.

        Args:
            user_id: Sleeper user ID
            sport: Sport ('nfl')
            season: Season year

        Returns:
            List of league dicts
        """
        return self._get(f"user/{user_id}/leagues/{sport}/{season}")

    # =========================================================================
    # State/Season Info
    # =========================================================================

    def get_nfl_state(self) -> Dict:
        """Get current NFL state (week, season status).

        Returns:
            Dict with week, season, season_type, etc.
        """
        return self._get("state/nfl")

    # =========================================================================
    # Data Transformations
    # =========================================================================

    def get_rosters_with_players(self) -> List[Dict]:
        """Get rosters with full player information.

        Enriches roster data with player names and details.

        Returns:
            List of roster dicts with player details
        """
        rosters = self.get_rosters()
        users = {u['user_id']: u for u in self.get_users()}
        players = self.get_players()

        enriched = []
        for roster in rosters:
            owner = users.get(roster.get('owner_id'), {})

            roster_players = []
            for pid in roster.get('players', []):
                player = players.get(pid, {})
                roster_players.append({
                    'player_id': pid,
                    'name': f"{player.get('first_name', '')} {player.get('last_name', '')}".strip(),
                    'position': player.get('position'),
                    'team': player.get('team'),
                    'age': player.get('age'),
                    'is_starter': pid in roster.get('starters', []),
                    'is_taxi': pid in roster.get('taxi', []),
                    'is_reserve': pid in roster.get('reserve', [])
                })

            enriched.append({
                'roster_id': roster.get('roster_id'),
                'owner_id': roster.get('owner_id'),
                'display_name': owner.get('display_name'),
                'team_name': owner.get('metadata', {}).get('team_name'),
                'wins': roster.get('settings', {}).get('wins', 0),
                'losses': roster.get('settings', {}).get('losses', 0),
                'fpts': roster.get('settings', {}).get('fpts', 0) + roster.get('settings', {}).get('fpts_decimal', 0) / 100,
                'players': roster_players
            })

        return enriched

    def rosters_to_dataframe(self) -> pd.DataFrame:
        """Convert rosters to pandas DataFrame.

        Returns:
            DataFrame with one row per rostered player
        """
        rosters = self.get_rosters_with_players()

        rows = []
        for roster in rosters:
            for player in roster['players']:
                rows.append({
                    'roster_id': roster['roster_id'],
                    'owner': roster['display_name'],
                    'team_name': roster['team_name'],
                    'wins': roster['wins'],
                    'losses': roster['losses'],
                    'fpts': roster['fpts'],
                    'player_id': player['player_id'],
                    'player_name': player['name'],
                    'position': player['position'],
                    'nfl_team': player['team'],
                    'age': player['age'],
                    'is_starter': player['is_starter'],
                    'is_taxi': player['is_taxi']
                })

        return pd.DataFrame(rows)

    def get_trade_history(self, weeks: int = 18) -> List[Dict]:
        """Get all trades from the season.

        Args:
            weeks: Number of weeks to check

        Returns:
            List of trade transactions
        """
        trades = []
        for week in range(1, weeks + 1):
            try:
                transactions = self.get_transactions(week)
                for tx in transactions:
                    if tx.get('type') == 'trade' and tx.get('status') == 'complete':
                        trades.append(tx)
            except:
                continue

        return trades


class SleeperNeo4jLoader:
    """Load Sleeper league data into Neo4j graph database."""

    def __init__(self, driver, league_id: str):
        """
        Initialize loader.

        Args:
            driver: Neo4j driver
            league_id: Sleeper league ID
        """
        self.driver = driver
        self.client = SleeperClient(league_id)
        self.league_id = league_id

    def load_league(self):
        """Load league info into Neo4j."""
        league = self.client.get_league()

        with self.driver.session() as session:
            session.run("""
                MERGE (l:League {league_id: $league_id})
                SET l.name = $name,
                    l.season = $season,
                    l.status = $status,
                    l.total_rosters = $total_rosters,
                    l.roster_positions = $roster_positions,
                    l.updated_at = datetime()
            """, {
                'league_id': self.league_id,
                'name': league.get('name'),
                'season': league.get('season'),
                'status': league.get('status'),
                'total_rosters': league.get('total_rosters'),
                'roster_positions': str(league.get('roster_positions', []))
            })

        return league

    def load_users_and_rosters(self):
        """Load league users and their rosters."""
        users = {u['user_id']: u for u in self.client.get_users()}
        rosters = self.client.get_rosters()
        players = self.client.get_players()

        with self.driver.session() as session:
            # Create Fantasy Team nodes
            for roster in rosters:
                owner = users.get(roster.get('owner_id'), {})
                settings = roster.get('settings', {})

                session.run("""
                    MERGE (ft:FantasyTeam {roster_id: $roster_id, league_id: $league_id})
                    SET ft.owner_id = $owner_id,
                        ft.display_name = $display_name,
                        ft.team_name = $team_name,
                        ft.wins = $wins,
                        ft.losses = $losses,
                        ft.fpts = $fpts,
                        ft.updated_at = datetime()

                    WITH ft
                    MATCH (l:League {league_id: $league_id})
                    MERGE (ft)-[:IN_LEAGUE]->(l)
                """, {
                    'roster_id': roster.get('roster_id'),
                    'league_id': self.league_id,
                    'owner_id': roster.get('owner_id'),
                    'display_name': owner.get('display_name'),
                    'team_name': owner.get('metadata', {}).get('team_name'),
                    'wins': settings.get('wins', 0),
                    'losses': settings.get('losses', 0),
                    'fpts': settings.get('fpts', 0) + settings.get('fpts_decimal', 0) / 100
                })

                # Link players to fantasy team
                for player_id in roster.get('players', []):
                    player = players.get(player_id, {})
                    if not player:
                        continue

                    full_name = f"{player.get('first_name', '')} {player.get('last_name', '')}".strip()
                    is_starter = player_id in roster.get('starters', [])
                    is_taxi = player_id in roster.get('taxi', [])

                    session.run("""
                        MATCH (ft:FantasyTeam {roster_id: $roster_id, league_id: $league_id})

                        // Try to find existing player
                        OPTIONAL MATCH (p:Player)
                        WHERE toLower(p.name) = toLower($player_name)
                           OR p.sleeper_id = $sleeper_id

                        // Create sleeper player if not found
                        WITH ft, p
                        CALL apoc.do.when(
                            p IS NULL,
                            'CREATE (sp:SleeperPlayer {sleeper_id: sleeper_id, name: name, position: pos})
                             MERGE (sp)-[r:ROSTERED_BY {is_starter: starter, is_taxi: taxi}]->(ft)
                             RETURN sp',
                            'SET p.sleeper_id = sleeper_id
                             MERGE (p)-[r:ROSTERED_BY {is_starter: starter, is_taxi: taxi}]->(ft)
                             RETURN p',
                            {sleeper_id: $sleeper_id, name: $player_name, pos: $position,
                             starter: $is_starter, taxi: $is_taxi, ft: ft}
                        ) YIELD value
                        RETURN value
                    """, {
                        'roster_id': roster.get('roster_id'),
                        'league_id': self.league_id,
                        'sleeper_id': player_id,
                        'player_name': full_name,
                        'position': player.get('position'),
                        'is_starter': is_starter,
                        'is_taxi': is_taxi
                    })

        return len(rosters)

    def load_trades(self, weeks: int = 18):
        """Load trade history into Neo4j."""
        trades = self.client.get_trade_history(weeks)
        players = self.client.get_players()

        with self.driver.session() as session:
            for trade in trades:
                trade_id = trade.get('transaction_id')
                adds = trade.get('adds', {}) or {}
                drops = trade.get('drops', {}) or {}

                # Create Trade node
                session.run("""
                    MERGE (t:Trade {transaction_id: $trade_id})
                    SET t.league_id = $league_id,
                        t.status = $status,
                        t.created = datetime({epochMillis: $created})
                """, {
                    'trade_id': trade_id,
                    'league_id': self.league_id,
                    'status': trade.get('status'),
                    'created': trade.get('created', 0)
                })

                # Link players received in trade
                for player_id, roster_id in adds.items():
                    player = players.get(player_id, {})
                    name = f"{player.get('first_name', '')} {player.get('last_name', '')}".strip()

                    session.run("""
                        MATCH (t:Trade {transaction_id: $trade_id})
                        MATCH (ft:FantasyTeam {roster_id: $roster_id, league_id: $league_id})
                        OPTIONAL MATCH (p:Player)
                        WHERE toLower(p.name) = toLower($name) OR p.sleeper_id = $sleeper_id

                        WITH t, ft, COALESCE(p, null) as player

                        FOREACH (ignore IN CASE WHEN player IS NOT NULL THEN [1] ELSE [] END |
                            MERGE (player)-[:TRADED_IN]->(t)
                            MERGE (t)-[:RECEIVED_BY]->(ft)
                        )
                    """, {
                        'trade_id': trade_id,
                        'roster_id': roster_id,
                        'league_id': self.league_id,
                        'name': name,
                        'sleeper_id': player_id
                    })

        return len(trades)

    def load_all(self):
        """Load all league data into Neo4j."""
        results = {}

        results['league'] = self.load_league()
        results['rosters'] = self.load_users_and_rosters()
        results['trades'] = self.load_trades()

        return results

    def get_league_summary(self) -> Dict:
        """Get comprehensive league summary.

        Returns:
            Dict with league info, standings, and roster summaries
        """
        league = self.get_league()
        rosters = self.get_rosters()
        users = {u['user_id']: u for u in self.get_users()}
        state = self.get_nfl_state()

        standings = []
        for roster in rosters:
            owner = users.get(roster.get('owner_id'), {})
            settings = roster.get('settings', {})

            standings.append({
                'roster_id': roster.get('roster_id'),
                'owner': owner.get('display_name'),
                'team_name': owner.get('metadata', {}).get('team_name'),
                'wins': settings.get('wins', 0),
                'losses': settings.get('losses', 0),
                'fpts': settings.get('fpts', 0) + settings.get('fpts_decimal', 0) / 100,
                'fpts_against': settings.get('fpts_against', 0) + settings.get('fpts_against_decimal', 0) / 100,
                'roster_count': len(roster.get('players', []))
            })

        standings.sort(key=lambda x: (-x['wins'], -x['fpts']))

        return {
            'league_name': league.get('name'),
            'season': league.get('season'),
            'status': league.get('status'),
            'current_week': state.get('week'),
            'total_rosters': league.get('total_rosters'),
            'scoring_settings': league.get('scoring_settings'),
            'roster_positions': league.get('roster_positions'),
            'standings': standings
        }
