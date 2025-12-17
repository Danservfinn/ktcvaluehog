"""
Retrain ML model with enhanced fantasy production features.
Includes career totals, trends, consistency, and peak production.
"""

import logging
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from neo4j import GraphDatabase

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import training classes
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.ml.train import DynastyMLTrainer, FeatureEngineer


def get_driver():
    """Get Neo4j driver."""
    return GraphDatabase.driver("bolt://localhost:7687", auth=None)


def fetch_training_data():
    """Fetch player data with all features from Neo4j."""
    driver = get_driver()

    with driver.session() as session:
        result = session.run("""
            MATCH (p:Player)
            WHERE p.position IN ['QB', 'RB', 'WR', 'TE']
              AND p.ktc_value > 0
            RETURN
                // Identity
                p.gsis_id as gsis_id,
                p.name as name,
                p.position as position,

                // Target variable
                p.ktc_value as ktc_value,

                // Core features
                p.age as age,
                p.years_exp as years_exp,
                p.draft_round as draft_round,
                p.draft_pick as draft_pick,

                // Current season production
                p.fantasy_points as fantasy_points,
                p.fantasy_points_ppr as fantasy_points_ppr,
                p.games_played as games_played,
                p.targets as targets,
                p.receptions as receptions,
                p.receiving_yards as receiving_yards,
                p.receiving_tds as receiving_tds,
                p.carries as carries,
                p.rushing_yards as rushing_yards,
                p.rushing_tds as rushing_tds,
                p.passing_yards as passing_yards,
                p.passing_tds as passing_tds,

                // Playing time
                p.avg_snap_pct as snap_pct,
                p.total_snaps as total_snaps,

                // Contract
                p.contract_apy as contract_apy,
                p.contract_guaranteed as contract_guaranteed,

                // Athletic
                p.combine_forty as forty_time,
                p.combine_vertical as vertical_jump,
                p.combine_broad_jump as broad_jump,
                p.combine_cone as three_cone,
                p.athletic_score as athletic_score,

                // === NEW FANTASY FEATURES ===

                // Career totals (all 3 formats)
                p.career_fpts_std as career_fpts_std,
                p.career_fpts_half as career_fpts_half,
                p.career_fpts_ppr as career_fpts_ppr,
                p.career_ppg_std as career_ppg_std,
                p.career_ppg_half as career_ppg_half,
                p.career_ppg_ppr as career_ppg_ppr,
                p.career_games as career_games,
                p.career_receptions as career_receptions,
                p.seasons_played as seasons_played,

                // PPG trends
                p.ppg_trend_slope as ppg_trend_slope,
                p.ppg_trend_3yr as ppg_trend_3yr,

                // Consistency metrics
                p.ppg_stddev as ppg_stddev,
                p.ppg_cv as ppg_cv,
                p.boom_rate as boom_rate,
                p.bust_rate as bust_rate,
                p.floor_ppg as floor_ppg,
                p.ceiling_ppg as ceiling_ppg,

                // Peak production
                p.peak_ppg as peak_ppg,
                p.peak_fpts as peak_fpts,
                p.years_from_peak_season as years_from_peak_season,
                p.peak_vs_career as peak_vs_career
        """)

        data = [dict(r) for r in result]

    driver.close()
    return pd.DataFrame(data)


def engineer_additional_features(df):
    """Add additional derived features specific to fantasy production."""
    df = df.copy()

    # Fantasy point differentials (Standard vs PPR value)
    if 'career_ppg_std' in df.columns and 'career_ppg_ppr' in df.columns:
        df['ppr_premium'] = df['career_ppg_ppr'] - df['career_ppg_std']

    # Production trajectory score
    if 'ppg_trend_slope' in df.columns and 'years_from_peak_season' in df.columns:
        df['trajectory_score'] = df['ppg_trend_slope'] - (df['years_from_peak_season'].fillna(0) * 0.5)

    # Consistency score (inverse of CV, higher = more consistent)
    if 'ppg_cv' in df.columns:
        df['consistency_score'] = 100 - df['ppg_cv'].clip(0, 100)

    # Upside score (ceiling - floor)
    if 'ceiling_ppg' in df.columns and 'floor_ppg' in df.columns:
        df['upside_score'] = df['ceiling_ppg'] - df['floor_ppg']

    # Career value per game
    if 'career_fpts_half' in df.columns and 'career_games' in df.columns:
        df['career_value_pg'] = df['career_fpts_half'] / df['career_games'].replace(0, np.nan)

    # Peak to current ratio (if current PPG available)
    if 'peak_ppg' in df.columns and 'fantasy_points_ppr' in df.columns and 'games_played' in df.columns:
        current_ppg = df['fantasy_points_ppr'] / df['games_played'].replace(0, np.nan)
        df['peak_to_current'] = df['peak_ppg'] / current_ppg.replace(0, np.nan)

    # Age-adjusted production (younger with same production = more valuable)
    if 'age' in df.columns and 'career_ppg_half' in df.columns:
        df['age_adjusted_production'] = df['career_ppg_half'] / (df['age'].fillna(25) / 25)

    return df


def store_predictions(df):
    """Store model predictions back to Neo4j."""
    driver = get_driver()

    with driver.session() as session:
        # Update predictions
        updates = df[['gsis_id', 'predicted_ktc_value', 'value_delta', 'value_delta_pct', 'edge_signal']].to_dict('records')

        session.run("""
            UNWIND $updates as u
            MATCH (p:Player {gsis_id: u.gsis_id})
            SET p.predicted_ktc_value = u.predicted_ktc_value,
                p.value_delta = u.value_delta,
                p.value_delta_pct = u.value_delta_pct,
                p.edge_signal = u.edge_signal,
                p.model_updated = datetime()
        """, {'updates': updates})

        logger.info(f"Stored predictions for {len(updates)} players")

    driver.close()


def generate_signals(df):
    """Generate buy/sell signals based on value gap."""
    df = df.copy()

    # Calculate value gap
    df['value_delta'] = df['predicted_ktc_value'] - df['ktc_value']
    df['value_delta_pct'] = (df['value_delta'] / df['ktc_value'] * 100).fillna(0)

    # Generate signals
    def get_signal(pct):
        if pct >= 20:
            return 'STRONG_BUY'
        elif pct >= 10:
            return 'BUY'
        elif pct <= -20:
            return 'STRONG_SELL'
        elif pct <= -10:
            return 'SELL'
        else:
            return 'HOLD'

    df['edge_signal'] = df['value_delta_pct'].apply(get_signal)

    return df


def main():
    """Main training pipeline."""
    print("=" * 70)
    print("DYNASTY ML MODEL RETRAINING")
    print(f"Started: {datetime.now()}")
    print("=" * 70)

    # 1. Fetch data
    print("\n📊 Fetching training data...")
    df = fetch_training_data()
    print(f"   Loaded {len(df)} players")

    # 2. Apply feature engineering
    print("\n🔧 Engineering features...")

    # Standard feature engineering
    df = FeatureEngineer.engineer_all_features(df)

    # Additional fantasy-specific features
    df = engineer_additional_features(df)

    # Count features
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    print(f"   Total features: {len(numeric_cols)}")

    # List new fantasy features
    new_features = [
        'career_fpts_std', 'career_fpts_half', 'career_fpts_ppr',
        'career_ppg_std', 'career_ppg_half', 'career_ppg_ppr',
        'ppg_trend_slope', 'ppg_trend_3yr', 'ppg_stddev', 'ppg_cv',
        'boom_rate', 'bust_rate', 'floor_ppg', 'ceiling_ppg',
        'peak_ppg', 'peak_fpts', 'years_from_peak_season',
        'ppr_premium', 'trajectory_score', 'consistency_score',
        'upside_score', 'age_adjusted_production'
    ]
    available_new = [f for f in new_features if f in df.columns]
    print(f"   New fantasy features: {len(available_new)}")

    # 3. Train model
    print("\n🎯 Training model...")
    trainer = DynastyMLTrainer(models_dir=Path('data/models'))

    try:
        results = trainer.train(
            df,
            target='ktc_value',
            max_runtime_secs=600,  # 10 minutes
            max_models=30
        )
    except Exception as e:
        logger.warning(f"H2O training failed: {e}")
        logger.info("Falling back to sklearn...")
        results = trainer.train_sklearn_fallback(
            df,
            target='ktc_value',
            n_estimators=300,
            max_depth=8
        )

    # 4. Display results
    print("\n" + "=" * 70)
    print("MODEL PERFORMANCE")
    print("=" * 70)
    perf = results['performance']
    print(f"   R² Score: {perf['r2']:.4f}")
    print(f"   RMSE: {perf['rmse']:.2f}")
    print(f"   Samples: {perf['n_samples']}")
    print(f"   Features: {perf['n_features']}")

    # 5. Feature importance
    print("\n" + "=" * 70)
    print("TOP 20 FEATURE IMPORTANCE")
    print("=" * 70)
    importance = results['feature_importance']
    if importance is not None:
        top_features = importance.head(20)
        for idx, row in top_features.iterrows():
            var = row['variable'] if 'variable' in row else row.get('Variable', 'unknown')
            imp = row['relative_importance'] if 'relative_importance' in row else row.get('Relative Importance', 0)
            # Highlight new fantasy features
            marker = "★" if var in new_features else " "
            print(f"   {marker} {var:<35} {imp:.4f}")

    # 6. Generate predictions for all players
    print("\n📈 Generating predictions...")
    feature_cols = results['feature_cols']

    # Prepare data for prediction
    X = df[feature_cols].fillna(0)

    # Check if it's an H2O model or sklearn model
    model = trainer.best_model
    model_type = str(type(model))

    if 'h2o' in model_type.lower() or 'H2O' in model_type:
        # H2O model - need to convert to H2O Frame
        import h2o
        hf = h2o.H2OFrame(X)
        predictions = model.predict(hf).as_data_frame()['predict'].values
    elif hasattr(trainer, 'scaler') and trainer.scaler is not None:
        # sklearn model with scaler
        X_scaled = trainer.scaler.transform(X)
        predictions = model.predict(X_scaled)
    else:
        # sklearn model without scaler
        predictions = model.predict(X)

    df['predicted_ktc_value'] = predictions

    # Generate signals
    df = generate_signals(df)

    # 7. Store predictions
    print("\n💾 Storing predictions...")
    store_predictions(df)

    # 8. Summary
    print("\n" + "=" * 70)
    print("SIGNAL DISTRIBUTION")
    print("=" * 70)
    signal_dist = df['edge_signal'].value_counts()
    for signal, count in signal_dist.items():
        print(f"   {signal}: {count}")

    # Show top buy/sell candidates
    print("\n" + "=" * 70)
    print("TOP BUY CANDIDATES")
    print("=" * 70)
    buys = df[df['edge_signal'].isin(['STRONG_BUY', 'BUY'])].nlargest(10, 'value_delta_pct')
    for _, row in buys.iterrows():
        print(f"   {row['name']:<25} ({row['position']}) | "
              f"KTC: {row['ktc_value']:>6,.0f} → Model: {row['predicted_ktc_value']:>6,.0f} | "
              f"{row['value_delta_pct']:>+6.1f}%")

    print("\n" + "=" * 70)
    print("TOP SELL CANDIDATES")
    print("=" * 70)
    sells = df[df['edge_signal'].isin(['STRONG_SELL', 'SELL'])].nsmallest(10, 'value_delta_pct')
    for _, row in sells.iterrows():
        print(f"   {row['name']:<25} ({row['position']}) | "
              f"KTC: {row['ktc_value']:>6,.0f} → Model: {row['predicted_ktc_value']:>6,.0f} | "
              f"{row['value_delta_pct']:>+6.1f}%")

    print("\n" + "=" * 70)
    print("RETRAINING COMPLETE")
    print(f"Finished: {datetime.now()}")
    print("=" * 70)

    return results


if __name__ == "__main__":
    main()
