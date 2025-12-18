"""Trade analysis endpoints."""

from fastapi import APIRouter, HTTPException
from typing import Optional

from ..database import get_db
from ..models.player import PlayerSummary
from ..models.trade import (
    TradeRequest, TradeAnalysis, TradeSide,
    EliteTradeRequest, EliteTradeAnalysis, EliteTradeSide,
    ElitePlayerAnalysis, PlayerValueAnalysis, PlayerProductionProfile,
    PlayerDynastyOutlook, PlayerRiskAssessment, TradeScoreBreakdown
)
from ..models.response import APIResponse

router = APIRouter(prefix="/trades", tags=["Trades"])


async def _get_players_by_ids(db, player_ids: list[str]) -> list[dict]:
    """Fetch player data for a list of IDs."""
    if not player_ids:
        return []

    query = """
        MATCH (p:Player)
        WHERE p.gsis_id IN $ids OR p.sleeper_id IN $ids OR p.name IN $ids
        RETURN p.gsis_id as player_id, p.name as name, p.position as position,
               p.team as team, p.age as age, p.ktc_value as ktc_value,
               p.predicted_value as predicted_value, p.signal as signal,
               p.edge_score as edge_score
    """
    return await db.execute(query, {"ids": player_ids})


def _build_trade_side(players: list[dict]) -> TradeSide:
    """Build TradeSide from player list."""
    summaries = []
    total_ktc = 0
    total_predicted = 0
    total_age = 0.0
    positions = {}

    for p in players:
        # Convert ktc_value to int for model
        ktc_raw = p.get("ktc_value")
        ktc_int = int(ktc_raw) if ktc_raw is not None else None

        summary = PlayerSummary(
            player_id=p.get("player_id") or "",
            name=p.get("name") or "",
            position=p.get("position"),
            team=p.get("team"),
            age=p.get("age"),
            ktc_value=ktc_int,
            signal=p.get("signal"),
        )
        summaries.append(summary)

        ktc = int(ktc_raw) if ktc_raw else 0
        pred_raw = p.get("predicted_value")
        pred = int(pred_raw) if pred_raw else ktc
        age = float(p.get("age") or 25)
        pos = p.get("position") or "UNKNOWN"

        total_ktc += ktc
        total_predicted += pred
        total_age += age
        positions[pos] = positions.get(pos, 0) + 1

    avg_age = total_age / len(players) if players else 0

    return TradeSide(
        players=summaries,
        total_ktc_value=int(total_ktc),
        total_predicted_value=int(total_predicted) if total_predicted > 0 else None,
        average_age=round(avg_age, 1) if avg_age else None,
        positions=positions,
    )


def _determine_recommendation(
    ktc_diff: int, pred_diff: int | None, age_diff: float | None
) -> tuple[str, float, str]:
    """Determine trade recommendation."""
    # Base on KTC differential
    if ktc_diff > 500:
        rec = "ACCEPT"
        confidence = min(95, 60 + (ktc_diff / 100))
        reason = f"You're getting {ktc_diff} more KTC value."
    elif ktc_diff < -500:
        rec = "REJECT"
        confidence = min(95, 60 + (abs(ktc_diff) / 100))
        reason = f"You're giving up {abs(ktc_diff)} more KTC value."
    else:
        rec = "FAIR"
        confidence = 50 + (30 - abs(ktc_diff) / 20)
        reason = "Trade is roughly fair in KTC value."

    # Adjust for predicted value
    if pred_diff is not None:
        if pred_diff > 200 and rec != "ACCEPT":
            reason += f" ML model suggests you gain {pred_diff} in predicted value."
            confidence += 10
        elif pred_diff < -200 and rec != "REJECT":
            reason += f" ML model suggests you lose {abs(pred_diff)} in predicted value."
            confidence -= 10

    # Adjust for age
    if age_diff is not None:
        if age_diff > 2:
            reason += f" You're getting {age_diff:.1f} years younger on average."
            if rec == "FAIR":
                rec = "ACCEPT"
                confidence += 15
        elif age_diff < -2:
            reason += f" You're getting {abs(age_diff):.1f} years older on average."
            if rec == "FAIR":
                confidence -= 10

    return rec, min(99, max(10, confidence)), reason


@router.post("/analyze", response_model=APIResponse[TradeAnalysis])
async def analyze_trade(request: TradeRequest):
    """Analyze a proposed trade."""
    if not request.give or not request.get:
        raise HTTPException(status_code=400, detail="Both give and get must have players")

    if len(request.give) > 8 or len(request.get) > 8:
        raise HTTPException(status_code=400, detail="Maximum 8 players per side")

    db = get_db()

    # Fetch both sides
    give_players = await _get_players_by_ids(db, request.give)
    get_players = await _get_players_by_ids(db, request.get)

    if not give_players:
        raise HTTPException(status_code=404, detail="No players found in 'give' side")
    if not get_players:
        raise HTTPException(status_code=404, detail="No players found in 'get' side")

    # Build trade sides
    give_side = _build_trade_side(give_players)
    get_side = _build_trade_side(get_players)

    # Calculate differentials
    ktc_diff = get_side.total_ktc_value - give_side.total_ktc_value

    pred_diff = None
    if get_side.total_predicted_value and give_side.total_predicted_value:
        pred_diff = get_side.total_predicted_value - give_side.total_predicted_value

    age_diff = None
    if get_side.average_age and give_side.average_age:
        age_diff = give_side.average_age - get_side.average_age  # Positive = getting younger

    # Get recommendation
    rec, confidence, reasoning = _determine_recommendation(ktc_diff, pred_diff, age_diff)

    # Collect signals
    give_signals = [p.get("signal") for p in give_players if p.get("signal")]
    get_signals = [p.get("signal") for p in get_players if p.get("signal")]

    return APIResponse(
        data=TradeAnalysis(
            give_side=give_side,
            get_side=get_side,
            ktc_differential=ktc_diff,
            predicted_differential=pred_diff,
            recommendation=rec,
            confidence=round(confidence, 1),
            reasoning=reasoning,
            give_side_signals=give_signals,
            get_side_signals=get_signals,
            age_differential=age_diff,
        )
    )


@router.get("/targets")
async def find_trade_targets(
    position: str,
    budget_ktc: int,
    signal: str = "BUY",
    limit: int = 10,
):
    """Find trade targets within budget for a position."""
    db = get_db()

    query = """
        MATCH (p:Player)
        WHERE p.position = $position
          AND p.ktc_value <= $budget
          AND p.ktc_value > $budget * 0.5
          AND (p.signal = $signal OR $signal = 'ANY')
        RETURN p.gsis_id as player_id, p.name as name, p.position as position,
               p.team as team, p.age as age, p.ktc_value as ktc_value,
               p.signal as signal, p.edge_score as edge_score
        ORDER BY p.edge_score DESC
        LIMIT $limit
    """

    results = await db.execute(
        query,
        {
            "position": position.upper(),
            "budget": budget_ktc,
            "signal": signal.upper() if signal != "ANY" else "ANY",
            "limit": limit,
        },
    )

    return APIResponse(data=results)


# === Elite Trade Analysis ===

# Position-specific aging curves (peak windows)
POSITION_PEAKS = {
    "QB": {"start": 26, "end": 34, "decline_rate": 0.03},
    "RB": {"start": 22, "end": 26, "decline_rate": 0.12},
    "WR": {"start": 24, "end": 29, "decline_rate": 0.06},
    "TE": {"start": 25, "end": 30, "decline_rate": 0.05},
}


async def _get_elite_player_data(db, player_ids: list[str]) -> list[dict]:
    """Fetch comprehensive player data for elite analysis."""
    if not player_ids:
        return []

    # Main query with all available data
    query = """
        MATCH (p:Player)
        WHERE p.gsis_id IN $ids OR p.sleeper_id IN $ids OR p.name IN $ids

        // Get KTC trend data if available
        OPTIONAL MATCH (p)-[:HAS_TREND]->(kt:KTCTrend)

        // Get injury profile if available
        OPTIONAL MATCH (p)-[:HAS_INJURY_PROFILE]->(ip:PlayerInjuryProfile)

        // Get role profile if available
        OPTIONAL MATCH (p)-[:HAS_ROLE]->(rp:PlayerRoleProfile)

        // Get PBP aggregates if available
        OPTIONAL MATCH (p)-[:HAS_PBP_STATS]->(pbp:PlayByPlayAggregates)
        WHERE pbp.season = 2024

        // Get recent season stats
        OPTIONAL MATCH (p)-[:HAD_SEASON]->(ss:HistoricalSeasonStats)
        WHERE ss.season = 2024

        // Get projection if available
        OPTIONAL MATCH (p)-[:HAS_PROJECTION]->(proj:PlayerProjection)

        RETURN
            p.gsis_id as player_id,
            p.name as name,
            p.position as position,
            p.team as team,
            p.age as age,
            p.ktc_value as ktc_value,
            p.predicted_value as predicted_value,
            p.signal as signal,
            p.edge_score as edge_score,

            // KTC Trend
            kt.trend_slope as ktc_slope,
            kt.ktc_momentum as ktc_momentum,
            kt.value_signal as value_signal,
            kt.ktc_30d_change as ktc_30d_change,

            // Injury Profile
            ip.injury_burden_score as injury_burden,
            ip.overall_injury_risk as injury_risk,
            ip.games_missed_last_3yr as games_missed,

            // Role Profile
            rp.starter_rate as starter_rate,
            rp.role as role,

            // PBP Stats
            pbp.epa_per_target as epa_target,
            pbp.epa_per_carry as epa_carry,
            pbp.adot as adot,
            pbp.wopr as wopr,
            pbp.target_share as target_share,
            pbp.rz_target_share as rz_target_share,

            // Season Stats
            ss.fantasy_points_ppr as season_pts,
            ss.games as games_played,

            // Projection
            proj.projected_ppg as proj_ppg,
            proj.floor as proj_floor,
            proj.ceiling as proj_ceiling,
            proj.confidence as proj_confidence
    """
    return await db.execute(query, {"ids": player_ids})


def _calculate_projected_value(current_value: int, age: int, position: str, years: int) -> int:
    """Calculate projected value based on aging curves."""
    if not current_value or not age or not position:
        return current_value or 0

    peak = POSITION_PEAKS.get(position, POSITION_PEAKS["WR"])
    decline_rate = peak["decline_rate"]

    # Determine aging phase
    future_age = age + years
    value = float(current_value)

    for y in range(years):
        player_age = age + y
        if player_age < peak["start"]:
            # Pre-peak: slight growth
            value *= 1.03
        elif player_age <= peak["end"]:
            # Peak: stable
            value *= 0.98
        else:
            # Post-peak: decline
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


def _generate_one_liner(player: dict, position: str) -> str:
    """Generate a brief player assessment."""
    age = player.get("age") or 25
    value = player.get("ktc_value") or 0
    signal = player.get("value_signal") or player.get("signal")

    aging_pos = _get_aging_curve_position(age, position)

    if aging_pos == "Pre-Peak":
        return f"Young talent with upside; {_calculate_years_in_peak(age, position)} years until peak"
    elif aging_pos == "Peak":
        if value >= 7000:
            return "Elite producer in prime years"
        else:
            return "Solid contributor in peak window"
    elif aging_pos == "Post-Peak":
        return "Production may decline; consider selling window"
    else:
        return "Declining asset; likely depreciating value"


def _build_elite_player_analysis(player: dict) -> ElitePlayerAnalysis:
    """Build complete analysis for a single player."""
    pos = player.get("position") or "WR"
    age = player.get("age") or 25
    ktc = player.get("ktc_value") or 0

    # Season PPG calculation
    season_pts = player.get("season_pts")
    games = player.get("games_played")
    season_ppg = round(season_pts / games, 1) if season_pts and games and games > 0 else None

    # Value analysis
    value = PlayerValueAnalysis(
        current_value=ktc,
        value_30d_change=player.get("ktc_30d_change"),
        value_trend="rising" if (player.get("ktc_momentum") or 0) > 0.5 else
                    "falling" if (player.get("ktc_momentum") or 0) < -0.5 else "stable",
        projected_value_1yr=_calculate_projected_value(ktc, age, pos, 1),
        projected_value_2yr=_calculate_projected_value(ktc, age, pos, 2),
        projected_value_3yr=_calculate_projected_value(ktc, age, pos, 3),
    )

    # Production profile
    epa_target = player.get("epa_target")
    epa_carry = player.get("epa_carry")
    epa_per_touch = epa_target if pos in ["WR", "TE"] else epa_carry

    production = PlayerProductionProfile(
        season_ppg=season_ppg,
        epa_per_touch=round(epa_per_touch, 3) if epa_per_touch else None,
        target_share=round(player.get("target_share") * 100, 1) if player.get("target_share") else None,
        red_zone_share=round(player.get("rz_target_share") * 100, 1) if player.get("rz_target_share") else None,
        wopr=round(player.get("wopr"), 2) if player.get("wopr") else None,
        adot=round(player.get("adot"), 1) if player.get("adot") else None,
    )

    # Dynasty outlook
    dynasty = PlayerDynastyOutlook(
        age=int(age),
        years_in_peak=int(_calculate_years_in_peak(int(age), pos)),
        peak_window=_get_peak_window(pos),
        aging_curve_position=_get_aging_curve_position(int(age), pos),
        projected_ppg=player.get("proj_ppg"),
        projection_floor=player.get("proj_floor"),
        projection_ceiling=player.get("proj_ceiling"),
        projection_confidence=player.get("proj_confidence"),
    )

    # Risk assessment
    injury_burden = player.get("injury_burden")
    injury_risk_raw = player.get("injury_risk")
    injury_risk = "Low" if not injury_risk_raw else (
        "High" if injury_risk_raw == "high" else
        "Medium" if injury_risk_raw == "medium" else "Low"
    )

    risk = PlayerRiskAssessment(
        injury_burden_score=round(injury_burden, 1) if injury_burden else None,
        injury_risk_level=injury_risk,
        games_missed_3yr=player.get("games_missed"),
        depth_chart_security="Locked" if (player.get("starter_rate") or 0) > 0.8 else
                            "Secure" if (player.get("starter_rate") or 0) > 0.5 else "At Risk",
    )

    return ElitePlayerAnalysis(
        player_id=player.get("player_id") or "",
        name=player.get("name") or "",
        position=pos,
        team=player.get("team"),
        age=int(age),
        value=value,
        production=production,
        dynasty=dynasty,
        risk=risk,
        overall_grade=_get_grade(ktc, season_ppg, int(age), pos),
        one_liner=_generate_one_liner(player, pos),
    )


def _build_elite_trade_side(players: list[dict]) -> EliteTradeSide:
    """Build elite trade side from player data."""
    analyses = [_build_elite_player_analysis(p) for p in players]

    total_current = sum(a.value.current_value for a in analyses)
    total_1yr = sum(a.value.projected_value_1yr or a.value.current_value for a in analyses)
    total_3yr = sum(a.value.projected_value_3yr or a.value.current_value for a in analyses)
    avg_age = sum(a.age or 25 for a in analyses) / len(analyses) if analyses else 0

    # Composite risk (simple average of injury burden, higher = riskier)
    risk_scores = [a.risk.injury_burden_score for a in analyses if a.risk.injury_burden_score]
    composite_risk = sum(risk_scores) / len(risk_scores) if risk_scores else None

    return EliteTradeSide(
        players=analyses,
        total_current_value=total_current,
        total_projected_value_1yr=total_1yr,
        total_projected_value_3yr=total_3yr,
        average_age=round(avg_age, 1),
        composite_risk_score=round(composite_risk, 1) if composite_risk else None,
    )


def _generate_executive_summary(
    give_side: EliteTradeSide,
    get_side: EliteTradeSide,
    score: float
) -> str:
    """Generate narrative executive summary."""
    value_diff = get_side.total_current_value - give_side.total_current_value
    value_pct = (value_diff / give_side.total_current_value * 100) if give_side.total_current_value else 0

    age_diff = (give_side.average_age or 25) - (get_side.average_age or 25)

    if score > 15:
        verdict_word = "significantly favors you"
    elif score > 5:
        verdict_word = "slightly favors you"
    elif score > -5:
        verdict_word = "is relatively balanced"
    elif score > -15:
        verdict_word = "slightly favors the other side"
    else:
        verdict_word = "significantly favors the other side"

    summary = f"This trade {verdict_word}. "

    if abs(value_pct) > 10:
        if value_pct > 0:
            summary += f"You're receiving {abs(value_pct):.0f}% more current KTC value. "
        else:
            summary += f"You're giving up {abs(value_pct):.0f}% more current KTC value. "

    if abs(age_diff) > 1:
        if age_diff > 0:
            summary += f"You're getting {age_diff:.1f} years younger on average, improving long-term outlook."
        else:
            summary += f"You're getting {abs(age_diff):.1f} years older on average, which may limit upside."

    return summary.strip()


def _generate_key_insights(give_side: EliteTradeSide, get_side: EliteTradeSide) -> list[str]:
    """Generate 3-5 key insights about the trade."""
    insights = []

    # Value insight
    value_diff_pct = ((get_side.total_current_value - give_side.total_current_value)
                     / give_side.total_current_value * 100) if give_side.total_current_value else 0
    if abs(value_diff_pct) > 5:
        insights.append(f"Current value differential: {value_diff_pct:+.1f}%")

    # Age insight
    if give_side.average_age and get_side.average_age:
        age_diff = give_side.average_age - get_side.average_age
        if age_diff > 1:
            insights.append(f"You're getting {age_diff:.1f} years younger on average")
        elif age_diff < -1:
            insights.append(f"You're getting {abs(age_diff):.1f} years older on average")

    # Position-specific insights
    give_positions = [p.position for p in give_side.players]
    get_positions = [p.position for p in get_side.players]

    if "RB" in give_positions and "RB" not in get_positions:
        insights.append("Trading away RB - historically depreciating position")
    if "RB" in get_positions and "RB" not in give_positions:
        insights.append("Acquiring RB - be mindful of shorter peak windows")

    # Projected value insight
    if give_side.total_projected_value_3yr and get_side.total_projected_value_3yr:
        proj_diff = get_side.total_projected_value_3yr - give_side.total_projected_value_3yr
        if abs(proj_diff) > 500:
            insights.append(f"3-year projected value: {proj_diff:+,} differential")

    # Player-specific insights
    for player in give_side.players:
        if player.dynasty.aging_curve_position == "Declining":
            insights.append(f"{player.name}: Past peak, good time to sell")
        elif player.dynasty.aging_curve_position == "Pre-Peak":
            insights.append(f"{player.name}: Pre-peak, consider holding")

    for player in get_side.players:
        if player.dynasty.aging_curve_position == "Pre-Peak":
            insights.append(f"{player.name}: Pre-peak with upside")

    return insights[:5]  # Limit to 5


@router.post("/analyze-elite", response_model=APIResponse[EliteTradeAnalysis])
async def analyze_trade_elite(request: EliteTradeRequest):
    """Elite trade analysis with comprehensive player analytics."""
    if not request.give or not request.get:
        raise HTTPException(status_code=400, detail="Both give and get must have players")

    if len(request.give) > 8 or len(request.get) > 8:
        raise HTTPException(status_code=400, detail="Maximum 8 players per side")

    db = get_db()

    # Fetch comprehensive player data
    give_players = await _get_elite_player_data(db, request.give)
    get_players = await _get_elite_player_data(db, request.get)

    if not give_players:
        raise HTTPException(status_code=404, detail="No players found in 'give' side")
    if not get_players:
        raise HTTPException(status_code=404, detail="No players found in 'get' side")

    # Build trade sides
    give_side = _build_elite_trade_side(give_players)
    get_side = _build_elite_trade_side(get_players)

    # Calculate score breakdown
    current_edge = ((get_side.total_current_value - give_side.total_current_value)
                   / give_side.total_current_value * 100) if give_side.total_current_value else 0

    proj_edge = 0
    if give_side.total_projected_value_3yr and get_side.total_projected_value_3yr:
        proj_edge = ((get_side.total_projected_value_3yr - give_side.total_projected_value_3yr)
                    / give_side.total_projected_value_3yr * 100)

    age_edge = 0
    if give_side.average_age and get_side.average_age:
        age_diff = give_side.average_age - get_side.average_age
        age_edge = age_diff * 3  # 3 points per year younger

    # Production edge (compare season PPG if available)
    give_ppg = sum(p.production.season_ppg or 0 for p in give_side.players)
    get_ppg = sum(p.production.season_ppg or 0 for p in get_side.players)
    production_edge = ((get_ppg - give_ppg) / give_ppg * 100) if give_ppg > 0 else 0

    # Weighted total
    total_edge = (
        current_edge * 0.30 +
        proj_edge * 0.25 +
        age_edge * 0.25 +
        production_edge * 0.20
    )

    score_breakdown = TradeScoreBreakdown(
        current_value_edge=round(current_edge, 1),
        projected_value_edge=round(proj_edge, 1),
        production_edge=round(production_edge, 1),
        age_edge=round(age_edge, 1),
        total_edge=round(total_edge, 1),
    )

    # Determine verdict
    if total_edge > 10:
        verdict = "WIN"
        confidence = min(95, 60 + total_edge)
    elif total_edge < -10:
        verdict = "LOSE"
        confidence = min(95, 60 + abs(total_edge))
    else:
        verdict = "FAIR"
        confidence = 50 + (10 - abs(total_edge)) * 3

    # Determine best for
    if get_side.average_age and give_side.average_age:
        if get_side.average_age < give_side.average_age - 1:
            best_for = "Rebuild"
        elif get_side.average_age > give_side.average_age + 1:
            best_for = "Contend"
        else:
            best_for = "Either"
    else:
        best_for = "Either"

    # Risk level
    risk_level = "Low"
    if any(p.risk.injury_risk_level == "High" for p in get_side.players):
        risk_level = "Medium"
    if sum(1 for p in get_side.players if p.risk.injury_risk_level == "High") >= 2:
        risk_level = "High"

    # Recommendations
    accept_if = []
    decline_if = []

    if verdict == "WIN":
        accept_if.append("You want to maximize value")
        if best_for == "Rebuild":
            accept_if.append("You're in a rebuild or have a 2+ year window")
    elif verdict == "LOSE":
        decline_if.append("Value matters to you")
        if best_for == "Contend":
            accept_if.append("You're competing this year and need immediate production")
    else:
        accept_if.append("The trade fits your team needs")
        decline_if.append("You can negotiate a better return")

    if best_for == "Rebuild":
        decline_if.append("You're competing this year")
    elif best_for == "Contend":
        decline_if.append("You're rebuilding for the future")

    # Suggested additions
    suggested = None
    if verdict == "LOSE" and abs(total_edge) > 10:
        value_gap = give_side.total_current_value - get_side.total_current_value
        if value_gap > 2000:
            suggested = f"Ask for a 1st round pick (~{value_gap:,} value gap)"
        elif value_gap > 1000:
            suggested = f"Ask for a 2nd round pick (~{value_gap:,} value gap)"
        elif value_gap > 500:
            suggested = f"Ask for a 3rd round pick (~{value_gap:,} value gap)"

    return APIResponse(
        data=EliteTradeAnalysis(
            verdict=verdict,
            verdict_score=round(total_edge, 1),
            confidence=round(confidence, 1),
            executive_summary=_generate_executive_summary(give_side, get_side, total_edge),
            best_for=best_for,
            risk_level=risk_level,
            give_side=give_side,
            get_side=get_side,
            score_breakdown=score_breakdown,
            key_insights=_generate_key_insights(give_side, get_side),
            recommendation_accept_if=accept_if,
            recommendation_decline_if=decline_if,
            suggested_additions=suggested,
            similar_trade_note="Elite WR-for-RB trades historically favor the WR side 62% of the time due to positional scarcity.",
        )
    )
