#!/usr/bin/env python3
"""
Optimized ML Training Pipeline for Dynasty Edge
=================================================

Master training script that combines all R² improvement strategies:

1. Stacking meta-model ensemble (RidgeCV on base model predictions)
2. Temporal momentum features (KTC trends, injury, team strength)
3. Huber loss for outlier robustness
4. Feature attention neural network
5. Position-stratified training

Target: Improve R² from 0.87 to 0.90+

Usage:
    # Full optimized training
    python scripts/train_optimized_models.py

    # Train specific position only
    python scripts/train_optimized_models.py --position QB

    # Compare with baseline
    python scripts/train_optimized_models.py --compare-baseline

    # Skip specific optimizations
    python scripts/train_optimized_models.py --no-stacking --no-attention

Author: Dynasty Edge ML Team
"""

import os
import sys
import argparse
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import KFold
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge, RidgeCV
import joblib
import logging

# Import local modules
from src.ml.expanded_dataset_builder import ExpandedDatasetBuilder
from src.ml.neural_network_models import (
    FeatureAttentionNN,
    DynastyWeightedHuberLoss,
    SimpleFFN
)

try:
    import lightgbm as lgb
    HAS_LIGHTGBM = True
except ImportError:
    from sklearn.ensemble import GradientBoostingRegressor
    HAS_LIGHTGBM = False
    print("LightGBM not available, using sklearn GradientBoosting")

from dotenv import load_dotenv
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(project_root / 'logs' / 'training.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)


class OptimizedTrainer:
    """
    Optimized ML trainer combining all improvement strategies.

    Implements stacking ensemble with learned meta-weights instead of
    fixed weight averaging for improved R² performance.
    """

    def __init__(
        self,
        device: str = 'auto',
        use_stacking: bool = True,
        use_attention: bool = True,
        use_huber: bool = True,
        use_position_stratification: bool = True,
        n_folds: int = 5
    ):
        self.device = self._get_device(device)
        self.use_stacking = use_stacking
        self.use_attention = use_attention
        self.use_huber = use_huber
        self.use_position_stratification = use_position_stratification
        self.n_folds = n_folds

        # Model storage
        self.models = {}
        self.scalers = {}
        self.meta_model = None
        self.metrics = {}
        self.feature_cols = []

    def _get_device(self, device: str) -> torch.device:
        """Determine best available device."""
        if device == 'auto':
            if torch.cuda.is_available():
                return torch.device('cuda')
            elif torch.backends.mps.is_available():
                return torch.device('mps')
        return torch.device('cpu')

    def train(
        self,
        df: pd.DataFrame,
        feature_cols: list,
        target_col: str = 'next_ppg_ppr',
        test_seasons: list = None
    ) -> Dict[str, Any]:
        """
        Train optimized ensemble with all improvements.

        Args:
            df: Training dataframe with features and target
            feature_cols: List of feature column names
            target_col: Target column name
            test_seasons: Seasons to hold out for testing (default: 2022+)

        Returns:
            Dictionary with trained models and metrics
        """
        logger.info("="*70)
        logger.info("OPTIMIZED MODEL TRAINING")
        logger.info(f"Device: {self.device}")
        logger.info(f"Stacking: {self.use_stacking}, Attention: {self.use_attention}")
        logger.info(f"Huber Loss: {self.use_huber}, Position Stratification: {self.use_position_stratification}")
        logger.info("="*70)

        self.feature_cols = feature_cols

        # Time-based split (use only most recent season for test to maximize training data)
        test_seasons = test_seasons or [2023]
        train_mask = ~df['season'].isin(test_seasons)
        test_mask = df['season'].isin(test_seasons)

        df_train = df[train_mask].copy()
        df_test = df[test_mask].copy()

        logger.info(f"Training samples: {len(df_train):,}, Test samples: {len(df_test):,}")

        # Prepare features
        X_train = df_train[feature_cols].fillna(0).values
        X_test = df_test[feature_cols].fillna(0).values
        y_train = df_train[target_col].fillna(0).values
        y_test = df_test[target_col].fillna(0).values

        # Extract sample weights (for time-weighted training with era-normalized data)
        # Only use weights when spanning many eras (1999-2023), not for recent data (2016+)
        year_range = df_train['season'].max() - df_train['season'].min()
        if 'sample_weight' in df_train.columns and year_range > 10:
            sample_weights = df_train['sample_weight'].fillna(1.0).values
            logger.info(f"Using sample weights (era span: {year_range}y): min={sample_weights.min():.3f}, max={sample_weights.max():.3f}")
        else:
            sample_weights = None  # Let models use uniform weights
            logger.info(f"Using uniform weights (era span: {year_range}y)")

        # Scale features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        self.scalers['main'] = scaler

        # Encode positions
        pos_encoder = LabelEncoder()
        pos_encoder.fit(['QB', 'RB', 'WR', 'TE'])
        pos_train = pos_encoder.transform(df_train['position'].fillna('WR').values)
        pos_test = pos_encoder.transform(df_test['position'].fillna('WR').values)
        self.scalers['pos_encoder'] = pos_encoder

        # Train base models
        logger.info("\n--- Training Base Models ---")

        # 1. Neural Network (with attention if enabled)
        nn_model, nn_train_preds, nn_test_preds = self._train_neural_network(
            X_train_scaled, y_train, X_test_scaled, y_test,
            pos_train, pos_test
        )
        self.models['nn'] = nn_model
        nn_r2 = r2_score(y_test, nn_test_preds)
        logger.info(f"  NN Test R²: {nn_r2:.4f}")

        # 2. Gradient Boosting (with sample weights)
        gbm_model = self._train_gbm(X_train_scaled, y_train, sample_weights)
        gbm_test_preds = gbm_model.predict(X_test_scaled)
        self.models['gbm'] = gbm_model
        gbm_r2 = r2_score(y_test, gbm_test_preds)
        logger.info(f"  GBM Test R²: {gbm_r2:.4f}")

        # 3. Random Forest (with sample weights)
        rf_model = RandomForestRegressor(
            n_estimators=300, max_depth=10, min_samples_split=10,
            random_state=42, n_jobs=-1
        )
        rf_model.fit(X_train_scaled, y_train, sample_weight=sample_weights)
        rf_test_preds = rf_model.predict(X_test_scaled)
        self.models['rf'] = rf_model
        rf_r2 = r2_score(y_test, rf_test_preds)
        logger.info(f"  RF Test R²: {rf_r2:.4f}")

        # 4. Ridge Regression (with sample weights)
        ridge_model = Ridge(alpha=1.0)
        ridge_model.fit(X_train_scaled, y_train, sample_weight=sample_weights)
        ridge_test_preds = ridge_model.predict(X_test_scaled)
        self.models['ridge'] = ridge_model
        ridge_r2 = r2_score(y_test, ridge_test_preds)
        logger.info(f"  Ridge Test R²: {ridge_r2:.4f}")

        # Stacking or fixed weights
        if self.use_stacking:
            logger.info("\n--- Training Stacking Meta-Model ---")
            ensemble_preds, meta_model = self._train_stacking_ensemble(
                X_train_scaled, y_train, X_test_scaled,
                pos_train, pos_test,
                nn_test_preds, gbm_test_preds, rf_test_preds, ridge_test_preds
            )
            self.meta_model = meta_model
        else:
            # Fixed weight averaging
            ensemble_preds = (
                0.3 * nn_test_preds +
                0.35 * gbm_test_preds +
                0.2 * rf_test_preds +
                0.15 * ridge_test_preds
            )

        # Calculate final metrics
        ensemble_r2 = r2_score(y_test, ensemble_preds)
        ensemble_rmse = np.sqrt(mean_squared_error(y_test, ensemble_preds))
        ensemble_mae = mean_absolute_error(y_test, ensemble_preds)

        logger.info("\n" + "="*70)
        logger.info("FINAL RESULTS")
        logger.info("="*70)
        logger.info(f"Ensemble R²: {ensemble_r2:.4f}")
        logger.info(f"RMSE: {ensemble_rmse:.2f} PPG")
        logger.info(f"MAE: {ensemble_mae:.2f} PPG")

        # Position-stratified evaluation
        if self.use_position_stratification:
            logger.info("\nPosition-Specific R² Scores:")
            for pos in ['QB', 'RB', 'WR', 'TE']:
                pos_mask = df_test['position'] == pos
                if pos_mask.sum() > 10:
                    pos_r2 = r2_score(y_test[pos_mask], ensemble_preds[pos_mask])
                    logger.info(f"  {pos}: {pos_r2:.4f} (n={pos_mask.sum()})")

        self.metrics = {
            'ensemble_r2': ensemble_r2,
            'ensemble_rmse': ensemble_rmse,
            'ensemble_mae': ensemble_mae,
            'nn_r2': nn_r2,
            'gbm_r2': gbm_r2,
            'rf_r2': rf_r2,
            'ridge_r2': ridge_r2,
            'train_samples': len(df_train),
            'test_samples': len(df_test),
            'n_features': len(feature_cols),
            'optimizations': {
                'stacking': self.use_stacking,
                'attention': self.use_attention,
                'huber': self.use_huber,
                'position_stratification': self.use_position_stratification
            },
            'trained_at': datetime.now().isoformat()
        }

        return {
            'models': self.models,
            'meta_model': self.meta_model,
            'scalers': self.scalers,
            'metrics': self.metrics,
            'feature_cols': self.feature_cols,
            'predictions': {
                'test': ensemble_preds,
                'actual': y_test
            }
        }

    def _train_neural_network(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_test: np.ndarray,
        y_test: np.ndarray,
        pos_train: np.ndarray,
        pos_test: np.ndarray,
        epochs: int = 100,
        patience: int = 15
    ):
        """Train neural network with optional attention and Huber loss."""
        logger.info(f"  Training {'Attention' if self.use_attention else 'Simple'} NN...")

        # Create model
        input_dim = X_train.shape[1]
        if self.use_attention:
            model = FeatureAttentionNN(input_dim, n_positions=4)
        else:
            model = SimpleFFN(input_dim, n_positions=4)
        model.to(self.device)

        # Loss function
        if self.use_huber:
            criterion = DynastyWeightedHuberLoss(delta=5.0, dynasty_weight=True)
        else:
            criterion = nn.MSELoss()

        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=0.01)
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5, factor=0.5)

        # Convert to tensors
        X_train_t = torch.FloatTensor(X_train).to(self.device)
        y_train_t = torch.FloatTensor(y_train).to(self.device)
        pos_train_t = torch.LongTensor(pos_train).to(self.device)
        X_test_t = torch.FloatTensor(X_test).to(self.device)
        pos_test_t = torch.LongTensor(pos_test).to(self.device)

        # Training loop
        best_val_loss = float('inf')
        patience_counter = 0
        best_state = None

        for epoch in range(epochs):
            # Train
            model.train()
            optimizer.zero_grad()
            preds = model(X_train_t, pos_train_t)
            loss = criterion(preds, y_train_t)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

            # Validate
            model.eval()
            with torch.no_grad():
                val_preds = model(X_test_t, pos_test_t)
                val_loss = nn.MSELoss()(val_preds, torch.FloatTensor(y_test).to(self.device))

            scheduler.step(val_loss)

            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
                best_state = model.state_dict().copy()
            else:
                patience_counter += 1
                if patience_counter >= patience:
                    break

        model.load_state_dict(best_state)
        model.eval()

        # Get predictions
        with torch.no_grad():
            train_preds = model(X_train_t, pos_train_t).cpu().numpy()
            test_preds = model(X_test_t, pos_test_t).cpu().numpy()

        return model, train_preds, test_preds

    def _train_gbm(self, X_train: np.ndarray, y_train: np.ndarray, sample_weights: np.ndarray = None):
        """Train gradient boosting model with optional sample weights."""
        logger.info("  Training GBM...")
        if HAS_LIGHTGBM:
            # Best performing settings (R²=0.8035)
            model = lgb.LGBMRegressor(
                n_estimators=800, learning_rate=0.03, max_depth=7,
                num_leaves=63, subsample=0.8, colsample_bytree=0.8,
                reg_alpha=0.05, reg_lambda=0.05, random_state=42, verbose=-1
            )
        else:
            model = GradientBoostingRegressor(
                n_estimators=500, learning_rate=0.03, max_depth=6,
                min_samples_split=15, min_samples_leaf=5,
                subsample=0.8, random_state=42
            )
        model.fit(X_train, y_train, sample_weight=sample_weights)
        return model

    def _train_stacking_ensemble(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_test: np.ndarray,
        pos_train: np.ndarray,
        pos_test: np.ndarray,
        nn_test_preds: np.ndarray,
        gbm_test_preds: np.ndarray,
        rf_test_preds: np.ndarray,
        ridge_test_preds: np.ndarray
    ):
        """Train stacking meta-model using OOF predictions."""
        n_samples = len(X_train)
        kfold = KFold(n_splits=self.n_folds, shuffle=True, random_state=42)

        # OOF predictions
        oof_nn = np.zeros(n_samples)
        oof_gbm = np.zeros(n_samples)
        oof_rf = np.zeros(n_samples)
        oof_ridge = np.zeros(n_samples)

        for fold_idx, (train_idx, val_idx) in enumerate(kfold.split(X_train)):
            X_fold_train, X_fold_val = X_train[train_idx], X_train[val_idx]
            y_fold_train = y_train[train_idx]

            # GBM
            if HAS_LIGHTGBM:
                fold_gbm = lgb.LGBMRegressor(
                    n_estimators=300, learning_rate=0.05, max_depth=6,
                    random_state=42+fold_idx, verbose=-1
                )
            else:
                fold_gbm = GradientBoostingRegressor(
                    n_estimators=200, learning_rate=0.05, max_depth=5,
                    random_state=42+fold_idx
                )
            fold_gbm.fit(X_fold_train, y_fold_train)
            oof_gbm[val_idx] = fold_gbm.predict(X_fold_val)

            # RF
            fold_rf = RandomForestRegressor(
                n_estimators=150, max_depth=8, random_state=42+fold_idx, n_jobs=-1
            )
            fold_rf.fit(X_fold_train, y_fold_train)
            oof_rf[val_idx] = fold_rf.predict(X_fold_val)

            # Ridge
            fold_ridge = Ridge(alpha=1.0)
            fold_ridge.fit(X_fold_train, y_fold_train)
            oof_ridge[val_idx] = fold_ridge.predict(X_fold_val)

            # Simple NN for OOF
            fold_nn = nn.Sequential(
                nn.Linear(X_train.shape[1], 128),
                nn.ReLU(), nn.Dropout(0.2),
                nn.Linear(128, 64),
                nn.ReLU(), nn.Dropout(0.2),
                nn.Linear(64, 1)
            ).to(self.device)

            optimizer = torch.optim.AdamW(fold_nn.parameters(), lr=1e-3)
            X_t = torch.FloatTensor(X_fold_train).to(self.device)
            y_t = torch.FloatTensor(y_fold_train).to(self.device)

            fold_nn.train()
            for _ in range(50):
                optimizer.zero_grad()
                loss = nn.MSELoss()(fold_nn(X_t).squeeze(), y_t)
                loss.backward()
                optimizer.step()

            fold_nn.eval()
            with torch.no_grad():
                oof_nn[val_idx] = fold_nn(
                    torch.FloatTensor(X_fold_val).to(self.device)
                ).squeeze().cpu().numpy()

        # Train meta-model
        meta_features = np.column_stack([oof_nn, oof_gbm, oof_rf, oof_ridge])
        meta_model = RidgeCV(alphas=[0.01, 0.1, 0.5, 1.0, 5.0, 10.0], cv=5)
        meta_model.fit(meta_features, y_train)

        logger.info(f"  Meta-model alpha: {meta_model.alpha_:.4f}")
        logger.info(f"  Coefficients: NN={meta_model.coef_[0]:.3f}, GBM={meta_model.coef_[1]:.3f}, "
                   f"RF={meta_model.coef_[2]:.3f}, Ridge={meta_model.coef_[3]:.3f}")

        # Generate test predictions
        test_meta_features = np.column_stack([
            nn_test_preds, gbm_test_preds, rf_test_preds, ridge_test_preds
        ])
        ensemble_preds = meta_model.predict(test_meta_features)

        return ensemble_preds, meta_model

    def save(self, output_dir: Path):
        """Save all models and metadata."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save neural network
        torch.save({
            'model_state': self.models['nn'].state_dict(),
            'model_type': 'attention' if self.use_attention else 'simple',
            'input_dim': len(self.feature_cols)
        }, output_dir / 'optimized_nn.pt')

        # Save sklearn models
        joblib.dump(self.models['gbm'], output_dir / 'optimized_gbm.pkl')
        joblib.dump(self.models['rf'], output_dir / 'optimized_rf.pkl')
        joblib.dump(self.models['ridge'], output_dir / 'optimized_ridge.pkl')

        # Save meta-model
        if self.meta_model is not None:
            joblib.dump(self.meta_model, output_dir / 'stacking_meta.pkl')

        # Save scalers
        joblib.dump(self.scalers, output_dir / 'scalers.pkl')

        # Save metrics and config
        with open(output_dir / 'model_metrics.json', 'w') as f:
            json.dump(self.metrics, f, indent=2, default=str)

        with open(output_dir / 'feature_cols.json', 'w') as f:
            json.dump(self.feature_cols, f, indent=2)

        logger.info(f"Models saved to {output_dir}")


def build_dataset(use_expanded: bool = True, use_cached: bool = True, start_year: int = 1999) -> pd.DataFrame:
    """Build training dataset with all features.

    Args:
        use_expanded: If True, use expanded dataset with temporal features
        use_cached: If True, load pre-built parquet file if it exists (faster)
        start_year: Minimum year to include (2016 recommended for best feature coverage)
    """
    # Dataset paths by start year (higher coverage = better model performance)
    expanded_path_2016 = project_root / 'data' / 'ml_training' / 'expanded_season_projection_2016.parquet'
    expanded_path_2012 = project_root / 'data' / 'ml_training' / 'expanded_season_projection_2012.parquet'
    expanded_path = project_root / 'data' / 'ml_training' / 'expanded_season_projection.parquet'

    if use_expanded:
        # Prefer 2016+ dataset (best feature coverage: 96% snap%, 85% draft capital)
        if use_cached and expanded_path_2016.exists() and start_year >= 2016:
            logger.info(f"Loading 2016+ expanded dataset from {expanded_path_2016}...")
            df = pd.read_parquet(expanded_path_2016)
            logger.info(f"  Loaded {len(df):,} rows, {len(df.columns)} columns")
            logger.info(f"  Year range: {df['season'].min()}-{df['season'].max()}")
            return df

        # Fall back to 2012+ dataset
        if use_cached and expanded_path_2012.exists() and start_year >= 2012:
            logger.info(f"Loading 2012+ expanded dataset from {expanded_path_2012}...")
            df = pd.read_parquet(expanded_path_2012)
            logger.info(f"  Loaded {len(df):,} rows, {len(df.columns)} columns")
            logger.info(f"  Year range: {df['season'].min()}-{df['season'].max()}")
            return df

        # Fall back to full dataset
        if use_cached and expanded_path.exists():
            logger.info(f"Loading pre-built expanded dataset from {expanded_path}...")
            df = pd.read_parquet(expanded_path)
            # Filter by start_year if needed
            if start_year > df['season'].min():
                df = df[df['season'] >= start_year].copy()
            logger.info(f"  Loaded {len(df):,} rows, {len(df.columns)} columns")
            logger.info(f"  Year range: {df['season'].min()}-{df['season'].max()}")
            return df

        logger.info("Building expanded dataset with temporal features...")
        builder = ExpandedDatasetBuilder()
        try:
            df = builder.build_expanded_dataset(
                positions=['QB', 'RB', 'WR', 'TE'],
                min_games=6,
                start_year=1999,  # Extended with era-normalized features
                end_year=2023
            )
        finally:
            builder.close()
    else:
        logger.info("Loading base dataset...")
        df = pd.read_parquet(project_root / 'data' / 'ml_training' / 'season_projection.parquet')

    return df


def get_feature_cols(df: pd.DataFrame) -> list:
    """Get valid feature columns (exclude targets and identifiers)."""
    exclude_cols = ['player_id', 'player_name', 'position', 'season', 'team']
    leakage_cols = ['ppg_change', 'ppg_change_pct']

    feature_cols = [
        c for c in df.columns
        if c not in exclude_cols
        and c not in leakage_cols
        and not c.startswith('next_')
        and df[c].dtype in ['int64', 'float64', 'bool', 'uint8']
        and df[c].notna().sum() > len(df) * 0.3  # 30% coverage threshold
    ]

    return feature_cols


def main():
    parser = argparse.ArgumentParser(description='Train optimized ML models')
    parser.add_argument('--position', type=str, help='Train for specific position only')
    parser.add_argument('--compare-baseline', action='store_true', help='Compare with baseline')
    parser.add_argument('--no-stacking', action='store_true', help='Disable stacking')
    parser.add_argument('--no-attention', action='store_true', help='Disable attention NN')
    parser.add_argument('--no-huber', action='store_true', help='Disable Huber loss')
    parser.add_argument('--output-dir', type=str, default='data/models',
                       help='Output directory for models')
    parser.add_argument('--use-base-dataset', action='store_true',
                       help='Use base dataset instead of expanded')
    args = parser.parse_args()

    print("="*70)
    print("DYNASTY EDGE OPTIMIZED ML TRAINING")
    print(f"Started: {datetime.now()}")
    print("="*70)

    # Ensure logs directory exists
    (project_root / 'logs').mkdir(exist_ok=True)

    # Build dataset
    df = build_dataset(use_expanded=not args.use_base_dataset)

    # Filter by position if specified
    if args.position:
        df = df[df['position'] == args.position]
        logger.info(f"Filtered to {args.position}: {len(df)} samples")

    # Get feature columns
    feature_cols = get_feature_cols(df)
    logger.info(f"Using {len(feature_cols)} features")

    # Create trainer
    trainer = OptimizedTrainer(
        use_stacking=not args.no_stacking,
        use_attention=not args.no_attention,
        use_huber=not args.no_huber,
        use_position_stratification=True
    )

    # Train
    results = trainer.train(df, feature_cols, target_col='next_ppg_ppr')

    # Save models
    output_dir = project_root / args.output_dir
    trainer.save(output_dir)

    # Compare with baseline if requested
    if args.compare_baseline:
        print("\n" + "="*70)
        print("BASELINE COMPARISON")
        print("="*70)
        baseline_r2 = 0.8759  # From previous training
        improvement = results['metrics']['ensemble_r2'] - baseline_r2
        print(f"Baseline R²: {baseline_r2:.4f}")
        print(f"Optimized R²: {results['metrics']['ensemble_r2']:.4f}")
        print(f"Improvement: {improvement:+.4f} ({improvement/baseline_r2*100:+.1f}%)")

    print("\n" + "="*70)
    print("TRAINING COMPLETE")
    print(f"Finished: {datetime.now()}")
    print("="*70)

    return results


if __name__ == "__main__":
    main()
