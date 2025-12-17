"""Pipeline orchestration for Dynasty Edge.

Provides:
- Full pipeline execution
- Daily refresh (KTC updates)
- Weekly retrain (ML model updates)
"""
from .dynasty_edge_pipeline import (
    DynastyEdgePipeline,
    run_daily_refresh,
    run_weekly_retrain
)
