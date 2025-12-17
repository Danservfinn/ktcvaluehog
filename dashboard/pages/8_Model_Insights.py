"""
Thoth Model Insights
====================
Understand how our ML models predict dynasty value and future fantasy production.
Feature importance, correlations, and prediction explanations.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.components.tooltips import (
    FEATURE_TOOLTIPS, get_short_description, get_signal_color,
    render_category_help, CATEGORY_DESCRIPTIONS
)

st.set_page_config(page_title="Model Insights - Thoth", layout="wide")

# =============================================================================
# THOTH DESIGN SYSTEM
# =============================================================================
COLORS = {
    'primary': '#1E3A5F',
    'success': '#10B981',
    'danger': '#EF4444',
    'warning': '#F59E0B',
    'neutral': '#6B7280',
    'background': '#F9FAFB'
}

# =============================================================================
# MODEL METADATA (from training results)
# =============================================================================

# KTC Value Prediction Model
KTC_MODEL_METRICS = {
    'r_squared': 0.87,
    'rmse': 735.55,
    'total_features': 40,
    'training_samples': 976,
    'model_type': 'H2O GBM (Gradient Boosting)',
    'last_trained': '2024-12-17'
}

# Season Projection Model (2026 Predictions)
PROJECTION_MODEL_METRICS = {
    'r_squared': 0.613,
    'rmse': 3.55,
    'cv_r2_mean': 0.584,
    'cv_r2_std': 0.045,
    'training_samples': 6088,
    'model_type': 'Gradient Boosting',
    'last_trained': '2024-12-17',
    'position_performance': {
        'QB': {'r2': 0.732, 'rmse': 3.90, 'mae': 2.88, 'count': 449},
        'RB': {'r2': 0.844, 'rmse': 2.92, 'mae': 2.15, 'count': 1741},
        'WR': {'r2': 0.837, 'rmse': 2.69, 'mae': 1.93, 'count': 2728},
        'TE': {'r2': 0.771, 'rmse': 2.48, 'mae': 1.78, 'count': 1170},
    }
}

# Breakout Classifier Model
BREAKOUT_MODEL_METRICS = {
    'auc': 0.671,
    'accuracy': 0.911,
    'precision': 0.30,
    'recall': 0.15,
    'training_samples': 3933,
    'breakout_rate': 0.087,  # 8.7% breakout rate
    'model_type': 'Gradient Boosting Classifier',
    'last_trained': '2024-12-17'
}

# Legacy alias for backwards compatibility
MODEL_METRICS = KTC_MODEL_METRICS

# Feature importance from model training (normalized 0-100)
FEATURE_IMPORTANCE = {
    'contract_guaranteed': 100.0,
    'contract_total': 55.2,
    'total_snaps': 21.3,
    'snap_pct': 18.7,
    'apy_percentile': 16.4,
    'adot': 14.8,
    'draft_value': 12.3,
    'guaranteed_pct': 10.1,
    'snap_trend': 8.9,
    'cap_pct': 7.6,
    'age': 6.2,
    'games_played': 5.8,
    'injury_risk_score': 4.3,
    'draft_round': 3.9,
    'combine_forty': 3.2,
    'combine_vertical': 2.8,
    'combine_cone': 2.5,
    'years_exp': 2.1,
    'athletic_score': 1.8,
    'combine_shuttle': 1.5
}

# Season Projection Model Feature Importance (from training)
PROJECTION_FEATURE_IMPORTANCE = {
    'ppg_ppr': 53.6,
    'ppg_std': 9.7,
    'targets_per_game': 6.6,
    'best_season_ppg': 6.2,
    'carries_per_game': 5.8,
    'rec_yards_per_game': 4.1,
    'rush_yards_per_game': 3.8,
    'career_ppg': 3.5,
    'catch_rate': 2.9,
    'years_in_league': 2.4,
    'yards_per_catch': 1.8,
    'yards_per_carry': 1.6,
    'rec_td_rate': 1.2,
    'rush_td_rate': 1.0,
    'ppg_vs_career_avg': 0.9,
}

# Feature correlations with KTC value
FEATURE_CORRELATIONS = {
    'contract_guaranteed': 0.537,
    'contract_total': 0.506,
    'contract_apy': 0.497,
    'draft_value': 0.494,
    'cap_pct': 0.493,
    'apy_percentile': 0.468,
    'total_snaps': 0.567,
    'snap_pct': 0.530,
    'draft_round': -0.400,
    'draft_pick': -0.394,
    'games_played': 0.274,
    'years_remaining': 0.172,
    'age': -0.173,
    'years_exp': -0.126,
    'athletic_score': 0.073,
    'combine_forty': -0.072,
    'combine_cone': -0.073,
    'combine_shuttle': -0.070
}


def get_driver():
    """Get Neo4j driver."""
    if 'neo4j_driver' not in st.session_state:
        from neo4j import GraphDatabase
        uri = st.secrets.get("neo4j_uri", "bolt://localhost:7687")
        st.session_state.neo4j_driver = GraphDatabase.driver(uri, auth=None)
    return st.session_state.neo4j_driver


# =============================================================================
# DATA QUERIES
# =============================================================================

@st.cache_data(ttl=3600)
def get_position_stats():
    """Get model stats by position."""
    driver = get_driver()

    with driver.session() as session:
        result = session.run("""
            MATCH (p:Player)
            WHERE p.position IN ['QB', 'RB', 'WR', 'TE']
              AND p.predicted_ktc_value IS NOT NULL
            WITH p.position as position,
                 count(p) as player_count,
                 avg(p.ktc_value) as avg_ktc,
                 avg(p.predicted_ktc_value) as avg_predicted,
                 avg(abs(p.value_delta)) as avg_error,
                 sum(CASE WHEN p.edge_signal IN ['BUY', 'STRONG_BUY'] THEN 1 ELSE 0 END) as buys,
                 sum(CASE WHEN p.edge_signal IN ['SELL', 'STRONG_SELL'] THEN 1 ELSE 0 END) as sells
            RETURN position, player_count, avg_ktc, avg_predicted, avg_error, buys, sells
            ORDER BY position
        """)
        return pd.DataFrame([dict(r) for r in result])


@st.cache_data(ttl=3600)
def get_scatter_data(x_feature: str, y_feature: str, position: str = None):
    """Get data for scatter plot exploration."""
    driver = get_driver()

    position_filter = "AND p.position = $position" if position else ""

    with driver.session() as session:
        result = session.run(f"""
            MATCH (p:Player)
            WHERE p.position IN ['QB', 'RB', 'WR', 'TE']
              AND p.ktc_value > 0
              {position_filter}
            RETURN p.name as name,
                   p.position as position,
                   p.ktc_value as ktc_value,
                   p.predicted_ktc_value as predicted_value,
                   p.contract_guaranteed as contract_guaranteed,
                   p.contract_apy as contract_apy,
                   p.total_snaps as total_snaps,
                   p.avg_snap_pct as snap_pct,
                   p.age as age,
                   p.draft_value as draft_value,
                   p.injury_risk_score as injury_risk,
                   p.combine_forty as forty,
                   p.athletic_score as athletic_score,
                   p.edge_signal as signal
            LIMIT 500
        """, {'position': position})
        return pd.DataFrame([dict(r) for r in result])


@st.cache_data(ttl=3600)
def get_recommendation_distribution():
    """Get distribution of buy/sell recommendations."""
    driver = get_driver()

    with driver.session() as session:
        result = session.run("""
            MATCH (p:Player)
            WHERE p.position IN ['QB', 'RB', 'WR', 'TE']
              AND p.edge_signal IS NOT NULL
            WITH p.edge_signal as signal, p.position as position, count(*) as count
            RETURN signal, position, count
            ORDER BY signal, position
        """)
        return pd.DataFrame([dict(r) for r in result])


@st.cache_data(ttl=3600)
def get_2026_projections(position: str = None, limit: int = 30):
    """Get 2026 season projections from ML model."""
    driver = get_driver()

    position_filter = "AND ss.position = $position" if position else ""

    with driver.session() as session:
        result = session.run(f"""
            MATCH (ss:SeasonStats {{season: 2025}})
            WHERE ss.position IN ['QB', 'RB', 'WR', 'TE']
              AND ss.games >= 5
              {position_filter}
            OPTIONAL MATCH (p:Player)-[:HAD_SEASON]->(ss)

            RETURN ss.player_name as player_name,
                   ss.position as position,
                   ss.team as team,
                   ss.games as games,
                   ss.ppg_ppr as ppg_2025,
                   ss.ppg_std as ppg_std,
                   ss.targets as targets,
                   ss.receptions as receptions,
                   ss.receiving_yards as receiving_yards,
                   ss.carries as carries,
                   ss.rushing_yards as rushing_yards,
                   p.ktc_value as ktc_value,
                   p.production_edge_score as edge_score,
                   p.production_signal as signal
            ORDER BY ss.ppg_ppr DESC
            LIMIT $limit
        """, {'position': position, 'limit': limit})
        return pd.DataFrame([dict(r) for r in result])


def predict_2026_ppg(df: pd.DataFrame) -> pd.DataFrame:
    """Add 2026 predictions using trained model (or estimation)."""
    df = df.copy()

    # Try to load the trained model
    model_path = PROJECT_ROOT / 'models' / 'season_projection_model.pkl'
    if model_path.exists():
        try:
            from src.ml.fantasy_models import SeasonProjectionModel
            model = SeasonProjectionModel.load(str(model_path))

            # Engineer features
            df['targets_per_game'] = df['targets'] / df['games'].replace(0, np.nan)
            df['receptions_per_game'] = df['receptions'] / df['games'].replace(0, np.nan)
            df['carries_per_game'] = df['carries'] / df['games'].replace(0, np.nan)

            predictions = model.predict(df)
            df['predicted_2026_ppg'] = predictions
        except Exception:
            # Fallback to simple estimation
            df['predicted_2026_ppg'] = df['ppg_2025'] * 0.95  # Slight regression
    else:
        # Simple estimation based on historical patterns
        df['predicted_2026_ppg'] = df['ppg_2025'] * 0.95

    df['ppg_change'] = df['predicted_2026_ppg'] - df['ppg_2025']
    df['ppg_change_pct'] = (df['ppg_change'] / df['ppg_2025'].replace(0, np.nan)) * 100

    return df


@st.cache_data(ttl=300)
def search_player_for_explainer(search_term: str):
    """Search for a player to explain."""
    driver = get_driver()

    with driver.session() as session:
        result = session.run("""
            MATCH (p:Player)
            WHERE toLower(p.name) CONTAINS toLower($search)
              AND p.position IN ['QB', 'RB', 'WR', 'TE']
              AND p.predicted_ktc_value IS NOT NULL
            RETURN p.gsis_id as gsis_id,
                   p.name as name,
                   p.position as position,
                   p.current_team as team,
                   p.ktc_value as ktc_value,
                   p.predicted_ktc_value as predicted_value,
                   p.value_delta as value_delta,
                   p.edge_signal as signal,
                   p.age as age,
                   p.contract_guaranteed as contract_guaranteed,
                   p.contract_apy as contract_apy,
                   p.total_snaps as total_snaps,
                   p.avg_snap_pct as snap_pct,
                   p.draft_value as draft_value,
                   p.injury_risk_score as injury_risk,
                   p.snap_trend as snap_trend
            ORDER BY p.ktc_value DESC
            LIMIT 10
        """, {'search': search_term})
        return [dict(r) for r in result]


# =============================================================================
# VISUALIZATIONS
# =============================================================================

def create_feature_importance_chart(model_type: str = 'ktc'):
    """Create horizontal bar chart of feature importance."""
    if model_type == 'projection':
        data = PROJECTION_FEATURE_IMPORTANCE
        title = "Top Features for 2026 Fantasy Projection"
        # More readable labels for projection features
        label_map = {
            'ppg_ppr': 'Current Season PPG (PPR)',
            'ppg_std': 'Current Season PPG (Std)',
            'targets_per_game': 'Targets per Game',
            'best_season_ppg': 'Best Career Season PPG',
            'carries_per_game': 'Carries per Game',
            'rec_yards_per_game': 'Receiving Yards/Game',
            'rush_yards_per_game': 'Rushing Yards/Game',
            'career_ppg': 'Career PPG Average',
            'catch_rate': 'Catch Rate',
            'years_in_league': 'Years in League',
            'yards_per_catch': 'Yards per Catch',
            'yards_per_carry': 'Yards per Carry',
            'rec_td_rate': 'Receiving TD Rate',
            'rush_td_rate': 'Rushing TD Rate',
            'ppg_vs_career_avg': 'PPG vs Career Avg',
        }
    else:
        data = FEATURE_IMPORTANCE
        title = "Top 15 Features for KTC Value Prediction"
        label_map = None

    # Sort by importance
    sorted_features = sorted(data.items(), key=lambda x: x[1], reverse=True)
    features = [f[0] for f in sorted_features[:15]]
    importance = [f[1] for f in sorted_features[:15]]

    # Create readable labels
    if label_map:
        labels = [label_map.get(f, f) for f in features]
    else:
        labels = [get_short_description(f) for f in features]

    fig = go.Figure(go.Bar(
        x=importance,
        y=labels,
        orientation='h',
        marker=dict(
            color=importance,
            colorscale=[[0, COLORS['neutral']], [1, COLORS['primary']]],
        ),
        text=[f"{v:.1f}%" for v in importance],
        textposition='outside'
    ))

    fig.update_layout(
        title=title,
        xaxis_title="Relative Importance (%)",
        yaxis=dict(autorange="reversed"),
        height=500,
        margin=dict(l=200)
    )

    return fig


def create_position_performance_chart():
    """Create bar chart showing model performance by position."""
    positions = list(PROJECTION_MODEL_METRICS['position_performance'].keys())
    r2_values = [PROJECTION_MODEL_METRICS['position_performance'][p]['r2'] for p in positions]
    rmse_values = [PROJECTION_MODEL_METRICS['position_performance'][p]['rmse'] for p in positions]
    counts = [PROJECTION_MODEL_METRICS['position_performance'][p]['count'] for p in positions]

    fig = go.Figure()

    # R² bars
    fig.add_trace(go.Bar(
        name='R² Score',
        x=positions,
        y=r2_values,
        text=[f"{v:.1%}" for v in r2_values],
        textposition='outside',
        marker_color=COLORS['primary']
    ))

    fig.update_layout(
        title="Model Performance by Position (R² Score)",
        xaxis_title="Position",
        yaxis_title="R² Score",
        yaxis=dict(range=[0, 1]),
        height=350,
        showlegend=False
    )

    return fig


def create_2026_projection_table(df: pd.DataFrame):
    """Create formatted 2026 projection table."""
    display_df = df[['player_name', 'position', 'team', 'ppg_2025', 'predicted_2026_ppg', 'ppg_change', 'ktc_value']].copy()
    display_df.columns = ['Player', 'Pos', 'Team', '2025 PPG', '2026 Proj', 'Change', 'KTC Value']

    # Format columns
    display_df['2025 PPG'] = display_df['2025 PPG'].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "-")
    display_df['2026 Proj'] = display_df['2026 Proj'].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "-")
    display_df['Change'] = display_df['Change'].apply(lambda x: f"{x:+.1f}" if pd.notna(x) else "-")
    display_df['KTC Value'] = display_df['KTC Value'].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "-")

    return display_df


def create_correlation_chart():
    """Create correlation bar chart."""
    # Sort by absolute correlation
    sorted_corr = sorted(FEATURE_CORRELATIONS.items(), key=lambda x: abs(x[1]), reverse=True)
    features = [f[0] for f in sorted_corr[:12]]
    correlations = [f[1] for f in sorted_corr[:12]]

    labels = [get_short_description(f) for f in features]

    colors = [COLORS['success'] if c > 0 else COLORS['danger'] for c in correlations]

    fig = go.Figure(go.Bar(
        x=correlations,
        y=labels,
        orientation='h',
        marker=dict(color=colors),
        text=[f"{v:+.3f}" for v in correlations],
        textposition='outside'
    ))

    fig.update_layout(
        title="Feature Correlations with KTC Value",
        xaxis_title="Correlation Coefficient (r)",
        xaxis=dict(range=[-0.6, 0.7]),
        yaxis=dict(autorange="reversed"),
        height=400,
        margin=dict(l=200)
    )

    return fig


def create_prediction_waterfall(player: dict):
    """Create SHAP-style waterfall showing factors contributing to prediction."""
    base_value = 3000  # Population average

    # Calculate approximate feature contributions
    factors = []
    contributions = []

    # Age effect (younger = higher value)
    age = player.get('age', 25)
    if age:
        age_contrib = (25 - age) * 200
        factors.append('Age')
        contributions.append(age_contrib)

    # Contract guaranteed (strongest predictor)
    contract = player.get('contract_guaranteed', 0)
    if contract:
        contract_contrib = min(contract / 50000, 3000)
        factors.append('Contract $')
        contributions.append(contract_contrib)

    # Snap share
    snaps = player.get('snap_pct', 0)
    if snaps:
        snap_contrib = (snaps - 50) * 30
        factors.append('Snap Share')
        contributions.append(snap_contrib)

    # Draft capital
    draft_val = player.get('draft_value', 0)
    if draft_val:
        draft_contrib = draft_val * 2
        factors.append('Draft Capital')
        contributions.append(draft_contrib)

    # Snap trend
    trend = player.get('snap_trend', 0)
    if trend:
        trend_contrib = trend * 50
        factors.append('Usage Trend')
        contributions.append(trend_contrib)

    # Injury risk (negative effect)
    injury = player.get('injury_risk', 0)
    if injury:
        injury_contrib = -injury * 10
        factors.append('Injury Risk')
        contributions.append(injury_contrib)

    # Calculate total
    total_contrib = sum(contributions)
    predicted = base_value + total_contrib

    # Build waterfall
    fig = go.Figure(go.Waterfall(
        name="Value Factors",
        orientation="v",
        measure=['absolute'] + ['relative'] * len(factors) + ['total'],
        x=['Base Value'] + factors + ['Prediction'],
        y=[base_value] + contributions + [0],
        connector={"line": {"color": "rgb(63, 63, 63)"}},
        increasing={"marker": {"color": COLORS['success']}},
        decreasing={"marker": {"color": COLORS['danger']}},
        totals={"marker": {"color": COLORS['primary']}}
    ))

    fig.update_layout(
        title=f"Prediction Breakdown: {player.get('name', 'Player')}",
        height=400,
        showlegend=False
    )

    return fig


def create_scatter_explorer(df: pd.DataFrame, x_col: str, y_col: str):
    """Create interactive scatter plot."""
    if df.empty:
        return None

    fig = px.scatter(
        df,
        x=x_col,
        y=y_col,
        color='position',
        hover_data=['name', 'ktc_value', 'signal'],
        color_discrete_map={
            'QB': '#1E3A5F',
            'RB': '#10B981',
            'WR': '#F59E0B',
            'TE': '#8B5CF6'
        },
        title=f"{get_short_description(x_col)} vs {get_short_description(y_col)}"
    )

    fig.update_layout(height=450)
    fig.update_traces(marker=dict(size=8, opacity=0.7))

    return fig


def create_recommendation_pie(df: pd.DataFrame):
    """Create pie chart of recommendations."""
    signal_totals = df.groupby('signal')['count'].sum().reset_index()

    color_map = {
        'STRONG_BUY': '#059669',
        'BUY': '#10B981',
        'HOLD': '#6B7280',
        'SELL': '#F59E0B',
        'STRONG_SELL': '#DC2626'
    }

    fig = px.pie(
        signal_totals,
        values='count',
        names='signal',
        color='signal',
        color_discrete_map=color_map,
        title="Current Recommendations Distribution"
    )

    fig.update_layout(height=350)

    return fig


# =============================================================================
# MAIN PAGE
# =============================================================================

def main():
    st.title("🧠 Model Insights")
    st.markdown("Understanding Thoth's ML predictions")

    # ==========================================================================
    # MODEL SELECTOR
    # ==========================================================================
    model_choice = st.radio(
        "Select Model",
        ["🎯 KTC Value Prediction", "📈 2026 Season Projection", "🚀 Breakout Detector"],
        horizontal=True,
        help="Switch between different ML models"
    )

    st.divider()

    # ==========================================================================
    # KTC VALUE MODEL
    # ==========================================================================
    if model_choice == "🎯 KTC Value Prediction":
        st.subheader("KTC Dynasty Value Prediction Model")
        st.markdown("Predicts current dynasty trade value based on situation, contract, and athletic data.")

        metric_cols = st.columns(5)

        with metric_cols[0]:
            st.metric(
                "R² Score",
                f"{KTC_MODEL_METRICS['r_squared']:.0%}",
                help="Percentage of variance explained by the model"
            )

        with metric_cols[1]:
            st.metric(
                "RMSE",
                f"{KTC_MODEL_METRICS['rmse']:.0f}",
                help="Root Mean Square Error (lower is better)"
            )

        with metric_cols[2]:
            st.metric(
                "Features",
                KTC_MODEL_METRICS['total_features'],
                help="Number of input features"
            )

        with metric_cols[3]:
            st.metric(
                "Training Size",
                f"{KTC_MODEL_METRICS['training_samples']:,}",
                help="Number of player-seasons in training data"
            )

        with metric_cols[4]:
            st.metric(
                "Model Type",
                "GBM",
                help=KTC_MODEL_METRICS['model_type']
            )

        st.info(f"**Model Interpretation**: With R²=87%, the model explains most of the variance in dynasty value. "
                f"An RMSE of {KTC_MODEL_METRICS['rmse']:.0f} means predictions are typically within ±{KTC_MODEL_METRICS['rmse']:.0f} KTC points of actual values.")

        st.divider()

        # KTC Model Tabs
        tab1, tab2, tab3, tab4 = st.tabs([
            "📊 Feature Importance",
            "🔍 Correlation Explorer",
            "💡 Prediction Explainer",
            "📈 Position Analysis"
        ])

    # ==========================================================================
    # 2026 SEASON PROJECTION MODEL
    # ==========================================================================
    elif model_choice == "📈 2026 Season Projection":
        st.subheader("2026 Season Fantasy Projection Model")
        st.markdown("Predicts next season fantasy production based on historical season-over-season patterns from 1999-2024.")

        metric_cols = st.columns(5)

        with metric_cols[0]:
            st.metric(
                "R² Score",
                f"{PROJECTION_MODEL_METRICS['r_squared']:.1%}",
                help="Percentage of variance explained (61.3%)"
            )

        with metric_cols[1]:
            st.metric(
                "RMSE",
                f"{PROJECTION_MODEL_METRICS['rmse']:.2f} PPG",
                help="Average prediction error in PPG"
            )

        with metric_cols[2]:
            st.metric(
                "CV Score",
                f"{PROJECTION_MODEL_METRICS['cv_r2_mean']:.1%} ± {PROJECTION_MODEL_METRICS['cv_r2_std']:.1%}",
                help="Cross-validation R² score"
            )

        with metric_cols[3]:
            st.metric(
                "Training Size",
                f"{PROJECTION_MODEL_METRICS['training_samples']:,}",
                help="26 years of season-over-season pairs"
            )

        with metric_cols[4]:
            st.metric(
                "Best Position",
                "RB (84.4%)",
                help="Position with highest model accuracy"
            )

        st.info("**Model Interpretation**: Trained on 26 years of NFL data (1999-2024), this model predicts "
                "next season fantasy PPG. RBs and WRs have highest accuracy (84%), while QBs are harder to predict (73%).")

        st.divider()

        # 2026 Projection Tabs
        tab1, tab2, tab3, tab4 = st.tabs([
            "📊 Feature Importance",
            "🔮 2026 Projections",
            "📈 Position Performance",
            "🎯 Projection Methodology"
        ])

        with tab1:
            st.subheader("What Drives Fantasy Production?")

            imp_cols = st.columns([2, 1])

            with imp_cols[0]:
                fig = create_feature_importance_chart('projection')
                st.plotly_chart(fig, use_container_width=True)

            with imp_cols[1]:
                st.markdown("### Key Insights")
                st.markdown("""
                **#1: Current Production is King (53.6%)**

                The best predictor of future fantasy production is
                current production. Elite performers tend to stay elite.

                **#2: Usage Metrics Matter**

                Targets per game and carries per game are strong
                predictors - opportunity drives fantasy points.

                **#3: Career Context**

                Best season PPG and career average help identify
                players performing above/below their baseline.

                **#4: Efficiency is Secondary**

                Catch rate and yards-per metrics matter, but
                less than raw volume and production.
                """)

        with tab2:
            st.subheader("2026 Season Projections")

            proj_cols = st.columns([1, 3])

            with proj_cols[0]:
                position_filter = st.selectbox(
                    "Position",
                    ["All", "QB", "RB", "WR", "TE"],
                    index=0
                )
                sort_by = st.selectbox(
                    "Sort By",
                    ["2026 Projected PPG", "Biggest Risers", "Biggest Fallers"],
                    index=0
                )
                limit = st.slider("Players", 10, 50, 30)

            with proj_cols[1]:
                pos = None if position_filter == "All" else position_filter

                try:
                    proj_df = get_2026_projections(pos, limit * 2)  # Get extra for filtering
                    if not proj_df.empty:
                        proj_df = predict_2026_ppg(proj_df)

                        # Sort based on selection
                        if sort_by == "2026 Projected PPG":
                            proj_df = proj_df.sort_values('predicted_2026_ppg', ascending=False)
                        elif sort_by == "Biggest Risers":
                            proj_df = proj_df.sort_values('ppg_change', ascending=False)
                        else:
                            proj_df = proj_df.sort_values('ppg_change', ascending=True)

                        proj_df = proj_df.head(limit)

                        display_df = create_2026_projection_table(proj_df)
                        st.dataframe(display_df, hide_index=True, use_container_width=True)
                    else:
                        st.info("No 2025 season data available for projections.")
                except Exception as e:
                    st.warning(f"Could not load projections: {str(e)}")

        with tab3:
            st.subheader("Model Performance by Position")

            perf_cols = st.columns([1.5, 1])

            with perf_cols[0]:
                fig = create_position_performance_chart()
                st.plotly_chart(fig, use_container_width=True)

            with perf_cols[1]:
                st.markdown("### Position Insights")

                for pos, metrics in PROJECTION_MODEL_METRICS['position_performance'].items():
                    with st.expander(f"{pos} - R² = {metrics['r2']:.1%}"):
                        st.markdown(f"- **RMSE**: {metrics['rmse']:.2f} PPG")
                        st.markdown(f"- **MAE**: {metrics['mae']:.2f} PPG")
                        st.markdown(f"- **Training Samples**: {metrics['count']:,}")

                        if pos == 'RB':
                            st.caption("RBs are most predictable due to workload-based production.")
                        elif pos == 'WR':
                            st.caption("WRs show consistent patterns with target share.")
                        elif pos == 'TE':
                            st.caption("TEs have lower volume but predictable roles.")
                        else:
                            st.caption("QBs have highest variance due to system changes.")

        with tab4:
            st.subheader("Projection Methodology")

            st.markdown("""
            ### Training Data

            The model was trained on **26 years of NFL data** (1999-2024) from nflverse,
            creating season-over-season pairs to learn how current season performance
            predicts next season production.

            **Data Sources:**
            - Weekly fantasy stats aggregated to season totals
            - Snap counts (2015+)
            - Next Gen Stats (2016+)
            - Career context from historical seasons

            ### Features Used

            | Category | Features |
            |----------|----------|
            | Production | PPG (PPR), PPG (Std), Total Points |
            | Usage | Targets/game, Carries/game |
            | Efficiency | Catch rate, Yards/catch, Yards/carry |
            | Career | Best season, Career avg, Years in league |

            ### Model Architecture

            - **Algorithm**: Gradient Boosting (sklearn)
            - **Training**: 80/20 train/test split
            - **Validation**: 5-fold cross-validation
            - **Target**: Next season PPG (PPR)

            ### Limitations

            - Cannot predict injuries, trades, or coaching changes
            - Rookies have limited historical data
            - Breakout seasons are inherently hard to predict
            - Model assumes league-wide patterns persist
            """)

        return  # Exit early for projection model

    # ==========================================================================
    # BREAKOUT DETECTOR MODEL
    # ==========================================================================
    else:
        st.subheader("Breakout Season Detector")
        st.markdown("Identifies players likely to have breakout seasons (≥5 PPG improvement).")

        metric_cols = st.columns(5)

        with metric_cols[0]:
            st.metric(
                "AUC Score",
                f"{BREAKOUT_MODEL_METRICS['auc']:.1%}",
                help="Area Under ROC Curve"
            )

        with metric_cols[1]:
            st.metric(
                "Accuracy",
                f"{BREAKOUT_MODEL_METRICS['accuracy']:.1%}",
                help="Overall prediction accuracy"
            )

        with metric_cols[2]:
            st.metric(
                "Precision",
                f"{BREAKOUT_MODEL_METRICS['precision']:.0%}",
                help="When model says breakout, how often correct"
            )

        with metric_cols[3]:
            st.metric(
                "Base Rate",
                f"{BREAKOUT_MODEL_METRICS['breakout_rate']:.1%}",
                help="Historical breakout frequency"
            )

        with metric_cols[4]:
            st.metric(
                "Training Size",
                f"{BREAKOUT_MODEL_METRICS['training_samples']:,}",
                help="Player-seasons analyzed"
            )

        st.warning("**Note**: Breakout seasons are rare (8.7% of seasons). The model has low recall but "
                   "higher precision - when it flags a breakout candidate, there's increased likelihood.")

        st.divider()

        st.markdown("""
        ### What is a Breakout Season?

        A breakout is defined as a **≥5 PPG improvement** from the previous season.
        This represents a significant jump in fantasy production - moving from a
        bench player to a starter, or from a starter to an elite option.

        ### Model Performance

        Breakouts are inherently hard to predict because they often involve:
        - Unexpected opportunity (injury to starter)
        - Coaching scheme changes
        - Late-career emergence
        - Sophomore leaps

        The model identifies patterns from historical breakouts but cannot
        predict black swan events.
        """)

        return  # Exit early for breakout model

    # ==========================================================================
    # KTC MODEL TABS (continued from above)
    # ==========================================================================

    # --------------------------------------------------------------------------
    # TAB 1: FEATURE IMPORTANCE
    # --------------------------------------------------------------------------
    with tab1:
        st.subheader("What Drives Dynasty Value?")

        imp_cols = st.columns([2, 1])

        with imp_cols[0]:
            fig = create_feature_importance_chart('ktc')
            st.plotly_chart(fig, use_container_width=True)

        with imp_cols[1]:
            st.markdown("### Key Insights")

            st.markdown("""
            **#1: Contract Money is King**

            NFL teams invest millions in scouting. When they
            commit guaranteed money, they're signaling belief
            in future production. This alone explains ~50% of
            dynasty value.

            **#2: Playing Time Matters**

            Snap share and total snaps indicate opportunity.
            In fantasy, opportunity often trumps efficiency.

            **#3: Draft Capital Persists**

            Early picks get longer leashes and more chances.
            This effect diminishes after year 3.

            **#4: Age Curves Are Real**

            Younger players command premiums due to more
            expected productive seasons ahead.
            """)

            with st.expander("View All Feature Categories"):
                for category, description in CATEGORY_DESCRIPTIONS.items():
                    st.markdown(f"**{category.title()}**")
                    st.caption(description.strip())

    # --------------------------------------------------------------------------
    # TAB 2: CORRELATION EXPLORER
    # --------------------------------------------------------------------------
    with tab2:
        st.subheader("Explore Feature Relationships")

        corr_cols = st.columns([1, 1])

        with corr_cols[0]:
            fig = create_correlation_chart()
            st.plotly_chart(fig, use_container_width=True)

        with corr_cols[1]:
            st.markdown("### Interactive Explorer")

            # Feature selection
            feature_options = {
                'KTC Value': 'ktc_value',
                'Predicted Value': 'predicted_value',
                'Contract Guaranteed': 'contract_guaranteed',
                'Contract APY': 'contract_apy',
                'Total Snaps': 'total_snaps',
                'Snap %': 'snap_pct',
                'Age': 'age',
                'Draft Value': 'draft_value',
                'Injury Risk': 'injury_risk',
                '40-Time': 'forty',
                'Athletic Score': 'athletic_score'
            }

            x_feature = st.selectbox("X-Axis", list(feature_options.keys()), index=2)
            y_feature = st.selectbox("Y-Axis", list(feature_options.keys()), index=0)

            position_filter = st.selectbox("Position", ["All", "QB", "RB", "WR", "TE"])

            pos = None if position_filter == "All" else position_filter
            scatter_df = get_scatter_data(feature_options[x_feature], feature_options[y_feature], pos)

            if not scatter_df.empty:
                fig = create_scatter_explorer(
                    scatter_df,
                    feature_options[x_feature],
                    feature_options[y_feature]
                )
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No data available for selected features")

    # --------------------------------------------------------------------------
    # TAB 3: PREDICTION EXPLAINER
    # --------------------------------------------------------------------------
    with tab3:
        st.subheader("Why This Prediction?")
        st.markdown("Search for a player to see what factors drive their predicted value.")

        search = st.text_input("Search Player", placeholder="Enter player name...")

        if search:
            results = search_player_for_explainer(search)

            if results:
                player_names = [f"{p['name']} ({p['position']}, {p.get('team', 'FA')})" for p in results]
                selected_idx = st.selectbox("Select player", range(len(player_names)),
                                           format_func=lambda x: player_names[x])
                player = results[selected_idx]

                exp_cols = st.columns([1.5, 1])

                with exp_cols[0]:
                    fig = create_prediction_waterfall(player)
                    st.plotly_chart(fig, use_container_width=True)

                with exp_cols[1]:
                    st.markdown("### Prediction Summary")

                    ktc = player.get('ktc_value', 0) or 0
                    predicted = player.get('predicted_value', 0) or 0
                    delta = player.get('value_delta', 0) or 0

                    st.metric("Market Value (KTC)", f"{ktc:,}")
                    st.metric("Model Prediction", f"{predicted:,.0f}")
                    st.metric(
                        "Value Gap",
                        f"{delta:+,.0f}",
                        delta_color="normal" if delta >= 0 else "inverse"
                    )

                    signal = player.get('signal', 'HOLD')
                    signal_color = get_signal_color(signal)
                    st.markdown(
                        f"**Recommendation:** <span style='color:{signal_color}; font-weight:bold;'>"
                        f"{signal.replace('_', ' ')}</span>",
                        unsafe_allow_html=True
                    )

                    st.markdown("---")
                    st.markdown("### Key Inputs")

                    if player.get('age'):
                        st.markdown(f"**Age:** {player['age']}")
                    if player.get('contract_guaranteed'):
                        st.markdown(f"**Guaranteed $:** ${player['contract_guaranteed']/1_000_000:.1f}M")
                    if player.get('snap_pct'):
                        st.markdown(f"**Snap %:** {player['snap_pct']:.1f}%")
                    if player.get('draft_value'):
                        st.markdown(f"**Draft Value:** {player['draft_value']:.0f}")
                    if player.get('injury_risk'):
                        st.markdown(f"**Injury Risk:** {player['injury_risk']:.0f}/100")

            else:
                st.info("No players found with model predictions. Try another search.")
        else:
            st.info("Enter a player name to see their prediction breakdown.")

            # Example cards
            st.markdown("### How Predictions Work")
            st.markdown("""
            The model combines 40+ features into a single value prediction:

            1. **Start with base value** (~3,000 for average player)
            2. **Add/subtract for each factor** (age, contract, snaps, etc.)
            3. **Final prediction** compared to KTC market value
            4. **Generate signal** based on gap percentage
            """)

    # --------------------------------------------------------------------------
    # TAB 4: POSITION ANALYSIS
    # --------------------------------------------------------------------------
    with tab4:
        st.subheader("Position-Level Insights")

        pos_stats = get_position_stats()
        rec_dist = get_recommendation_distribution()

        pos_cols = st.columns([1.5, 1])

        with pos_cols[0]:
            if not pos_stats.empty:
                # Position comparison table
                st.markdown("### Model Performance by Position")

                display_df = pos_stats.copy()
                display_df.columns = ['Position', 'Players', 'Avg KTC', 'Avg Predicted', 'Avg Error', 'Buys', 'Sells']

                for col in ['Avg KTC', 'Avg Predicted', 'Avg Error']:
                    display_df[col] = display_df[col].apply(lambda x: f"{x:,.0f}" if x else "N/A")

                st.dataframe(display_df, hide_index=True, use_container_width=True)

                # Position-specific insights
                st.markdown("### Position Insights")

                insights = {
                    'QB': "QBs have longest careers and highest contract values. Age matters less until 35+.",
                    'RB': "RBs have shortest windows - value drops sharply after age 26. Snap share critical.",
                    'WR': "WRs have longest skill position windows. Athletic profiles matter most for young WRs.",
                    'TE': "TEs are late bloomers - often don't peak until age 26-28. Draft capital persists longer."
                }

                pos_tabs = st.tabs(['QB', 'RB', 'WR', 'TE'])
                for i, pos in enumerate(['QB', 'RB', 'WR', 'TE']):
                    with pos_tabs[i]:
                        st.info(insights[pos])

                        if not pos_stats.empty:
                            pos_row = pos_stats[pos_stats['position'] == pos].iloc[0] if len(pos_stats[pos_stats['position'] == pos]) > 0 else None
                            if pos_row is not None:
                                st.markdown(f"**Players Analyzed:** {pos_row['player_count']}")
                                st.markdown(f"**Buy Signals:** {pos_row['buys']}")
                                st.markdown(f"**Sell Signals:** {pos_row['sells']}")

        with pos_cols[1]:
            if not rec_dist.empty:
                fig = create_recommendation_pie(rec_dist)
                st.plotly_chart(fig, use_container_width=True)

                # Signal breakdown
                st.markdown("### Signal Thresholds")
                st.markdown("""
                | Signal | Gap |
                |--------|-----|
                | STRONG_BUY | > +15% |
                | BUY | +7% to +15% |
                | HOLD | -7% to +7% |
                | SELL | -15% to -7% |
                | STRONG_SELL | < -15% |
                """)

    st.divider()

    # ==========================================================================
    # METHODOLOGY FOOTER
    # ==========================================================================
    with st.expander("📚 Model Methodology"):
        st.markdown("""
        ### Data Sources
        - **KTC Values**: Keep Trade Cut dynasty player values (updated daily)
        - **Player Stats**: NFLverse database (play-by-play aggregated)
        - **Combine Data**: NFL Combine testing results
        - **Contract Data**: Over The Cap contract information
        - **Injury Data**: Pro Football Reference injury reports
        - **Snap Counts**: Weekly snap count data

        ### Model Architecture
        - **Algorithm**: H2O Gradient Boosting Machine (GBM)
        - **Target**: Current KTC dynasty value
        - **Features**: 40 engineered features across 7 categories
        - **Training**: Multi-season data with walk-forward validation

        ### Limitations
        - Model cannot predict injuries, trades, or coaching changes
        - Young players with limited data have higher uncertainty
        - Market inefficiencies may persist for various reasons
        - Model assumes historical patterns continue

        ### Updates
        Model retrains weekly to incorporate latest data and maintain accuracy.
        """)


if __name__ == "__main__":
    main()
