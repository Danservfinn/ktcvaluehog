"""Graph-derived features from Neo4j.

Extracts ML features based on player relationships and graph structure:
- QB quality score for receivers
- Competition index within team
- Team offensive context
- Opportunity flow metrics
- Chemistry scores
"""

import pandas as pd
from typing import Dict, Optional, List

from ..database.neo4j_client import Neo4jClient


def extract_graph_features(client: Neo4jClient,
                            season: int = 2025) -> Dict[str, pd.DataFrame]:
    """Extract all graph-based features for ML training.

    Args:
        client: Neo4j client
        season: Season to extract features for

    Returns:
        Dict with feature DataFrames:
        - qb_quality: QB situation scores for receivers
        - competition: Same-position competition metrics
        - team_context: Team offensive environment
        - opportunity: Opportunity share metrics
        - chemistry: QB-receiver chemistry scores
    """
    features = {}

    print(f"Extracting graph features for {season} season...")

    # QB Quality for receivers
    print("  Extracting QB quality features...")
    features['qb_quality'] = extract_qb_quality_features(client, season)

    # Competition index
    print("  Extracting competition features...")
    features['competition'] = extract_competition_features(client, season)

    # Team context
    print("  Extracting team context features...")
    features['team_context'] = extract_team_context_features(client, season)

    # Opportunity metrics
    print("  Extracting opportunity features...")
    features['opportunity'] = extract_opportunity_features(client, season)

    # Chemistry scores
    print("  Extracting chemistry features...")
    features['chemistry'] = extract_chemistry_features(client, season)

    print("Done extracting graph features.")
    return features


def extract_qb_quality_features(client: Neo4jClient, season: int = 2025) -> pd.DataFrame:
    """Extract QB quality context for receivers.

    For each WR/TE, calculate:
    - qb_quality_score: Weighted score of QB ability
    - qb_age: QB's current age (affects long-term outlook)
    - qb_epa: QB's EPA per play (efficiency)
    - qb_age_factor: Multiplier based on QB career stage
    """
    query = """
        MATCH (rec:Player)-[t:TARGETS_FROM]->(qb:Player)
        WHERE rec.position IN ['WR', 'TE']
          AND t.season = $season
        WITH rec, qb, t,
             CASE
                 WHEN qb.age < 26 THEN 1.1   // Young QB premium
                 WHEN qb.age > 32 THEN 0.9   // Aging QB discount
                 ELSE 1.0
             END as qb_age_factor
        OPTIONAL MATCH (qb)-[:HAD_SEASON]->(ps:PlayerSeason {season: $season})
        WITH rec, qb, t, qb_age_factor,
             COALESCE(ps.epa_per_play, 0) as qb_epa,
             COALESCE(ps.fantasy_points_ppr, 0) as qb_fpts
        RETURN rec.gsis_id as gsis_id,
               rec.name as player_name,
               qb.gsis_id as qb_gsis_id,
               qb.name as qb_name,
               qb.age as qb_age,
               qb_age_factor,
               qb_epa,
               qb_fpts,
               t.target_share as target_share,
               t.targets as targets
    """

    try:
        results = client.run_query(query, {'season': season})
        if not results:
            return pd.DataFrame()

        df = pd.DataFrame(results)

        # Calculate QB quality score (0-100)
        if len(df) > 0:
            # Normalize EPA to 0-100 scale
            if 'qb_epa' in df.columns:
                epa_min, epa_max = df['qb_epa'].min(), df['qb_epa'].max()
                if epa_max > epa_min:
                    df['qb_epa_normalized'] = 100 * (df['qb_epa'] - epa_min) / (epa_max - epa_min)
                else:
                    df['qb_epa_normalized'] = 50

            # Quality score = EPA (60%) + Age Factor (20%) + Stability (20%)
            df['qb_quality_score'] = (
                0.6 * df.get('qb_epa_normalized', 50) +
                0.2 * (df['qb_age_factor'] * 50) +
                0.2 * 50  # Placeholder for stability
            )

        return df

    except Exception as e:
        print(f"    Warning: Could not extract QB quality features: {e}")
        return pd.DataFrame()


def extract_competition_features(client: Neo4jClient, season: int = 2025) -> pd.DataFrame:
    """Extract same-position competition metrics.

    For each player, calculate:
    - num_competitors: Number of same-position teammates
    - avg_comp_value: Average KTC value of competitors
    - value_share: Player's share of positional value
    - competition_intensity: How competitive the depth chart is
    """
    query = """
        MATCH (p:Player)-[c:COMPETES_WITH]-(comp:Player)
        WHERE c.season = $season
          AND p.position IN ['RB', 'WR', 'TE']
        WITH p,
             count(DISTINCT comp) as num_competitors,
             avg(comp.ktc_value_sf) as avg_comp_value,
             sum(comp.ktc_value_sf) as total_comp_value,
             collect(comp.ktc_value_sf) as comp_values
        WHERE num_competitors > 0
        RETURN p.gsis_id as gsis_id,
               p.name as player_name,
               p.position as position,
               p.current_team as team,
               p.ktc_value_sf as player_value,
               num_competitors,
               avg_comp_value,
               total_comp_value,
               p.ktc_value_sf / (p.ktc_value_sf + total_comp_value) as value_share
    """

    try:
        results = client.run_query(query, {'season': season})
        if not results:
            return pd.DataFrame()

        df = pd.DataFrame(results)

        # Calculate competition intensity (0-100)
        # Higher = more crowded depth chart
        if len(df) > 0 and 'value_share' in df.columns:
            df['competition_intensity'] = 100 * (1 - df['value_share'])

        return df

    except Exception as e:
        print(f"    Warning: Could not extract competition features: {e}")
        return pd.DataFrame()


def extract_team_context_features(client: Neo4jClient, season: int = 2025) -> pd.DataFrame:
    """Extract team offensive context for players.

    For each player, get team metrics:
    - team_pass_rate: Team's pass play percentage
    - team_plays_per_game: Team's pace
    - team_pass_epa: Team's passing efficiency
    - team_pa_rate: Play action usage
    """
    query = """
        MATCH (p:Player)-[:PLAYS_FOR]->(t:Team)
        WHERE p.position IN ['QB', 'RB', 'WR', 'TE']
        OPTIONAL MATCH (t)-[:HAD_SEASON]->(ts:TeamSeason {season: $season})
        RETURN p.gsis_id as gsis_id,
               p.name as player_name,
               t.team_abbr as team,
               ts.pass_rate as team_pass_rate,
               ts.plays_per_game as team_plays_per_game,
               ts.pass_epa as team_pass_epa,
               ts.play_action_rate as team_pa_rate,
               ts.red_zone_pass_rate as team_rz_pass_rate
    """

    try:
        results = client.run_query(query, {'season': season})
        return pd.DataFrame(results) if results else pd.DataFrame()

    except Exception as e:
        print(f"    Warning: Could not extract team context features: {e}")
        return pd.DataFrame()


def extract_opportunity_features(client: Neo4jClient, season: int = 2025) -> pd.DataFrame:
    """Extract opportunity flow metrics.

    For each player, calculate their share of team opportunities:
    - target_share: Share of team targets
    - carry_share: Share of team carries
    - snap_share: Share of offensive snaps
    - opportunity_score: Combined opportunity metric
    """
    query = """
        MATCH (p:Player)-[c:CAPTURES_OPPORTUNITY]->(op:OpportunityPool)
        WHERE op.season = $season
        RETURN p.gsis_id as gsis_id,
               p.name as player_name,
               p.position as position,
               op.team_abbr as team,
               c.target_share as target_share,
               c.carry_share as carry_share,
               c.snap_share as snap_share,
               c.opportunity_score as opportunity_score,
               op.total_targets as team_targets,
               op.total_carries as team_carries,
               op.target_elasticity as target_elasticity
    """

    try:
        results = client.run_query(query, {'season': season})
        return pd.DataFrame(results) if results else pd.DataFrame()

    except Exception as e:
        print(f"    Warning: Could not extract opportunity features: {e}")
        return pd.DataFrame()


def extract_chemistry_features(client: Neo4jClient, season: int = 2025) -> pd.DataFrame:
    """Extract QB-receiver chemistry scores.

    For each receiver, get chemistry metrics with their QB:
    - cqi_score: Chemistry Quantification Index
    - trust_score: QB trust indicator
    - pressure_target_rate: Targets under pressure
    """
    query = """
        MATCH (rec:Player)-[c:CHEMISTRY_WITH]->(qb:Player)
        WHERE c.season = $season
        RETURN rec.gsis_id as gsis_id,
               rec.name as player_name,
               qb.gsis_id as qb_gsis_id,
               qb.name as qb_name,
               c.cqi_score as cqi_score,
               c.trust_score as trust_score,
               c.pressure_target_rate as pressure_target_rate,
               c.red_zone_target_rate as rz_target_rate,
               c.contested_target_rate as contested_rate
    """

    try:
        results = client.run_query(query, {'season': season})
        return pd.DataFrame(results) if results else pd.DataFrame()

    except Exception as e:
        print(f"    Warning: Could not extract chemistry features: {e}")
        return pd.DataFrame()


def combine_graph_features(features: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Combine all graph features into single DataFrame.

    Joins on gsis_id to create one row per player.

    Args:
        features: Dict from extract_graph_features()

    Returns:
        Combined DataFrame with all graph features
    """
    if not features:
        return pd.DataFrame()

    # Start with the largest DataFrame
    max_key = max(features.keys(), key=lambda k: len(features[k]) if isinstance(features[k], pd.DataFrame) else 0)
    df = features[max_key].copy() if not features[max_key].empty else pd.DataFrame()

    if df.empty:
        return df

    # Join other feature sets
    for key, feature_df in features.items():
        if key == max_key or feature_df.empty:
            continue

        # Get non-duplicate columns
        join_cols = ['gsis_id']
        new_cols = [c for c in feature_df.columns if c not in df.columns or c in join_cols]

        if new_cols:
            df = df.merge(
                feature_df[new_cols],
                on='gsis_id',
                how='left'
            )

    return df


def calculate_edge_signal_features(client: Neo4jClient) -> pd.DataFrame:
    """Calculate edge signal features for all players.

    Uses graph relationships to determine value signals.

    Returns:
        DataFrame with edge analysis features
    """
    query = """
        MATCH (p:Player)
        WHERE p.ktc_value_sf > 1000 AND p.position IN ['QB', 'RB', 'WR', 'TE']

        // Get QB relationship for receivers
        OPTIONAL MATCH (p)-[:TARGETS_FROM]->(qb:Player)

        // Get competition
        OPTIONAL MATCH (p)-[:COMPETES_WITH]-(comp:Player)

        WITH p, qb, count(DISTINCT comp) as num_competitors,
             avg(comp.ktc_value_sf) as avg_comp_value

        // Calculate factors
        WITH p, qb, num_competitors, avg_comp_value,
             CASE p.position
                 WHEN 'QB' THEN 38 - p.age
                 WHEN 'RB' THEN 30 - p.age
                 WHEN 'WR' THEN 33 - p.age
                 WHEN 'TE' THEN 34 - p.age
                 ELSE 32 - p.age
             END as years_remaining,
             CASE
                 WHEN p.position = 'RB' AND p.age >= 27 THEN 0.7
                 WHEN p.position = 'RB' AND p.age >= 26 THEN 0.85
                 WHEN p.position = 'WR' AND p.age >= 30 THEN 0.75
                 WHEN p.position = 'QB' AND p.age >= 34 THEN 0.8
                 ELSE 1.0
             END as age_factor,
             CASE
                 WHEN qb IS NOT NULL AND qb.age < 26 THEN 1.08
                 WHEN qb IS NOT NULL AND qb.age > 32 THEN 0.92
                 ELSE 1.0
             END as qb_factor

        RETURN p.gsis_id as gsis_id,
               p.name as player_name,
               p.position as position,
               p.age as age,
               p.ktc_value_sf as ktc_value,
               years_remaining,
               age_factor,
               qb.name as qb_name,
               qb_factor,
               num_competitors,
               avg_comp_value,
               toInteger(p.ktc_value_sf * age_factor * qb_factor) as adjusted_value,
               ((p.ktc_value_sf * age_factor * qb_factor - p.ktc_value_sf) / p.ktc_value_sf) * 100 as value_delta_pct
        ORDER BY ABS(value_delta_pct) DESC
    """

    try:
        results = client.run_query(query)
        if not results:
            return pd.DataFrame()

        df = pd.DataFrame(results)

        # Add edge signal
        def get_signal(delta_pct):
            if delta_pct < -15:
                return 'STRONG_BUY'
            elif delta_pct < -5:
                return 'BUY'
            elif delta_pct > 15:
                return 'STRONG_SELL'
            elif delta_pct > 5:
                return 'SELL'
            else:
                return 'HOLD'

        df['edge_signal'] = df['value_delta_pct'].apply(get_signal)

        return df

    except Exception as e:
        print(f"Warning: Could not calculate edge signals: {e}")
        return pd.DataFrame()
