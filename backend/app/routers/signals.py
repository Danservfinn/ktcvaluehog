"""Edge signals and analysis endpoints."""

from fastapi import APIRouter, Query
from typing import Optional

from ..database import get_db
from ..models.player import Position, Signal, PlayerSummary
from ..models.response import PaginatedResponse

router = APIRouter(prefix="/signals", tags=["Signals"])


@router.get("/edge", response_model=PaginatedResponse[dict])
async def get_edge_signals(
    signal: Optional[Signal] = Query(None, description="Filter by signal type"),
    position: Optional[Position] = None,
    min_edge: Optional[float] = Query(None, description="Minimum edge score %"),
    max_edge: Optional[float] = Query(None, description="Maximum edge score %"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Get players with buy/sell edge signals."""
    db = get_db()

    where_clauses = ["p.edge_score IS NOT NULL"]
    params = {}

    if signal:
        where_clauses.append("p.signal = $signal")
        params["signal"] = signal.value

    if position:
        where_clauses.append("p.position = $position")
        params["position"] = position.value

    if min_edge is not None:
        where_clauses.append("p.edge_score >= $min_edge")
        params["min_edge"] = min_edge

    if max_edge is not None:
        where_clauses.append("p.edge_score <= $max_edge")
        params["max_edge"] = max_edge

    where_clause = " AND ".join(where_clauses)

    # Count
    count_query = f"""
        MATCH (p:Player)
        WHERE {where_clause}
        RETURN count(p) as total
    """
    count_result = await db.execute(count_query, params)
    total = count_result[0]["total"] if count_result else 0

    # Data - sort by absolute edge score (strongest signals first)
    data_query = f"""
        MATCH (p:Player)
        WHERE {where_clause}
        RETURN p.gsis_id as player_id, p.name as name, p.position as position,
               p.team as team, p.age as age, p.ktc_value as ktc_value,
               p.predicted_value as predicted_value, p.edge_score as edge_score,
               p.signal as signal
        ORDER BY abs(p.edge_score) DESC
        SKIP $offset LIMIT $limit
    """
    params["offset"] = offset
    params["limit"] = limit

    results = await db.execute(data_query, params)

    return PaginatedResponse(
        data=results,
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + limit) < total,
    )


@router.get("/buy-targets", response_model=PaginatedResponse[dict])
async def get_buy_targets(
    position: Optional[Position] = None,
    min_edge: float = Query(10.0, description="Minimum undervalue %"),
    limit: int = Query(25, ge=1, le=100),
):
    """Get undervalued players (BUY signals)."""
    db = get_db()

    where_clauses = ["p.edge_score >= $min_edge", "p.signal IN ['BUY', 'STRONG_BUY']"]
    params = {"min_edge": min_edge}

    if position:
        where_clauses.append("p.position = $position")
        params["position"] = position.value

    where_clause = " AND ".join(where_clauses)

    query = f"""
        MATCH (p:Player)
        WHERE {where_clause}
        RETURN p.gsis_id as player_id, p.name as name, p.position as position,
               p.team as team, p.age as age, p.ktc_value as ktc_value,
               p.predicted_value as predicted_value, p.edge_score as edge_score,
               p.signal as signal
        ORDER BY p.edge_score DESC
        LIMIT $limit
    """
    params["limit"] = limit

    results = await db.execute(query, params)

    return PaginatedResponse(data=results, total=len(results), limit=limit, offset=0)


@router.get("/sell-candidates", response_model=PaginatedResponse[dict])
async def get_sell_candidates(
    position: Optional[Position] = None,
    max_edge: float = Query(-10.0, description="Maximum overvalue % (negative)"),
    limit: int = Query(25, ge=1, le=100),
):
    """Get overvalued players (SELL signals)."""
    db = get_db()

    where_clauses = ["p.edge_score <= $max_edge", "p.signal IN ['SELL', 'STRONG_SELL']"]
    params = {"max_edge": max_edge}

    if position:
        where_clauses.append("p.position = $position")
        params["position"] = position.value

    where_clause = " AND ".join(where_clauses)

    query = f"""
        MATCH (p:Player)
        WHERE {where_clause}
        RETURN p.gsis_id as player_id, p.name as name, p.position as position,
               p.team as team, p.age as age, p.ktc_value as ktc_value,
               p.predicted_value as predicted_value, p.edge_score as edge_score,
               p.signal as signal
        ORDER BY p.edge_score ASC
        LIMIT $limit
    """
    params["limit"] = limit

    results = await db.execute(query, params)

    return PaginatedResponse(data=results, total=len(results), limit=limit, offset=0)


@router.get("/breakout-candidates", response_model=PaginatedResponse[dict])
async def get_breakout_candidates(
    position: Optional[Position] = None,
    max_age: int = Query(26, description="Maximum age for breakout candidates"),
    min_snap_pct: float = Query(30.0, description="Minimum snap percentage"),
    limit: int = Query(25, ge=1, le=100),
):
    """Get young players showing breakout potential."""
    db = get_db()

    where_clauses = [
        "p.age <= $max_age",
        "p.snap_percentage >= $min_snap_pct",
        "p.ktc_value IS NOT NULL",
    ]
    params = {"max_age": max_age, "min_snap_pct": min_snap_pct}

    if position:
        where_clauses.append("p.position = $position")
        params["position"] = position.value

    where_clause = " AND ".join(where_clauses)

    query = f"""
        MATCH (p:Player)
        WHERE {where_clause}
        RETURN p.gsis_id as player_id, p.name as name, p.position as position,
               p.team as team, p.age as age, p.ktc_value as ktc_value,
               p.snap_percentage as snap_pct, p.edge_score as edge_score,
               p.signal as signal, p.experience as experience
        ORDER BY p.snap_percentage DESC, p.edge_score DESC
        LIMIT $limit
    """
    params["limit"] = limit

    results = await db.execute(query, params)

    return PaginatedResponse(data=results, total=len(results), limit=limit, offset=0)


@router.get("/production-leaders", response_model=PaginatedResponse[dict])
async def get_production_leaders(
    position: Optional[Position] = None,
    stat: str = Query("ppg_ppr", regex="^(ppg_ppr|total_points|ppg_half|ppg_std)$"),
    limit: int = Query(25, ge=1, le=100),
):
    """Get 2025 season production leaders."""
    db = get_db()

    where_clauses = ["p.ppg_ppr IS NOT NULL"]
    params = {}

    if position:
        where_clauses.append("p.position = $position")
        params["position"] = position.value

    where_clause = " AND ".join(where_clauses)

    # Map stat to property
    stat_prop = {
        "ppg_ppr": "p.ppg_ppr",
        "total_points": "p.total_points_2025",
        "ppg_half": "p.ppg_half",
        "ppg_std": "p.ppg_std",
    }.get(stat, "p.ppg_ppr")

    query = f"""
        MATCH (p:Player)
        WHERE {where_clause}
        RETURN p.gsis_id as player_id, p.name as name, p.position as position,
               p.team as team, p.ktc_value as ktc_value,
               p.ppg_ppr as ppg_ppr, p.total_points_2025 as total_points,
               p.games_played_2025 as games, p.edge_score as edge_score
        ORDER BY {stat_prop} DESC
        LIMIT $limit
    """
    params["limit"] = limit

    results = await db.execute(query, params)

    return PaginatedResponse(data=results, total=len(results), limit=limit, offset=0)
