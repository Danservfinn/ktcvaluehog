"""Player endpoints."""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from ..database import get_db
from ..models.player import (
    Player,
    PlayerSummary,
    PlayerComparison,
    PlayerResearch,
    ResearchValueAnalysis,
    ResearchProductionProfile,
    ResearchDynastyOutlook,
    ResearchRiskAssessment,
    ResearchAthleticProfile,
    CareerProjection,
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


# === Player Research Endpoint ===

# Position-specific aging curves (peak windows)
POSITION_PEAKS = {
    "QB": {"start": 26, "end": 34, "decline_rate": 0.03},
    "RB": {"start": 22, "end": 26, "decline_rate": 0.12},
    "WR": {"start": 24, "end": 29, "decline_rate": 0.06},
    "TE": {"start": 25, "end": 30, "decline_rate": 0.05},
}


def _calculate_projected_value(current_value: int, age: int, position: str, years: int) -> int:
    """Calculate projected value based on aging curves."""
    if not current_value or not age or not position:
        return current_value or 0

    peak = POSITION_PEAKS.get(position, POSITION_PEAKS["WR"])
    decline_rate = peak["decline_rate"]
    value = float(current_value)

    for y in range(years):
        player_age = age + y
        if player_age < peak["start"]:
            value *= 1.03  # Pre-peak growth
        elif player_age <= peak["end"]:
            value *= 0.98  # Peak: stable
        else:
            years_past_peak = player_age - peak["end"]
            value *= (1 - decline_rate * (1 + years_past_peak * 0.1))

    return max(int(value), 100)


def _get_aging_curve_position(age: int, position: str) -> str:
    """Determine where player is on aging curve."""
    peak = POSITION_PEAKS.get(position, POSITION_PEAKS["WR"])
    if age < peak["start"]:
        return "Pre-Peak"
    elif age <= peak["end"]:
        return "Peak"
    elif age <= peak["end"] + 2:
        return "Post-Peak"
    else:
        return "Declining"


def _get_peak_window(position: str) -> str:
    """Get peak window description for position."""
    peak = POSITION_PEAKS.get(position, POSITION_PEAKS["WR"])
    return f"{peak['start']}-{peak['end']} ({position})"


def _calculate_years_in_peak(age: int, position: str) -> int:
    """Calculate years remaining in peak window."""
    peak = POSITION_PEAKS.get(position, POSITION_PEAKS["WR"])
    if age >= peak["end"]:
        return 0
    return max(0, peak["end"] - age)


def _get_grade(value: int, ppg: float | None, age: int, position: str) -> str:
    """Calculate overall player grade."""
    score = 0

    # Value component (0-40 points)
    if value >= 8000:
        score += 40
    elif value >= 6000:
        score += 32
    elif value >= 4000:
        score += 24
    elif value >= 2000:
        score += 16
    else:
        score += 8

    # Production component (0-30 points)
    if ppg:
        if ppg >= 18:
            score += 30
        elif ppg >= 14:
            score += 24
        elif ppg >= 10:
            score += 18
        elif ppg >= 6:
            score += 12
        else:
            score += 6

    # Age component (0-30 points)
    years_left = _calculate_years_in_peak(age, position)
    score += min(30, years_left * 6)

    # Convert to grade
    if score >= 85:
        return "A+"
    elif score >= 75:
        return "A"
    elif score >= 65:
        return "B+"
    elif score >= 55:
        return "B"
    elif score >= 45:
        return "C+"
    elif score >= 35:
        return "C"
    else:
        return "D"


def _generate_one_liner(age: int, position: str, ktc_value: int, aging_pos: str) -> str:
    """Generate a brief player assessment."""
    if aging_pos == "Pre-Peak":
        years_left = _calculate_years_in_peak(age, position)
        return f"Young talent with upside; {years_left} years until peak"
    elif aging_pos == "Peak":
        if ktc_value >= 7000:
            return "Elite producer in prime years"
        else:
            return "Solid contributor in peak window"
    elif aging_pos == "Post-Peak":
        return "Production may decline; consider selling window"
    else:
        return "Declining asset; likely depreciating value"


# Career end ages by position (when value typically drops to minimal)
CAREER_END_AGES = {
    "QB": 40,
    "RB": 30,
    "WR": 34,
    "TE": 35,
}


def _project_ppg(current_ppg: float, age: int, position: str, years: int) -> float:
    """Project fantasy PPG for a future year based on aging curves."""
    if not current_ppg:
        return 0.0

    peak = POSITION_PEAKS.get(position, POSITION_PEAKS["WR"])
    ppg = current_ppg

    for y in range(years):
        player_age = age + y + 1
        if player_age <= peak["start"]:
            # Pre-peak: growth as player develops (3% per year)
            ppg *= 1.03
        elif player_age <= peak["end"]:
            # Peak: stable production
            ppg *= 1.0
        else:
            # Post-peak: decline accelerates
            years_past = player_age - peak["end"]
            decline = 0.08 + (years_past * 0.02)  # 8% + 2% per year past peak
            ppg *= (1 - decline)

    return max(round(ppg, 1), 0)


def _calculate_career_projections(
    age: int, position: str, ktc: int, current_ppg: float | None
) -> list[CareerProjection]:
    """Calculate year-by-year projections for remaining career."""
    max_age = CAREER_END_AGES.get(position, 34)
    years_remaining = max(0, max_age - age)

    # Cap at 10 years for chart readability
    max_years = min(years_remaining, 10)

    projections = []
    for year in range(1, max_years + 1):
        proj_age = age + year
        proj_ktc = _calculate_projected_value(ktc, age, position, year)
        proj_ppg = _project_ppg(current_ppg, age, position, year) if current_ppg else None

        projections.append(CareerProjection(
            year=year,
            age=proj_age,
            projected_ktc=proj_ktc,
            projected_ppg=proj_ppg
        ))

    return projections


@router.get("/{player_id}/research", response_model=APIResponse[PlayerResearch])
async def get_player_research(player_id: str):
    """
    Get comprehensive player research data for modal display.

    Returns all available Neo4j data organized into sections:
    - Value Analysis (KTC, trends, projections)
    - Production Metrics (PPG, shares, EPA, WOPR)
    - Dynasty Outlook (aging curve, peak window)
    - Risk Assessment (injury, depth chart)
    - Athletic Profile (combine, draft)
    """
    db = get_db()

    query = """
        MATCH (p:Player)
        WHERE p.gsis_id = $player_id OR p.sleeper_id = $player_id OR p.name = $player_id

        // KTC trend data
        OPTIONAL MATCH (p)-[:HAS_TREND]->(kt:KTCTrend)

        // Injury profile
        OPTIONAL MATCH (p)-[:HAS_INJURY_PROFILE]->(ip:PlayerInjuryProfile)

        // Role profile
        OPTIONAL MATCH (p)-[:HAS_ROLE]->(rp:PlayerRoleProfile)

        // PBP aggregates (latest season)
        OPTIONAL MATCH (pbp:PlayByPlayAggregates)
        WHERE pbp.player_id = p.gsis_id AND pbp.season >= 2023

        // Season stats (latest available - prefer 2024 over 2023)
        OPTIONAL MATCH (ss:HistoricalSeasonStats)
        WHERE ss.player_id = p.gsis_id AND ss.season >= 2023
        WITH p, kt, ip, rp, pbp, ss
        ORDER BY ss.season DESC
        WITH p, kt, ip, rp, pbp, head(collect(ss)) as ss

        // ML projections
        OPTIONAL MATCH (p)-[:HAS_PROJECTION]->(proj:PlayerProjection)

        // Combine results
        OPTIONAL MATCH (p)-[:HAD_COMBINE]->(c:CombineResult)

        // Draft capital
        OPTIONAL MATCH (p)-[:WAS_DRAFTED]->(d:DraftPick)

        RETURN
            // Core player
            p.gsis_id as player_id,
            p.name as name,
            p.position as position,
            p.team as team,
            p.age as age,
            p.experience as experience,
            p.college as college,

            // Current valuation
            p.ktc_value as ktc_value,
            p.ktc_rank as ktc_rank,
            p.ktc_positional_rank as ktc_positional_rank,

            // KTC Trend
            kt.ktc_30d_change as ktc_30d_change,
            kt.ktc_momentum as ktc_momentum,

            // Injury Profile
            ip.injury_burden_score as injury_burden,
            ip.overall_injury_risk as injury_risk,
            ip.games_missed_last_3yr as games_missed,

            // Role Profile
            rp.starter_rate as starter_rate,

            // PBP Stats
            pbp.epa_per_target as epa_target,
            pbp.epa_per_carry as epa_carry,
            pbp.adot as adot,
            pbp.wopr as wopr,
            pbp.target_share as target_share,
            pbp.touch_share as touch_share,
            pbp.rz_target_share as rz_target_share,
            pbp.rz_carry_share as rz_carry_share,

            // Season Stats (using ppg_ppr * games for total points)
            ss.ppg_ppr as season_ppg_raw,
            ss.games as games_played,
            ss.targets as targets,
            ss.receptions as receptions,
            ss.receiving_yards as receiving_yards,
            ss.receiving_tds as receiving_tds,
            ss.carries as carries,
            ss.rushing_yards as rushing_yards,
            ss.rushing_tds as rushing_tds,

            // Projection
            proj.projected_ppg as proj_ppg,
            proj.floor as proj_floor,
            proj.ceiling as proj_ceiling,
            proj.confidence as proj_confidence,

            // Combine
            c.forty_yard as forty_time,
            c.vertical as vertical_jump,
            c.broad_jump as broad_jump,
            c.three_cone as three_cone,
            c.shuttle as shuttle,
            c.bench as bench_press,
            c.height as height,
            c.weight as weight,

            // Draft
            d.round as draft_round,
            d.pick as draft_pick,
            d.season as draft_year

        LIMIT 1
    """

    results = await db.execute(query, {"player_id": player_id})

    if not results:
        raise HTTPException(status_code=404, detail=f"Player {player_id} not found")

    row = results[0]
    pos = row.get("position") or "WR"
    age = int(row.get("age") or 25)
    ktc = row.get("ktc_value") or 0

    # Calculate derived values
    season_ppg_raw = row.get("season_ppg_raw")
    games = row.get("games_played")
    season_ppg = round(season_ppg_raw, 1) if season_ppg_raw else None
    season_pts = round(season_ppg_raw * games, 1) if season_ppg_raw and games else None

    aging_pos = _get_aging_curve_position(age, pos)

    # Determine position-appropriate metrics
    if pos == "RB":
        share_metric = row.get("touch_share")
        rz_metric = row.get("rz_carry_share")
        epa_per_touch = row.get("epa_carry")
    else:
        share_metric = row.get("target_share")
        rz_metric = row.get("rz_target_share")
        epa_per_touch = row.get("epa_target")

    # Build response
    value = ResearchValueAnalysis(
        current_value=ktc,
        value_rank=row.get("ktc_rank"),
        positional_rank=row.get("ktc_positional_rank"),
        value_30d_change=row.get("ktc_30d_change"),
        value_trend="rising" if (row.get("ktc_momentum") or 0) > 0.5 else
                    "falling" if (row.get("ktc_momentum") or 0) < -0.5 else "stable",
        projected_value_1yr=_calculate_projected_value(ktc, age, pos, 1),
        projected_value_2yr=_calculate_projected_value(ktc, age, pos, 2),
        projected_value_3yr=_calculate_projected_value(ktc, age, pos, 3),
    )

    production = ResearchProductionProfile(
        season_ppg=season_ppg,
        games_played=games,
        total_points=season_pts,
        targets=row.get("targets"),
        receptions=row.get("receptions"),
        receiving_yards=row.get("receiving_yards"),
        receiving_tds=row.get("receiving_tds"),
        carries=row.get("carries"),
        rushing_yards=row.get("rushing_yards"),
        rushing_tds=row.get("rushing_tds"),
        target_share=round(share_metric * 100, 1) if share_metric else None,
        touch_share=round(row.get("touch_share") * 100, 1) if row.get("touch_share") else None,
        red_zone_share=round(rz_metric * 100, 1) if rz_metric else None,
        epa_per_touch=round(epa_per_touch, 3) if epa_per_touch else None,
        wopr=round(row.get("wopr"), 2) if row.get("wopr") else None,
        adot=round(row.get("adot"), 1) if row.get("adot") else None,
    )

    # Calculate career projections for chart
    career_projections = _calculate_career_projections(age, pos, ktc, season_ppg)

    dynasty = ResearchDynastyOutlook(
        years_in_peak=_calculate_years_in_peak(age, pos),
        peak_window=_get_peak_window(pos),
        aging_curve_position=aging_pos,
        projected_ppg=row.get("proj_ppg"),
        projection_floor=row.get("proj_floor"),
        projection_ceiling=row.get("proj_ceiling"),
        projection_confidence=row.get("proj_confidence"),
        career_projections=career_projections if career_projections else None,
    )

    injury_risk_raw = row.get("injury_risk")
    injury_risk_level = "Low" if not injury_risk_raw else (
        "High" if injury_risk_raw == "high" else
        "Medium" if injury_risk_raw == "medium" else "Low"
    )
    starter_rate = row.get("starter_rate")

    risk = ResearchRiskAssessment(
        injury_burden_score=round(row.get("injury_burden"), 1) if row.get("injury_burden") else None,
        injury_risk_level=injury_risk_level,
        games_missed_3yr=row.get("games_missed"),
        starter_rate=round(starter_rate * 100, 1) if starter_rate else None,
        depth_chart_security="Locked" if (starter_rate or 0) > 0.8 else
                             "Secure" if (starter_rate or 0) > 0.5 else "At Risk",
    )

    athletic = None
    if any([row.get("forty_time"), row.get("draft_round")]):
        athletic = ResearchAthleticProfile(
            forty_time=row.get("forty_time"),
            vertical_jump=row.get("vertical_jump"),
            broad_jump=row.get("broad_jump"),
            three_cone=row.get("three_cone"),
            shuttle=row.get("shuttle"),
            bench_press=row.get("bench_press"),
            height=row.get("height"),
            weight=row.get("weight"),
            draft_round=row.get("draft_round"),
            draft_pick=row.get("draft_pick"),
            draft_year=row.get("draft_year"),
        )

    return APIResponse(
        data=PlayerResearch(
            player_id=row.get("player_id") or "",
            name=row.get("name") or "",
            position=pos,
            team=row.get("team"),
            age=age,
            experience=row.get("experience"),
            college=row.get("college"),
            value=value,
            production=production,
            dynasty=dynasty,
            risk=risk,
            athletic=athletic,
            overall_grade=_get_grade(ktc, season_ppg, age, pos),
            one_liner=_generate_one_liner(age, pos, ktc, aging_pos),
        )
    )
