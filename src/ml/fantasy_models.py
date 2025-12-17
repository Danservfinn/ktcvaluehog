"""
Fantasy Football ML Models
===========================
Machine learning models for predicting fantasy football production.

Models:
1. SeasonProjectionModel - Predict next year's PPG from current stats
2. BreakoutClassifier - Predict breakout probability (50%+ PPG increase)
3. WeeklyPredictor - Predict weekly fantasy points

Uses Gradient Boosting (XGBoost/LightGBM/sklearn) for best tabular data performance.
"""

import logging
import pickle
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import (
    mean_squared_error, mean_absolute_error, r2_score,
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, classification_report
)
from sklearn.ensemble import GradientBoostingRegressor, GradientBoostingClassifier
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier

# Try to import XGBoost/LightGBM for better performance
try:
    import xgboost as xgb
    # Test if XGBoost actually works (OpenMP dependency)
    _test = xgb.XGBRegressor()
    XGBOOST_AVAILABLE = True
except (ImportError, Exception):
    XGBOOST_AVAILABLE = False

try:
    import lightgbm as lgb
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False

logger = logging.getLogger(__name__)


class SeasonProjectionModel:
    """
    Predict next season's fantasy PPG from current season stats.

    Features:
    - Current season stats (PPG, targets, carries, yards, TDs)
    - Career context (years in league, career avg, best season)
    - Position
    - Efficiency metrics (catch rate, yards per carry, etc.)

    Target:
    - next_ppg_ppr: PPR points per game in following season
    """

    # Features to use for prediction
    NUMERIC_FEATURES = [
        # Core stats
        'ppg_ppr', 'ppg_std', 'games',
        'passing_yards', 'passing_tds', 'interceptions',
        'rushing_yards', 'rushing_tds', 'carries',
        'targets', 'receptions', 'receiving_yards', 'receiving_tds',
        # Career context
        'years_in_league', 'career_ppg', 'best_season_ppg',
        # Per-game rates
        'targets_per_game', 'receptions_per_game', 'rec_yards_per_game',
        'carries_per_game', 'rush_yards_per_game',
        # Efficiency
        'catch_rate', 'yards_per_catch', 'yards_per_carry',
        'ppg_vs_career_avg', 'ppg_vs_best',
        'rec_td_rate', 'rush_td_rate',
        # Team share features
        'target_share_calc', 'carry_share', 'opportunity_share',
        'rec_yards_share', 'rush_yards_share',
        # Age curve features
        'estimated_age', 'years_to_peak', 'years_from_cliff',
        'in_prime_window', 'age_decline_risk', 'age_score',
        # Surge detection features
        'first_half_ppg', 'second_half_ppg', 'ppg_surge', 'ppg_surge_pct',
        'target_surge', 'is_surging', 'is_fading', 'hot_finish'
    ]

    CATEGORICAL_FEATURES = ['position']
    TARGET = 'next_ppg_ppr'

    def __init__(self, model_type: str = 'auto'):
        """
        Initialize the model.

        Args:
            model_type: 'xgboost', 'lightgbm', 'sklearn', or 'auto'
        """
        self.model_type = self._select_model_type(model_type)
        self.model = None
        self.scaler = StandardScaler()
        self.label_encoders = {}
        self.feature_columns = []
        self.is_fitted = False
        self.metrics = {}

    def _select_model_type(self, model_type: str) -> str:
        """Select best available model type."""
        if model_type == 'auto':
            if XGBOOST_AVAILABLE:
                return 'xgboost'
            elif LIGHTGBM_AVAILABLE:
                return 'lightgbm'
            else:
                return 'sklearn'
        return model_type

    def _create_model(self):
        """Create the underlying ML model with regularization to prevent overfitting."""
        if self.model_type == 'xgboost' and XGBOOST_AVAILABLE:
            return xgb.XGBRegressor(
                n_estimators=100,
                max_depth=3,
                learning_rate=0.05,
                subsample=0.7,
                colsample_bytree=0.8,
                min_child_weight=20,
                random_state=42,
                n_jobs=-1
            )
        elif self.model_type == 'lightgbm' and LIGHTGBM_AVAILABLE:
            return lgb.LGBMRegressor(
                n_estimators=100,
                max_depth=3,
                learning_rate=0.05,
                subsample=0.7,
                colsample_bytree=0.8,
                min_child_samples=20,
                random_state=42,
                n_jobs=-1,
                verbose=-1
            )
        else:
            return GradientBoostingRegressor(
                n_estimators=100,
                max_depth=3,
                learning_rate=0.05,
                subsample=0.7,
                min_samples_split=20,
                random_state=42
            )

    def _prepare_features(self, df: pd.DataFrame, fit: bool = False) -> np.ndarray:
        """Prepare features for model input."""
        # Select numeric features that exist
        available_numeric = [f for f in self.NUMERIC_FEATURES if f in df.columns]

        # Handle numeric features
        X_numeric = df[available_numeric].copy()
        X_numeric = X_numeric.fillna(0)

        if fit:
            X_numeric_scaled = self.scaler.fit_transform(X_numeric)
            self.feature_columns = available_numeric.copy()
        else:
            X_numeric_scaled = self.scaler.transform(X_numeric)

        # Handle categorical features
        X_cat_list = []
        for cat_col in self.CATEGORICAL_FEATURES:
            if cat_col in df.columns:
                if fit:
                    le = LabelEncoder()
                    encoded = le.fit_transform(df[cat_col].fillna('UNKNOWN'))
                    self.label_encoders[cat_col] = le
                else:
                    le = self.label_encoders.get(cat_col)
                    if le:
                        # Handle unseen categories
                        values = df[cat_col].fillna('UNKNOWN')
                        encoded = np.array([
                            le.transform([v])[0] if v in le.classes_ else -1
                            for v in values
                        ])
                    else:
                        encoded = np.zeros(len(df))

                X_cat_list.append(encoded.reshape(-1, 1))
                if fit:
                    self.feature_columns.append(cat_col)

        # Combine features
        if X_cat_list:
            X_cat = np.hstack(X_cat_list)
            X = np.hstack([X_numeric_scaled, X_cat])
        else:
            X = X_numeric_scaled

        return X

    def fit(self, df: pd.DataFrame, verbose: bool = True) -> Dict[str, float]:
        """
        Train the model on historical data.

        Args:
            df: Training DataFrame with features and target
            verbose: Print training progress

        Returns:
            Dictionary of training metrics
        """
        if self.TARGET not in df.columns:
            raise ValueError(f"Target column '{self.TARGET}' not found in DataFrame")

        # Remove rows with missing target
        df_clean = df.dropna(subset=[self.TARGET])

        if verbose:
            logger.info(f"Training on {len(df_clean):,} samples")
            logger.info(f"Model type: {self.model_type}")

        # Prepare features
        X = self._prepare_features(df_clean, fit=True)
        y = df_clean[self.TARGET].values

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        # Create and train model
        self.model = self._create_model()
        self.model.fit(X_train, y_train)

        # Evaluate
        y_pred_train = self.model.predict(X_train)
        y_pred_test = self.model.predict(X_test)

        self.metrics = {
            'train_rmse': np.sqrt(mean_squared_error(y_train, y_pred_train)),
            'test_rmse': np.sqrt(mean_squared_error(y_test, y_pred_test)),
            'train_mae': mean_absolute_error(y_train, y_pred_train),
            'test_mae': mean_absolute_error(y_test, y_pred_test),
            'train_r2': r2_score(y_train, y_pred_train),
            'test_r2': r2_score(y_test, y_pred_test),
            'n_train': len(y_train),
            'n_test': len(y_test),
            'n_features': X.shape[1]
        }

        # Cross-validation
        cv_scores = cross_val_score(self.model, X, y, cv=5, scoring='r2')
        self.metrics['cv_r2_mean'] = cv_scores.mean()
        self.metrics['cv_r2_std'] = cv_scores.std()

        self.is_fitted = True

        if verbose:
            logger.info(f"Training R²: {self.metrics['train_r2']:.3f}")
            logger.info(f"Test R²: {self.metrics['test_r2']:.3f}")
            logger.info(f"Test RMSE: {self.metrics['test_rmse']:.2f} PPG")
            logger.info(f"Test MAE: {self.metrics['test_mae']:.2f} PPG")
            logger.info(f"CV R² (5-fold): {self.metrics['cv_r2_mean']:.3f} ± {self.metrics['cv_r2_std']:.3f}")

        return self.metrics

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        """Predict next season PPG for given players."""
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")

        X = self._prepare_features(df, fit=False)
        return self.model.predict(X)

    def get_feature_importance(self) -> pd.DataFrame:
        """Get feature importance scores."""
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")

        if hasattr(self.model, 'feature_importances_'):
            importance = self.model.feature_importances_
        else:
            importance = np.zeros(len(self.feature_columns))

        return pd.DataFrame({
            'feature': self.feature_columns,
            'importance': importance
        }).sort_values('importance', ascending=False)

    def save(self, filepath: str):
        """Save model to file."""
        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'label_encoders': self.label_encoders,
            'feature_columns': self.feature_columns,
            'metrics': self.metrics,
            'model_type': self.model_type,
            'saved_at': datetime.now().isoformat()
        }
        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)
        logger.info(f"Model saved to {filepath}")

    @classmethod
    def load(cls, filepath: str) -> 'SeasonProjectionModel':
        """Load model from file."""
        with open(filepath, 'rb') as f:
            model_data = pickle.load(f)

        instance = cls(model_type=model_data['model_type'])
        instance.model = model_data['model']
        instance.scaler = model_data['scaler']
        instance.label_encoders = model_data['label_encoders']
        instance.feature_columns = model_data['feature_columns']
        instance.metrics = model_data['metrics']
        instance.is_fitted = True

        logger.info(f"Model loaded from {filepath}")
        return instance


class BreakoutClassifier:
    """
    Classify players likely to break out (50%+ PPG increase).

    Binary classification: breakout (1) vs no breakout (0)
    """

    NUMERIC_FEATURES = [
        'ppg_ppr', 'games', 'years_in_league',
        'targets', 'receptions', 'receiving_yards',
        'carries', 'rushing_yards',
        'targets_per_game', 'carries_per_game',
        'catch_rate', 'yards_per_catch', 'yards_per_carry',
        'career_ppg', 'best_season_ppg', 'ppg_vs_career_avg'
    ]

    CATEGORICAL_FEATURES = ['position']
    TARGET = 'is_breakout'

    def __init__(self, model_type: str = 'auto'):
        self.model_type = self._select_model_type(model_type)
        self.model = None
        self.scaler = StandardScaler()
        self.label_encoders = {}
        self.feature_columns = []
        self.is_fitted = False
        self.metrics = {}

    def _select_model_type(self, model_type: str) -> str:
        if model_type == 'auto':
            if XGBOOST_AVAILABLE:
                return 'xgboost'
            elif LIGHTGBM_AVAILABLE:
                return 'lightgbm'
            else:
                return 'sklearn'
        return model_type

    def _create_model(self):
        if self.model_type == 'xgboost' and XGBOOST_AVAILABLE:
            return xgb.XGBClassifier(
                n_estimators=200,
                max_depth=5,
                learning_rate=0.1,
                scale_pos_weight=5,  # Handle class imbalance
                random_state=42,
                n_jobs=-1
            )
        elif self.model_type == 'lightgbm' and LIGHTGBM_AVAILABLE:
            return lgb.LGBMClassifier(
                n_estimators=200,
                max_depth=5,
                learning_rate=0.1,
                class_weight='balanced',
                random_state=42,
                n_jobs=-1,
                verbose=-1
            )
        else:
            return GradientBoostingClassifier(
                n_estimators=200,
                max_depth=5,
                learning_rate=0.1,
                random_state=42
            )

    def _prepare_features(self, df: pd.DataFrame, fit: bool = False) -> np.ndarray:
        available_numeric = [f for f in self.NUMERIC_FEATURES if f in df.columns]

        X_numeric = df[available_numeric].copy()
        X_numeric = X_numeric.fillna(0)

        if fit:
            X_numeric_scaled = self.scaler.fit_transform(X_numeric)
            self.feature_columns = available_numeric.copy()
        else:
            X_numeric_scaled = self.scaler.transform(X_numeric)

        X_cat_list = []
        for cat_col in self.CATEGORICAL_FEATURES:
            if cat_col in df.columns:
                if fit:
                    le = LabelEncoder()
                    encoded = le.fit_transform(df[cat_col].fillna('UNKNOWN'))
                    self.label_encoders[cat_col] = le
                else:
                    le = self.label_encoders.get(cat_col)
                    if le:
                        values = df[cat_col].fillna('UNKNOWN')
                        encoded = np.array([
                            le.transform([v])[0] if v in le.classes_ else -1
                            for v in values
                        ])
                    else:
                        encoded = np.zeros(len(df))

                X_cat_list.append(encoded.reshape(-1, 1))
                if fit:
                    self.feature_columns.append(cat_col)

        if X_cat_list:
            X_cat = np.hstack(X_cat_list)
            X = np.hstack([X_numeric_scaled, X_cat])
        else:
            X = X_numeric_scaled

        return X

    def fit(self, df: pd.DataFrame, verbose: bool = True) -> Dict[str, float]:
        if self.TARGET not in df.columns:
            raise ValueError(f"Target column '{self.TARGET}' not found")

        df_clean = df.dropna(subset=[self.TARGET])

        if verbose:
            breakout_rate = df_clean[self.TARGET].mean() * 100
            logger.info(f"Training on {len(df_clean):,} samples ({breakout_rate:.1f}% breakouts)")

        X = self._prepare_features(df_clean, fit=True)
        y = df_clean[self.TARGET].values

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        self.model = self._create_model()
        self.model.fit(X_train, y_train)

        y_pred_train = self.model.predict(X_train)
        y_pred_test = self.model.predict(X_test)
        y_prob_test = self.model.predict_proba(X_test)[:, 1]

        self.metrics = {
            'train_accuracy': accuracy_score(y_train, y_pred_train),
            'test_accuracy': accuracy_score(y_test, y_pred_test),
            'test_precision': precision_score(y_test, y_pred_test, zero_division=0),
            'test_recall': recall_score(y_test, y_pred_test, zero_division=0),
            'test_f1': f1_score(y_test, y_pred_test, zero_division=0),
            'test_auc': roc_auc_score(y_test, y_prob_test),
            'n_train': len(y_train),
            'n_test': len(y_test),
            'breakout_rate': y.mean()
        }

        self.is_fitted = True

        if verbose:
            logger.info(f"Test Accuracy: {self.metrics['test_accuracy']:.3f}")
            logger.info(f"Test AUC: {self.metrics['test_auc']:.3f}")
            logger.info(f"Test Precision: {self.metrics['test_precision']:.3f}")
            logger.info(f"Test Recall: {self.metrics['test_recall']:.3f}")

        return self.metrics

    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        """Predict breakout probability."""
        if not self.is_fitted:
            raise ValueError("Model not fitted")

        X = self._prepare_features(df, fit=False)
        return self.model.predict_proba(X)[:, 1]

    def save(self, filepath: str):
        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'label_encoders': self.label_encoders,
            'feature_columns': self.feature_columns,
            'metrics': self.metrics,
            'model_type': self.model_type,
            'saved_at': datetime.now().isoformat()
        }
        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)

    @classmethod
    def load(cls, filepath: str) -> 'BreakoutClassifier':
        with open(filepath, 'rb') as f:
            model_data = pickle.load(f)

        instance = cls(model_type=model_data['model_type'])
        instance.model = model_data['model']
        instance.scaler = model_data['scaler']
        instance.label_encoders = model_data['label_encoders']
        instance.feature_columns = model_data['feature_columns']
        instance.metrics = model_data['metrics']
        instance.is_fitted = True

        return instance


def train_all_models(
    data_dir: str = 'data/ml_training',
    output_dir: str = 'models'
) -> Dict[str, Any]:
    """
    Train all fantasy ML models.

    Returns:
        Dictionary with trained models and their metrics
    """
    data_path = Path(data_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    results = {}

    # 1. Season Projection Model
    logger.info("=" * 60)
    logger.info("Training Season Projection Model")
    logger.info("=" * 60)

    season_df = pd.read_parquet(data_path / 'season_projection.parquet')

    season_model = SeasonProjectionModel(model_type='auto')
    season_metrics = season_model.fit(season_df)
    season_model.save(str(output_path / 'season_projection_model.pkl'))

    results['season_projection'] = {
        'model': season_model,
        'metrics': season_metrics,
        'feature_importance': season_model.get_feature_importance()
    }

    # 2. Breakout Classifier
    logger.info("\n" + "=" * 60)
    logger.info("Training Breakout Classifier")
    logger.info("=" * 60)

    breakout_df = pd.read_parquet(data_path / 'breakout_probability.parquet')

    breakout_model = BreakoutClassifier(model_type='auto')
    breakout_metrics = breakout_model.fit(breakout_df)
    breakout_model.save(str(output_path / 'breakout_classifier.pkl'))

    results['breakout_classifier'] = {
        'model': breakout_model,
        'metrics': breakout_metrics
    }

    logger.info("\n" + "=" * 60)
    logger.info("All models trained successfully!")
    logger.info("=" * 60)

    return results
