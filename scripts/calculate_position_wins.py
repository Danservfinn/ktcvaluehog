#!/usr/bin/env python3
"""
Calculate historical position wins and build lifetime wins projection model.

A "position win" occurs when a player scores more fantasy points than the
median player at their position in a given week.

This script:
1. Calculates historical position wins from weekly stats
2. Builds player volatility profiles
3. Creates career length statistics
4. Prepares data for Monte Carlo lifetime wins simulation
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import numpy as np
from scipy import stats
from typing import Dict, List, Tuple, Optional
import logging
import json
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Fantasy-relevant positions
FANTASY_POSITIONS = ['QB', 'RB', 'WR', 'TE']

# Position-specific career length parameters (based on historical data)
CAREER_LENGTH_PARAMS = {
    'QB': {'median': 10, 'std': 4, 'max_age': 45},
    'RB': {'median': 6, 'std': 2.5, 'max_age': 34},
    'WR': {'median': 9, 'std': 3, 'max_age': 38},
    'TE': {'median': 9, 'std': 3, 'max_age': 38},
}

# Age curves - performance multiplier by age (1.0 = peak)
AGE_CURVES = {
    'QB': {21: 0.75, 22: 0.82, 23: 0.88, 24: 0.93, 25: 0.97, 26: 1.0, 27: 1.0,
           28: 1.0, 29: 0.99, 30: 0.98, 31: 0.96, 32: 0.94, 33: 0.91, 34: 0.88,
           35: 0.84, 36: 0.80, 37: 0.75, 38: 0.70, 39: 0.65, 40: 0.60},
    'RB': {21: 0.90, 22: 0.95, 23: 0.98, 24: 1.0, 25: 1.0, 26: 0.97, 27: 0.92,
           28: 0.85, 29: 0.77, 30: 0.68, 31: 0.58, 32: 0.48, 33: 0.38, 34: 0.28},
    'WR': {21: 0.80, 22: 0.85, 23: 0.90, 24: 0.94, 25: 0.97, 26: 1.0, 27: 1.0,
           28: 0.98, 29: 0.95, 30: 0.91, 31: 0.86, 32: 0.80, 33: 0.73, 34: 0.65,
           35: 0.56, 36: 0.47, 37: 0.38},
    'TE': {21: 0.70, 22: 0.78, 23: 0.85, 24: 0.91, 25: 0.96, 26: 0.99, 27: 1.0,
           28: 1.0, 29: 0.98, 30: 0.95, 31: 0.90, 32: 0.84, 33: 0.77, 34: 0.69,
           35: 0.60, 36: 0.51, 37: 0.42},
}


def load_weekly_stats() -> pd.DataFrame:
    """Load weekly fantasy stats from nflverse data."""
    logger.info("Loading weekly stats...")

    data_path = PROJECT_ROOT / "data" / "nflverse" / "player_stats_all.parquet"
    if not data_path.exists():
        raise FileNotFoundError(f"Weekly stats not found: {data_path}")

    df = pd.read_parquet(data_path)

    # Filter to fantasy positions and regular season
    df = df[df['position'].isin(FANTASY_POSITIONS)].copy()
    df = df[df['season_type'] == 'REG'].copy()

    # Clean data
    df = df.dropna(subset=['fantasy_points_ppr', 'player_id'])
    df = df[df['fantasy_points_ppr'] >= 0]

    logger.info(f"  Loaded {len(df):,} weekly records ({df['season'].min()}-{df['season'].max()})")

    return df


def calculate_position_baselines(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate weekly position baselines (median of starters)."""
    logger.info("Calculating position baselines...")

    # Define starter thresholds per position (top N players)
    starter_counts = {'QB': 32, 'RB': 48, 'WR': 64, 'TE': 32}

    baselines = []

    for (season, week, position), group in df.groupby(['season', 'week', 'position']):
        # Get top N players by fantasy points (starters)
        n_starters = starter_counts.get(position, 32)
        top_players = group.nlargest(n_starters, 'fantasy_points_ppr')

        baseline = {
            'season': season,
            'week': week,
            'position': position,
            'baseline_median': top_players['fantasy_points_ppr'].median(),
            'baseline_mean': top_players['fantasy_points_ppr'].mean(),
            'baseline_std': top_players['fantasy_points_ppr'].std(),
            'baseline_p25': top_players['fantasy_points_ppr'].quantile(0.25),
            'baseline_p75': top_players['fantasy_points_ppr'].quantile(0.75),
            'n_players': len(group),
            'n_starters': len(top_players),
        }
        baselines.append(baseline)

    baseline_df = pd.DataFrame(baselines)
    logger.info(f"  Generated {len(baseline_df):,} weekly baselines")

    return baseline_df


def calculate_position_wins(df: pd.DataFrame, baseline_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate position wins for each player-week."""
    logger.info("Calculating position wins...")

    # Merge baselines
    df = df.merge(
        baseline_df[['season', 'week', 'position', 'baseline_median', 'baseline_mean', 'baseline_std']],
        on=['season', 'week', 'position'],
        how='left'
    )

    # Calculate position win (beat the median)
    df['position_win'] = (df['fantasy_points_ppr'] > df['baseline_median']).astype(int)

    # Calculate margin (how much they won/lost by)
    df['win_margin'] = df['fantasy_points_ppr'] - df['baseline_median']

    # Calculate z-score (performance vs baseline)
    df['performance_zscore'] = (df['fantasy_points_ppr'] - df['baseline_mean']) / df['baseline_std'].replace(0, 1)

    wins = df['position_win'].sum()
    total = len(df)
    logger.info(f"  Position wins: {wins:,} / {total:,} ({wins/total*100:.1f}%)")

    return df


def build_player_profiles(df: pd.DataFrame) -> pd.DataFrame:
    """Build player profiles with volatility and career stats."""
    logger.info("Building player profiles...")

    profiles = []

    for player_id, player_df in df.groupby('player_id'):
        if len(player_df) < 4:  # Need minimum games for stats
            continue

        # Get player info from most recent season
        latest = player_df.loc[player_df['season'].idxmax()]

        # Career stats
        career_seasons = player_df['season'].nunique()
        career_games = len(player_df)
        first_season = player_df['season'].min()
        last_season = player_df['season'].max()

        # Fantasy performance
        career_ppg = player_df['fantasy_points_ppr'].mean()
        career_std = player_df['fantasy_points_ppr'].std()
        career_median = player_df['fantasy_points_ppr'].median()

        # Position wins
        total_wins = player_df['position_win'].sum()
        win_rate = total_wins / len(player_df)

        # Per-season breakdown
        season_stats = player_df.groupby('season').agg({
            'fantasy_points_ppr': ['mean', 'std', 'count'],
            'position_win': 'sum',
            'win_margin': 'mean'
        })

        # Best season
        season_ppg = player_df.groupby('season')['fantasy_points_ppr'].mean()
        best_season = season_ppg.idxmax()
        best_ppg = season_ppg.max()

        # Volatility metrics
        cv = career_std / career_ppg if career_ppg > 0 else 0  # Coefficient of variation

        # Boom/bust rates
        boom_threshold = career_ppg * 1.5
        bust_threshold = career_ppg * 0.5
        boom_rate = (player_df['fantasy_points_ppr'] >= boom_threshold).mean()
        bust_rate = (player_df['fantasy_points_ppr'] <= bust_threshold).mean()

        profile = {
            'player_id': player_id,
            'player_name': latest.get('player_name') or latest.get('player_display_name'),
            'position': latest['position'],
            'first_season': first_season,
            'last_season': last_season,
            'career_seasons': career_seasons,
            'career_games': career_games,
            'career_ppg': career_ppg,
            'career_std': career_std,
            'career_median': career_median,
            'career_cv': cv,
            'total_position_wins': total_wins,
            'position_win_rate': win_rate,
            'best_season': best_season,
            'best_season_ppg': best_ppg,
            'boom_rate': boom_rate,
            'bust_rate': bust_rate,
            'games_per_season': career_games / career_seasons,
        }
        profiles.append(profile)

    profile_df = pd.DataFrame(profiles)
    logger.info(f"  Built {len(profile_df):,} player profiles")

    return profile_df


def calculate_career_length_stats(profile_df: pd.DataFrame) -> Dict:
    """Calculate career length statistics by position and tier."""
    logger.info("Calculating career length statistics...")

    # Only use "completed" careers (last season before 2023)
    completed = profile_df[profile_df['last_season'] < 2023].copy()

    stats = {}
    for position in FANTASY_POSITIONS:
        pos_df = completed[completed['position'] == position]

        if len(pos_df) < 10:
            continue

        # Overall stats
        stats[position] = {
            'n_players': len(pos_df),
            'median_seasons': pos_df['career_seasons'].median(),
            'mean_seasons': pos_df['career_seasons'].mean(),
            'std_seasons': pos_df['career_seasons'].std(),
            'median_games': pos_df['career_games'].median(),
            'mean_games_per_season': pos_df['games_per_season'].mean(),
        }

        # By performance tier
        pos_df['ppg_percentile'] = pos_df['career_ppg'].rank(pct=True)

        for tier, (low, high) in [('elite', (0.9, 1.0)), ('good', (0.7, 0.9)),
                                   ('average', (0.4, 0.7)), ('below_avg', (0.0, 0.4))]:
            tier_df = pos_df[(pos_df['ppg_percentile'] >= low) & (pos_df['ppg_percentile'] < high)]
            if len(tier_df) >= 5:
                stats[position][f'{tier}_median_seasons'] = tier_df['career_seasons'].median()
                stats[position][f'{tier}_mean_games_per_season'] = tier_df['games_per_season'].mean()

    logger.info(f"  Career stats calculated for {len(stats)} positions")

    return stats


def calculate_win_probability_model(df: pd.DataFrame, profile_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate win probability parameters for each player."""
    logger.info("Building win probability model...")

    # Get recent performance (last 2 seasons)
    recent_df = df[df['season'] >= df['season'].max() - 1]

    recent_stats = recent_df.groupby('player_id').agg({
        'fantasy_points_ppr': ['mean', 'std', 'count'],
        'position_win': 'mean',
        'win_margin': 'mean',
        'baseline_median': 'mean'
    }).reset_index()

    recent_stats.columns = ['player_id', 'recent_ppg', 'recent_std', 'recent_games',
                            'recent_win_rate', 'recent_margin', 'recent_baseline']

    # Merge with profiles
    model_df = profile_df.merge(recent_stats, on='player_id', how='left')

    # Use recent stats if available, else career stats
    model_df['projected_ppg'] = model_df['recent_ppg'].fillna(model_df['career_ppg'])
    model_df['projected_std'] = model_df['recent_std'].fillna(model_df['career_std'])
    model_df['projected_win_rate'] = model_df['recent_win_rate'].fillna(model_df['position_win_rate'])

    # Calculate analytical win probability
    # P(player > baseline) where player ~ N(mu_p, sigma_p) and baseline ~ N(mu_b, sigma_b)
    # P(X > Y) = Phi((mu_p - mu_b) / sqrt(sigma_p^2 + sigma_b^2))

    # Get position baselines
    baseline_stats = df.groupby('position').agg({
        'baseline_median': 'mean',
        'baseline_std': 'mean'
    }).reset_index()
    baseline_stats.columns = ['position', 'pos_baseline_mean', 'pos_baseline_std']

    model_df = model_df.merge(baseline_stats, on='position', how='left')

    # Calculate analytical win probability
    combined_std = np.sqrt(model_df['projected_std']**2 + model_df['pos_baseline_std']**2)
    combined_std = combined_std.replace(0, 1)  # Avoid division by zero

    z_score = (model_df['projected_ppg'] - model_df['pos_baseline_mean']) / combined_std
    model_df['analytical_win_prob'] = stats.norm.cdf(z_score)

    # Blend analytical and empirical
    model_df['win_prob'] = (
        0.6 * model_df['analytical_win_prob'] +
        0.4 * model_df['projected_win_rate']
    )

    logger.info(f"  Win probability model built for {len(model_df):,} players")

    return model_df


def simulate_lifetime_wins(
    player_id: str,
    position: str,
    current_age: int,
    projected_ppg: float,
    projected_std: float,
    win_prob: float,
    games_per_season: float = 14.5,
    n_simulations: int = 10000,
    baseline_mean: float = None,
    baseline_std: float = None,
    is_established: bool = False
) -> Dict:
    """
    Monte Carlo simulation of lifetime position wins.

    Returns distribution of total career wins remaining.
    """
    # Position-specific baselines (from historical data)
    POSITION_BASELINES = {
        'QB': {'mean': 13.85, 'std': 6.5},
        'RB': {'mean': 11.08, 'std': 5.5},
        'WR': {'mean': 11.90, 'std': 5.0},
        'TE': {'mean': 7.98, 'std': 4.5},
    }

    if baseline_mean is None:
        baseline_mean = POSITION_BASELINES.get(position, {'mean': 11.0})['mean']
    if baseline_std is None:
        baseline_std = POSITION_BASELINES.get(position, {'std': 5.0})['std']

    career_params = CAREER_LENGTH_PARAMS.get(position, CAREER_LENGTH_PARAMS['WR'])
    age_curve = AGE_CURVES.get(position, AGE_CURVES['WR'])
    max_age = career_params['max_age']

    # Minimum seasons based on player type
    min_seasons = 2 if is_established else 1

    wins_samples = []
    seasons_samples = []
    yearly_wins = []

    for sim in range(n_simulations):
        total_wins = 0
        seasons_played = 0
        age = current_age
        sim_yearly = []

        while age <= max_age:
            years_since_22 = max(0, age - 22)

            # Retirement probability - more nuanced
            if seasons_played < min_seasons:
                # Young/established players very unlikely to retire early
                continue_prob = 0.98
            else:
                # Base continuation probability by position
                if position == 'RB':
                    base_prob = 0.82
                    age_penalty = 0.07 * max(0, age - 26)  # RBs decline after 26
                else:
                    base_prob = 0.88
                    age_penalty = 0.04 * max(0, age - 30)  # Others decline after 30

                continue_prob = max(0.15, base_prob - age_penalty)

            if np.random.random() > continue_prob:
                break

            # Sample games played this season
            injury_risk = 0.02 * years_since_22
            expected_games = games_per_season * (1 - injury_risk)
            games = max(1, int(np.random.normal(expected_games, 2.5)))
            games = min(games, 17)

            # Age curve adjustment
            age_mult = age_curve.get(age, age_curve.get(max(age_curve.keys()), 0.4))
            adjusted_ppg = projected_ppg * age_mult
            adjusted_std = projected_std * (1 + 0.05 * years_since_22)

            # Win probability adjusted for age decline
            base_win_prob = stats.norm.cdf(
                (adjusted_ppg - baseline_mean) /
                np.sqrt(adjusted_std**2 + baseline_std**2)
            )

            # Simulate wins this season
            season_wins = np.random.binomial(games, base_win_prob)
            total_wins += season_wins
            sim_yearly.append(season_wins)

            seasons_played += 1
            age += 1

        wins_samples.append(total_wins)
        seasons_samples.append(seasons_played)
        yearly_wins.append(sim_yearly)

    wins_array = np.array(wins_samples)
    seasons_array = np.array(seasons_samples)

    # Calculate per-season breakdown (for first 10 seasons)
    max_seasons_to_track = 10
    yearly_means = []
    for s in range(max_seasons_to_track):
        season_wins = [yw[s] if len(yw) > s else 0 for yw in yearly_wins]
        yearly_means.append(float(np.mean(season_wins)))

    return {
        'player_id': player_id,
        'position': position,
        'current_age': current_age,
        'lifetime_wins_mean': float(np.mean(wins_array)),
        'lifetime_wins_median': float(np.median(wins_array)),
        'lifetime_wins_std': float(np.std(wins_array)),
        'lifetime_wins_p10': float(np.percentile(wins_array, 10)),
        'lifetime_wins_p25': float(np.percentile(wins_array, 25)),
        'lifetime_wins_p75': float(np.percentile(wins_array, 75)),
        'lifetime_wins_p90': float(np.percentile(wins_array, 90)),
        'seasons_remaining_mean': float(np.mean(seasons_array)),
        'seasons_remaining_median': float(np.median(seasons_array)),
        'wins_per_season': float(np.mean(wins_array) / max(1, np.mean(seasons_array))),
        'yearly_wins_projection': yearly_means,
    }


def project_all_players(
    model_df: pd.DataFrame,
    current_season: int = 2024,
    include_rookies: bool = True
) -> pd.DataFrame:
    """Project lifetime wins for all active players."""
    logger.info("Projecting lifetime wins for all players...")

    # Filter to recently active players
    active_df = model_df[model_df['last_season'] >= current_season - 1].copy()

    # Estimate current age (rough approximation)
    active_df['estimated_age'] = current_season - active_df['first_season'] + 22

    # Mark established players (3+ seasons in league)
    active_df['is_established'] = (current_season - active_df['first_season']) >= 3

    projections = []

    for _, player in active_df.iterrows():
        try:
            projection = simulate_lifetime_wins(
                player_id=player['player_id'],
                position=player['position'],
                current_age=int(player['estimated_age']),
                projected_ppg=player['projected_ppg'],
                projected_std=player['projected_std'],
                win_prob=player['win_prob'],
                games_per_season=player.get('games_per_season', 14.5),
                n_simulations=5000,
                is_established=bool(player['is_established'])
            )
            projection['player_name'] = player['player_name']
            projection['career_wins_to_date'] = player['total_position_wins']
            projection['career_win_rate'] = player['position_win_rate']
            projection['projected_ppg'] = player['projected_ppg']
            projection['is_rookie'] = False
            projections.append(projection)
        except Exception as e:
            logger.warning(f"  Failed for {player['player_name']}: {e}")

    # Add 2025 rookie class projections
    if include_rookies:
        rookies = get_2025_rookie_projections()
        for rookie in rookies:
            try:
                projection = simulate_lifetime_wins(
                    player_id=rookie['player_id'],
                    position=rookie['position'],
                    current_age=rookie['age'],
                    projected_ppg=rookie['projected_ppg'],
                    projected_std=rookie['projected_std'],
                    win_prob=0.5,  # Default for rookies
                    games_per_season=rookie.get('expected_games', 14.0),
                    n_simulations=5000,
                    is_established=False
                )
                projection['player_name'] = rookie['player_name']
                projection['career_wins_to_date'] = 0
                projection['career_win_rate'] = None
                projection['projected_ppg'] = rookie['projected_ppg']
                projection['is_rookie'] = True
                projections.append(projection)
            except Exception as e:
                logger.warning(f"  Failed for rookie {rookie['player_name']}: {e}")

    projection_df = pd.DataFrame(projections)

    # Sort by expected lifetime wins
    projection_df = projection_df.sort_values('lifetime_wins_mean', ascending=False)

    logger.info(f"  Projected lifetime wins for {len(projection_df):,} players")

    return projection_df


def get_2025_rookie_projections() -> List[Dict]:
    """
    Get projected 2025 rookie class for position wins modeling.
    Based on dynasty consensus rankings and college production.
    """
    # Top 2025 rookies with projected NFL stats
    rookies = [
        # RBs
        {'player_id': 'rookie_jeanty', 'player_name': 'Ashton Jeanty', 'position': 'RB',
         'age': 21, 'projected_ppg': 16.5, 'projected_std': 7.0, 'expected_games': 15,
         'notes': 'Boise State, Heisman finalist, elite prospect'},
        {'player_id': 'rookie_sanders', 'player_name': 'Omarion Hampton', 'position': 'RB',
         'age': 21, 'projected_ppg': 13.0, 'projected_std': 6.0, 'expected_games': 14},
        {'player_id': 'rookie_johnson', 'player_name': 'Kaleb Johnson', 'position': 'RB',
         'age': 21, 'projected_ppg': 11.5, 'projected_std': 5.5, 'expected_games': 13},

        # WRs
        {'player_id': 'rookie_coleman', 'player_name': 'Luther Burden III', 'position': 'WR',
         'age': 21, 'projected_ppg': 12.0, 'projected_std': 5.5, 'expected_games': 15},
        {'player_id': 'rookie_ware', 'player_name': 'Tetairoa McMillan', 'position': 'WR',
         'age': 21, 'projected_ppg': 11.5, 'projected_std': 5.0, 'expected_games': 15},
        {'player_id': 'rookie_hunter', 'player_name': 'Travis Hunter', 'position': 'WR',
         'age': 21, 'projected_ppg': 13.5, 'projected_std': 6.0, 'expected_games': 15,
         'notes': 'Heisman winner, two-way player'},
        {'player_id': 'rookie_egbuka', 'player_name': 'Emeka Egbuka', 'position': 'WR',
         'age': 22, 'projected_ppg': 10.5, 'projected_std': 4.5, 'expected_games': 14},

        # TEs
        {'player_id': 'rookie_ffrench', 'player_name': 'Tyler Warren', 'position': 'TE',
         'age': 22, 'projected_ppg': 9.5, 'projected_std': 4.5, 'expected_games': 14},
        {'player_id': 'rookie_loveland', 'player_name': 'Colston Loveland', 'position': 'TE',
         'age': 21, 'projected_ppg': 8.5, 'projected_std': 4.0, 'expected_games': 13},

        # QBs
        {'player_id': 'rookie_ward', 'player_name': 'Cam Ward', 'position': 'QB',
         'age': 22, 'projected_ppg': 17.0, 'projected_std': 6.5, 'expected_games': 14},
        {'player_id': 'rookie_sanders', 'player_name': 'Shedeur Sanders', 'position': 'QB',
         'age': 22, 'projected_ppg': 16.0, 'projected_std': 6.0, 'expected_games': 14},
    ]

    logger.info(f"  Added {len(rookies)} 2025 rookie projections")
    return rookies


def main():
    """Main pipeline for position wins calculation."""
    logger.info("="*70)
    logger.info("POSITION WINS CALCULATION PIPELINE")
    logger.info("="*70)

    # Step 1: Load weekly stats
    weekly_df = load_weekly_stats()

    # Step 2: Calculate position baselines
    baseline_df = calculate_position_baselines(weekly_df)

    # Step 3: Calculate position wins
    weekly_df = calculate_position_wins(weekly_df, baseline_df)

    # Step 4: Build player profiles
    profile_df = build_player_profiles(weekly_df)

    # Step 5: Calculate career length statistics
    career_stats = calculate_career_length_stats(profile_df)

    # Step 6: Build win probability model
    model_df = calculate_win_probability_model(weekly_df, profile_df)

    # Step 7: Project lifetime wins
    projection_df = project_all_players(model_df)

    # Save outputs
    output_dir = PROJECT_ROOT / "data" / "position_wins"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save weekly data with position wins
    weekly_df.to_parquet(output_dir / "weekly_stats_with_wins.parquet", index=False)
    logger.info(f"  Saved weekly stats to {output_dir / 'weekly_stats_with_wins.parquet'}")

    # Save player profiles
    profile_df.to_parquet(output_dir / "player_profiles.parquet", index=False)
    logger.info(f"  Saved player profiles to {output_dir / 'player_profiles.parquet'}")

    # Save model data
    model_df.to_parquet(output_dir / "win_probability_model.parquet", index=False)
    logger.info(f"  Saved win model to {output_dir / 'win_probability_model.parquet'}")

    # Save projections
    projection_df.to_parquet(output_dir / "lifetime_wins_projections.parquet", index=False)
    logger.info(f"  Saved projections to {output_dir / 'lifetime_wins_projections.parquet'}")

    # Save career stats as JSON
    with open(output_dir / "career_length_stats.json", 'w') as f:
        json.dump(career_stats, f, indent=2)

    # Print top projections
    print("\n" + "="*70)
    print("TOP 25 LIFETIME POSITION WINS PROJECTIONS")
    print("="*70)

    top_cols = ['player_name', 'position', 'current_age', 'lifetime_wins_mean',
                'lifetime_wins_p10', 'lifetime_wins_p90', 'career_wins_to_date']

    print(projection_df[top_cols].head(25).to_string(index=False))

    # Position breakdown
    print("\n" + "="*70)
    print("TOP 5 BY POSITION")
    print("="*70)

    for pos in FANTASY_POSITIONS:
        pos_df = projection_df[projection_df['position'] == pos].head(5)
        print(f"\n{pos}:")
        print(pos_df[['player_name', 'current_age', 'lifetime_wins_mean',
                      'lifetime_wins_p90']].to_string(index=False))

    logger.info("\n" + "="*70)
    logger.info("PIPELINE COMPLETE")
    logger.info("="*70)

    return 0


if __name__ == '__main__':
    sys.exit(main())
