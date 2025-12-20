"""League analysis API endpoints."""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from ..models.league import (
    LeagueConnectRequest,
    LeagueConnectResponse,
    LeagueSelectRequest,
    LeagueAnalysis,
    SleeperLeague,
    RosterAnalysis,
    PowerRanking,
    LineupOptimization,
)
from ..services.sleeper import get_sleeper_client
from ..services.league_analysis import get_league_analyzer

router = APIRouter(prefix="/api/v1/league", tags=["league"])


@router.post("/connect", response_model=LeagueConnectResponse)
async def connect_sleeper_account(request: LeagueConnectRequest):
    """
    Connect a Sleeper account and fetch all leagues.

    Returns user info and list of dynasty leagues.
    """
    client = get_sleeper_client()

    # Get user by username
    user = await client.get_user(request.sleeper_username)
    if not user:
        raise HTTPException(
            status_code=404,
            detail=f"Sleeper user '{request.sleeper_username}' not found"
        )

    user_id = user.get("user_id")
    display_name = user.get("display_name", request.sleeper_username)

    # Fetch all NFL leagues for current season
    leagues = await client.get_user_leagues(user_id, "nfl", "2025")

    # Filter to dynasty leagues and convert to response model
    dynasty_leagues = []
    for league in leagues:
        # Check if dynasty
        if client.is_dynasty_league(league):
            dynasty_leagues.append(SleeperLeague(
                league_id=league["league_id"],
                name=league.get("name", "Unknown League"),
                season=league.get("season", "2025"),
                status=league.get("status", "unknown"),
                total_rosters=league.get("total_rosters", 12),
                roster_positions=league.get("roster_positions", []),
                scoring_settings=league.get("scoring_settings", {}),
                settings=league.get("settings", {}),
            ))

    return LeagueConnectResponse(
        user_id=user_id,
        username=display_name,
        leagues=dynasty_leagues,
    )


@router.get("/{league_id}/analysis", response_model=LeagueAnalysis)
async def analyze_league(
    league_id: str,
    roster_id: Optional[int] = Query(None, description="Your roster ID (optional)"),
):
    """
    Get comprehensive league analysis.

    Returns:
    - Power rankings (KTC + ML-projected)
    - Championship probability simulation
    - Dynasty health score breakdown
    - Trade radar with suggestions
    - Buy low / sell high candidates
    """
    analyzer = get_league_analyzer()

    try:
        analysis = await analyzer.analyze_league(league_id, roster_id)
        return analysis
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze league: {str(e)}"
        )


@router.get("/{league_id}/power-rankings", response_model=list[PowerRanking])
async def get_power_rankings(league_id: str):
    """
    Get league power rankings.

    Returns teams ranked by championship probability and dynasty value.
    """
    analyzer = get_league_analyzer()

    try:
        analysis = await analyzer.analyze_league(league_id)
        return analysis.power_rankings
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get power rankings: {str(e)}"
        )


@router.get("/{league_id}/roster/{roster_id}", response_model=RosterAnalysis)
async def get_roster_analysis(league_id: str, roster_id: int):
    """
    Get detailed analysis for a specific roster.

    Returns:
    - Player breakdowns with projections
    - Positional strength grades
    - Age analysis and peak windows
    - Draft capital inventory
    """
    analyzer = get_league_analyzer()

    try:
        analysis = await analyzer.analyze_league(league_id, roster_id)

        roster = next(
            (r for r in [analysis.your_analysis] if r.roster_id == roster_id),
            None
        )

        if not roster:
            # Check other rosters in power rankings context
            full_analysis = await analyzer.analyze_league(league_id)
            # Rerun to get specific roster
            roster = next(
                (pr for pr in full_analysis.power_rankings if pr.roster_id == roster_id),
                None
            )

        if not roster:
            raise HTTPException(
                status_code=404,
                detail=f"Roster {roster_id} not found in league"
            )

        return analysis.your_analysis

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze roster: {str(e)}"
        )


@router.get("/{league_id}/trades")
async def get_trade_suggestions(
    league_id: str,
    roster_id: Optional[int] = Query(None, description="Your roster ID"),
):
    """
    Get trade suggestions and partner analysis.

    Returns:
    - Best trade partners ranked by compatibility
    - Specific trade suggestions with value analysis
    - Win-win scores and rationale
    """
    analyzer = get_league_analyzer()

    try:
        analysis = await analyzer.analyze_league(league_id, roster_id)

        return {
            "trade_partners": analysis.trade_partners,
            "top_suggestions": analysis.top_trade_suggestions,
            "buy_low_targets": analysis.buy_low_targets,
            "sell_high_candidates": analysis.sell_high_candidates,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get trade suggestions: {str(e)}"
        )


@router.get("/{league_id}/dynasty-health")
async def get_dynasty_health(
    league_id: str,
    roster_id: Optional[int] = Query(None, description="Your roster ID"),
):
    """
    Get dynasty health score breakdown.

    Returns:
    - Total score (0-100)
    - Component scores (age, peak overlap, injury, positions, picks)
    - Strengths and weaknesses
    - Recommendations
    """
    analyzer = get_league_analyzer()

    try:
        analysis = await analyzer.analyze_league(league_id, roster_id)
        return analysis.your_dynasty_health
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get dynasty health: {str(e)}"
        )


@router.get("/{league_id}/championship-odds")
async def get_championship_odds(
    league_id: str,
    roster_id: Optional[int] = Query(None, description="Your roster ID"),
):
    """
    Get championship probability simulation results.

    Returns:
    - Playoff/bye/championship probabilities
    - Seed distribution
    - Expected wins and points
    - Best/worst/likely records
    """
    analyzer = get_league_analyzer()

    try:
        analysis = await analyzer.analyze_league(league_id, roster_id)
        return analysis.your_championship_odds
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to simulate championship: {str(e)}"
        )


@router.get("/{league_id}/matchups/{week}")
async def get_weekly_matchups(league_id: str, week: int):
    """
    Get matchups for a specific week.

    Returns matchup data from Sleeper API.
    """
    client = get_sleeper_client()

    try:
        matchups = await client.get_matchups(league_id, week)
        return {"week": week, "matchups": matchups}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get matchups: {str(e)}"
        )


@router.get("/{league_id}/state")
async def get_league_state(league_id: str):
    """
    Get current NFL state and league info.

    Returns current week, season, and league details.
    """
    client = get_sleeper_client()

    try:
        league = await client.get_league(league_id)
        state = await client.get_nfl_state()

        if not league:
            raise HTTPException(status_code=404, detail="League not found")

        return {
            "league": league,
            "nfl_state": state,
            "current_week": state.get("week", 1) if state else 1,
            "season": state.get("season", "2025") if state else "2025",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get league state: {str(e)}"
        )
