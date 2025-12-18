"""Machine learning pipeline for Dynasty Edge.

Implements:
- Stacked ensemble training (NN + GBM + RF + Ridge + Meta-Model)
- H2O AutoML training for KTC value prediction
- Prediction and signal generation
- Feature importance analysis
- Model version tracking and registry
"""
from .train import DynastyMLTrainer, FeatureEngineer
from .predict import DynastyPredictor, SignalReporter, update_neo4j_with_predictions
from .model_registry import ModelRegistry, register_optimized_ensemble
