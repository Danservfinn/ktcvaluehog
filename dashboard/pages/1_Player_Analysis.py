"""
Thoth Player Intelligence
=========================
Deep dive into individual player valuations, athletic profiles,
situational context, and historical trends.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.components.tooltips import (
    get_short_description, get_signal_color, get_signal_emoji,
    render_feature_tooltip, render_category_help, FEATURE_TOOLTIPS
)

st.set_page_config(page_title="Player Intelligence - Thoth", layout="wide")

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

@st.cache_data(ttl=300)
def search_players(search_term: str, position: str = None):
    """Search for players by name."""
    driver = get_driver()
    position_filter = "AND p.position = $position" if position else ""

    with driver.session() as session:
        result = session.run(f"""
            MATCH (p:Player)
            WHERE toLower(p.name) CONTAINS toLower($search)
              AND p.position IN ['QB', 'RB', 'WR', 'TE']
              {position_filter}
            RETURN p.gsis_id as gsis_id,
                   p.name as name,
                   p.position as position,
                   p.ktc_value as ktc_value,
                   p.predicted_ktc_value as predicted_value,
                   p.edge_signal as signal,
                   p.age as age,
                   p.current_team as team
            ORDER BY p.ktc_value DESC
            LIMIT 20
        """, {'search': search_term, 'position': position})
        return [dict(r) for r in result]


@st.cache_data(ttl=300)
def get_player_details(gsis_id: str):
    """Get comprehensive player information with all enriched data."""
    driver = get_driver()

    with driver.session() as session:
        result = session.run("""
            MATCH (p:Player {gsis_id: $gsis_id})

            // Get career stage
            OPTIONAL MATCH (p)-[:AT_CAREER_STAGE]->(cs:CareerStage)

            // Get chemistry
            OPTIONAL MATCH (p)-[chem:CHEMISTRY_WITH]->(qb:Player)

            // Get teammates
            OPTIONAL MATCH (p)-[:PLAYS_FOR]->(t:Team)<-[:PLAYS_FOR]-(teammate:Player)
            WHERE teammate <> p AND teammate.position IN ['QB', 'RB', 'WR', 'TE']

            // Get competitors
            OPTIONAL MATCH (p)-[:COMPETES_WITH]-(competitor:Player)

            WITH p, cs, chem, qb, collect(DISTINCT teammate.name)[0..5] as teammates,
                 collect(DISTINCT competitor.name)[0..5] as competitors

            RETURN
                // Basic Info
                p.gsis_id as gsis_id,
                p.name as name,
                p.position as position,
                p.age as age,
                p.current_team as team,
                p.college as college,
                p.years_exp as experience,
                p.height as height,
                p.weight as weight,

                // KTC & Model Values
                p.ktc_value as ktc_value,
                p.predicted_ktc_value as predicted_value,
                p.value_delta as value_delta,
                p.value_delta_pct as value_delta_pct,
                p.edge_signal as signal,
                p.dynasty_edge_score as edge_score,
                p.edge_delta as edge_delta,

                // Athletic Profile
                p.combine_forty as forty,
                p.combine_vertical as vertical,
                p.combine_broad_jump as broad_jump,
                p.combine_bench as bench,
                p.combine_cone as cone,
                p.combine_shuttle as shuttle,

                // Draft Capital
                p.draft_round as draft_round,
                p.draft_pick as draft_pick,
                p.draft_year as draft_year,
                p.draft_value as draft_value,
                p.draft_age as draft_age,

                // Contract
                p.contract_apy as contract_apy,
                p.contract_value as contract_value,
                p.contract_guaranteed as contract_guaranteed,
                p.contract_guaranteed_pct as guaranteed_pct,
                p.contract_cap_pct as cap_pct,
                p.contract_years as contract_years,

                // Playing Time
                p.total_snaps as total_snaps,
                p.avg_snap_pct as snap_pct,
                p.games_played as games_played,
                p.snap_trend as snap_trend,

                // Injury
                p.injury_reports as injury_reports,
                p.injuries_per_season as injuries_per_season,
                p.injury_risk_score as injury_risk,

                // Performance
                p.fantasy_points_season as fantasy_points,
                p.targets as targets,
                p.receptions as receptions,
                p.receiving_yards as receiving_yards,
                p.receiving_tds as receiving_tds,
                p.carries as carries,
                p.rushing_yards as rushing_yards,
                p.rushing_tds as rushing_tds,

                // QBR (QB only)
                p.qbr as qbr,
                p.qbr_pts_added as qbr_pts_added,

                // Graph Metrics
                p.pagerank as pagerank,
                p.influence_score as influence,
                cs.production_tier as production_tier,
                cs.age_bucket as age_bucket,
                chem.cqi_score as chemistry_score,
                qb.name as qb_name,
                teammates,
                competitors
        """, {'gsis_id': gsis_id})
        record = result.single()
        return dict(record) if record else None


@st.cache_data(ttl=300)
def get_player_snapshots(gsis_id: str):
    """Get player value history."""
    driver = get_driver()

    with driver.session() as session:
        result = session.run("""
            MATCH (p:Player {gsis_id: $gsis_id})-[:HAD_SNAPSHOT]->(s:Snapshot)
            RETURN s.date as date,
                   s.ktc_value as ktc_value,
                   s.ktc_delta as ktc_delta,
                   s.ktc_delta_pct as ktc_delta_pct
            ORDER BY s.date DESC
            LIMIT 30
        """, {'gsis_id': gsis_id})
        return pd.DataFrame([dict(r) for r in result])


@st.cache_data(ttl=3600)
def get_position_percentiles(position: str):
    """Get percentile benchmarks for a position."""
    driver = get_driver()

    with driver.session() as session:
        result = session.run("""
            MATCH (p:Player)
            WHERE p.position = $position
              AND p.combine_forty IS NOT NULL
            RETURN
                percentileCont(p.combine_forty, 0.25) as forty_p25,
                percentileCont(p.combine_forty, 0.50) as forty_p50,
                percentileCont(p.combine_forty, 0.75) as forty_p75,
                percentileCont(p.combine_vertical, 0.25) as vertical_p25,
                percentileCont(p.combine_vertical, 0.50) as vertical_p50,
                percentileCont(p.combine_vertical, 0.75) as vertical_p75,
                percentileCont(p.combine_broad_jump, 0.25) as broad_p25,
                percentileCont(p.combine_broad_jump, 0.50) as broad_p50,
                percentileCont(p.combine_broad_jump, 0.75) as broad_p75,
                percentileCont(p.combine_cone, 0.25) as cone_p25,
                percentileCont(p.combine_cone, 0.50) as cone_p50,
                percentileCont(p.combine_cone, 0.75) as cone_p75,
                percentileCont(p.combine_shuttle, 0.25) as shuttle_p25,
                percentileCont(p.combine_shuttle, 0.50) as shuttle_p50,
                percentileCont(p.combine_shuttle, 0.75) as shuttle_p75
        """, {'position': position})
        record = result.single()
        return dict(record) if record else {}


# =============================================================================
# VISUALIZATION HELPERS
# =============================================================================

def create_value_waterfall(player: dict):
    """Create waterfall chart showing factors contributing to value."""
    # Calculate contributions (simplified - in production would use SHAP values)
    base_value = 3000  # Average player value

    factors = []
    values = []

    # Age factor
    age = player.get('age', 25)
    age_impact = (25 - age) * 150 if age else 0
    factors.append('Age')
    values.append(age_impact)

    # Contract factor
    contract = player.get('contract_guaranteed', 0)
    if contract:
        contract_impact = min(contract / 100000, 2000)  # Cap contribution
        factors.append('Contract')
        values.append(contract_impact)

    # Draft capital
    draft_value = player.get('draft_value', 0)
    if draft_value:
        draft_impact = draft_value / 2
        factors.append('Draft Capital')
        values.append(draft_impact)

    # Snap share
    snap_pct = player.get('snap_pct', 0)
    if snap_pct:
        snap_impact = (snap_pct - 50) * 20
        factors.append('Snap Share')
        values.append(snap_impact)

    # Production
    fpts = player.get('fantasy_points', 0)
    if fpts:
        prod_impact = (fpts - 100) * 5
        factors.append('Production')
        values.append(prod_impact)

    # Calculate cumulative for waterfall
    measures = ['relative'] * len(factors)

    fig = go.Figure(go.Waterfall(
        name="Value Factors",
        orientation="v",
        measure=measures + ['total'],
        x=factors + ['Total'],
        y=values + [sum(values) + base_value],
        connector={"line": {"color": "rgb(63, 63, 63)"}},
        increasing={"marker": {"color": COLORS['success']}},
        decreasing={"marker": {"color": COLORS['danger']}},
        totals={"marker": {"color": COLORS['primary']}}
    ))

    fig.update_layout(
        title="Value Factor Breakdown",
        showlegend=False,
        height=400
    )

    return fig


def create_athletic_spider(player: dict, percentiles: dict):
    """Create spider/radar chart for athletic profile."""
    categories = ['Speed', 'Explosion', 'Power', 'Agility', 'Quickness']

    # Normalize values to 0-100 scale (invert times)
    def normalize_time(val, p25, p75):
        """Lower is better for times."""
        if val is None:
            return 50
        return max(0, min(100, 100 - ((val - p25) / (p75 - p25) * 50 + 25)))

    def normalize_distance(val, p25, p75):
        """Higher is better for jumps."""
        if val is None:
            return 50
        return max(0, min(100, (val - p25) / (p75 - p25) * 50 + 25))

    player_values = [
        normalize_time(player.get('forty'), percentiles.get('forty_p25', 4.4), percentiles.get('forty_p75', 4.7)),
        normalize_distance(player.get('vertical'), percentiles.get('vertical_p25', 30), percentiles.get('vertical_p75', 38)),
        normalize_distance(player.get('broad_jump'), percentiles.get('broad_p25', 110), percentiles.get('broad_p75', 125)),
        normalize_time(player.get('cone'), percentiles.get('cone_p25', 6.8), percentiles.get('cone_p75', 7.3)),
        normalize_time(player.get('shuttle'), percentiles.get('shuttle_p25', 4.1), percentiles.get('shuttle_p75', 4.4))
    ]

    # Add first point again to close the radar
    categories_closed = categories + [categories[0]]
    player_values_closed = player_values + [player_values[0]]

    fig = go.Figure()

    # Add average reference line
    fig.add_trace(go.Scatterpolar(
        r=[50, 50, 50, 50, 50, 50],
        theta=categories_closed,
        fill=None,
        line=dict(color=COLORS['neutral'], dash='dash'),
        name='Position Average'
    ))

    # Add player values
    fig.add_trace(go.Scatterpolar(
        r=player_values_closed,
        theta=categories_closed,
        fill='toself',
        fillcolor=f"rgba(30, 58, 95, 0.3)",
        line=dict(color=COLORS['primary'], width=2),
        name=player.get('name', 'Player')
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100])
        ),
        showlegend=True,
        title="Athletic Profile",
        height=400
    )

    return fig


def create_value_timeline(snapshots: pd.DataFrame, predicted: float = None):
    """Create value timeline with prediction overlay."""
    if snapshots.empty:
        return None

    fig = go.Figure()

    # Historical values
    fig.add_trace(go.Scatter(
        x=snapshots['date'],
        y=snapshots['ktc_value'],
        mode='lines+markers',
        name='KTC Value',
        line=dict(color=COLORS['primary'], width=2),
        marker=dict(size=6)
    ))

    # Add predicted value line if available
    if predicted:
        fig.add_hline(
            y=predicted,
            line_dash="dash",
            line_color=COLORS['success'],
            annotation_text=f"Model Prediction: {predicted:,.0f}",
            annotation_position="top right"
        )

    fig.update_layout(
        title="Value Timeline",
        xaxis_title="Date",
        yaxis_title="KTC Value",
        height=350,
        hovermode='x unified'
    )

    return fig


def render_signal_badge(signal: str):
    """Render a colored signal badge."""
    color = get_signal_color(signal)
    emoji = get_signal_emoji(signal)

    badge_styles = {
        'STRONG_BUY': ('background-color: #D1FAE5; color: #065F46;', '🟢🟢'),
        'BUY': ('background-color: #ECFDF5; color: #047857;', '🟢'),
        'HOLD': ('background-color: #F3F4F6; color: #374151;', '🟡'),
        'SELL': ('background-color: #FEF3C7; color: #92400E;', '🟠'),
        'STRONG_SELL': ('background-color: #FEE2E2; color: #991B1B;', '🔴')
    }

    style, icon = badge_styles.get(signal, ('', ''))
    st.markdown(
        f'<span style="padding: 4px 12px; border-radius: 9999px; font-weight: 600; {style}">'
        f'{icon} {signal.replace("_", " ")}</span>',
        unsafe_allow_html=True
    )


def format_money(value):
    """Format money values."""
    if value is None:
        return "N/A"
    if value >= 1_000_000:
        return f"${value/1_000_000:.1f}M"
    if value >= 1_000:
        return f"${value/1_000:.0f}K"
    return f"${value:.0f}"


# =============================================================================
# MAIN PAGE
# =============================================================================

def main():
    st.title("🔮 Player Intelligence")
    st.markdown("Deep analysis powered by Thoth's ML engine")

    # Search section
    col1, col2 = st.columns([3, 1])
    with col1:
        search_term = st.text_input(
            "Search Player",
            placeholder="Enter player name...",
            help="Search by player name to view comprehensive analysis"
        )
    with col2:
        position = st.selectbox("Position", ["All", "QB", "RB", "WR", "TE"])

    if search_term:
        pos_filter = None if position == "All" else position
        players = search_players(search_term, pos_filter)

        if players:
            # Create selection with signal preview
            player_options = {}
            for p in players:
                signal = p.get('signal', 'HOLD') or 'HOLD'
                emoji = get_signal_emoji(signal)
                label = f"{p['name']} ({p['position']}, {p['team'] or 'FA'}) {emoji}"
                player_options[label] = p['gsis_id']

            selected = st.selectbox("Select a player", list(player_options.keys()))

            if selected:
                gsis_id = player_options[selected]
                player = get_player_details(gsis_id)

                if player:
                    st.divider()

                    # ==========================================================
                    # PLAYER HEADER
                    # ==========================================================
                    header_cols = st.columns([2.5, 1, 1, 1])

                    with header_cols[0]:
                        st.header(f"{player['name']}")
                        team = player.get('team', 'FA') or 'FA'
                        st.markdown(f"**{player['position']}** | {team} | Age {player.get('age', '?')}")
                        if player.get('college'):
                            st.caption(f"{player['college']} | {player.get('experience', 0)} years NFL exp")

                    with header_cols[1]:
                        ktc = player.get('ktc_value', 0) or 0
                        st.metric("KTC Value", f"{ktc:,}")

                    with header_cols[2]:
                        predicted = player.get('predicted_value')
                        if predicted:
                            delta = player.get('value_delta', 0) or 0
                            st.metric("Model Value", f"{predicted:,.0f}", delta=f"{delta:+,.0f}")
                        else:
                            st.metric("Model Value", "N/A")

                    with header_cols[3]:
                        signal = player.get('signal', 'HOLD') or 'HOLD'
                        st.markdown("**Signal**")
                        render_signal_badge(signal)
                        if player.get('value_delta_pct'):
                            st.caption(f"Gap: {player['value_delta_pct']:+.1f}%")

                    st.divider()

                    # ==========================================================
                    # FOUR ANALYSIS TABS
                    # ==========================================================
                    tab1, tab2, tab3, tab4 = st.tabs([
                        "📊 Valuation",
                        "🏃 Athletic Profile",
                        "📈 Situation",
                        "📜 History"
                    ])

                    # ----------------------------------------------------------
                    # TAB 1: VALUATION
                    # ----------------------------------------------------------
                    with tab1:
                        st.subheader("Value Analysis")
                        render_category_help('output')

                        val_cols = st.columns([1.5, 1])

                        with val_cols[0]:
                            # Waterfall chart
                            fig = create_value_waterfall(player)
                            st.plotly_chart(fig, use_container_width=True)

                        with val_cols[1]:
                            st.markdown("#### Key Value Drivers")

                            # Value gap analysis
                            predicted = player.get('predicted_value')
                            ktc = player.get('ktc_value', 0) or 0

                            if predicted and ktc:
                                gap = predicted - ktc
                                gap_pct = (gap / ktc * 100) if ktc else 0

                                st.metric(
                                    "Value Gap",
                                    f"{gap:+,.0f}",
                                    delta=f"{gap_pct:+.1f}%",
                                    delta_color="normal" if gap >= 0 else "inverse"
                                )

                                if gap > 500:
                                    st.success("Model sees upside vs market price")
                                elif gap < -500:
                                    st.warning("Model sees risk vs market price")
                                else:
                                    st.info("Fairly valued by model")

                            st.markdown("---")
                            st.markdown("#### Production")
                            fpts = player.get('fantasy_points', 0) or 0
                            games = player.get('games_played', 0) or 0
                            ppg = fpts / games if games > 0 else 0

                            st.metric("Fantasy Points", f"{fpts:.1f}")
                            st.metric("Points/Game", f"{ppg:.1f}")

                            # Position rank estimate
                            if ppg > 20:
                                st.caption("Elite Production")
                            elif ppg > 12:
                                st.caption("Starter Level")
                            elif ppg > 6:
                                st.caption("Flex/Depth")
                            else:
                                st.caption("Lottery Ticket")

                    # ----------------------------------------------------------
                    # TAB 2: ATHLETIC PROFILE
                    # ----------------------------------------------------------
                    with tab2:
                        st.subheader("Athletic Profile")
                        render_category_help('athletic')

                        # Check if combine data exists
                        has_combine = any([
                            player.get('forty'), player.get('vertical'),
                            player.get('broad_jump'), player.get('cone')
                        ])

                        if has_combine:
                            ath_cols = st.columns([1.5, 1])

                            with ath_cols[0]:
                                # Spider chart
                                percentiles = get_position_percentiles(player['position'])
                                fig = create_athletic_spider(player, percentiles)
                                st.plotly_chart(fig, use_container_width=True)

                            with ath_cols[1]:
                                st.markdown("#### Combine Results")

                                metrics_data = [
                                    ("40-Yard", player.get('forty'), "s", True),
                                    ("Vertical", player.get('vertical'), '"', False),
                                    ("Broad Jump", player.get('broad_jump'), '"', False),
                                    ("3-Cone", player.get('cone'), "s", True),
                                    ("Shuttle", player.get('shuttle'), "s", True),
                                    ("Bench", player.get('bench'), " reps", False)
                                ]

                                for label, value, unit, lower_better in metrics_data:
                                    if value:
                                        st.metric(label, f"{value:.2f}{unit}")

                                # Physical
                                st.markdown("---")
                                st.markdown("#### Physical")
                                if player.get('height'):
                                    feet = int(player['height'] // 12)
                                    inches = int(player['height'] % 12)
                                    st.metric("Height", f"{feet}'{inches}\"")
                                if player.get('weight'):
                                    st.metric("Weight", f"{player['weight']} lbs")
                        else:
                            st.info("No combine data available for this player")
                            st.markdown("""
                            Possible reasons:
                            - Player did not participate in NFL Combine
                            - Pre-Combine era player
                            - Data not yet loaded
                            """)

                    # ----------------------------------------------------------
                    # TAB 3: SITUATION
                    # ----------------------------------------------------------
                    with tab3:
                        st.subheader("Situational Context")

                        sit_cols = st.columns(3)

                        # Column 1: Playing Time
                        with sit_cols[0]:
                            st.markdown("#### Playing Time")
                            render_category_help('playing_time')

                            snap_pct = player.get('snap_pct')
                            snap_trend = player.get('snap_trend')
                            games = player.get('games_played')
                            snaps = player.get('total_snaps')

                            if snap_pct:
                                st.metric("Snap %", f"{snap_pct:.1f}%")
                                if snap_pct >= 80:
                                    st.caption("Workhorse role")
                                elif snap_pct >= 60:
                                    st.caption("Clear starter")
                                elif snap_pct >= 40:
                                    st.caption("Committee/Rotational")
                                else:
                                    st.caption("Backup/Situational")

                            if snap_trend is not None:
                                trend_delta = f"{snap_trend:+.1f}%" if snap_trend else "0%"
                                color = "normal" if snap_trend and snap_trend > 0 else "inverse"
                                st.metric("Snap Trend", trend_delta, delta_color=color)
                                if snap_trend and snap_trend > 5:
                                    st.success("Role expanding")
                                elif snap_trend and snap_trend < -5:
                                    st.warning("Role declining")

                            if games:
                                st.metric("Games", games)
                            if snaps:
                                st.metric("Total Snaps", f"{snaps:,}")

                        # Column 2: Contract
                        with sit_cols[1]:
                            st.markdown("#### Contract")
                            render_category_help('contract')

                            apy = player.get('contract_apy')
                            guaranteed = player.get('contract_guaranteed')
                            years = player.get('contract_years')
                            cap_pct = player.get('cap_pct')

                            if apy:
                                st.metric("APY", format_money(apy))
                            if guaranteed:
                                st.metric("Guaranteed", format_money(guaranteed))
                                guar_pct = player.get('guaranteed_pct')
                                if guar_pct:
                                    st.caption(f"{guar_pct:.0f}% guaranteed")
                            if years:
                                st.metric("Years Left", years)
                            if cap_pct:
                                st.metric("Cap %", f"{cap_pct:.1f}%")

                            if not any([apy, guaranteed, years]):
                                st.info("No contract data available")

                        # Column 3: Risk Factors
                        with sit_cols[2]:
                            st.markdown("#### Risk Assessment")
                            render_category_help('injury')

                            injury_risk = player.get('injury_risk')
                            injuries_ps = player.get('injuries_per_season')

                            if injury_risk is not None:
                                st.metric("Injury Risk", f"{injury_risk:.0f}/100")
                                if injury_risk > 60:
                                    st.error("High injury risk")
                                elif injury_risk > 40:
                                    st.warning("Elevated risk")
                                elif injury_risk > 20:
                                    st.info("Moderate risk")
                                else:
                                    st.success("Low injury history")

                            if injuries_ps:
                                st.metric("Injuries/Season", f"{injuries_ps:.1f}")

                            # Age risk
                            age = player.get('age')
                            position = player.get('position')
                            if age and position:
                                st.markdown("---")
                                st.markdown("**Age Curve**")
                                endpoints = {'QB': 40, 'RB': 29, 'WR': 32, 'TE': 34}
                                remaining = endpoints.get(position, 32) - age
                                st.metric("Years Remaining", max(0, remaining))

                                if position == 'RB' and age >= 26:
                                    st.warning("Past RB prime window")
                                elif age >= 30:
                                    st.warning("Aging asset")

                    # ----------------------------------------------------------
                    # TAB 4: HISTORY
                    # ----------------------------------------------------------
                    with tab4:
                        st.subheader("Value History")

                        snapshots = get_player_snapshots(gsis_id)

                        if not snapshots.empty:
                            # Timeline chart
                            fig = create_value_timeline(
                                snapshots,
                                player.get('predicted_value')
                            )
                            if fig:
                                st.plotly_chart(fig, use_container_width=True)

                            # Stats table
                            hist_cols = st.columns([1, 1])

                            with hist_cols[0]:
                                st.markdown("#### Value Changes")
                                recent = snapshots.head(10).copy()
                                recent['date'] = pd.to_datetime(recent['date']).dt.strftime('%Y-%m-%d')
                                recent['ktc_value'] = recent['ktc_value'].apply(lambda x: f"{x:,.0f}" if x else "N/A")
                                recent['ktc_delta'] = recent['ktc_delta'].apply(
                                    lambda x: f"{x:+,.0f}" if x else "0"
                                )
                                st.dataframe(
                                    recent[['date', 'ktc_value', 'ktc_delta']].rename(columns={
                                        'date': 'Date',
                                        'ktc_value': 'Value',
                                        'ktc_delta': 'Change'
                                    }),
                                    hide_index=True,
                                    use_container_width=True
                                )

                            with hist_cols[1]:
                                st.markdown("#### Summary Stats")
                                if len(snapshots) > 1:
                                    high = snapshots['ktc_value'].max()
                                    low = snapshots['ktc_value'].min()
                                    current = snapshots['ktc_value'].iloc[0]

                                    st.metric("30-Day High", f"{high:,.0f}")
                                    st.metric("30-Day Low", f"{low:,.0f}")
                                    st.metric("Volatility", f"{((high-low)/current*100):.1f}%" if current else "N/A")

                                    # Trend
                                    if len(snapshots) >= 7:
                                        week_ago = snapshots['ktc_value'].iloc[6] if len(snapshots) > 6 else snapshots['ktc_value'].iloc[-1]
                                        week_delta = current - week_ago
                                        st.metric("7-Day Change", f"{week_delta:+,.0f}")
                        else:
                            st.info("No historical snapshots available yet.")
                            st.markdown("""
                            Historical tracking begins when the daily refresh job runs.

                            **Current Data Available:**
                            - Real-time KTC value
                            - Model predictions
                            - All enriched features
                            """)

                        # Connections section
                        st.divider()
                        st.markdown("#### Team Context")

                        conn_cols = st.columns(2)
                        with conn_cols[0]:
                            st.markdown("**Teammates**")
                            teammates = player.get('teammates', [])
                            if teammates:
                                for tm in teammates:
                                    st.markdown(f"• {tm}")
                            else:
                                st.caption("No teammate data")

                        with conn_cols[1]:
                            st.markdown("**Position Competitors**")
                            competitors = player.get('competitors', [])
                            if competitors:
                                for comp in competitors:
                                    st.markdown(f"• {comp}")
                            else:
                                st.caption("No competitor data")

                            # QB Chemistry for skill players
                            if player.get('chemistry_score') and player.get('qb_name'):
                                st.markdown("---")
                                st.markdown("**QB Chemistry**")
                                st.metric(
                                    player['qb_name'],
                                    f"{player['chemistry_score']:.1f} CQI"
                                )

        else:
            st.info("No players found matching your search.")

    else:
        # Empty state
        st.info("Enter a player name to begin analysis")

        st.markdown("""
        ### What you'll find:

        - **Valuation Tab**: Model predictions, value gaps, and factor breakdowns
        - **Athletic Tab**: Combine metrics, spider charts, physical profile
        - **Situation Tab**: Snap share, contract details, injury risk
        - **History Tab**: Value trends, volatility, team context

        *Powered by Thoth's ML model trained on 40+ features*
        """)


if __name__ == "__main__":
    main()
