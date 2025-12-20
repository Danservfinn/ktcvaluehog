"""ML Monitor API - Autonomous ML Improvement System Monitoring."""

import os
from fastapi import APIRouter
from pydantic import BaseModel
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


def load_json_file(path: Path) -> Any:
    """Load JSON file with fallback."""
    if path.exists():
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            pass
    return None


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
