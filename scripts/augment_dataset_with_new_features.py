#!/usr/bin/env python3
"""
Augment existing ML training dataset with new defense and coaching features.

This script adds the new features from cached PBP data without needing
to rebuild the entire dataset from Neo4j.
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import numpy as np
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def add_defense_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add opponent defense quality features from cached PBP data."""
    logger.info("Adding defense matchup features...")

    cache_dir = Path('data/defense_cache')
    cache_files = list(cache_dir.glob('pbp_defense_*.parquet'))

    if not cache_files:
        logger.warning("  No defense cache found - skipping")
        return df

    # Use the largest cache file (multi-year files are bigger)
    cache_file = max(cache_files, key=lambda f: f.stat().st_size)
    logger.info(f"  Using cache file: {cache_file.name}")

    # Load cached PBP data
    pbp_df = pd.read_parquet(cache_file)
    logger.info(f"  Loaded {len(pbp_df):,} plays from cache")

    if 'play_type' not in pbp_df.columns:
        logger.warning("  Cache format unexpected - skipping")
        return df

    pbp_df = pbp_df[pbp_df['play_type'].isin(['pass', 'run'])].copy()

    # Aggregate by defending team and season
    defense_profiles = []

    for (season, defteam), group in pbp_df.groupby(['season', 'defteam']):
        if pd.isna(defteam) or defteam == '':
            continue

        profile = {
            'def_season': int(season),
            'def_team': str(defteam),
        }

        # Overall defensive EPA
        profile['def_epa_per_play'] = -group['epa'].mean() if 'epa' in group.columns else np.nan

        # Pass defense
        pass_plays = group[group['play_type'] == 'pass']
        if len(pass_plays) > 0:
            profile['pass_epa_allowed'] = -pass_plays['epa'].mean() if 'epa' in pass_plays.columns else np.nan
            if 'sack' in pass_plays.columns:
                profile['sack_rate'] = pass_plays['sack'].fillna(0).mean()
            else:
                profile['sack_rate'] = np.nan
        else:
            profile['pass_epa_allowed'] = np.nan
            profile['sack_rate'] = np.nan

        # Rush defense
        rush_plays = group[group['play_type'] == 'run']
        if len(rush_plays) > 0:
            profile['rush_epa_allowed'] = -rush_plays['epa'].mean() if 'epa' in rush_plays.columns else np.nan
        else:
            profile['rush_epa_allowed'] = np.nan

        defense_profiles.append(profile)

    if not defense_profiles:
        logger.warning("  No defense profiles generated")
        return df

    def_df = pd.DataFrame(defense_profiles)
    logger.info(f"  Generated {len(def_df):,} team-season defense profiles")

    # Calculate league averages per season
    season_avg = def_df.groupby('def_season').agg({
        'def_epa_per_play': 'mean',
        'sack_rate': 'mean',
        'pass_epa_allowed': 'mean',
        'rush_epa_allowed': 'mean'
    }).reset_index()

    season_avg.columns = ['season', 'league_avg_def_epa', 'league_avg_sack_rate',
                         'league_avg_pass_def', 'league_avg_rush_def']

    # Merge with main dataframe
    df = df.merge(season_avg, on='season', how='left')

    # Calculate position-specific opponent quality
    def get_opponent_quality(row):
        pos = row.get('position')
        if pos == 'QB':
            return row.get('league_avg_pass_def', 0) * 0.7
        elif pos == 'RB':
            return row.get('league_avg_rush_def', 0) * 1.0
        elif pos in ['WR', 'TE']:
            return row.get('league_avg_pass_def', 0) * 1.0
        return 0.0

    df['opponent_def_quality'] = df.apply(get_opponent_quality, axis=1)

    matched = df['league_avg_def_epa'].notna().sum()
    logger.info(f"  Added defense features for {matched:,} player-seasons")

    return df


def add_coaching_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add coaching scheme features from cached PBP data."""
    logger.info("Adding coaching scheme features...")

    cache_dir = Path('data/coaching_cache')
    cache_files = list(cache_dir.glob('pbp_coaching_*.parquet'))

    if not cache_files:
        logger.warning("  No coaching cache found - skipping")
        return df

    # Use the largest cache file (multi-year files are bigger)
    cache_file = max(cache_files, key=lambda f: f.stat().st_size)
    logger.info(f"  Using cache file: {cache_file.name}")

    # Load cached PBP data
    pbp_df = pd.read_parquet(cache_file)
    logger.info(f"  Loaded {len(pbp_df):,} plays from cache")

    if 'play_type' not in pbp_df.columns:
        logger.warning("  Cache format unexpected - skipping")
        return df

    pbp_df = pbp_df[pbp_df['play_type'].isin(['pass', 'run'])].copy()

    # Define neutral game script
    if all(c in pbp_df.columns for c in ['score_differential', 'qtr', 'down']):
        pbp_df['is_neutral'] = (
            (pbp_df['score_differential'].abs() <= 7) &
            (pbp_df['qtr'].isin([1, 2, 3])) &
            (pbp_df['down'].isin([1, 2, 3]))
        )
    else:
        pbp_df['is_neutral'] = True

    # Aggregate by team-season
    coaching_profiles = []

    for (season, team), group in pbp_df.groupby(['season', 'posteam']):
        if pd.isna(team) or team == '':
            continue

        profile = {
            'coach_season': int(season),
            'coach_team': str(team),
        }

        neutral_plays = group[group['is_neutral']]

        if len(neutral_plays) > 0:
            profile['pass_rate_neutral'] = (neutral_plays['play_type'] == 'pass').mean()
        else:
            profile['pass_rate_neutral'] = 0.55

        # Motion rate
        if 'motion' in group.columns:
            profile['motion_rate'] = group['motion'].fillna(0).mean()
        else:
            profile['motion_rate'] = 0.45

        # Play-action rate
        if 'play_action' in group.columns:
            profile['play_action_rate'] = group['play_action'].fillna(0).mean()
        else:
            profile['play_action_rate'] = 0.25

        coaching_profiles.append(profile)

    if not coaching_profiles:
        logger.warning("  No coaching profiles generated")
        return df

    coach_df = pd.DataFrame(coaching_profiles)
    logger.info(f"  Generated {len(coach_df):,} team-season coaching profiles")

    # Rename for merge
    coach_df = coach_df.rename(columns={
        'coach_season': 'season',
        'coach_team': 'team',
        'pass_rate_neutral': 'team_pass_rate_neutral',
        'motion_rate': 'team_motion_rate',
        'play_action_rate': 'team_play_action_rate',
    })

    # Coaching tree scores
    COACHING_TREE_SCORES = {
        'KC': 3.0, 'LAR': 3.0, 'SF': 3.0, 'MIA': 3.0, 'MIN': 3.0,
        'GB': 2.5, 'PHI': 2.5, 'DET': 2.5,
        'BUF': 2.0, 'CIN': 2.0, 'DAL': 2.0, 'LAC': 2.0,
    }

    coach_df['coaching_tree_score'] = coach_df['team'].map(
        lambda t: COACHING_TREE_SCORES.get(t, 1.5)
    )

    # Merge with main dataframe
    df = df.merge(
        coach_df[['team', 'season', 'team_pass_rate_neutral', 'team_motion_rate',
                 'team_play_action_rate', 'coaching_tree_score']],
        on=['team', 'season'],
        how='left'
    )

    matched = df['team_pass_rate_neutral'].notna().sum()
    logger.info(f"  Added coaching features for {matched:,} player-seasons")

    return df


def smart_impute_features(df: pd.DataFrame) -> pd.DataFrame:
    """Impute missing values using position-specific means from 2016+ data.

    This prevents noise from zeros in years without PBP data (1999-2015).
    """
    logger.info("Applying smart imputation for missing values...")

    new_feats = ['league_avg_def_epa', 'team_pass_rate_neutral', 'coaching_tree_score',
                 'opponent_def_quality', 'league_avg_sack_rate', 'team_motion_rate',
                 'league_avg_pass_def', 'league_avg_rush_def', 'team_play_action_rate']

    # Get recent data for calculating means
    recent_df = df[df['season'] >= 2016]

    imputed_counts = {}
    for feat in new_feats:
        if feat not in df.columns:
            continue

        # Calculate position-specific means from 2016+ data
        if 'position' in df.columns:
            pos_means = recent_df.groupby('position')[feat].mean()

            # Impute missing values by position
            for pos in pos_means.index:
                mask = (df[feat].isna()) & (df['position'] == pos)
                imputed = mask.sum()
                if imputed > 0:
                    df.loc[mask, feat] = pos_means[pos]
                    imputed_counts[f"{feat}_{pos}"] = imputed

        # Fill remaining with overall mean
        overall_mean = recent_df[feat].mean()
        remaining_na = df[feat].isna().sum()
        if remaining_na > 0:
            df[feat] = df[feat].fillna(overall_mean)
            imputed_counts[f"{feat}_other"] = remaining_na

    total_imputed = sum(imputed_counts.values())
    logger.info(f"  Imputed {total_imputed:,} total missing values across {len(new_feats)} features")

    return df


def main():
    """Load existing dataset, add new features, save."""
    input_path = Path('data/ml_training/expanded_season_projection.parquet')
    output_path = Path('data/ml_training/expanded_season_projection.parquet')
    backup_path = Path('data/ml_training/expanded_season_projection_backup.parquet')

    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        return 1

    # Load existing dataset
    logger.info(f"Loading existing dataset: {input_path}")
    df = pd.read_parquet(input_path)
    logger.info(f"  Loaded {len(df):,} rows, {len(df.columns)} columns")

    # Backup
    df.to_parquet(backup_path, index=False)
    logger.info(f"  Backed up to {backup_path}")

    # Add new features
    df = add_defense_features(df)
    df = add_coaching_features(df)

    # Smart imputation for years without PBP data
    df = smart_impute_features(df)

    # Save
    df.to_parquet(output_path, index=False)
    logger.info(f"  Saved to {output_path}")
    logger.info(f"  Final: {len(df):,} rows, {len(df.columns)} columns")

    # Print new feature coverage
    new_features = ['league_avg_def_epa', 'league_avg_sack_rate', 'opponent_def_quality',
                   'team_pass_rate_neutral', 'team_motion_rate', 'coaching_tree_score']

    print("\nNew feature coverage:")
    for feat in new_features:
        if feat in df.columns:
            coverage = df[feat].notna().mean() * 100
            print(f"  {feat}: {coverage:.1f}% non-null")

    return 0


if __name__ == '__main__':
    sys.exit(main())
