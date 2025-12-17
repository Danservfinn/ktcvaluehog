#!/usr/bin/env python3
"""
KTC Value Prediction Pipeline

Predicts future KTC value changes using historical snapshots and NFL performance data.

REQUIREMENTS:
- Minimum 30 daily KTC snapshots (4-6 weeks of data collection)
- NFL performance data from nflverse
- Run: python pipelines/ktc_prediction_pipeline.py

TIMELINE:
- Start collecting: Now (archive_ktc_snapshot.py runs daily)
- Ready for training: ~January 2025 (after 30+ snapshots)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, List

# Paths
DATA_DIR = Path(__file__).parent.parent / "data"
HISTORICAL_DIR = DATA_DIR / "historical" / "ktc_snapshots"
FEATURES_DIR = DATA_DIR / "features"
MODELS_DIR = DATA_DIR / "models"


# =============================================================================
# FEATURE ENGINEERING
# =============================================================================

class KTCFeatureEngineer:
    """Generate features for KTC prediction from historical snapshots."""

    def __init__(self, lookback_days: int = 14):
        self.lookback_days = lookback_days

    def load_snapshots(self) -> pd.DataFrame:
        """Load consolidated historical KTC data."""
        consolidated = HISTORICAL_DIR / "ktc_all_snapshots.csv"
        if not consolidated.exists():
            raise FileNotFoundError(
                f"No historical data found. Need {consolidated}\n"
                "Run scripts/archive_ktc_snapshot.py daily to collect data."
            )

        df = pd.read_csv(consolidated)
        df['snapshot_date'] = pd.to_datetime(df['snapshot_date'], format='%Y%m%d')
        return df.sort_values(['player_id', 'snapshot_date'])

    def calculate_value_changes(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate value changes over time windows."""
        df = df.copy()

        # Sort by player and date
        df = df.sort_values(['player_id', 'snapshot_date'])

        # Calculate changes for each player
        for days in [1, 3, 7, 14]:
            df[f'value_change_{days}d'] = df.groupby('player_id')['sf_value'].diff(days)
            df[f'value_pct_change_{days}d'] = df.groupby('player_id')['sf_value'].pct_change(days) * 100

        # Future target: value change in next 7 days
        df['target_value_7d'] = df.groupby('player_id')['sf_value'].shift(-7) - df['sf_value']
        df['target_pct_7d'] = (df.groupby('player_id')['sf_value'].shift(-7) / df['sf_value'] - 1) * 100

        return df

    def add_momentum_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add momentum and trend features."""
        df = df.copy()

        # Rolling statistics
        for window in [3, 7, 14]:
            df[f'value_ma_{window}d'] = df.groupby('player_id')['sf_value'].transform(
                lambda x: x.rolling(window, min_periods=1).mean()
            )
            df[f'value_std_{window}d'] = df.groupby('player_id')['sf_value'].transform(
                lambda x: x.rolling(window, min_periods=1).std()
            )

        # Trend direction (positive days / total days)
        df['trend_direction_7d'] = df.groupby('player_id')['value_change_1d'].transform(
            lambda x: x.rolling(7, min_periods=1).apply(lambda y: (y > 0).sum() / len(y))
        )

        # Value relative to moving average
        df['value_vs_ma7'] = df['sf_value'] / df['value_ma_7d'] - 1

        return df

    def add_position_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add position-relative features."""
        df = df.copy()

        # Rank within position on each day
        df['pos_rank_daily'] = df.groupby(['snapshot_date', 'position'])['sf_value'].rank(
            ascending=False, method='dense'
        )

        # Position average value
        df['pos_avg_value'] = df.groupby(['snapshot_date', 'position'])['sf_value'].transform('mean')
        df['value_vs_pos_avg'] = df['sf_value'] / df['pos_avg_value'] - 1

        return df

    def add_age_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add age-based features."""
        df = df.copy()

        # Age buckets
        df['age_bucket'] = pd.cut(
            df['age'],
            bins=[0, 23, 26, 28, 30, 35, 50],
            labels=['rookie', 'rising', 'prime', 'declining', 'veteran', 'old']
        )

        # Position-specific age premium/discount
        age_peaks = {'QB': 28, 'RB': 24, 'WR': 26, 'TE': 27}
        df['years_from_peak'] = df.apply(
            lambda x: x['age'] - age_peaks.get(x['position'], 26), axis=1
        )

        return df

    def engineer_features(self) -> pd.DataFrame:
        """Run full feature engineering pipeline."""
        print("Loading historical snapshots...")
        df = self.load_snapshots()

        snapshot_count = df['snapshot_date'].nunique()
        print(f"Found {snapshot_count} snapshots")

        if snapshot_count < 14:
            print(f"WARNING: Only {snapshot_count} snapshots. Need 14+ for reliable features.")
            print("Continue collecting daily snapshots.")

        print("Calculating value changes...")
        df = self.calculate_value_changes(df)

        print("Adding momentum features...")
        df = self.add_momentum_features(df)

        print("Adding position features...")
        df = self.add_position_features(df)

        print("Adding age features...")
        df = self.add_age_features(df)

        return df


# =============================================================================
# MODEL TRAINING
# =============================================================================

class KTCPredictor:
    """Train and evaluate KTC prediction models."""

    def __init__(self):
        self.model = None
        self.feature_cols = []

    def prepare_training_data(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """Prepare features and target for training."""

        # Feature columns
        self.feature_cols = [
            # Value momentum
            'value_change_1d', 'value_change_3d', 'value_change_7d',
            'value_pct_change_7d',
            'value_vs_ma7', 'trend_direction_7d',
            'value_std_7d',

            # Position context
            'pos_rank_daily', 'value_vs_pos_avg',

            # Age
            'age', 'years_from_peak',

            # Current value (normalized)
            'sf_value',
        ]

        # Filter to rows with valid target
        train_df = df.dropna(subset=['target_value_7d'] + self.feature_cols)

        X = train_df[self.feature_cols]
        y = train_df['target_value_7d']

        return X, y

    def train_gradient_boosting(self, X: pd.DataFrame, y: pd.Series):
        """Train gradient boosting model."""
        try:
            from sklearn.model_selection import train_test_split, cross_val_score
            from sklearn.ensemble import GradientBoostingRegressor
            from sklearn.metrics import mean_absolute_error, r2_score
        except ImportError:
            print("Install scikit-learn: pip install scikit-learn")
            return None

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        print(f"Training on {len(X_train)} samples, testing on {len(X_test)}...")

        # Train model
        self.model = GradientBoostingRegressor(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            random_state=42
        )
        self.model.fit(X_train, y_train)

        # Evaluate
        train_pred = self.model.predict(X_train)
        test_pred = self.model.predict(X_test)

        print("\n=== Model Performance ===")
        print(f"Train MAE: {mean_absolute_error(y_train, train_pred):.1f}")
        print(f"Test MAE:  {mean_absolute_error(y_test, test_pred):.1f}")
        print(f"Test R2:   {r2_score(y_test, test_pred):.3f}")

        # Feature importance
        print("\n=== Feature Importance ===")
        importance = pd.DataFrame({
            'feature': self.feature_cols,
            'importance': self.model.feature_importances_
        }).sort_values('importance', ascending=False)
        print(importance.to_string(index=False))

        return self.model

    def predict_value_changes(self, df: pd.DataFrame) -> pd.DataFrame:
        """Predict future value changes for current players."""
        if self.model is None:
            raise ValueError("Model not trained. Run train_gradient_boosting() first.")

        # Get latest snapshot
        latest_date = df['snapshot_date'].max()
        current = df[df['snapshot_date'] == latest_date].copy()

        # Predict
        X = current[self.feature_cols].fillna(0)
        current['predicted_change_7d'] = self.model.predict(X)
        current['predicted_pct_change'] = current['predicted_change_7d'] / current['sf_value'] * 100

        return current.sort_values('predicted_change_7d', ascending=False)


# =============================================================================
# MAIN PIPELINE
# =============================================================================

def check_data_readiness() -> Dict:
    """Check if enough data exists for training."""
    consolidated = HISTORICAL_DIR / "ktc_all_snapshots.csv"

    if not consolidated.exists():
        return {
            'ready': False,
            'snapshots': 0,
            'message': "No historical data. Run scripts/archive_ktc_snapshot.py daily."
        }

    df = pd.read_csv(consolidated)
    snapshot_count = df['snapshot_date'].nunique()

    return {
        'ready': snapshot_count >= 30,
        'snapshots': snapshot_count,
        'days_remaining': max(0, 30 - snapshot_count),
        'message': f"Have {snapshot_count}/30 required snapshots"
    }


def run_pipeline(force: bool = False):
    """Run the full prediction pipeline."""

    # Check readiness
    status = check_data_readiness()
    print(f"\n{'='*60}")
    print("KTC PREDICTION PIPELINE")
    print(f"{'='*60}")
    print(f"Status: {status['message']}")

    if not status['ready'] and not force:
        print(f"\nNot enough data for reliable predictions.")
        print(f"Continue collecting snapshots. {status['days_remaining']} more days needed.")
        print(f"\nTo force training anyway: run_pipeline(force=True)")
        return None

    # Feature engineering
    engineer = KTCFeatureEngineer()
    df = engineer.engineer_features()

    # Train model
    predictor = KTCPredictor()
    X, y = predictor.prepare_training_data(df)

    print(f"\nTraining data: {len(X)} samples")
    if len(X) < 100:
        print("WARNING: Very small training set. Results may be unreliable.")

    model = predictor.train_gradient_boosting(X, y)

    if model is None:
        return None

    # Generate predictions
    print("\n=== Top Predicted Risers (Next 7 Days) ===")
    predictions = predictor.predict_value_changes(df)
    risers = predictions.nlargest(10, 'predicted_change_7d')[
        ['name', 'position', 'age', 'sf_value', 'predicted_change_7d', 'predicted_pct_change']
    ]
    print(risers.to_string(index=False))

    print("\n=== Top Predicted Fallers (Next 7 Days) ===")
    fallers = predictions.nsmallest(10, 'predicted_change_7d')[
        ['name', 'position', 'age', 'sf_value', 'predicted_change_7d', 'predicted_pct_change']
    ]
    print(fallers.to_string(index=False))

    # Save predictions
    output_file = DATA_DIR / "predictions" / f"ktc_predictions_{datetime.now().strftime('%Y%m%d')}.csv"
    output_file.parent.mkdir(exist_ok=True)
    predictions.to_csv(output_file, index=False)
    print(f"\nPredictions saved to {output_file}")

    return predictions


if __name__ == "__main__":
    # Check status
    status = check_data_readiness()
    print(f"Data status: {status['message']}")

    if status['ready']:
        run_pipeline()
    else:
        print(f"\nCollect {status['days_remaining']} more daily snapshots before training.")
        print("The daily-refresh GitHub Action will archive snapshots automatically.")
