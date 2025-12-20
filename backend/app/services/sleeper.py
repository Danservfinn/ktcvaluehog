"""Sleeper API client service."""

import httpx
from typing import Optional
from functools import lru_cache

SLEEPER_API_BASE = "https://api.sleeper.app/v1"


class SleeperClient:
    """Client for Sleeper API."""

    def __init__(self):
        self.base_url = SLEEPER_API_BASE
        self._player_cache: dict = {}

    async def _get(self, endpoint: str) -> dict | list | None:
        """Make GET request to Sleeper API."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{self.base_url}{endpoint}")
            if response.status_code == 200:
                return response.json()
            return None

    # === User Endpoints ===

    async def get_user(self, username: str) -> Optional[dict]:
        """Get user by username."""
        return await self._get(f"/user/{username}")

    async def get_user_leagues(
        self, user_id: str, sport: str = "nfl", season: str = "2025"
    ) -> list[dict]:
        """Get all leagues for a user."""
        result = await self._get(f"/user/{user_id}/leagues/{sport}/{season}")
        return result or []

    # === League Endpoints ===

    async def get_league(self, league_id: str) -> Optional[dict]:
        """Get league details."""
        return await self._get(f"/league/{league_id}")

    async def get_rosters(self, league_id: str) -> list[dict]:
        """Get all rosters in a league."""
        result = await self._get(f"/league/{league_id}/rosters")
        return result or []

    async def get_users(self, league_id: str) -> list[dict]:
        """Get all users in a league."""
        result = await self._get(f"/league/{league_id}/users")
        return result or []

    async def get_matchups(self, league_id: str, week: int) -> list[dict]:
        """Get matchups for a specific week."""
        result = await self._get(f"/league/{league_id}/matchups/{week}")
        return result or []

    async def get_transactions(
        self, league_id: str, week: int
    ) -> list[dict]:
        """Get transactions for a specific week."""
        result = await self._get(f"/league/{league_id}/transactions/{week}")
        return result or []

    async def get_traded_picks(self, league_id: str) -> list[dict]:
        """Get all traded draft picks."""
        result = await self._get(f"/league/{league_id}/traded_picks")
        return result or []

    async def get_winners_bracket(self, league_id: str) -> list[dict]:
        """Get playoff winners bracket."""
        result = await self._get(f"/league/{league_id}/winners_bracket")
        return result or []

    async def get_losers_bracket(self, league_id: str) -> list[dict]:
        """Get playoff losers bracket."""
        result = await self._get(f"/league/{league_id}/losers_bracket")
        return result or []

    # === Draft Endpoints ===

    async def get_drafts(self, league_id: str) -> list[dict]:
        """Get all drafts for a league."""
        result = await self._get(f"/league/{league_id}/drafts")
        return result or []

    async def get_draft(self, draft_id: str) -> Optional[dict]:
        """Get draft details."""
        return await self._get(f"/draft/{draft_id}")

    async def get_draft_picks(self, draft_id: str) -> list[dict]:
        """Get all picks in a draft."""
        result = await self._get(f"/draft/{draft_id}/picks")
        return result or []

    # === Player Endpoints ===

    async def get_all_players(self) -> dict:
        """Get all NFL players (cached heavily - ~5MB response)."""
        if not self._player_cache:
            result = await self._get("/players/nfl")
            if result:
                self._player_cache = result
        return self._player_cache

    async def get_trending_players(
        self,
        sport: str = "nfl",
        trend_type: str = "add",  # add or drop
        lookback_hours: int = 24,
        limit: int = 25,
    ) -> list[dict]:
        """Get trending players."""
        result = await self._get(
            f"/players/{sport}/trending/{trend_type}?lookback_hours={lookback_hours}&limit={limit}"
        )
        return result or []

    # === State Endpoint ===

    async def get_nfl_state(self) -> Optional[dict]:
        """Get current NFL state (week, season, etc.)."""
        return await self._get("/state/nfl")

    # === Helper Methods ===

    async def get_full_league_data(self, league_id: str) -> dict:
        """Fetch all league data in parallel."""
        import asyncio

        league, rosters, users, traded_picks, state = await asyncio.gather(
            self.get_league(league_id),
            self.get_rosters(league_id),
            self.get_users(league_id),
            self.get_traded_picks(league_id),
            self.get_nfl_state(),
        )

        # Get current week matchups
        current_week = state.get("week", 1) if state else 1
        matchups = await self.get_matchups(league_id, current_week)

        # Build user map
        user_map = {u["user_id"]: u for u in users}

        return {
            "league": league,
            "rosters": rosters,
            "users": users,
            "user_map": user_map,
            "traded_picks": traded_picks,
            "matchups": matchups,
            "current_week": current_week,
            "state": state,
        }

    def get_scoring_type(self, scoring_settings: dict) -> str:
        """Determine scoring type from settings."""
        rec_pts = scoring_settings.get("rec", 0)
        if rec_pts >= 1:
            return "ppr"
        elif rec_pts >= 0.5:
            return "half_ppr"
        return "standard"

    def is_dynasty_league(self, league: dict) -> bool:
        """Check if league is dynasty format."""
        settings = league.get("settings", {})
        # Dynasty leagues typically have taxi squads or type = 2
        return (
            settings.get("type", 0) == 2
            or league.get("settings", {}).get("taxi_slots", 0) > 0
            or "dynasty" in league.get("name", "").lower()
        )


# Singleton instance
_sleeper_client: Optional[SleeperClient] = None


def get_sleeper_client() -> SleeperClient:
    """Get or create Sleeper client instance."""
    global _sleeper_client
    if _sleeper_client is None:
        _sleeper_client = SleeperClient()
    return _sleeper_client
