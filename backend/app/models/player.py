"""Player-related Pydantic models."""

from datetime import date
from enum import Enum
from pydantic import BaseModel, Field


class Position(str, Enum):
    QB = "QB"
    RB = "RB"
    WR = "WR"
    TE = "TE"
    K = "K"
    DEF = "DEF"


class Signal(str, Enum):
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"


class PlayerSummary(BaseModel):
    """Minimal player info for lists and search results."""

    player_id: str = Field(..., description="Unique player identifier (gsis_id)")
    name: str
    position: Position | None = None
    team: str | None = None
    age: float | None = None
    ktc_value: int | None = Field(None, description="Current KTC dynasty value")
    signal: Signal | None = None


class AthleticProfile(BaseModel):
    """NFL Combine athletic testing results."""

    forty_yard: float | None = Field(None, description="40-yard dash time")
    vertical: float | None = Field(None, description="Vertical jump (inches)")
    broad_jump: int | None = Field(None, description="Broad jump (inches)")
    cone: float | None = Field(None, description="3-cone drill time")
    shuttle: float | None = Field(None, description="20-yard shuttle time")
    bench: int | None = Field(None, description="Bench press reps")
    height: int | None = Field(None, description="Height (inches)")
    weight: int | None = Field(None, description="Weight (pounds)")
    arm_length: float | None = Field(None, description="Arm length (inches)")
    hand_size: float | None = Field(None, description="Hand size (inches)")


class ContractInfo(BaseModel):
    """Player contract details."""

    apy: float | None = Field(None, description="Average annual value")
    guaranteed: float | None = Field(None, description="Total guaranteed money")
    years_remaining: int | None = None
    contract_year: bool = False


class ValueHistory(BaseModel):
    """KTC value snapshot."""

    date: date
    value: int
    rank: int | None = None
    positional_rank: int | None = None


class PlayerSignal(BaseModel):
    """Buy/sell signal with reasoning."""

    signal: Signal
    edge_score: float = Field(..., description="Value delta percentage")
    predicted_value: int | None = None
    current_value: int
    reasoning: str | None = None


class Player(BaseModel):
    """Full player profile with all available data."""

    # Identifiers
    player_id: str = Field(..., description="Primary ID (gsis_id)")
    sleeper_id: str | None = None
    name: str
    first_name: str | None = None
    last_name: str | None = None

    # Basic Info
    position: Position | None = None
    team: str | None = None
    age: float | None = None
    experience: int | None = None
    college: str | None = None

    # Draft Info
    draft_year: int | None = None
    draft_round: int | None = None
    draft_pick: int | None = None
    draft_age: float | None = None

    # Valuation
    ktc_value: int | None = None
    ktc_rank: int | None = None
    ktc_positional_rank: int | None = None
    ktc_trend: str | None = Field(None, description="UP, DOWN, or STABLE")

    # ML Predictions
    predicted_value: int | None = None
    edge_score: float | None = Field(None, description="(predicted - actual) / actual * 100")
    signal: Signal | None = None

    # Athletic Profile
    athletic: AthleticProfile | None = None

    # Contract
    contract: ContractInfo | None = None

    # Playing Time
    total_snaps: int | None = None
    snap_percentage: float | None = None
    snap_trend: str | None = None

    # Injury
    injury_risk: float | None = Field(None, ge=0, le=100)
    games_missed_career: int | None = None

    # 2025 Production
    ppg_ppr: float | None = None
    total_points_2025: float | None = None
    games_played_2025: int | None = None

    # Career Stage
    career_stage: str | None = Field(None, description="ASCENDING, PRIME, DECLINING, etc.")


class PlayerComparison(BaseModel):
    """Side-by-side player comparison."""

    players: list[Player]
    comparison_summary: str | None = None
    recommendation: str | None = None


class PlayerSearchParams(BaseModel):
    """Search/filter parameters for players."""

    position: Position | None = None
    team: str | None = None
    min_age: int | None = None
    max_age: int | None = None
    min_ktc: int | None = None
    max_ktc: int | None = None
    signal: Signal | None = None
    min_snap_pct: float | None = Field(None, ge=0, le=100)
    limit: int = Field(50, ge=1, le=200)
    offset: int = Field(0, ge=0)
    sort_by: str = "ktc_value"
    sort_desc: bool = True
