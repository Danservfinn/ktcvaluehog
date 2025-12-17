"""
H2O AutoML Training Pipeline for Dynasty Value Prediction
From: IMPLEMENTATION_PLAN_V2.md Phase 4
"""

import logging
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any
from datetime import datetime

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# Check for H2O availability
try:
    import h2o
    from h2o.automl import H2OAutoML
    from h2o.estimators import H2OGradientBoostingEstimator, H2OXGBoostEstimator
    H2O_AVAILABLE = True
except ImportError:
    H2O_AVAILABLE = False
    logger.warning("H2O not available. Install with: pip install h2o")

# Fallback to scikit-learn
try:
    from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
    from sklearn.model_selection import cross_val_score, train_test_split
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import mean_squared_error, r2_score
    import joblib
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


class DynastyMLTrainer:
    """
    Train ML models to predict dynasty player values.

    Primary: H2O AutoML (if available)
    Fallback: scikit-learn GradientBoosting
    """

    # Features to exclude from training
    EXCLUDE_COLUMNS = [
        'gsis_id', 'sleeper_id', 'espn_id', 'pfr_id', 'pff_id',
        'name', 'display_name', 'player_name', 'first_name', 'last_name',
        'player_id', 'id',
        'team', 'current_team', 'team_abbr',
        'birth_date', 'updated_at', 'ktc_updated',
        'edge_signal', 'confidence_score',  # These are outputs, not inputs
    ]

    # Default target variable
    DEFAULT_TARGET = 'ktc_value'

    def __init__(self, models_dir: Path = None):
        self.models_dir = Path(models_dir or 'data/models')
        self.models_dir.mkdir(parents=True, exist_ok=True)

        self.h2o_initialized = False
        self.best_model = None
        self.feature_importance = None
        self.model_performance = {}

    def _init_h2o(self):
        """Initialize H2O cluster."""
        if not H2O_AVAILABLE:
            raise ImportError("H2O is required for this trainer. Install with: pip install h2o")

        if not self.h2o_initialized:
            logger.info("Initializing H2O cluster...")
            h2o.init(
                nthreads=-1,  # Use all cores
                max_mem_size="4G",
                verbose=False
            )
            self.h2o_initialized = True
            logger.info("H2O initialized.")

    def prepare_features(self, df: pd.DataFrame, target: str = None) -> Tuple[pd.DataFrame, List[str]]:
        """
        Prepare features for training.

        Args:
            df: Input DataFrame
            target: Target variable name

        Returns:
            Tuple of (prepared DataFrame, feature column names)
        """
        target = target or self.DEFAULT_TARGET

        # Drop exclude columns
        feature_cols = [c for c in df.columns
                       if c not in self.EXCLUDE_COLUMNS
                       and c != target
                       and df[c].dtype in ['int64', 'float64', 'int32', 'float32']]

        # Handle missing values
        df_clean = df[feature_cols + [target]].copy()

        # Fill numeric NaN with median
        for col in feature_cols:
            if df_clean[col].isna().any():
                df_clean[col] = df_clean[col].fillna(df_clean[col].median())

        # Drop rows with missing target
        df_clean = df_clean.dropna(subset=[target])

        # Filter to positive target values (KTC > 0)
        df_clean = df_clean[df_clean[target] > 0]

        logger.info(f"Prepared {len(df_clean)} rows with {len(feature_cols)} features")

        return df_clean, feature_cols

    def train_h2o_automl(self,
                         df: pd.DataFrame,
                         target: str = None,
                         max_runtime_secs: int = 3600,
                         max_models: int = 50,
                         nfolds: int = 5,
                         seed: int = 42) -> Dict[str, Any]:
        """
        Train models using H2O AutoML.

        Args:
            df: Training DataFrame
            target: Target variable
            max_runtime_secs: Maximum training time
            max_models: Maximum number of models to train
            nfolds: Number of cross-validation folds
            seed: Random seed

        Returns:
            Dict with model info and performance metrics
        """
        self._init_h2o()
        target = target or self.DEFAULT_TARGET

        # Prepare features
        df_clean, feature_cols = self.prepare_features(df, target)

        logger.info(f"Training H2O AutoML on {len(df_clean)} samples...")
        logger.info(f"Features: {len(feature_cols)}, Target: {target}")
        logger.info(f"Max runtime: {max_runtime_secs}s, Max models: {max_models}")

        # Convert to H2O frame
        hf = h2o.H2OFrame(df_clean)

        # Set column types
        hf[target] = hf[target].asnumeric()
        for col in feature_cols:
            hf[col] = hf[col].asnumeric()

        # Split data
        train, valid, test = hf.split_frame(ratios=[0.7, 0.15], seed=seed)

        logger.info(f"Train: {train.nrows}, Valid: {valid.nrows}, Test: {test.nrows}")

        # Run AutoML
        aml = H2OAutoML(
            max_runtime_secs=max_runtime_secs,
            max_models=max_models,
            seed=seed,
            sort_metric='RMSE',
            nfolds=nfolds,
            verbosity='info',
            exclude_algos=['DeepLearning'],  # Exclude slow deep learning
        )

        aml.train(x=feature_cols, y=target, training_frame=train, validation_frame=valid)

        # Get results
        leaderboard = aml.leaderboard.as_data_frame()
        best_model = aml.leader

        logger.info(f"\nTop 5 Models:\n{leaderboard.head()}")

        # Feature importance
        if hasattr(best_model, 'varimp'):
            try:
                importance = best_model.varimp(use_pandas=True)
                self.feature_importance = importance
                logger.info(f"\nTop 10 Features:\n{importance.head(10)}")
            except:
                self.feature_importance = None

        # Test performance
        perf = best_model.model_performance(test)
        test_rmse = perf.rmse()
        test_r2 = perf.r2()

        logger.info(f"\nTest Performance:")
        logger.info(f"  RMSE: {test_rmse:.2f}")
        logger.info(f"  R²: {test_r2:.4f}")

        # Save model
        model_path = h2o.save_model(best_model, path=str(self.models_dir), force=True)
        logger.info(f"Model saved to: {model_path}")

        self.best_model = best_model
        self.model_performance = {
            'rmse': test_rmse,
            'r2': test_r2,
            'model_id': best_model.model_id,
            'model_path': model_path,
            'trained_at': datetime.now().isoformat(),
            'n_features': len(feature_cols),
            'n_samples': len(df_clean),
        }

        return {
            'model': best_model,
            'leaderboard': leaderboard,
            'feature_importance': self.feature_importance,
            'performance': self.model_performance,
            'feature_cols': feature_cols,
        }

    def train_sklearn_fallback(self,
                               df: pd.DataFrame,
                               target: str = None,
                               n_estimators: int = 200,
                               max_depth: int = 6,
                               seed: int = 42) -> Dict[str, Any]:
        """
        Train using scikit-learn as fallback when H2O unavailable.

        Args:
            df: Training DataFrame
            target: Target variable
            n_estimators: Number of trees
            max_depth: Max tree depth
            seed: Random seed

        Returns:
            Dict with model info and performance
        """
        if not SKLEARN_AVAILABLE:
            raise ImportError("scikit-learn required. Install with: pip install scikit-learn")

        target = target or self.DEFAULT_TARGET

        # Prepare features
        df_clean, feature_cols = self.prepare_features(df, target)

        X = df_clean[feature_cols].values
        y = df_clean[target].values

        # Split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=seed
        )

        logger.info(f"Training sklearn GradientBoosting on {len(X_train)} samples...")

        # Scale features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)

        # Train model
        model = GradientBoostingRegressor(
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=0.1,
            random_state=seed,
            verbose=1,
        )

        model.fit(X_train_scaled, y_train)

        # Evaluate
        y_pred = model.predict(X_test_scaled)
        test_rmse = np.sqrt(mean_squared_error(y_test, y_pred))
        test_r2 = r2_score(y_test, y_pred)

        logger.info(f"\nTest Performance:")
        logger.info(f"  RMSE: {test_rmse:.2f}")
        logger.info(f"  R²: {test_r2:.4f}")

        # Feature importance
        importance = pd.DataFrame({
            'variable': feature_cols,
            'relative_importance': model.feature_importances_,
        }).sort_values('relative_importance', ascending=False)

        self.feature_importance = importance
        logger.info(f"\nTop 10 Features:\n{importance.head(10)}")

        # Save model
        model_path = self.models_dir / 'sklearn_ktc_model.joblib'
        scaler_path = self.models_dir / 'sklearn_scaler.joblib'

        joblib.dump(model, model_path)
        joblib.dump(scaler, scaler_path)

        logger.info(f"Model saved to: {model_path}")

        self.best_model = model
        self.scaler = scaler
        self.model_performance = {
            'rmse': test_rmse,
            'r2': test_r2,
            'model_path': str(model_path),
            'trained_at': datetime.now().isoformat(),
            'n_features': len(feature_cols),
            'n_samples': len(df_clean),
        }

        return {
            'model': model,
            'scaler': scaler,
            'feature_importance': importance,
            'performance': self.model_performance,
            'feature_cols': feature_cols,
        }

    def train(self, df: pd.DataFrame, **kwargs) -> Dict[str, Any]:
        """
        Train model using best available method.

        Uses H2O AutoML if available, falls back to sklearn.
        """
        if H2O_AVAILABLE:
            logger.info("Using H2O AutoML for training")
            return self.train_h2o_automl(df, **kwargs)
        elif SKLEARN_AVAILABLE:
            logger.info("H2O not available, using sklearn fallback")
            return self.train_sklearn_fallback(df, **kwargs)
        else:
            raise ImportError("No ML framework available. Install h2o or scikit-learn.")

    def load_model(self, model_path: str = None):
        """Load a previously saved model."""
        if model_path is None:
            # Try to find most recent model
            h2o_models = list(self.models_dir.glob('**/GBM_*'))
            sklearn_models = list(self.models_dir.glob('sklearn_*.joblib'))

            if h2o_models and H2O_AVAILABLE:
                model_path = str(h2o_models[0])
            elif sklearn_models:
                model_path = str(sklearn_models[0])
            else:
                raise FileNotFoundError("No saved models found")

        if 'joblib' in str(model_path):
            # sklearn model
            self.best_model = joblib.load(model_path)
            scaler_path = model_path.replace('model', 'scaler')
            if Path(scaler_path).exists():
                self.scaler = joblib.load(scaler_path)
            logger.info(f"Loaded sklearn model from {model_path}")
        else:
            # H2O model
            self._init_h2o()
            self.best_model = h2o.load_model(model_path)
            logger.info(f"Loaded H2O model from {model_path}")

        return self.best_model

    def shutdown(self):
        """Shutdown H2O cluster."""
        if self.h2o_initialized and H2O_AVAILABLE:
            h2o.cluster().shutdown()
            self.h2o_initialized = False


class FeatureEngineer:
    """
    Engineer features for dynasty ML models.
    From: IMPLEMENTATION_PLAN_V2.md Phase 3
    """

    @staticmethod
    def add_age_curve_features(df: pd.DataFrame) -> pd.DataFrame:
        """Add position-specific age curve features."""
        df = df.copy()

        # Peak ages by position
        peak_ages = {'QB': 29, 'RB': 24, 'WR': 26, 'TE': 27}

        if 'age' in df.columns and 'position' in df.columns:
            # Years from peak
            df['years_from_peak'] = df.apply(
                lambda x: x['age'] - peak_ages.get(x['position'], 26)
                if pd.notna(x['age']) else 0, axis=1
            )

            # Age factor (decay curve)
            def age_factor(row):
                if pd.isna(row.get('age')):
                    return 1.0
                pos = row.get('position', 'WR')
                age = row['age']

                if pos == 'RB':
                    if age < 24: return 1.0
                    elif age < 26: return 0.9
                    elif age < 27: return 0.75
                    elif age < 28: return 0.55
                    else: return 0.35
                elif pos == 'WR':
                    if age < 27: return 1.0
                    elif age < 29: return 0.9
                    elif age < 31: return 0.75
                    else: return 0.5
                elif pos == 'QB':
                    if age < 32: return 1.0
                    elif age < 35: return 0.9
                    elif age < 38: return 0.75
                    else: return 0.5
                elif pos == 'TE':
                    if age < 28: return 1.0
                    elif age < 30: return 0.9
                    elif age < 32: return 0.75
                    else: return 0.5
                return 0.8

            df['age_factor'] = df.apply(age_factor, axis=1)

            # Years remaining estimate
            career_end = {'QB': 38, 'RB': 30, 'WR': 33, 'TE': 34}
            df['years_remaining'] = df.apply(
                lambda x: max(1, career_end.get(x['position'], 32) - x['age'])
                if pd.notna(x.get('age')) else 5, axis=1
            )

        return df

    @staticmethod
    def add_efficiency_features(df: pd.DataFrame) -> pd.DataFrame:
        """Add efficiency metrics."""
        df = df.copy()

        # Fantasy points per opportunity
        if 'fantasy_points_ppr' in df.columns:
            # Per target efficiency
            if 'targets' in df.columns:
                df['fpts_per_target'] = df['fantasy_points_ppr'] / df['targets'].replace(0, np.nan)

            # Per carry efficiency
            if 'carries' in df.columns:
                df['fpts_per_carry'] = df['fantasy_points_ppr'] / df['carries'].replace(0, np.nan)

            # Per game efficiency
            if 'games_played' in df.columns:
                df['fpts_per_game'] = df['fantasy_points_ppr'] / df['games_played'].replace(0, np.nan)

        # Yards per touch
        if 'receiving_yards' in df.columns and 'rushing_yards' in df.columns:
            total_yards = df['receiving_yards'].fillna(0) + df['rushing_yards'].fillna(0)
            total_touches = df['receptions'].fillna(0) + df['carries'].fillna(0)
            df['yards_per_touch'] = total_yards / total_touches.replace(0, np.nan)

        # TD rate
        if 'receiving_tds' in df.columns and 'rushing_tds' in df.columns:
            total_tds = df['receiving_tds'].fillna(0) + df['rushing_tds'].fillna(0)
            if 'targets' in df.columns and 'carries' in df.columns:
                total_opps = df['targets'].fillna(0) + df['carries'].fillna(0)
                df['td_rate'] = total_tds / total_opps.replace(0, np.nan)

        return df

    @staticmethod
    def add_draft_capital_features(df: pd.DataFrame) -> pd.DataFrame:
        """Add draft capital features."""
        df = df.copy()

        if 'draft_round' in df.columns:
            # Draft capital score (higher = more capital)
            df['draft_capital'] = 8 - df['draft_round'].fillna(7)

            # First round indicator
            df['is_first_round'] = (df['draft_round'] == 1).astype(int)

            # Day 1/2/3 indicator
            df['draft_day'] = df['draft_round'].apply(
                lambda x: 1 if x == 1 else (2 if x <= 3 else 3) if pd.notna(x) else 3
            )

        if 'draft_pick' in df.columns:
            # Overall pick value (inverse)
            df['pick_value'] = 1 / (df['draft_pick'].fillna(256) + 1) * 100

        return df

    @staticmethod
    def add_interaction_features(df: pd.DataFrame) -> pd.DataFrame:
        """Add interaction features."""
        df = df.copy()

        # Age × production interaction
        if 'age' in df.columns and 'fantasy_points_ppr' in df.columns:
            df['age_x_production'] = df['age'] * df['fantasy_points_ppr'].fillna(0)

        # Draft capital × age (younger + high capital = valuable)
        if 'draft_capital' in df.columns and 'age' in df.columns:
            df['capital_x_youth'] = df['draft_capital'] * (30 - df['age'].fillna(26))

        # Experience × production
        if 'years_exp' in df.columns and 'fantasy_points_ppr' in df.columns:
            df['exp_x_production'] = df['years_exp'].fillna(0) * df['fantasy_points_ppr'].fillna(0)

        return df

    @classmethod
    def engineer_all_features(cls, df: pd.DataFrame) -> pd.DataFrame:
        """Apply all feature engineering."""
        df = cls.add_age_curve_features(df)
        df = cls.add_efficiency_features(df)
        df = cls.add_draft_capital_features(df)
        df = cls.add_interaction_features(df)

        # Fill remaining NaN with 0
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        df[numeric_cols] = df[numeric_cols].fillna(0)

        return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test with sample data
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver("bolt://localhost:7687", auth=None)

    with driver.session() as session:
        result = session.run("""
            MATCH (p:Player)
            WHERE p.ktc_value > 0 AND p.position IN ['QB', 'RB', 'WR', 'TE']
            RETURN p.name as name, p.position as position, p.age as age,
                   p.ktc_value as ktc_value, p.years_exp as years_exp
        """)
        data = [dict(r) for r in result]

    driver.close()

    if data:
        df = pd.DataFrame(data)
        print(f"Loaded {len(df)} players")

        # Engineer features
        df = FeatureEngineer.engineer_all_features(df)
        print(f"Features: {list(df.columns)}")

        # Train model
        trainer = DynastyMLTrainer()
        results = trainer.train(df, max_runtime_secs=300)

        print(f"\nTraining complete!")
        print(f"Performance: {results['performance']}")
