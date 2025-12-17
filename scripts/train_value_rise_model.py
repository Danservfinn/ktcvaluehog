"""
Train ML model to predict players likely to rise in value.

Since we don't have historical KTC value changes, we use a proxy:
- The difference between model-predicted value and actual KTC value
- Combined with breakout scores and other indicators

This identifies players who are statistically undervalued based on their
performance and situation metrics.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from neo4j import GraphDatabase
from sklearn.ensemble import GradientBoostingRegressor, RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, r2_score, classification_report
import joblib
import warnings
warnings.filterwarnings('ignore')


def get_driver():
    """Get Neo4j driver."""
    return GraphDatabase.driver("bolt://localhost:7687", auth=None)


def fetch_training_data():
    """Fetch all player data with features and breakout scores."""
    driver = get_driver()

    with driver.session() as session:
        result = session.run("""
            MATCH (p:Player)
            WHERE p.position IN ['QB', 'RB', 'WR', 'TE']
              AND p.ktc_value > 0
              AND p.breakout_score IS NOT NULL

            RETURN
                // Identity
                p.gsis_id as gsis_id,
                p.name as name,
                p.position as position,

                // Target/Labels
                p.ktc_value as ktc_value,
                p.predicted_ktc_value as predicted_value,
                p.value_delta_pct as value_gap_pct,
                p.edge_signal as edge_signal,

                // Core features
                p.age as age,
                p.years_exp as years_exp,
                p.draft_round as draft_round,
                p.draft_pick as draft_pick,

                // Production features
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

                // Career metrics
                p.career_ppg_ppr as career_ppg,
                p.career_fpts_ppr as career_fpts,
                p.career_games as career_games,
                p.seasons_played as seasons_played,

                // Trend metrics
                p.ppg_trend_slope as ppg_trend_slope,
                p.ppg_trend_3yr as ppg_trend_3yr,

                // Consistency metrics
                p.ppg_stddev as ppg_stddev,
                p.ppg_cv as ppg_cv,
                p.boom_rate as boom_rate,
                p.bust_rate as bust_rate,
                p.floor_ppg as floor_ppg,
                p.ceiling_ppg as ceiling_ppg,

                // Peak metrics
                p.peak_ppg as peak_ppg,
                p.years_from_peak_season as years_from_peak,

                // Playing time
                p.avg_snap_pct as snap_pct,
                p.total_snaps as total_snaps,

                // Contract
                p.contract_apy as contract_apy,
                p.contract_guaranteed as contract_guaranteed,

                // Athletic
                p.athletic_score as athletic_score,
                p.combine_forty as forty_time,

                // Breakout scores
                p.breakout_score as breakout_score,
                p.trajectory_score as trajectory_score,
                p.efficiency_gap as efficiency_gap,
                p.ceiling_ratio as ceiling_ratio,
                p.athletic_upside as athletic_upside,
                p.situation_score as situation_score
        """)

        data = [dict(r) for r in result]

    driver.close()
    return pd.DataFrame(data)


def engineer_features(df):
    """Engineer additional features for value rise prediction."""
    df = df.copy()

    # Current PPG
    games = df['games_played'].fillna(1).replace(0, 1)
    df['current_ppg'] = df['fantasy_points_ppr'].fillna(0) / games

    # PPG relative to career
    career_ppg = df['career_ppg'].fillna(df['current_ppg'])
    df['ppg_vs_career'] = df['current_ppg'] / career_ppg.replace(0, 1) * 100

    # PPG relative to peak
    peak_ppg = df['peak_ppg'].fillna(df['current_ppg'])
    df['ppg_vs_peak'] = df['current_ppg'] / peak_ppg.replace(0, 1) * 100

    # Value per PPG (efficiency metric)
    df['value_per_ppg'] = df['ktc_value'] / df['current_ppg'].replace(0, 1)

    # Age-value ratio (higher = potentially overvalued due to age)
    df['age_value_ratio'] = df['age'].fillna(26) * 100 / df['ktc_value'].replace(0, 1)

    # Production momentum (trend * current production)
    df['production_momentum'] = df['ppg_trend_slope'].fillna(0) * df['current_ppg']

    # Consistency-adjusted upside
    cv = df['ppg_cv'].fillna(50)
    df['stability_adjusted_ceiling'] = df['ceiling_ppg'].fillna(0) * (100 - cv) / 100

    # Position-specific features
    # WR/TE target share efficiency
    df['target_efficiency'] = np.where(
        df['targets'].fillna(0) > 0,
        df['receiving_yards'].fillna(0) / df['targets'].fillna(1),
        0
    )

    # RB rushing efficiency
    df['rush_efficiency'] = np.where(
        df['carries'].fillna(0) > 0,
        df['rushing_yards'].fillna(0) / df['carries'].fillna(1),
        0
    )

    # One-hot encode position
    df = pd.get_dummies(df, columns=['position'], prefix='pos')

    return df


def create_value_rise_target(df):
    """
    Create target variable for value rise prediction.

    Without historical data, we use the model's predicted vs actual gap
    as a proxy for "should be worth more than current value".
    """
    df = df.copy()

    # Primary target: value gap percentage
    # Positive = model thinks player is undervalued
    df['value_rise_target'] = df['value_gap_pct'].fillna(0)

    # Create classification target for "likely to rise"
    # Based on multiple indicators:
    # 1. Model says undervalued (value_gap > 10%)
    # 2. High breakout score (> 60)
    # 3. Positive trajectory

    df['likely_rise'] = (
        (df['value_gap_pct'].fillna(0) > 10) |
        (df['breakout_score'].fillna(0) > 65) |
        ((df['trajectory_score'].fillna(0) > 70) & (df['value_gap_pct'].fillna(0) > 0))
    ).astype(int)

    return df


def train_regression_model(df, feature_cols):
    """Train regression model to predict value gap percentage."""
    print("\n🎯 Training Regression Model (Value Gap Prediction)...")

    # Prepare data
    X = df[feature_cols].fillna(0)
    y = df['value_rise_target']

    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Train model
    model = GradientBoostingRegressor(
        n_estimators=200,
        max_depth=5,
        learning_rate=0.1,
        min_samples_split=10,
        random_state=42
    )

    model.fit(X_train_scaled, y_train)

    # Evaluate
    y_pred = model.predict(X_test_scaled)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    r2 = r2_score(y_test, y_pred)

    print(f"   R² Score: {r2:.4f}")
    print(f"   RMSE: {rmse:.2f}%")

    # Cross-validation
    cv_scores = cross_val_score(model, scaler.transform(X), y, cv=5)
    print(f"   CV R² (5-fold): {cv_scores.mean():.4f} (+/- {cv_scores.std()*2:.4f})")

    return model, scaler, r2, rmse


def train_classification_model(df, feature_cols):
    """Train classification model to predict likely value risers."""
    print("\n🎯 Training Classification Model (Likely Risers)...")

    # Prepare data
    X = df[feature_cols].fillna(0)
    y = df['likely_rise']

    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Train model
    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=8,
        min_samples_split=10,
        class_weight='balanced',
        random_state=42
    )

    model.fit(X_train_scaled, y_train)

    # Evaluate
    y_pred = model.predict(X_test_scaled)
    y_prob = model.predict_proba(X_test_scaled)[:, 1]

    print("\n   Classification Report:")
    print(classification_report(y_test, y_pred, target_names=['Hold/Sell', 'Likely Rise']))

    return model, scaler


def get_feature_importance(model, feature_cols, top_n=20):
    """Get feature importance from trained model."""
    importance = pd.DataFrame({
        'feature': feature_cols,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)

    return importance.head(top_n)


def generate_predictions(df, reg_model, clf_model, reg_scaler, clf_scaler, feature_cols):
    """Generate predictions for all players."""
    X = df[feature_cols].fillna(0)

    # Regression predictions (predicted value gap)
    X_reg_scaled = reg_scaler.transform(X)
    df['predicted_value_gap'] = reg_model.predict(X_reg_scaled)

    # Classification predictions (rise probability)
    X_clf_scaled = clf_scaler.transform(X)
    df['rise_probability'] = clf_model.predict_proba(X_clf_scaled)[:, 1]
    df['rise_prediction'] = clf_model.predict(X_clf_scaled)

    # Composite score: combine both models + breakout score
    df['value_rise_score'] = (
        df['predicted_value_gap'].clip(-50, 50) / 100 * 30 +  # Value gap contribution
        df['rise_probability'] * 40 +  # Classification probability
        df['breakout_score'].fillna(50) / 100 * 30  # Breakout score
    )

    # Normalize to 0-100
    min_score = df['value_rise_score'].min()
    max_score = df['value_rise_score'].max()
    df['value_rise_score'] = ((df['value_rise_score'] - min_score) / (max_score - min_score) * 100).round(2)

    return df


def store_predictions(df):
    """Store predictions in Neo4j."""
    driver = get_driver()

    with driver.session() as session:
        records = df[['gsis_id', 'value_rise_score', 'rise_probability', 'predicted_value_gap']].to_dict('records')

        session.run("""
            UNWIND $records as r
            MATCH (p:Player {gsis_id: r.gsis_id})
            SET p.value_rise_score = r.value_rise_score,
                p.rise_probability = r.rise_probability,
                p.predicted_value_gap = r.predicted_value_gap,
                p.rise_model_updated = datetime()
        """, {'records': records})

        print(f"   Updated {len(records)} players")

    driver.close()


def main():
    """Main training pipeline."""
    print("=" * 70)
    print("VALUE RISE PREDICTION MODEL TRAINING")
    print(f"Started: {datetime.now()}")
    print("=" * 70)

    # 1. Fetch data
    print("\n📊 Fetching training data...")
    df = fetch_training_data()
    print(f"   Loaded {len(df)} players with breakout scores")

    # 2. Engineer features
    print("\n🔧 Engineering features...")
    df = engineer_features(df)
    df = create_value_rise_target(df)

    # Define feature columns (exclude targets and identifiers)
    exclude_cols = [
        'gsis_id', 'name', 'ktc_value', 'predicted_value', 'value_gap_pct',
        'edge_signal', 'value_rise_target', 'likely_rise'
    ]
    feature_cols = [c for c in df.columns if c not in exclude_cols and df[c].dtype in ['int64', 'float64', 'bool', 'uint8']]

    print(f"   Using {len(feature_cols)} features")

    # 3. Train regression model
    reg_model, reg_scaler, r2, rmse = train_regression_model(df, feature_cols)

    # 4. Train classification model
    clf_model, clf_scaler = train_classification_model(df, feature_cols)

    # 5. Feature importance
    print("\n" + "=" * 70)
    print("TOP 20 FEATURE IMPORTANCE (Regression)")
    print("=" * 70)
    importance = get_feature_importance(reg_model, feature_cols)
    for _, row in importance.iterrows():
        print(f"   {row['feature']:<35} {row['importance']:.4f}")

    # 6. Generate predictions for all players
    print("\n📈 Generating predictions...")
    df = generate_predictions(df, reg_model, clf_model, reg_scaler, clf_scaler, feature_cols)

    # 7. Store predictions
    print("\n💾 Storing predictions in Neo4j...")
    store_predictions(df)

    # 8. Save models
    models_dir = Path('data/models')
    models_dir.mkdir(parents=True, exist_ok=True)

    joblib.dump(reg_model, models_dir / 'value_rise_regression.pkl')
    joblib.dump(clf_model, models_dir / 'value_rise_classifier.pkl')
    joblib.dump(reg_scaler, models_dir / 'value_rise_reg_scaler.pkl')
    joblib.dump(clf_scaler, models_dir / 'value_rise_clf_scaler.pkl')
    joblib.dump(feature_cols, models_dir / 'value_rise_features.pkl')

    print(f"   Models saved to {models_dir}")

    # 9. Show top candidates
    print("\n" + "=" * 70)
    print("TOP VALUE RISE CANDIDATES BY POSITION")
    print("=" * 70)

    for pos_col in ['pos_QB', 'pos_RB', 'pos_WR', 'pos_TE']:
        if pos_col in df.columns:
            pos = pos_col.replace('pos_', '')
            pos_df = df[df[pos_col] == 1].nlargest(5, 'value_rise_score')

            print(f"\n{pos}:")
            for _, row in pos_df.iterrows():
                print(f"   {row['name']:<25} | Rise Score: {row['value_rise_score']:5.1f} | "
                      f"Prob: {row['rise_probability']*100:5.1f}% | "
                      f"KTC: {row['ktc_value']:,}")

    # 10. Score distribution
    print("\n" + "=" * 70)
    print("VALUE RISE SCORE DISTRIBUTION")
    print("=" * 70)
    print(f"   Mean: {df['value_rise_score'].mean():.1f}")
    print(f"   Std:  {df['value_rise_score'].std():.1f}")
    print(f"   Min:  {df['value_rise_score'].min():.1f}")
    print(f"   Max:  {df['value_rise_score'].max():.1f}")

    # Classification distribution
    print(f"\n   Players predicted to rise: {df['rise_prediction'].sum()} ({df['rise_prediction'].mean()*100:.1f}%)")

    print("\n" + "=" * 70)
    print("VALUE RISE MODEL TRAINING COMPLETE")
    print("=" * 70)

    return df, reg_model, clf_model


if __name__ == "__main__":
    main()
