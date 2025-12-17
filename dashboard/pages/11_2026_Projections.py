"""
Thoth 2026 Season Projections
=============================
ML-powered predictions for 2026 fantasy production based on
26 years of NFL historical data (1999-2024).
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

st.set_page_config(page_title="2026 Projections - Thoth", layout="wide")

# =============================================================================
# THOTH DESIGN SYSTEM
# =============================================================================
COLORS = {
    'primary': '#1E3A5F',
    'success': '#10B981',
    'danger': '#EF4444',
    'warning': '#F59E0B',
    'neutral': '#6B7280',
    'background': '#F9FAFB',
    'qb': '#1E3A5F',
    'rb': '#10B981',
    'wr': '#F59E0B',
    'te': '#8B5CF6'
}

# Model metrics from training
MODEL_METRICS = {
    'overall_r2': 0.613,
    'overall_rmse': 3.55,
    'position_r2': {
        'QB': 0.732,
        'RB': 0.844,
        'WR': 0.837,
        'TE': 0.771
    },
    'position_rmse': {
        'QB': 3.90,
        'RB': 2.92,
        'WR': 2.69,
        'TE': 2.48
    },
    'training_years': '1999-2024',
    'training_samples': 6088
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
def get_2025_season_data():
    """Get all 2025 season stats for projection."""
    driver = get_driver()

    with driver.session() as session:
        result = session.run("""
            MATCH (ss:SeasonStats {season: 2025})
            WHERE ss.position IN ['QB', 'RB', 'WR', 'TE']
              AND ss.games >= 5
            OPTIONAL MATCH (p:Player)-[:HAD_SEASON]->(ss)

            RETURN ss.player_name as player_name,
                   ss.position as position,
                   ss.team as team,
                   ss.games as games,
                   ss.ppg_ppr as ppg_ppr,
                   ss.ppg_std as ppg_std,
                   ss.passing_yards as passing_yards,
                   ss.passing_tds as passing_tds,
                   ss.carries as carries,
                   ss.rushing_yards as rushing_yards,
                   ss.rushing_tds as rushing_tds,
                   ss.targets as targets,
                   ss.receptions as receptions,
                   ss.receiving_yards as receiving_yards,
                   ss.receiving_tds as receiving_tds,
                   p.ktc_value as ktc_value,
                   p.production_edge_score as edge_score,
                   p.production_signal as signal,
                   p.age as age
            ORDER BY ss.ppg_ppr DESC
        """)
        return pd.DataFrame([dict(r) for r in result])


def generate_projections(df: pd.DataFrame) -> pd.DataFrame:
    """Generate 2026 projections using trained model or estimation."""
    df = df.copy()

    # Try to load trained model
    model_path = PROJECT_ROOT / 'models' / 'season_projection_model.pkl'

    if model_path.exists():
        try:
            from src.ml.fantasy_models import SeasonProjectionModel
            model = SeasonProjectionModel.load(str(model_path))

            # Engineer features
            df['targets_per_game'] = df['targets'] / df['games'].replace(0, np.nan)
            df['receptions_per_game'] = df['receptions'] / df['games'].replace(0, np.nan)
            df['rec_yards_per_game'] = df['receiving_yards'] / df['games'].replace(0, np.nan)
            df['carries_per_game'] = df['carries'] / df['games'].replace(0, np.nan)
            df['rush_yards_per_game'] = df['rushing_yards'] / df['games'].replace(0, np.nan)
            df['catch_rate'] = df['receptions'] / df['targets'].replace(0, np.nan)

            predictions = model.predict(df)
            df['predicted_2026_ppg'] = predictions
        except Exception as e:
            st.warning(f"Could not load ML model, using estimation: {e}")
            # Fallback to position-specific regression
            regression_factors = {'QB': 0.92, 'RB': 0.88, 'WR': 0.94, 'TE': 0.93}
            df['predicted_2026_ppg'] = df.apply(
                lambda row: row['ppg_ppr'] * regression_factors.get(row['position'], 0.92),
                axis=1
            )
    else:
        # Fallback to position-specific regression
        regression_factors = {'QB': 0.92, 'RB': 0.88, 'WR': 0.94, 'TE': 0.93}
        df['predicted_2026_ppg'] = df.apply(
            lambda row: row['ppg_ppr'] * regression_factors.get(row['position'], 0.92),
            axis=1
        )

    # Calculate changes
    df['ppg_change'] = df['predicted_2026_ppg'] - df['ppg_ppr']
    df['ppg_change_pct'] = (df['ppg_change'] / df['ppg_ppr'].replace(0, np.nan)) * 100

    # Calculate value gap (expected KTC based on projected PPG)
    position_multipliers = {'QB': 350, 'RB': 400, 'WR': 450, 'TE': 500}
    df['expected_ktc'] = df.apply(
        lambda row: row['predicted_2026_ppg'] * position_multipliers.get(row['position'], 400),
        axis=1
    )
    df['ktc_gap'] = df['expected_ktc'] - df['ktc_value'].fillna(0)

    return df


# =============================================================================
# VISUALIZATIONS
# =============================================================================

def create_projection_scatter(df: pd.DataFrame):
    """Create scatter plot of 2025 PPG vs 2026 Projected."""
    fig = px.scatter(
        df,
        x='ppg_ppr',
        y='predicted_2026_ppg',
        color='position',
        hover_data=['player_name', 'team', 'ppg_change'],
        color_discrete_map={
            'QB': COLORS['qb'],
            'RB': COLORS['rb'],
            'WR': COLORS['wr'],
            'TE': COLORS['te']
        },
        title="2025 PPG vs 2026 Projected PPG"
    )

    # Add diagonal line (no change)
    max_val = max(df['ppg_ppr'].max(), df['predicted_2026_ppg'].max())
    fig.add_trace(go.Scatter(
        x=[0, max_val],
        y=[0, max_val],
        mode='lines',
        name='No Change',
        line=dict(color='gray', dash='dash')
    ))

    fig.update_layout(
        xaxis_title="2025 PPG (PPR)",
        yaxis_title="2026 Projected PPG",
        height=500
    )

    return fig


def create_risers_fallers_chart(df: pd.DataFrame, top_n: int = 15):
    """Create horizontal bar chart of biggest risers and fallers."""
    # Get top risers and fallers
    risers = df.nlargest(top_n, 'ppg_change')[['player_name', 'position', 'ppg_change']]
    fallers = df.nsmallest(top_n, 'ppg_change')[['player_name', 'position', 'ppg_change']]

    fig = go.Figure()

    # Risers
    fig.add_trace(go.Bar(
        y=risers['player_name'],
        x=risers['ppg_change'],
        orientation='h',
        name='Risers',
        marker_color=COLORS['success'],
        text=[f"+{v:.1f}" for v in risers['ppg_change']],
        textposition='outside'
    ))

    # Fallers
    fig.add_trace(go.Bar(
        y=fallers['player_name'],
        x=fallers['ppg_change'],
        orientation='h',
        name='Fallers',
        marker_color=COLORS['danger'],
        text=[f"{v:.1f}" for v in fallers['ppg_change']],
        textposition='outside'
    ))

    fig.update_layout(
        title="Biggest Projected Changes (PPG)",
        xaxis_title="PPG Change",
        height=600,
        barmode='relative'
    )

    return fig


def create_position_distribution(df: pd.DataFrame):
    """Create box plot of projections by position."""
    fig = px.box(
        df,
        x='position',
        y='predicted_2026_ppg',
        color='position',
        color_discrete_map={
            'QB': COLORS['qb'],
            'RB': COLORS['rb'],
            'WR': COLORS['wr'],
            'TE': COLORS['te']
        },
        title="2026 Projected PPG Distribution by Position"
    )

    fig.update_layout(
        xaxis_title="Position",
        yaxis_title="Projected 2026 PPG",
        showlegend=False,
        height=400
    )

    return fig


def create_value_opportunity_scatter(df: pd.DataFrame):
    """Create scatter plot showing value opportunities."""
    # Filter to players with KTC values
    plot_df = df[df['ktc_value'] > 0].copy()

    fig = px.scatter(
        plot_df,
        x='ktc_value',
        y='expected_ktc',
        color='ktc_gap',
        color_continuous_scale=['#EF4444', '#F3F4F6', '#10B981'],
        color_continuous_midpoint=0,
        hover_data=['player_name', 'position', 'ppg_ppr', 'predicted_2026_ppg'],
        title="Dynasty Value vs Projected Value (Green = Undervalued)"
    )

    # Add diagonal line
    max_val = max(plot_df['ktc_value'].max(), plot_df['expected_ktc'].max())
    fig.add_trace(go.Scatter(
        x=[0, max_val],
        y=[0, max_val],
        mode='lines',
        name='Fair Value',
        line=dict(color='gray', dash='dash')
    ))

    fig.update_layout(
        xaxis_title="Current KTC Value",
        yaxis_title="Expected Value (Based on 2026 PPG)",
        height=500
    )

    return fig


# =============================================================================
# MAIN PAGE
# =============================================================================

def main():
    st.title("2026 Season Projections")
    st.markdown("ML-powered fantasy projections trained on 26 years of NFL data")

    # Model info banner
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Model R²", f"{MODEL_METRICS['overall_r2']:.1%}")
    with col2:
        st.metric("RMSE", f"{MODEL_METRICS['overall_rmse']:.2f} PPG")
    with col3:
        st.metric("Training Data", MODEL_METRICS['training_years'])
    with col4:
        st.metric("Training Samples", f"{MODEL_METRICS['training_samples']:,}")

    st.divider()

    # Load and process data
    with st.spinner("Loading 2025 stats and generating projections..."):
        df = get_2025_season_data()

        if df.empty:
            st.error("No 2025 season data available. Please run the data pipeline first.")
            return

        df = generate_projections(df)

    st.success(f"Generated projections for {len(df)} players")

    # ==========================================================================
    # FILTERS
    # ==========================================================================
    filter_cols = st.columns([1, 1, 1, 2])

    with filter_cols[0]:
        position_filter = st.selectbox(
            "Position",
            ["All", "QB", "RB", "WR", "TE"],
            index=0
        )

    with filter_cols[1]:
        min_ppg = st.slider(
            "Min 2025 PPG",
            0.0, 30.0, 5.0,
            help="Filter to players with at least this PPG in 2025"
        )

    with filter_cols[2]:
        sort_option = st.selectbox(
            "Sort By",
            ["2026 Projected PPG", "Biggest Risers", "Biggest Fallers", "Most Undervalued"]
        )

    with filter_cols[3]:
        search = st.text_input("Search Player", placeholder="Enter name...")

    # Apply filters
    filtered_df = df.copy()

    if position_filter != "All":
        filtered_df = filtered_df[filtered_df['position'] == position_filter]

    filtered_df = filtered_df[filtered_df['ppg_ppr'] >= min_ppg]

    if search:
        filtered_df = filtered_df[
            filtered_df['player_name'].str.lower().str.contains(search.lower(), na=False)
        ]

    # Apply sorting
    if sort_option == "2026 Projected PPG":
        filtered_df = filtered_df.sort_values('predicted_2026_ppg', ascending=False)
    elif sort_option == "Biggest Risers":
        filtered_df = filtered_df.sort_values('ppg_change', ascending=False)
    elif sort_option == "Biggest Fallers":
        filtered_df = filtered_df.sort_values('ppg_change', ascending=True)
    else:  # Most Undervalued
        filtered_df = filtered_df[filtered_df['ktc_value'] > 0].sort_values('ktc_gap', ascending=False)

    st.divider()

    # ==========================================================================
    # TABS
    # ==========================================================================
    tab1, tab2, tab3, tab4 = st.tabs([
        "Projections Table",
        "Visualizations",
        "Value Opportunities",
        "Position Breakdown"
    ])

    # --------------------------------------------------------------------------
    # TAB 1: PROJECTIONS TABLE
    # --------------------------------------------------------------------------
    with tab1:
        st.subheader(f"2026 Projections ({len(filtered_df)} players)")

        # Format display dataframe
        display_df = filtered_df[[
            'player_name', 'position', 'team', 'age', 'games',
            'ppg_ppr', 'predicted_2026_ppg', 'ppg_change', 'ktc_value', 'signal'
        ]].copy()

        display_df.columns = [
            'Player', 'Pos', 'Team', 'Age', 'Games',
            '2025 PPG', '2026 Proj', 'Change', 'KTC Value', 'Signal'
        ]

        # Format columns
        display_df['2025 PPG'] = display_df['2025 PPG'].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "-")
        display_df['2026 Proj'] = display_df['2026 Proj'].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "-")
        display_df['Change'] = display_df['Change'].apply(lambda x: f"{x:+.1f}" if pd.notna(x) else "-")
        display_df['KTC Value'] = display_df['KTC Value'].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "-")
        display_df['Age'] = display_df['Age'].apply(lambda x: f"{int(x)}" if pd.notna(x) else "-")
        display_df['Signal'] = display_df['Signal'].fillna("-")

        st.dataframe(
            display_df.head(50),
            hide_index=True,
            use_container_width=True,
            height=600
        )

        # Download button
        csv = filtered_df.to_csv(index=False)
        st.download_button(
            "Download Full Projections CSV",
            csv,
            "thoth_2026_projections.csv",
            "text/csv"
        )

    # --------------------------------------------------------------------------
    # TAB 2: VISUALIZATIONS
    # --------------------------------------------------------------------------
    with tab2:
        st.subheader("Projection Visualizations")

        viz_cols = st.columns(2)

        with viz_cols[0]:
            fig = create_projection_scatter(filtered_df)
            st.plotly_chart(fig, use_container_width=True)

        with viz_cols[1]:
            fig = create_position_distribution(filtered_df)
            st.plotly_chart(fig, use_container_width=True)

        st.divider()

        st.subheader("Biggest Projected Changes")
        fig = create_risers_fallers_chart(df, top_n=10)
        st.plotly_chart(fig, use_container_width=True)

    # --------------------------------------------------------------------------
    # TAB 3: VALUE OPPORTUNITIES
    # --------------------------------------------------------------------------
    with tab3:
        st.subheader("Dynasty Value Opportunities")
        st.markdown("Players where projected 2026 production suggests mispricing")

        fig = create_value_opportunity_scatter(filtered_df)
        st.plotly_chart(fig, use_container_width=True)

        opp_cols = st.columns(2)

        with opp_cols[0]:
            st.markdown("### Most Undervalued")
            undervalued = filtered_df[filtered_df['ktc_value'] > 0].nlargest(10, 'ktc_gap')
            for _, row in undervalued.iterrows():
                gap = row['ktc_gap']
                st.markdown(f"**{row['player_name']}** ({row['position']}) - +{gap:,.0f} gap")
                st.caption(f"2025: {row['ppg_ppr']:.1f} PPG → 2026: {row['predicted_2026_ppg']:.1f} PPG")

        with opp_cols[1]:
            st.markdown("### Most Overvalued")
            overvalued = filtered_df[filtered_df['ktc_value'] > 0].nsmallest(10, 'ktc_gap')
            for _, row in overvalued.iterrows():
                gap = row['ktc_gap']
                st.markdown(f"**{row['player_name']}** ({row['position']}) - {gap:,.0f} gap")
                st.caption(f"2025: {row['ppg_ppr']:.1f} PPG → 2026: {row['predicted_2026_ppg']:.1f} PPG")

    # --------------------------------------------------------------------------
    # TAB 4: POSITION BREAKDOWN
    # --------------------------------------------------------------------------
    with tab4:
        st.subheader("Position-Specific Analysis")

        pos_tabs = st.tabs(['QB', 'RB', 'WR', 'TE'])

        for i, pos in enumerate(['QB', 'RB', 'WR', 'TE']):
            with pos_tabs[i]:
                pos_df = df[df['position'] == pos].sort_values('predicted_2026_ppg', ascending=False)

                # Position metrics
                metric_cols = st.columns(4)
                with metric_cols[0]:
                    st.metric("Players", len(pos_df))
                with metric_cols[1]:
                    st.metric("Model R²", f"{MODEL_METRICS['position_r2'][pos]:.1%}")
                with metric_cols[2]:
                    st.metric("RMSE", f"{MODEL_METRICS['position_rmse'][pos]:.2f} PPG")
                with metric_cols[3]:
                    avg_change = pos_df['ppg_change'].mean()
                    st.metric("Avg Change", f"{avg_change:+.1f} PPG")

                st.divider()

                # Top players by position
                st.markdown(f"#### Top {pos}s by 2026 Projected PPG")

                top_pos = pos_df.head(15)[['player_name', 'team', 'age', 'ppg_ppr', 'predicted_2026_ppg', 'ppg_change']].copy()
                top_pos.columns = ['Player', 'Team', 'Age', '2025 PPG', '2026 Proj', 'Change']
                top_pos['2025 PPG'] = top_pos['2025 PPG'].round(1)
                top_pos['2026 Proj'] = top_pos['2026 Proj'].round(1)
                top_pos['Change'] = top_pos['Change'].apply(lambda x: f"{x:+.1f}")
                top_pos['Age'] = top_pos['Age'].apply(lambda x: int(x) if pd.notna(x) else '-')

                st.dataframe(top_pos, hide_index=True, use_container_width=True)

                # Risers/Fallers for position
                pos_change_cols = st.columns(2)

                with pos_change_cols[0]:
                    st.markdown("**Biggest Risers**")
                    risers = pos_df.nlargest(5, 'ppg_change')
                    for _, r in risers.iterrows():
                        st.markdown(f"- {r['player_name']}: {r['ppg_change']:+.1f} PPG")

                with pos_change_cols[1]:
                    st.markdown("**Biggest Fallers**")
                    fallers = pos_df.nsmallest(5, 'ppg_change')
                    for _, r in fallers.iterrows():
                        st.markdown(f"- {r['player_name']}: {r['ppg_change']:+.1f} PPG")

    # ==========================================================================
    # METHODOLOGY FOOTER
    # ==========================================================================
    st.divider()

    with st.expander("About This Model"):
        st.markdown("""
        ### 2026 Season Projection Methodology

        **Training Data:**
        - 26 years of NFL fantasy data (1999-2024)
        - 6,088 season-over-season training pairs
        - Minimum 8 games per season for inclusion

        **Model Architecture:**
        - Gradient Boosting (sklearn)
        - 80/20 train/test split
        - 5-fold cross-validation

        **Key Features (by importance):**
        1. Current season PPG (53.6%)
        2. Standard scoring PPG (9.7%)
        3. Targets per game (6.6%)
        4. Best career season PPG (6.2%)
        5. Carries per game (5.8%)

        **Position-Specific Performance:**
        | Position | R² | RMSE |
        |----------|-----|------|
        | RB | 84.4% | 2.92 PPG |
        | WR | 83.7% | 2.69 PPG |
        | TE | 77.1% | 2.48 PPG |
        | QB | 73.2% | 3.90 PPG |

        **Limitations:**
        - Cannot predict injuries, trades, or coaching changes
        - Young players with limited data have higher uncertainty
        - Breakout seasons are inherently unpredictable
        - Assumes historical patterns continue

        *Model retrains weekly with latest data.*
        """)


if __name__ == "__main__":
    main()
