"""
Prediction and Signal Generation for Dynasty Edge
From: IMPLEMENTATION_PLAN_V2.md Phase 5
"""

import logging
from pathlib import Path
from typing import Optional, Dict, List, Any
from datetime import datetime

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# Check for H2O
try:
    import h2o
    H2O_AVAILABLE = True
except ImportError:
    H2O_AVAILABLE = False

# Check for sklearn
try:
    import joblib
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


class DynastyPredictor:
    """Generate dynasty value predictions and trading signals."""

    # Signal thresholds
    SIGNAL_THRESHOLDS = {
        'STRONG_BUY': -20,   # Model says worth 20%+ more than KTC
        'BUY': -10,          # Model says worth 10-20% more
        'HOLD': 10,          # Within +/- 10%
        'SELL': 20,          # Model says worth 10-20% less
        'STRONG_SELL': 100,  # Model says worth 20%+ less
    }

    def __init__(self, models_dir: Path = None):
        self.models_dir = Path(models_dir or 'data/models')
        self.model = None
        self.scaler = None
        self.feature_cols = None
        self.model_type = None

    def load_model(self, model_path: str = None):
        """Load prediction model."""
        if model_path is None:
            # Auto-detect model
            h2o_models = list(self.models_dir.glob('**/GBM_*')) + list(self.models_dir.glob('**/XGB_*'))
            sklearn_models = list(self.models_dir.glob('sklearn_*.joblib'))

            if h2o_models and H2O_AVAILABLE:
                model_path = str(h2o_models[0])
            elif sklearn_models:
                model_path = str(sklearn_models[0])
            else:
                raise FileNotFoundError("No saved models found")

        if 'joblib' in str(model_path) or '.joblib' in str(model_path):
            self.model = joblib.load(model_path)
            scaler_path = str(model_path).replace('model', 'scaler')
            if Path(scaler_path).exists():
                self.scaler = joblib.load(scaler_path)
            self.model_type = 'sklearn'
            logger.info(f"Loaded sklearn model from {model_path}")
        else:
            if not H2O_AVAILABLE:
                raise ImportError("H2O required to load this model")
            h2o.init(verbose=False)
            self.model = h2o.load_model(model_path)
            self.model_type = 'h2o'
            logger.info(f"Loaded H2O model from {model_path}")

        return self.model

    def predict(self, df: pd.DataFrame, feature_cols: List[str] = None) -> pd.DataFrame:
        """
        Generate predictions for players.

        Args:
            df: DataFrame with player features
            feature_cols: Feature columns to use (auto-detect if None)

        Returns:
            DataFrame with predictions added
        """
        if self.model is None:
            self.load_model()

        # Auto-detect numeric feature columns
        if feature_cols is None:
            exclude = ['gsis_id', 'name', 'player_name', 'team', 'position',
                      'ktc_value', 'predicted_ktc', 'edge_signal', 'value_delta']
            feature_cols = [c for c in df.columns
                          if c not in exclude
                          and df[c].dtype in ['int64', 'float64', 'int32', 'float32']]

        self.feature_cols = feature_cols

        # Prepare features
        X = df[feature_cols].copy()
        X = X.fillna(0)

        # Generate predictions
        if self.model_type == 'h2o':
            hf = h2o.H2OFrame(X)
            predictions = self.model.predict(hf).as_data_frame()['predict'].values
        else:
            if self.scaler:
                X_scaled = self.scaler.transform(X)
            else:
                X_scaled = X.values
            predictions = self.model.predict(X_scaled)

        # Add predictions to dataframe
        result = df.copy()
        result['predicted_ktc'] = predictions.astype(int)

        return result

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate buy/sell signals based on predictions vs actual KTC.

        Args:
            df: DataFrame with 'ktc_value' and 'predicted_ktc'

        Returns:
            DataFrame with signals added
        """
        result = df.copy()

        if 'predicted_ktc' not in result.columns:
            raise ValueError("Must run predict() first")

        if 'ktc_value' not in result.columns:
            raise ValueError("DataFrame must contain 'ktc_value' column")

        # Calculate delta
        result['value_delta'] = result['predicted_ktc'] - result['ktc_value']
        result['value_delta_pct'] = (
            (result['value_delta'] / result['ktc_value'].replace(0, np.nan)) * 100
        ).round(1)

        # Generate signals
        def get_signal(delta_pct):
            if pd.isna(delta_pct):
                return 'HOLD'
            if delta_pct > 20:
                return 'STRONG_BUY'  # Predicted > KTC by 20%+
            elif delta_pct > 10:
                return 'BUY'
            elif delta_pct < -20:
                return 'STRONG_SELL'  # Predicted < KTC by 20%+
            elif delta_pct < -10:
                return 'SELL'
            else:
                return 'HOLD'

        result['edge_signal'] = result['value_delta_pct'].apply(get_signal)

        # Confidence score (0-1 based on how far from threshold)
        result['confidence_score'] = (abs(result['value_delta_pct']) / 50).clip(0, 1).round(2)

        return result

    def predict_and_signal(self, df: pd.DataFrame, feature_cols: List[str] = None) -> pd.DataFrame:
        """Convenience method: predict then generate signals."""
        df = self.predict(df, feature_cols)
        df = self.generate_signals(df)
        return df

    def get_opportunities(self, df: pd.DataFrame, signal_type: str = 'BUY',
                          min_value: int = 1000, max_results: int = 20) -> pd.DataFrame:
        """
        Get top opportunities by signal type.

        Args:
            df: DataFrame with signals
            signal_type: 'BUY', 'STRONG_BUY', 'SELL', 'STRONG_SELL'
            min_value: Minimum KTC value to consider
            max_results: Maximum results to return

        Returns:
            DataFrame of opportunities
        """
        if 'edge_signal' not in df.columns:
            df = self.generate_signals(df)

        filtered = df[
            (df['edge_signal'].str.contains(signal_type, case=False, na=False)) &
            (df['ktc_value'] >= min_value)
        ].copy()

        # Sort by delta magnitude
        if 'BUY' in signal_type:
            filtered = filtered.sort_values('value_delta_pct', ascending=False)
        else:
            filtered = filtered.sort_values('value_delta_pct', ascending=True)

        return filtered.head(max_results)


class SignalReporter:
    """Generate reports from prediction signals."""

    @staticmethod
    def generate_summary(df: pd.DataFrame) -> Dict[str, Any]:
        """Generate summary statistics of signals."""
        if 'edge_signal' not in df.columns:
            return {}

        summary = {
            'total_players': len(df),
            'signal_distribution': df['edge_signal'].value_counts().to_dict(),
            'avg_delta_pct': df['value_delta_pct'].mean(),
            'median_delta_pct': df['value_delta_pct'].median(),
            'generated_at': datetime.now().isoformat(),
        }

        # Top opportunities
        buys = df[df['edge_signal'].isin(['BUY', 'STRONG_BUY'])]
        sells = df[df['edge_signal'].isin(['SELL', 'STRONG_SELL'])]

        if len(buys) > 0:
            top_buys = buys.nlargest(5, 'value_delta_pct')
            summary['top_buys'] = top_buys[['name', 'position', 'ktc_value',
                                             'predicted_ktc', 'value_delta_pct']].to_dict('records')

        if len(sells) > 0:
            top_sells = sells.nsmallest(5, 'value_delta_pct')
            summary['top_sells'] = top_sells[['name', 'position', 'ktc_value',
                                               'predicted_ktc', 'value_delta_pct']].to_dict('records')

        return summary

    @staticmethod
    def print_report(df: pd.DataFrame, title: str = "Dynasty Edge Signal Report"):
        """Print formatted signal report."""
        summary = SignalReporter.generate_summary(df)

        print("\n" + "=" * 70)
        print(f"  {title}")
        print("=" * 70)

        print(f"\nTotal Players Analyzed: {summary['total_players']}")
        print(f"Average Delta: {summary['avg_delta_pct']:.1f}%")

        print("\nSignal Distribution:")
        for signal, count in summary.get('signal_distribution', {}).items():
            pct = count / summary['total_players'] * 100
            print(f"  {signal}: {count} ({pct:.1f}%)")

        if 'top_buys' in summary:
            print("\n" + "-" * 70)
            print("TOP BUY OPPORTUNITIES (Model > KTC)")
            print("-" * 70)
            for p in summary['top_buys']:
                print(f"  {p['name']:<25} {p['position']:<4} "
                      f"KTC: {p['ktc_value']:>6,} → Pred: {p['predicted_ktc']:>6,} "
                      f"({p['value_delta_pct']:+.1f}%)")

        if 'top_sells' in summary:
            print("\n" + "-" * 70)
            print("TOP SELL OPPORTUNITIES (Model < KTC)")
            print("-" * 70)
            for p in summary['top_sells']:
                print(f"  {p['name']:<25} {p['position']:<4} "
                      f"KTC: {p['ktc_value']:>6,} → Pred: {p['predicted_ktc']:>6,} "
                      f"({p['value_delta_pct']:+.1f}%)")

        print("\n" + "=" * 70)


def update_neo4j_with_predictions(driver, predictions_df: pd.DataFrame):
    """
    Update Neo4j Player nodes with ML predictions.

    Args:
        driver: Neo4j driver
        predictions_df: DataFrame with predictions
    """
    required_cols = ['gsis_id', 'predicted_ktc', 'value_delta', 'value_delta_pct',
                    'edge_signal', 'confidence_score']

    missing = [c for c in required_cols if c not in predictions_df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    with driver.session() as session:
        updated = 0
        for _, row in predictions_df.iterrows():
            if pd.isna(row.get('gsis_id')):
                continue

            try:
                session.run("""
                    MATCH (p:Player {gsis_id: $gsis_id})
                    SET p.predicted_ktc_value = $predicted,
                        p.value_delta = $delta,
                        p.value_delta_pct = $delta_pct,
                        p.edge_signal = $signal,
                        p.confidence_score = $confidence,
                        p.prediction_updated = datetime()
                """, {
                    'gsis_id': row['gsis_id'],
                    'predicted': int(row['predicted_ktc']),
                    'delta': int(row['value_delta']),
                    'delta_pct': float(row['value_delta_pct']),
                    'signal': row['edge_signal'],
                    'confidence': float(row['confidence_score']),
                })
                updated += 1
            except Exception as e:
                logger.warning(f"Failed to update {row.get('name', 'unknown')}: {e}")

    logger.info(f"Updated {updated} players in Neo4j with predictions")
    return updated


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test prediction
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver("bolt://localhost:7687", auth=None)

    with driver.session() as session:
        result = session.run("""
            MATCH (p:Player)
            WHERE p.ktc_value > 0 AND p.position IN ['QB', 'RB', 'WR', 'TE']
            RETURN p.gsis_id as gsis_id, p.name as name, p.position as position,
                   p.age as age, p.ktc_value as ktc_value, p.years_exp as years_exp
        """)
        data = [dict(r) for r in result]

    driver.close()

    if data:
        df = pd.DataFrame(data)
        print(f"Loaded {len(df)} players")

        # Try to load and predict
        try:
            predictor = DynastyPredictor()
            df = predictor.predict_and_signal(df)

            SignalReporter.print_report(df)

        except FileNotFoundError:
            print("No trained model found. Train a model first using train.py")
