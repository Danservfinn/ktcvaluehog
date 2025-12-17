"""
Calculate composite breakout scores for predicting future value rises.

Composite Scores:
1. breakout_score - Overall likelihood of value increase
2. trajectory_score - Production trend momentum
3. efficiency_gap - Production efficiency vs opportunity
4. ceiling_ratio - Peak performance potential
5. athletic_upside - Athletic profile vs current production
6. situation_score - Team/contract favorability
"""

import pandas as pd
import numpy as np
from neo4j import GraphDatabase
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')


def get_driver():
    """Get Neo4j driver."""
    return GraphDatabase.driver("bolt://localhost:7687", auth=None)


def fetch_player_data():
    """Fetch all player data needed for composite score calculation."""
    driver = get_driver()

    with driver.session() as session:
        result = session.run("""
            MATCH (p:Player)
            WHERE p.position IN ['QB', 'RB', 'WR', 'TE']
              AND p.ktc_value > 0

            RETURN
                p.gsis_id as gsis_id,
                p.name as name,
                p.position as position,
                p.ktc_value as ktc_value,
                p.age as age,
                p.years_exp as years_exp,

                // Production metrics
                p.fantasy_points_ppr as fantasy_points_ppr,
                p.games_played as games_played,
                p.targets as targets,
                p.receptions as receptions,
                p.receiving_yards as receiving_yards,
                p.carries as carries,
                p.rushing_yards as rushing_yards,
                p.passing_yards as passing_yards,

                // Career metrics
                p.career_ppg_ppr as career_ppg_ppr,
                p.career_ppg_half as career_ppg_half,
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
                p.peak_fpts as peak_fpts,
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
                p.combine_vertical as vertical_jump,
                p.combine_broad_jump as broad_jump,

                // Draft
                p.draft_round as draft_round,
                p.draft_pick as draft_pick
        """)

        data = [dict(r) for r in result]

    driver.close()
    return pd.DataFrame(data)


def calculate_trajectory_score(df):
    """
    Calculate trajectory score based on production trends.
    Higher = player trending upward.
    """
    df = df.copy()

    # Components:
    # 1. PPG trend slope (positive = improving)
    # 2. Recent 3-year trend
    # 3. Years from peak (negative = farther from peak)
    # 4. Age-adjusted trajectory

    # Normalize trend slope to 0-100 scale
    slope = df['ppg_trend_slope'].fillna(0)
    slope_score = np.clip((slope + 5) * 10, 0, 100)  # -5 to +5 range -> 0-100

    # 3-year trend score
    trend_3yr = df['ppg_trend_3yr'].fillna(0)
    trend_3yr_score = np.clip((trend_3yr + 50) / 100 * 100, 0, 100)

    # Peak proximity score (closer to peak = higher)
    years_from_peak = df['years_from_peak'].fillna(3)
    peak_score = np.clip(100 - (years_from_peak * 20), 0, 100)

    # Age factor (younger with upward trend = bonus)
    age = df['age'].fillna(26)
    age_factor = np.where(
        (age < 26) & (slope > 0), 1.2,
        np.where(age > 30, 0.8, 1.0)
    )

    # Combined trajectory score
    trajectory = (slope_score * 0.4 + trend_3yr_score * 0.3 + peak_score * 0.3) * age_factor
    df['trajectory_score'] = np.clip(trajectory, 0, 100).round(2)

    return df


def calculate_efficiency_gap(df):
    """
    Calculate efficiency gap - production relative to opportunity.
    High efficiency + low opportunity = breakout candidate.
    """
    df = df.copy()

    # Calculate current PPG
    games = df['games_played'].fillna(1).replace(0, 1)
    current_ppg = df['fantasy_points_ppr'].fillna(0) / games

    # Target share efficiency (for WR/TE)
    targets = df['targets'].fillna(0)
    target_efficiency = np.where(
        targets > 0,
        df['receiving_yards'].fillna(0) / targets,
        0
    )

    # Rush efficiency (for RB)
    carries = df['carries'].fillna(0)
    rush_efficiency = np.where(
        carries > 0,
        df['rushing_yards'].fillna(0) / carries,
        0
    )

    # Snap efficiency (production per snap)
    snaps = df['total_snaps'].fillna(100).replace(0, 100)
    snap_efficiency = (df['fantasy_points_ppr'].fillna(0) / snaps) * 100

    # Normalize efficiencies (convert to Series for rank method)
    def percentile_rank(arr):
        return pd.Series(arr).rank(pct=True).values * 100

    target_eff_pct = percentile_rank(target_efficiency)
    rush_eff_pct = percentile_rank(rush_efficiency)
    snap_eff_pct = percentile_rank(snap_efficiency)

    # Opportunity level (lower = more room for growth)
    snap_pct = df['snap_pct'].fillna(50)
    opportunity_room = 100 - snap_pct

    # Efficiency gap = high efficiency + room for more opportunity
    position = df['position']
    efficiency_gap = np.where(
        position.isin(['WR', 'TE']),
        (target_eff_pct * 0.5 + snap_eff_pct * 0.3 + opportunity_room * 0.2),
        np.where(
            position == 'RB',
            (rush_eff_pct * 0.5 + snap_eff_pct * 0.3 + opportunity_room * 0.2),
            snap_eff_pct  # QB
        )
    )

    df['efficiency_gap'] = np.clip(efficiency_gap, 0, 100).round(2)

    return df


def calculate_ceiling_ratio(df):
    """
    Calculate ceiling ratio - how much upside remains.
    Peak production vs current production.
    """
    df = df.copy()

    # Current PPG
    games = df['games_played'].fillna(1).replace(0, 1)
    current_ppg = df['fantasy_points_ppr'].fillna(0) / games

    # Peak PPG
    peak_ppg = df['peak_ppg'].fillna(current_ppg)

    # Ceiling vs floor spread
    ceiling = df['ceiling_ppg'].fillna(current_ppg)
    floor = df['floor_ppg'].fillna(0)
    upside_spread = ceiling - floor

    # Ceiling ratio = how much of peak they could recover
    # Plus bonus for high ceiling spread
    peak_gap = np.where(
        peak_ppg > current_ppg,
        (peak_ppg - current_ppg) / peak_ppg.replace(0, 1) * 100,
        0
    )

    # Normalize upside spread
    upside_pct = upside_spread.rank(pct=True) * 100

    # Combined ceiling score
    ceiling_ratio = peak_gap * 0.6 + upside_pct * 0.4
    df['ceiling_ratio'] = np.clip(ceiling_ratio, 0, 100).round(2)

    return df


def calculate_athletic_upside(df):
    """
    Calculate athletic upside - athletic profile vs current production.
    Elite athlete + low production = breakout potential.
    """
    df = df.copy()

    # Athletic score (already calculated, or use components)
    athletic = df['athletic_score'].fillna(50)

    # Production percentile
    games = df['games_played'].fillna(1).replace(0, 1)
    current_ppg = df['fantasy_points_ppr'].fillna(0) / games
    production_pct = current_ppg.rank(pct=True) * 100

    # Athletic upside = high athletic + room for production growth
    athletic_gap = np.where(
        athletic > production_pct,
        athletic - production_pct,
        0
    )

    # Boost for young athletic players
    age = df['age'].fillna(26)
    age_boost = np.where(age < 25, 1.3, np.where(age < 27, 1.1, 1.0))

    athletic_upside = athletic_gap * age_boost
    df['athletic_upside'] = np.clip(athletic_upside, 0, 100).round(2)

    return df


def calculate_situation_score(df):
    """
    Calculate situation score based on contract and opportunity factors.
    """
    df = df.copy()

    # Contract value percentile
    contract_apy = df['contract_apy'].fillna(0)
    contract_pct = contract_apy.rank(pct=True) * 100

    # Guaranteed money (higher = team invested)
    guaranteed = df['contract_guaranteed'].fillna(0)
    guaranteed_pct = guaranteed.rank(pct=True) * 100

    # Draft capital (lower round = exceeded expectations potential)
    draft_round = df['draft_round'].fillna(5)
    draft_value = np.where(
        draft_round <= 2, 80,  # High draft capital
        np.where(draft_round <= 4, 60, 40)  # Lower = overachiever potential
    )

    # Experience sweet spot (2-4 years = breakout window)
    years_exp = df['years_exp'].fillna(3)
    exp_score = np.where(
        years_exp.between(1, 2), 90,  # Prime breakout window
        np.where(years_exp.between(2, 4), 80,
        np.where(years_exp < 1, 70, 50))  # Rookie or veteran
    )

    # Combined situation score
    situation = (
        contract_pct * 0.25 +
        guaranteed_pct * 0.25 +
        draft_value * 0.25 +
        exp_score * 0.25
    )

    df['situation_score'] = np.clip(situation, 0, 100).round(2)

    return df


def calculate_breakout_score(df):
    """
    Calculate overall breakout score - weighted combination of all factors.
    """
    df = df.copy()

    # Weight by importance for value rise prediction
    weights = {
        'trajectory_score': 0.30,    # Most important - trending up
        'efficiency_gap': 0.20,      # Efficient but underutilized
        'ceiling_ratio': 0.20,       # Room to grow
        'athletic_upside': 0.15,     # Physical tools
        'situation_score': 0.15,     # Team/contract factors
    }

    # Ensure all component scores exist
    for col in weights.keys():
        if col not in df.columns:
            df[col] = 50  # Default

    # Calculate weighted sum
    breakout = sum(df[col].fillna(50) * weight for col, weight in weights.items())

    # Age adjustment (younger = higher potential)
    age = df['age'].fillna(26)
    age_multiplier = np.where(
        age < 24, 1.15,
        np.where(age < 26, 1.08,
        np.where(age < 28, 1.0,
        np.where(age < 30, 0.92, 0.85)))
    )

    # Value adjustment (lower value = more room to rise)
    ktc_value = df['ktc_value'].fillna(5000)
    value_multiplier = np.where(
        ktc_value < 2000, 1.15,  # Low value = more upside
        np.where(ktc_value < 4000, 1.05,
        np.where(ktc_value < 6000, 1.0, 0.95))  # High value = less room
    )

    df['breakout_score'] = np.clip(breakout * age_multiplier * value_multiplier, 0, 100).round(2)

    return df


def store_breakout_scores(df):
    """Store calculated breakout scores in Neo4j."""
    driver = get_driver()

    with driver.session() as session:
        # Prepare update records
        score_cols = [
            'gsis_id', 'breakout_score', 'trajectory_score', 'efficiency_gap',
            'ceiling_ratio', 'athletic_upside', 'situation_score'
        ]

        records = df[score_cols].to_dict('records')

        # Batch update
        session.run("""
            UNWIND $records as r
            MATCH (p:Player {gsis_id: r.gsis_id})
            SET p.breakout_score = r.breakout_score,
                p.trajectory_score = r.trajectory_score,
                p.efficiency_gap = r.efficiency_gap,
                p.ceiling_ratio = r.ceiling_ratio,
                p.athletic_upside = r.athletic_upside,
                p.situation_score = r.situation_score,
                p.breakout_updated = datetime()
        """, {'records': records})

        print(f"   Updated {len(records)} players with breakout scores")

    driver.close()


def main():
    """Main pipeline."""
    print("=" * 70)
    print("COMPOSITE BREAKOUT SCORE CALCULATION")
    print(f"Started: {datetime.now()}")
    print("=" * 70)

    # 1. Fetch data
    print("\n📊 Fetching player data...")
    df = fetch_player_data()
    print(f"   Loaded {len(df)} players")

    # 2. Calculate component scores
    print("\n🔧 Calculating component scores...")

    print("   - Trajectory score...")
    df = calculate_trajectory_score(df)

    print("   - Efficiency gap...")
    df = calculate_efficiency_gap(df)

    print("   - Ceiling ratio...")
    df = calculate_ceiling_ratio(df)

    print("   - Athletic upside...")
    df = calculate_athletic_upside(df)

    print("   - Situation score...")
    df = calculate_situation_score(df)

    # 3. Calculate overall breakout score
    print("\n🎯 Calculating overall breakout score...")
    df = calculate_breakout_score(df)

    # 4. Store in Neo4j
    print("\n💾 Storing scores in Neo4j...")
    store_breakout_scores(df)

    # 5. Show top breakout candidates
    print("\n" + "=" * 70)
    print("TOP BREAKOUT CANDIDATES BY POSITION")
    print("=" * 70)

    for pos in ['QB', 'RB', 'WR', 'TE']:
        pos_df = df[df['position'] == pos].nlargest(5, 'breakout_score')
        print(f"\n{pos}:")
        for _, row in pos_df.iterrows():
            print(f"   {row['name']:<25} | Breakout: {row['breakout_score']:5.1f} | "
                  f"Traj: {row['trajectory_score']:5.1f} | Eff: {row['efficiency_gap']:5.1f} | "
                  f"KTC: {row['ktc_value']:,}")

    # 6. Score distribution
    print("\n" + "=" * 70)
    print("BREAKOUT SCORE DISTRIBUTION")
    print("=" * 70)
    print(f"   Mean: {df['breakout_score'].mean():.1f}")
    print(f"   Std:  {df['breakout_score'].std():.1f}")
    print(f"   Min:  {df['breakout_score'].min():.1f}")
    print(f"   Max:  {df['breakout_score'].max():.1f}")

    # Score tiers
    df['breakout_tier'] = pd.cut(
        df['breakout_score'],
        bins=[0, 40, 55, 70, 85, 100],
        labels=['Low', 'Below Avg', 'Average', 'High', 'Elite']
    )
    tier_dist = df['breakout_tier'].value_counts().sort_index()
    print("\n   Tier Distribution:")
    for tier, count in tier_dist.items():
        print(f"      {tier}: {count}")

    print("\n" + "=" * 70)
    print("BREAKOUT SCORE CALCULATION COMPLETE")
    print("=" * 70)

    return df


if __name__ == "__main__":
    main()
