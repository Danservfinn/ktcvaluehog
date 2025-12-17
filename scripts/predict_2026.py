#!/usr/bin/env python3
"""
2026 Season Projection Script
==============================
Use trained ML models to predict 2026 fantasy production for current players.

Usage:
    python scripts/predict_2026.py                    # Full predictions
    python scripts/predict_2026.py --top 20          # Top N players
    python scripts/predict_2026.py --position WR     # Filter by position
    python scripts/predict_2026.py --undervalued     # Show undervalued players
"""

import os
import sys
import argparse
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from neo4j import GraphDatabase
import pandas as pd
import numpy as np

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_driver():
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")
    auth = (user, password) if user and password else None
    return GraphDatabase.driver(uri, auth=auth)


def get_2025_season_stats(driver) -> pd.DataFrame:
    """Get 2025 season stats for all players."""
    query = """
    MATCH (ss:SeasonStats {season: 2025})
    WHERE ss.position IN ['QB', 'RB', 'WR', 'TE']
      AND ss.games >= 5
    OPTIONAL MATCH (p:Player)-[:HAD_SEASON]->(ss)

    // Get career history from historical data
    OPTIONAL MATCH (hist:HistoricalSeasonStats)
    WHERE hist.player_id = p.sleeper_id
      AND hist.season < 2025
      AND hist.games >= 8
    WITH ss, p, collect(hist) as prior_seasons

    RETURN ss.player_name as player_name,
           ss.position as position,
           ss.team as team,
           ss.games as games,
           ss.ppg_ppr as ppg_ppr,
           ss.ppg_std as ppg_std,

           // Stats
           ss.passing_yards as passing_yards,
           ss.passing_tds as passing_tds,
           ss.interceptions as interceptions,
           ss.carries as carries,
           ss.rushing_yards as rushing_yards,
           ss.rushing_tds as rushing_tds,
           ss.targets as targets,
           ss.receptions as receptions,
           ss.receiving_yards as receiving_yards,
           ss.receiving_tds as receiving_tds,

           // KTC value
           p.ktc_value as ktc_value,
           p.production_edge_score as edge_score,
           p.production_signal as signal,

           // Career context
           size(prior_seasons) as years_in_league,
           CASE WHEN size(prior_seasons) > 0
                THEN reduce(s=0.0, h IN prior_seasons | s + h.ppg_ppr) / size(prior_seasons)
                ELSE 0 END as career_ppg,
           CASE WHEN size(prior_seasons) > 0
                THEN reduce(mx=0.0, h IN prior_seasons | CASE WHEN h.ppg_ppr > mx THEN h.ppg_ppr ELSE mx END)
                ELSE 0 END as best_season_ppg

    ORDER BY ss.ppg_ppr DESC
    """

    with driver.session() as session:
        result = session.run(query)
        records = [dict(r) for r in result]

    return pd.DataFrame(records)


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add engineered features matching the training data."""
    df = df.copy()

    # Per-game stats
    df['targets_per_game'] = df['targets'] / df['games'].replace(0, np.nan)
    df['receptions_per_game'] = df['receptions'] / df['games'].replace(0, np.nan)
    df['rec_yards_per_game'] = df['receiving_yards'] / df['games'].replace(0, np.nan)
    df['carries_per_game'] = df['carries'] / df['games'].replace(0, np.nan)
    df['rush_yards_per_game'] = df['rushing_yards'] / df['games'].replace(0, np.nan)

    # Efficiency
    df['catch_rate'] = df['receptions'] / df['targets'].replace(0, np.nan)
    df['yards_per_catch'] = df['receiving_yards'] / df['receptions'].replace(0, np.nan)
    df['yards_per_carry'] = df['rushing_yards'] / df['carries'].replace(0, np.nan)

    # Career comparison
    df['ppg_vs_career_avg'] = df['ppg_ppr'] - df['career_ppg']
    df['ppg_vs_best'] = df['ppg_ppr'] - df['best_season_ppg']

    # TD rates
    df['rec_td_rate'] = df['receiving_tds'] / df['targets'].replace(0, np.nan)
    df['rush_td_rate'] = df['rushing_tds'] / df['carries'].replace(0, np.nan)

    # Team share features (approximate - set to 0 if not available)
    df['target_share_calc'] = 0.0
    df['carry_share'] = 0.0
    df['opportunity_share'] = 0.0
    df['rec_yards_share'] = 0.0
    df['rush_yards_share'] = 0.0

    # Age curve features (estimate from years_in_league)
    df['estimated_age'] = 22 + df['years_in_league'].fillna(0)

    # Position-specific age curves
    POSITION_PEAKS = {
        'QB': {'peak_start': 27, 'peak_end': 35, 'cliff_age': 38},
        'RB': {'peak_start': 23, 'peak_end': 26, 'cliff_age': 28},
        'WR': {'peak_start': 25, 'peak_end': 29, 'cliff_age': 31},
        'TE': {'peak_start': 26, 'peak_end': 30, 'cliff_age': 32}
    }

    def calc_age_features(row):
        pos = row.get('position')
        age = row.get('estimated_age', 22)
        if pos not in POSITION_PEAKS:
            return pd.Series({'years_to_peak': 0, 'years_from_cliff': 10, 'in_prime_window': 0,
                            'age_decline_risk': 0, 'age_score': 80})
        peaks = POSITION_PEAKS[pos]
        years_to_peak = peaks['peak_start'] - age
        years_from_cliff = peaks['cliff_age'] - age
        in_prime = 1 if peaks['peak_start'] <= age <= peaks['peak_end'] else 0

        if age < peaks['peak_start']:
            decline_risk = 0
            age_score = 100 - (peaks['peak_start'] - age) * 5
        elif age <= peaks['peak_end']:
            decline_risk = 0.1
            age_score = 90 - (age - peaks['peak_start']) * 2
        elif age <= peaks['cliff_age']:
            decline_risk = 0.1 + 0.6 * (age - peaks['peak_end']) / (peaks['cliff_age'] - peaks['peak_end'])
            age_score = max(0, 80 - (age - peaks['peak_end']) * 10)
        else:
            decline_risk = 0.7 + 0.3 * min((age - peaks['cliff_age']) / 3, 1)
            age_score = max(0, 80 - (age - peaks['peak_end']) * 10)

        return pd.Series({'years_to_peak': years_to_peak, 'years_from_cliff': years_from_cliff,
                         'in_prime_window': in_prime, 'age_decline_risk': decline_risk, 'age_score': age_score})

    age_features = df.apply(calc_age_features, axis=1)
    df = pd.concat([df, age_features], axis=1)

    # Surge detection features (set to neutral values for prediction)
    df['first_half_ppg'] = df['ppg_ppr'] * 0.95  # Estimate
    df['second_half_ppg'] = df['ppg_ppr'] * 1.05  # Estimate
    df['ppg_surge'] = df['second_half_ppg'] - df['first_half_ppg']
    df['ppg_surge_pct'] = (df['ppg_surge'] / df['first_half_ppg'].replace(0, np.nan)) * 100
    df['target_surge'] = 0.0
    df['is_surging'] = 0
    df['is_fading'] = 0
    df['hot_finish'] = 0

    return df


def predict_2026(df: pd.DataFrame) -> pd.DataFrame:
    """Add 2026 predictions using trained model."""
    from src.ml.fantasy_models import SeasonProjectionModel

    model_path = Path('models/season_projection_model.pkl')
    if not model_path.exists():
        raise FileNotFoundError("Model not found. Run train_models.py first.")

    model = SeasonProjectionModel.load(str(model_path))

    # Make predictions
    predictions = model.predict(df)
    df['predicted_2026_ppg'] = predictions

    # Calculate value metrics
    df['ppg_change'] = df['predicted_2026_ppg'] - df['ppg_ppr']
    df['ppg_change_pct'] = (df['ppg_change'] / df['ppg_ppr'].replace(0, np.nan)) * 100

    return df


def calculate_value_gap(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate gap between predicted production and KTC value."""
    df = df.copy()

    # Expected KTC based on predicted PPG (simple linear model)
    # Elite (20+ PPG) = 8000+ KTC, Starter (15 PPG) = 5000 KTC, etc.
    position_multipliers = {'QB': 350, 'RB': 400, 'WR': 450, 'TE': 500}

    df['expected_ktc'] = df.apply(
        lambda row: row['predicted_2026_ppg'] * position_multipliers.get(row['position'], 400),
        axis=1
    )

    # Value gap (positive = undervalued)
    df['ktc_gap'] = df['expected_ktc'] - df['ktc_value'].fillna(0)
    df['ktc_gap_pct'] = (df['ktc_gap'] / df['ktc_value'].replace(0, np.nan)) * 100

    return df


def main():
    parser = argparse.ArgumentParser(description='2026 Season Predictions')
    parser.add_argument('--top', type=int, default=30, help='Show top N players')
    parser.add_argument('--position', type=str, help='Filter by position (QB, RB, WR, TE)')
    parser.add_argument('--undervalued', action='store_true', help='Show undervalued players')
    parser.add_argument('--overvalued', action='store_true', help='Show overvalued players')
    parser.add_argument('--risers', action='store_true', help='Show biggest projected risers')

    args = parser.parse_args()

    driver = get_driver()

    try:
        # Get 2025 data
        logger.info("Loading 2025 season stats...")
        df = get_2025_season_stats(driver)
        logger.info(f"Found {len(df)} players with 2025 stats")

        # Engineer features
        df = engineer_features(df)

        # Predict 2026
        logger.info("Predicting 2026 fantasy production...")
        df = predict_2026(df)

        # Calculate value gaps
        df = calculate_value_gap(df)

        # Filter by position if specified
        if args.position:
            df = df[df['position'] == args.position.upper()]

        # Display results
        print("\n" + "=" * 90)
        print("2026 FANTASY PROJECTION MODEL - PREDICTIONS")
        print("=" * 90)

        if args.undervalued:
            # Show undervalued players (high predicted PPG, low KTC)
            print("\nMOST UNDERVALUED PLAYERS (High Production, Low Value):")
            print("-" * 90)
            df_sorted = df[df['ktc_value'] > 0].sort_values('ktc_gap', ascending=False).head(args.top)

            print(f"{'Player':25} {'Pos':3} {'2025 PPG':>8} {'2026 Pred':>10} {'KTC':>7} {'Gap':>8} {'Signal':>10}")
            print("-" * 90)
            for _, row in df_sorted.iterrows():
                signal = row['signal'] or ''
                print(f"{row['player_name']:25} {row['position']:3} "
                      f"{row['ppg_ppr']:8.1f} {row['predicted_2026_ppg']:10.1f} "
                      f"{int(row['ktc_value'] or 0):>7,} {int(row['ktc_gap']):>+8,} {signal:>10}")

        elif args.overvalued:
            # Show overvalued players
            print("\nMOST OVERVALUED PLAYERS (Low Production, High Value):")
            print("-" * 90)
            df_sorted = df[df['ktc_value'] > 0].sort_values('ktc_gap', ascending=True).head(args.top)

            print(f"{'Player':25} {'Pos':3} {'2025 PPG':>8} {'2026 Pred':>10} {'KTC':>7} {'Gap':>8} {'Signal':>10}")
            print("-" * 90)
            for _, row in df_sorted.iterrows():
                signal = row['signal'] or ''
                print(f"{row['player_name']:25} {row['position']:3} "
                      f"{row['ppg_ppr']:8.1f} {row['predicted_2026_ppg']:10.1f} "
                      f"{int(row['ktc_value'] or 0):>7,} {int(row['ktc_gap']):>+8,} {signal:>10}")

        elif args.risers:
            # Show biggest predicted risers
            print("\nBIGGEST PROJECTED RISERS (2025 -> 2026):")
            print("-" * 90)
            df_sorted = df.sort_values('ppg_change', ascending=False).head(args.top)

            print(f"{'Player':25} {'Pos':3} {'2025 PPG':>8} {'2026 Pred':>10} {'Change':>8} {'Change %':>9}")
            print("-" * 90)
            for _, row in df_sorted.iterrows():
                print(f"{row['player_name']:25} {row['position']:3} "
                      f"{row['ppg_ppr']:8.1f} {row['predicted_2026_ppg']:10.1f} "
                      f"{row['ppg_change']:>+8.1f} {row['ppg_change_pct']:>+8.1f}%")

        else:
            # Default: Show top predicted 2026 performers
            print(f"\nTOP {args.top} PROJECTED 2026 FANTASY PERFORMERS:")
            print("-" * 90)
            df_sorted = df.sort_values('predicted_2026_ppg', ascending=False).head(args.top)

            print(f"{'Player':25} {'Pos':3} {'Team':4} {'2025 PPG':>8} {'2026 Pred':>10} {'Change':>8} {'KTC':>7}")
            print("-" * 90)
            for _, row in df_sorted.iterrows():
                team = row['team'] or '???'
                ktc = int(row['ktc_value']) if pd.notna(row['ktc_value']) else 0
                print(f"{row['player_name']:25} {row['position']:3} {team:4} "
                      f"{row['ppg_ppr']:8.1f} {row['predicted_2026_ppg']:10.1f} "
                      f"{row['ppg_change']:>+8.1f} {ktc:>7,}")

        # Summary stats
        print("\n" + "=" * 90)
        print("SUMMARY STATISTICS")
        print("-" * 90)
        for pos in ['QB', 'RB', 'WR', 'TE']:
            pos_df = df[df['position'] == pos]
            if len(pos_df) > 0:
                avg_change = pos_df['ppg_change'].mean()
                print(f"  {pos}: Avg Predicted Change = {avg_change:+.2f} PPG ({len(pos_df)} players)")

    finally:
        driver.close()


if __name__ == "__main__":
    main()
