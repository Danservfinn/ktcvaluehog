"""
CollegeFootballData.com API Client
Fetches recruiting, player stats, team ratings, and draft data for dynasty analysis.

API Documentation: https://api.collegefootballdata.com/api/docs
"""

import os
import requests
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional, Any
from dotenv import load_dotenv
import time
import logging

load_dotenv()
logger = logging.getLogger(__name__)


class CFBDClient:
    """
    Client for CollegeFootballData.com API.

    Provides access to:
    - Player recruiting rankings (247Sports/Rivals composite)
    - College player statistics by season
    - Team ratings (SP+, talent composite)
    - NFL draft picks (links college to NFL)
    - Transfer portal data
    """

    BASE_URL = "https://api.collegefootballdata.com"

    # Fantasy-relevant positions
    FANTASY_POSITIONS = ["QB", "RB", "WR", "TE", "ATH"]

    # Conference tiers for competition adjustment
    CONFERENCE_TIERS = {
        "SEC": 1.15,
        "Big Ten": 1.12,
        "Big 12": 1.08,
        "ACC": 1.05,
        "Pac-12": 1.02,
        "Mountain West": 0.95,
        "American Athletic": 0.92,
        "Sun Belt": 0.90,
        "Mid-American": 0.88,
        "Conference USA": 0.85,
        "FBS Independents": 1.00
    }

    def __init__(self, api_key: str = None):
        """
        Initialize CFBD client.

        Args:
            api_key: CFBD API key. If not provided, reads from CFBD_API_KEY env var.
        """
        self.api_key = api_key or os.getenv("CFBD_API_KEY")
        if not self.api_key:
            raise ValueError(
                "CFBD API key required. Get one at https://collegefootballdata.com/key "
                "and set CFBD_API_KEY environment variable."
            )

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json"
        }
        self._request_count = 0
        self._last_request_time = 0

    def _rate_limit(self):
        """Implement rate limiting (10 requests/second max)."""
        current_time = time.time()
        elapsed = current_time - self._last_request_time
        if elapsed < 0.1:  # 100ms between requests
            time.sleep(0.1 - elapsed)
        self._last_request_time = time.time()
        self._request_count += 1

    def _get(self, endpoint: str, params: Dict = None) -> Any:
        """Make GET request to CFBD API."""
        self._rate_limit()
        url = f"{self.BASE_URL}{endpoint}"

        try:
            response = requests.get(url, headers=self.headers, params=params or {}, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"CFBD API error: {e.response.status_code} - {e.response.text}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"CFBD request failed: {e}")
            raise

    # =========================================================================
    # RECRUITING DATA
    # =========================================================================

    def get_recruiting_players(
        self,
        year: int,
        position: Optional[str] = None,
        classification: str = "HighSchool",
        state: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Get player recruiting rankings for a given year.

        Args:
            year: Recruiting class year (e.g., 2024)
            position: Position filter (QB, RB, WR, TE, ATH)
            classification: HighSchool, JUCO, or PrepSchool
            state: State abbreviation filter (e.g., "TX", "CA")

        Returns:
            DataFrame with recruiting data including:
            - name, position, height, weight
            - stars, rating, ranking
            - committedTo (college), state
        """
        params = {
            "year": year,
            "classification": classification
        }
        if position:
            params["position"] = position
        if state:
            params["state"] = state

        data = self._get("/recruiting/players", params)

        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data)
        df["recruiting_year"] = year
        df["classification"] = classification

        return df

    def get_team_recruiting(self, year: int) -> pd.DataFrame:
        """
        Get team recruiting class rankings.

        Args:
            year: Recruiting class year

        Returns:
            DataFrame with team recruiting rankings:
            - team, conference, rank, points
        """
        data = self._get("/recruiting/teams", {"year": year})

        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data)
        df["year"] = year

        return df

    def get_recruiting_groups(self, start_year: int = None, end_year: int = None) -> pd.DataFrame:
        """
        Get position group recruiting rankings.

        Args:
            start_year: Start year for range
            end_year: End year for range

        Returns:
            DataFrame with position group rankings by team
        """
        params = {}
        if start_year:
            params["startYear"] = start_year
        if end_year:
            params["endYear"] = end_year

        data = self._get("/recruiting/groups", params)
        return pd.DataFrame(data) if data else pd.DataFrame()

    # =========================================================================
    # PLAYER STATISTICS
    # =========================================================================

    def get_player_season_stats(
        self,
        year: int,
        category: str = "passing",
        conference: Optional[str] = None,
        team: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Get player season statistics.

        Args:
            year: Season year
            category: Stat category (passing, rushing, receiving, defensive)
            conference: Conference filter
            team: Team filter

        Returns:
            DataFrame with player stats for the category
        """
        params = {
            "year": year,
            "category": category
        }
        if conference:
            params["conference"] = conference
        if team:
            params["team"] = team

        data = self._get("/stats/player/season", params)

        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data)
        df["season"] = year
        df["category"] = category

        return df

    def get_player_usage(
        self,
        year: int,
        conference: Optional[str] = None,
        team: Optional[str] = None,
        position: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Get player usage metrics (PPA, success rate, etc.).

        Args:
            year: Season year
            conference: Conference filter
            team: Team filter
            position: Position filter

        Returns:
            DataFrame with advanced usage metrics
        """
        params = {"year": year}
        if conference:
            params["conference"] = conference
        if team:
            params["team"] = team
        if position:
            params["position"] = position

        data = self._get("/player/usage", params)
        return pd.DataFrame(data) if data else pd.DataFrame()

    def get_player_returning(self, year: int, team: Optional[str] = None) -> pd.DataFrame:
        """
        Get returning production metrics by team.

        Args:
            year: Season year
            team: Team filter

        Returns:
            DataFrame with returning production percentages
        """
        params = {"year": year}
        if team:
            params["team"] = team

        data = self._get("/player/returning", params)
        return pd.DataFrame(data) if data else pd.DataFrame()

    # =========================================================================
    # TEAM DATA
    # =========================================================================

    def get_sp_ratings(self, year: int) -> pd.DataFrame:
        """
        Get SP+ team ratings (Bill Connelly's advanced rating system).

        Args:
            year: Season year

        Returns:
            DataFrame with SP+ ratings:
            - team, conference, rating, offense.rating, defense.rating
            - specialTeams.rating, sos (strength of schedule)
        """
        data = self._get("/ratings/sp", {"year": year})

        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data)
        df["year"] = year

        return df

    def get_team_talent(self, year: int) -> pd.DataFrame:
        """
        Get team talent composite ratings.

        Args:
            year: Season year

        Returns:
            DataFrame with team talent scores based on recruiting
        """
        data = self._get("/talent", {"year": year})

        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data)
        df["year"] = year

        return df

    def get_teams(self, conference: Optional[str] = None) -> pd.DataFrame:
        """
        Get team information.

        Args:
            conference: Conference filter

        Returns:
            DataFrame with team info (name, conference, mascot, colors, etc.)
        """
        params = {}
        if conference:
            params["conference"] = conference

        data = self._get("/teams", params)
        return pd.DataFrame(data) if data else pd.DataFrame()

    def get_fbs_teams(self, year: Optional[int] = None) -> pd.DataFrame:
        """Get list of FBS teams for a given year."""
        params = {}
        if year:
            params["year"] = year

        data = self._get("/teams/fbs", params)
        return pd.DataFrame(data) if data else pd.DataFrame()

    # =========================================================================
    # NFL DRAFT DATA
    # =========================================================================

    def get_draft_picks(
        self,
        year: Optional[int] = None,
        college: Optional[str] = None,
        position: Optional[str] = None,
        nfl_team: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Get NFL draft picks (links college to NFL).

        Args:
            year: Draft year
            college: College team filter
            position: Position filter
            nfl_team: NFL team filter

        Returns:
            DataFrame with draft picks:
            - collegeTeam, nflTeam, year, round, pick
            - name, position, height, weight
            - preDraftRanking, preDraftPositionRanking
        """
        params = {}
        if year:
            params["year"] = year
        if college:
            params["college"] = college
        if position:
            params["position"] = position
        if nfl_team:
            params["nflTeam"] = nfl_team

        data = self._get("/draft/picks", params)
        return pd.DataFrame(data) if data else pd.DataFrame()

    def get_draft_teams(self) -> pd.DataFrame:
        """Get list of NFL teams for draft queries."""
        data = self._get("/draft/teams")
        return pd.DataFrame(data) if data else pd.DataFrame()

    def get_draft_positions(self) -> pd.DataFrame:
        """Get list of draft positions."""
        data = self._get("/draft/positions")
        return pd.DataFrame(data) if data else pd.DataFrame()

    # =========================================================================
    # TRANSFER PORTAL
    # =========================================================================

    def get_transfer_portal(self, year: int) -> pd.DataFrame:
        """
        Get transfer portal entries.

        Args:
            year: Transfer portal year

        Returns:
            DataFrame with transfer portal data:
            - firstName, lastName, position
            - origin, destination (if committed)
            - transferDate, rating, stars
        """
        data = self._get("/player/portal", {"year": year})

        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data)
        df["portal_year"] = year

        return df

    # =========================================================================
    # CONVENIENCE METHODS
    # =========================================================================

    def get_fantasy_recruits(
        self,
        years: List[int],
        min_stars: int = 3
    ) -> pd.DataFrame:
        """
        Get all fantasy-relevant recruits for multiple years.

        Args:
            years: List of recruiting years to fetch
            min_stars: Minimum star rating to include (default 3)

        Returns:
            Combined DataFrame with all recruits
        """
        all_recruits = []

        for year in years:
            for pos in self.FANTASY_POSITIONS:
                try:
                    df = self.get_recruiting_players(year, position=pos)
                    if not df.empty:
                        all_recruits.append(df)
                        logger.info(f"Fetched {len(df)} {pos} recruits from {year}")
                except Exception as e:
                    logger.warning(f"Failed to fetch {pos} recruits for {year}: {e}")

        if not all_recruits:
            return pd.DataFrame()

        combined = pd.concat(all_recruits, ignore_index=True)

        # Filter by star rating
        if "stars" in combined.columns:
            combined = combined[combined["stars"] >= min_stars]

        return combined

    def get_all_player_stats(
        self,
        year: int,
        categories: List[str] = None
    ) -> pd.DataFrame:
        """
        Get all player stats for a season across multiple categories.

        Args:
            year: Season year
            categories: List of categories (default: passing, rushing, receiving)

        Returns:
            Combined DataFrame with all stats
        """
        if categories is None:
            categories = ["passing", "rushing", "receiving"]

        all_stats = []

        for category in categories:
            try:
                df = self.get_player_season_stats(year, category=category)
                if not df.empty:
                    all_stats.append(df)
                    logger.info(f"Fetched {len(df)} {category} stats for {year}")
            except Exception as e:
                logger.warning(f"Failed to fetch {category} stats for {year}: {e}")

        if not all_stats:
            return pd.DataFrame()

        return pd.concat(all_stats, ignore_index=True)

    def get_prospect_with_draft_outcome(
        self,
        recruiting_years: List[int],
        include_undrafted: bool = False
    ) -> pd.DataFrame:
        """
        Get recruits with their eventual NFL draft outcomes.
        Useful for training prediction models.

        Args:
            recruiting_years: Years of recruiting classes to fetch
            include_undrafted: Whether to include players who weren't drafted

        Returns:
            DataFrame with recruiting + draft data merged
        """
        # Get recruits
        recruits = self.get_fantasy_recruits(recruiting_years)

        if recruits.empty:
            return pd.DataFrame()

        # Estimate draft years (typically 3-4 years after recruiting class)
        draft_years = list(range(min(recruiting_years) + 3, max(recruiting_years) + 5))

        # Get draft picks
        all_picks = []
        for year in draft_years:
            try:
                picks = self.get_draft_picks(year=year)
                if not picks.empty:
                    all_picks.append(picks)
            except Exception as e:
                logger.warning(f"Failed to fetch draft picks for {year}: {e}")

        if not all_picks:
            return recruits if include_undrafted else pd.DataFrame()

        draft_df = pd.concat(all_picks, ignore_index=True)

        # Merge on name (imperfect but usually works)
        merged = recruits.merge(
            draft_df[["name", "year", "round", "pick", "nflTeam", "collegeTeam"]],
            left_on="name",
            right_on="name",
            how="left" if include_undrafted else "inner",
            suffixes=("_recruit", "_draft")
        )

        # Add drafted flag
        merged["was_drafted"] = merged["round"].notna()

        return merged


# =============================================================================
# CLI TESTING
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    client = CFBDClient()

    # Test recruiting data
    print("\n=== Testing Recruiting Data ===")
    recruits = client.get_recruiting_players(2024, position="WR")
    print(f"2024 WR Recruits: {len(recruits)}")
    if not recruits.empty:
        print(recruits[["name", "stars", "rating", "committedTo"]].head())

    # Test player stats
    print("\n=== Testing Player Stats ===")
    stats = client.get_player_season_stats(2023, category="receiving")
    print(f"2023 Receiving Stats: {len(stats)}")
    if not stats.empty:
        print(stats[["player", "team", "stat", "statType"]].head())

    # Test SP+ ratings
    print("\n=== Testing SP+ Ratings ===")
    sp = client.get_sp_ratings(2023)
    print(f"2023 SP+ Ratings: {len(sp)}")
    if not sp.empty:
        print(sp[["team", "conference", "rating"]].head())

    # Test draft picks
    print("\n=== Testing Draft Picks ===")
    picks = client.get_draft_picks(year=2024)
    print(f"2024 Draft Picks: {len(picks)}")
    if not picks.empty:
        print(picks[["name", "position", "collegeTeam", "round", "pick"]].head())

    print(f"\n=== Total API Requests: {client._request_count} ===")
