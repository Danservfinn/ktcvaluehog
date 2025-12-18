"""Trade analysis Pydantic models."""

from pydantic import BaseModel, Field
from typing import Optional
from .player import PlayerSummary, Signal


class TradeSide(BaseModel):
    """One side of a trade (give or get)."""

    players: list[PlayerSummary]
    total_ktc_value: int = 0
    total_predicted_value: int | None = None
    average_age: float | None = None
    positions: dict[str, int] = Field(default_factory=dict)


class TradeRequest(BaseModel):
    """Trade analysis request."""

    give: list[str] = Field(..., description="Player IDs to give away")
    get: list[str] = Field(..., description="Player IDs to receive")
    league_format: str = Field("PPR", description="PPR, HALF_PPR, or STANDARD")
    team_needs: list[str] | None = Field(None, description="Positions team needs")


class TradeAnalysis(BaseModel):
    """Complete trade analysis response."""

    give_side: TradeSide
    get_side: TradeSide

    # Value Comparison
    ktc_differential: int = Field(..., description="get - give KTC value")
    predicted_differential: int | None = None

    # Recommendation
    recommendation: str = Field(..., description="ACCEPT, REJECT, or FAIR")
    confidence: float = Field(..., ge=0, le=100)
    reasoning: str

    # Signals
    give_side_signals: list[Signal] = []
    get_side_signals: list[Signal] = []

    # Context
    age_differential: float | None = Field(None, description="Positive = getting younger")
    positional_balance: str | None = None


class TradeTarget(BaseModel):
    """Suggested trade target based on roster needs."""

    player: PlayerSummary
    why: str
    estimated_cost: str = Field(..., description="e.g., 'Late 1st + 2nd'")
    signal: Signal


# === Elite Trade Analysis Models ===

class PlayerValueAnalysis(BaseModel):
    """Value analysis for a single player."""
    current_value: int
    value_rank: Optional[int] = None
    value_30d_change: Optional[float] = None
    value_90d_change: Optional[float] = None
    value_trend: Optional[str] = None  # "rising", "stable", "falling"
    projected_value_1yr: Optional[int] = None
    projected_value_2yr: Optional[int] = None
    projected_value_3yr: Optional[int] = None


class PlayerProductionProfile(BaseModel):
    """Production metrics for a single player."""
    season_ppg: Optional[float] = None
    last_4_ppg: Optional[float] = None
    ppg_trend: Optional[str] = None  # "up", "stable", "down"
    consistency_score: Optional[float] = None  # lower = more consistent
    boom_rate: Optional[float] = None  # % of games 20+ pts
    bust_rate: Optional[float] = None  # % of games <10 pts
    # Efficiency metrics
    epa_per_touch: Optional[float] = None
    target_share: Optional[float] = None
    touch_share: Optional[float] = None
    red_zone_share: Optional[float] = None
    wopr: Optional[float] = None
    adot: Optional[float] = None


class PlayerDynastyOutlook(BaseModel):
    """Dynasty-specific outlook for a player."""
    age: Optional[int] = None
    years_in_peak: Optional[int] = None  # Years remaining in peak window
    peak_window: Optional[str] = None  # e.g., "24-29 (WR)"
    aging_curve_position: Optional[str] = None  # "pre-peak", "peak", "post-peak", "declining"
    # ML Projections
    projected_ppg: Optional[float] = None
    projection_floor: Optional[float] = None
    projection_ceiling: Optional[float] = None
    projection_confidence: Optional[float] = None
    projected_pos_rank: Optional[int] = None


class PlayerRiskAssessment(BaseModel):
    """Risk factors for a player."""
    injury_burden_score: Optional[float] = None
    injury_risk_level: Optional[str] = None  # "low", "medium", "high"
    games_missed_3yr: Optional[int] = None
    key_injury_concerns: Optional[str] = None
    # Situation risk
    situation_score: Optional[float] = None  # 0-100
    qb_situation: Optional[str] = None
    team_stability: Optional[str] = None
    depth_chart_security: Optional[str] = None


class ElitePlayerAnalysis(BaseModel):
    """Complete analysis for a single player in elite trade report."""
    player_id: str
    name: str
    position: str
    team: Optional[str] = None
    age: Optional[int] = None

    value: PlayerValueAnalysis
    production: PlayerProductionProfile
    dynasty: PlayerDynastyOutlook
    risk: PlayerRiskAssessment

    # Quick summary
    overall_grade: Optional[str] = None  # "A+", "A", "B+", etc.
    one_liner: Optional[str] = None  # Brief assessment


class EliteTradeSide(BaseModel):
    """One side of an elite trade analysis."""
    players: list[ElitePlayerAnalysis]
    total_current_value: int = 0
    total_projected_value_1yr: Optional[int] = None
    total_projected_value_3yr: Optional[int] = None
    average_age: Optional[float] = None
    composite_risk_score: Optional[float] = None


class TradeScoreBreakdown(BaseModel):
    """Weighted score breakdown for trade verdict."""
    current_value_edge: float = 0  # % edge
    projected_value_edge: float = 0
    production_edge: float = 0
    age_edge: float = 0
    risk_edge: float = 0
    total_edge: float = 0


class EliteTradeRequest(BaseModel):
    """Request for elite trade analysis."""
    give: list[str] = Field(..., description="Player IDs to give away")
    get: list[str] = Field(..., description="Player IDs to receive")
    league_format: str = Field("PPR", description="PPR, HALF_PPR, or STANDARD")
    superflex: bool = False
    tep: bool = False  # Tight end premium


class EliteTradeAnalysis(BaseModel):
    """Complete elite trade analysis - research paper style."""

    # Executive Summary
    verdict: str  # "WIN", "LOSE", "FAIR"
    verdict_score: float  # -100 to +100
    confidence: float  # 0-100
    executive_summary: str  # 2-3 sentence narrative
    best_for: str  # "Rebuild", "Contend", "Either"
    risk_level: str  # "Low", "Medium", "High"

    # Trade Sides
    give_side: EliteTradeSide
    get_side: EliteTradeSide

    # Score Breakdown
    score_breakdown: TradeScoreBreakdown

    # Key Insights
    key_insights: list[str]  # 3-5 bullet points

    # Recommendations
    recommendation_accept_if: list[str]
    recommendation_decline_if: list[str]
    suggested_additions: Optional[str] = None  # "Ask for a 2nd to balance"

    # Historical Context
    similar_trade_note: Optional[str] = None
