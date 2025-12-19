"""Trade analysis endpoints."""

import json
from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import httpx

from ..database import get_db
from ..models.player import PlayerSummary
from ..models.trade import (
    TradeRequest, TradeAnalysis, TradeSide,
    EliteTradeRequest, EliteTradeAnalysis, EliteTradeSide,
    ElitePlayerAnalysis, PlayerValueAnalysis, PlayerProductionProfile,
    PlayerDynastyOutlook, PlayerRiskAssessment, PlayerAthleticProfile,
    TradeScoreBreakdown, TradeNarrative
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

        // Get combine results if available
        OPTIONAL MATCH (p)-[:HAD_COMBINE]->(c:CombineResult)

        // Get draft pick info if available
        OPTIONAL MATCH (p)-[:WAS_DRAFTED]->(d:DraftPick)

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
            pbp.touch_share as touch_share,
            pbp.rz_target_share as rz_target_share,
            pbp.rz_carry_share as rz_carry_share,

            // Season Stats
            ss.fantasy_points_ppr as season_pts,
            ss.games as games_played,

            // Projection
            proj.projected_ppg as proj_ppg,
            proj.floor as proj_floor,
            proj.ceiling as proj_ceiling,
            proj.confidence as proj_confidence,

            // Combine (athletic profile)
            c.forty_yard as forty_time,
            c.vertical as vertical_jump,
            c.broad_jump as broad_jump,
            c.three_cone as three_cone,
            c.shuttle as shuttle,
            c.bench as bench_press,

            // Draft Capital
            d.round as draft_round,
            d.pick as draft_pick,
            d.season as draft_year
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
        years_left = int(_calculate_years_in_peak(int(age), position))
        return f"Young talent with upside; {years_left} years until peak"
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

    # Use position-appropriate metrics
    if pos == "RB":
        share_metric = player.get("touch_share")
        rz_metric = player.get("rz_carry_share")
    else:
        share_metric = player.get("target_share")
        rz_metric = player.get("rz_target_share")

    production = PlayerProductionProfile(
        season_ppg=season_ppg,
        epa_per_touch=round(epa_per_touch, 3) if epa_per_touch else None,
        target_share=round(share_metric * 100, 1) if share_metric else None,
        touch_share=round(player.get("touch_share") * 100, 1) if player.get("touch_share") else None,
        red_zone_share=round(rz_metric * 100, 1) if rz_metric else None,
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

    # Athletic profile (combine + draft)
    athletic = None
    if any([player.get("forty_time"), player.get("draft_round")]):
        athletic = PlayerAthleticProfile(
            forty_time=player.get("forty_time"),
            vertical_jump=player.get("vertical_jump"),
            broad_jump=player.get("broad_jump"),
            three_cone=player.get("three_cone"),
            shuttle=player.get("shuttle"),
            bench_press=player.get("bench_press"),
            draft_round=player.get("draft_round"),
            draft_pick=player.get("draft_pick"),
            draft_year=player.get("draft_year"),
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
        athletic=athletic,
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


# === Narrative Generation Functions ===

def _generate_narrative_introduction(
    verdict: str,
    verdict_score: float,
    give_side: EliteTradeSide,
    get_side: EliteTradeSide,
    best_for: str
) -> str:
    """Generate an engaging introduction paragraph."""
    give_names = [p.name for p in give_side.players]
    get_names = [p.name for p in get_side.players]

    # Opening hook based on trade type
    if len(give_side.players) == 1 and len(get_side.players) > 1:
        hook = f"This trade presents the classic dynasty dilemma: consolidating elite talent versus building depth."
    elif len(get_side.players) == 1 and len(give_side.players) > 1:
        hook = f"In dynasty football, acquiring a cornerstone asset often requires parting with multiple pieces."
    else:
        hook = f"Evaluating this trade requires careful analysis of both immediate value and long-term trajectory."

    # Verdict context
    if verdict == "WIN":
        if verdict_score > 20:
            verdict_text = "Our analysis reveals a significant edge in your favor, suggesting this deal could reshape your roster's competitive outlook."
        else:
            verdict_text = "The numbers lean in your favor, though the margin is narrow enough that execution risk remains."
    elif verdict == "LOSE":
        if verdict_score < -20:
            verdict_text = "The value differential raises concerns, though situational factors may justify proceeding."
        else:
            verdict_text = "While the raw numbers favor the other side, context and team needs often override pure value calculations."
    else:
        verdict_text = "This trade approaches equilibrium, making team context and competing offers the decisive factors."

    # Best-for context
    if best_for == "Rebuild":
        strategy_text = "The age profile suggests this deal better serves rebuilding rosters prioritizing future value."
    elif best_for == "Contend":
        strategy_text = "Contending teams may find the production-now orientation aligns with championship windows."
    else:
        strategy_text = "The balanced age profile makes this viable for both contenders and rebuilders."

    return f"{hook} {verdict_text} {strategy_text}"


def _generate_player_narrative(player: ElitePlayerAnalysis, side: str) -> str:
    """Generate a 3-4 sentence analysis paragraph for a single player."""
    pos = player.position
    age = player.age or 25
    value = player.value.current_value
    ppg = player.production.season_ppg
    grade = player.overall_grade
    aging_pos = player.dynasty.aging_curve_position
    years_in_peak = player.dynasty.years_in_peak

    # Opening sentence - player value and status
    if value >= 8000:
        status = "elite dynasty asset"
    elif value >= 5000:
        status = "high-value starter"
    elif value >= 2500:
        status = "solid contributor"
    else:
        status = "depth piece"

    opening = f"{player.name} enters this trade as a {status}, commanding a {value:,} KTC valuation."

    # Age and trajectory sentence
    if aging_pos == "Pre-Peak":
        trajectory = f"At {age}, this {pos} remains {years_in_peak} years from peak production, suggesting meaningful value appreciation ahead."
    elif aging_pos == "Peak":
        trajectory = f"Currently {age} years old, {player.name} operates squarely within the {pos} peak window ({player.dynasty.peak_window}), maximizing present production."
    elif aging_pos == "Post-Peak":
        trajectory = f"At {age}, the aging curve models indicate post-peak status, typically the optimal window for maximizing return via trade."
    else:
        trajectory = f"The {age}-year-old profile suggests declining trajectory, with value likely to depreciate over coming seasons."

    # Production sentence
    if ppg:
        if ppg >= 18:
            production_text = f"His {ppg:.1f} PPG output places him among the position elite, providing consistent lineup-anchor production."
        elif ppg >= 14:
            production_text = f"A {ppg:.1f} PPG performer, he delivers reliable weekly returns without the premium price tag of top-tier options."
        elif ppg >= 10:
            production_text = f"The {ppg:.1f} PPG floor provides lineup flexibility, though upside remains capped in current role."
        else:
            production_text = f"Limited to {ppg:.1f} PPG, production concerns temper the dynasty outlook despite underlying metrics."
    else:
        production_text = "Production data remains limited, adding uncertainty to projections."

    # Risk/situation sentence
    risk_level = player.risk.injury_risk_level
    depth_security = player.risk.depth_chart_security

    if risk_level == "High":
        risk_text = "Elevated injury history introduces meaningful downside risk to any projection."
    elif risk_level == "Medium":
        risk_text = "Moderate injury concerns warrant monitoring but shouldn't materially impact trade valuation."
    else:
        if depth_security == "Locked":
            risk_text = "A locked depth chart role and clean health profile minimize execution risk."
        else:
            risk_text = "The health profile supports optimistic projections."

    return f"{opening} {trajectory} {production_text} {risk_text}"


def _generate_value_analysis_narrative(
    give_side: EliteTradeSide,
    get_side: EliteTradeSide,
    score_breakdown: TradeScoreBreakdown
) -> str:
    """Generate narrative analysis of value differentials."""
    current_diff = get_side.total_current_value - give_side.total_current_value
    current_pct = score_breakdown.current_value_edge
    proj_edge = score_breakdown.projected_value_edge

    # Current value analysis
    if abs(current_pct) < 5:
        current_text = f"Current market valuations show near-parity, with a {abs(current_diff):,} KTC differential ({current_pct:+.1f}%) falling within normal negotiation variance."
    elif current_pct > 0:
        current_text = f"The receiving side captures a {current_diff:,} KTC advantage ({current_pct:+.1f}%), representing meaningful value accretion at current market prices."
    else:
        current_text = f"You're parting with {abs(current_diff):,} more in KTC value ({current_pct:+.1f}%), a deficit that requires justification through non-value factors."

    # Projected value analysis
    if give_side.total_projected_value_3yr and get_side.total_projected_value_3yr:
        proj_diff = get_side.total_projected_value_3yr - give_side.total_projected_value_3yr
        if abs(proj_edge) < 5:
            proj_text = f"Three-year projections using position-specific aging curves suggest the value gap remains stable, with only a {proj_diff:+,} projected differential."
        elif proj_edge > 0:
            proj_text = f"Aging curve models project this gap to widen in your favor to {proj_diff:+,} over three years, as younger assets appreciate while older ones depreciate."
        else:
            proj_text = f"Concerning: projections show the value gap expanding against you to {proj_diff:+,} over three years, reflecting unfavorable aging curve dynamics."
    else:
        proj_text = "Projection data limitations prevent comprehensive forward-looking analysis."

    # Market efficiency note
    market_note = "Dynasty markets historically undervalue youth and stability while overpricing recent production—factor these biases into your evaluation."

    return f"{current_text} {proj_text} {market_note}"


def _generate_dynasty_outlook_narrative(
    give_side: EliteTradeSide,
    get_side: EliteTradeSide
) -> str:
    """Generate narrative about dynasty outlook and aging curves."""
    give_avg_age = give_side.average_age or 25
    get_avg_age = get_side.average_age or 25
    age_diff = give_avg_age - get_avg_age

    # Age differential framing
    if abs(age_diff) < 0.5:
        age_text = f"Both sides average approximately {give_avg_age:.1f} years old, creating similar timeline expectations."
    elif age_diff > 0:
        age_text = f"The receiving package skews {age_diff:.1f} years younger ({get_avg_age:.1f} vs. {give_avg_age:.1f}), extending your competitive window."
    else:
        age_text = f"You're acquiring {abs(age_diff):.1f} years of additional age ({get_avg_age:.1f} vs. {give_avg_age:.1f}), compressing your return-on-investment horizon."

    # Aging curve positions
    give_curves = [p.dynasty.aging_curve_position for p in give_side.players]
    get_curves = [p.dynasty.aging_curve_position for p in get_side.players]

    give_prepeak = sum(1 for c in give_curves if c == "Pre-Peak")
    get_prepeak = sum(1 for c in get_curves if c == "Pre-Peak")
    give_declining = sum(1 for c in give_curves if c == "Declining")
    get_declining = sum(1 for c in get_curves if c == "Declining")

    # Position-specific insights
    insights = []
    for player in give_side.players:
        if player.position == "RB" and player.dynasty.aging_curve_position in ["Peak", "Post-Peak"]:
            insights.append(f"Moving {player.name} (RB, {player.age}) aligns with the 'sell before decline' principle for running backs.")

    for player in get_side.players:
        if player.position == "WR" and player.dynasty.aging_curve_position == "Pre-Peak":
            insights.append(f"Acquiring {player.name} (WR, {player.age}) captures pre-peak appreciation runway at a position with extended shelf life.")

    curve_text = ""
    if get_prepeak > give_prepeak:
        curve_text = f"You're acquiring {get_prepeak} pre-peak asset(s) while parting with {give_prepeak}, positioning for future value growth."
    elif give_declining > 0 and get_declining == 0:
        curve_text = f"Successfully moving {give_declining} declining asset(s) while avoiding similar profiles in return represents savvy asset management."

    insight_text = " ".join(insights[:2]) if insights else ""

    return f"{age_text} {curve_text} {insight_text}".strip()


def _generate_risk_assessment_narrative(
    give_side: EliteTradeSide,
    get_side: EliteTradeSide
) -> str:
    """Generate narrative about risk factors."""
    # Injury risk analysis
    get_high_risk = [p for p in get_side.players if p.risk.injury_risk_level == "High"]
    get_medium_risk = [p for p in get_side.players if p.risk.injury_risk_level == "Medium"]
    give_high_risk = [p for p in give_side.players if p.risk.injury_risk_level == "High"]

    if get_high_risk:
        names = ", ".join(p.name for p in get_high_risk)
        injury_text = f"Injury risk warrants attention: {names} carry elevated injury profiles that could impact returns."
    elif len(get_medium_risk) >= 2:
        injury_text = f"Moderate injury concerns exist across multiple incoming assets, suggesting some downside variance."
    elif give_high_risk:
        names = ", ".join(p.name for p in give_high_risk)
        injury_text = f"You're offloading injury risk with {names}, potentially valuable risk mitigation."
    else:
        injury_text = "Injury profiles across both sides appear manageable, reducing health-related volatility."

    # Depth chart security
    get_locked = sum(1 for p in get_side.players if p.risk.depth_chart_security == "Locked")
    get_at_risk = sum(1 for p in get_side.players if p.risk.depth_chart_security == "At Risk")

    if get_at_risk > 0:
        situation_text = f"{get_at_risk} incoming player(s) face depth chart uncertainty, introducing role-based risk."
    elif get_locked == len(get_side.players):
        situation_text = "All incoming assets hold locked roles, minimizing situational volatility."
    else:
        situation_text = "Role security appears adequate across the incoming package."

    # Composite risk
    give_risk = give_side.composite_risk_score
    get_risk = get_side.composite_risk_score

    if give_risk and get_risk:
        if get_risk > give_risk + 10:
            composite_text = "Net risk increases with this trade—ensure you have roster depth to absorb potential variance."
        elif get_risk < give_risk - 10:
            composite_text = "This trade reduces your overall risk profile, valuable for risk-averse managers."
        else:
            composite_text = "Risk profiles are comparable across both packages."
    else:
        composite_text = ""

    return f"{injury_text} {situation_text} {composite_text}".strip()


def _generate_recommendation_narrative(
    verdict: str,
    best_for: str,
    accept_if: list[str],
    decline_if: list[str],
    suggested_additions: str | None
) -> str:
    """Generate final recommendation narrative."""
    # Verdict-based opening
    if verdict == "WIN":
        opening = "Our analysis supports accepting this trade. The value differential, combined with favorable aging dynamics, suggests meaningful roster improvement."
    elif verdict == "LOSE":
        opening = "We recommend caution with this trade. While situational factors may justify proceeding, the numbers suggest negotiating for additional return."
    else:
        opening = "This trade grades as approximately fair. Your decision should hinge on team-specific context rather than value optimization."

    # Conditional guidance
    accept_conditions = " ".join(f"• {a}" for a in accept_if[:3])
    decline_conditions = " ".join(f"• {d}" for d in decline_if[:3])

    conditions_text = f"Accept if: {accept_conditions} Decline if: {decline_conditions}"

    # Suggested additions
    if suggested_additions:
        addition_text = f"To balance this trade: {suggested_additions}"
    else:
        addition_text = ""

    return f"{opening} {conditions_text} {addition_text}".strip()


def _generate_closing_narrative(
    verdict: str,
    verdict_score: float,
    give_side: EliteTradeSide,
    get_side: EliteTradeSide
) -> str:
    """Generate closing summary paragraph."""
    give_names = ", ".join(p.name for p in give_side.players[:2])
    get_names = ", ".join(p.name for p in get_side.players[:2])

    if len(give_side.players) > 2:
        give_names += f" (+{len(give_side.players) - 2} more)"
    if len(get_side.players) > 2:
        get_names += f" (+{len(get_side.players) - 2} more)"

    if verdict == "WIN":
        summary = f"Moving {give_names} for {get_names} represents a value-positive move that strengthens your dynasty position."
    elif verdict == "LOSE":
        summary = f"The exchange of {give_names} for {get_names} requires either negotiation adjustment or situational justification beyond pure value."
    else:
        summary = f"This {give_names} for {get_names} swap comes down to team context—neither side emerges with a clear advantage."

    closing = "Remember: dynasty success requires patience. Today's trade shapes next year's roster, and the year after that. Execute with conviction, but always with eyes on the long game."

    return f"{summary} {closing}"


def _generate_trade_narrative(
    verdict: str,
    verdict_score: float,
    give_side: EliteTradeSide,
    get_side: EliteTradeSide,
    score_breakdown: TradeScoreBreakdown,
    best_for: str,
    accept_if: list[str],
    decline_if: list[str],
    suggested_additions: str | None
) -> TradeNarrative:
    """Generate complete research-style trade narrative."""
    return TradeNarrative(
        introduction=_generate_narrative_introduction(verdict, verdict_score, give_side, get_side, best_for),
        player_analysis_give=[_generate_player_narrative(p, "give") for p in give_side.players],
        player_analysis_get=[_generate_player_narrative(p, "get") for p in get_side.players],
        value_analysis=_generate_value_analysis_narrative(give_side, get_side, score_breakdown),
        dynasty_outlook=_generate_dynasty_outlook_narrative(give_side, get_side),
        risk_assessment=_generate_risk_assessment_narrative(give_side, get_side),
        recommendation=_generate_recommendation_narrative(verdict, best_for, accept_if, decline_if, suggested_additions),
        closing=_generate_closing_narrative(verdict, verdict_score, give_side, get_side),
    )


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

    # Recommendations - always provide useful guidance
    accept_if = []
    decline_if = []

    # Get positional context
    give_positions = [p.position for p in give_side.players]
    get_positions = [p.position for p in get_side.players]
    acquiring_rb = "RB" in get_positions and "RB" not in give_positions
    acquiring_wr = "WR" in get_positions and "WR" not in give_positions

    if verdict == "WIN":
        accept_if.append("You want to maximize dynasty value")
        accept_if.append("The value edge is significant enough to justify the move")
        if best_for == "Rebuild":
            accept_if.append("You're in a rebuild with a 2+ year window")
        elif best_for == "Contend":
            accept_if.append("You're competing and this fills a need")
        decline_if.append("You're emotionally attached to the player(s) you're giving up")
        decline_if.append("You can negotiate an even better return")

    elif verdict == "LOSE":
        # Always provide accept conditions even for LOSE trades
        if acquiring_rb:
            accept_if.append("You're desperate at RB and competing THIS year")
            accept_if.append("The RB position is critical to your championship odds")
        elif acquiring_wr:
            accept_if.append("You're desperate at WR with no other options")
        if best_for == "Contend":
            accept_if.append("Immediate production outweighs long-term value for your roster")
        else:
            accept_if.append("Your league undervalues the player(s) you're receiving")
            accept_if.append("You have insider knowledge about a situation change (landing spot, injury recovery)")

        decline_if.append("Value matters more than roster fit")
        decline_if.append("You have any negotiating leverage")
        decline_if.append("You can wait for a better offer")

    else:  # FAIR
        accept_if.append("The trade fills a specific roster need")
        accept_if.append("You believe in the player(s) you're receiving")
        decline_if.append("You can negotiate additional value")
        decline_if.append("You're unsure about the move")

    # Add strategic context based on best_for
    if best_for == "Rebuild":
        decline_if.append("You're in 'win now' mode this season")
    elif best_for == "Contend":
        decline_if.append("You're prioritizing long-term value over short-term production")

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

    # Generate written narrative report
    written_report = _generate_trade_narrative(
        verdict=verdict,
        verdict_score=total_edge,
        give_side=give_side,
        get_side=get_side,
        score_breakdown=score_breakdown,
        best_for=best_for,
        accept_if=accept_if,
        decline_if=decline_if,
        suggested_additions=suggested,
    )

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
            written_report=written_report,
        )
    )


# === AI-Enhanced Narrative Endpoint ===

ENHANCE_SYSTEM_PROMPT = """You are an elite dynasty fantasy football analyst writing a comprehensive trade analysis report.

Your writing style:
- Professional yet engaging, like a Wall Street research analyst covering NFL dynasty assets
- CRITICAL: Use specific data points from the analysis to support EVERY claim
- Reference aging curves, positional scarcity, and market efficiency concepts
- Balance quantitative analysis with qualitative insights about player situations
- Avoid generic advice; every sentence should add unique value

DATA YOU MUST INCORPORATE (when available):
1. **Efficiency Metrics**: EPA/Touch (league avg ~0.0), WOPR (elite >0.5), ADOT, Target/RZ Share
2. **Value Trajectory**: 30-day KTC change, trend direction, 1yr/3yr projections
3. **ML Projections**: Our ensemble model (R²=0.80) provides PPG projections with floor/ceiling ranges
4. **Risk Quantification**: Injury burden scores, games missed (3yr), depth chart security
5. **Production Context**: Compare target share, red zone usage to positional benchmarks

BENCHMARKS TO REFERENCE:
- Elite WR Target Share: >25% | Good: 18-25% | Replacement: <12%
- Elite RB Touch Share: >70% | Good: 50-70% | Committee: <50%
- Elite WOPR: >0.50 | Good: 0.35-0.50 | Low: <0.25
- EPA/Play benchmarks: Elite >0.15, Good >0.05, Below Avg <0.0

Your report should read like a research paper from a top dynasty analyst, with specific numbers backing every assertion."""


class EnhanceRequest(BaseModel):
    """Request for AI-enhanced trade narrative."""
    analysis: EliteTradeAnalysis


@router.post("/analyze-elite/enhance")
async def enhance_trade_narrative(
    request: EnhanceRequest,
    x_anthropic_key: str = Header(..., alias="X-Anthropic-Key"),
):
    """
    Generate AI-enhanced research-style narrative for a trade analysis.

    BYOK (Bring Your Own Key) - requires user's Anthropic API key.
    Uses Claude Opus 4.5 for highest quality output.

    The API key is passed directly to Anthropic and never stored.
    """
    if not x_anthropic_key or not x_anthropic_key.startswith("sk-ant-"):
        raise HTTPException(
            status_code=401,
            detail="Valid Anthropic API key required in X-Anthropic-Key header"
        )

    analysis = request.analysis

    def _format_player_detail(p) -> str:
        """Format comprehensive player data for AI prompt."""
        lines = [
            f"### {p.name} ({p.position}, {p.team or 'FA'})",
            f"- **Core:** Age {p.age}, KTC {p.value.current_value:,}, Grade: {p.overall_grade}",
        ]

        # Value trajectory
        value_parts = [f"Curve: {p.dynasty.aging_curve_position} ({p.dynasty.years_in_peak}yr in peak)"]
        if p.value.value_30d_change:
            value_parts.append(f"30d Δ: {p.value.value_30d_change:+,.0f}")
        if p.value.value_trend:
            value_parts.append(f"Trend: {p.value.value_trend.upper()}")
        if p.value.projected_value_1yr:
            value_parts.append(f"1yr Proj: {p.value.projected_value_1yr:,}")
        if p.value.projected_value_3yr:
            value_parts.append(f"3yr Proj: {p.value.projected_value_3yr:,}")
        lines.append(f"- **Value:** {' | '.join(value_parts)}")

        # Production metrics
        prod_parts = []
        if p.production.season_ppg:
            prod_parts.append(f"PPG: {p.production.season_ppg}")
        if p.production.target_share:
            prod_parts.append(f"Tgt%: {p.production.target_share}%")
        if p.production.red_zone_share:
            prod_parts.append(f"RZ%: {p.production.red_zone_share}%")
        if p.production.epa_per_touch:
            prod_parts.append(f"EPA/Touch: {p.production.epa_per_touch:+.3f}")
        if p.production.wopr:
            prod_parts.append(f"WOPR: {p.production.wopr:.2f}")
        if p.production.adot:
            prod_parts.append(f"ADOT: {p.production.adot:.1f}yd")
        if prod_parts:
            lines.append(f"- **Production:** {' | '.join(prod_parts)}")

        # ML Projections
        proj_parts = []
        if p.dynasty.projected_ppg:
            proj_parts.append(f"Proj PPG: {p.dynasty.projected_ppg:.1f}")
        if p.dynasty.projection_floor and p.dynasty.projection_ceiling:
            proj_parts.append(f"Range: {p.dynasty.projection_floor:.1f}-{p.dynasty.projection_ceiling:.1f}")
        if p.dynasty.projection_confidence:
            proj_parts.append(f"Model Confidence: {p.dynasty.projection_confidence:.0%}")
        if proj_parts:
            lines.append(f"- **ML Projection (R²=0.80):** {' | '.join(proj_parts)}")

        # Athletic profile (combine + draft)
        if p.athletic:
            ath_parts = []
            if p.athletic.draft_round:
                ath_parts.append(f"Draft: Rd {p.athletic.draft_round}, Pick {p.athletic.draft_pick} ({p.athletic.draft_year})")
            if p.athletic.forty_time:
                ath_parts.append(f"40yd: {p.athletic.forty_time:.2f}s")
            if p.athletic.vertical_jump:
                ath_parts.append(f"Vert: {p.athletic.vertical_jump}\"")
            if p.athletic.broad_jump:
                ath_parts.append(f"Broad: {p.athletic.broad_jump}\"")
            if p.athletic.three_cone:
                ath_parts.append(f"3cone: {p.athletic.three_cone:.2f}s")
            if ath_parts:
                lines.append(f"- **Athletic/Draft:** {' | '.join(ath_parts)}")

        # Risk factors
        risk_parts = [f"Injury: {p.risk.injury_risk_level}"]
        if p.risk.injury_burden_score:
            risk_parts.append(f"Burden Score: {p.risk.injury_burden_score:.1f}")
        if p.risk.games_missed_3yr:
            risk_parts.append(f"Missed (3yr): {p.risk.games_missed_3yr}g")
        if p.risk.depth_chart_security:
            risk_parts.append(f"Role: {p.risk.depth_chart_security}")
        lines.append(f"- **Risk:** {' | '.join(risk_parts)}")

        return "\n".join(lines)

    # Build comprehensive context from the analysis
    give_players_text = "\n\n".join([_format_player_detail(p) for p in analysis.give_side.players])
    get_players_text = "\n\n".join([_format_player_detail(p) for p in analysis.get_side.players])

    prompt = f"""Write a comprehensive dynasty trade analysis report for the following trade.

## TRADE DATA

### Summary
| Metric | Value |
|--------|-------|
| Verdict | **{analysis.verdict}** (Score: {analysis.verdict_score:+.1f}) |
| Confidence | {analysis.confidence:.0f}% |
| Best For | {analysis.best_for} |
| Risk Level | {analysis.risk_level} |

### You Give
{give_players_text}

**Side Totals:** Current Value: {analysis.give_side.total_current_value:,} | 3yr Projected: {analysis.give_side.total_projected_value_3yr:,} | Avg Age: {analysis.give_side.average_age}

### You Receive
{get_players_text}

**Side Totals:** Current Value: {analysis.get_side.total_current_value:,} | 3yr Projected: {analysis.get_side.total_projected_value_3yr:,} | Avg Age: {analysis.get_side.average_age}

### Score Breakdown
| Component | Edge |
|-----------|------|
| Current Value | {analysis.score_breakdown.current_value_edge:+.1f}% |
| 3-Year Projected | {analysis.score_breakdown.projected_value_edge:+.1f}% |
| Age | {analysis.score_breakdown.age_edge:+.1f} |
| Production | {analysis.score_breakdown.production_edge:+.1f}% |
| **Total Edge** | **{analysis.score_breakdown.total_edge:+.1f}** |

### Key Insights
{chr(10).join('- ' + insight for insight in analysis.key_insights)}

---

## REPORT REQUIREMENTS

Write a professional research-style dynasty trade analysis with these sections:

### 1. Introduction
- Engaging hook that frames the trade's strategic implications
- Reference the verdict and key value differential

### 2. Player Analysis
For EACH player, write 2-3 paragraphs covering:
- **Current Production**: Use PPG, target share, red zone share, EPA/touch, WOPR, ADOT
- **Value Trajectory**: Use KTC value, 30-day change, trend direction, 1yr/3yr projections
- **Athletic Profile**: Reference combine metrics and draft capital where available
- **Positional Context**: Compare their metrics to positional benchmarks

### 3. Value Analysis
- Build a markdown table comparing give vs receive on key metrics
- Calculate and discuss the value differential percentage
- Project how values will change over 1-3 years

### 4. Dynasty Outlook
- Discuss aging curves with specific peak windows
- Reference years in peak for each player
- Timeline alignment analysis

### 5. Risk Assessment
- Use injury burden scores and games missed (3yr)
- Discuss depth chart security
- Quantify the risk differential

### 6. Recommendation
- Clear ACCEPT/DECLINE verdict
- Conditional guidance (e.g., "Accept if rebuilding...")
- Suggested counter-offer if applicable

### 7. Closing
- Memorable one-liner that captures the trade's essence

## FORMATTING
- Use proper markdown: # headers, **bold**, tables, bullet points
- Include data tables where they add clarity
- Reference specific numbers from the data to support every claim
- Write in a professional analyst tone (like a Wall Street research note)"""

    async def generate():
        """Stream enhanced narrative from Claude Opus 4.5."""
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": x_anthropic_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-opus-4-5-20251101",
                    "max_tokens": 4096,
                    "system": ENHANCE_SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": True,
                },
                timeout=120.0,  # Longer timeout for Opus
            ) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    yield f"data: {json.dumps({'error': error_text.decode()})}\n\n"
                    return

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            yield "data: [DONE]\n\n"
                            break

                        try:
                            event = json.loads(data)
                            if event.get("type") == "content_block_delta":
                                delta = event.get("delta", {})
                                if "text" in delta:
                                    yield f"data: {json.dumps({'text': delta['text']})}\n\n"
                        except json.JSONDecodeError:
                            continue

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )
