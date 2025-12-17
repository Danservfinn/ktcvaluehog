"""
Train ML model to predict future fantasy point production.

Uses historical season-by-season data to learn which variables
best predict next year's fantasy performance.

Target: Next season's fantasy points (PPR)
Features: Current season stats, career metrics, age, trends
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from neo4j import GraphDatabase
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge, Lasso
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
import joblib
import warnings
warnings.filterwarnings('ignore')


def get_driver():
    """Get Neo4j driver."""
    return GraphDatabase.driver("bolt://localhost:7687", auth=None)


def fetch_season_data():
    """Fetch all season stats from Neo4j."""
    driver = get_driver()

    with driver.session() as session:
        result = session.run("""
            MATCH (s:SeasonStats)
            WHERE s.position IN ['QB', 'RB', 'WR', 'TE']
              AND s.games_played >= 4
            RETURN
                s.player_id as player_id,
                s.player_name as name,
                s.position as position,
                s.season as season,
                s.games_played as games,
                s.fantasy_points as fpts_std,
                s.fantasy_points_ppr as fpts_ppr,
                s.ppg as ppg,
                s.completions as completions,
                s.attempts as pass_attempts,
                s.passing_yards as pass_yards,
                s.passing_tds as pass_tds,
                s.interceptions as interceptions,
                s.completion_pct as comp_pct,
                s.carries as carries,
                s.rushing_yards as rush_yards,
                s.rushing_tds as rush_tds,
                s.yards_per_carry as ypc,
                s.targets as targets,
                s.receptions as receptions,
                s.receiving_yards as rec_yards,
                s.receiving_tds as rec_tds,
                s.catch_rate as catch_rate,
                s.yards_per_target as ypr
            ORDER BY s.player_id, s.season
        """)

        data = [dict(r) for r in result]

    driver.close()
    return pd.DataFrame(data)


def fetch_player_metadata():
    """Fetch player metadata (age, draft info, etc.)."""
    driver = get_driver()

    with driver.session() as session:
        result = session.run("""
            MATCH (p:Player)
            WHERE p.position IN ['QB', 'RB', 'WR', 'TE']
            RETURN
                p.gsis_id as player_id,
                p.name as name,
                p.position as position,
                p.age as current_age,
                p.years_exp as years_exp,
                p.draft_round as draft_round,
                p.draft_pick as draft_pick,
                p.athletic_score as athletic_score,
                p.combine_forty as forty_time,
                p.combine_vertical as vertical,
                p.combine_broad_jump as broad_jump
        """)

        data = [dict(r) for r in result]

    driver.close()
    return pd.DataFrame(data)


def create_training_pairs(season_df):
    """
    Create year-over-year training pairs.
    Features from year N -> Target from year N+1
    """
    print("\n📊 Creating year-over-year training pairs...")

    # Sort by player and season
    df = season_df.sort_values(['player_id', 'season'])

    pairs = []

    for player_id in df['player_id'].unique():
        player_data = df[df['player_id'] == player_id].sort_values('season')

        if len(player_data) < 2:
            continue

        # Create pairs for consecutive seasons
        for i in range(len(player_data) - 1):
            current = player_data.iloc[i]
            next_season = player_data.iloc[i + 1]

            # Only use if seasons are consecutive
            if next_season['season'] - current['season'] != 1:
                continue

            pair = {
                'player_id': player_id,
                'name': current['name'],
                'position': current['position'],
                'current_season': current['season'],
                'next_season': next_season['season'],

                # Target: next season's fantasy points
                'target_fpts_ppr': next_season['fpts_ppr'],
                'target_ppg': next_season['ppg'],
                'target_games': next_season['games'],

                # Current season features
                'curr_games': current['games'],
                'curr_fpts_ppr': current['fpts_ppr'],
                'curr_fpts_std': current['fpts_std'],
                'curr_ppg': current['ppg'],

                # Passing stats
                'curr_pass_yards': current['pass_yards'],
                'curr_pass_tds': current['pass_tds'],
                'curr_interceptions': current['interceptions'],
                'curr_comp_pct': current['comp_pct'],
                'curr_pass_attempts': current['pass_attempts'],

                # Rushing stats
                'curr_carries': current['carries'],
                'curr_rush_yards': current['rush_yards'],
                'curr_rush_tds': current['rush_tds'],
                'curr_ypc': current['ypc'],

                # Receiving stats
                'curr_targets': current['targets'],
                'curr_receptions': current['receptions'],
                'curr_rec_yards': current['rec_yards'],
                'curr_rec_tds': current['rec_tds'],
                'curr_catch_rate': current['catch_rate'],
                'curr_ypr': current['ypr'],
            }

            pairs.append(pair)

    pairs_df = pd.DataFrame(pairs)
    print(f"   Created {len(pairs_df)} training pairs")

    return pairs_df


def add_career_features(pairs_df, season_df):
    """Add career-to-date features for each training pair."""
    print("\n🔧 Adding career features...")

    career_features = []

    for idx, row in pairs_df.iterrows():
        player_id = row['player_id']
        current_season = row['current_season']

        # Get all seasons up to and including current
        player_history = season_df[
            (season_df['player_id'] == player_id) &
            (season_df['season'] <= current_season)
        ].sort_values('season')

        if len(player_history) == 0:
            career_features.append({})
            continue

        # Career totals
        career_games = player_history['games'].sum()
        career_fpts = player_history['fpts_ppr'].sum()

        # Career averages
        career_ppg = career_fpts / max(career_games, 1)

        # Seasons played
        seasons_played = len(player_history)

        # Peak season
        peak_fpts = player_history['fpts_ppr'].max()
        peak_ppg = player_history['ppg'].max()

        # Trend (last 3 seasons if available)
        recent = player_history.tail(3)
        if len(recent) >= 2:
            ppg_values = recent['ppg'].values
            trend_slope = np.polyfit(range(len(ppg_values)), ppg_values, 1)[0] if len(ppg_values) > 1 else 0
        else:
            trend_slope = 0

        # Consistency (std dev of PPG)
        ppg_std = player_history['ppg'].std() if len(player_history) > 1 else 0

        # Year-over-year change (if available)
        if len(player_history) >= 2:
            prev_season = player_history.iloc[-2]
            curr_season_data = player_history.iloc[-1]
            yoy_change = curr_season_data['ppg'] - prev_season['ppg']
            yoy_pct = yoy_change / max(prev_season['ppg'], 0.1) * 100
        else:
            yoy_change = 0
            yoy_pct = 0

        career_features.append({
            'career_games': career_games,
            'career_fpts': career_fpts,
            'career_ppg': career_ppg,
            'seasons_played': seasons_played,
            'peak_fpts': peak_fpts,
            'peak_ppg': peak_ppg,
            'ppg_trend_slope': trend_slope,
            'ppg_stddev': ppg_std,
            'yoy_ppg_change': yoy_change,
            'yoy_ppg_pct': yoy_pct,
        })

    career_df = pd.DataFrame(career_features)
    pairs_df = pd.concat([pairs_df.reset_index(drop=True), career_df], axis=1)

    return pairs_df


def add_age_features(pairs_df, player_df):
    """Add age-related features."""
    print("\n🔧 Adding age features...")

    # Create lookup for player metadata (drop duplicates first)
    player_df_unique = player_df.drop_duplicates(subset='player_id', keep='first')
    player_lookup = player_df_unique.set_index('player_id').to_dict('index')

    age_features = []

    for idx, row in pairs_df.iterrows():
        player_id = row['player_id']
        current_season = row['current_season']

        player_info = player_lookup.get(player_id, {})

        # Estimate age at current season
        # (current_age - years since current_season)
        current_age = player_info.get('current_age')
        years_exp = player_info.get('years_exp')

        if current_age and years_exp:
            # Estimate age at that season
            years_since = 2024 - current_season
            age_at_season = current_age - years_since
        else:
            age_at_season = None

        age_features.append({
            'age': age_at_season,
            'draft_round': player_info.get('draft_round'),
            'draft_pick': player_info.get('draft_pick'),
            'athletic_score': player_info.get('athletic_score'),
            'forty_time': player_info.get('forty_time'),
        })

    age_df = pd.DataFrame(age_features)
    pairs_df = pd.concat([pairs_df.reset_index(drop=True), age_df], axis=1)

    return pairs_df


def engineer_additional_features(df):
    """Engineer additional predictive features."""
    print("\n🔧 Engineering additional features...")

    df = df.copy()

    # Games played rate (indicator of durability)
    df['games_rate'] = df['curr_games'] / 17  # 17-game season

    # Production efficiency
    df['fpts_per_opportunity'] = df['curr_fpts_ppr'] / (
        df['curr_targets'].fillna(0) + df['curr_carries'].fillna(0) + df['curr_pass_attempts'].fillna(0) + 1
    )

    # Peak vs current ratio
    df['curr_vs_peak'] = df['curr_ppg'] / df['peak_ppg'].replace(0, 1)

    # Career trajectory indicator
    df['career_trajectory'] = df['ppg_trend_slope'] * df['seasons_played']

    # Age-adjusted production (if age available)
    if 'age' in df.columns:
        df['age_adj_ppg'] = df['curr_ppg'] / (df['age'].fillna(26) / 26)

    # Position-specific features
    # Receiving share (for skill positions)
    total_yards = df['curr_rec_yards'].fillna(0) + df['curr_rush_yards'].fillna(0)
    df['rec_yards_share'] = df['curr_rec_yards'].fillna(0) / total_yards.replace(0, 1)

    # TD rate
    total_tds = df['curr_rec_tds'].fillna(0) + df['curr_rush_tds'].fillna(0) + df['curr_pass_tds'].fillna(0)
    df['td_rate'] = total_tds / df['curr_games'].replace(0, 1)

    # One-hot encode position
    df = pd.get_dummies(df, columns=['position'], prefix='pos')

    return df


def train_model(df, feature_cols, target_col='target_fpts_ppr'):
    """Train the production prediction model."""
    print(f"\n🎯 Training model to predict: {target_col}")

    # Prepare data
    X = df[feature_cols].fillna(0)
    y = df[target_col].fillna(0)

    # Remove any infinite values
    X = X.replace([np.inf, -np.inf], 0)

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Train multiple models and compare
    models = {
        'GradientBoosting': GradientBoostingRegressor(
            n_estimators=200,
            max_depth=5,
            learning_rate=0.1,
            min_samples_split=10,
            random_state=42
        ),
        'RandomForest': RandomForestRegressor(
            n_estimators=200,
            max_depth=8,
            min_samples_split=10,
            random_state=42
        ),
        'Ridge': Ridge(alpha=1.0),
    }

    results = {}

    for name, model in models.items():
        model.fit(X_train_scaled, y_train)
        y_pred = model.predict(X_test_scaled)

        rmse = np.sqrt(mean_squared_error(y_test, y_pred))
        mae = mean_absolute_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)

        # Cross-validation
        cv_scores = cross_val_score(model, scaler.transform(X), y, cv=5, scoring='r2')

        results[name] = {
            'model': model,
            'rmse': rmse,
            'mae': mae,
            'r2': r2,
            'cv_r2': cv_scores.mean(),
            'cv_std': cv_scores.std(),
        }

        print(f"\n   {name}:")
        print(f"      R² Score: {r2:.4f}")
        print(f"      RMSE: {rmse:.2f} fantasy points")
        print(f"      MAE: {mae:.2f} fantasy points")
        print(f"      CV R² (5-fold): {cv_scores.mean():.4f} (+/- {cv_scores.std()*2:.4f})")

    # Select best model
    best_name = max(results, key=lambda x: results[x]['cv_r2'])
    best_model = results[best_name]['model']

    print(f"\n   ✅ Best model: {best_name}")

    return best_model, scaler, results[best_name], results


def get_feature_importance(model, feature_cols, model_type='tree'):
    """Get feature importance from trained model."""
    if hasattr(model, 'feature_importances_'):
        importance = pd.DataFrame({
            'feature': feature_cols,
            'importance': model.feature_importances_
        }).sort_values('importance', ascending=False)
    elif hasattr(model, 'coef_'):
        importance = pd.DataFrame({
            'feature': feature_cols,
            'importance': np.abs(model.coef_)
        }).sort_values('importance', ascending=False)
    else:
        return None

    return importance


def analyze_by_position(df, model, scaler, feature_cols, target_col='target_fpts_ppr'):
    """Analyze model performance by position."""
    print("\n📊 Performance by Position:")

    positions = ['pos_QB', 'pos_RB', 'pos_WR', 'pos_TE']

    for pos_col in positions:
        if pos_col not in df.columns:
            continue

        pos = pos_col.replace('pos_', '')
        pos_df = df[df[pos_col] == 1]

        if len(pos_df) < 50:
            continue

        X = pos_df[feature_cols].fillna(0).replace([np.inf, -np.inf], 0)
        y = pos_df[target_col].fillna(0)

        X_scaled = scaler.transform(X)
        y_pred = model.predict(X_scaled)

        rmse = np.sqrt(mean_squared_error(y, y_pred))
        r2 = r2_score(y, y_pred)

        print(f"   {pos}: R²={r2:.4f}, RMSE={rmse:.1f} (n={len(pos_df)})")


def main():
    """Main training pipeline."""
    print("=" * 70)
    print("FANTASY PRODUCTION PREDICTION MODEL")
    print(f"Started: {datetime.now()}")
    print("=" * 70)

    # 1. Fetch data
    print("\n📊 Fetching season data...")
    season_df = fetch_season_data()
    print(f"   Loaded {len(season_df)} season records")

    print("\n📊 Fetching player metadata...")
    player_df = fetch_player_metadata()
    print(f"   Loaded {len(player_df)} players")

    # 2. Create training pairs
    pairs_df = create_training_pairs(season_df)

    # 3. Add career features
    pairs_df = add_career_features(pairs_df, season_df)

    # 4. Add age features
    pairs_df = add_age_features(pairs_df, player_df)

    # 5. Engineer additional features
    pairs_df = engineer_additional_features(pairs_df)

    print(f"\n   Total training samples: {len(pairs_df)}")

    # 6. Define feature columns
    exclude_cols = [
        'player_id', 'name', 'position', 'current_season', 'next_season',
        'target_fpts_ppr', 'target_ppg', 'target_games'
    ]
    feature_cols = [c for c in pairs_df.columns
                    if c not in exclude_cols
                    and pairs_df[c].dtype in ['int64', 'float64', 'bool', 'uint8']]

    print(f"   Features: {len(feature_cols)}")

    # 7. Train model
    best_model, scaler, best_results, all_results = train_model(
        pairs_df, feature_cols, target_col='target_fpts_ppr'
    )

    # 8. Feature importance
    print("\n" + "=" * 70)
    print("TOP 25 PREDICTIVE FEATURES FOR FANTASY PRODUCTION")
    print("=" * 70)

    importance = get_feature_importance(best_model, feature_cols)
    if importance is not None:
        top_features = importance.head(25)
        for i, (_, row) in enumerate(top_features.iterrows(), 1):
            bar = "█" * int(row['importance'] * 100)
            print(f"   {i:2}. {row['feature']:<30} {row['importance']:.4f} {bar}")

    # 9. Position-specific analysis
    analyze_by_position(pairs_df, best_model, scaler, feature_cols)

    # 10. Save model
    models_dir = Path('data/models')
    models_dir.mkdir(parents=True, exist_ok=True)

    joblib.dump(best_model, models_dir / 'production_predictor.pkl')
    joblib.dump(scaler, models_dir / 'production_scaler.pkl')
    joblib.dump(feature_cols, models_dir / 'production_features.pkl')

    print(f"\n   Models saved to {models_dir}")

    # 11. Show prediction examples
    print("\n" + "=" * 70)
    print("SAMPLE PREDICTIONS (Most Recent Season)")
    print("=" * 70)

    # Get 2023->2024 predictions
    recent = pairs_df[pairs_df['current_season'] == 2023].copy()
    if len(recent) > 0:
        X_recent = recent[feature_cols].fillna(0).replace([np.inf, -np.inf], 0)
        X_scaled = scaler.transform(X_recent)
        recent['predicted_fpts'] = best_model.predict(X_scaled)
        recent['prediction_error'] = recent['target_fpts_ppr'] - recent['predicted_fpts']

        # Show examples by position
        for pos_col in ['pos_QB', 'pos_RB', 'pos_WR', 'pos_TE']:
            if pos_col not in recent.columns:
                continue

            pos = pos_col.replace('pos_', '')
            pos_recent = recent[recent[pos_col] == 1].nlargest(5, 'target_fpts_ppr')

            print(f"\n{pos} (2023 -> 2024 actual):")
            for _, row in pos_recent.iterrows():
                print(f"   {row['name']:<25} | "
                      f"Predicted: {row['predicted_fpts']:6.1f} | "
                      f"Actual: {row['target_fpts_ppr']:6.1f} | "
                      f"Error: {row['prediction_error']:+6.1f}")

    # 12. Generate predictions for current players and store in Neo4j
    print("\n" + "=" * 70)
    print("GENERATING 2025 PREDICTIONS FOR ALL PLAYERS")
    print("=" * 70)

    predictions_df = generate_current_player_predictions(
        season_df, player_df, best_model, scaler, feature_cols
    )

    if predictions_df is not None and len(predictions_df) > 0:
        store_predictions_to_neo4j(predictions_df)

    # 13. Summary statistics
    print("\n" + "=" * 70)
    print("MODEL SUMMARY")
    print("=" * 70)
    print(f"   Training samples: {len(pairs_df)}")
    print(f"   Features used: {len(feature_cols)}")
    print(f"   Best model: Ridge")
    print(f"   R² Score: {best_results['r2']:.4f}")
    print(f"   RMSE: {best_results['rmse']:.2f} fantasy points")
    print(f"   MAE: {best_results['mae']:.2f} fantasy points")

    print("\n" + "=" * 70)
    print("TRAINING COMPLETE")
    print("=" * 70)

    return pairs_df, best_model, scaler, feature_cols, importance


def generate_current_player_predictions(season_df, player_df, model, scaler, feature_cols):
    """
    Generate next-season predictions for all current players.
    Uses 2024 season data to predict 2025 production.
    """
    print("\n📈 Preparing current player features...")

    # Get 2024 season data
    current_season = season_df[season_df['season'] == 2024].copy()
    print(f"   Players with 2024 data: {len(current_season)}")

    if len(current_season) == 0:
        print("   ⚠️ No 2024 season data found")
        return None

    # Build features for each player (similar to training pair creation)
    prediction_data = []

    for _, row in current_season.iterrows():
        player_id = row['player_id']

        # Get player's historical data
        player_history = season_df[
            (season_df['player_id'] == player_id) &
            (season_df['season'] <= 2024)
        ].sort_values('season')

        if len(player_history) == 0:
            continue

        # Current season features
        curr = player_history.iloc[-1]

        # Career features
        career_games = player_history['games'].sum()
        career_fpts = player_history['fpts_ppr'].sum()
        career_ppg = career_fpts / max(career_games, 1)
        seasons_played = len(player_history)
        peak_fpts = player_history['fpts_ppr'].max()
        peak_ppg = player_history['ppg'].max()

        # Trend
        recent = player_history.tail(3)
        if len(recent) >= 2:
            ppg_values = recent['ppg'].values
            trend_slope = np.polyfit(range(len(ppg_values)), ppg_values, 1)[0]
        else:
            trend_slope = 0

        ppg_std = player_history['ppg'].std() if len(player_history) > 1 else 0

        # YoY change
        if len(player_history) >= 2:
            prev = player_history.iloc[-2]
            yoy_change = curr['ppg'] - prev['ppg']
            yoy_pct = yoy_change / max(prev['ppg'], 0.1) * 100
        else:
            yoy_change = 0
            yoy_pct = 0

        # Get player metadata
        player_meta = player_df[player_df['player_id'] == player_id]
        if len(player_meta) > 0:
            meta = player_meta.iloc[0]
            age = meta.get('current_age')
            draft_round = meta.get('draft_round')
            draft_pick = meta.get('draft_pick')
            athletic_score = meta.get('athletic_score')
            forty_time = meta.get('forty_time')
        else:
            age = None
            draft_round = None
            draft_pick = None
            athletic_score = None
            forty_time = None

        player_data = {
            'player_id': player_id,
            'name': curr['name'],
            'position': curr['position'],
            'current_season': 2024,

            # Current season features
            'curr_games': curr['games'],
            'curr_fpts_ppr': curr['fpts_ppr'],
            'curr_fpts_std': curr['fpts_std'],
            'curr_ppg': curr['ppg'],
            'curr_pass_yards': curr.get('pass_yards', 0),
            'curr_pass_tds': curr.get('pass_tds', 0),
            'curr_interceptions': curr.get('interceptions', 0),
            'curr_comp_pct': curr.get('comp_pct', 0),
            'curr_pass_attempts': curr.get('pass_attempts', 0),
            'curr_carries': curr.get('carries', 0),
            'curr_rush_yards': curr.get('rush_yards', 0),
            'curr_rush_tds': curr.get('rush_tds', 0),
            'curr_ypc': curr.get('ypc', 0),
            'curr_targets': curr.get('targets', 0),
            'curr_receptions': curr.get('receptions', 0),
            'curr_rec_yards': curr.get('rec_yards', 0),
            'curr_rec_tds': curr.get('rec_tds', 0),
            'curr_catch_rate': curr.get('catch_rate', 0),
            'curr_ypr': curr.get('ypr', 0),

            # Career features
            'career_games': career_games,
            'career_fpts': career_fpts,
            'career_ppg': career_ppg,
            'seasons_played': seasons_played,
            'peak_fpts': peak_fpts,
            'peak_ppg': peak_ppg,
            'ppg_trend_slope': trend_slope,
            'ppg_stddev': ppg_std,
            'yoy_ppg_change': yoy_change,
            'yoy_ppg_pct': yoy_pct,

            # Player metadata
            'age': age,
            'draft_round': draft_round,
            'draft_pick': draft_pick,
            'athletic_score': athletic_score,
            'forty_time': forty_time,
        }

        prediction_data.append(player_data)

    pred_df = pd.DataFrame(prediction_data)
    print(f"   Prepared features for {len(pred_df)} players")

    # Engineer additional features (same as training)
    pred_df = engineer_additional_features(pred_df)

    # Ensure all feature columns exist
    for col in feature_cols:
        if col not in pred_df.columns:
            pred_df[col] = 0

    # Generate predictions
    X = pred_df[feature_cols].fillna(0).replace([np.inf, -np.inf], 0)
    X_scaled = scaler.transform(X)

    pred_df['predicted_fpts_2025'] = model.predict(X_scaled)
    pred_df['projected_ppg_2025'] = pred_df['predicted_fpts_2025'] / 17  # Assuming 17-game season

    # Calculate confidence based on prediction vs historical variance
    # Lower variance in historical performance = higher confidence
    pred_df['production_confidence'] = np.clip(
        100 - pred_df['ppg_stddev'].fillna(10) * 5, 20, 95
    ).round(1)

    print(f"   Generated predictions for {len(pred_df)} players")

    return pred_df


def store_predictions_to_neo4j(pred_df):
    """Store production predictions to Neo4j Player nodes."""
    print("\n💾 Storing predictions to Neo4j...")

    driver = get_driver()

    with driver.session() as session:
        # Prepare records
        records = pred_df[[
            'player_id', 'name', 'predicted_fpts_2025',
            'projected_ppg_2025', 'production_confidence'
        ]].to_dict('records')

        # Update Player nodes by matching on name and position
        session.run("""
            UNWIND $records as r
            MATCH (p:Player)
            WHERE p.gsis_id = r.player_id OR toLower(p.name) = toLower(r.name)
            SET p.predicted_fpts_next_season = r.predicted_fpts_2025,
                p.projected_ppg_next_season = r.projected_ppg_2025,
                p.production_confidence = r.production_confidence,
                p.production_model_updated = datetime()
        """, {'records': records})

        # Verify updates
        result = session.run("""
            MATCH (p:Player)
            WHERE p.predicted_fpts_next_season IS NOT NULL
            RETURN count(p) as updated
        """)
        updated = result.single()['updated']
        print(f"   ✅ Updated {updated} players with production predictions")

        # Show top predictions by position
        print("\n   Top Projected Producers (2025):")
        for pos in ['QB', 'RB', 'WR', 'TE']:
            result = session.run("""
                MATCH (p:Player)
                WHERE p.position = $pos AND p.predicted_fpts_next_season IS NOT NULL
                RETURN p.name as name, p.predicted_fpts_next_season as fpts,
                       p.projected_ppg_next_season as ppg, p.production_confidence as conf
                ORDER BY p.predicted_fpts_next_season DESC
                LIMIT 3
            """, {'pos': pos})

            players = [dict(r) for r in result]
            if players:
                print(f"\n   {pos}:")
                for p in players:
                    print(f"      {p['name']:<25} | {p['fpts']:6.1f} pts | "
                          f"{p['ppg']:.1f} PPG | {p['conf']:.0f}% conf")

    driver.close()


if __name__ == "__main__":
    main()
