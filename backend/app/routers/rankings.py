"""Dynasty rankings endpoints."""

from fastapi import APIRouter, Query
from typing import Optional

from ..database import get_db
from ..models.player import Position, PlayerSummary
from ..models.response import PaginatedResponse

router = APIRouter(prefix="/rankings", tags=["Rankings"])


@router.get("", response_model=PaginatedResponse[dict])
async def get_rankings(
    position: Optional[Position] = None,
    limit: int = Query(100, ge=1, le=500, description="Free: 100 max, Pro: 500"),
    offset: int = Query(0, ge=0),
    include_rookies: bool = Query(False, description="Include rookie draft picks (Elite only)"),
):
    """
    Get dynasty rankings ordered by KTC value.

    Free tier: Top 100 rankings
    Pro tier: Top 500 rankings
    Elite tier: All rankings + rookies
    """
    db = get_db()

    where_clauses = ["p.ktc_value IS NOT NULL"]
    params = {}

    if position:
        where_clauses.append("p.position = $position")
        params["position"] = position.value

    if not include_rookies:
        # Exclude players without team (likely rookies not yet drafted)
        where_clauses.append("p.team IS NOT NULL")

    where_clause = " AND ".join(where_clauses)

    # Count query
    count_query = f"""
        MATCH (p:Player)
        WHERE {where_clause}
        RETURN count(p) as total
    """
    count_result = await db.execute(count_query, params)
    total = count_result[0]["total"] if count_result else 0

    # Data query
    data_query = f"""
        MATCH (p:Player)
        WHERE {where_clause}
        RETURN p.gsis_id as player_id, p.name as name, p.position as position,
               p.team as team, p.age as age, p.ktc_value as ktc_value,
               p.ktc_rank as rank, p.ktc_positional_rank as positional_rank,
               p.ktc_trend as trend, p.production_edge_score as edge_score,
               p.signal as signal
        ORDER BY p.ktc_value DESC
        SKIP $offset LIMIT $limit
    """
    params["offset"] = offset
    params["limit"] = limit

    results = await db.execute(data_query, params)

    # Add ranking index if not present
    for i, r in enumerate(results):
        if r.get("rank") is None:
            r["rank"] = offset + i + 1

    return PaginatedResponse(
        data=results,
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + limit) < total,
    )


@router.get("/positional/{position}", response_model=PaginatedResponse[dict])
async def get_positional_rankings(
    position: Position,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Get rankings for a specific position."""
    db = get_db()

    query = """
        MATCH (p:Player)
        WHERE p.position = $position AND p.ktc_value IS NOT NULL
        RETURN p.gsis_id as player_id, p.name as name, p.position as position,
               p.team as team, p.age as age, p.ktc_value as ktc_value,
               p.ktc_positional_rank as positional_rank,
               p.production_edge_score as edge_score, p.signal as signal,
               p.ppg_ppr as ppg_ppr
        ORDER BY p.ktc_value DESC
        SKIP $offset LIMIT $limit
    """

    results = await db.execute(
        query, {"position": position.value, "offset": offset, "limit": limit}
    )

    # Add positional rank if not present
    for i, r in enumerate(results):
        if r.get("positional_rank") is None:
            r["positional_rank"] = offset + i + 1

    count_query = """
        MATCH (p:Player)
        WHERE p.position = $position AND p.ktc_value IS NOT NULL
        RETURN count(p) as total
    """
    count_result = await db.execute(count_query, {"position": position.value})
    total = count_result[0]["total"] if count_result else 0

    return PaginatedResponse(
        data=results, total=total, limit=limit, offset=offset, has_more=(offset + limit) < total
    )


@router.get("/risers", response_model=PaginatedResponse[dict])
async def get_risers(
    days: int = Query(7, ge=1, le=30, description="Time period for trend"),
    position: Optional[Position] = None,
    limit: int = Query(25, ge=1, le=100),
):
    """Get players with biggest value increases."""
    db = get_db()

    where_clauses = ["p.ktc_value IS NOT NULL", "p.ktc_trend > 0"]
    params = {}

    if position:
        where_clauses.append("p.position = $position")
        params["position"] = position.value

    where_clause = " AND ".join(where_clauses)

    query = f"""
        MATCH (p:Player)
        WHERE {where_clause}
        RETURN p.gsis_id as player_id, p.name as name, p.position as position,
               p.team as team, p.age as age, p.ktc_value as ktc_value,
               p.ktc_trend as trend_value, p.signal as signal
        ORDER BY p.ktc_trend DESC
        LIMIT $limit
    """
    params["limit"] = limit

    results = await db.execute(query, params)

    return PaginatedResponse(data=results, total=len(results), limit=limit, offset=0)


@router.get("/fallers", response_model=PaginatedResponse[dict])
async def get_fallers(
    days: int = Query(7, ge=1, le=30, description="Time period for trend"),
    position: Optional[Position] = None,
    limit: int = Query(25, ge=1, le=100),
):
    """Get players with biggest value decreases."""
    db = get_db()

    where_clauses = ["p.ktc_value IS NOT NULL", "p.ktc_trend < 0"]
    params = {}

    if position:
        where_clauses.append("p.position = $position")
        params["position"] = position.value

    where_clause = " AND ".join(where_clauses)

    query = f"""
        MATCH (p:Player)
        WHERE {where_clause}
        RETURN p.gsis_id as player_id, p.name as name, p.position as position,
               p.team as team, p.age as age, p.ktc_value as ktc_value,
               p.ktc_trend as trend_value, p.signal as signal
        ORDER BY p.ktc_trend ASC
        LIMIT $limit
    """
    params["limit"] = limit

    results = await db.execute(query, params)

    return PaginatedResponse(data=results, total=len(results), limit=limit, offset=0)


@router.get("/rookie-rankings", response_model=PaginatedResponse[dict])
async def get_rookie_rankings(
    position: Optional[Position] = None,
    draft_year: int = Query(2025, ge=2020, le=2026),
    limit: int = Query(50, ge=1, le=200),
):
    """Get rookie dynasty rankings (Elite only)."""
    db = get_db()

    where_clauses = ["p.ktc_value IS NOT NULL", "p.draft_year = $draft_year"]
    params = {"draft_year": draft_year}

    if position:
        where_clauses.append("p.position = $position")
        params["position"] = position.value

    where_clause = " AND ".join(where_clauses)

    query = f"""
        MATCH (p:Player)
        WHERE {where_clause}
        RETURN p.gsis_id as player_id, p.name as name, p.position as position,
               p.team as team, p.age as age, p.ktc_value as ktc_value,
               p.draft_round as draft_round, p.draft_pick as draft_pick,
               p.college as college, p.signal as signal
        ORDER BY p.ktc_value DESC
        LIMIT $limit
    """
    params["limit"] = limit

    results = await db.execute(query, params)

    # Add rookie rank
    for i, r in enumerate(results):
        r["rookie_rank"] = i + 1

    return PaginatedResponse(data=results, total=len(results), limit=limit, offset=0)
