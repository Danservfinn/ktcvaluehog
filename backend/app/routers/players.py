"""Player endpoints."""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from ..database import get_db
from ..models.player import (
    Player,
    PlayerSummary,
    PlayerComparison,
    Position,
    Signal,
    AthleticProfile,
    ContractInfo,
)
from ..models.response import APIResponse, PaginatedResponse

router = APIRouter(prefix="/players", tags=["Players"])


def _parse_player(row: dict) -> Player:
    """Parse Neo4j row into Player model."""
    # Parse athletic profile if available
    athletic = None
    if any(row.get(f) for f in ["forty_yard", "vertical", "broad_jump"]):
        athletic = AthleticProfile(
            forty_yard=row.get("forty_yard"),
            vertical=row.get("vertical"),
            broad_jump=row.get("broad_jump"),
            cone=row.get("cone"),
            shuttle=row.get("shuttle"),
            bench=row.get("bench"),
            height=row.get("height"),
            weight=row.get("weight"),
        )

    # Parse contract if available
    contract = None
    if row.get("apy"):
        contract = ContractInfo(
            apy=row.get("apy"),
            guaranteed=row.get("guaranteed"),
            years_remaining=row.get("years_remaining"),
        )

    return Player(
        player_id=row.get("gsis_id") or row.get("player_id") or "",
        sleeper_id=row.get("sleeper_id"),
        name=row.get("name") or row.get("full_name") or "",
        first_name=row.get("first_name"),
        last_name=row.get("last_name"),
        position=row.get("position"),
        team=row.get("team"),
        age=row.get("age"),
        experience=row.get("experience"),
        college=row.get("college"),
        draft_year=row.get("draft_year"),
        draft_round=row.get("draft_round"),
        draft_pick=row.get("draft_pick"),
        ktc_value=row.get("ktc_value"),
        ktc_rank=row.get("ktc_rank"),
        ktc_positional_rank=row.get("ktc_positional_rank"),
        ktc_trend=row.get("ktc_trend"),
        predicted_value=row.get("predicted_value"),
        edge_score=row.get("edge_score"),
        signal=row.get("signal"),
        athletic=athletic,
        contract=contract,
        total_snaps=row.get("total_snaps"),
        snap_percentage=row.get("snap_percentage"),
        injury_risk=row.get("injury_risk"),
        ppg_ppr=row.get("ppg_ppr"),
        total_points_2025=row.get("total_points_2025"),
        career_stage=row.get("career_stage"),
    )


@router.get("/search", response_model=PaginatedResponse[PlayerSummary])
async def search_players(
    position: Optional[Position] = None,
    team: Optional[str] = None,
    min_age: Optional[int] = Query(None, ge=18, le=50),
    max_age: Optional[int] = Query(None, ge=18, le=50),
    min_ktc: Optional[int] = Query(None, ge=0),
    max_ktc: Optional[int] = Query(None, ge=0),
    signal: Optional[Signal] = None,
    q: Optional[str] = Query(None, description="Name search"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("ktc_value", regex="^(ktc_value|age|name|edge_score)$"),
    sort_desc: bool = True,
):
    """Search and filter players."""
    db = get_db()

    # Build dynamic query
    where_clauses = []
    params = {}

    if position:
        where_clauses.append("p.position = $position")
        params["position"] = position.value

    if team:
        where_clauses.append("p.team = $team")
        params["team"] = team.upper()

    if min_age:
        where_clauses.append("p.age >= $min_age")
        params["min_age"] = min_age

    if max_age:
        where_clauses.append("p.age <= $max_age")
        params["max_age"] = max_age

    if min_ktc:
        where_clauses.append("p.ktc_value >= $min_ktc")
        params["min_ktc"] = min_ktc

    if max_ktc:
        where_clauses.append("p.ktc_value <= $max_ktc")
        params["max_ktc"] = max_ktc

    if signal:
        where_clauses.append("p.signal = $signal")
        params["signal"] = signal.value

    if q:
        where_clauses.append("toLower(p.name) CONTAINS toLower($q)")
        params["q"] = q

    where_clause = " AND ".join(where_clauses) if where_clauses else "TRUE"
    sort_field = {"ktc_value": "p.ktc_value", "age": "p.age", "name": "p.name", "edge_score": "p.edge_score"}.get(sort_by, "p.ktc_value")
    sort_order = "DESC" if sort_desc else "ASC"

    # Count query
    count_query = f"""
        MATCH (p:Player)
        WHERE {where_clause} AND p.ktc_value IS NOT NULL
        RETURN count(p) as total
    """

    # Data query
    data_query = f"""
        MATCH (p:Player)
        WHERE {where_clause} AND p.ktc_value IS NOT NULL
        RETURN p.gsis_id as player_id, p.name as name, p.position as position,
               p.team as team, p.age as age, p.ktc_value as ktc_value, p.signal as signal
        ORDER BY {sort_field} {sort_order}
        SKIP $offset LIMIT $limit
    """
    params["offset"] = offset
    params["limit"] = limit

    # Execute both
    count_result = await db.execute(count_query, {k: v for k, v in params.items() if k not in ["offset", "limit"]})
    total = count_result[0]["total"] if count_result else 0

    results = await db.execute(data_query, params)

    players = [
        PlayerSummary(
            player_id=r["player_id"] or "",
            name=r["name"] or "",
            position=r["position"],
            team=r["team"],
            age=r["age"],
            ktc_value=r["ktc_value"],
            signal=r["signal"],
        )
        for r in results
        if r.get("player_id")
    ]

    return PaginatedResponse(
        data=players,
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + limit) < total,
    )


@router.get("/{player_id}", response_model=APIResponse[Player])
async def get_player(player_id: str):
    """Get full player profile by ID."""
    db = get_db()

    query = """
        MATCH (p:Player)
        WHERE p.gsis_id = $player_id OR p.sleeper_id = $player_id
        OPTIONAL MATCH (p)-[:HAS_COMBINE]->(c:CombineResult)
        OPTIONAL MATCH (p)-[:HAS_KTC]->(k:KTCSnapshot)
        WITH p, c, k
        ORDER BY k.snapshot_date DESC
        LIMIT 1
        RETURN p.gsis_id as gsis_id, p.sleeper_id as sleeper_id,
               p.name as name, p.first_name as first_name, p.last_name as last_name,
               p.position as position, p.team as team, p.age as age,
               p.experience as experience, p.college as college,
               p.draft_year as draft_year, p.draft_round as draft_round,
               p.draft_pick as draft_pick, p.draft_age as draft_age,
               k.value as ktc_value, k.rank as ktc_rank,
               k.positional_rank as ktc_positional_rank, k.trend as ktc_trend,
               p.predicted_value as predicted_value, p.edge_score as edge_score,
               p.signal as signal,
               c.forty_yard as forty_yard, c.vertical as vertical,
               c.broad_jump as broad_jump, c.cone as cone, c.shuttle as shuttle,
               c.bench as bench, c.height as height, c.weight as weight,
               p.injury_risk as injury_risk, p.career_stage as career_stage
    """

    results = await db.execute(query, {"player_id": player_id})

    if not results:
        raise HTTPException(status_code=404, detail=f"Player {player_id} not found")

    return APIResponse(data=_parse_player(results[0]))


@router.get("/{player_id}/value-history")
async def get_value_history(player_id: str, days: int = Query(90, ge=7, le=365)):
    """Get player's KTC value history."""
    db = get_db()

    query = """
        MATCH (p:Player)-[:HAS_KTC]->(k:KTCSnapshot)
        WHERE p.gsis_id = $player_id OR p.sleeper_id = $player_id
        RETURN k.snapshot_date as date, k.value as value,
               k.rank as rank, k.positional_rank as positional_rank
        ORDER BY k.snapshot_date DESC
        LIMIT $limit
    """

    results = await db.execute(query, {"player_id": player_id, "limit": days})

    return APIResponse(data=results)


@router.post("/compare", response_model=APIResponse[PlayerComparison])
async def compare_players(player_ids: list[str]):
    """Compare 2-5 players side by side."""
    if len(player_ids) < 2 or len(player_ids) > 5:
        raise HTTPException(status_code=400, detail="Must compare 2-5 players")

    db = get_db()

    query = """
        MATCH (p:Player)
        WHERE p.gsis_id IN $player_ids OR p.sleeper_id IN $player_ids
        OPTIONAL MATCH (p)-[:HAS_COMBINE]->(c:CombineResult)
        RETURN p.gsis_id as gsis_id, p.sleeper_id as sleeper_id,
               p.name as name, p.position as position, p.team as team,
               p.age as age, p.ktc_value as ktc_value, p.signal as signal,
               p.edge_score as edge_score, p.predicted_value as predicted_value,
               c.forty_yard as forty_yard, c.vertical as vertical,
               c.broad_jump as broad_jump
    """

    results = await db.execute(query, {"player_ids": player_ids})

    if len(results) < 2:
        raise HTTPException(status_code=404, detail="Not enough players found")

    players = [_parse_player(r) for r in results]

    # Generate simple comparison summary
    best_value = max(players, key=lambda p: p.ktc_value or 0)
    youngest = min(players, key=lambda p: p.age or 99)

    summary = f"Highest value: {best_value.name} ({best_value.ktc_value}). Youngest: {youngest.name} ({youngest.age})."

    return APIResponse(
        data=PlayerComparison(
            players=players,
            comparison_summary=summary,
        )
    )
