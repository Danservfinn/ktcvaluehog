"""
Thoth Athletic Profiles
=======================
NFL Combine data analysis and athletic comparisons.
Find the athletic freaks who might be undervalued.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.components.tooltips import render_category_help, get_short_description

st.set_page_config(page_title="Athletic Profiles - Thoth", layout="wide")

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

# Athletic benchmarks by position
BENCHMARKS = {
    'QB': {'forty': 4.75, 'vertical': 32, 'broad_jump': 110, 'cone': 7.2, 'shuttle': 4.4},
    'RB': {'forty': 4.50, 'vertical': 36, 'broad_jump': 118, 'cone': 7.0, 'shuttle': 4.2},
    'WR': {'forty': 4.48, 'vertical': 36, 'broad_jump': 120, 'cone': 6.9, 'shuttle': 4.2},
    'TE': {'forty': 4.65, 'vertical': 34, 'broad_jump': 115, 'cone': 7.1, 'shuttle': 4.3}
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
def get_athletic_leaderboard(position: str = None, sort_by: str = 'forty', limit: int = 50):
    """Get athletic leaderboard."""
    driver = get_driver()

    position_filter = "AND p.position = $position" if position else ""

    # Handle sort direction (lower is better for times)
    sort_direction = "ASC" if sort_by in ['forty', 'cone', 'shuttle'] else "DESC"

    with driver.session() as session:
        result = session.run(f"""
            MATCH (p:Player)
            WHERE p.position IN ['QB', 'RB', 'WR', 'TE']
              AND p.combine_forty IS NOT NULL
              {position_filter}
            RETURN p.gsis_id as gsis_id,
                   p.name as name,
                   p.position as position,
                   p.current_team as team,
                   p.age as age,
                   p.ktc_value as ktc_value,
                   p.predicted_ktc_value as predicted_value,
                   p.edge_signal as signal,
                   p.combine_forty as forty,
                   p.combine_vertical as vertical,
                   p.combine_broad_jump as broad_jump,
                   p.combine_cone as cone,
                   p.combine_shuttle as shuttle,
                   p.combine_bench as bench,
                   p.height as height,
                   p.weight as weight,
                   p.draft_year as draft_year
            ORDER BY p.combine_{sort_by} {sort_direction}
            LIMIT $limit
        """, {'position': position, 'limit': limit})
        return pd.DataFrame([dict(r) for r in result])


@st.cache_data(ttl=3600)
def get_position_distributions(position: str):
    """Get athletic distributions for a position."""
    driver = get_driver()

    with driver.session() as session:
        result = session.run("""
            MATCH (p:Player)
            WHERE p.position = $position
              AND p.combine_forty IS NOT NULL
            RETURN p.combine_forty as forty,
                   p.combine_vertical as vertical,
                   p.combine_broad_jump as broad_jump,
                   p.combine_cone as cone,
                   p.combine_shuttle as shuttle,
                   p.combine_bench as bench
        """, {'position': position})
        return pd.DataFrame([dict(r) for r in result])


@st.cache_data(ttl=3600)
def get_athletic_value_scatter():
    """Get data for athletic score vs value analysis."""
    driver = get_driver()

    with driver.session() as session:
        result = session.run("""
            MATCH (p:Player)
            WHERE p.position IN ['QB', 'RB', 'WR', 'TE']
              AND p.combine_forty IS NOT NULL
              AND p.ktc_value > 0
            RETURN p.name as name,
                   p.position as position,
                   p.ktc_value as ktc_value,
                   p.predicted_ktc_value as predicted_value,
                   p.edge_signal as signal,
                   p.combine_forty as forty,
                   p.combine_vertical as vertical,
                   p.age as age,
                   p.years_exp as experience
            LIMIT 300
        """)
        return pd.DataFrame([dict(r) for r in result])


@st.cache_data(ttl=300)
def search_for_comparison(search_term: str):
    """Search for players to compare."""
    driver = get_driver()

    with driver.session() as session:
        result = session.run("""
            MATCH (p:Player)
            WHERE toLower(p.name) CONTAINS toLower($search)
              AND p.position IN ['QB', 'RB', 'WR', 'TE']
              AND p.combine_forty IS NOT NULL
            RETURN p.gsis_id as gsis_id,
                   p.name as name,
                   p.position as position,
                   p.current_team as team,
                   p.combine_forty as forty,
                   p.combine_vertical as vertical,
                   p.combine_broad_jump as broad_jump,
                   p.combine_cone as cone,
                   p.combine_shuttle as shuttle,
                   p.combine_bench as bench,
                   p.height as height,
                   p.weight as weight
            ORDER BY p.ktc_value DESC
            LIMIT 10
        """, {'search': search_term})
        return [dict(r) for r in result]


@st.cache_data(ttl=3600)
def get_undervalued_athletes(position: str = None):
    """Find athletic players who might be undervalued."""
    driver = get_driver()

    position_filter = "AND p.position = $position" if position else ""

    with driver.session() as session:
        result = session.run(f"""
            MATCH (p:Player)
            WHERE p.position IN ['QB', 'RB', 'WR', 'TE']
              AND p.combine_forty IS NOT NULL
              AND p.edge_signal IN ['BUY', 'STRONG_BUY']
              AND p.combine_forty < 4.55
              {position_filter}
            RETURN p.name as name,
                   p.position as position,
                   p.current_team as team,
                   p.age as age,
                   p.ktc_value as ktc_value,
                   p.predicted_ktc_value as predicted_value,
                   p.value_delta as value_gap,
                   p.edge_signal as signal,
                   p.combine_forty as forty,
                   p.combine_vertical as vertical,
                   p.avg_snap_pct as snap_pct
            ORDER BY p.value_delta DESC
            LIMIT 20
        """, {'position': position})
        return pd.DataFrame([dict(r) for r in result])


# =============================================================================
# VISUALIZATIONS
# =============================================================================

def create_comparison_spider(players: list, benchmarks: dict):
    """Create spider chart comparing multiple players."""
    categories = ['Speed', 'Explosion', 'Power', 'Agility', 'Quickness']

    def normalize_metric(value, metric, position):
        """Normalize to 0-100 scale based on position benchmarks."""
        if value is None:
            return 50

        bench = benchmarks.get(position, benchmarks['WR'])

        if metric == 'forty':
            # Lower is better, invert
            return max(0, min(100, (bench['forty'] - value + 0.3) / 0.6 * 100))
        elif metric == 'vertical':
            return max(0, min(100, (value - bench['vertical'] + 8) / 16 * 100))
        elif metric == 'broad_jump':
            return max(0, min(100, (value - bench['broad_jump'] + 15) / 30 * 100))
        elif metric == 'cone':
            return max(0, min(100, (bench['cone'] - value + 0.5) / 1.0 * 100))
        elif metric == 'shuttle':
            return max(0, min(100, (bench['shuttle'] - value + 0.3) / 0.6 * 100))
        return 50

    fig = go.Figure()

    colors = [COLORS['primary'], COLORS['success'], COLORS['warning'], COLORS['danger']]

    for i, player in enumerate(players):
        pos = player.get('position', 'WR')
        values = [
            normalize_metric(player.get('forty'), 'forty', pos),
            normalize_metric(player.get('vertical'), 'vertical', pos),
            normalize_metric(player.get('broad_jump'), 'broad_jump', pos),
            normalize_metric(player.get('cone'), 'cone', pos),
            normalize_metric(player.get('shuttle'), 'shuttle', pos)
        ]

        # Close the polygon
        categories_closed = categories + [categories[0]]
        values_closed = values + [values[0]]

        fig.add_trace(go.Scatterpolar(
            r=values_closed,
            theta=categories_closed,
            fill='toself',
            fillcolor=f"rgba({int(colors[i % len(colors)][1:3], 16)}, "
                      f"{int(colors[i % len(colors)][3:5], 16)}, "
                      f"{int(colors[i % len(colors)][5:7], 16)}, 0.2)",
            line=dict(color=colors[i % len(colors)], width=2),
            name=player.get('name', f'Player {i+1}')
        ))

    # Add position average reference
    fig.add_trace(go.Scatterpolar(
        r=[50, 50, 50, 50, 50, 50],
        theta=categories + [categories[0]],
        fill=None,
        line=dict(color=COLORS['neutral'], dash='dash'),
        name='Position Average'
    ))

    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        showlegend=True,
        title="Athletic Comparison",
        height=500
    )

    return fig


def create_distribution_box(df: pd.DataFrame, metric: str, title: str):
    """Create box plot for metric distribution."""
    if df.empty or metric not in df.columns:
        return None

    fig = px.box(
        df,
        y=metric,
        title=title,
        color_discrete_sequence=[COLORS['primary']]
    )

    fig.update_layout(
        height=300,
        showlegend=False,
        yaxis_title=title
    )

    return fig


def create_athletic_value_scatter(df: pd.DataFrame):
    """Create scatter plot of speed vs value."""
    if df.empty:
        return None

    # Calculate speed score (inverted 40 time)
    df = df.copy()
    df['speed_score'] = 100 - (df['forty'] - 4.2) / 0.8 * 100

    fig = px.scatter(
        df,
        x='speed_score',
        y='ktc_value',
        color='position',
        size='vertical',
        hover_data=['name', 'forty', 'signal'],
        color_discrete_map=COLORS,
        title="Speed vs Dynasty Value"
    )

    fig.update_layout(
        height=450,
        xaxis_title="Speed Score (higher = faster)",
        yaxis_title="KTC Value"
    )

    fig.update_traces(marker=dict(opacity=0.7))

    return fig


# =============================================================================
# MAIN PAGE
# =============================================================================

def main():
    st.title("🏃 Athletic Profiles")
    st.markdown("NFL Combine data analysis and player comparisons")

    render_category_help('athletic')

    # ==========================================================================
    # TABS
    # ==========================================================================
    tab1, tab2, tab3, tab4 = st.tabs([
        "🏆 Leaderboard",
        "⚖️ Compare Players",
        "📊 Position Analysis",
        "💎 Undervalued Athletes"
    ])

    # --------------------------------------------------------------------------
    # TAB 1: ATHLETIC LEADERBOARD
    # --------------------------------------------------------------------------
    with tab1:
        st.subheader("Athletic Leaderboard")

        filter_cols = st.columns([1, 1, 1, 1])

        with filter_cols[0]:
            position = st.selectbox("Position", ["All", "QB", "RB", "WR", "TE"], key="lb_pos")

        with filter_cols[1]:
            metric_map = {
                "40-Yard Dash": "forty",
                "Vertical Jump": "vertical",
                "Broad Jump": "broad_jump",
                "3-Cone Drill": "cone",
                "20-Yard Shuttle": "shuttle"
            }
            sort_metric = st.selectbox("Sort By", list(metric_map.keys()))

        with filter_cols[2]:
            limit = st.selectbox("Show", [25, 50, 100], index=1)

        pos_filter = None if position == "All" else position
        df = get_athletic_leaderboard(pos_filter, metric_map[sort_metric], limit)

        if not df.empty:
            # Add rank column
            df = df.reset_index(drop=True)
            df.index = df.index + 1
            df.index.name = 'Rank'

            # Format display columns
            display_cols = ['name', 'position', 'team', 'age', 'forty', 'vertical', 'broad_jump', 'cone', 'shuttle', 'ktc_value', 'signal']
            display_df = df[display_cols].copy()
            display_df.columns = ['Player', 'Pos', 'Team', 'Age', '40 Time', 'Vert', 'Broad', '3-Cone', 'Shuttle', 'KTC', 'Signal']

            # Format numeric columns
            for col in ['40 Time', '3-Cone', 'Shuttle']:
                display_df[col] = display_df[col].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "—")
            for col in ['Vert', 'Broad']:
                display_df[col] = display_df[col].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "—")
            display_df['KTC'] = display_df['KTC'].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "—")

            st.dataframe(
                display_df,
                use_container_width=True,
                height=500
            )

            # Summary stats
            st.markdown("---")
            stat_cols = st.columns(4)
            with stat_cols[0]:
                st.metric("Fastest 40", f"{df['forty'].min():.2f}s")
            with stat_cols[1]:
                st.metric("Highest Vert", f"{df['vertical'].max():.1f}\"")
            with stat_cols[2]:
                st.metric("Longest Broad", f"{df['broad_jump'].max():.0f}\"")
            with stat_cols[3]:
                st.metric("Best 3-Cone", f"{df['cone'].min():.2f}s")

        else:
            st.info("No combine data available for selected filters")

    # --------------------------------------------------------------------------
    # TAB 2: PLAYER COMPARISON
    # --------------------------------------------------------------------------
    with tab2:
        st.subheader("Compare Athletic Profiles")
        st.markdown("Search and select up to 4 players to compare")

        # Initialize comparison list in session state
        if 'comparison_players' not in st.session_state:
            st.session_state.comparison_players = []

        search_cols = st.columns([3, 1])
        with search_cols[0]:
            search = st.text_input("Search Player", placeholder="Enter player name...", key="comp_search")

        if search:
            results = search_for_comparison(search)
            if results:
                for player in results:
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.markdown(f"**{player['name']}** ({player['position']}, {player.get('team', 'FA')})")
                        st.caption(f"40: {player.get('forty', 'N/A')} | Vert: {player.get('vertical', 'N/A')} | Broad: {player.get('broad_jump', 'N/A')}")
                    with col2:
                        if len(st.session_state.comparison_players) < 4:
                            if st.button("Add", key=f"add_{player['gsis_id']}"):
                                if player not in st.session_state.comparison_players:
                                    st.session_state.comparison_players.append(player)
                                    st.rerun()

        # Show selected players
        st.markdown("---")
        st.markdown("### Selected Players")

        if st.session_state.comparison_players:
            for i, player in enumerate(st.session_state.comparison_players):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"**{i+1}. {player['name']}** ({player['position']})")
                with col2:
                    if st.button("Remove", key=f"remove_{i}"):
                        st.session_state.comparison_players.pop(i)
                        st.rerun()

            # Clear all button
            if st.button("Clear All"):
                st.session_state.comparison_players = []
                st.rerun()

            # Create comparison chart
            st.markdown("---")
            fig = create_comparison_spider(st.session_state.comparison_players, BENCHMARKS)
            st.plotly_chart(fig, use_container_width=True)

            # Comparison table
            st.markdown("### Raw Metrics")
            comp_data = []
            for player in st.session_state.comparison_players:
                comp_data.append({
                    'Player': player['name'],
                    'Position': player['position'],
                    '40 Time': f"{player.get('forty', 'N/A'):.2f}" if player.get('forty') else "N/A",
                    'Vertical': f"{player.get('vertical', 'N/A'):.1f}\"" if player.get('vertical') else "N/A",
                    'Broad Jump': f"{player.get('broad_jump', 'N/A'):.0f}\"" if player.get('broad_jump') else "N/A",
                    '3-Cone': f"{player.get('cone', 'N/A'):.2f}" if player.get('cone') else "N/A",
                    'Shuttle': f"{player.get('shuttle', 'N/A'):.2f}" if player.get('shuttle') else "N/A",
                    'Height': f"{int(player['height']//12)}'{int(player['height']%12)}\"" if player.get('height') else "N/A",
                    'Weight': f"{player.get('weight', 'N/A')} lbs" if player.get('weight') else "N/A"
                })
            st.dataframe(pd.DataFrame(comp_data), hide_index=True, use_container_width=True)

        else:
            st.info("Search for players above and click 'Add' to compare their athletic profiles")

    # --------------------------------------------------------------------------
    # TAB 3: POSITION ANALYSIS
    # --------------------------------------------------------------------------
    with tab3:
        st.subheader("Position Athletic Distributions")

        pos = st.selectbox("Select Position", ["RB", "WR", "TE", "QB"], key="dist_pos")

        dist_df = get_position_distributions(pos)

        if not dist_df.empty:
            st.markdown(f"### {pos} Athletic Benchmarks")

            bench = BENCHMARKS.get(pos, BENCHMARKS['WR'])
            bench_cols = st.columns(5)
            with bench_cols[0]:
                st.metric("Avg 40 Time", f"{bench['forty']:.2f}s")
            with bench_cols[1]:
                st.metric("Avg Vertical", f"{bench['vertical']}\"")
            with bench_cols[2]:
                st.metric("Avg Broad", f"{bench['broad_jump']}\"")
            with bench_cols[3]:
                st.metric("Avg 3-Cone", f"{bench['cone']:.2f}s")
            with bench_cols[4]:
                st.metric("Avg Shuttle", f"{bench['shuttle']:.2f}s")

            st.markdown("---")

            # Distribution plots
            dist_cols = st.columns(3)

            metrics = [
                ('forty', '40-Yard Dash (s)'),
                ('vertical', 'Vertical Jump (in)'),
                ('broad_jump', 'Broad Jump (in)')
            ]

            for i, (metric, title) in enumerate(metrics):
                with dist_cols[i]:
                    fig = create_distribution_box(dist_df, metric, title)
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)

            dist_cols2 = st.columns(3)
            metrics2 = [
                ('cone', '3-Cone Drill (s)'),
                ('shuttle', '20-Yard Shuttle (s)'),
                ('bench', 'Bench Press (reps)')
            ]

            for i, (metric, title) in enumerate(metrics2):
                with dist_cols2[i]:
                    fig = create_distribution_box(dist_df, metric, title)
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)

            # Summary stats
            st.markdown("---")
            st.markdown("### Distribution Statistics")
            stats_df = dist_df.describe().T
            stats_df = stats_df[['mean', 'std', 'min', '25%', '50%', '75%', 'max']]
            stats_df.columns = ['Mean', 'Std Dev', 'Min', '25th %ile', 'Median', '75th %ile', 'Max']
            st.dataframe(stats_df.round(2), use_container_width=True)

        else:
            st.info(f"No combine data available for {pos}")

    # --------------------------------------------------------------------------
    # TAB 4: UNDERVALUED ATHLETES
    # --------------------------------------------------------------------------
    with tab4:
        st.subheader("Undervalued Athletes")
        st.markdown("Fast players with BUY signals - athletic upside the market may be missing")

        pos_filter = st.selectbox("Position", ["All", "QB", "RB", "WR", "TE"], key="under_pos")

        pos = None if pos_filter == "All" else pos_filter
        undervalued = get_undervalued_athletes(pos)

        if not undervalued.empty:
            st.success(f"Found {len(undervalued)} athletic players with BUY signals")

            for _, row in undervalued.iterrows():
                with st.container():
                    cols = st.columns([2, 1, 1, 1, 1])

                    with cols[0]:
                        st.markdown(f"**{row['name']}**")
                        st.caption(f"{row['position']} | {row.get('team', 'FA')} | Age {row.get('age', '?')}")

                    with cols[1]:
                        st.metric("40 Time", f"{row['forty']:.2f}s")

                    with cols[2]:
                        vert = row.get('vertical')
                        st.metric("Vertical", f"{vert:.1f}\"" if vert else "N/A")

                    with cols[3]:
                        ktc = row.get('ktc_value', 0)
                        st.metric("KTC Value", f"{ktc:,}")

                    with cols[4]:
                        gap = row.get('value_gap', 0)
                        st.metric("Value Gap", f"+{gap:,.0f}")

                    st.divider()

            # Value vs Speed scatter
            st.markdown("---")
            st.markdown("### Speed vs Value Analysis")
            scatter_df = get_athletic_value_scatter()
            if not scatter_df.empty:
                fig = create_athletic_value_scatter(scatter_df)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)

                st.markdown("""
                **What to look for:**
                - High speed score (right side) + Low KTC (bottom) = potential value
                - Young players with elite speed often haven't realized their upside
                - Speed is most predictive for WRs and RBs
                """)

        else:
            st.info("No undervalued athletic players found with current filters")
            st.markdown("""
            This could mean:
            - The market is efficiently pricing athletic upside
            - Try a different position filter
            - Or the opportunity window has closed

            Keep checking back as values change daily!
            """)


if __name__ == "__main__":
    main()
