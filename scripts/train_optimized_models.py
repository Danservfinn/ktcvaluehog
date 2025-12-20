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

try:
    import xgboost as xgb
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False
    print("XGBoost not available")

try:
    import catboost as cb
    HAS_CATBOOST = True
except ImportError:
    HAS_CATBOOST = False
    print("CatBoost not available")

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

# Phase 1.3: QB-specific feature subset (30 features optimized for QB prediction)
QB_FEATURES = [
    # Core passing (primary fantasy value)
    'passing_yards', 'passing_tds', 'interceptions', 'cpoe',
    'avg_time_to_throw', 'adot', 'completions', 'attempts',
    'completion_pct', 'yards_per_attempt',

    # Rushing (critical for dual-threat QBs)
    'rushing_yards', 'rushing_tds', 'carries', 'yards_per_carry',

    # Derived metrics (if available)
    'int_rate', 'td_rate', 'sack_rate',

    # Context features
    'team_elo_above_avg', 'team_ppg', 'team_off_rank',
    'avg_game_total', 'team_pass_rate',

    # Career features
    'years_exp', 'draft_round', 'draft_capital', 'age_score',
    'age', 'games', 'games_started',

    # PPG history
    'ppg_ppr', 'ppg_ppr_zscore', 'ppg_ppr_percentile'
]


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
        use_log_target: bool = False,  # Phase 1.1: Log-transform option
        use_xgboost: bool = True,  # Phase 3.1: XGBoost
        use_catboost: bool = True,  # Phase 3.2: CatBoost
        use_gbm_stacking: bool = False,  # Phase 3.3: Gradient-boosted meta-model
        use_temporal_cv: bool = False,  # Phase 3.4: Temporal cross-validation
        n_folds: int = 5
    ):
        self.device = self._get_device(device)
        self.use_stacking = use_stacking
        self.use_attention = use_attention
        self.use_huber = use_huber
        self.use_position_stratification = use_position_stratification
        self.use_log_target = use_log_target
        self.use_xgboost = use_xgboost and HAS_XGBOOST
        self.use_catboost = use_catboost and HAS_CATBOOST
        self.use_gbm_stacking = use_gbm_stacking
        self.use_temporal_cv = use_temporal_cv
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
        logger.info(f"Log Target: {self.use_log_target}, XGBoost: {self.use_xgboost}, CatBoost: {self.use_catboost}")
        logger.info(f"GBM Stacking: {self.use_gbm_stacking}, Temporal CV: {self.use_temporal_cv}")
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

        # Phase 1.1: Target variable with optional log-transform
        y_train_raw = df_train[target_col].fillna(0).values
        y_test_raw = df_test[target_col].fillna(0).values

        if self.use_log_target:
            # Log-transform to reduce outlier impact (Mahomes 30 PPG vs backup 5 PPG)
            y_train = np.log1p(y_train_raw)
            y_test = np.log1p(y_test_raw)
            logger.info("Using log1p-transformed target variable")
        else:
            y_train = y_train_raw
            y_test = y_test_raw

        self._y_test_raw = y_test_raw  # Always store raw values for evaluation

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

        # Phase 3.1: XGBoost (if enabled)
        if self.use_xgboost:
            xgb_model = xgb.XGBRegressor(
                n_estimators=500, max_depth=6, learning_rate=0.03,
                subsample=0.8, colsample_bytree=0.8,
                reg_alpha=0.05, reg_lambda=0.05,
                random_state=42, n_jobs=-1
            )
            xgb_model.fit(X_train_scaled, y_train, sample_weight=sample_weights)
            xgb_test_preds = xgb_model.predict(X_test_scaled)
            self.models['xgb'] = xgb_model
            xgb_r2 = r2_score(y_test, xgb_test_preds)
            logger.info(f"  XGBoost Test R²: {xgb_r2:.4f}")
        else:
            xgb_test_preds = None

        # Phase 3.2: CatBoost (if enabled)
        if self.use_catboost:
            cat_model = cb.CatBoostRegressor(
                iterations=500, depth=6, learning_rate=0.03,
                l2_leaf_reg=5, random_seed=42,
                verbose=0, thread_count=-1
            )
            cat_model.fit(X_train_scaled, y_train, sample_weight=sample_weights)
            cat_test_preds = cat_model.predict(X_test_scaled)
            self.models['cat'] = cat_model
            cat_r2 = r2_score(y_test, cat_test_preds)
            logger.info(f"  CatBoost Test R²: {cat_r2:.4f}")
        else:
            cat_test_preds = None

        # Stacking or fixed weights
        if self.use_stacking:
            logger.info("\n--- Training Stacking Meta-Model ---")
            ensemble_preds, meta_model = self._train_stacking_ensemble(
                X_train_scaled, y_train, X_test_scaled,
                pos_train, pos_test,
                nn_test_preds, gbm_test_preds, rf_test_preds, ridge_test_preds,
                xgb_test_preds, cat_test_preds
            )
            self.meta_model = meta_model
        else:
            # Fixed weight averaging (adjust weights based on available models)
            if self.use_xgboost and self.use_catboost:
                ensemble_preds = (
                    0.20 * nn_test_preds +
                    0.25 * gbm_test_preds +
                    0.15 * rf_test_preds +
                    0.10 * ridge_test_preds +
                    0.15 * xgb_test_preds +
                    0.15 * cat_test_preds
                )
            elif self.use_xgboost:
                ensemble_preds = (
                    0.25 * nn_test_preds +
                    0.30 * gbm_test_preds +
                    0.15 * rf_test_preds +
                    0.10 * ridge_test_preds +
                    0.20 * xgb_test_preds
                )
            elif self.use_catboost:
                ensemble_preds = (
                    0.25 * nn_test_preds +
                    0.30 * gbm_test_preds +
                    0.15 * rf_test_preds +
                    0.10 * ridge_test_preds +
                    0.20 * cat_test_preds
                )
            else:
                ensemble_preds = (
                    0.3 * nn_test_preds +
                    0.35 * gbm_test_preds +
                    0.2 * rf_test_preds +
                    0.15 * ridge_test_preds
                )

        # Inverse log-transform predictions for evaluation on original PPG scale
        if self.use_log_target:
            ensemble_preds_original = np.expm1(ensemble_preds)  # exp(x) - 1
            y_test_original = self._y_test_raw
        else:
            ensemble_preds_original = ensemble_preds
            y_test_original = y_test

        # Calculate final metrics on original scale
        ensemble_r2 = r2_score(y_test_original, ensemble_preds_original)
        ensemble_rmse = np.sqrt(mean_squared_error(y_test_original, ensemble_preds_original))
        ensemble_mae = mean_absolute_error(y_test_original, ensemble_preds_original)

        logger.info("\n" + "="*70)
        logger.info("FINAL RESULTS")
        logger.info("="*70)
        logger.info(f"Ensemble R²: {ensemble_r2:.4f}")
        logger.info(f"RMSE: {ensemble_rmse:.2f} PPG")
        logger.info(f"MAE: {ensemble_mae:.2f} PPG")

        # Position-stratified evaluation (on original scale)
        if self.use_position_stratification:
            logger.info("\nPosition-Specific R² Scores:")
            for pos in ['QB', 'RB', 'WR', 'TE']:
                pos_mask = df_test['position'] == pos
                if pos_mask.sum() > 10:
                    pos_r2 = r2_score(y_test_original[pos_mask], ensemble_preds_original[pos_mask])
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
                'position_stratification': self.use_position_stratification,
                'log_target': self.use_log_target,
                'xgboost': self.use_xgboost,
                'catboost': self.use_catboost,
                'gbm_stacking': self.use_gbm_stacking,
                'temporal_cv': self.use_temporal_cv
            },
            'trained_at': datetime.now().isoformat()
        }

        # Add XGBoost and CatBoost R² if available
        if self.use_xgboost:
            self.metrics['xgb_r2'] = xgb_r2
        if self.use_catboost:
            self.metrics['cat_r2'] = cat_r2

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
        epochs: int = 150,  # Increased for deeper network
        patience: int = 20
    ):
        """Train neural network with optional attention and Huber loss."""
        logger.info(f"  Training {'Attention' if self.use_attention else 'Simple'} NN...")

        # Create model (with reproducible initialization)
        torch.manual_seed(42)
        if self.device.type == 'mps':
            torch.mps.manual_seed(42)
        input_dim = X_train.shape[1]
        if self.use_attention:
            model = FeatureAttentionNN(input_dim, n_positions=4)  # Default [256, 128, 64]
        else:
            model = SimpleFFN(input_dim, n_positions=4)
        model.to(self.device)

        # Loss function
        if self.use_huber:
            criterion = DynastyWeightedHuberLoss(delta=5.0, dynasty_weight=True)
        else:
            criterion = nn.MSELoss()

        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=0.02)  # Increased from 0.01

        # Phase 3.4: Learning rate warmup + cosine annealing
        warmup_epochs = max(1, epochs // 10)  # 10% warmup
        def lr_lambda(epoch):
            if epoch < warmup_epochs:
                return float(epoch + 1) / warmup_epochs  # Linear warmup
            else:
                # Cosine annealing after warmup
                progress = (epoch - warmup_epochs) / (epochs - warmup_epochs)
                return 0.5 * (1.0 + np.cos(np.pi * progress))

        scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)

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

            scheduler.step()  # LambdaLR scheduler (epoch-based)

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
        ridge_test_preds: np.ndarray,
        xgb_test_preds: np.ndarray = None,
        cat_test_preds: np.ndarray = None
    ):
        """Train stacking meta-model using OOF predictions."""
        n_samples = len(X_train)
        kfold = KFold(n_splits=self.n_folds, shuffle=True, random_state=42)

        # OOF predictions
        oof_nn = np.zeros(n_samples)
        oof_gbm = np.zeros(n_samples)
        oof_rf = np.zeros(n_samples)
        oof_ridge = np.zeros(n_samples)
        oof_xgb = np.zeros(n_samples) if self.use_xgboost else None
        oof_cat = np.zeros(n_samples) if self.use_catboost else None

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

            # XGBoost (if enabled)
            if self.use_xgboost:
                fold_xgb = xgb.XGBRegressor(
                    n_estimators=300, max_depth=6, learning_rate=0.05,
                    random_state=42+fold_idx, n_jobs=-1
                )
                fold_xgb.fit(X_fold_train, y_fold_train)
                oof_xgb[val_idx] = fold_xgb.predict(X_fold_val)

            # CatBoost (if enabled)
            if self.use_catboost:
                fold_cat = cb.CatBoostRegressor(
                    iterations=300, depth=6, learning_rate=0.05,
                    random_seed=42+fold_idx, verbose=0
                )
                fold_cat.fit(X_fold_train, y_fold_train)
                oof_cat[val_idx] = fold_cat.predict(X_fold_val)

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

        # Train meta-model (Phase 3.3: optional gradient-boosted stacking)
        # Build meta-features dynamically based on enabled models
        meta_feature_list = [oof_nn, oof_gbm, oof_rf, oof_ridge]
        test_feature_list = [nn_test_preds, gbm_test_preds, rf_test_preds, ridge_test_preds]
        feature_names = ['NN', 'GBM', 'RF', 'Ridge']

        if self.use_xgboost and oof_xgb is not None:
            meta_feature_list.append(oof_xgb)
            test_feature_list.append(xgb_test_preds)
            feature_names.append('XGB')

        if self.use_catboost and oof_cat is not None:
            meta_feature_list.append(oof_cat)
            test_feature_list.append(cat_test_preds)
            feature_names.append('CAT')

        meta_features = np.column_stack(meta_feature_list)

        if self.use_gbm_stacking:
            # Phase 3.3: Gradient-boosted meta-model for non-linear stacking
            if HAS_LIGHTGBM:
                meta_model = lgb.LGBMRegressor(
                    n_estimators=100, max_depth=3, learning_rate=0.1,
                    subsample=0.8, random_state=42, verbose=-1
                )
            else:
                meta_model = GradientBoostingRegressor(
                    n_estimators=100, max_depth=3, learning_rate=0.1,
                    random_state=42
                )
            meta_model.fit(meta_features, y_train)
            logger.info(f"  GBM meta-model trained with {len(feature_names)} base models")
        else:
            # Default: RidgeCV for linear stacking
            meta_model = RidgeCV(alphas=[0.01, 0.1, 0.5, 1.0, 5.0, 10.0], cv=5)
            meta_model.fit(meta_features, y_train)
            logger.info(f"  Meta-model alpha: {meta_model.alpha_:.4f}")
            coef_str = ", ".join([f"{name}={coef:.3f}" for name, coef in zip(feature_names, meta_model.coef_)])
            logger.info(f"  Coefficients: {coef_str}")

        # Generate test predictions
        test_meta_features = np.column_stack(test_feature_list)
        ensemble_preds = meta_model.predict(test_meta_features)

        return ensemble_preds, meta_model

    def temporal_cross_validation(
        self,
        df: pd.DataFrame,
        feature_cols: list,
        target_col: str = 'next_ppg_ppr'
    ) -> Dict[str, Any]:
        """
        Phase 3.4: Temporal cross-validation (walk-forward validation).

        Train on progressively more data:
        - Train 1999-2020, test 2021 → R²_1
        - Train 1999-2021, test 2022 → R²_2
        - Train 1999-2022, test 2023 → R²_3

        Returns mean and std of R² scores for confidence estimation.
        """
        logger.info("\n" + "="*70)
        logger.info("TEMPORAL CROSS-VALIDATION (Walk-Forward)")
        logger.info("="*70)

        test_years = [2021, 2022, 2023]
        cv_results = []

        for test_year in test_years:
            logger.info(f"\n--- Fold: Test on {test_year} ---")

            # Train on all years before test year
            train_mask = df['season'] < test_year
            test_mask = df['season'] == test_year

            df_train = df[train_mask]
            df_test = df[test_mask]

            if len(df_test) < 50:
                logger.warning(f"Skipping {test_year}: only {len(df_test)} test samples")
                continue

            logger.info(f"Train: {df_train['season'].min()}-{df_train['season'].max()} "
                       f"({len(df_train)} samples)")
            logger.info(f"Test: {test_year} ({len(df_test)} samples)")

            # Prepare data
            X_train = df_train[feature_cols].fillna(0).values
            X_test = df_test[feature_cols].fillna(0).values
            y_train = df_train[target_col].fillna(0).values
            y_test = df_test[target_col].fillna(0).values

            # Scale
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)

            # Train simple ensemble (faster for CV)
            if HAS_LIGHTGBM:
                model = lgb.LGBMRegressor(
                    n_estimators=500, learning_rate=0.03, max_depth=6,
                    random_state=42, verbose=-1
                )
            else:
                model = GradientBoostingRegressor(
                    n_estimators=300, learning_rate=0.03, max_depth=5,
                    random_state=42
                )

            model.fit(X_train_scaled, y_train)
            preds = model.predict(X_test_scaled)

            # Metrics
            r2 = r2_score(y_test, preds)
            rmse = np.sqrt(mean_squared_error(y_test, preds))

            logger.info(f"  R² = {r2:.4f}, RMSE = {rmse:.2f}")

            cv_results.append({
                'test_year': test_year,
                'r2': r2,
                'rmse': rmse,
                'train_size': len(df_train),
                'test_size': len(df_test)
            })

        # Summary statistics
        r2_scores = [r['r2'] for r in cv_results]
        rmse_scores = [r['rmse'] for r in cv_results]

        logger.info("\n" + "="*70)
        logger.info("TEMPORAL CV SUMMARY")
        logger.info("="*70)
        logger.info(f"Mean R²: {np.mean(r2_scores):.4f} ± {np.std(r2_scores):.4f}")
        logger.info(f"Mean RMSE: {np.mean(rmse_scores):.2f} ± {np.std(rmse_scores):.2f}")
        logger.info(f"R² Range: [{np.min(r2_scores):.4f}, {np.max(r2_scores):.4f}]")

        return {
            'folds': cv_results,
            'mean_r2': np.mean(r2_scores),
            'std_r2': np.std(r2_scores),
            'mean_rmse': np.mean(rmse_scores),
            'std_rmse': np.std(rmse_scores)
        }

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

        # Save XGBoost and CatBoost if available
        if 'xgb' in self.models:
            joblib.dump(self.models['xgb'], output_dir / 'optimized_xgb.pkl')
        if 'cat' in self.models:
            joblib.dump(self.models['cat'], output_dir / 'optimized_cat.pkl')

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


class PositionSpecificTrainer:
    """
    Train separate models for each position to improve position-specific R².

    Key insight: QB R² = 0.59 is unacceptable. Position-specific models can
    capture the unique predictive patterns for each position.
    """

    POSITION_FEATURE_WEIGHTS = {
        'QB': {
            'passing_yards': 2.0, 'passing_tds': 2.0, 'cpoe': 1.5,
            'avg_time_to_throw': 1.5, 'interceptions': 1.5,
            'rushing_yards': 1.2, 'rushing_tds': 1.2,
            'targets': 0.3, 'receptions': 0.3  # De-weight receiving
        },
        'RB': {
            'carries': 2.0, 'rushing_yards': 2.0, 'rushing_tds': 1.5,
            'snap_pct': 2.0, 'targets': 1.5, 'receptions': 1.5,
            'receiving_yards': 1.2,
            'passing_yards': 0.1  # De-weight passing
        },
        'WR': {
            'targets': 2.0, 'receptions': 2.0, 'receiving_yards': 2.0,
            'target_share': 2.0, 'avg_separation': 1.5, 'wopr': 1.5,
            'receiving_tds': 1.5,
            'passing_yards': 0.1, 'carries': 0.3
        },
        'TE': {
            'targets': 1.5, 'receptions': 1.5, 'receiving_yards': 1.5,
            'snap_pct': 1.5, 'receiving_tds': 1.5,
            'passing_yards': 0.1, 'carries': 0.3
        }
    }

    MIN_SAMPLES = {'QB': 80, 'RB': 150, 'WR': 200, 'TE': 100}

    def __init__(self, device: str = 'auto'):
        self.device = self._get_device(device)
        self.position_models = {}
        self.position_scalers = {}
        self.position_metrics = {}

    def _get_device(self, device: str) -> torch.device:
        if device == 'auto':
            if torch.cuda.is_available():
                return torch.device('cuda')
            elif torch.backends.mps.is_available():
                return torch.device('mps')
        return torch.device('cpu')

    def train_all_positions(
        self,
        df: pd.DataFrame,
        feature_cols: list,
        target_col: str = 'next_ppg_ppr',
        test_seasons: list = None
    ) -> Dict[str, Any]:
        """Train separate models for each position."""
        test_seasons = test_seasons or [2023]
        all_results = {}

        logger.info("="*70)
        logger.info("POSITION-SPECIFIC MODEL TRAINING")
        logger.info("="*70)

        for position in ['QB', 'RB', 'WR', 'TE']:
            pos_df = df[df['position'] == position].copy()

            if len(pos_df) < self.MIN_SAMPLES.get(position, 100):
                logger.warning(f"Skipping {position}: only {len(pos_df)} samples (min: {self.MIN_SAMPLES[position]})")
                continue

            logger.info(f"\n--- Training {position} Model ({len(pos_df)} samples) ---")

            # Train position-specific model
            result = self._train_position_model(
                pos_df, feature_cols, target_col, position, test_seasons
            )

            if result:
                all_results[position] = result
                self.position_models[position] = result['model']
                self.position_scalers[position] = result['scaler']
                self.position_metrics[position] = result['metrics']

        # Summary
        logger.info("\n" + "="*70)
        logger.info("POSITION-SPECIFIC RESULTS SUMMARY")
        logger.info("="*70)
        for pos, result in all_results.items():
            logger.info(f"  {pos}: R² = {result['metrics']['r2']:.4f}, "
                       f"RMSE = {result['metrics']['rmse']:.2f}")

        return all_results

    def _train_position_model(
        self,
        pos_df: pd.DataFrame,
        feature_cols: list,
        target_col: str,
        position: str,
        test_seasons: list
    ) -> Optional[Dict[str, Any]]:
        """Train a single position-specific model.

        Phase 1.4: Use Ridge regression for QB (small sample ~80) to prevent overfitting.
        Use LightGBM for other positions with more samples.
        """

        # Split data
        train_mask = ~pos_df['season'].isin(test_seasons)
        test_mask = pos_df['season'].isin(test_seasons)

        df_train = pos_df[train_mask]
        df_test = pos_df[test_mask]

        if len(df_test) < 10:
            logger.warning(f"  Insufficient test samples for {position}: {len(df_test)}")
            return None

        logger.info(f"  Train: {len(df_train)}, Test: {len(df_test)}")

        # Phase 1.3: Use QB-specific features for quarterbacks
        if position == 'QB':
            # Filter to QB-relevant features that exist in dataset
            qb_features = [f for f in QB_FEATURES if f in feature_cols]
            logger.info(f"  Using {len(qb_features)} QB-specific features (of {len(QB_FEATURES)} defined)")
            active_features = qb_features
        else:
            active_features = feature_cols

        # Prepare features
        X_train = df_train[active_features].fillna(0).values
        X_test = df_test[active_features].fillna(0).values

        # Target variable (raw values)
        y_train = df_train[target_col].fillna(0).values
        y_test_raw = df_test[target_col].fillna(0).values

        # Scale
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)

        # Phase 1.4: Use Ridge for QB (small sample size ~80), LightGBM for others
        if position == 'QB':
            logger.info(f"  Using Ridge regression for QB (strong regularization)")
            model = Ridge(alpha=10.0)  # High regularization to prevent overfitting
            model.fit(X_train_scaled, y_train)
        else:
            # Train LightGBM for positions with more samples
            if HAS_LIGHTGBM:
                model = lgb.LGBMRegressor(
                    n_estimators=500,
                    learning_rate=0.03,
                    max_depth=6,
                    num_leaves=31,
                    subsample=0.8,
                    colsample_bytree=0.8,
                    reg_alpha=0.1,
                    reg_lambda=0.1,
                    random_state=42,
                    verbose=-1
                )
            else:
                model = GradientBoostingRegressor(
                    n_estimators=300,
                    learning_rate=0.03,
                    max_depth=5,
                    random_state=42
                )
            model.fit(X_train_scaled, y_train)

        # Predict and evaluate
        preds = model.predict(X_test_scaled)

        r2 = r2_score(y_test_raw, preds)
        rmse = np.sqrt(mean_squared_error(y_test_raw, preds))
        mae = mean_absolute_error(y_test_raw, preds)

        logger.info(f"  {position} R²: {r2:.4f}, RMSE: {rmse:.2f}, MAE: {mae:.2f}")

        return {
            'model': model,
            'scaler': scaler,
            'metrics': {'r2': r2, 'rmse': rmse, 'mae': mae},
            'predictions': preds,
            'actual': y_test_raw
        }

    def save(self, output_dir: Path):
        """Save all position-specific models."""
        output_dir = Path(output_dir) / 'position_models'
        output_dir.mkdir(parents=True, exist_ok=True)

        for position in self.position_models:
            joblib.dump(self.position_models[position],
                       output_dir / f'{position.lower()}_model.pkl')
            joblib.dump(self.position_scalers[position],
                       output_dir / f'{position.lower()}_scaler.pkl')

        # Save metrics
        with open(output_dir / 'position_metrics.json', 'w') as f:
            json.dump(self.position_metrics, f, indent=2, default=str)

        logger.info(f"Position models saved to {output_dir}")


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


def get_feature_cols(df: pd.DataFrame, min_coverage: float = 0.30) -> list:
    """Get valid feature columns (exclude targets and identifiers).

    Args:
        df: DataFrame with features
        min_coverage: Minimum non-null coverage required (default 30%)
                     Note: Lower to 20% to include defense/coaching features
                     from 2020+ data once more historical data is available.
    """
    exclude_cols = ['player_id', 'player_name', 'position', 'season', 'team']
    leakage_cols = ['ppg_change', 'ppg_change_pct']

    feature_cols = [
        c for c in df.columns
        if c not in exclude_cols
        and c not in leakage_cols
        and not c.startswith('next_')
        and df[c].dtype in ['int64', 'float64', 'bool', 'uint8']
        and df[c].notna().sum() > len(df) * min_coverage
    ]

    return feature_cols


def main():
    parser = argparse.ArgumentParser(description='Train optimized ML models')
    parser.add_argument('--position', type=str, help='Train for specific position only')
    parser.add_argument('--position-specific', action='store_true',
                       help='Train separate models for each position (improves QB R²)')
    parser.add_argument('--compare-baseline', action='store_true', help='Compare with baseline')
    parser.add_argument('--no-stacking', action='store_true', help='Disable stacking')
    parser.add_argument('--no-attention', action='store_true', help='Disable attention NN')
    parser.add_argument('--no-huber', action='store_true', help='Disable Huber loss')
    parser.add_argument('--output-dir', type=str, default='data/models',
                       help='Output directory for models')
    parser.add_argument('--use-base-dataset', action='store_true',
                       help='Use base dataset instead of expanded')

    # Phase 1 & 3 arguments
    parser.add_argument('--log-target', action='store_true',
                       help='Phase 1.1: Use log-transform on target variable')
    parser.add_argument('--no-xgboost', action='store_true',
                       help='Phase 3.1: Disable XGBoost')
    parser.add_argument('--no-catboost', action='store_true',
                       help='Phase 3.2: Disable CatBoost')
    parser.add_argument('--gbm-stacking', action='store_true',
                       help='Phase 3.3: Use gradient-boosted meta-model instead of Ridge')
    parser.add_argument('--temporal-cv', action='store_true',
                       help='Phase 3.4: Use temporal cross-validation')

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

    output_dir = project_root / args.output_dir

    # Train position-specific models if requested
    if args.position_specific:
        logger.info("\n*** POSITION-SPECIFIC TRAINING MODE ***")
        pos_trainer = PositionSpecificTrainer()
        pos_results = pos_trainer.train_all_positions(df, feature_cols, target_col='next_ppg_ppr')
        pos_trainer.save(output_dir)

    # Create and train main ensemble trainer with Phase 1 & 3 enhancements
    trainer = OptimizedTrainer(
        use_stacking=not args.no_stacking,
        use_attention=not args.no_attention,
        use_huber=not args.no_huber,
        use_position_stratification=True,
        use_log_target=args.log_target,
        use_xgboost=not args.no_xgboost,
        use_catboost=not args.no_catboost,
        use_gbm_stacking=args.gbm_stacking,
        use_temporal_cv=args.temporal_cv
    )

    # Phase 3.4: Temporal cross-validation (if enabled)
    if args.temporal_cv:
        cv_results = trainer.temporal_cross_validation(df, feature_cols, target_col='next_ppg_ppr')

    # Train
    results = trainer.train(df, feature_cols, target_col='next_ppg_ppr')

    # Save models
    trainer.save(output_dir)

    # Save temporal CV results if available
    if args.temporal_cv:
        with open(output_dir / 'temporal_cv_results.json', 'w') as f:
            json.dump(cv_results, f, indent=2, default=str)

    # Compare with baseline if requested
    if args.compare_baseline:
        print("\n" + "="*70)
        print("BASELINE COMPARISON")
        print("="*70)
        baseline_r2 = 0.8015  # Temporal split baseline (train <2023, test 2023)
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
