"""FTN charting feature aggregation.

FTN (Fantasy Network) charting data provides play-level details that are
extremely valuable for dynasty analysis:
- Play action, RPO, screen pass indicators
- QB pocket behavior (out of pocket, throw away)
- Interception-worthy throws
- Catchable/contested/dropped balls
- Defensive alignments (blitzers, box defenders)
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional

try:
    import polars as pl
    POLARS_AVAILABLE = True
except ImportError:
    POLARS_AVAILABLE = False


def aggregate_ftn_features(ftn_df: pd.DataFrame,
                           player_stats_df: pd.DataFrame = None) -> Dict[str, pd.DataFrame]:
    """Aggregate FTN charting data to player-season level.

    This creates three feature sets:
    - QB features: Play calling, accuracy, decision making
    - Receiver features: Target quality, contested catches, drops
    - RB features: Box defenders faced, efficiency context

    Args:
        ftn_df: Raw FTN charting DataFrame
        player_stats_df: Optional player stats for joining

    Returns:
        Dict with 'qb', 'rec', 'rb' DataFrames
    """
    if ftn_df is None or ftn_df.empty:
        return {
            'qb': pd.DataFrame(),
            'rec': pd.DataFrame(),
            'rb': pd.DataFrame()
        }

    # Ensure we have the necessary columns
    required_cols = ['season']
    available_cols = set(ftn_df.columns)

    # QB Features
    qb_features = _aggregate_qb_features(ftn_df)

    # Receiver Features
    rec_features = _aggregate_receiver_features(ftn_df)

    # RB Features
    rb_features = _aggregate_rb_features(ftn_df)

    return {
        'qb': qb_features,
        'rec': rec_features,
        'rb': rb_features
    }


def _aggregate_qb_features(ftn_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate QB-specific FTN features."""

    # Identify passer column
    passer_col = None
    for col in ['passer_player_id', 'passer_id', 'passer']:
        if col in ftn_df.columns:
            passer_col = col
            break

    if passer_col is None:
        return pd.DataFrame()

    # Filter to passing plays
    pass_plays = ftn_df[ftn_df[passer_col].notna()].copy()

    if pass_plays.empty:
        return pd.DataFrame()

    # Define aggregations based on available columns
    agg_dict = {}

    # Play type rates
    if 'is_play_action' in pass_plays.columns:
        agg_dict['play_action_rate'] = ('is_play_action', 'mean')
    if 'is_rpo' in pass_plays.columns:
        agg_dict['rpo_rate'] = ('is_rpo', 'mean')
    if 'is_screen_pass' in pass_plays.columns:
        agg_dict['screen_rate'] = ('is_screen_pass', 'mean')

    # Pocket behavior
    if 'is_qb_out_of_pocket' in pass_plays.columns:
        agg_dict['out_of_pocket_rate'] = ('is_qb_out_of_pocket', 'mean')
    if 'is_throw_away' in pass_plays.columns:
        agg_dict['throwaway_rate'] = ('is_throw_away', 'mean')

    # Accuracy/decision
    if 'is_interception_worthy' in pass_plays.columns:
        agg_dict['int_worthy_rate'] = ('is_interception_worthy', 'mean')

    # Pressure faced
    if 'n_blitzers' in pass_plays.columns:
        agg_dict['avg_blitzers_faced'] = ('n_blitzers', 'mean')
    if 'n_pass_rushers' in pass_plays.columns:
        agg_dict['avg_pass_rushers'] = ('n_pass_rushers', 'mean')

    if not agg_dict:
        return pd.DataFrame()

    # Group and aggregate
    qb_features = pass_plays.groupby([passer_col, 'season']).agg(
        **{name: pd.NamedAgg(column=col, aggfunc=func)
           for name, (col, func) in agg_dict.items()}
    ).reset_index()

    qb_features = qb_features.rename(columns={passer_col: 'gsis_id'})

    # Add play count for context
    play_counts = pass_plays.groupby([passer_col, 'season']).size().reset_index(name='ftn_pass_plays')
    play_counts = play_counts.rename(columns={passer_col: 'gsis_id'})
    qb_features = qb_features.merge(play_counts, on=['gsis_id', 'season'], how='left')

    return qb_features


def _aggregate_receiver_features(ftn_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate receiver-specific FTN features."""

    # Identify receiver column
    rec_col = None
    for col in ['receiver_player_id', 'receiver_id', 'receiver']:
        if col in ftn_df.columns:
            rec_col = col
            break

    if rec_col is None:
        return pd.DataFrame()

    # Filter to plays with receivers
    rec_plays = ftn_df[ftn_df[rec_col].notna()].copy()

    if rec_plays.empty:
        return pd.DataFrame()

    # Define aggregations
    agg_dict = {}

    # Target quality
    if 'is_catchable_ball' in rec_plays.columns:
        agg_dict['catchable_target_rate'] = ('is_catchable_ball', 'mean')
    if 'is_contested_ball' in rec_plays.columns:
        agg_dict['contested_rate'] = ('is_contested_ball', 'mean')

    # Reception quality
    if 'is_drop' in rec_plays.columns:
        agg_dict['drop_rate_ftn'] = ('is_drop', 'mean')
    if 'is_created_reception' in rec_plays.columns:
        agg_dict['created_reception_rate'] = ('is_created_reception', 'mean')

    if not agg_dict:
        return pd.DataFrame()

    # Group and aggregate
    rec_features = rec_plays.groupby([rec_col, 'season']).agg(
        **{name: pd.NamedAgg(column=col, aggfunc=func)
           for name, (col, func) in agg_dict.items()}
    ).reset_index()

    rec_features = rec_features.rename(columns={rec_col: 'gsis_id'})

    # Add target count
    target_counts = rec_plays.groupby([rec_col, 'season']).size().reset_index(name='ftn_targets')
    target_counts = target_counts.rename(columns={rec_col: 'gsis_id'})
    rec_features = rec_features.merge(target_counts, on=['gsis_id', 'season'], how='left')

    return rec_features


def _aggregate_rb_features(ftn_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate RB-specific FTN features (rush plays)."""

    # Check for rush indicator
    rush_col = None
    for col in ['is_rush', 'play_type']:
        if col in ftn_df.columns:
            rush_col = col
            break

    rusher_col = None
    for col in ['rusher_player_id', 'rusher_id', 'rusher']:
        if col in ftn_df.columns:
            rusher_col = col
            break

    if rusher_col is None:
        return pd.DataFrame()

    # Filter to rush plays
    if rush_col == 'is_rush':
        rush_plays = ftn_df[ftn_df['is_rush'] == True].copy()
    elif rush_col == 'play_type':
        rush_plays = ftn_df[ftn_df['play_type'] == 'run'].copy()
    else:
        rush_plays = ftn_df[ftn_df[rusher_col].notna()].copy()

    if rush_plays.empty:
        return pd.DataFrame()

    # Define aggregations
    agg_dict = {}

    if 'n_defense_box' in rush_plays.columns:
        agg_dict['avg_box_defenders'] = ('n_defense_box', 'mean')

    if not agg_dict:
        return pd.DataFrame()

    # Group and aggregate
    rb_features = rush_plays.groupby([rusher_col, 'season']).agg(
        **{name: pd.NamedAgg(column=col, aggfunc=func)
           for name, (col, func) in agg_dict.items()}
    ).reset_index()

    rb_features = rb_features.rename(columns={rusher_col: 'gsis_id'})

    # Add carry count
    carry_counts = rush_plays.groupby([rusher_col, 'season']).size().reset_index(name='ftn_carries')
    carry_counts = carry_counts.rename(columns={rusher_col: 'gsis_id'})
    rb_features = rb_features.merge(carry_counts, on=['gsis_id', 'season'], how='left')

    return rb_features


def calculate_chemistry_features(ftn_df: pd.DataFrame,
                                  pbp_df: pd.DataFrame = None) -> pd.DataFrame:
    """Calculate QB-WR chemistry features from FTN data.

    Chemistry Quantification Index (CQI) measures:
    - Trust under pressure (targeted when blitzed/pressured)
    - High-leverage targets (red zone, 3rd down)
    - Contested target share
    - Throwaway rate when receiver is covered

    Args:
        ftn_df: FTN charting data
        pbp_df: Play-by-play data for additional context

    Returns:
        DataFrame with QB-receiver chemistry metrics
    """
    if ftn_df is None or ftn_df.empty:
        return pd.DataFrame()

    # Identify columns
    passer_col = None
    receiver_col = None

    for col in ['passer_player_id', 'passer_id']:
        if col in ftn_df.columns:
            passer_col = col
            break

    for col in ['receiver_player_id', 'receiver_id']:
        if col in ftn_df.columns:
            receiver_col = col
            break

    if passer_col is None or receiver_col is None:
        return pd.DataFrame()

    # Filter to pass plays with receivers
    pass_plays = ftn_df[(ftn_df[passer_col].notna()) & (ftn_df[receiver_col].notna())].copy()

    if pass_plays.empty:
        return pd.DataFrame()

    # Group by QB-receiver pair per season
    groupby_cols = [passer_col, receiver_col, 'season']

    # Calculate chemistry metrics
    chemistry_data = []

    for (qb_id, rec_id, season), group in pass_plays.groupby(groupby_cols):
        targets = len(group)

        # Skip small sample sizes
        if targets < 10:
            continue

        metrics = {
            'qb_gsis_id': qb_id,
            'receiver_gsis_id': rec_id,
            'season': season,
            'targets': targets
        }

        # Trust under pressure (if blitz data available)
        if 'n_blitzers' in group.columns:
            pressure_plays = group[group['n_blitzers'] >= 5]
            if len(group) > 0:
                metrics['pressure_target_rate'] = len(pressure_plays) / len(group)

        # Contested catches (if available)
        if 'is_contested_ball' in group.columns:
            contested = group['is_contested_ball'].sum()
            metrics['contested_target_rate'] = contested / targets

        # Catchable ball rate (trust indicator)
        if 'is_catchable_ball' in group.columns:
            catchable = group['is_catchable_ball'].mean()
            metrics['catchable_rate'] = catchable

        # Drop rate (chemistry negative)
        if 'is_drop' in group.columns:
            drop_rate = group['is_drop'].mean()
            metrics['drop_rate'] = drop_rate

        # Calculate CQI score (0-100)
        cqi = 50  # Base score
        if 'pressure_target_rate' in metrics:
            cqi += 15 * metrics['pressure_target_rate']  # Trust under pressure
        if 'contested_target_rate' in metrics:
            cqi += 10 * metrics['contested_target_rate']  # Contested catches
        if 'catchable_rate' in metrics:
            cqi += 15 * (metrics['catchable_rate'] - 0.7)  # Above average catchable
        if 'drop_rate' in metrics:
            cqi -= 20 * metrics['drop_rate']  # Penalize drops

        metrics['cqi_score'] = max(0, min(100, cqi))

        # Trust score (simplified)
        trust = 50
        if 'catchable_rate' in metrics:
            trust += 30 * (metrics['catchable_rate'] - 0.5)
        if 'drop_rate' in metrics:
            trust -= 30 * metrics['drop_rate']
        metrics['trust_score'] = max(0, min(100, trust))

        chemistry_data.append(metrics)

    return pd.DataFrame(chemistry_data)


def join_ftn_to_stats(ftn_features: Dict[str, pd.DataFrame],
                       player_stats: pd.DataFrame) -> pd.DataFrame:
    """Join FTN features to player stats DataFrame.

    Args:
        ftn_features: Dict from aggregate_ftn_features()
        player_stats: Player statistics DataFrame

    Returns:
        Player stats with FTN features joined
    """
    df = player_stats.copy()

    # Join QB features
    if 'qb' in ftn_features and not ftn_features['qb'].empty:
        qb_cols = [c for c in ftn_features['qb'].columns
                   if c not in df.columns or c in ['gsis_id', 'season']]
        df = df.merge(
            ftn_features['qb'][qb_cols],
            on=['gsis_id', 'season'],
            how='left'
        )

    # Join receiver features
    if 'rec' in ftn_features and not ftn_features['rec'].empty:
        rec_cols = [c for c in ftn_features['rec'].columns
                    if c not in df.columns or c in ['gsis_id', 'season']]
        df = df.merge(
            ftn_features['rec'][rec_cols],
            on=['gsis_id', 'season'],
            how='left'
        )

    # Join RB features
    if 'rb' in ftn_features and not ftn_features['rb'].empty:
        rb_cols = [c for c in ftn_features['rb'].columns
                   if c not in df.columns or c in ['gsis_id', 'season']]
        df = df.merge(
            ftn_features['rb'][rb_cols],
            on=['gsis_id', 'season'],
            how='left'
        )

    return df
