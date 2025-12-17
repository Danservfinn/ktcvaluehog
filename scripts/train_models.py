#!/usr/bin/env python3
"""
Fantasy Football ML Model Training Script
==========================================
Train ML models on historical NFL data.

Usage:
    python scripts/train_models.py                  # Train all models
    python scripts/train_models.py --season-only   # Only season projection
    python scripts/train_models.py --breakout-only # Only breakout classifier
    python scripts/train_models.py --evaluate      # Evaluate existing models
"""

import os
import sys
import argparse
import logging
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def train_season_projection_model(data_dir: str, output_dir: str):
    """Train the season projection model."""
    from src.ml.fantasy_models import SeasonProjectionModel

    logger.info("=" * 70)
    logger.info("TRAINING: Season Projection Model")
    logger.info("=" * 70)

    # Load data
    data_path = Path(data_dir) / 'season_projection.parquet'
    df = pd.read_parquet(data_path)

    logger.info(f"Dataset: {len(df):,} samples, {len(df.columns)} features")
    logger.info(f"Positions: {df['position'].value_counts().to_dict()}")

    # Train model
    model = SeasonProjectionModel(model_type='auto')
    metrics = model.fit(df)

    # Save model
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    model.save(str(output_path / 'season_projection_model.pkl'))

    # Show feature importance
    importance = model.get_feature_importance()
    logger.info("\nTop 15 Feature Importances:")
    logger.info("-" * 50)
    for _, row in importance.head(15).iterrows():
        bar = "█" * int(row['importance'] * 50)
        logger.info(f"  {row['feature']:25} {row['importance']:.3f} {bar}")

    return model, metrics


def train_breakout_classifier(data_dir: str, output_dir: str):
    """Train the breakout classifier."""
    from src.ml.fantasy_models import BreakoutClassifier

    logger.info("=" * 70)
    logger.info("TRAINING: Breakout Classifier")
    logger.info("=" * 70)

    # Load data
    data_path = Path(data_dir) / 'breakout_probability.parquet'
    df = pd.read_parquet(data_path)

    logger.info(f"Dataset: {len(df):,} samples")
    logger.info(f"Breakouts: {df['is_breakout'].sum()} ({df['is_breakout'].mean()*100:.1f}%)")

    # Train model
    model = BreakoutClassifier(model_type='auto')
    metrics = model.fit(df)

    # Save model
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    model.save(str(output_path / 'breakout_classifier.pkl'))

    return model, metrics


def evaluate_models(data_dir: str, model_dir: str):
    """Evaluate trained models on test data."""
    from src.ml.fantasy_models import SeasonProjectionModel, BreakoutClassifier

    logger.info("=" * 70)
    logger.info("MODEL EVALUATION")
    logger.info("=" * 70)

    model_path = Path(model_dir)
    data_path = Path(data_dir)

    # Evaluate Season Projection Model
    if (model_path / 'season_projection_model.pkl').exists():
        logger.info("\n--- Season Projection Model ---")
        model = SeasonProjectionModel.load(str(model_path / 'season_projection_model.pkl'))

        logger.info(f"Model type: {model.model_type}")
        logger.info(f"Features: {len(model.feature_columns)}")

        for key, value in model.metrics.items():
            if isinstance(value, float):
                logger.info(f"  {key}: {value:.4f}")
            else:
                logger.info(f"  {key}: {value}")

        # Test predictions on recent data
        df = pd.read_parquet(data_path / 'season_projection.parquet')
        recent = df[df['season'] >= 2020].head(10)

        if not recent.empty:
            predictions = model.predict(recent)
            logger.info("\nSample Predictions (2020+ seasons):")
            logger.info(f"  {'Player ID':15} {'Pos':3} {'Year':4} {'Actual':>8} {'Predicted':>10} {'Error':>8}")
            logger.info("  " + "-" * 55)
            for i, (_, row) in enumerate(recent.iterrows()):
                actual = row['next_ppg_ppr']
                pred = predictions[i]
                error = pred - actual
                logger.info(f"  {row['player_id']:15} {row['position']:3} {row['season']:4} "
                          f"{actual:8.1f} {pred:10.1f} {error:+8.1f}")

    # Evaluate Breakout Classifier
    if (model_path / 'breakout_classifier.pkl').exists():
        logger.info("\n--- Breakout Classifier ---")
        model = BreakoutClassifier.load(str(model_path / 'breakout_classifier.pkl'))

        logger.info(f"Model type: {model.model_type}")

        for key, value in model.metrics.items():
            if isinstance(value, float):
                logger.info(f"  {key}: {value:.4f}")
            else:
                logger.info(f"  {key}: {value}")


def show_model_insights(data_dir: str, model_dir: str):
    """Show detailed model insights and predictions."""
    from src.ml.fantasy_models import SeasonProjectionModel

    logger.info("=" * 70)
    logger.info("MODEL INSIGHTS")
    logger.info("=" * 70)

    model_path = Path(model_dir)
    data_path = Path(data_dir)

    if not (model_path / 'season_projection_model.pkl').exists():
        logger.error("Season projection model not found. Train first.")
        return

    model = SeasonProjectionModel.load(str(model_path / 'season_projection_model.pkl'))
    df = pd.read_parquet(data_path / 'season_projection.parquet')

    # Predictions by position
    logger.info("\nPrediction Performance by Position:")
    logger.info("-" * 50)

    for pos in ['QB', 'RB', 'WR', 'TE']:
        pos_df = df[df['position'] == pos]
        if len(pos_df) > 0:
            predictions = model.predict(pos_df)
            actuals = pos_df['next_ppg_ppr'].values
            rmse = np.sqrt(np.mean((predictions - actuals) ** 2))
            mae = np.mean(np.abs(predictions - actuals))
            r2 = 1 - np.sum((actuals - predictions) ** 2) / np.sum((actuals - actuals.mean()) ** 2)
            logger.info(f"  {pos}: RMSE={rmse:.2f}, MAE={mae:.2f}, R²={r2:.3f} (n={len(pos_df)})")

    # Feature importance by category
    importance = model.get_feature_importance()

    categories = {
        'Production': ['ppg_ppr', 'ppg_std', 'total_fpts', 'games'],
        'Receiving': ['targets', 'receptions', 'receiving_yards', 'receiving_tds',
                     'targets_per_game', 'rec_yards_per_game', 'catch_rate', 'yards_per_catch'],
        'Rushing': ['carries', 'rushing_yards', 'rushing_tds',
                   'carries_per_game', 'rush_yards_per_game', 'yards_per_carry'],
        'Career': ['years_in_league', 'career_ppg', 'best_season_ppg',
                  'ppg_vs_career_avg', 'ppg_vs_best']
    }

    logger.info("\nFeature Importance by Category:")
    logger.info("-" * 50)

    for category, features in categories.items():
        cat_importance = importance[importance['feature'].isin(features)]['importance'].sum()
        logger.info(f"  {category:15} {cat_importance:.3f}")


def main():
    parser = argparse.ArgumentParser(description='Train Fantasy Football ML Models')
    parser.add_argument('--season-only', action='store_true', help='Train only season projection')
    parser.add_argument('--breakout-only', action='store_true', help='Train only breakout classifier')
    parser.add_argument('--evaluate', action='store_true', help='Evaluate existing models')
    parser.add_argument('--insights', action='store_true', help='Show model insights')
    parser.add_argument('--data-dir', type=str, default='data/ml_training', help='Training data directory')
    parser.add_argument('--model-dir', type=str, default='models', help='Model output directory')

    args = parser.parse_args()

    start_time = datetime.now()

    if args.evaluate:
        evaluate_models(args.data_dir, args.model_dir)
    elif args.insights:
        show_model_insights(args.data_dir, args.model_dir)
    elif args.season_only:
        train_season_projection_model(args.data_dir, args.model_dir)
    elif args.breakout_only:
        train_breakout_classifier(args.data_dir, args.model_dir)
    else:
        # Train all models
        logger.info("=" * 70)
        logger.info("FANTASY FOOTBALL ML MODEL TRAINING")
        logger.info(f"Started: {start_time}")
        logger.info("=" * 70)

        season_model, season_metrics = train_season_projection_model(args.data_dir, args.model_dir)
        breakout_model, breakout_metrics = train_breakout_classifier(args.data_dir, args.model_dir)

        duration = datetime.now() - start_time

        logger.info("\n" + "=" * 70)
        logger.info("TRAINING COMPLETE")
        logger.info("=" * 70)
        logger.info(f"\nSeason Projection Model:")
        logger.info(f"  Test R²: {season_metrics['test_r2']:.3f}")
        logger.info(f"  Test RMSE: {season_metrics['test_rmse']:.2f} PPG")
        logger.info(f"  CV R²: {season_metrics['cv_r2_mean']:.3f} ± {season_metrics['cv_r2_std']:.3f}")

        logger.info(f"\nBreakout Classifier:")
        logger.info(f"  Test AUC: {breakout_metrics['test_auc']:.3f}")
        logger.info(f"  Test Precision: {breakout_metrics['test_precision']:.3f}")
        logger.info(f"  Test Recall: {breakout_metrics['test_recall']:.3f}")

        logger.info(f"\nDuration: {duration}")
        logger.info(f"Models saved to: {args.model_dir}/")


if __name__ == "__main__":
    main()
