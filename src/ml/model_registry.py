"""Model Registry for Dynasty Edge ML Pipeline.

Tracks model versions, metrics, and metadata for production deployment.
Enables model comparison, rollback, and automated best-model selection.

Usage:
    from src.ml.model_registry import ModelRegistry

    registry = ModelRegistry()

    # Register new model
    registry.register_model(
        model_type='ensemble',
        version='v2.1',
        metrics={'r2': 0.91, 'rmse': 2.1},
        config={'n_folds': 5, 'stacking': True}
    )

    # Get best performing model
    best = registry.get_best_model(metric='r2')

    # Compare models
    comparison = registry.compare_models(['v2.0', 'v2.1'])
"""

import json
import hashlib
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any, Union
import logging

logger = logging.getLogger(__name__)


class ModelRegistry:
    """
    Centralized model version tracking and management.

    Features:
    - Version tracking with semantic versioning
    - Performance metric storage (R², RMSE, MAE, etc.)
    - Training configuration logging
    - Model file checksums for integrity
    - Comparison and rollback support
    - Production deployment tracking

    Attributes:
        models_dir: Path to model storage directory
        registry_file: Path to JSON registry metadata
    """

    def __init__(
        self,
        models_dir: Union[str, Path] = "data/models",
        registry_file: Optional[Union[str, Path]] = None
    ):
        """
        Initialize the model registry.

        Args:
            models_dir: Directory containing model files
            registry_file: Path to registry JSON (defaults to models_dir/registry.json)
        """
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)

        self.registry_file = Path(registry_file) if registry_file else self.models_dir / "registry.json"
        self._registry = self._load_registry()

    def _load_registry(self) -> Dict[str, Any]:
        """Load registry from JSON file or create empty registry."""
        if self.registry_file.exists():
            try:
                with open(self.registry_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.warning(f"Corrupted registry file, creating new: {self.registry_file}")

        return {
            "models": {},
            "production": None,
            "created": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat()
        }

    def _save_registry(self) -> None:
        """Persist registry to JSON file."""
        self._registry["last_updated"] = datetime.now().isoformat()
        with open(self.registry_file, 'w') as f:
            json.dump(self._registry, f, indent=2, default=str)

    def _compute_checksum(self, file_path: Path) -> str:
        """Compute MD5 checksum of a file for integrity verification."""
        if not file_path.exists():
            return ""

        hasher = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _get_model_files(self, model_type: str, version: str) -> Dict[str, Path]:
        """Get expected file paths for a model version."""
        prefix = f"{model_type}_{version.replace('.', '_')}"

        return {
            "nn": self.models_dir / f"{prefix}_nn.pt",
            "gbm": self.models_dir / f"{prefix}_gbm.pkl",
            "rf": self.models_dir / f"{prefix}_rf.pkl",
            "ridge": self.models_dir / f"{prefix}_ridge.pkl",
            "meta": self.models_dir / f"{prefix}_meta.pkl",
            "scaler": self.models_dir / f"{prefix}_scaler.pkl",
            "config": self.models_dir / f"{prefix}_config.json"
        }

    def register_model(
        self,
        model_type: str,
        version: str,
        metrics: Dict[str, float],
        config: Dict[str, Any],
        files: Optional[Dict[str, Union[str, Path]]] = None,
        description: str = "",
        set_production: bool = False
    ) -> str:
        """
        Register a new model version in the registry.

        Args:
            model_type: Type of model (e.g., 'ensemble', 'nn', 'gbm')
            version: Semantic version string (e.g., 'v2.1.0')
            metrics: Performance metrics dict (r2, rmse, mae, etc.)
            config: Training configuration dict
            files: Dict mapping file types to paths (optional)
            description: Human-readable description
            set_production: Whether to set this as production model

        Returns:
            Unique model ID
        """
        model_id = f"{model_type}_{version}"

        # Validate version doesn't already exist
        if model_id in self._registry["models"]:
            logger.warning(f"Model {model_id} already exists, updating...")

        # Compute checksums for provided files
        checksums = {}
        file_sizes = {}
        if files:
            for file_type, file_path in files.items():
                path = Path(file_path)
                if path.exists():
                    checksums[file_type] = self._compute_checksum(path)
                    file_sizes[file_type] = path.stat().st_size

        # Create model entry
        model_entry = {
            "model_type": model_type,
            "version": version,
            "metrics": metrics,
            "config": config,
            "description": description,
            "files": {k: str(v) for k, v in (files or {}).items()},
            "checksums": checksums,
            "file_sizes": file_sizes,
            "registered": datetime.now().isoformat(),
            "trained_date": config.get("trained_date", datetime.now().isoformat()),
            "is_production": set_production
        }

        self._registry["models"][model_id] = model_entry

        if set_production:
            # Unset previous production model
            if self._registry["production"]:
                prev_id = self._registry["production"]
                if prev_id in self._registry["models"]:
                    self._registry["models"][prev_id]["is_production"] = False
            self._registry["production"] = model_id

        self._save_registry()
        logger.info(f"Registered model: {model_id} (R²={metrics.get('r2', 'N/A')})")

        return model_id

    def get_model(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Get model entry by ID."""
        return self._registry["models"].get(model_id)

    def get_best_model(
        self,
        model_type: Optional[str] = None,
        metric: str = "r2",
        minimize: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Get the best performing model by a specific metric.

        Args:
            model_type: Filter by model type (optional)
            metric: Metric to compare (default: 'r2')
            minimize: If True, lower is better (e.g., RMSE)

        Returns:
            Best model entry or None
        """
        candidates = []

        for model_id, entry in self._registry["models"].items():
            if model_type and entry["model_type"] != model_type:
                continue
            if metric in entry["metrics"]:
                candidates.append(entry)

        if not candidates:
            return None

        return sorted(
            candidates,
            key=lambda x: x["metrics"].get(metric, float('-inf' if not minimize else 'inf')),
            reverse=not minimize
        )[0]

    def get_production_model(self) -> Optional[Dict[str, Any]]:
        """Get the current production model."""
        prod_id = self._registry.get("production")
        if prod_id:
            return self._registry["models"].get(prod_id)
        return None

    def set_production_model(self, model_id: str) -> bool:
        """
        Set a model as the production model.

        Args:
            model_id: ID of model to set as production

        Returns:
            True if successful
        """
        if model_id not in self._registry["models"]:
            logger.error(f"Model {model_id} not found in registry")
            return False

        # Unset previous production model
        if self._registry["production"]:
            prev_id = self._registry["production"]
            if prev_id in self._registry["models"]:
                self._registry["models"][prev_id]["is_production"] = False

        self._registry["models"][model_id]["is_production"] = True
        self._registry["production"] = model_id
        self._save_registry()

        logger.info(f"Set production model: {model_id}")
        return True

    def compare_models(
        self,
        model_ids: Optional[List[str]] = None,
        metrics: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Compare multiple models side-by-side.

        Args:
            model_ids: List of model IDs to compare (all if None)
            metrics: Specific metrics to include (all if None)

        Returns:
            Comparison dict with rankings
        """
        if model_ids is None:
            model_ids = list(self._registry["models"].keys())

        models_data = []
        for mid in model_ids:
            entry = self._registry["models"].get(mid)
            if entry:
                models_data.append({
                    "model_id": mid,
                    **entry
                })

        if not models_data:
            return {"error": "No models found"}

        # Determine metrics to compare
        if metrics is None:
            all_metrics = set()
            for m in models_data:
                all_metrics.update(m.get("metrics", {}).keys())
            metrics = list(all_metrics)

        # Create comparison table
        comparison = {
            "models": models_data,
            "metrics_compared": metrics,
            "rankings": {}
        }

        # Rank by each metric
        for metric in metrics:
            # Determine if lower is better
            minimize = metric.lower() in ['rmse', 'mae', 'mse', 'loss', 'error']

            ranked = sorted(
                [m for m in models_data if metric in m.get("metrics", {})],
                key=lambda x: x["metrics"].get(metric, float('inf' if minimize else '-inf')),
                reverse=not minimize
            )

            comparison["rankings"][metric] = [
                {"model_id": m["model_id"], "value": m["metrics"][metric]}
                for m in ranked
            ]

        # Add summary
        if models_data:
            comparison["summary"] = {
                "total_models": len(models_data),
                "best_r2": max(
                    (m["metrics"].get("r2", 0) for m in models_data),
                    default=0
                ),
                "best_rmse": min(
                    (m["metrics"].get("rmse", float('inf')) for m in models_data),
                    default=float('inf')
                ),
                "production_model": self._registry.get("production")
            }

        return comparison

    def list_models(
        self,
        model_type: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        List registered models, sorted by registration date.

        Args:
            model_type: Filter by type (optional)
            limit: Max number to return

        Returns:
            List of model entries
        """
        models = []
        for model_id, entry in self._registry["models"].items():
            if model_type and entry["model_type"] != model_type:
                continue
            models.append({"model_id": model_id, **entry})

        # Sort by registration date (newest first)
        models.sort(key=lambda x: x.get("registered", ""), reverse=True)

        return models[:limit]

    def delete_model(self, model_id: str, delete_files: bool = False) -> bool:
        """
        Remove a model from the registry.

        Args:
            model_id: ID of model to delete
            delete_files: Also delete model files from disk

        Returns:
            True if successful
        """
        if model_id not in self._registry["models"]:
            logger.warning(f"Model {model_id} not found")
            return False

        if model_id == self._registry.get("production"):
            logger.error("Cannot delete production model. Set a different production model first.")
            return False

        entry = self._registry["models"][model_id]

        if delete_files and "files" in entry:
            for file_type, file_path in entry["files"].items():
                path = Path(file_path)
                if path.exists():
                    path.unlink()
                    logger.info(f"Deleted file: {path}")

        del self._registry["models"][model_id]
        self._save_registry()

        logger.info(f"Deleted model: {model_id}")
        return True

    def verify_model_integrity(self, model_id: str) -> Dict[str, bool]:
        """
        Verify model files match stored checksums.

        Args:
            model_id: ID of model to verify

        Returns:
            Dict mapping file types to verification status
        """
        entry = self._registry["models"].get(model_id)
        if not entry:
            return {"error": f"Model {model_id} not found"}

        results = {}
        for file_type, stored_checksum in entry.get("checksums", {}).items():
            file_path = entry.get("files", {}).get(file_type)
            if file_path:
                path = Path(file_path)
                if path.exists():
                    current_checksum = self._compute_checksum(path)
                    results[file_type] = current_checksum == stored_checksum
                else:
                    results[file_type] = False  # File missing
            else:
                results[file_type] = True  # No file expected

        return results

    def export_registry(self, output_path: Union[str, Path]) -> None:
        """Export registry to a JSON file."""
        with open(output_path, 'w') as f:
            json.dump(self._registry, f, indent=2, default=str)
        logger.info(f"Exported registry to: {output_path}")

    def get_model_history(
        self,
        model_type: str,
        metric: str = "r2"
    ) -> List[Dict[str, Any]]:
        """
        Get performance history for a model type over versions.

        Args:
            model_type: Type of model to track
            metric: Metric to track

        Returns:
            List of {version, metric_value, date} sorted by date
        """
        history = []

        for model_id, entry in self._registry["models"].items():
            if entry["model_type"] != model_type:
                continue

            history.append({
                "version": entry["version"],
                "model_id": model_id,
                metric: entry["metrics"].get(metric),
                "date": entry.get("trained_date", entry.get("registered"))
            })

        # Sort by date
        history.sort(key=lambda x: x.get("date", ""))

        return history

    def generate_report(self) -> str:
        """Generate a human-readable registry report."""
        lines = [
            "=" * 60,
            "DYNASTY EDGE MODEL REGISTRY REPORT",
            "=" * 60,
            f"Generated: {datetime.now().isoformat()}",
            f"Total Models: {len(self._registry['models'])}",
            f"Production Model: {self._registry.get('production', 'None')}",
            "",
            "-" * 60,
            "REGISTERED MODELS",
            "-" * 60
        ]

        for model_id, entry in sorted(
            self._registry["models"].items(),
            key=lambda x: x[1].get("registered", ""),
            reverse=True
        ):
            prod_marker = " [PRODUCTION]" if entry.get("is_production") else ""
            lines.append(f"\n{model_id}{prod_marker}")
            lines.append(f"  Type: {entry['model_type']}")
            lines.append(f"  Version: {entry['version']}")
            lines.append(f"  Registered: {entry.get('registered', 'Unknown')}")

            if entry.get("metrics"):
                metrics_str = ", ".join(
                    f"{k}={v:.4f}" if isinstance(v, float) else f"{k}={v}"
                    for k, v in entry["metrics"].items()
                )
                lines.append(f"  Metrics: {metrics_str}")

            if entry.get("description"):
                lines.append(f"  Description: {entry['description']}")

        lines.extend([
            "",
            "-" * 60,
            "PERFORMANCE RANKINGS (by R²)",
            "-" * 60
        ])

        comparison = self.compare_models()
        if "rankings" in comparison and "r2" in comparison["rankings"]:
            for i, ranked in enumerate(comparison["rankings"]["r2"][:5], 1):
                lines.append(f"  {i}. {ranked['model_id']}: R²={ranked['value']:.4f}")

        lines.append("=" * 60)

        return "\n".join(lines)


# Convenience functions for CLI usage
def register_optimized_ensemble(
    registry: ModelRegistry,
    version: str,
    r2: float,
    rmse: float,
    config: Dict[str, Any],
    files: Dict[str, str],
    set_production: bool = True
) -> str:
    """
    Register a new optimized stacked ensemble model.

    Args:
        registry: ModelRegistry instance
        version: Version string (e.g., 'v2.1')
        r2: R² score on test set
        rmse: RMSE on test set
        config: Training configuration
        files: Dict of model file paths
        set_production: Set as production model

    Returns:
        Model ID
    """
    return registry.register_model(
        model_type="stacked_ensemble",
        version=version,
        metrics={
            "r2": r2,
            "rmse": rmse,
            "improvements": config.get("improvements", [])
        },
        config=config,
        files=files,
        description=f"Stacked ensemble with R²={r2:.4f}",
        set_production=set_production
    )


if __name__ == "__main__":
    # CLI for model registry management
    import argparse

    parser = argparse.ArgumentParser(description="Dynasty Edge Model Registry")
    parser.add_argument("--list", action="store_true", help="List all models")
    parser.add_argument("--compare", action="store_true", help="Compare all models")
    parser.add_argument("--report", action="store_true", help="Generate full report")
    parser.add_argument("--production", type=str, help="Set production model by ID")
    parser.add_argument("--models-dir", default="data/models", help="Models directory")

    args = parser.parse_args()

    registry = ModelRegistry(models_dir=args.models_dir)

    if args.list:
        models = registry.list_models()
        print("\nRegistered Models:")
        for m in models:
            r2 = m.get("metrics", {}).get("r2", "N/A")
            prod = " [PRODUCTION]" if m.get("is_production") else ""
            print(f"  - {m['model_id']}: R²={r2}{prod}")

    elif args.compare:
        comparison = registry.compare_models()
        print("\nModel Comparison:")
        print(json.dumps(comparison, indent=2, default=str))

    elif args.report:
        print(registry.generate_report())

    elif args.production:
        if registry.set_production_model(args.production):
            print(f"Set production model: {args.production}")
        else:
            print(f"Failed to set production model: {args.production}")

    else:
        parser.print_help()
