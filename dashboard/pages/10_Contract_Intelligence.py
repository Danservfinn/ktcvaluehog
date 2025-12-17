"""
Thoth Contract Intelligence
===========================
Analyze NFL contracts and their impact on dynasty value.
Find value efficiency and contract-based edges.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.components.tooltips import render_category_help, get_signal_color

st.set_page_config(page_title="Contract Intelligence - Thoth", layout="wide")

# =============================================================================
# THOTH DESIGN SYSTEM
# =============================================================================
COLORS = {
    'primary': '#1E3A5F',
    'success': '#10B981',
    'danger': '#EF4444',
    'warning': '#F59E0B',
    'neutral': '#6B7280',
    'QB': '#1E3A5F',
    'RB': '#10B981',
    'WR': '#F59E0B',
    'TE': '#8B5CF6'
}


def get_driver():
    """Get Neo4j driver."""
    if 'neo4j_driver' not in st.session_state:
        from neo4j import GraphDatabase
        uri = st.secrets.get("neo4j_uri", "bolt://localhost:7687")
        st.session_state.neo4j_driver = GraphDatabase.driver(uri, auth=None)
    return st.session_state.neo4j_driver


def format_money(value):
    """Format money values."""
    if value is None or pd.isna(value):
        return "N/A"
    if value >= 1_000_000:
        return f"${value/1_000_000:.1f}M"
    if value >= 1_000:
        return f"${value/1_000:.0f}K"
    return f"${value:.0f}"


# =============================================================================
# DATA QUERIES
# =============================================================================

@st.cache_data(ttl=3600)
def get_contract_leaderboard(position: str = None, sort_by: str = 'apy', limit: int = 50):
    """Get contract leaderboard."""
    driver = get_driver()

    position_filter = "AND p.position = $position" if position else ""

    sort_map = {
        'apy': 'p.contract_apy DESC',
        'guaranteed': 'p.contract_guaranteed DESC',
        'ktc_value': 'p.ktc_value DESC',
        'value_efficiency': '(p.fantasy_points_season / p.contract_apy * 1000000) DESC'
    }
    sort_clause = sort_map.get(sort_by, 'p.contract_apy DESC')

    with driver.session() as session:
        result = session.run(f"""
            MATCH (p:Player)
            WHERE p.position IN ['QB', 'RB', 'WR', 'TE']
              AND p.contract_apy IS NOT NULL
              AND p.contract_apy > 0
              {position_filter}
            RETURN p.gsis_id as gsis_id,
                   p.name as name,
                   p.position as position,
                   p.current_team as team,
                   p.age as age,
                   p.contract_apy as apy,
                   p.contract_guaranteed as guaranteed,
                   p.contract_value as total_value,
                   p.contract_guaranteed_pct as guaranteed_pct,
                   p.contract_cap_pct as cap_pct,
                   p.contract_years as years_remaining,
                   p.ktc_value as ktc_value,
                   p.predicted_ktc_value as predicted_value,
                   p.edge_signal as signal,
                   p.fantasy_points_season as fpts,
                   p.avg_snap_pct as snap_pct
            ORDER BY {sort_clause}
            LIMIT $limit
        """, {'position': position, 'limit': limit})
        return pd.DataFrame([dict(r) for r in result])


@st.cache_data(ttl=3600)
def get_value_efficiency_data(position: str = None):
    """Get data for value efficiency scatter."""
    driver = get_driver()

    position_filter = "AND p.position = $position" if position else ""

    with driver.session() as session:
        result = session.run(f"""
            MATCH (p:Player)
            WHERE p.position IN ['QB', 'RB', 'WR', 'TE']
              AND p.contract_apy IS NOT NULL
              AND p.contract_apy > 0
              AND p.fantasy_points_season IS NOT NULL
              AND p.fantasy_points_season > 0
              {position_filter}
            RETURN p.name as name,
                   p.position as position,
                   p.current_team as team,
                   p.contract_apy as apy,
                   p.contract_guaranteed as guaranteed,
                   p.fantasy_points_season as fpts,
                   p.ktc_value as ktc_value,
                   p.edge_signal as signal,
                   p.age as age
            LIMIT 200
        """, {'position': position})
        return pd.DataFrame([dict(r) for r in result])


@st.cache_data(ttl=3600)
def get_position_contract_stats():
    """Get contract statistics by position."""
    driver = get_driver()

    with driver.session() as session:
        result = session.run("""
            MATCH (p:Player)
            WHERE p.position IN ['QB', 'RB', 'WR', 'TE']
              AND p.contract_apy IS NOT NULL
              AND p.contract_apy > 0
            WITH p.position as position,
                 count(p) as player_count,
                 avg(p.contract_apy) as avg_apy,
                 max(p.contract_apy) as max_apy,
                 avg(p.contract_guaranteed) as avg_guaranteed,
                 avg(p.contract_guaranteed_pct) as avg_guaranteed_pct,
                 avg(p.ktc_value) as avg_ktc
            RETURN position, player_count, avg_apy, max_apy, avg_guaranteed, avg_guaranteed_pct, avg_ktc
            ORDER BY avg_apy DESC
        """)
        return pd.DataFrame([dict(r) for r in result])


@st.cache_data(ttl=3600)
def get_contract_value_mismatches():
    """Find players with contract/value mismatches."""
    driver = get_driver()

    with driver.session() as session:
        # High paid but low value (potential sell)
        overpaid = session.run("""
            MATCH (p:Player)
            WHERE p.position IN ['QB', 'RB', 'WR', 'TE']
              AND p.contract_apy IS NOT NULL
              AND p.contract_apy > 10000000
              AND p.edge_signal IN ['SELL', 'STRONG_SELL']
            RETURN p.name as name,
                   p.position as position,
                   p.current_team as team,
                   p.age as age,
                   p.contract_apy as apy,
                   p.contract_guaranteed as guaranteed,
                   p.ktc_value as ktc_value,
                   p.value_delta as value_gap,
                   p.edge_signal as signal,
                   p.fantasy_points_season as fpts
            ORDER BY p.contract_apy DESC
            LIMIT 15
        """)
        overpaid_df = pd.DataFrame([dict(r) for r in overpaid])

        # Low paid but high value (potential buy)
        underpaid = session.run("""
            MATCH (p:Player)
            WHERE p.position IN ['QB', 'RB', 'WR', 'TE']
              AND p.contract_apy IS NOT NULL
              AND p.contract_apy < 15000000
              AND p.edge_signal IN ['BUY', 'STRONG_BUY']
              AND p.ktc_value > 3000
            RETURN p.name as name,
                   p.position as position,
                   p.current_team as team,
                   p.age as age,
                   p.contract_apy as apy,
                   p.contract_guaranteed as guaranteed,
                   p.ktc_value as ktc_value,
                   p.value_delta as value_gap,
                   p.edge_signal as signal,
                   p.fantasy_points_season as fpts
            ORDER BY p.value_delta DESC
            LIMIT 15
        """)
        underpaid_df = pd.DataFrame([dict(r) for r in underpaid])

        return overpaid_df, underpaid_df


@st.cache_data(ttl=3600)
def get_expiring_contracts():
    """Get players with expiring contracts."""
    driver = get_driver()

    with driver.session() as session:
        result = session.run("""
            MATCH (p:Player)
            WHERE p.position IN ['QB', 'RB', 'WR', 'TE']
              AND p.contract_years IS NOT NULL
              AND p.contract_years <= 1
              AND p.ktc_value > 2000
            RETURN p.name as name,
                   p.position as position,
                   p.current_team as team,
                   p.age as age,
                   p.contract_years as years_left,
                   p.contract_apy as current_apy,
                   p.ktc_value as ktc_value,
                   p.edge_signal as signal,
                   p.fantasy_points_season as fpts
            ORDER BY p.ktc_value DESC
            LIMIT 30
        """)
        return pd.DataFrame([dict(r) for r in result])


# =============================================================================
# VISUALIZATIONS
# =============================================================================

def create_efficiency_quadrant(df: pd.DataFrame):
    """Create value efficiency quadrant chart."""
    if df.empty:
        return None

    # Calculate points per million
    df = df.copy()
    df['ppm'] = df['fpts'] / (df['apy'] / 1_000_000)

    # Calculate median values for quadrant lines
    median_apy = df['apy'].median()
    median_fpts = df['fpts'].median()

    fig = px.scatter(
        df,
        x='apy',
        y='fpts',
        color='position',
        size='ktc_value',
        hover_data=['name', 'team', 'signal'],
        color_discrete_map=COLORS,
        labels={'apy': 'Annual Contract Value ($)', 'fpts': 'Fantasy Points (Season)'}
    )

    # Add quadrant lines
    fig.add_hline(y=median_fpts, line_dash="dash", line_color=COLORS['neutral'], opacity=0.5)
    fig.add_vline(x=median_apy, line_dash="dash", line_color=COLORS['neutral'], opacity=0.5)

    # Add quadrant labels
    fig.add_annotation(x=median_apy * 1.5, y=median_fpts * 1.3, text="FAIR VALUE",
                      showarrow=False, font=dict(size=12, color=COLORS['neutral']))
    fig.add_annotation(x=median_apy * 0.5, y=median_fpts * 1.3, text="HIGH EFFICIENCY",
                      showarrow=False, font=dict(size=12, color=COLORS['success']))
    fig.add_annotation(x=median_apy * 1.5, y=median_fpts * 0.5, text="LOW EFFICIENCY",
                      showarrow=False, font=dict(size=12, color=COLORS['danger']))
    fig.add_annotation(x=median_apy * 0.5, y=median_fpts * 0.5, text="DEVELOPING",
                      showarrow=False, font=dict(size=12, color=COLORS['warning']))

    fig.update_layout(
        title="Contract Efficiency Quadrant",
        height=500,
        xaxis=dict(tickformat='$,.0f'),
        showlegend=True
    )

    fig.update_traces(marker=dict(opacity=0.7, line=dict(width=1, color='white')))

    return fig


def create_position_contract_bars(df: pd.DataFrame):
    """Create bar chart of average APY by position."""
    if df.empty:
        return None

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=df['position'],
        y=df['avg_apy'],
        name='Average APY',
        marker_color=[COLORS.get(pos, COLORS['neutral']) for pos in df['position']],
        text=[format_money(v) for v in df['avg_apy']],
        textposition='outside'
    ))

    fig.update_layout(
        title="Average Contract APY by Position",
        xaxis_title="Position",
        yaxis_title="Average APY",
        height=400,
        yaxis=dict(tickformat='$,.0f'),
        showlegend=False
    )

    return fig


def create_contract_ktc_scatter(df: pd.DataFrame):
    """Create scatter of contract guaranteed vs KTC value."""
    if df.empty:
        return None

    fig = px.scatter(
        df,
        x='guaranteed',
        y='ktc_value',
        color='position',
        hover_data=['name', 'team', 'apy', 'signal'],
        color_discrete_map=COLORS,
        title="Guaranteed Money vs Dynasty Value",
        labels={'guaranteed': 'Guaranteed Money ($)', 'ktc_value': 'KTC Value'}
    )

    # Add trend line
    fig.update_layout(
        height=450,
        xaxis=dict(tickformat='$,.0f')
    )

    fig.update_traces(marker=dict(size=8, opacity=0.7))

    return fig


# =============================================================================
# MAIN PAGE
# =============================================================================

def main():
    st.title("💰 Contract Intelligence")
    st.markdown("NFL contract analysis and dynasty value implications")

    render_category_help('contract')

    # ==========================================================================
    # KEY INSIGHT
    # ==========================================================================
    st.info("""
    **Why Contracts Matter for Dynasty**: NFL teams invest millions in player evaluation.
    Contract guaranteed money is the #1 predictor of dynasty value in our model (100% importance).
    When teams commit guaranteed dollars, they're signaling belief in future production.
    """)

    st.divider()

    # ==========================================================================
    # TABS
    # ==========================================================================
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Contract Leaderboard",
        "⚖️ Efficiency Analysis",
        "🎯 Mismatches",
        "📅 Expiring Contracts"
    ])

    # --------------------------------------------------------------------------
    # TAB 1: CONTRACT LEADERBOARD
    # --------------------------------------------------------------------------
    with tab1:
        st.subheader("Contract Leaderboard")

        filter_cols = st.columns([1, 1, 1])

        with filter_cols[0]:
            position = st.selectbox("Position", ["All", "QB", "RB", "WR", "TE"], key="lb_pos")

        with filter_cols[1]:
            sort_options = {
                "Highest APY": "apy",
                "Most Guaranteed": "guaranteed",
                "Highest KTC Value": "ktc_value"
            }
            sort_by = st.selectbox("Sort By", list(sort_options.keys()))

        with filter_cols[2]:
            limit = st.selectbox("Show", [25, 50, 100], index=1)

        pos_filter = None if position == "All" else position
        df = get_contract_leaderboard(pos_filter, sort_options[sort_by], limit)

        if not df.empty:
            # Summary metrics
            metric_cols = st.columns(4)
            with metric_cols[0]:
                st.metric("Highest APY", format_money(df['apy'].max()))
            with metric_cols[1]:
                st.metric("Avg APY", format_money(df['apy'].mean()))
            with metric_cols[2]:
                st.metric("Total Guaranteed", format_money(df['guaranteed'].sum()))
            with metric_cols[3]:
                st.metric("Players", len(df))

            st.markdown("---")

            # Format display
            display_df = df[['name', 'position', 'team', 'age', 'apy', 'guaranteed', 'guaranteed_pct', 'years_remaining', 'ktc_value', 'signal']].copy()
            display_df.columns = ['Player', 'Pos', 'Team', 'Age', 'APY', 'Guaranteed', 'Guar %', 'Years', 'KTC', 'Signal']

            display_df['APY'] = display_df['APY'].apply(format_money)
            display_df['Guaranteed'] = display_df['Guaranteed'].apply(format_money)
            display_df['Guar %'] = display_df['Guar %'].apply(lambda x: f"{x:.0f}%" if pd.notna(x) else "N/A")
            display_df['KTC'] = display_df['KTC'].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "N/A")

            st.dataframe(display_df, use_container_width=True, height=500)

        else:
            st.info("No contract data available")

    # --------------------------------------------------------------------------
    # TAB 2: EFFICIENCY ANALYSIS
    # --------------------------------------------------------------------------
    with tab2:
        st.subheader("Contract Efficiency")
        st.markdown("**Question**: Who provides the best fantasy production per dollar spent?")

        eff_pos = st.selectbox("Position Filter", ["All", "QB", "RB", "WR", "TE"], key="eff_pos")

        pos_filter = None if eff_pos == "All" else eff_pos
        eff_df = get_value_efficiency_data(pos_filter)

        if not eff_df.empty:
            # Quadrant chart
            fig = create_efficiency_quadrant(eff_df)
            if fig:
                st.plotly_chart(fig, use_container_width=True)

            st.markdown("""
            **How to read this chart:**
            - **Top-Left (High Efficiency)**: High production, low cost - best value
            - **Top-Right (Fair Value)**: High production, high cost - paying for elite
            - **Bottom-Left (Developing)**: Low production, low cost - young/unproven
            - **Bottom-Right (Low Efficiency)**: Low production, high cost - overpaid
            """)

            # Position stats
            st.markdown("---")
            st.markdown("### Position Market Analysis")

            pos_stats = get_position_contract_stats()
            if not pos_stats.empty:
                pos_cols = st.columns(2)

                with pos_cols[0]:
                    fig = create_position_contract_bars(pos_stats)
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)

                with pos_cols[1]:
                    # Stats table
                    stats_display = pos_stats.copy()
                    stats_display['avg_apy'] = stats_display['avg_apy'].apply(format_money)
                    stats_display['max_apy'] = stats_display['max_apy'].apply(format_money)
                    stats_display['avg_guaranteed'] = stats_display['avg_guaranteed'].apply(format_money)
                    stats_display['avg_guaranteed_pct'] = stats_display['avg_guaranteed_pct'].apply(
                        lambda x: f"{x:.0f}%" if pd.notna(x) else "N/A"
                    )
                    stats_display['avg_ktc'] = stats_display['avg_ktc'].apply(
                        lambda x: f"{x:,.0f}" if pd.notna(x) else "N/A"
                    )

                    stats_display.columns = ['Position', 'Players', 'Avg APY', 'Max APY', 'Avg Guaranteed', 'Avg Guar %', 'Avg KTC']
                    st.dataframe(stats_display, hide_index=True, use_container_width=True)

        else:
            st.info("No efficiency data available")

    # --------------------------------------------------------------------------
    # TAB 3: MISMATCHES
    # --------------------------------------------------------------------------
    with tab3:
        st.subheader("Contract/Value Mismatches")
        st.markdown("Players where contract status creates dynasty opportunities")

        overpaid_df, underpaid_df = get_contract_value_mismatches()

        mismatch_cols = st.columns(2)

        with mismatch_cols[0]:
            st.markdown("### 🔴 Overpaid (Sell Candidates)")
            st.caption("High salary + SELL signal = potential value trap")

            if not overpaid_df.empty:
                for _, row in overpaid_df.head(10).iterrows():
                    with st.container():
                        st.markdown(f"**{row['name']}** ({row['position']}, {row.get('team', 'FA')})")
                        info_cols = st.columns(3)
                        with info_cols[0]:
                            st.caption(f"APY: {format_money(row['apy'])}")
                        with info_cols[1]:
                            st.caption(f"KTC: {row.get('ktc_value', 0):,.0f}")
                        with info_cols[2]:
                            gap = row.get('value_gap', 0) or 0
                            st.caption(f"Gap: {gap:+,.0f}")
                        st.divider()
            else:
                st.info("No overpaid players with sell signals found")

        with mismatch_cols[1]:
            st.markdown("### 🟢 Value Contracts (Buy Candidates)")
            st.caption("Lower salary + BUY signal = potential bargain")

            if not underpaid_df.empty:
                for _, row in underpaid_df.head(10).iterrows():
                    with st.container():
                        st.markdown(f"**{row['name']}** ({row['position']}, {row.get('team', 'FA')})")
                        info_cols = st.columns(3)
                        with info_cols[0]:
                            st.caption(f"APY: {format_money(row['apy'])}")
                        with info_cols[1]:
                            st.caption(f"KTC: {row.get('ktc_value', 0):,.0f}")
                        with info_cols[2]:
                            gap = row.get('value_gap', 0) or 0
                            st.caption(f"Gap: +{gap:,.0f}")
                        st.divider()
            else:
                st.info("No undervalued players with buy signals found")

        # Scatter plot
        st.markdown("---")
        st.markdown("### Contract vs Dynasty Value Correlation")

        full_df = get_contract_leaderboard(limit=200)
        if not full_df.empty:
            fig = create_contract_ktc_scatter(full_df)
            if fig:
                st.plotly_chart(fig, use_container_width=True)

            st.markdown("""
            **Key Insight**: There's strong correlation (r=0.54) between guaranteed money and dynasty value.
            NFL teams are effectively predicting dynasty value through their contract decisions.
            Look for outliers above the trend line (undervalued) and below (overvalued).
            """)

    # --------------------------------------------------------------------------
    # TAB 4: EXPIRING CONTRACTS
    # --------------------------------------------------------------------------
    with tab4:
        st.subheader("Expiring Contracts")
        st.markdown("Players entering contract years or free agency - watch for volatility")

        expiring_df = get_expiring_contracts()

        if not expiring_df.empty:
            st.warning(f"Found {len(expiring_df)} valuable players with contracts expiring soon")

            # Group by status
            fa = expiring_df[expiring_df['years_left'] == 0]
            contract_year = expiring_df[expiring_df['years_left'] == 1]

            exp_cols = st.columns(2)

            with exp_cols[0]:
                st.markdown("### 🆓 Pending Free Agents")
                if not fa.empty:
                    for _, row in fa.head(10).iterrows():
                        st.markdown(f"**{row['name']}** ({row['position']}, {row.get('team', 'FA')})")
                        st.caption(f"Age {row.get('age', '?')} | KTC: {row.get('ktc_value', 0):,.0f} | Signal: {row.get('signal', 'N/A')}")
                        st.divider()
                else:
                    st.info("No pending free agents in top value tier")

            with exp_cols[1]:
                st.markdown("### 📋 Contract Year Players")
                if not contract_year.empty:
                    for _, row in contract_year.head(10).iterrows():
                        st.markdown(f"**{row['name']}** ({row['position']}, {row.get('team', 'FA')})")
                        st.caption(f"Age {row.get('age', '?')} | KTC: {row.get('ktc_value', 0):,.0f} | Signal: {row.get('signal', 'N/A')}")
                        st.divider()
                else:
                    st.info("No contract year players in top value tier")

            st.markdown("---")
            st.markdown("### Dynasty Implications")
            st.markdown("""
            **Contract Year Watch**:
            - Players in contract years often see increased usage (motivated to earn new deals)
            - However, landing spot uncertainty creates value volatility
            - RBs especially risky - could end up in committees
            - WRs can benefit from landing with better QBs

            **Strategy Considerations**:
            - Buy low on FA uncertainty if you believe in the talent
            - Sell high on contract year production spikes that may not sustain
            - Monitor training camp for landing spot clarity
            """)

        else:
            st.info("No expiring contracts data available")


if __name__ == "__main__":
    main()
