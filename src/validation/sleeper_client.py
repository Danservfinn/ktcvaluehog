"""
Sleeper API Client for Dynasty League Analysis

Integrates with Sleeper's free API to pull:
- Trade transactions from dynasty leagues
- Roster compositions
- Manager performance data
"""

import requests
import json
import time
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SleeperClient:
    """Client for Sleeper Fantasy Football API."""

    BASE_URL = "https://api.sleeper.app/v1"
    CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "sleeper"

    def __init__(self, cache_enabled: bool = True):
        self.cache_enabled = cache_enabled
        self.cache_dir = self.CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._players_cache = None
        self._rate_limit_delay = 0.5  # Be nice to the API

    def _get(self, endpoint: str) -> Optional[Dict]:
        """Make GET request with caching and rate limiting."""
        cache_file = self.cache_dir / f"{endpoint.replace('/', '_')}.json"

        # Check cache first
        if self.cache_enabled and cache_file.exists():
            cache_age = time.time() - cache_file.stat().st_mtime
            if cache_age < 3600:  # 1 hour cache
                with open(cache_file) as f:
                    return json.load(f)

        # Make request
        url = f"{self.BASE_URL}/{endpoint}"
        try:
            time.sleep(self._rate_limit_delay)
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()

            # Cache response
            if self.cache_enabled and data:
                with open(cache_file, 'w') as f:
                    json.dump(data, f)

            return data
        except requests.RequestException as e:
            logger.error(f"API request failed: {e}")
            return None

    def get_all_players(self) -> Dict[str, Dict]:
        """Get all NFL players from Sleeper."""
        if self._players_cache:
            return self._players_cache

        logger.info("Fetching all players from Sleeper...")
        players = self._get("players/nfl")
        if players:
            self._players_cache = players
            logger.info(f"Loaded {len(players)} players")
        return players or {}

    def get_user(self, username: str) -> Optional[Dict]:
        """Get user info by username."""
        return self._get(f"user/{username}")

    def get_user_leagues(self, user_id: str, season: int = 2024) -> List[Dict]:
        """Get all leagues for a user in a season."""
        return self._get(f"user/{user_id}/leagues/nfl/{season}") or []

    def get_league(self, league_id: str) -> Optional[Dict]:
        """Get league details."""
        return self._get(f"league/{league_id}")

    def get_league_users(self, league_id: str) -> List[Dict]:
        """Get all users in a league."""
        return self._get(f"league/{league_id}/users") or []

    def get_league_rosters(self, league_id: str) -> List[Dict]:
        """Get all rosters in a league."""
        return self._get(f"league/{league_id}/rosters") or []

    def get_league_transactions(self, league_id: str, week: int) -> List[Dict]:
        """Get transactions for a specific week."""
        return self._get(f"league/{league_id}/transactions/{week}") or []

    def get_all_league_transactions(self, league_id: str) -> List[Dict]:
        """Get all transactions for entire season."""
        all_transactions = []
        for week in range(1, 19):  # Weeks 1-18
            txns = self.get_league_transactions(league_id, week)
            all_transactions.extend(txns)
        return all_transactions

    def get_league_matchups(self, league_id: str, week: int) -> List[Dict]:
        """Get matchups for a specific week."""
        return self._get(f"league/{league_id}/matchups/{week}") or []


class DynastyLeagueAnalyzer:
    """Analyze dynasty league trades and manager performance."""

    def __init__(self):
        self.client = SleeperClient()
        self.players = {}

    def load_players(self):
        """Load player database."""
        self.players = self.client.get_all_players()

    def get_player_name(self, player_id: str) -> str:
        """Get player name from ID."""
        if not self.players:
            self.load_players()
        player = self.players.get(player_id, {})
        return player.get('full_name', f'Unknown ({player_id})')

    def get_player_position(self, player_id: str) -> str:
        """Get player position from ID."""
        if not self.players:
            self.load_players()
        player = self.players.get(player_id, {})
        return player.get('position', 'UNK')

    def analyze_league_trades(self, league_id: str) -> List[Dict]:
        """Analyze all trades in a league."""
        logger.info(f"Analyzing trades for league {league_id}")

        transactions = self.client.get_all_league_transactions(league_id)
        trades = [t for t in transactions if t.get('type') == 'trade']

        analyzed_trades = []
        for trade in trades:
            analyzed = self._analyze_trade(trade)
            if analyzed:
                analyzed_trades.append(analyzed)

        logger.info(f"Found {len(analyzed_trades)} trades")
        return analyzed_trades

    def _analyze_trade(self, trade: Dict) -> Optional[Dict]:
        """Analyze a single trade transaction."""
        if trade.get('status') != 'complete':
            return None

        roster_ids = trade.get('roster_ids', [])
        if len(roster_ids) != 2:
            return None  # Only analyze 2-team trades

        adds = trade.get('adds', {}) or {}
        drops = trade.get('drops', {}) or {}
        draft_picks = trade.get('draft_picks', []) or []

        # Organize by roster
        side_a = {'roster_id': roster_ids[0], 'players': [], 'picks': []}
        side_b = {'roster_id': roster_ids[1], 'players': [], 'picks': []}

        for player_id, roster_id in adds.items():
            player_info = {
                'id': player_id,
                'name': self.get_player_name(player_id),
                'position': self.get_player_position(player_id)
            }
            if roster_id == roster_ids[0]:
                side_a['players'].append(player_info)
            else:
                side_b['players'].append(player_info)

        for pick in draft_picks:
            pick_info = {
                'season': pick.get('season'),
                'round': pick.get('round'),
                'original_owner': pick.get('owner_id')
            }
            if pick.get('owner_id') == roster_ids[0]:
                side_a['picks'].append(pick_info)
            else:
                side_b['picks'].append(pick_info)

        return {
            'transaction_id': trade.get('transaction_id'),
            'timestamp': trade.get('created'),
            'week': trade.get('leg'),
            'side_a': side_a,
            'side_b': side_b
        }

    def calculate_manager_performance(self, league_id: str) -> Dict[int, Dict]:
        """Calculate performance metrics for each manager."""
        rosters = self.client.get_league_rosters(league_id)
        users = self.client.get_league_users(league_id)

        # Map roster_id to user
        roster_to_user = {}
        for roster in rosters:
            roster_to_user[roster['roster_id']] = roster.get('owner_id')

        user_names = {u['user_id']: u.get('display_name', 'Unknown') for u in users}

        # Calculate metrics
        performance = {}
        for roster in rosters:
            roster_id = roster['roster_id']
            settings = roster.get('settings', {})

            wins = settings.get('wins', 0)
            losses = settings.get('losses', 0)
            ties = settings.get('ties', 0)
            total_games = wins + losses + ties

            fpts = settings.get('fpts', 0) + settings.get('fpts_decimal', 0) / 100
            fpts_against = settings.get('fpts_against', 0) + settings.get('fpts_against_decimal', 0) / 100

            performance[roster_id] = {
                'roster_id': roster_id,
                'owner_id': roster.get('owner_id'),
                'display_name': user_names.get(roster.get('owner_id'), 'Unknown'),
                'wins': wins,
                'losses': losses,
                'win_pct': wins / total_games if total_games > 0 else 0,
                'points_for': fpts,
                'points_against': fpts_against,
                'point_differential': fpts - fpts_against
            }

        return performance

    def identify_sharp_managers(self, league_id: str, min_win_pct: float = 0.55) -> List[Dict]:
        """Identify high-performing managers."""
        performance = self.calculate_manager_performance(league_id)

        sharp = []
        for roster_id, metrics in performance.items():
            if metrics['win_pct'] >= min_win_pct:
                sharp.append(metrics)

        return sorted(sharp, key=lambda x: x['win_pct'], reverse=True)


class TradeValueValidator:
    """Validate model recommendations against actual trade data."""

    def __init__(self, ktc_values: Dict[str, float]):
        self.ktc_values = ktc_values  # player_name -> ktc_value
        self.analyzer = DynastyLeagueAnalyzer()

    def evaluate_trade(self, trade: Dict) -> Dict:
        """Evaluate a trade using our model values."""
        side_a_value = 0
        side_b_value = 0

        for player in trade['side_a']['players']:
            value = self.ktc_values.get(player['name'], 0)
            side_a_value += value
            player['ktc_value'] = value

        for player in trade['side_b']['players']:
            value = self.ktc_values.get(player['name'], 0)
            side_b_value += value
            player['ktc_value'] = value

        # Add draft pick values (approximate)
        pick_values = {1: 5000, 2: 2500, 3: 1000, 4: 500}
        for pick in trade['side_a']['picks']:
            side_a_value += pick_values.get(pick['round'], 250)
        for pick in trade['side_b']['picks']:
            side_b_value += pick_values.get(pick['round'], 250)

        return {
            'trade': trade,
            'side_a_value': side_a_value,
            'side_b_value': side_b_value,
            'value_difference': side_a_value - side_b_value,
            'winner': 'side_a' if side_a_value > side_b_value else 'side_b' if side_b_value > side_a_value else 'even'
        }

    def validate_against_sharp_managers(self, league_id: str) -> Dict:
        """Check if sharp managers trade in agreement with our model."""
        trades = self.analyzer.analyze_league_trades(league_id)
        sharp = self.analyzer.identify_sharp_managers(league_id)
        sharp_roster_ids = {m['roster_id'] for m in sharp}

        agreements = 0
        disagreements = 0

        for trade in trades:
            evaluation = self.evaluate_trade(trade)
            winner = evaluation['winner']

            side_a_sharp = trade['side_a']['roster_id'] in sharp_roster_ids
            side_b_sharp = trade['side_b']['roster_id'] in sharp_roster_ids

            if winner == 'side_a' and side_a_sharp:
                agreements += 1
            elif winner == 'side_b' and side_b_sharp:
                agreements += 1
            elif winner == 'side_a' and side_b_sharp:
                disagreements += 1
            elif winner == 'side_b' and side_a_sharp:
                disagreements += 1

        total = agreements + disagreements
        return {
            'agreements': agreements,
            'disagreements': disagreements,
            'total_evaluated': total,
            'agreement_rate': agreements / total if total > 0 else 0
        }


# Example expert/high-stakes league IDs to analyze
EXPERT_LEAGUES = [
    # Add known dynasty league IDs here
    # These should be public leagues or leagues you have access to
]


if __name__ == "__main__":
    # Test the client
    client = SleeperClient()

    # Get all players
    players = client.get_all_players()
    print(f"Loaded {len(players)} players")

    # Sample: Get a user's leagues
    # user = client.get_user("your_username")
    # if user:
    #     leagues = client.get_user_leagues(user['user_id'], 2024)
    #     print(f"Found {len(leagues)} leagues")
