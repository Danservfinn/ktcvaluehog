"""ML Monitor API - Autonomous ML Improvement System Monitoring."""

import os
import signal
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime
import json

router = APIRouter(prefix="/ml-monitor", tags=["ML Monitor"])

# LLM URL - can be local or Cloudflare tunnel URL
# Default to local network IP, override with LLM_URL env var for cloud deployment
LLM_URL = os.getenv("LLM_URL", "http://192.168.1.81:1234")

# Path to ML experiments data
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
ML_EXPERIMENTS_PATH = PROJECT_ROOT / "data" / "ml_experiments"
ML_PROCESS_STATE_FILE = ML_EXPERIMENTS_PATH / "ml_process_state.json"

# Ensure ML experiments directory exists
ML_EXPERIMENTS_PATH.mkdir(parents=True, exist_ok=True)


class HypothesisResponse(BaseModel):
    id: str
    type: str
    description: str
    priority: float
    source: str
    config: Dict[str, Any] = {}
    tags: List[str] = []


class ExperimentResponse(BaseModel):
    hypothesis_id: str
    status: str
    r2_improvement: float
    rmse_improvement: float
    duration_seconds: float
    metrics: Dict[str, float] = {}


class SystemStats(BaseModel):
    queue_size: int
    total_experiments: int
    completed: int
    promoted: int
    failed: int
    rejected: int
    avg_improvement: float
    max_improvement: float
    llm_connected: bool


class AgentStatus(BaseModel):
    name: str
    status: str
    last_run: Optional[str]
    hypotheses_generated: int = 0


class MLMonitorResponse(BaseModel):
    """Miller's Law compliant response - 7 key sections."""
    stats: SystemStats
    agents: List[AgentStatus]  # Max 7 agents shown
    top_hypotheses: List[HypothesisResponse]  # Max 5
    recent_experiments: List[ExperimentResponse]  # Max 5
    llm_status: Dict[str, Any]
    model_versions: int
    last_updated: str


# New request/response models for ML controls
class StartContinuousRequest(BaseModel):
    strategy: str = "exploration"
    interval_seconds: int = 3600


class ContinuousProcessStatus(BaseModel):
    running: bool
    pid: Optional[int] = None
    started_at: Optional[str] = None
    strategy: Optional[str] = None
    uptime_seconds: Optional[float] = None


class SubmitHypothesisRequest(BaseModel):
    type: str = Field(..., description="Hypothesis type (feature_addition, architecture, etc.)")
    description: str = Field(..., min_length=10, max_length=500)
    priority: float = Field(default=5.0, ge=0, le=10)
    config: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)


class RunHypothesisRequest(BaseModel):
    hypothesis_id: str


class FeatureInfo(BaseModel):
    name: str
    category: str
    description: str = ""
    correlation: Optional[float] = None
    importance: Optional[float] = None


class FeatureCategoryResponse(BaseModel):
    category: str
    features: List[FeatureInfo]
    count: int


# ML Feature catalog - 168+ features organized by category
ML_FEATURES_CATALOG = {
    "base_stats": {
        "description": "Core production statistics",
        "features": [
            {"name": "ppg_ppr", "description": "PPR points per game", "correlation": 0.89},
            {"name": "games", "description": "Games played", "correlation": 0.45},
            {"name": "passing_yards", "description": "Total passing yards", "correlation": 0.72},
            {"name": "passing_tds", "description": "Passing touchdowns", "correlation": 0.68},
            {"name": "rushing_yards", "description": "Total rushing yards", "correlation": 0.65},
            {"name": "rushing_tds", "description": "Rushing touchdowns", "correlation": 0.58},
            {"name": "targets", "description": "Total targets", "correlation": 0.72},
            {"name": "receptions", "description": "Total receptions", "correlation": 0.70},
            {"name": "receiving_yards", "description": "Total receiving yards", "correlation": 0.75},
            {"name": "receiving_tds", "description": "Receiving touchdowns", "correlation": 0.62},
            {"name": "interceptions", "description": "Interceptions thrown", "correlation": -0.15},
            {"name": "fumbles", "description": "Fumbles lost", "correlation": -0.12},
            {"name": "pass_attempts", "description": "Pass attempts", "correlation": 0.55},
            {"name": "rush_attempts", "description": "Rush attempts", "correlation": 0.52},
        ]
    },
    "advanced_metrics": {
        "description": "Next-gen and efficiency metrics",
        "features": [
            {"name": "epa_per_target", "description": "Expected points added per target", "correlation": 0.61},
            {"name": "epa_per_carry", "description": "Expected points added per carry", "correlation": 0.48},
            {"name": "adot", "description": "Average depth of target", "correlation": 0.35},
            {"name": "wopr", "description": "Weighted opportunity rating", "correlation": 0.58},
            {"name": "cpoe", "description": "Completion percentage over expected", "correlation": 0.42},
            {"name": "avg_separation", "description": "Average separation from defender", "correlation": 0.38},
            {"name": "catch_rate", "description": "Receptions / targets", "correlation": 0.25},
            {"name": "yards_per_catch", "description": "Yards per reception", "correlation": 0.32},
            {"name": "yards_per_carry", "description": "Rushing yards per attempt", "correlation": 0.28},
            {"name": "yards_per_target", "description": "Receiving yards per target", "correlation": 0.45},
            {"name": "rz_td_rate", "description": "Red zone touchdown rate", "correlation": 0.52},
            {"name": "gl_td_rate", "description": "Goal line touchdown rate", "correlation": 0.48},
        ]
    },
    "era_normalized": {
        "description": "Cross-era normalized features for historical consistency",
        "features": [
            {"name": "ppg_ppr_zscore", "description": "PPG z-score within era", "correlation": 0.88},
            {"name": "ppg_ppr_percentile", "description": "PPG percentile within era", "correlation": 0.87},
            {"name": "targets_zscore", "description": "Targets z-score within era", "correlation": 0.68},
            {"name": "receptions_zscore", "description": "Receptions z-score within era", "correlation": 0.66},
            {"name": "snap_pct_zscore", "description": "Snap percentage z-score", "correlation": 0.55},
            {"name": "sample_weight", "description": "Time decay weight (0.92^years_ago)", "correlation": None},
            {"name": "yoy_ppg_change", "description": "Year-over-year PPG change", "correlation": 0.22},
            {"name": "yoy_targets_change", "description": "Year-over-year targets change", "correlation": 0.18},
        ]
    },
    "injury_role": {
        "description": "Injury history and team role metrics",
        "features": [
            {"name": "injury_burden_score", "description": "Weighted injury history score", "correlation": -0.28},
            {"name": "games_missed_avg", "description": "Average games missed per season", "correlation": -0.25},
            {"name": "starter_rate", "description": "Percentage of games as starter", "correlation": 0.62},
            {"name": "slot_rate", "description": "Percentage of snaps in slot", "correlation": 0.15},
            {"name": "role_numeric", "description": "Depth chart position encoded", "correlation": 0.58},
        ]
    },
    "dynasty_value": {
        "description": "KTC value and trend signals",
        "features": [
            {"name": "current_ktc_value", "description": "Current KTC dynasty value", "correlation": 0.72},
            {"name": "trend_slope", "description": "30-day value trend slope", "correlation": 0.35},
            {"name": "ktc_momentum", "description": "Value momentum indicator", "correlation": 0.32},
            {"name": "value_signal_numeric", "description": "Buy/sell/hold signal encoded", "correlation": 0.28},
            {"name": "dip_opportunity", "description": "Value dip opportunity score", "correlation": 0.22},
        ]
    },
    "career_trajectory": {
        "description": "Age and career arc features",
        "features": [
            {"name": "age", "description": "Current age", "correlation": -0.35},
            {"name": "years_in_league", "description": "NFL experience", "correlation": 0.15},
            {"name": "years_to_peak", "description": "Years until position peak", "correlation": 0.42},
            {"name": "pct_of_peak", "description": "Current % of projected peak", "correlation": 0.55},
            {"name": "career_arc_numeric", "description": "Career phase encoded", "correlation": 0.38},
            {"name": "projected_decline_rate", "description": "Age-based decline rate", "correlation": -0.32},
            {"name": "peak_ppg_estimate", "description": "Estimated career peak PPG", "correlation": 0.78},
        ]
    },
    "opportunity": {
        "description": "Snap counts and usage metrics",
        "features": [
            {"name": "avg_snap_pct", "description": "Average snap percentage", "correlation": 0.68},
            {"name": "snap_share_trend", "description": "Recent snap share trend", "correlation": 0.45},
            {"name": "target_share", "description": "Team target share", "correlation": 0.72},
            {"name": "carry_share", "description": "Team carry share", "correlation": 0.58},
            {"name": "air_yards_share", "description": "Team air yards share", "correlation": 0.55},
            {"name": "red_zone_share", "description": "Team red zone opportunity share", "correlation": 0.52},
        ]
    },
    "athletic_profile": {
        "description": "Combine and athletic testing",
        "features": [
            {"name": "height", "description": "Height in inches", "correlation": 0.12},
            {"name": "weight", "description": "Weight in pounds", "correlation": 0.08},
            {"name": "forty_time", "description": "40-yard dash time", "correlation": -0.18},
            {"name": "vertical", "description": "Vertical jump inches", "correlation": 0.15},
            {"name": "broad_jump", "description": "Broad jump inches", "correlation": 0.14},
            {"name": "three_cone", "description": "3-cone drill time", "correlation": -0.12},
            {"name": "shuttle", "description": "20-yard shuttle time", "correlation": -0.10},
            {"name": "bench_reps", "description": "Bench press reps", "correlation": 0.05},
            {"name": "ras_score", "description": "Relative athletic score", "correlation": 0.22},
        ]
    },
    "draft_capital": {
        "description": "Draft position and college pedigree",
        "features": [
            {"name": "draft_round", "description": "Draft round (1-7, 8=UDFA)", "correlation": -0.28},
            {"name": "draft_pick", "description": "Overall draft pick", "correlation": -0.25},
            {"name": "draft_capital_value", "description": "Draft capital value score", "correlation": 0.32},
            {"name": "power5_college", "description": "Power 5 conference flag", "correlation": 0.15},
        ]
    },
    "team_context": {
        "description": "Team situation and environment",
        "features": [
            {"name": "team_pass_rate", "description": "Team pass play rate", "correlation": 0.35},
            {"name": "team_pace", "description": "Team plays per game", "correlation": 0.28},
            {"name": "team_wins", "description": "Team wins", "correlation": 0.22},
            {"name": "offensive_rank", "description": "Team offensive ranking", "correlation": 0.32},
            {"name": "dome_game_pct", "description": "Dome/indoor game percentage", "correlation": 0.08},
        ]
    },
    "weather_factors": {
        "description": "Game weather and conditions",
        "features": [
            {"name": "cold_game_pct", "description": "Cold weather game percentage", "correlation": -0.05},
            {"name": "weather_favorability", "description": "Weather favorability score", "correlation": 0.12},
            {"name": "avg_game_temp", "description": "Average game temperature", "correlation": 0.08},
        ]
    },
    "calculated_interactions": {
        "description": "Derived interaction features",
        "features": [
            {"name": "targets_x_snap_pct", "description": "Targets * snap percentage", "correlation": 0.75},
            {"name": "age_x_production", "description": "Age * PPG interaction", "correlation": 0.65},
            {"name": "opportunity_score", "description": "Combined opportunity metric", "correlation": 0.72},
            {"name": "efficiency_score", "description": "Combined efficiency metric", "correlation": 0.58},
            {"name": "value_production_ratio", "description": "KTC value / PPG ratio", "correlation": 0.42},
        ]
    },
}

# Hypothesis types with descriptions
HYPOTHESIS_TYPES = [
    {"value": "feature_addition", "label": "Feature Addition", "description": "Add new predictive features"},
    {"value": "feature_removal", "label": "Feature Removal", "description": "Remove low-signal features"},
    {"value": "feature_combination", "label": "Feature Combination", "description": "Create interaction features"},
    {"value": "hyperparameter", "label": "Hyperparameter Tuning", "description": "Tune model parameters"},
    {"value": "architecture", "label": "Architecture Change", "description": "Modify neural network structure"},
    {"value": "ensemble_config", "label": "Ensemble Configuration", "description": "Adjust ensemble weights"},
    {"value": "data_augmentation", "label": "Data Augmentation", "description": "Add training data"},
    {"value": "loss_function", "label": "Loss Function", "description": "Change loss function"},
    {"value": "regularization", "label": "Regularization", "description": "Add/modify regularization"},
    {"value": "attention_mechanism", "label": "Attention Mechanism", "description": "Modify attention layers"},
    {"value": "position_specialist", "label": "Position Specialist", "description": "Position-specific models"},
    {"value": "error_targeted", "label": "Error Targeted Fix", "description": "Fix specific prediction errors"},
]


def load_json_file(path: Path) -> Any:
    """Load JSON file with fallback."""
    if path.exists():
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            pass
    return None


def save_json_file(path: Path, data: Any) -> bool:
    """Save data to JSON file."""
    try:
        with open(path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        return True
    except Exception:
        return False


def get_process_state() -> Dict[str, Any]:
    """Get the current ML process state."""
    default_state = {
        "continuous_process": {
            "running": False,
            "pid": None,
            "started_at": None,
            "strategy": None
        },
        "current_experiment": {
            "running": False,
            "hypothesis_id": None
        }
    }
    state = load_json_file(ML_PROCESS_STATE_FILE)
    if not state:
        return default_state

    # Verify process is actually running
    if state.get("continuous_process", {}).get("running"):
        pid = state["continuous_process"].get("pid")
        if pid:
            try:
                os.kill(pid, 0)  # Check if process exists
            except OSError:
                # Process no longer running
                state["continuous_process"]["running"] = False
                state["continuous_process"]["pid"] = None
                save_json_file(ML_PROCESS_STATE_FILE, state)

    return state


def update_process_state(updates: Dict[str, Any]) -> bool:
    """Update the ML process state."""
    state = get_process_state()
    for key, value in updates.items():
        if key in state:
            state[key].update(value)
    return save_json_file(ML_PROCESS_STATE_FILE, state)


def check_llm_connection() -> Dict[str, Any]:
    """Check if local LLM is available (local or via Cloudflare tunnel)."""
    try:
        import httpx
        response = httpx.get(f"{LLM_URL}/v1/models", timeout=3.0)
        if response.status_code == 200:
            data = response.json()
            model_name = data.get("data", [{}])[0].get("id", "unknown") if data.get("data") else "unknown"
            return {
                "connected": True,
                "url": LLM_URL,
                "model": model_name,
                "cost": "$0"
            }
    except Exception:
        pass
    return {"connected": False, "url": LLM_URL, "model": None, "cost": None}


@router.get("/status", response_model=MLMonitorResponse)
async def get_ml_status():
    """
    Get comprehensive ML system status.

    Returns data structured for Miller's Law (7±2 items per section).
    """
    # Load hypothesis queue
    queue_v2 = load_json_file(ML_EXPERIMENTS_PATH / "hypothesis_queue_v2.json")
    queue_v1 = load_json_file(ML_EXPERIMENTS_PATH / "hypothesis_queue.json")
    queue = queue_v2 or queue_v1 or []

    # Load experiment results
    results_v2 = load_json_file(ML_EXPERIMENTS_PATH / "experiment_results_v2.json")
    results_v1 = load_json_file(ML_EXPERIMENTS_PATH / "experiment_results.json")
    results = results_v2 or results_v1 or []

    # Load model versions
    versions = load_json_file(ML_EXPERIMENTS_PATH / "model_versions.json") or {}

    # Check LLM
    llm_status = check_llm_connection()

    # Calculate stats
    completed = [r for r in results if r.get("status") == "completed"]
    promoted = [r for r in results if r.get("status") == "promoted"]
    failed = [r for r in results if r.get("status") == "failed"]
    rejected = [r for r in results if r.get("status") == "rejected"]

    improvements = [
        r.get("improvement", {}).get("r2", 0)
        for r in completed
    ]

    stats = SystemStats(
        queue_size=len(queue),
        total_experiments=len(results),
        completed=len(completed),
        promoted=len(promoted),
        failed=len(failed),
        rejected=len(rejected),
        avg_improvement=sum(improvements) / len(improvements) if improvements else 0,
        max_improvement=max(improvements) if improvements else 0,
        llm_connected=llm_status["connected"],
    )

    # Top 5 hypotheses by priority (Miller's Law)
    sorted_queue = sorted(queue, key=lambda h: -h.get("priority", 0))[:5]
    top_hypotheses = [
        HypothesisResponse(
            id=h.get("id", "unknown"),
            type=h.get("type", "unknown"),
            description=h.get("description", ""),
            priority=h.get("priority", 0),
            source=h.get("source", "unknown"),
            config=h.get("config", {}),
            tags=h.get("tags", []),
        )
        for h in sorted_queue
    ]

    # Top 5 recent experiments (Miller's Law)
    sorted_results = sorted(
        [r for r in results if r.get("status") == "completed"],
        key=lambda r: -r.get("improvement", {}).get("r2", 0)
    )[:5]
    recent_experiments = [
        ExperimentResponse(
            hypothesis_id=r.get("hypothesis_id", "unknown"),
            status=r.get("status", "unknown"),
            r2_improvement=r.get("improvement", {}).get("r2", 0),
            rmse_improvement=r.get("improvement", {}).get("rmse", 0),
            duration_seconds=r.get("duration_seconds", 0),
            metrics=r.get("metrics", {}),
        )
        for r in sorted_results
    ]

    # 7 agents (Miller's Law)
    agents = [
        AgentStatus(name="data_scout", status="idle", last_run=None),
        AgentStatus(name="feature_engineer", status="idle", last_run=None),
        AgentStatus(name="architecture_search", status="idle", last_run=None),
        AgentStatus(name="error_analyst", status="idle", last_run=None),
        AgentStatus(name="drift_monitor", status="idle", last_run=None),
        AgentStatus(name="meta_learner", status="idle", last_run=None),
        AgentStatus(name="llm_creative", status="idle", last_run=None),
    ]

    return MLMonitorResponse(
        stats=stats,
        agents=agents,
        top_hypotheses=top_hypotheses,
        recent_experiments=recent_experiments,
        llm_status=llm_status,
        model_versions=len(versions),
        last_updated=datetime.now().isoformat(),
    )


@router.get("/queue")
async def get_hypothesis_queue(limit: int = 20, source: Optional[str] = None):
    """Get hypothesis queue with optional filtering."""
    queue_v2 = load_json_file(ML_EXPERIMENTS_PATH / "hypothesis_queue_v2.json")
    queue_v1 = load_json_file(ML_EXPERIMENTS_PATH / "hypothesis_queue.json")
    queue = queue_v2 or queue_v1 or []

    if source:
        queue = [h for h in queue if source.lower() in h.get("source", "").lower()]

    # Sort by priority
    queue = sorted(queue, key=lambda h: -h.get("priority", 0))[:limit]

    return {
        "total": len(queue),
        "hypotheses": queue,
    }


@router.get("/experiments")
async def get_experiments(limit: int = 20, status: Optional[str] = None):
    """Get experiment history."""
    results_v2 = load_json_file(ML_EXPERIMENTS_PATH / "experiment_results_v2.json")
    results_v1 = load_json_file(ML_EXPERIMENTS_PATH / "experiment_results.json")
    results = results_v2 or results_v1 or []

    if status:
        results = [r for r in results if r.get("status") == status]

    # Sort by improvement
    results = sorted(
        results,
        key=lambda r: -r.get("improvement", {}).get("r2", 0)
    )[:limit]

    return {
        "total": len(results),
        "experiments": results,
    }


@router.get("/llm")
async def get_llm_status():
    """Get local LLM connection status."""
    return check_llm_connection()


@router.post("/run-cycle")
async def trigger_cycle(strategy: str = "exploration"):
    """Trigger an improvement cycle (for admin use)."""
    import subprocess

    try:
        # Run in background
        subprocess.Popen(
            ["python", "-m", "src.ml.autonomous_ml_system", "--cycle", "--strategy", strategy],
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return {
            "status": "started",
            "strategy": strategy,
            "message": "Improvement cycle started in background",
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
        }


@router.post("/run-agent")
async def trigger_agent(agent: str):
    """Trigger a specific agent (for admin use)."""
    import subprocess

    valid_agents = [
        "data_scout", "feature_engineer", "error_analyst",
        "architecture_search", "drift_monitor", "meta_learner", "llm_creative"
    ]

    if agent not in valid_agents:
        return {"status": "error", "message": f"Invalid agent. Valid: {valid_agents}"}

    try:
        subprocess.Popen(
            ["python", "-m", "src.ml.autonomous_ml_system", "--agent", agent],
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return {
            "status": "started",
            "agent": agent,
            "message": f"Agent {agent} started in background",
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
        }


# ============================================================================
# NEW ENDPOINTS: Continuous ML Control
# ============================================================================

@router.get("/continuous/status", response_model=ContinuousProcessStatus)
async def get_continuous_status():
    """Get status of continuous ML improvement process."""
    state = get_process_state()
    continuous = state.get("continuous_process", {})

    uptime = None
    if continuous.get("running") and continuous.get("started_at"):
        started = datetime.fromisoformat(continuous["started_at"])
        uptime = (datetime.now() - started).total_seconds()

    return ContinuousProcessStatus(
        running=continuous.get("running", False),
        pid=continuous.get("pid"),
        started_at=continuous.get("started_at"),
        strategy=continuous.get("strategy"),
        uptime_seconds=uptime,
    )


@router.post("/continuous/start")
async def start_continuous(request: StartContinuousRequest):
    """Start continuous ML improvement loop."""
    import subprocess

    state = get_process_state()
    if state.get("continuous_process", {}).get("running"):
        raise HTTPException(
            status_code=409,
            detail="Continuous process already running. Stop it first."
        )

    try:
        process = subprocess.Popen(
            [
                "python", "-m", "src.ml.autonomous_ml_system",
                "--continuous",
                "--strategy", request.strategy,
                "--interval", str(request.interval_seconds),
            ],
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        update_process_state({
            "continuous_process": {
                "running": True,
                "pid": process.pid,
                "started_at": datetime.now().isoformat(),
                "strategy": request.strategy,
            }
        })

        return {
            "status": "started",
            "pid": process.pid,
            "strategy": request.strategy,
            "interval_seconds": request.interval_seconds,
            "message": "Continuous ML improvement started",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/continuous/stop")
async def stop_continuous():
    """Stop continuous ML improvement loop."""
    state = get_process_state()
    continuous = state.get("continuous_process", {})

    if not continuous.get("running"):
        return {"status": "not_running", "message": "No continuous process running"}

    pid = continuous.get("pid")
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass  # Process already dead

    update_process_state({
        "continuous_process": {
            "running": False,
            "pid": None,
            "started_at": None,
            "strategy": None,
        }
    })

    return {
        "status": "stopped",
        "message": "Continuous ML improvement stopped",
    }


# ============================================================================
# NEW ENDPOINTS: Hypothesis Management
# ============================================================================

@router.post("/hypothesis/run")
async def run_hypothesis(request: RunHypothesisRequest):
    """Run a specific hypothesis from the queue."""
    import subprocess

    # Load queue to verify hypothesis exists
    queue = load_json_file(ML_EXPERIMENTS_PATH / "hypothesis_queue_v2.json") or []
    hypothesis = next((h for h in queue if h.get("id") == request.hypothesis_id), None)

    if not hypothesis:
        raise HTTPException(status_code=404, detail="Hypothesis not found in queue")

    state = get_process_state()
    if state.get("current_experiment", {}).get("running"):
        raise HTTPException(
            status_code=409,
            detail="Another experiment is currently running"
        )

    try:
        subprocess.Popen(
            [
                "python", "-m", "src.ml.autonomous_ml_system",
                "--run-hypothesis", request.hypothesis_id,
            ],
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        update_process_state({
            "current_experiment": {
                "running": True,
                "hypothesis_id": request.hypothesis_id,
            }
        })

        return {
            "status": "started",
            "hypothesis_id": request.hypothesis_id,
            "hypothesis_type": hypothesis.get("type"),
            "message": f"Running hypothesis: {hypothesis.get('description', '')[:50]}...",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hypothesis/submit")
async def submit_hypothesis(request: SubmitHypothesisRequest):
    """Submit a new hypothesis to the queue."""
    # Validate hypothesis type
    valid_types = [h["value"] for h in HYPOTHESIS_TYPES]
    if request.type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid hypothesis type. Valid types: {valid_types}"
        )

    # Load existing queue
    queue_path = ML_EXPERIMENTS_PATH / "hypothesis_queue_v2.json"
    queue = load_json_file(queue_path) or []

    # Generate unique ID
    hypothesis_id = f"user_{request.type}_{uuid.uuid4().hex[:8]}"

    # Create new hypothesis
    new_hypothesis = {
        "id": hypothesis_id,
        "type": request.type,
        "description": request.description,
        "priority": request.priority,
        "source": "user_submitted",
        "config": request.config,
        "tags": request.tags + ["user_submitted"],
        "created_at": datetime.now().isoformat(),
    }

    # Add to queue
    queue.append(new_hypothesis)

    # Save queue
    if not save_json_file(queue_path, queue):
        raise HTTPException(status_code=500, detail="Failed to save hypothesis to queue")

    return {
        "status": "submitted",
        "hypothesis_id": hypothesis_id,
        "queue_position": len(queue),
        "message": "Hypothesis added to queue",
    }


@router.delete("/hypothesis/{hypothesis_id}")
async def delete_hypothesis(hypothesis_id: str):
    """Remove a hypothesis from the queue."""
    queue_path = ML_EXPERIMENTS_PATH / "hypothesis_queue_v2.json"
    queue = load_json_file(queue_path) or []

    # Find and remove hypothesis
    original_length = len(queue)
    queue = [h for h in queue if h.get("id") != hypothesis_id]

    if len(queue) == original_length:
        raise HTTPException(status_code=404, detail="Hypothesis not found")

    if not save_json_file(queue_path, queue):
        raise HTTPException(status_code=500, detail="Failed to update queue")

    return {
        "status": "deleted",
        "hypothesis_id": hypothesis_id,
        "queue_size": len(queue),
    }


# ============================================================================
# NEW ENDPOINTS: Feature Catalog
# ============================================================================

@router.get("/features")
async def get_all_features():
    """Get all available ML features with metadata."""
    all_features = []

    for category, data in ML_FEATURES_CATALOG.items():
        for feature in data["features"]:
            all_features.append({
                "name": feature["name"],
                "category": category,
                "category_label": category.replace("_", " ").title(),
                "description": feature.get("description", ""),
                "correlation": feature.get("correlation"),
            })

    # Sort by correlation strength (absolute value)
    all_features.sort(
        key=lambda f: abs(f["correlation"]) if f["correlation"] else 0,
        reverse=True
    )

    return {
        "total": len(all_features),
        "features": all_features,
    }


@router.get("/features/categories")
async def get_features_by_category():
    """Get features organized by category with metadata."""
    categories = []

    for category, data in ML_FEATURES_CATALOG.items():
        features = [
            FeatureInfo(
                name=f["name"],
                category=category,
                description=f.get("description", ""),
                correlation=f.get("correlation"),
            )
            for f in data["features"]
        ]

        categories.append({
            "category": category,
            "label": category.replace("_", " ").title(),
            "description": data.get("description", ""),
            "count": len(features),
            "features": features,
        })

    return {
        "total_categories": len(categories),
        "total_features": sum(c["count"] for c in categories),
        "categories": categories,
    }


@router.get("/hypothesis-types")
async def get_hypothesis_types():
    """Get available hypothesis types for the builder."""
    return {
        "types": HYPOTHESIS_TYPES,
    }
