"""League analysis Pydantic models."""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class LeagueType(str, Enum):
    DYNASTY = "dynasty"
    KEEPER = "keeper"
    REDRAFT = "redraft"


class ScoringType(str, Enum):
    PPR = "ppr"
    HALF_PPR = "half_ppr"
    STANDARD = "standard"


class TeamClassification(str, Enum):
    CONTENDER = "CONTENDER"
    FRINGE = "FRINGE"
    REBUILDER = "REBUILDER"


# === Sleeper API Response Models ===

class SleeperLeague(BaseModel):
    """League info from Sleeper API."""
    league_id: str
    name: str
    season: str
    status: str
    total_rosters: int
    roster_positions: list[str]
    scoring_settings: dict
    settings: dict


class SleeperRoster(BaseModel):
    """Roster from Sleeper API."""
    roster_id: int
    owner_id: Optional[str] = None
    players: Optional[list[str]] = None
    starters: Optional[list[str]] = None
    reserve: Optional[list[str]] = None
    taxi: Optional[list[str]] = None


class SleeperUser(BaseModel):
    """User from Sleeper API."""
    user_id: str
    display_name: str
    avatar: Optional[str] = None


class SleeperMatchup(BaseModel):
    """Matchup from Sleeper API."""
    roster_id: int
    matchup_id: int
    points: float
    starters: Optional[list[str]] = None
    players: Optional[list[str]] = None


class SleeperDraftPick(BaseModel):
    """Traded draft pick from Sleeper API."""
    season: str
    round: int
    roster_id: int
    previous_owner_id: int
    owner_id: int


# === Analysis Models ===

class PlayerAnalysis(BaseModel):
    """Individual player analysis within a roster."""
    player_id: str
    sleeper_id: Optional[str] = None
    name: str
    position: str
    team: Optional[str] = None
    age: Optional[float] = None

    # Values
    ktc_value: int = 0
    projected_ppg: Optional[float] = None

    # Career outlook
    years_until_peak: Optional[int] = None
    years_in_peak: Optional[int] = None
    career_phase: Optional[str] = None  # Pre-Peak, Peak, Post-Peak, Declining

    # Risk factors
    injury_risk: Optional[str] = None

    # Flags
    is_starter: bool = False
    is_breakout_candidate: bool = False
    is_sell_candidate: bool = False


class PositionalStrength(BaseModel):
    """Strength at a single position."""
    position: str
    starter_value: int = 0
    starter_ppg: float = 0.0
    depth_value: int = 0
    depth_ppg: float = 0.0
    total_value: int = 0
    player_count: int = 0
    grade: str = "C"  # A+, A, B+, B, C+, C, D, F


class RosterAnalysis(BaseModel):
    """Complete roster analysis for a team."""
    roster_id: int
    owner_id: Optional[str] = None
    team_name: str

    # Players
    players: list[PlayerAnalysis] = []
    starters: list[PlayerAnalysis] = []
    bench: list[PlayerAnalysis] = []

    # Aggregate values
    total_ktc_value: int = 0
    total_projected_ppg: float = 0.0
    starter_ppg: float = 0.0

    # Positional breakdown
    positional_strength: list[PositionalStrength] = []

    # Age analysis
    average_age: float = 0.0
    age_weighted_value: int = 0
    peak_window_start: Optional[int] = None
    peak_window_end: Optional[int] = None

    # Classification
    classification: TeamClassification = TeamClassification.FRINGE

    # Scores
    dynasty_health_score: float = 0.0
    championship_probability: float = 0.0

    # Draft capital
    future_picks: list[dict] = []
    draft_capital_value: int = 0


class TradeTarget(BaseModel):
    """A potential trade target on another team."""
    player: PlayerAnalysis
    owner_roster_id: int
    owner_team_name: str
    trade_value: int
    fit_score: float  # How well they fit YOUR roster (0-100)
    availability_score: float  # How likely owner is to trade (0-100)


class TradeSuggestion(BaseModel):
    """A specific trade suggestion."""
    give_players: list[PlayerAnalysis]
    get_players: list[PlayerAnalysis]
    give_value: int
    get_value: int
    value_differential: int

    # Impact analysis
    your_ppg_change: float
    their_ppg_change: float
    your_championship_change: float

    # Reasoning
    rationale: str
    win_win_score: float  # How mutually beneficial (0-100)


class TradePartner(BaseModel):
    """Analysis of a potential trade partner."""
    roster_id: int
    team_name: str
    owner_name: str

    # Their needs
    weak_positions: list[str] = []

    # What they have that you want
    trade_targets: list[TradeTarget] = []

    # Suggested trades
    suggestions: list[TradeSuggestion] = []

    # Overall trade compatibility
    compatibility_score: float = 0.0


class PowerRanking(BaseModel):
    """Single team in power rankings."""
    rank: int
    roster_id: int
    team_name: str
    owner_name: str

    # Values
    ktc_value: int
    projected_value: int  # Based on ML projections

    # Scores
    dynasty_health_score: float
    championship_probability: float

    # Classification
    classification: TeamClassification

    # Trend
    value_trend: str = "stable"  # rising, stable, falling


class StartSitRecommendation(BaseModel):
    """Start/sit recommendation for a player."""
    player: PlayerAnalysis
    recommendation: str  # START, SIT, FLEX
    confidence: float  # 0-100
    projected_points: float
    matchup_boost: float  # Positive = good matchup
    reasoning: str


class LineupOptimization(BaseModel):
    """Optimal lineup for a week."""
    week: int
    optimal_starters: list[PlayerAnalysis]
    projected_points: float

    # Current vs optimal
    current_starters: list[PlayerAnalysis]
    current_projected: float
    points_gained: float

    # Start/sit decisions
    start_sit: list[StartSitRecommendation]

    # Borderline decisions
    toss_ups: list[dict] = []


class ChampionshipSimulation(BaseModel):
    """Results of championship probability simulation."""
    simulations_run: int = 10000

    # Probabilities
    playoff_probability: float
    bye_probability: float
    championship_probability: float

    # Seeding distribution
    seed_probabilities: dict[int, float] = {}

    # Expected outcomes
    expected_wins: float
    expected_points_for: float

    # Scenarios
    best_case_record: str
    worst_case_record: str
    most_likely_record: str


class DynastyHealthBreakdown(BaseModel):
    """Breakdown of dynasty health score components."""
    total_score: float  # 0-100

    # Components
    age_score: float  # 0-25
    peak_overlap_score: float  # 0-20
    injury_risk_score: float  # 0-15
    position_wins_score: float  # 0-25
    draft_capital_score: float  # 0-15

    # Insights
    strengths: list[str] = []
    weaknesses: list[str] = []
    recommendations: list[str] = []


class LeagueAnalysis(BaseModel):
    """Complete league analysis response."""
    # League info
    league_id: str
    league_name: str
    season: str
    scoring_type: ScoringType
    total_teams: int

    # Your team
    your_roster_id: int
    your_analysis: RosterAnalysis
    your_dynasty_health: DynastyHealthBreakdown
    your_championship_odds: ChampionshipSimulation

    # League-wide
    power_rankings: list[PowerRanking]

    # Trade opportunities
    trade_partners: list[TradePartner]
    top_trade_suggestions: list[TradeSuggestion]

    # Alerts
    buy_low_targets: list[TradeTarget] = []
    sell_high_candidates: list[PlayerAnalysis] = []
    waiver_targets: list[PlayerAnalysis] = []

    # Metadata
    analysis_timestamp: str
    data_freshness: str


# === API Request/Response Models ===

class LeagueConnectRequest(BaseModel):
    """Request to connect a Sleeper account."""
    sleeper_username: str


class LeagueConnectResponse(BaseModel):
    """Response with user's leagues."""
    user_id: str
    username: str
    leagues: list[SleeperLeague]


class LeagueSelectRequest(BaseModel):
    """Request to analyze a specific league."""
    league_id: str
    user_roster_id: Optional[int] = None  # Which team is "yours"
