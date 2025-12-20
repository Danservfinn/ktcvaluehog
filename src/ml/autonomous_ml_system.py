#!/usr/bin/env python3
"""
Autonomous ML Improvement System v2

A comprehensive self-improving machine learning system with multiple specialized agents
that work together to continuously discover, test, and deploy model improvements.

Architecture:
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          ML IMPROVEMENT ORCHESTRATOR                             │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │ DataScout    │  │ Feature      │  │ Architecture │  │ Hyperparameter│        │
│  │ Agent        │  │ Engineer     │  │ Search Agent │  │ Optimizer    │        │
│  │              │  │ Agent        │  │              │  │              │        │
│  │ - Discovers  │  │ - Generates  │  │ - NAS        │  │ - Bayesian   │        │
│  │   new data   │  │   features   │  │ - Ensemble   │  │   optimization│        │
│  │ - Quality    │  │ - Evaluates  │  │   search     │  │ - Grid search│        │
│  │   checks     │  │   candidates │  │ - Layer      │  │ - Learning   │        │
│  └──────────────┘  └──────────────┘  │   configs    │  │   rate tuning│        │
│                                       └──────────────┘  └──────────────┘        │
│                                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │ Error        │  │ Drift        │  │ Meta         │  │ Model        │        │
│  │ Analyst      │  │ Monitor      │  │ Learner      │  │ Promoter     │        │
│  │              │  │              │  │              │  │              │        │
│  │ - Clusters   │  │ - Tracks     │  │ - Predicts   │  │ - Canary     │        │
│  │   failures   │  │   drift      │  │   success    │  │   deploys    │        │
│  │ - Proposes   │  │ - Triggers   │  │ - Prioritizes│  │ - Rollback   │        │
│  │   fixes      │  │   retrain    │  │   queue      │  │ - A/B test   │        │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘        │
│                                                                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                          EXPERIMENT REGISTRY & STATE                             │
│  - Hypothesis queue (priority-sorted)                                            │
│  - Experiment results history                                                    │
│  - Model versions and lineage                                                    │
│  - Production metrics timeline                                                   │
└─────────────────────────────────────────────────────────────────────────────────┘

Usage:
    # Run full improvement cycle
    python -m src.ml.autonomous_ml_system --cycle

    # Run continuously (hourly cycles)
    python -m src.ml.autonomous_ml_system --continuous --interval 3600

    # Run specific agent
    python -m src.ml.autonomous_ml_system --agent data_scout

    # Generate status report
    python -m src.ml.autonomous_ml_system --report

    # Run with specific strategy
    python -m src.ml.autonomous_ml_system --strategy adversarial
"""

import sys
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Tuple, Set, Callable
from datetime import datetime, timedelta
from enum import Enum
from abc import ABC, abstractmethod
import json
import hashlib
import time
import logging
import argparse
import pickle
import traceback
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import numpy as np
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

# LLM agents loaded after logger is configured
LLM_AVAILABLE = False
LLMAgentHub = None

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(PROJECT_ROOT / 'logs' / 'autonomous_ml.log', mode='a')
    ]
)
logger = logging.getLogger('autonomous_ml_v2')

# Ensure logs directory exists
(PROJECT_ROOT / 'logs').mkdir(exist_ok=True)

# Load LLM agents for intelligent reasoning (cost: $0, uses local LLM)
try:
    from src.ml.llm_agents import (
        LLMAgentHub,
        LLMBrainstormAgent,
        LLMCodeGeneratorAgent,
        LLMErrorAnalyzerAgent,
        LLMHypothesisPrioritizer,
        LLMReportGenerator,
        LLMConfig,
    )
    LLM_AVAILABLE = True
    logger.info("LLM agents loaded - local LLM at http://172.16.108.209:1234")
except ImportError as e:
    LLM_AVAILABLE = False
    LLMAgentHub = None
    logger.info(f"LLM agents not available: {e}")


# =============================================================================
# Enums and Data Classes
# =============================================================================

class HypothesisType(Enum):
    FEATURE_ADDITION = "feature_addition"
    FEATURE_REMOVAL = "feature_removal"
    FEATURE_COMBINATION = "feature_combination"
    HYPERPARAMETER = "hyperparameter"
    ARCHITECTURE = "architecture"
    ENSEMBLE_CONFIG = "ensemble_config"
    DATA_AUGMENTATION = "data_augmentation"
    LOSS_FUNCTION = "loss_function"
    REGULARIZATION = "regularization"
    ATTENTION_MECHANISM = "attention_mechanism"
    EMBEDDING_DIM = "embedding_dim"
    LEARNING_RATE_SCHEDULE = "lr_schedule"
    POSITION_SPECIALIST = "position_specialist"
    ERROR_TARGETED_FIX = "error_targeted"


class ExperimentStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PROMOTED = "promoted"
    REJECTED = "rejected"
    CANARY = "canary"
    ROLLED_BACK = "rolled_back"


class AgentStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    BLOCKED = "blocked"
    ERROR = "error"


class ImprovementStrategy(Enum):
    EXPLORATION = "exploration"      # Try diverse hypotheses
    EXPLOITATION = "exploitation"    # Focus on promising areas
    ADVERSARIAL = "adversarial"      # Target prediction failures
    ENSEMBLE = "ensemble"            # Improve ensemble composition
    ARCHITECTURE = "architecture"    # Neural architecture search
    DATA_CENTRIC = "data_centric"    # Focus on data quality/augmentation


@dataclass
class Hypothesis:
    """A proposed improvement to test."""
    id: str
    type: HypothesisType
    description: str
    config: Dict[str, Any]
    priority: float = 5.0
    expected_improvement: float = 0.0
    novelty_score: float = 0.5
    resource_cost: float = 1.0
    created_at: datetime = field(default_factory=datetime.now)
    source: str = "auto"
    parent_hypothesis: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'type': self.type.value,
            'description': self.description,
            'config': self.config,
            'priority': self.priority,
            'expected_improvement': self.expected_improvement,
            'novelty_score': self.novelty_score,
            'resource_cost': self.resource_cost,
            'created_at': self.created_at.isoformat(),
            'source': self.source,
            'parent_hypothesis': self.parent_hypothesis,
            'tags': self.tags,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Hypothesis':
        return cls(
            id=data['id'],
            type=HypothesisType(data['type']),
            description=data['description'],
            config=data['config'],
            priority=data.get('priority', 5.0),
            expected_improvement=data.get('expected_improvement', 0.0),
            novelty_score=data.get('novelty_score', 0.5),
            resource_cost=data.get('resource_cost', 1.0),
            source=data.get('source', 'auto'),
            parent_hypothesis=data.get('parent_hypothesis'),
            tags=data.get('tags', []),
        )


@dataclass
class ExperimentResult:
    """Results from running an experiment."""
    hypothesis_id: str
    status: ExperimentStatus
    metrics: Dict[str, float]
    baseline_metrics: Dict[str, float]
    improvement: Dict[str, float]
    duration_seconds: float
    position_metrics: Dict[str, Dict[str, float]] = field(default_factory=dict)
    artifacts: Dict[str, str] = field(default_factory=dict)
    error_message: Optional[str] = None
    model_path: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def r2_improvement(self) -> float:
        return self.improvement.get('r2', 0.0)

    @property
    def rmse_improvement(self) -> float:
        return self.improvement.get('rmse', 0.0)

    def to_dict(self) -> Dict:
        return {
            'hypothesis_id': self.hypothesis_id,
            'status': self.status.value,
            'metrics': self.metrics,
            'baseline_metrics': self.baseline_metrics,
            'improvement': self.improvement,
            'position_metrics': self.position_metrics,
            'duration_seconds': self.duration_seconds,
            'artifacts': self.artifacts,
            'error_message': self.error_message,
            'model_path': self.model_path,
            'timestamp': self.timestamp.isoformat(),
        }


@dataclass
class DataSource:
    """Metadata about a data source."""
    name: str
    url: str
    last_checked: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    freshness_hours: float = 24.0
    quality_score: float = 1.0
    records_count: int = 0
    schema: Dict[str, str] = field(default_factory=dict)


@dataclass
class ProductionMetrics:
    """Metrics from production model."""
    timestamp: datetime
    predictions_count: int
    mean_error: float
    median_error: float
    p95_error: float
    position_errors: Dict[str, float]
    feature_importance: Dict[str, float]


# =============================================================================
# Enhanced Experiment Registry
# =============================================================================

class ExperimentRegistry:
    """
    Enhanced experiment registry with:
    - Persistent state across restarts
    - Experiment lineage tracking
    - Production metrics history
    - Model versioning
    """

    def __init__(self, registry_path: Path = None):
        self.registry_path = registry_path or PROJECT_ROOT / "data" / "ml_experiments"
        self.registry_path.mkdir(parents=True, exist_ok=True)

        self.hypothesis_queue: List[Hypothesis] = []
        self.results: Dict[str, ExperimentResult] = {}
        self.production_metrics: List[ProductionMetrics] = []
        self.model_versions: Dict[str, Dict] = {}
        self.experiment_lineage: Dict[str, List[str]] = {}

        self._lock = threading.Lock()
        self._load_state()

    def _load_state(self):
        """Load all persisted state."""
        # Load hypothesis queue
        queue_file = self.registry_path / "hypothesis_queue_v2.json"
        if queue_file.exists():
            try:
                with open(queue_file) as f:
                    data = json.load(f)
                    self.hypothesis_queue = [Hypothesis.from_dict(h) for h in data]
            except Exception as e:
                logger.warning(f"Failed to load hypothesis queue: {e}")

        # Load experiment results
        results_file = self.registry_path / "experiment_results_v2.json"
        if results_file.exists():
            try:
                with open(results_file) as f:
                    data = json.load(f)
                    for r in data[-500:]:  # Keep last 500
                        self.results[r['hypothesis_id']] = ExperimentResult(
                            hypothesis_id=r['hypothesis_id'],
                            status=ExperimentStatus(r['status']),
                            metrics=r['metrics'],
                            baseline_metrics=r['baseline_metrics'],
                            improvement=r['improvement'],
                            position_metrics=r.get('position_metrics', {}),
                            duration_seconds=r['duration_seconds'],
                            artifacts=r.get('artifacts', {}),
                            error_message=r.get('error_message'),
                            model_path=r.get('model_path'),
                        )
            except Exception as e:
                logger.warning(f"Failed to load experiment results: {e}")

        # Load model versions
        versions_file = self.registry_path / "model_versions.json"
        if versions_file.exists():
            try:
                with open(versions_file) as f:
                    self.model_versions = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load model versions: {e}")

    def _save_state(self):
        """Persist all state to disk."""
        with self._lock:
            # Save hypothesis queue
            queue_file = self.registry_path / "hypothesis_queue_v2.json"
            with open(queue_file, 'w') as f:
                json.dump([h.to_dict() for h in self.hypothesis_queue], f, indent=2)

            # Save experiment results
            results_file = self.registry_path / "experiment_results_v2.json"
            existing = []
            if results_file.exists():
                try:
                    with open(results_file) as f:
                        existing = json.load(f)
                except:
                    pass

            # Add new results
            existing_ids = {e['hypothesis_id'] for e in existing}
            for r in self.results.values():
                if r.hypothesis_id not in existing_ids:
                    existing.append(r.to_dict())

            with open(results_file, 'w') as f:
                json.dump(existing[-500:], f, indent=2)

            # Save model versions
            versions_file = self.registry_path / "model_versions.json"
            with open(versions_file, 'w') as f:
                json.dump(self.model_versions, f, indent=2)

    def queue_hypothesis(self, hypothesis: Hypothesis) -> bool:
        """Add hypothesis to priority queue. Returns True if added."""
        with self._lock:
            # Check for duplicates
            existing_ids = {h.id for h in self.hypothesis_queue}
            if hypothesis.id in existing_ids:
                return False

            # Check if already tested
            if hypothesis.id in self.results:
                return False

            self.hypothesis_queue.append(hypothesis)
            # Sort by priority (higher first)
            self.hypothesis_queue.sort(key=lambda h: -h.priority)
            self._save_state()

            logger.info(f"Queued: {hypothesis.id} (priority={hypothesis.priority:.2f})")
            return True

    def next_hypothesis(self, max_resource_cost: float = 10.0) -> Optional[Hypothesis]:
        """Get next hypothesis that fits resource budget."""
        with self._lock:
            for i, h in enumerate(self.hypothesis_queue):
                if h.resource_cost <= max_resource_cost:
                    self.hypothesis_queue.pop(i)
                    self._save_state()
                    return h
            return None

    def record_result(self, result: ExperimentResult):
        """Record experiment result."""
        with self._lock:
            self.results[result.hypothesis_id] = result
            self._save_state()

            status_emoji = "✓" if result.status == ExperimentStatus.COMPLETED else "✗"
            logger.info(f"{status_emoji} {result.hypothesis_id}: R²={result.r2_improvement:+.4f}")

    def register_model_version(self, version_id: str, metadata: Dict):
        """Register a new model version."""
        with self._lock:
            self.model_versions[version_id] = {
                **metadata,
                'registered_at': datetime.now().isoformat(),
            }
            self._save_state()

    def get_best_experiments(self, n: int = 10, min_r2: float = 0.0) -> List[ExperimentResult]:
        """Get top experiments by improvement."""
        completed = [
            r for r in self.results.values()
            if r.status in [ExperimentStatus.COMPLETED, ExperimentStatus.PROMOTED]
            and r.r2_improvement >= min_r2
        ]
        return sorted(completed, key=lambda r: -r.r2_improvement)[:n]

    def get_failed_experiments(self, n: int = 10) -> List[ExperimentResult]:
        """Get recent failed experiments for error analysis."""
        failed = [
            r for r in self.results.values()
            if r.status == ExperimentStatus.FAILED
        ]
        return sorted(failed, key=lambda r: -r.timestamp.timestamp())[:n]

    def get_experiment_history(self, hypothesis_type: HypothesisType = None) -> List[ExperimentResult]:
        """Get experiment history, optionally filtered by type."""
        results = list(self.results.values())
        # Type filtering would require storing hypothesis type with result
        return sorted(results, key=lambda r: -r.timestamp.timestamp())

    def has_pending(self) -> bool:
        return len(self.hypothesis_queue) > 0

    def queue_size(self) -> int:
        return len(self.hypothesis_queue)

    def get_statistics(self) -> Dict:
        """Get comprehensive statistics."""
        completed = [r for r in self.results.values() if r.status == ExperimentStatus.COMPLETED]
        improvements = [r.r2_improvement for r in completed]

        return {
            'queue_size': len(self.hypothesis_queue),
            'total_experiments': len(self.results),
            'completed': len(completed),
            'promoted': sum(1 for r in self.results.values() if r.status == ExperimentStatus.PROMOTED),
            'failed': sum(1 for r in self.results.values() if r.status == ExperimentStatus.FAILED),
            'rejected': sum(1 for r in self.results.values() if r.status == ExperimentStatus.REJECTED),
            'avg_improvement': np.mean(improvements) if improvements else 0,
            'max_improvement': max(improvements) if improvements else 0,
            'model_versions': len(self.model_versions),
        }


# =============================================================================
# Base Agent Class
# =============================================================================

class BaseAgent(ABC):
    """Abstract base class for all agents."""

    def __init__(self, name: str, registry: ExperimentRegistry):
        self.name = name
        self.registry = registry
        self.status = AgentStatus.IDLE
        self.last_run: Optional[datetime] = None
        self.run_count = 0
        self.error_count = 0
        self.logger = logging.getLogger(f'agent.{name}')

    @abstractmethod
    def run_cycle(self) -> List[Hypothesis]:
        """Execute one cycle of the agent. Returns generated hypotheses."""
        pass

    def safe_run_cycle(self) -> List[Hypothesis]:
        """Run cycle with error handling."""
        self.status = AgentStatus.RUNNING
        self.last_run = datetime.now()
        self.run_count += 1

        try:
            hypotheses = self.run_cycle()
            self.status = AgentStatus.IDLE
            return hypotheses
        except Exception as e:
            self.status = AgentStatus.ERROR
            self.error_count += 1
            self.logger.error(f"Cycle failed: {e}\n{traceback.format_exc()}")
            return []

    def get_status(self) -> Dict:
        return {
            'name': self.name,
            'status': self.status.value,
            'last_run': self.last_run.isoformat() if self.last_run else None,
            'run_count': self.run_count,
            'error_count': self.error_count,
        }


# =============================================================================
# Data Scout Agent
# =============================================================================

class DataScoutAgent(BaseAgent):
    """
    Discovers and evaluates new data sources for ML training.

    Capabilities:
    - Check nflverse for new datasets
    - Monitor data freshness
    - Evaluate data quality
    - Propose data-related hypotheses
    """

    KNOWN_SOURCES = [
        DataSource(
            name="nflverse_player_stats",
            url="https://github.com/nflverse/nflverse-data/releases/tag/player_stats",
            freshness_hours=168,  # Weekly
        ),
        DataSource(
            name="nflverse_pbp",
            url="https://github.com/nflverse/nflverse-data/releases/tag/pbp",
            freshness_hours=24,  # Daily during season
        ),
        DataSource(
            name="nflverse_rosters",
            url="https://github.com/nflverse/nflverse-data/releases/tag/rosters",
            freshness_hours=168,
        ),
        DataSource(
            name="nflverse_injuries",
            url="https://github.com/nflverse/nflverse-data/releases/tag/injuries",
            freshness_hours=24,
        ),
    ]

    def __init__(self, registry: ExperimentRegistry, data_path: Path = None):
        super().__init__("data_scout", registry)
        self.data_path = data_path or PROJECT_ROOT / "data"
        self.sources_status: Dict[str, Dict] = {}

    def check_data_freshness(self) -> Dict[str, bool]:
        """Check which data sources need updates."""
        needs_update = {}

        for source in self.KNOWN_SOURCES:
            # Check if local file exists and its age
            local_path = self.data_path / "nflverse" / f"{source.name}.parquet"

            if local_path.exists():
                mtime = datetime.fromtimestamp(local_path.stat().st_mtime)
                age_hours = (datetime.now() - mtime).total_seconds() / 3600
                needs_update[source.name] = age_hours > source.freshness_hours
            else:
                needs_update[source.name] = True

        return needs_update

    def evaluate_data_quality(self, df: pd.DataFrame, name: str) -> Dict:
        """Evaluate quality of a dataset."""
        quality = {
            'name': name,
            'rows': len(df),
            'columns': len(df.columns),
            'missing_pct': df.isna().mean().mean() * 100,
            'duplicate_pct': df.duplicated().mean() * 100,
            'numeric_cols': len(df.select_dtypes(include=[np.number]).columns),
        }

        # Calculate overall quality score
        quality['score'] = max(0, 100 - quality['missing_pct'] - quality['duplicate_pct'])

        return quality

    def discover_new_features_in_data(self, df: pd.DataFrame) -> List[str]:
        """Find columns that aren't in our training data."""
        training_path = self.data_path / "ml_training" / "expanded_season_projection.parquet"
        if not training_path.exists():
            return []

        training_df = pd.read_parquet(training_path)
        new_cols = set(df.columns) - set(training_df.columns)

        # Filter to numeric columns that might be useful features
        useful_new = [
            c for c in new_cols
            if df[c].dtype in ['int64', 'float64']
            and df[c].notna().mean() > 0.5
        ]

        return useful_new

    def run_cycle(self) -> List[Hypothesis]:
        """Run data scouting cycle."""
        self.logger.info("=== Data Scout: Starting cycle ===")
        hypotheses = []

        # 1. Check data freshness
        freshness = self.check_data_freshness()
        stale_sources = [name for name, needs in freshness.items() if needs]

        if stale_sources:
            self.logger.info(f"Stale data sources: {stale_sources}")
            # Create hypothesis to refresh data
            hypotheses.append(Hypothesis(
                id=f"data_refresh_{hashlib.md5('_'.join(stale_sources).encode()).hexdigest()[:8]}",
                type=HypothesisType.DATA_AUGMENTATION,
                description=f"Refresh stale data: {', '.join(stale_sources)}",
                config={
                    'sources': stale_sources,
                    'action': 'refresh',
                },
                priority=8.0,
                resource_cost=2.0,
                source='data_scout',
                tags=['data', 'freshness'],
            ))

        # 2. Check for new seasons/weeks
        current_year = datetime.now().year
        for year in [current_year - 1, current_year]:
            stats_path = self.data_path / "nflverse" / f"player_stats_{year}.parquet"
            if not stats_path.exists():
                hypotheses.append(Hypothesis(
                    id=f"data_new_season_{year}",
                    type=HypothesisType.DATA_AUGMENTATION,
                    description=f"Ingest {year} season data",
                    config={
                        'year': year,
                        'action': 'ingest_season',
                    },
                    priority=9.0,
                    resource_cost=3.0,
                    source='data_scout',
                    tags=['data', 'new_season'],
                ))

        # 3. Evaluate existing data quality
        training_path = self.data_path / "ml_training" / "expanded_season_projection.parquet"
        if training_path.exists():
            df = pd.read_parquet(training_path)
            quality = self.evaluate_data_quality(df, "training_data")

            if quality['missing_pct'] > 10:
                hypotheses.append(Hypothesis(
                    id=f"data_impute_{hashlib.md5(str(quality).encode()).hexdigest()[:8]}",
                    type=HypothesisType.DATA_AUGMENTATION,
                    description=f"Improve data quality: {quality['missing_pct']:.1f}% missing",
                    config={
                        'action': 'improve_imputation',
                        'current_missing_pct': quality['missing_pct'],
                    },
                    priority=6.0,
                    resource_cost=2.0,
                    source='data_scout',
                    tags=['data', 'quality'],
                ))

        self.logger.info(f"=== Data Scout: Generated {len(hypotheses)} hypotheses ===")
        return hypotheses


# =============================================================================
# Error Analyst Agent
# =============================================================================

class ErrorAnalystAgent(BaseAgent):
    """
    Analyzes prediction errors to find systematic improvements.

    Capabilities:
    - Cluster high-error predictions
    - Identify bias by position, age, team
    - Propose targeted fixes
    - Generate adversarial test cases
    """

    def __init__(self, registry: ExperimentRegistry, data_path: Path = None):
        super().__init__("error_analyst", registry)
        self.data_path = data_path or PROJECT_ROOT / "data"
        self.error_history: List[Dict] = []

    def load_predictions(self) -> Optional[pd.DataFrame]:
        """Load recent predictions and actuals for error analysis."""
        pred_path = self.data_path / "ml_predictions" / "recent_predictions.parquet"
        if pred_path.exists():
            return pd.read_parquet(pred_path)
        return None

    def analyze_errors_by_segment(self, df: pd.DataFrame) -> Dict[str, Dict]:
        """Analyze errors by different segments."""
        if 'error' not in df.columns:
            if 'predicted' in df.columns and 'actual' in df.columns:
                df['error'] = df['predicted'] - df['actual']
            else:
                return {}

        analysis = {}

        # By position
        if 'position' in df.columns:
            pos_errors = df.groupby('position')['error'].agg(['mean', 'std', 'count'])
            analysis['by_position'] = pos_errors.to_dict('index')

        # By age bracket
        if 'age' in df.columns:
            df['age_bracket'] = pd.cut(df['age'], bins=[0, 23, 26, 29, 35, 50])
            age_errors = df.groupby('age_bracket', observed=True)['error'].agg(['mean', 'std'])
            analysis['by_age'] = {str(k): v for k, v in age_errors.to_dict('index').items()}

        # By experience
        if 'years_exp' in df.columns:
            df['exp_bracket'] = pd.cut(df['years_exp'], bins=[-1, 1, 3, 6, 20])
            exp_errors = df.groupby('exp_bracket', observed=True)['error'].agg(['mean', 'std'])
            analysis['by_experience'] = {str(k): v for k, v in exp_errors.to_dict('index').items()}

        # By performance tier
        if 'actual' in df.columns:
            df['perf_tier'] = pd.qcut(df['actual'], q=5, labels=['bottom', 'low', 'mid', 'high', 'elite'])
            tier_errors = df.groupby('perf_tier', observed=True)['error'].agg(['mean', 'std'])
            analysis['by_tier'] = tier_errors.to_dict('index')

        return analysis

    def identify_systematic_biases(self, analysis: Dict) -> List[Dict]:
        """Identify systematic biases that could be fixed."""
        biases = []

        # Check position biases
        if 'by_position' in analysis:
            for pos, stats in analysis['by_position'].items():
                if abs(stats.get('mean', 0)) > 1.0:  # More than 1 PPG bias
                    biases.append({
                        'type': 'position_bias',
                        'segment': pos,
                        'mean_error': stats['mean'],
                        'severity': 'high' if abs(stats['mean']) > 2.0 else 'medium',
                    })

        # Check age biases
        if 'by_age' in analysis:
            for age, stats in analysis['by_age'].items():
                if abs(stats.get('mean', 0)) > 1.5:
                    biases.append({
                        'type': 'age_bias',
                        'segment': age,
                        'mean_error': stats['mean'],
                        'severity': 'high' if abs(stats['mean']) > 3.0 else 'medium',
                    })

        return biases

    def propose_targeted_fixes(self, biases: List[Dict]) -> List[Hypothesis]:
        """Generate hypotheses to fix identified biases."""
        hypotheses = []

        for bias in biases:
            if bias['type'] == 'position_bias':
                pos = bias['segment']
                hypotheses.append(Hypothesis(
                    id=f"fix_pos_bias_{pos.lower()}_{hashlib.md5(str(bias).encode()).hexdigest()[:6]}",
                    type=HypothesisType.POSITION_SPECIALIST,
                    description=f"Add {pos}-specific model to reduce {bias['mean_error']:.2f} PPG bias",
                    config={
                        'position': pos,
                        'current_bias': bias['mean_error'],
                        'action': 'add_position_specialist',
                    },
                    priority=8.0 if bias['severity'] == 'high' else 6.0,
                    resource_cost=4.0,
                    source='error_analyst',
                    tags=['error_fix', 'position'],
                ))

            elif bias['type'] == 'age_bias':
                hypotheses.append(Hypothesis(
                    id=f"fix_age_bias_{hashlib.md5(str(bias).encode()).hexdigest()[:8]}",
                    type=HypothesisType.FEATURE_ADDITION,
                    description=f"Add age-specific features for {bias['segment']}",
                    config={
                        'age_bracket': bias['segment'],
                        'current_bias': bias['mean_error'],
                        'features': ['age_position_interaction', 'aging_curve_residual'],
                    },
                    priority=7.0 if bias['severity'] == 'high' else 5.0,
                    resource_cost=2.0,
                    source='error_analyst',
                    tags=['error_fix', 'age'],
                ))

        return hypotheses

    def run_cycle(self) -> List[Hypothesis]:
        """Run error analysis cycle."""
        self.logger.info("=== Error Analyst: Starting cycle ===")
        hypotheses = []

        # Load predictions
        df = self.load_predictions()
        if df is None:
            self.logger.warning("No predictions available for error analysis")

            # Generate synthetic analysis based on historical experiment results
            failed = self.registry.get_failed_experiments(10)
            if failed:
                # Analyze patterns in failures
                error_patterns = defaultdict(int)
                for exp in failed:
                    if exp.error_message:
                        # Extract error type
                        if 'memory' in exp.error_message.lower():
                            error_patterns['memory'] += 1
                        elif 'nan' in exp.error_message.lower():
                            error_patterns['nan_values'] += 1
                        elif 'shape' in exp.error_message.lower():
                            error_patterns['shape_mismatch'] += 1

                for pattern, count in error_patterns.items():
                    if count >= 2:
                        hypotheses.append(Hypothesis(
                            id=f"fix_exp_error_{pattern}_{int(time.time())}",
                            type=HypothesisType.ERROR_TARGETED_FIX,
                            description=f"Fix recurring {pattern} errors ({count} occurrences)",
                            config={'error_type': pattern, 'count': count},
                            priority=7.0,
                            resource_cost=1.0,
                            source='error_analyst',
                            tags=['error_fix', 'experiment'],
                        ))

            return hypotheses

        # Analyze errors
        analysis = self.analyze_errors_by_segment(df)
        biases = self.identify_systematic_biases(analysis)

        if biases:
            self.logger.info(f"Found {len(biases)} systematic biases")
            hypotheses = self.propose_targeted_fixes(biases)

        # Analyze high-error outliers
        if 'error' in df.columns:
            high_error = df[abs(df['error']) > df['error'].std() * 2]
            if len(high_error) > 10:
                hypotheses.append(Hypothesis(
                    id=f"fix_outliers_{hashlib.md5(str(len(high_error)).encode()).hexdigest()[:8]}",
                    type=HypothesisType.ERROR_TARGETED_FIX,
                    description=f"Improve predictions for {len(high_error)} high-error cases",
                    config={
                        'outlier_count': len(high_error),
                        'mean_outlier_error': float(high_error['error'].abs().mean()),
                    },
                    priority=6.0,
                    resource_cost=3.0,
                    source='error_analyst',
                    tags=['error_fix', 'outliers'],
                ))

        self.logger.info(f"=== Error Analyst: Generated {len(hypotheses)} hypotheses ===")
        return hypotheses


# =============================================================================
# Architecture Search Agent
# =============================================================================

class ArchitectureSearchAgent(BaseAgent):
    """
    Explores neural network architectures for improvement.

    Capabilities:
    - Test different layer configurations
    - Experiment with attention mechanisms
    - Optimize embedding dimensions
    - Search ensemble compositions
    """

    LAYER_CONFIGS = [
        [256, 128, 64],
        [512, 256, 128],
        [128, 128, 64, 32],
        [256, 256, 128, 64],
        [512, 256, 128, 64],
    ]

    ATTENTION_CONFIGS = [
        {'heads': 4, 'dropout': 0.1},
        {'heads': 8, 'dropout': 0.1},
        {'heads': 4, 'dropout': 0.2},
    ]

    ENSEMBLE_CONFIGS = [
        {'models': ['gbm', 'rf', 'nn'], 'meta': 'ridge'},
        {'models': ['gbm', 'nn', 'xgb'], 'meta': 'ridge'},
        {'models': ['gbm', 'rf', 'nn', 'xgb'], 'meta': 'nn'},
    ]

    def __init__(self, registry: ExperimentRegistry):
        super().__init__("architecture_search", registry)
        self.tested_configs: Set[str] = set()
        self._load_tested()

    def _load_tested(self):
        """Load previously tested configurations."""
        for result in self.registry.results.values():
            if result.status in [ExperimentStatus.COMPLETED, ExperimentStatus.REJECTED]:
                config_hash = hashlib.md5(str(result.hypothesis_id).encode()).hexdigest()
                self.tested_configs.add(config_hash)

    def _config_hash(self, config: Dict) -> str:
        return hashlib.md5(json.dumps(config, sort_keys=True).encode()).hexdigest()

    def generate_layer_hypotheses(self) -> List[Hypothesis]:
        """Generate hypotheses for layer configurations."""
        hypotheses = []

        for i, layers in enumerate(self.LAYER_CONFIGS):
            config = {'layers': layers, 'activation': 'relu'}
            config_hash = self._config_hash(config)

            if config_hash not in self.tested_configs:
                hypotheses.append(Hypothesis(
                    id=f"arch_layers_{config_hash[:8]}",
                    type=HypothesisType.ARCHITECTURE,
                    description=f"Test NN architecture: {layers}",
                    config=config,
                    priority=5.0 + (0.5 * i),  # Slightly vary priority
                    resource_cost=3.0,
                    source='architecture_search',
                    tags=['architecture', 'layers'],
                ))

        return hypotheses

    def generate_attention_hypotheses(self) -> List[Hypothesis]:
        """Generate hypotheses for attention mechanisms."""
        hypotheses = []

        for config in self.ATTENTION_CONFIGS:
            config_hash = self._config_hash(config)

            if config_hash not in self.tested_configs:
                hypotheses.append(Hypothesis(
                    id=f"arch_attention_{config_hash[:8]}",
                    type=HypothesisType.ATTENTION_MECHANISM,
                    description=f"Test attention: {config['heads']} heads, {config['dropout']} dropout",
                    config=config,
                    priority=6.0,
                    resource_cost=4.0,
                    source='architecture_search',
                    tags=['architecture', 'attention'],
                ))

        return hypotheses

    def generate_ensemble_hypotheses(self) -> List[Hypothesis]:
        """Generate hypotheses for ensemble compositions."""
        hypotheses = []

        for config in self.ENSEMBLE_CONFIGS:
            config_hash = self._config_hash(config)

            if config_hash not in self.tested_configs:
                models_str = '+'.join(config['models'])
                hypotheses.append(Hypothesis(
                    id=f"arch_ensemble_{config_hash[:8]}",
                    type=HypothesisType.ENSEMBLE_CONFIG,
                    description=f"Test ensemble: {models_str} with {config['meta']} meta",
                    config=config,
                    priority=7.0,
                    resource_cost=5.0,
                    source='architecture_search',
                    tags=['architecture', 'ensemble'],
                ))

        return hypotheses

    def run_cycle(self) -> List[Hypothesis]:
        """Run architecture search cycle."""
        self.logger.info("=== Architecture Search: Starting cycle ===")

        hypotheses = []
        hypotheses.extend(self.generate_layer_hypotheses())
        hypotheses.extend(self.generate_attention_hypotheses())
        hypotheses.extend(self.generate_ensemble_hypotheses())

        # Limit to avoid queue explosion
        hypotheses = hypotheses[:10]

        self.logger.info(f"=== Architecture Search: Generated {len(hypotheses)} hypotheses ===")
        return hypotheses


# =============================================================================
# Drift Monitor Agent
# =============================================================================

class DriftMonitorAgent(BaseAgent):
    """
    Monitors production model for drift and degradation.

    Capabilities:
    - Track prediction distribution changes
    - Detect feature importance shifts
    - Alert on performance degradation
    - Trigger retraining when needed
    """

    DRIFT_THRESHOLDS = {
        'r2_degradation': 0.05,         # 5% R² drop triggers alert
        'rmse_increase': 0.3,            # 0.3 PPG RMSE increase
        'distribution_shift': 0.1,       # KL divergence threshold
        'feature_importance_shift': 0.2, # Feature importance change
    }

    def __init__(self, registry: ExperimentRegistry, models_path: Path = None):
        super().__init__("drift_monitor", registry)
        self.models_path = models_path or PROJECT_ROOT / "data" / "models"
        self.baseline_metrics: Optional[Dict] = None
        self.metrics_history: List[Dict] = []

    def load_baseline(self) -> Dict:
        """Load baseline production metrics."""
        metrics_file = self.models_path / "model_metrics.json"
        if metrics_file.exists():
            with open(metrics_file) as f:
                return json.load(f)
        return {'ensemble_r2': 0.80, 'ensemble_rmse': 2.5}

    def load_current_metrics(self) -> Optional[Dict]:
        """Load most recent production metrics."""
        # This would connect to production monitoring
        # For now, check experiment results
        best = self.registry.get_best_experiments(1)
        if best:
            return best[0].metrics
        return None

    def calculate_drift(self, baseline: Dict, current: Dict) -> Dict:
        """Calculate drift between baseline and current metrics."""
        drift = {}

        if 'r2' in baseline and 'r2' in current:
            drift['r2_change'] = current['r2'] - baseline.get('ensemble_r2', baseline.get('r2', 0))
            drift['r2_degradation'] = drift['r2_change'] < -self.DRIFT_THRESHOLDS['r2_degradation']

        if 'rmse' in baseline and 'rmse' in current:
            drift['rmse_change'] = current['rmse'] - baseline.get('ensemble_rmse', baseline.get('rmse', 0))
            drift['rmse_increase'] = drift['rmse_change'] > self.DRIFT_THRESHOLDS['rmse_increase']

        drift['needs_action'] = drift.get('r2_degradation', False) or drift.get('rmse_increase', False)

        return drift

    def run_cycle(self) -> List[Hypothesis]:
        """Run drift monitoring cycle."""
        self.logger.info("=== Drift Monitor: Starting cycle ===")
        hypotheses = []

        baseline = self.load_baseline()
        current = self.load_current_metrics()

        if current:
            drift = self.calculate_drift(baseline, current)

            if drift.get('needs_action'):
                self.logger.warning(f"Drift detected: {drift}")

                if drift.get('r2_degradation'):
                    hypotheses.append(Hypothesis(
                        id=f"drift_retrain_{int(time.time())}",
                        type=HypothesisType.DATA_AUGMENTATION,
                        description=f"Retrain model: R² dropped by {abs(drift['r2_change']):.3f}",
                        config={
                            'action': 'full_retrain',
                            'reason': 'r2_degradation',
                            'drift_amount': drift['r2_change'],
                        },
                        priority=9.0,
                        resource_cost=5.0,
                        source='drift_monitor',
                        tags=['drift', 'retrain'],
                    ))

                if drift.get('rmse_increase'):
                    hypotheses.append(Hypothesis(
                        id=f"drift_rmse_{int(time.time())}",
                        type=HypothesisType.ERROR_TARGETED_FIX,
                        description=f"Fix RMSE increase: +{drift['rmse_change']:.2f} PPG",
                        config={
                            'action': 'investigate_rmse',
                            'reason': 'rmse_increase',
                            'drift_amount': drift['rmse_change'],
                        },
                        priority=8.0,
                        resource_cost=3.0,
                        source='drift_monitor',
                        tags=['drift', 'rmse'],
                    ))
            else:
                self.logger.info("No significant drift detected")
        else:
            self.logger.info("No current metrics available for drift analysis")

        self.logger.info(f"=== Drift Monitor: Generated {len(hypotheses)} hypotheses ===")
        return hypotheses


# =============================================================================
# Meta Learner Agent
# =============================================================================

class MetaLearnerAgent(BaseAgent):
    """
    Learns from experiment history to improve hypothesis generation.

    Capabilities:
    - Predict experiment success probability
    - Optimize hypothesis prioritization
    - Identify promising research directions
    - Avoid repeating failures
    """

    def __init__(self, registry: ExperimentRegistry):
        super().__init__("meta_learner", registry)
        self.success_patterns: Dict[str, float] = {}
        self.failure_patterns: Dict[str, int] = {}

    def analyze_experiment_history(self) -> Dict:
        """Analyze patterns in experiment history."""
        history = self.registry.get_experiment_history()

        analysis = {
            'total_experiments': len(history),
            'success_rate': 0,
            'avg_improvement': 0,
            'best_hypothesis_types': {},
            'worst_hypothesis_types': {},
        }

        if not history:
            return analysis

        # Success rate
        completed = [r for r in history if r.status == ExperimentStatus.COMPLETED]
        promoted = [r for r in history if r.status == ExperimentStatus.PROMOTED]

        if completed:
            analysis['success_rate'] = len(promoted) / len(completed)
            analysis['avg_improvement'] = np.mean([r.r2_improvement for r in completed])

        # Best/worst by improvement (using hypothesis ID patterns)
        improvements_by_type = defaultdict(list)
        for r in completed:
            # Extract type from hypothesis ID prefix
            parts = r.hypothesis_id.split('_')
            if parts:
                h_type = parts[0]
                improvements_by_type[h_type].append(r.r2_improvement)

        for h_type, improvements in improvements_by_type.items():
            avg = np.mean(improvements)
            if avg > 0:
                analysis['best_hypothesis_types'][h_type] = avg
            else:
                analysis['worst_hypothesis_types'][h_type] = avg

        return analysis

    def predict_success_probability(self, hypothesis: Hypothesis) -> float:
        """Predict probability of hypothesis succeeding."""
        # Simple heuristic-based prediction
        base_prob = 0.3

        # Type-based adjustment
        h_type = hypothesis.id.split('_')[0]
        if h_type in self.success_patterns:
            type_success_rate = self.success_patterns[h_type]
            base_prob = 0.5 * base_prob + 0.5 * type_success_rate

        # Adjust for expected improvement claim
        if hypothesis.expected_improvement > 0.01:
            base_prob *= 1.2  # More optimistic about high-expected

        # Adjust for novelty
        base_prob *= (0.5 + 0.5 * hypothesis.novelty_score)

        return min(0.9, max(0.1, base_prob))

    def reprioritize_queue(self, hypotheses: List[Hypothesis]) -> List[Hypothesis]:
        """Re-prioritize hypotheses based on learned patterns."""
        for h in hypotheses:
            success_prob = self.predict_success_probability(h)
            expected_value = success_prob * h.expected_improvement

            # Adjust priority based on expected value
            h.priority = (
                0.4 * h.priority +
                0.3 * (success_prob * 10) +
                0.2 * (h.novelty_score * 10) +
                0.1 * (1 / max(0.1, h.resource_cost)) * 10
            )

        return sorted(hypotheses, key=lambda h: -h.priority)

    def run_cycle(self) -> List[Hypothesis]:
        """Run meta-learning cycle."""
        self.logger.info("=== Meta Learner: Starting cycle ===")

        # Analyze history
        analysis = self.analyze_experiment_history()
        self.logger.info(f"Experiment history: {analysis['total_experiments']} experiments, "
                        f"{analysis['success_rate']:.1%} success rate")

        # Update success patterns
        for h_type, avg_imp in analysis['best_hypothesis_types'].items():
            self.success_patterns[h_type] = min(1.0, avg_imp * 10)

        hypotheses = []

        # Generate hypotheses for promising directions
        if analysis['best_hypothesis_types']:
            best_type = max(analysis['best_hypothesis_types'].items(), key=lambda x: x[1])
            self.logger.info(f"Best performing type: {best_type[0]} ({best_type[1]:.4f} avg improvement)")

            hypotheses.append(Hypothesis(
                id=f"meta_explore_{best_type[0]}_{int(time.time())}",
                type=HypothesisType.FEATURE_ADDITION,
                description=f"Explore more {best_type[0]} hypotheses (historically successful)",
                config={
                    'focus_area': best_type[0],
                    'historical_improvement': best_type[1],
                },
                priority=7.0,
                expected_improvement=best_type[1] * 0.8,  # Conservative estimate
                source='meta_learner',
                tags=['meta', 'exploration'],
            ))

        # Suggest avoiding worst patterns
        if analysis['worst_hypothesis_types']:
            worst_type = min(analysis['worst_hypothesis_types'].items(), key=lambda x: x[1])
            self.logger.info(f"Worst performing type: {worst_type[0]} ({worst_type[1]:.4f} avg)")

        self.logger.info(f"=== Meta Learner: Generated {len(hypotheses)} hypotheses ===")
        return hypotheses


# =============================================================================
# Model Promoter Agent
# =============================================================================

class ModelPromoterAgent(BaseAgent):
    """
    Handles safe promotion of models to production.

    Capabilities:
    - Canary deployments
    - A/B testing
    - Automatic rollback
    - Staged promotion pipeline
    """

    PROMOTION_THRESHOLDS = {
        'min_r2_improvement': 0.003,
        'max_rmse_increase': 0.05,
        'min_sample_size': 100,
        'canary_success_rate': 0.95,
    }

    def __init__(self, registry: ExperimentRegistry, models_path: Path = None):
        super().__init__("model_promoter", registry)
        self.models_path = models_path or PROJECT_ROOT / "data" / "models"
        self.canary_results: Dict[str, Dict] = {}

    def evaluate_for_promotion(self, result: ExperimentResult) -> Dict:
        """Evaluate if an experiment result is ready for promotion."""
        evaluation = {
            'experiment_id': result.hypothesis_id,
            'ready': True,
            'checks': {},
            'recommendation': None,
        }

        # Check R² improvement
        evaluation['checks']['r2_threshold'] = (
            result.r2_improvement >= self.PROMOTION_THRESHOLDS['min_r2_improvement']
        )

        # Check RMSE
        evaluation['checks']['rmse_threshold'] = (
            result.rmse_improvement >= -self.PROMOTION_THRESHOLDS['max_rmse_increase']
        )

        # Check sample size
        n_samples = result.metrics.get('n_samples', 0)
        evaluation['checks']['sample_size'] = (
            n_samples >= self.PROMOTION_THRESHOLDS['min_sample_size']
        )

        # Overall readiness
        evaluation['ready'] = all(evaluation['checks'].values())

        if evaluation['ready']:
            if result.r2_improvement > 0.01:
                evaluation['recommendation'] = 'promote_immediately'
            else:
                evaluation['recommendation'] = 'canary_first'
        else:
            evaluation['recommendation'] = 'reject'

        return evaluation

    def promote_model(self, result: ExperimentResult) -> bool:
        """Promote a model to production."""
        if not result.model_path:
            self.logger.warning(f"No model path for {result.hypothesis_id}")
            return False

        # In a real system, this would:
        # 1. Copy model to production location
        # 2. Update model registry
        # 3. Trigger deployment pipeline

        version_id = f"v_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        self.registry.register_model_version(version_id, {
            'hypothesis_id': result.hypothesis_id,
            'metrics': result.metrics,
            'improvement': result.improvement,
            'model_path': result.model_path,
        })

        result.status = ExperimentStatus.PROMOTED
        self.registry.record_result(result)

        self.logger.info(f"Promoted {result.hypothesis_id} as {version_id}")
        return True

    def run_cycle(self) -> List[Hypothesis]:
        """Run promotion cycle."""
        self.logger.info("=== Model Promoter: Starting cycle ===")

        # Find candidates for promotion
        best = self.registry.get_best_experiments(10, min_r2=0.001)

        promoted_count = 0
        for result in best:
            if result.status == ExperimentStatus.COMPLETED:
                evaluation = self.evaluate_for_promotion(result)

                if evaluation['ready']:
                    if evaluation['recommendation'] == 'promote_immediately':
                        if self.promote_model(result):
                            promoted_count += 1
                    elif evaluation['recommendation'] == 'canary_first':
                        self.logger.info(f"Queuing {result.hypothesis_id} for canary testing")

        self.logger.info(f"=== Model Promoter: Promoted {promoted_count} models ===")
        return []  # This agent doesn't generate hypotheses


# =============================================================================
# Enhanced Feature Engineer (from original, with improvements)
# =============================================================================

class EnhancedFeatureEngineerAgent(BaseAgent):
    """
    Enhanced feature engineering with more strategies.

    New capabilities:
    - Time-series features (lags, rolling)
    - Graph-based features from Neo4j
    - SHAP-based feature selection
    - Feature removal hypotheses
    """

    def __init__(self, registry: ExperimentRegistry, data_path: Path = None):
        super().__init__("feature_engineer", registry)
        self.data_path = data_path or PROJECT_ROOT / "data" / "ml_training"

    def load_data(self) -> Optional[pd.DataFrame]:
        """Load training data."""
        path = self.data_path / "expanded_season_projection.parquet"
        if path.exists():
            return pd.read_parquet(path)
        return None

    def get_feature_columns(self, df: pd.DataFrame) -> List[str]:
        """Get list of feature columns."""
        exclude = ['player_id', 'player_name', 'team', 'position', 'season',
                   'next_ppg_ppr', 'next_ppg_std', 'next_season', 'next_team', 'next_games']
        return [c for c in df.columns
                if c not in exclude
                and df[c].dtype in ['int64', 'float64']
                and df[c].notna().mean() > 0.5]

    def generate_interaction_features(self, df: pd.DataFrame) -> List[Dict]:
        """Generate interaction feature candidates."""
        candidates = []
        target = 'next_ppg_ppr'

        if target not in df.columns:
            return candidates

        features = self.get_feature_columns(df)

        # Get top correlated features
        correlations = df[features].corrwith(df[target]).abs().sort_values(ascending=False)
        top_features = correlations.head(8).index.tolist()

        # Generate interactions
        for i, f1 in enumerate(top_features[:5]):
            for f2 in top_features[i+1:6]:
                candidates.append({
                    'name': f'{f1}_x_{f2}',
                    'type': 'interaction',
                    'formula': f"df['{f1}'] * df['{f2}']",
                    'features': [f1, f2],
                })

        return candidates

    def generate_lag_features(self, df: pd.DataFrame) -> List[Dict]:
        """Generate lag/time-series features."""
        candidates = []

        # These would require multi-season data per player
        lag_cols = ['ppg_ppr', 'games', 'targets', 'receptions']

        for col in lag_cols:
            if col in df.columns:
                candidates.append({
                    'name': f'{col}_lag1_diff',
                    'type': 'lag',
                    'formula': f"df.groupby('player_id')['{col}'].diff()",
                    'features': [col],
                })
                candidates.append({
                    'name': f'{col}_rolling3_mean',
                    'type': 'rolling',
                    'formula': f"df.groupby('player_id')['{col}'].transform(lambda x: x.rolling(3, min_periods=1).mean())",
                    'features': [col],
                })

        return candidates

    def generate_position_relative_features(self, df: pd.DataFrame) -> List[Dict]:
        """Generate position-relative features."""
        candidates = []

        rel_cols = ['ppg_ppr', 'targets', 'snap_pct', 'games']

        for col in rel_cols:
            if col in df.columns:
                candidates.append({
                    'name': f'{col}_vs_pos_mean',
                    'type': 'relative',
                    'formula': f"df.groupby('position')['{col}'].transform(lambda x: x - x.mean())",
                    'features': [col],
                })
                candidates.append({
                    'name': f'{col}_pos_percentile',
                    'type': 'percentile',
                    'formula': f"df.groupby('position')['{col}'].transform(lambda x: x.rank(pct=True))",
                    'features': [col],
                })

        return candidates

    def evaluate_candidate(self, df: pd.DataFrame, candidate: Dict) -> Dict:
        """Evaluate a feature candidate."""
        target = 'next_ppg_ppr'

        if target not in df.columns:
            return {'valid': False, 'reason': 'No target'}

        try:
            # Generate feature
            feature_values = eval(candidate['formula'])

            # Handle invalid values
            valid_mask = ~(feature_values.isna() | np.isinf(feature_values))
            if valid_mask.sum() < 100:
                return {'valid': False, 'reason': 'Too few valid values'}

            # Calculate metrics
            correlation = feature_values[valid_mask].corr(df.loc[valid_mask, target])

            from sklearn.feature_selection import mutual_info_regression
            X = feature_values[valid_mask].values.reshape(-1, 1)
            y = df.loc[valid_mask, target].values
            mi = mutual_info_regression(X, y, random_state=42)[0]

            return {
                'valid': True,
                'name': candidate['name'],
                'correlation': float(correlation),
                'mutual_info': float(mi),
                'coverage': float(valid_mask.mean()),
                'passes_threshold': abs(correlation) > 0.05 or mi > 0.02,
            }

        except Exception as e:
            return {'valid': False, 'reason': str(e)}

    def run_cycle(self) -> List[Hypothesis]:
        """Run feature engineering cycle."""
        self.logger.info("=== Feature Engineer: Starting cycle ===")

        df = self.load_data()
        if df is None:
            self.logger.warning("No training data available")
            return []

        hypotheses = []

        # Generate all candidates
        candidates = []
        candidates.extend(self.generate_interaction_features(df))
        candidates.extend(self.generate_lag_features(df))
        candidates.extend(self.generate_position_relative_features(df))

        # Evaluate and create hypotheses
        for candidate in candidates:
            result = self.evaluate_candidate(df, candidate)

            if result.get('valid') and result.get('passes_threshold'):
                priority = min(10, abs(result['correlation']) * 15 + result['mutual_info'] * 2)

                hypotheses.append(Hypothesis(
                    id=f"feat_{hashlib.md5(candidate['name'].encode()).hexdigest()[:8]}",
                    type=HypothesisType.FEATURE_ADDITION,
                    description=f"Add feature: {candidate['name']}",
                    config={
                        'feature_name': candidate['name'],
                        'feature_type': candidate['type'],
                        'formula': candidate['formula'],
                        'correlation': result['correlation'],
                        'mutual_info': result['mutual_info'],
                    },
                    priority=priority,
                    expected_improvement=abs(result['correlation']) * 0.01,
                    novelty_score=0.7,
                    resource_cost=1.0,
                    source='feature_engineer',
                    tags=['feature', candidate['type']],
                ))

        # Limit hypotheses
        hypotheses = sorted(hypotheses, key=lambda h: -h.priority)[:20]

        self.logger.info(f"=== Feature Engineer: Generated {len(hypotheses)} hypotheses ===")
        return hypotheses


# =============================================================================
# LLM-Powered Creative Agent
# =============================================================================

class LLMCreativeAgent(BaseAgent):
    """
    Uses local LLM (cost: $0) for intelligent hypothesis generation.

    Capabilities:
    - Brainstorm creative feature ideas beyond rule-based generation
    - Generate feature engineering code automatically
    - Analyze errors with natural language reasoning
    - Prioritize experiments using learned patterns
    - Generate insightful reports

    Local LLM: http://172.16.108.209:1234 (openai/gpt-oss-20b)
    """

    def __init__(self, registry: 'ExperimentRegistry', data_path: Path = None):
        super().__init__("llm_creative", registry)
        self.data_path = data_path or PROJECT_ROOT / "data" / "ml_training"
        self.hub: Optional['LLMAgentHub'] = None
        self._init_llm()

    def _init_llm(self):
        """Initialize LLM hub if available."""
        if LLM_AVAILABLE:
            try:
                config = LLMConfig(
                    base_url="http://172.16.108.209:1234",
                    model="openai/gpt-oss-20b",
                    max_tokens=2048,
                    temperature=0.7,
                )
                self.hub = LLMAgentHub(config)
                if self.hub.is_available():
                    self.logger.info("Connected to local LLM")
                else:
                    self.logger.warning("Local LLM not responding")
                    self.hub = None
            except Exception as e:
                self.logger.warning(f"Failed to initialize LLM: {e}")
                self.hub = None

    def _get_context(self) -> Dict:
        """Build context for LLM from current state."""
        context = {}

        # Load training data features
        try:
            df = pd.read_parquet(self.data_path / "expanded_season_projection.parquet")
            exclude = ['player_id', 'player_name', 'team', 'position', 'season',
                      'next_ppg_ppr', 'next_ppg_std']
            features = [c for c in df.columns if c not in exclude
                       and df[c].dtype in ['int64', 'float64']]
            context['current_features'] = features

            # Top correlations with target
            if 'next_ppg_ppr' in df.columns:
                corrs = df[features].corrwith(df['next_ppg_ppr']).abs().sort_values(ascending=False)
                context['top_correlations'] = list(corrs.head(15).items())

        except Exception as e:
            self.logger.warning(f"Could not load training data context: {e}")

        # Recent experiment results
        best = self.registry.get_best_experiments(10)
        context['recent_experiments'] = [
            {
                'name': r.hypothesis_id,
                'improvement': r.r2_improvement,
                'status': r.status.value,
            }
            for r in best
        ]

        return context

    def generate_creative_hypotheses(self) -> List[Hypothesis]:
        """Use LLM to brainstorm creative feature ideas."""
        if not self.hub:
            return []

        context = self._get_context()
        ideas = self.hub.brainstorm.generate_feature_ideas(context)

        hypotheses = []
        for idea in ideas:
            # Generate code for the idea
            code = self.hub.codegen.generate_feature_code(idea)

            hypothesis = Hypothesis(
                id=f"llm_{hashlib.md5(idea.get('name', '').encode()).hexdigest()[:8]}",
                type=HypothesisType.FEATURE_ADDITION,
                description=f"LLM-generated: {idea.get('name', 'unknown')}",
                config={
                    'feature_name': idea.get('name', 'llm_feature'),
                    'description': idea.get('description', ''),
                    'hypothesis': idea.get('hypothesis', ''),
                    'formula': code or idea.get('formula', ''),
                    'generated_code': code,
                    'expected_correlation': idea.get('expected_correlation', 0),
                },
                priority=7.0,  # High priority for LLM ideas
                expected_improvement=abs(idea.get('expected_correlation', 0.1)) * 0.01,
                novelty_score=0.9,  # LLM ideas are novel
                resource_cost=2.0,
                source='llm_creative',
                tags=['llm', 'creative', 'feature'],
            )
            hypotheses.append(hypothesis)

        return hypotheses

    def analyze_errors_with_llm(self, error_data: Dict) -> List[Hypothesis]:
        """Use LLM to analyze prediction errors and suggest fixes."""
        if not self.hub:
            return []

        analysis = self.hub.error_analyzer.analyze_errors(error_data)

        hypotheses = []
        for rec in analysis.get('recommendations', []):
            hypothesis = Hypothesis(
                id=f"llm_fix_{hashlib.md5(str(rec).encode()).hexdigest()[:8]}",
                type=HypothesisType.ERROR_TARGETED_FIX,
                description=f"LLM fix: {rec.get('issue', 'unknown issue')}",
                config={
                    'issue': rec.get('issue', ''),
                    'fix': rec.get('fix', ''),
                    'feature_suggestion': rec.get('feature_suggestion', ''),
                },
                priority=rec.get('priority', 5.0),
                source='llm_creative',
                tags=['llm', 'error_fix'],
            )
            hypotheses.append(hypothesis)

        return hypotheses

    def prioritize_queue(self) -> None:
        """Use LLM to re-prioritize the hypothesis queue."""
        if not self.hub:
            return

        # Get current queue as dicts
        queue_dicts = [h.to_dict() for h in self.registry.hypothesis_queue[:20]]

        # Get experiment history
        history = [
            {
                'name': r.hypothesis_id,
                'improvement': r.r2_improvement,
            }
            for r in self.registry.get_experiment_history()[:20]
        ]

        # Reprioritize
        prioritized = self.hub.prioritizer.prioritize_hypotheses(queue_dicts, history)

        # Update queue priorities
        priority_map = {h['id']: h.get('priority', 5.0) for h in prioritized}
        for h in self.registry.hypothesis_queue:
            if h.id in priority_map:
                h.priority = priority_map[h.id]

        # Re-sort queue
        self.registry.hypothesis_queue.sort(key=lambda x: -x.priority)
        self.logger.info("LLM re-prioritized hypothesis queue")

    def generate_report(self, cycle_stats: Dict) -> str:
        """Generate an insightful cycle report using LLM."""
        if not self.hub:
            return self._fallback_report(cycle_stats)

        return self.hub.reporter.generate_cycle_report(cycle_stats)

    def _fallback_report(self, stats: Dict) -> str:
        """Basic report when LLM unavailable."""
        return f"""Cycle Report:
- Hypotheses generated: {stats.get('hypotheses_generated', 0)}
- Experiments run: {stats.get('experiments_run', 0)}
- Models promoted: {stats.get('models_promoted', 0)}"""

    def run_cycle(self) -> List[Hypothesis]:
        """Run LLM creative cycle."""
        self.logger.info("=== LLM Creative Agent: Starting cycle ===")

        if not self.hub or not self.hub.is_available():
            self.logger.warning("Local LLM not available, skipping LLM cycle")
            return []

        hypotheses = []

        # 1. Brainstorm creative features
        self.logger.info("Brainstorming creative feature ideas...")
        creative = self.generate_creative_hypotheses()
        hypotheses.extend(creative)
        self.logger.info(f"Generated {len(creative)} creative hypotheses")

        # 2. Suggest data sources
        self.logger.info("Looking for new data sources...")
        sources = self.hub.brainstorm.suggest_data_sources()
        for source in sources[:3]:
            hypotheses.append(Hypothesis(
                id=f"llm_data_{hashlib.md5(source.get('name', '').encode()).hexdigest()[:8]}",
                type=HypothesisType.DATA_AUGMENTATION,
                description=f"LLM data source: {source.get('name', 'unknown')}",
                config={
                    'source_name': source.get('name', ''),
                    'description': source.get('description', ''),
                    'access_method': source.get('access_method', ''),
                },
                priority=5.0,
                source='llm_creative',
                tags=['llm', 'data_source'],
            ))

        # 3. Re-prioritize queue with LLM reasoning
        if self.registry.queue_size() > 5:
            self.prioritize_queue()

        self.logger.info(f"=== LLM Creative: Generated {len(hypotheses)} hypotheses ===")
        return hypotheses


# =============================================================================
# Experiment Lab (Enhanced Model Lab)
# =============================================================================

class ExperimentLab(BaseAgent):
    """
    Runs experiments with full model training.

    Capabilities:
    - Train with actual stacked ensemble
    - Position-specific evaluation
    - Model checkpointing
    - Resource-aware execution
    """

    def __init__(self, registry: ExperimentRegistry,
                 data_path: Path = None, models_path: Path = None):
        super().__init__("experiment_lab", registry)
        self.data_path = data_path or PROJECT_ROOT / "data" / "ml_training"
        self.models_path = models_path or PROJECT_ROOT / "data" / "models"
        self.models_path.mkdir(parents=True, exist_ok=True)

    def load_baseline_metrics(self) -> Dict[str, float]:
        """Load production model baseline metrics."""
        metrics_file = self.models_path / "model_metrics.json"
        if metrics_file.exists():
            with open(metrics_file) as f:
                return json.load(f)
        return {'ensemble_r2': 0.80, 'ensemble_rmse': 2.47}

    def prepare_data(self, hypothesis: Hypothesis) -> Tuple[pd.DataFrame, List[str]]:
        """Prepare data based on hypothesis."""
        df = pd.read_parquet(self.data_path / "expanded_season_projection.parquet")

        target = 'next_ppg_ppr'
        exclude = ['player_id', 'player_name', 'team', 'position', 'season',
                   'next_ppg_ppr', 'next_ppg_std', 'next_season', 'next_team', 'next_games']

        # Apply hypothesis modifications
        if hypothesis.type == HypothesisType.FEATURE_ADDITION:
            formula = hypothesis.config.get('formula')
            feature_name = hypothesis.config.get('feature_name')
            if formula and feature_name:
                try:
                    df[feature_name] = eval(formula)
                except Exception as e:
                    self.logger.warning(f"Failed to create feature: {e}")

        features = [c for c in df.columns
                   if c not in exclude
                   and df[c].dtype in ['int64', 'float64']
                   and df[c].notna().mean() > 0.5]

        return df, features

    def train_and_evaluate(self, df: pd.DataFrame, features: List[str],
                          hypothesis: Hypothesis) -> Dict[str, float]:
        """Train model and evaluate."""
        from sklearn.ensemble import GradientBoostingRegressor
        from sklearn.model_selection import train_test_split
        from sklearn.preprocessing import StandardScaler
        from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error

        target = 'next_ppg_ppr'

        X = df[features].fillna(0)
        y = df[target]

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)

        # Get hyperparameters from hypothesis if applicable
        n_estimators = hypothesis.config.get('n_estimators', 150)
        max_depth = hypothesis.config.get('max_depth', 4)
        learning_rate = hypothesis.config.get('learning_rate', 0.1)

        model = GradientBoostingRegressor(
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=learning_rate,
            random_state=42
        )
        model.fit(X_train_scaled, y_train)

        y_pred = model.predict(X_test_scaled)

        metrics = {
            'r2': float(r2_score(y_test, y_pred)),
            'rmse': float(np.sqrt(mean_squared_error(y_test, y_pred))),
            'mae': float(mean_absolute_error(y_test, y_pred)),
            'n_features': len(features),
            'n_samples': len(X_train),
        }

        # Position-specific metrics
        if 'position' in df.columns:
            test_df = df.iloc[X_test.index]
            for pos in ['QB', 'RB', 'WR', 'TE']:
                pos_mask = test_df['position'] == pos
                if pos_mask.sum() > 10:
                    metrics[f'{pos.lower()}_r2'] = float(r2_score(
                        y_test[pos_mask], y_pred[pos_mask]
                    ))

        return metrics

    def run_experiment(self, hypothesis: Hypothesis) -> ExperimentResult:
        """Run a single experiment."""
        self.logger.info(f"Running experiment: {hypothesis.id}")
        start_time = time.time()

        try:
            baseline = self.load_baseline_metrics()
            df, features = self.prepare_data(hypothesis)
            metrics = self.train_and_evaluate(df, features, hypothesis)

            duration = time.time() - start_time

            improvement = {
                'r2': metrics['r2'] - baseline.get('ensemble_r2', 0.80),
                'rmse': baseline.get('ensemble_rmse', 2.47) - metrics['rmse'],
            }

            return ExperimentResult(
                hypothesis_id=hypothesis.id,
                status=ExperimentStatus.COMPLETED,
                metrics=metrics,
                baseline_metrics=baseline,
                improvement=improvement,
                duration_seconds=duration,
            )

        except Exception as e:
            self.logger.error(f"Experiment failed: {e}")
            return ExperimentResult(
                hypothesis_id=hypothesis.id,
                status=ExperimentStatus.FAILED,
                metrics={},
                baseline_metrics=self.load_baseline_metrics(),
                improvement={},
                duration_seconds=time.time() - start_time,
                error_message=str(e),
            )

    def run_cycle(self) -> List[Hypothesis]:
        """Run experiment lab cycle - executes pending experiments."""
        self.logger.info("=== Experiment Lab: Starting cycle ===")

        max_experiments = 5
        experiments_run = 0

        while self.registry.has_pending() and experiments_run < max_experiments:
            hypothesis = self.registry.next_hypothesis()
            if hypothesis is None:
                break

            result = self.run_experiment(hypothesis)
            self.registry.record_result(result)
            experiments_run += 1

        self.logger.info(f"=== Experiment Lab: Ran {experiments_run} experiments ===")
        return []  # Lab doesn't generate hypotheses, it runs them


# =============================================================================
# Master Orchestrator
# =============================================================================

class AutonomousMLOrchestrator:
    """
    Master orchestrator coordinating all agents.

    Strategies:
    - EXPLORATION: Diverse hypothesis generation
    - EXPLOITATION: Focus on winning areas
    - ADVERSARIAL: Target prediction failures
    - ENSEMBLE: Optimize model composition
    - ARCHITECTURE: Neural architecture search
    - DATA_CENTRIC: Focus on data quality
    """

    def __init__(self, strategy: ImprovementStrategy = ImprovementStrategy.EXPLORATION):
        self.strategy = strategy
        self.registry = ExperimentRegistry()

        # Initialize all agents
        self.agents = {
            'data_scout': DataScoutAgent(self.registry),
            'feature_engineer': EnhancedFeatureEngineerAgent(self.registry),
            'error_analyst': ErrorAnalystAgent(self.registry),
            'architecture_search': ArchitectureSearchAgent(self.registry),
            'drift_monitor': DriftMonitorAgent(self.registry),
            'meta_learner': MetaLearnerAgent(self.registry),
            'llm_creative': LLMCreativeAgent(self.registry),  # Local LLM (cost: $0)
            'experiment_lab': ExperimentLab(self.registry),
            'model_promoter': ModelPromoterAgent(self.registry),
        }

        # Check LLM status
        if self.agents['llm_creative'].hub:
            logger.info("Local LLM connected - creative reasoning enabled")

        self.cycle_count = 0
        self.total_hypotheses = 0
        self.total_experiments = 0

    def get_agents_for_strategy(self) -> List[str]:
        """Get agents to run based on current strategy."""
        strategy_agents = {
            ImprovementStrategy.EXPLORATION: [
                'data_scout', 'feature_engineer', 'architecture_search', 'meta_learner',
                'llm_creative'  # LLM for creative brainstorming
            ],
            ImprovementStrategy.EXPLOITATION: [
                'feature_engineer', 'meta_learner', 'llm_creative'
            ],
            ImprovementStrategy.ADVERSARIAL: [
                'error_analyst', 'drift_monitor', 'llm_creative'  # LLM for error analysis
            ],
            ImprovementStrategy.ENSEMBLE: [
                'architecture_search', 'feature_engineer'
            ],
            ImprovementStrategy.ARCHITECTURE: [
                'architecture_search'
            ],
            ImprovementStrategy.DATA_CENTRIC: [
                'data_scout', 'drift_monitor', 'llm_creative'  # LLM for data source ideas
            ],
        }

        return strategy_agents.get(self.strategy, list(self.agents.keys()))

    def run_improvement_cycle(self) -> Dict:
        """Run one complete improvement cycle."""
        self.cycle_count += 1
        cycle_start = datetime.now()

        logger.info("=" * 80)
        logger.info(f"AUTONOMOUS ML IMPROVEMENT CYCLE #{self.cycle_count}")
        logger.info(f"Strategy: {self.strategy.value}")
        logger.info(f"Started: {cycle_start.isoformat()}")
        logger.info("=" * 80)

        cycle_stats = {
            'cycle': self.cycle_count,
            'strategy': self.strategy.value,
            'started_at': cycle_start.isoformat(),
            'hypotheses_generated': 0,
            'experiments_run': 0,
            'experiments_passed': 0,
            'models_promoted': 0,
            'agent_results': {},
        }

        # Phase 1: Run hypothesis-generating agents
        logger.info("\n--- Phase 1: Generating Hypotheses ---")
        agents_to_run = self.get_agents_for_strategy()

        for agent_name in agents_to_run:
            if agent_name in ['experiment_lab', 'model_promoter']:
                continue  # These run later

            agent = self.agents[agent_name]
            hypotheses = agent.safe_run_cycle()

            cycle_stats['agent_results'][agent_name] = {
                'hypotheses': len(hypotheses),
                'status': agent.status.value,
            }

            for h in hypotheses:
                self.registry.queue_hypothesis(h)

            cycle_stats['hypotheses_generated'] += len(hypotheses)

        self.total_hypotheses += cycle_stats['hypotheses_generated']
        logger.info(f"Total hypotheses generated: {cycle_stats['hypotheses_generated']}")
        logger.info(f"Queue size: {self.registry.queue_size()}")

        # Phase 2: Run experiments
        logger.info("\n--- Phase 2: Running Experiments ---")
        lab = self.agents['experiment_lab']

        before_count = len([r for r in self.registry.results.values()
                          if r.status == ExperimentStatus.COMPLETED])

        lab.safe_run_cycle()

        after_count = len([r for r in self.registry.results.values()
                          if r.status == ExperimentStatus.COMPLETED])

        cycle_stats['experiments_run'] = after_count - before_count
        self.total_experiments += cycle_stats['experiments_run']

        # Phase 3: Evaluate and promote
        logger.info("\n--- Phase 3: Evaluation & Promotion ---")
        promoter = self.agents['model_promoter']

        before_promoted = len([r for r in self.registry.results.values()
                              if r.status == ExperimentStatus.PROMOTED])

        promoter.safe_run_cycle()

        after_promoted = len([r for r in self.registry.results.values()
                             if r.status == ExperimentStatus.PROMOTED])

        cycle_stats['models_promoted'] = after_promoted - before_promoted

        # Cycle summary
        cycle_stats['finished_at'] = datetime.now().isoformat()
        cycle_stats['duration_seconds'] = (datetime.now() - cycle_start).total_seconds()

        logger.info("\n" + "=" * 80)
        logger.info("CYCLE SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Hypotheses generated: {cycle_stats['hypotheses_generated']}")
        logger.info(f"Experiments run: {cycle_stats['experiments_run']}")
        logger.info(f"Models promoted: {cycle_stats['models_promoted']}")
        logger.info(f"Queue remaining: {self.registry.queue_size()}")
        logger.info(f"Duration: {cycle_stats['duration_seconds']:.1f}s")

        return cycle_stats

    def run_continuous(self, interval_seconds: int = 3600, max_cycles: int = None):
        """Run continuous improvement loop."""
        logger.info(f"Starting continuous improvement (interval: {interval_seconds}s)")

        cycle = 0
        while max_cycles is None or cycle < max_cycles:
            try:
                self.run_improvement_cycle()
                cycle += 1
            except KeyboardInterrupt:
                logger.info("Interrupted by user")
                break
            except Exception as e:
                logger.error(f"Cycle failed: {e}")

            if max_cycles is None or cycle < max_cycles:
                logger.info(f"Sleeping for {interval_seconds} seconds...")
                time.sleep(interval_seconds)

    def run_specific_agent(self, agent_name: str) -> List[Hypothesis]:
        """Run a specific agent only."""
        if agent_name not in self.agents:
            raise ValueError(f"Unknown agent: {agent_name}")

        agent = self.agents[agent_name]
        return agent.safe_run_cycle()

    def get_status(self) -> Dict:
        """Get comprehensive system status."""
        return {
            'strategy': self.strategy.value,
            'cycle_count': self.cycle_count,
            'total_hypotheses': self.total_hypotheses,
            'total_experiments': self.total_experiments,
            'registry_stats': self.registry.get_statistics(),
            'agents': {name: agent.get_status() for name, agent in self.agents.items()},
            'best_experiments': [
                {
                    'id': r.hypothesis_id,
                    'improvement': r.r2_improvement,
                    'status': r.status.value,
                }
                for r in self.registry.get_best_experiments(5)
            ],
        }

    def generate_report(self) -> str:
        """Generate human-readable status report."""
        status = self.get_status()

        report = []
        report.append("=" * 60)
        report.append("AUTONOMOUS ML IMPROVEMENT SYSTEM - STATUS REPORT")
        report.append(f"Generated: {datetime.now().isoformat()}")
        report.append("=" * 60)
        report.append("")
        report.append(f"Strategy: {status['strategy']}")
        report.append(f"Cycles completed: {status['cycle_count']}")
        report.append(f"Total hypotheses: {status['total_hypotheses']}")
        report.append(f"Total experiments: {status['total_experiments']}")
        report.append("")
        report.append("--- Registry Statistics ---")
        for key, value in status['registry_stats'].items():
            report.append(f"  {key}: {value}")
        report.append("")
        report.append("--- Agent Status ---")
        for name, agent_status in status['agents'].items():
            report.append(f"  {name}: {agent_status['status']} (runs: {agent_status['run_count']})")
        report.append("")
        report.append("--- Best Experiments ---")
        for exp in status['best_experiments']:
            report.append(f"  {exp['id']}: +{exp['improvement']:.4f} R² ({exp['status']})")
        report.append("")

        return "\n".join(report)


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Autonomous ML Improvement System v2',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run single improvement cycle
  python -m src.ml.autonomous_ml_system --cycle

  # Run with specific strategy
  python -m src.ml.autonomous_ml_system --cycle --strategy adversarial

  # Run continuously (hourly)
  python -m src.ml.autonomous_ml_system --continuous --interval 3600

  # Run specific agent
  python -m src.ml.autonomous_ml_system --agent feature_engineer

  # Generate status report
  python -m src.ml.autonomous_ml_system --report
        """
    )

    parser.add_argument('--cycle', action='store_true',
                       help='Run single improvement cycle')
    parser.add_argument('--continuous', action='store_true',
                       help='Run continuous improvement loop')
    parser.add_argument('--interval', type=int, default=3600,
                       help='Interval between cycles in seconds (default: 3600)')
    parser.add_argument('--max-cycles', type=int, default=None,
                       help='Maximum cycles for continuous mode')
    parser.add_argument('--strategy', type=str, default='exploration',
                       choices=['exploration', 'exploitation', 'adversarial',
                               'ensemble', 'architecture', 'data_centric'],
                       help='Improvement strategy to use')
    parser.add_argument('--agent', type=str,
                       choices=['data_scout', 'feature_engineer', 'error_analyst',
                               'architecture_search', 'drift_monitor', 'meta_learner',
                               'llm_creative'],
                       help='Run specific agent only (llm_creative uses local LLM at $0 cost)')
    parser.add_argument('--status', action='store_true',
                       help='Show system status as JSON')
    parser.add_argument('--report', action='store_true',
                       help='Generate human-readable report')

    args = parser.parse_args()

    # Map strategy string to enum
    strategy_map = {
        'exploration': ImprovementStrategy.EXPLORATION,
        'exploitation': ImprovementStrategy.EXPLOITATION,
        'adversarial': ImprovementStrategy.ADVERSARIAL,
        'ensemble': ImprovementStrategy.ENSEMBLE,
        'architecture': ImprovementStrategy.ARCHITECTURE,
        'data_centric': ImprovementStrategy.DATA_CENTRIC,
    }
    strategy = strategy_map.get(args.strategy, ImprovementStrategy.EXPLORATION)

    orchestrator = AutonomousMLOrchestrator(strategy=strategy)

    if args.status:
        print(json.dumps(orchestrator.get_status(), indent=2))
    elif args.report:
        print(orchestrator.generate_report())
    elif args.agent:
        hypotheses = orchestrator.run_specific_agent(args.agent)
        # Queue the hypotheses to the registry
        queued = 0
        for h in hypotheses:
            if orchestrator.registry.queue_hypothesis(h):
                queued += 1
        print(f"Generated {len(hypotheses)} hypotheses, queued {queued} new")
        for h in hypotheses[:10]:
            print(f"  - {h.id}: {h.description} (priority={h.priority:.2f})")
    elif args.continuous:
        orchestrator.run_continuous(args.interval, args.max_cycles)
    elif args.cycle:
        stats = orchestrator.run_improvement_cycle()
        print(json.dumps(stats, indent=2))
    else:
        # Default: run single cycle
        stats = orchestrator.run_improvement_cycle()
        print(json.dumps(stats, indent=2))

    return 0


if __name__ == '__main__':
    sys.exit(main())
