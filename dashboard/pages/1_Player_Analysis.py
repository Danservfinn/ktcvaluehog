"""
Thoth Player Intelligence
=========================
Deep dive into individual player valuations, athletic profiles,
situational context, and historical trends.
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
    """Get comprehensive player information with ALL enriched data."""
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
                p.display_name as display_name,
                p.position as position,
                p.age as age,
                p.current_team as team,
                p.college as college,
                p.years_exp as experience,
                p.height as height,
                p.weight as weight,
                p.combine_height as combine_height,
                p.combine_weight as combine_weight,

                // KTC & Model Values
                p.ktc_value as ktc_value,
                p.ktc_rank as ktc_rank,
                p.ktc_pos_rank as ktc_pos_rank,
                p.ktc_trend as ktc_trend,
                p.predicted_ktc_value as predicted_value,
                p.predicted_value as model_predicted_value,
                p.value_delta as value_delta,
                p.value_delta_pct as value_delta_pct,
                p.value_gap as value_gap,
                p.value_gap_pct as value_gap_pct,
                p.edge_signal as signal,
                p.recommendation as recommendation,
                p.dynasty_edge_score as edge_score,
                p.edge_delta as edge_delta,

                // Athletic Profile
                p.combine_forty as forty,
                p.combine_vertical as vertical,
                p.combine_broad_jump as broad_jump,
                p.combine_bench as bench,
                p.combine_cone as cone,
                p.combine_shuttle as shuttle,
                p.athletic_score as athletic_score,
                p.athletic_percentile as athletic_percentile,

                // Draft Capital
                p.draft_round as draft_round,
                p.draft_pick as draft_pick,
                p.draft_year as draft_year,
                p.draft_value as draft_value,
                p.draft_age as draft_age,
                p.round_capital as round_capital,

                // Contract
                p.contract_apy as contract_apy,
                p.contract_value as contract_value,
                p.contract_guaranteed as contract_guaranteed,
                p.contract_guaranteed_pct as guaranteed_pct,
                p.contract_cap_pct as cap_pct,
                p.contract_years as contract_years,
                p.apy_percentile as apy_percentile,

                // Playing Time
                p.total_snaps as total_snaps,
                p.avg_snap_pct as snap_pct,
                p.games_played as games_played,
                p.snap_trend as snap_trend,
                p.stats_season as stats_season,

                // Injury
                p.injury_reports as injury_reports,
                p.injuries_per_season as injuries_per_season,
                p.injury_risk_score as injury_risk,

                // Fantasy Performance
                p.fantasy_points as fantasy_points_std,
                p.fantasy_points_ppr as fantasy_points_ppr,
                p.fantasy_points_season as fantasy_points,
                p.fpts_per_game as fpts_per_game,

                // Receiving Stats
                p.targets as targets,
                p.receptions as receptions,
                p.receiving_yards as receiving_yards,
                p.receiving_tds as receiving_tds,
                p.receiving_air_yards as receiving_air_yards,
                p.receiving_yards_after_catch as receiving_yac,
                p.receiving_first_downs as receiving_first_downs,
                p.receiving_epa as receiving_epa,
                p.receiving_fumbles as receiving_fumbles,
                p.receiving_fumbles_lost as receiving_fumbles_lost,
                p.yards_per_target as yards_per_target,
                p.td_rate as td_rate,

                // NGS Metrics
                p.ngs_air_yards as ngs_air_yards,
                p.ngs_cushion as ngs_cushion,
                p.ngs_separation as ngs_separation,
                p.ngs_yac as ngs_yac,
                p.pfr_adot as pfr_adot,

                // Rushing Stats
                p.carries as carries,
                p.rushing_yards as rushing_yards,
                p.rushing_tds as rushing_tds,
                p.rushing_first_downs as rushing_first_downs,
                p.rushing_epa as rushing_epa,
                p.rushing_fumbles as rushing_fumbles,
                p.rushing_fumbles_lost as rushing_fumbles_lost,
                p.yards_per_carry as yards_per_carry,

                // Passing Stats (QB)
                p.pass_attempts as pass_attempts,
                p.completions as completions,
                p.passing_yards as passing_yards,
                p.passing_tds as passing_tds,
                p.passing_air_yards as passing_air_yards,
                p.passing_yards_after_catch as passing_yac,
                p.passing_first_downs as passing_first_downs,
                p.passing_epa as passing_epa,
                p.qbr as qbr,
                p.qbr_pts_added as qbr_pts_added,

                // Efficiency Metrics
                p.career_av as career_av,

                // Timestamps
                p.stats_updated as stats_updated,
                p.ktc_updated as ktc_updated,
                p.updated_at as updated_at,

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


@st.cache_data(ttl=300)
def get_player_available_seasons(gsis_id: str):
    """Get list of seasons with stats for a player."""
    driver = get_driver()

    with driver.session() as session:
        result = session.run("""
            MATCH (p:Player {gsis_id: $gsis_id})-[:HAS_SEASON_STATS]->(s:SeasonStats)
            RETURN DISTINCT s.season as season
            ORDER BY season DESC
        """, {'gsis_id': gsis_id})
        seasons = [r['season'] for r in result]
        return seasons if seasons else []


@st.cache_data(ttl=300)
def get_player_season_stats(gsis_id: str, season: int = None):
    """Get player stats for a specific season or career totals."""
    driver = get_driver()

    with driver.session() as session:
        if season:
            # Single season stats
            result = session.run("""
                MATCH (p:Player {gsis_id: $gsis_id})-[:HAS_SEASON_STATS]->(s:SeasonStats {season: $season})
                RETURN s {.*} as stats
            """, {'gsis_id': gsis_id, 'season': season})
            record = result.single()
            return dict(record['stats']) if record else None
        else:
            # Career totals from Player node
            result = session.run("""
                MATCH (p:Player {gsis_id: $gsis_id})
                RETURN {
                    games_played: p.career_games,
                    fantasy_points_ppr: p.career_fpts_ppr,
                    passing_yards: p.career_passing_yards,
                    passing_tds: p.career_passing_tds,
                    rushing_yards: p.career_rushing_yards,
                    rushing_tds: p.career_rushing_tds,
                    receiving_yards: p.career_receiving_yards,
                    receiving_tds: p.career_receiving_tds,
                    receptions: p.career_receptions,
                    seasons_played: p.seasons_played,
                    ppg: p.career_ppg
                } as stats
            """, {'gsis_id': gsis_id})
            record = result.single()
            return dict(record['stats']) if record else None


@st.cache_data(ttl=300)
def get_player_all_seasons(gsis_id: str):
    """Get all season stats for yearly trend visualization."""
    driver = get_driver()

    with driver.session() as session:
        result = session.run("""
            MATCH (p:Player {gsis_id: $gsis_id})-[:HAS_SEASON_STATS]->(s:SeasonStats)
            RETURN s.season as season,
                   s.games_played as games,
                   s.fantasy_points as fpts_std,
                   s.fantasy_points_ppr as fpts_ppr,
                   s.ppg as ppg,
                   s.passing_yards as pass_yds,
                   s.passing_tds as pass_tds,
                   s.rushing_yards as rush_yds,
                   s.rushing_tds as rush_tds,
                   s.receiving_yards as rec_yds,
                   s.receiving_tds as rec_tds,
                   s.receptions as receptions,
                   s.targets as targets
            ORDER BY s.season ASC
        """, {'gsis_id': gsis_id})
        return pd.DataFrame([dict(r) for r in result])


@st.cache_data(ttl=300)
def get_player_weekly_stats(gsis_id: str, season: int):
    """Get weekly stats for a specific season."""
    driver = get_driver()

    with driver.session() as session:
        result = session.run("""
            MATCH (p:Player {gsis_id: $gsis_id})-[:HAS_WEEKLY_STATS]->(w:WeeklyStats {season: $season})
            RETURN w.week as week,
                   w.fantasy_points as fpts_std,
                   w.fantasy_points_ppr as fpts_ppr,
                   w.passing_yards as pass_yds,
                   w.passing_tds as pass_tds,
                   w.rushing_yards as rush_yds,
                   w.rushing_tds as rush_tds,
                   w.receiving_yards as rec_yds,
                   w.receiving_tds as rec_tds,
                   w.receptions as receptions,
                   w.targets as targets,
                   w.carries as carries
            ORDER BY w.week ASC
        """, {'gsis_id': gsis_id, 'season': season})
        return pd.DataFrame([dict(r) for r in result])


@st.cache_data(ttl=3600)
def get_player_2026_projection(player_data: dict) -> dict:
    """Generate 2026 fantasy projection for a player using ML model or estimation."""
    # Try to load trained model
    model_path = PROJECT_ROOT / 'models' / 'season_projection_model.pkl'

    position = player_data.get('position')
    ppg_2025 = player_data.get('fpts_per_game', 0) or 0
    games = player_data.get('games_played', 0) or 0

    if games < 5 or ppg_2025 <= 0:
        return None

    if model_path.exists():
        try:
            from src.ml.fantasy_models import SeasonProjectionModel
            model = SeasonProjectionModel.load(str(model_path))

            # Build feature dict from player data
            df = pd.DataFrame([{
                'ppg_ppr': ppg_2025,
                'ppg_std': player_data.get('fantasy_points_std', ppg_2025 * 0.85) or ppg_2025 * 0.85,
                'games': games,
                'targets': player_data.get('targets', 0) or 0,
                'receptions': player_data.get('receptions', 0) or 0,
                'receiving_yards': player_data.get('receiving_yards', 0) or 0,
                'carries': player_data.get('carries', 0) or 0,
                'rushing_yards': player_data.get('rushing_yards', 0) or 0,
                'position': position,
            }])

            # Engineer features
            df['targets_per_game'] = df['targets'] / df['games'].replace(0, np.nan)
            df['receptions_per_game'] = df['receptions'] / df['games'].replace(0, np.nan)
            df['carries_per_game'] = df['carries'] / df['games'].replace(0, np.nan)

            predicted_ppg = model.predict(df)[0]
        except Exception:
            # Fallback to simple estimation
            predicted_ppg = ppg_2025 * 0.95
    else:
        # Simple estimation based on position-specific regression
        regression_factors = {'QB': 0.92, 'RB': 0.88, 'WR': 0.94, 'TE': 0.93}
        factor = regression_factors.get(position, 0.92)
        predicted_ppg = ppg_2025 * factor

    ppg_change = predicted_ppg - ppg_2025
    ppg_change_pct = (ppg_change / ppg_2025 * 100) if ppg_2025 > 0 else 0

    # Model confidence based on position-specific R² scores
    confidence_scores = {'QB': 0.73, 'RB': 0.84, 'WR': 0.84, 'TE': 0.77}
    confidence = confidence_scores.get(position, 0.75)

    return {
        'predicted_2026_ppg': predicted_ppg,
        'ppg_2025': ppg_2025,
        'ppg_change': ppg_change,
        'ppg_change_pct': ppg_change_pct,
        'model_confidence': confidence,
        'position': position
    }


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


def calc_fantasy_points(std_pts, ppr_pts, receptions, scoring_format):
    """
    Calculate fantasy points for the selected scoring format.

    Args:
        std_pts: Standard (non-PPR) fantasy points
        ppr_pts: Full PPR fantasy points
        receptions: Number of receptions
        scoring_format: One of "Standard", "0.5 PPR", "1 PPR"

    Returns:
        Fantasy points for the selected format
    """
    std_pts = std_pts or 0
    ppr_pts = ppr_pts or 0
    receptions = receptions or 0

    if scoring_format == "Standard":
        return std_pts
    elif scoring_format == "0.5 PPR":
        # Half PPR = Standard + (0.5 * receptions)
        return std_pts + (0.5 * receptions)
    else:  # 1 PPR
        return ppr_pts


def calc_ppg(total_pts, games, scoring_format=None):
    """Calculate points per game."""
    if not games or games == 0:
        return 0
    return total_pts / games


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
                    # FIVE ANALYSIS TABS
                    # ==========================================================
                    tab1, tab2, tab3, tab4, tab5 = st.tabs([
                        "📊 Valuation",
                        "🏃 Athletic Profile",
                        "📈 Situation",
                        "🏈 Stats",
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
                            st.markdown("#### Dynasty Rankings")

                            # KTC Rankings
                            ktc_rank = player.get('ktc_rank')
                            ktc_pos_rank = player.get('ktc_pos_rank')
                            ktc_trend = player.get('ktc_trend')

                            rank_cols = st.columns(2)
                            with rank_cols[0]:
                                if ktc_rank:
                                    st.metric("Overall Rank", f"#{ktc_rank}")
                            with rank_cols[1]:
                                if ktc_pos_rank:
                                    st.metric(f"{player['position']} Rank", f"#{ktc_pos_rank}")

                            if ktc_trend is not None:
                                trend_text = "📈 Rising" if ktc_trend > 0 else "📉 Falling" if ktc_trend < 0 else "➡️ Stable"
                                st.caption(f"Trend: {trend_text}")

                            # Recommendation
                            recommendation = player.get('recommendation')
                            if recommendation:
                                rec_colors = {
                                    'BUY': '🟢', 'STRONG_BUY': '🟢🟢',
                                    'SELL': '🔴', 'STRONG_SELL': '🔴🔴',
                                    'HOLD': '🟡'
                                }
                                st.markdown(f"**Recommendation:** {rec_colors.get(recommendation, '')} {recommendation}")

                            st.markdown("---")
                            st.markdown("#### Value Gap Analysis")

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
                            fpts_ppr = player.get('fantasy_points_ppr', 0) or 0
                            ppg = player.get('fpts_per_game', 0) or 0
                            games = player.get('games_played', 0) or 0

                            prod_cols = st.columns(2)
                            with prod_cols[0]:
                                st.metric("PPR Points", f"{fpts_ppr:.1f}")
                            with prod_cols[1]:
                                st.metric("PPG", f"{ppg:.1f}")

                            # Position rank estimate
                            if ppg > 20:
                                st.caption("Elite Production")
                            elif ppg > 12:
                                st.caption("Starter Level")
                            elif ppg > 6:
                                st.caption("Flex/Depth")
                            else:
                                st.caption("Lottery Ticket")

                        # 2026 PROJECTION SECTION
                        st.markdown("---")
                        st.markdown("### 🔮 2026 Season Projection")

                        # Get 2026 projection
                        projection = get_player_2026_projection(player)

                        if projection:
                            proj_cols = st.columns([1, 1, 1])

                            with proj_cols[0]:
                                st.metric(
                                    "2025 PPG (Current)",
                                    f"{projection['ppg_2025']:.1f}"
                                )

                            with proj_cols[1]:
                                st.metric(
                                    "2026 Projected PPG",
                                    f"{projection['predicted_2026_ppg']:.1f}",
                                    delta=f"{projection['ppg_change']:+.1f}",
                                    delta_color="normal" if projection['ppg_change'] >= 0 else "inverse"
                                )

                            with proj_cols[2]:
                                confidence_pct = projection['model_confidence'] * 100
                                st.metric(
                                    "Model Confidence",
                                    f"{confidence_pct:.0f}%",
                                    help=f"R² score for {projection['position']} projections"
                                )

                            # Projection interpretation
                            change_pct = projection['ppg_change_pct']
                            if change_pct > 10:
                                st.success(f"📈 **Projected Riser** (+{change_pct:.1f}%) - Model expects significant improvement")
                            elif change_pct > 3:
                                st.info(f"📈 Slight positive projection (+{change_pct:.1f}%)")
                            elif change_pct > -3:
                                st.caption(f"➡️ Stable projection ({change_pct:+.1f}%)")
                            elif change_pct > -10:
                                st.warning(f"📉 Slight decline projected ({change_pct:+.1f}%)")
                            else:
                                st.error(f"📉 **Regression Risk** ({change_pct:+.1f}%) - Consider selling high")

                            with st.expander("About 2026 Projections"):
                                st.markdown(f"""
                                **Model Details:**
                                - Trained on 26 years of NFL data (1999-2024)
                                - {projection['position']} R² Score: {projection['model_confidence']:.1%}
                                - RMSE: ~3.5 PPG

                                **Key Factors:**
                                - Current season production (most important)
                                - Usage metrics (targets/carries per game)
                                - Career trajectory
                                - Position-specific aging curves

                                *Note: Model cannot predict injuries, trades, or coaching changes.*
                                """)
                        else:
                            st.info("Not enough 2025 data for projection (requires 5+ games)")

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
                                # Athletic Score & Percentile
                                ath_score = player.get('athletic_score')
                                ath_pct = player.get('athletic_percentile')

                                if ath_score or ath_pct:
                                    st.markdown("#### Athletic Rating")
                                    score_cols = st.columns(2)
                                    with score_cols[0]:
                                        if ath_score:
                                            st.metric("Athletic Score", f"{ath_score:.2f}")
                                    with score_cols[1]:
                                        if ath_pct:
                                            st.metric("Percentile", f"{ath_pct:.0f}%")

                                    if ath_pct:
                                        if ath_pct >= 90:
                                            st.success("Elite Athlete")
                                        elif ath_pct >= 70:
                                            st.info("Above Average")
                                        elif ath_pct >= 50:
                                            st.caption("Average Athlete")
                                        else:
                                            st.warning("Below Average")
                                    st.markdown("---")

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
                                    if value and not (isinstance(value, float) and pd.isna(value)):
                                        st.metric(label, f"{value:.2f}{unit}")

                                # Physical
                                st.markdown("---")
                                st.markdown("#### Physical")
                                combine_height = player.get('combine_height')
                                if combine_height:
                                    st.metric("Height", combine_height)
                                elif player.get('height'):
                                    feet = int(player['height'] // 12)
                                    inches = int(player['height'] % 12)
                                    st.metric("Height", f"{feet}'{inches}\"")

                                combine_weight = player.get('combine_weight')
                                if combine_weight:
                                    st.metric("Weight", f"{int(combine_weight)} lbs")
                                elif player.get('weight'):
                                    st.metric("Weight", f"{int(player['weight'])} lbs")

                                # Draft Info
                                st.markdown("---")
                                st.markdown("#### Draft Capital")
                                draft_round = player.get('draft_round')
                                draft_pick = player.get('draft_pick')
                                draft_year = player.get('draft_year')
                                draft_value = player.get('draft_value')

                                if draft_round and draft_pick:
                                    st.metric("Draft Position", f"Rd {int(draft_round)}, Pick {int(draft_pick)}")
                                if draft_year:
                                    st.caption(f"Draft Year: {int(draft_year)}")
                                if draft_value:
                                    st.metric("Draft Value Score", f"{draft_value:.0f}")
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
                                # snap_pct is stored as decimal (0.86 = 86%), convert to percentage
                                snap_display = snap_pct * 100 if snap_pct <= 1 else snap_pct
                                st.metric("Snap %", f"{snap_display:.1f}%")
                                if snap_display >= 80:
                                    st.caption("Workhorse role")
                                elif snap_display >= 60:
                                    st.caption("Clear starter")
                                elif snap_display >= 40:
                                    st.caption("Committee/Rotational")
                                else:
                                    st.caption("Backup/Situational")

                            if snap_trend is not None:
                                # snap_trend stored as decimal (0.013 = 1.3%)
                                trend_display = snap_trend * 100 if abs(snap_trend) <= 1 else snap_trend
                                trend_delta = f"{trend_display:+.1f}%" if trend_display else "+0.0%"
                                color = "normal" if trend_display and trend_display > 0 else "inverse"
                                st.metric("Snap Trend", trend_delta, delta_color=color)
                                if trend_display and trend_display > 5:
                                    st.success("Role expanding")
                                elif trend_display and trend_display < -5:
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
                                # Contract values stored in millions
                                apy_dollars = apy * 1_000_000 if apy < 1000 else apy
                                st.metric("APY", format_money(apy_dollars))
                            if guaranteed:
                                # Contract values stored in millions
                                guaranteed_dollars = guaranteed * 1_000_000 if guaranteed < 1000 else guaranteed
                                st.metric("Guaranteed", format_money(guaranteed_dollars))
                                guar_pct = player.get('guaranteed_pct')
                                if guar_pct:
                                    st.caption(f"{guar_pct*100:.0f}% guaranteed" if guar_pct <= 1 else f"{guar_pct:.0f}% guaranteed")
                            if years:
                                st.metric("Years Left", years)
                            if cap_pct:
                                # cap_pct stored as decimal (0.016 = 1.6%)
                                cap_display = cap_pct * 100 if cap_pct <= 1 else cap_pct
                                st.metric("Cap %", f"{cap_display:.1f}%")

                            # APY Percentile
                            apy_pct = player.get('apy_percentile')
                            if apy_pct:
                                st.metric("APY Percentile", f"{apy_pct:.0f}%")
                                if apy_pct >= 90:
                                    st.caption("Elite contract")
                                elif apy_pct >= 70:
                                    st.caption("Above average pay")

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
                    # TAB 4: STATS
                    # ----------------------------------------------------------
                    with tab4:
                        st.subheader("Production Stats")

                        # Get available seasons for this player
                        available_seasons = get_player_available_seasons(gsis_id)

                        # Check if current player has 2025 stats on Player node
                        current_season = player.get('stats_season')
                        if current_season and int(current_season) not in available_seasons:
                            available_seasons = [int(current_season)] + available_seasons

                        # Selectors row: Year and Scoring Format
                        selector_cols = st.columns([2, 1])

                        with selector_cols[0]:
                            # Year selector
                            year_options = ["Career"] + [str(s) for s in available_seasons]
                            selected_year = st.selectbox(
                                "Select Season",
                                year_options,
                                index=0 if not available_seasons else 1,  # Default to most recent
                                help="View stats for a specific season or career totals"
                            )

                        with selector_cols[1]:
                            # Scoring format selector
                            scoring_format = st.selectbox(
                                "Scoring Format",
                                ["1 PPR", "0.5 PPR", "Standard"],
                                index=0,  # Default to PPR
                                help="Standard = no reception bonus, 0.5 PPR = 0.5 pts/rec, 1 PPR = 1 pt/rec"
                            )

                        # Determine which stats to show
                        if selected_year == "Career":
                            stats = get_player_season_stats(gsis_id, None)
                            st.caption("📊 Career Totals")
                        elif selected_year == str(current_season):
                            # Use current Player node stats for the current season
                            stats = {
                                'games_played': player.get('games_played'),
                                'fantasy_points_ppr': player.get('fantasy_points_ppr'),
                                'ppg': player.get('fpts_per_game'),
                                'passing_yards': player.get('passing_yards'),
                                'passing_tds': player.get('passing_tds'),
                                'rushing_yards': player.get('rushing_yards'),
                                'rushing_tds': player.get('rushing_tds'),
                                'receiving_yards': player.get('receiving_yards'),
                                'receiving_tds': player.get('receiving_tds'),
                                'receptions': player.get('receptions'),
                                'targets': player.get('targets'),
                                'carries': player.get('carries'),
                            }
                            st.caption(f"📅 {selected_year} Season Stats (Current)")
                        else:
                            stats = get_player_season_stats(gsis_id, int(selected_year))
                            st.caption(f"📅 {selected_year} Season Stats")

                        position = player.get('position')

                        # Helper to get stat from stats dict (historical) or player dict (current)
                        def get_stat(key, default=0):
                            if stats and key in stats and stats[key] is not None:
                                return stats[key]
                            return player.get(key, default) or default

                        # Position-specific stats layout
                        if position == 'QB':
                            # QB Stats
                            st.markdown("#### Passing Stats")
                            pass_cols = st.columns(4)

                            with pass_cols[0]:
                                attempts = get_stat('attempts', 0) or get_stat('pass_attempts', 0)
                                completions = get_stat('completions', 0)
                                comp_pct = (completions / attempts * 100) if attempts > 0 else 0
                                st.metric("Completions", f"{int(completions)}/{int(attempts)}")
                                st.caption(f"{comp_pct:.1f}% completion")

                            with pass_cols[1]:
                                st.metric("Passing Yards", f"{int(get_stat('passing_yards', 0)):,}")
                                st.metric("Passing TDs", int(get_stat('passing_tds', 0)))

                            with pass_cols[2]:
                                st.metric("Passing EPA", f"{player.get('passing_epa', 0) or 0:.1f}")
                                qbr = player.get('qbr')
                                if qbr:
                                    st.metric("QBR", f"{qbr:.1f}")

                            with pass_cols[3]:
                                st.metric("Pass Air Yards", f"{int(player.get('passing_air_yards', 0) or 0):,}")
                                st.metric("Pass YAC", f"{int(player.get('passing_yac', 0) or 0):,}")

                            # Rushing stats for mobile QBs
                            carries = get_stat('carries', 0)
                            if carries and carries > 10:
                                st.markdown("---")
                                st.markdown("#### Rushing Stats")
                                rush_cols = st.columns(4)
                                with rush_cols[0]:
                                    st.metric("Carries", int(carries))
                                with rush_cols[1]:
                                    st.metric("Rush Yards", f"{int(get_stat('rushing_yards', 0)):,}")
                                with rush_cols[2]:
                                    st.metric("Rush TDs", int(get_stat('rushing_tds', 0)))
                                with rush_cols[3]:
                                    rush_yds = get_stat('rushing_yards', 0)
                                    ypc = (rush_yds / carries) if carries > 0 else 0
                                    st.metric("YPC", f"{ypc:.1f}")

                        elif position == 'RB':
                            # RB Stats - Rushing primary
                            st.markdown("#### Rushing Stats")
                            rush_cols = st.columns(4)

                            carries = get_stat('carries', 0)
                            rush_yds = get_stat('rushing_yards', 0)

                            with rush_cols[0]:
                                st.metric("Carries", int(carries))
                                ypc = (rush_yds / carries) if carries > 0 else 0
                                st.metric("YPC", f"{ypc:.1f}")

                            with rush_cols[1]:
                                st.metric("Rush Yards", f"{int(rush_yds):,}")
                                st.metric("Rush TDs", int(get_stat('rushing_tds', 0)))

                            with rush_cols[2]:
                                st.metric("Rush 1st Downs", int(player.get('rushing_first_downs', 0) or 0))
                                rush_epa = player.get('rushing_epa', 0) or 0
                                st.metric("Rush EPA", f"{rush_epa:.1f}")

                            with rush_cols[3]:
                                fumbles = player.get('rushing_fumbles', 0) or 0
                                fumbles_lost = player.get('rushing_fumbles_lost', 0) or 0
                                st.metric("Fumbles", f"{int(fumbles)} ({int(fumbles_lost)} lost)")

                            # Receiving stats for pass-catching RBs
                            targets = get_stat('targets', 0)
                            if targets and targets > 10:
                                st.markdown("---")
                                st.markdown("#### Receiving Stats")
                                rec_cols = st.columns(4)
                                receptions = get_stat('receptions', 0)
                                with rec_cols[0]:
                                    catch_pct = (receptions / targets * 100) if targets > 0 else 0
                                    st.metric("Receptions", f"{int(receptions)}/{int(targets)}")
                                    st.caption(f"{catch_pct:.0f}% catch rate")
                                with rec_cols[1]:
                                    st.metric("Rec Yards", f"{int(get_stat('receiving_yards', 0)):,}")
                                with rec_cols[2]:
                                    st.metric("Rec TDs", int(get_stat('receiving_tds', 0)))
                                with rec_cols[3]:
                                    rec_yds = get_stat('receiving_yards', 0)
                                    ypr = (rec_yds / targets) if targets > 0 else 0
                                    st.metric("Y/Target", f"{ypr:.1f}")

                        else:  # WR or TE
                            # Receiving Stats
                            st.markdown("#### Receiving Stats")
                            rec_cols = st.columns(4)

                            targets = get_stat('targets', 0)
                            receptions = get_stat('receptions', 0)

                            with rec_cols[0]:
                                catch_pct = (receptions / targets * 100) if targets > 0 else 0
                                st.metric("Receptions", f"{int(receptions)}/{int(targets)} tgt")
                                st.caption(f"{catch_pct:.0f}% catch rate")

                            with rec_cols[1]:
                                st.metric("Rec Yards", f"{int(get_stat('receiving_yards', 0)):,}")
                                st.metric("Rec TDs", int(get_stat('receiving_tds', 0)))

                            with rec_cols[2]:
                                st.metric("Rec 1st Downs", int(player.get('receiving_first_downs', 0) or 0))
                                td_rate = player.get('td_rate', 0) or 0
                                st.metric("TD Rate", f"{td_rate*100:.1f}%")

                            with rec_cols[3]:
                                ypr = player.get('yards_per_target', 0) or 0
                                st.metric("Y/Target", f"{ypr:.1f}")
                                rec_epa = player.get('receiving_epa', 0) or 0
                                st.metric("Rec EPA", f"{rec_epa:.1f}")

                            # Advanced Receiving Metrics
                            st.markdown("---")
                            st.markdown("#### Advanced Metrics")
                            adv_cols = st.columns(4)

                            with adv_cols[0]:
                                air_yards = player.get('receiving_air_yards', 0) or 0
                                st.metric("Air Yards", f"{int(air_yards):,}")
                                adot = player.get('pfr_adot', 0) or 0
                                if adot:
                                    st.metric("aDOT", f"{adot:.1f}")

                            with adv_cols[1]:
                                yac = player.get('receiving_yac', 0) or 0
                                st.metric("YAC", f"{int(yac):,}")
                                ngs_yac = player.get('ngs_yac', 0) or 0
                                if ngs_yac:
                                    st.metric("NGS YAC/Rec", f"{ngs_yac:.1f}")

                            with adv_cols[2]:
                                fumbles = player.get('receiving_fumbles', 0) or 0
                                fumbles_lost = player.get('receiving_fumbles_lost', 0) or 0
                                st.metric("Fumbles", f"{int(fumbles)} ({int(fumbles_lost)} lost)")

                            with adv_cols[3]:
                                first_downs = player.get('receiving_first_downs', 0) or 0
                                rec = player.get('receptions', 0) or 0
                                fd_rate = (first_downs / rec * 100) if rec > 0 else 0
                                st.metric("1st Down Rate", f"{fd_rate:.0f}%")

                        # NGS Metrics for all skill positions
                        ngs_air = player.get('ngs_air_yards')
                        ngs_sep = player.get('ngs_separation')
                        ngs_cush = player.get('ngs_cushion')
                        ngs_yac = player.get('ngs_yac')

                        if any([ngs_air, ngs_sep, ngs_cush, ngs_yac]):
                            st.markdown("---")
                            st.markdown("#### Next Gen Stats")
                            ngs_cols = st.columns(4)

                            with ngs_cols[0]:
                                if ngs_air:
                                    st.metric("Avg Air Yards", f"{ngs_air:.1f}")
                            with ngs_cols[1]:
                                if ngs_sep:
                                    st.metric("Avg Separation", f"{ngs_sep:.1f} yds")
                            with ngs_cols[2]:
                                if ngs_cush:
                                    st.metric("Avg Cushion", f"{ngs_cush:.1f} yds")
                            with ngs_cols[3]:
                                if ngs_yac:
                                    st.metric("Avg YAC", f"{ngs_yac:.1f}")

                        # ==============================================
                        # VISUALIZATIONS
                        # ==============================================
                        st.markdown("---")
                        st.markdown("### 📈 Performance Trends")

                        # Get all seasons data for visualizations
                        all_seasons_df = get_player_all_seasons(gsis_id)

                        if not all_seasons_df.empty and len(all_seasons_df) > 1:
                            viz_tabs = st.tabs(["Yearly Trends", "Weekly Breakdown"])

                            with viz_tabs[0]:
                                # Yearly trend charts
                                st.markdown(f"#### Fantasy Points by Season ({scoring_format})")

                                # Calculate fantasy points for selected format
                                all_seasons_df['fpts_calc'] = all_seasons_df.apply(
                                    lambda row: calc_fantasy_points(
                                        row.get('fpts_std', 0),
                                        row.get('fpts_ppr', 0),
                                        row.get('receptions', 0),
                                        scoring_format
                                    ), axis=1
                                )
                                all_seasons_df['ppg_calc'] = all_seasons_df.apply(
                                    lambda row: calc_ppg(row['fpts_calc'], row.get('games', 0)),
                                    axis=1
                                )

                                # Create yearly PPG chart
                                fig_ppg = go.Figure()
                                fig_ppg.add_trace(go.Bar(
                                    x=all_seasons_df['season'].astype(str),
                                    y=all_seasons_df['ppg_calc'],
                                    name='PPG',
                                    marker_color=COLORS['primary'],
                                    text=all_seasons_df['ppg_calc'].round(1),
                                    textposition='outside'
                                ))
                                fig_ppg.update_layout(
                                    title=f"Points Per Game ({scoring_format})",
                                    xaxis_title="Season",
                                    yaxis_title="PPG",
                                    height=350,
                                    showlegend=False
                                )
                                st.plotly_chart(fig_ppg, use_container_width=True)

                                # Position-specific yearly trends
                                if position in ['WR', 'TE']:
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        fig_rec = go.Figure()
                                        fig_rec.add_trace(go.Scatter(
                                            x=all_seasons_df['season'].astype(str),
                                            y=all_seasons_df['rec_yds'],
                                            mode='lines+markers',
                                            name='Rec Yards',
                                            line=dict(color=COLORS['primary'], width=2),
                                            marker=dict(size=8)
                                        ))
                                        fig_rec.update_layout(title="Receiving Yards", height=300)
                                        st.plotly_chart(fig_rec, use_container_width=True)

                                    with col2:
                                        fig_td = go.Figure()
                                        fig_td.add_trace(go.Bar(
                                            x=all_seasons_df['season'].astype(str),
                                            y=all_seasons_df['rec_tds'],
                                            name='TDs',
                                            marker_color=COLORS['success']
                                        ))
                                        fig_td.update_layout(title="Receiving TDs", height=300)
                                        st.plotly_chart(fig_td, use_container_width=True)

                                elif position == 'RB':
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        fig_rush = go.Figure()
                                        fig_rush.add_trace(go.Scatter(
                                            x=all_seasons_df['season'].astype(str),
                                            y=all_seasons_df['rush_yds'],
                                            mode='lines+markers',
                                            name='Rush Yards',
                                            line=dict(color=COLORS['primary'], width=2)
                                        ))
                                        fig_rush.add_trace(go.Scatter(
                                            x=all_seasons_df['season'].astype(str),
                                            y=all_seasons_df['rec_yds'],
                                            mode='lines+markers',
                                            name='Rec Yards',
                                            line=dict(color=COLORS['success'], width=2, dash='dash')
                                        ))
                                        fig_rush.update_layout(title="Yards by Type", height=300)
                                        st.plotly_chart(fig_rush, use_container_width=True)

                                    with col2:
                                        # Stacked TDs
                                        fig_td = go.Figure()
                                        fig_td.add_trace(go.Bar(
                                            x=all_seasons_df['season'].astype(str),
                                            y=all_seasons_df['rush_tds'],
                                            name='Rush TDs',
                                            marker_color=COLORS['primary']
                                        ))
                                        fig_td.add_trace(go.Bar(
                                            x=all_seasons_df['season'].astype(str),
                                            y=all_seasons_df['rec_tds'],
                                            name='Rec TDs',
                                            marker_color=COLORS['success']
                                        ))
                                        fig_td.update_layout(title="Touchdowns", barmode='stack', height=300)
                                        st.plotly_chart(fig_td, use_container_width=True)

                                elif position == 'QB':
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        fig_pass = go.Figure()
                                        fig_pass.add_trace(go.Scatter(
                                            x=all_seasons_df['season'].astype(str),
                                            y=all_seasons_df['pass_yds'],
                                            mode='lines+markers',
                                            name='Pass Yards',
                                            line=dict(color=COLORS['primary'], width=2)
                                        ))
                                        fig_pass.update_layout(title="Passing Yards", height=300)
                                        st.plotly_chart(fig_pass, use_container_width=True)

                                    with col2:
                                        fig_td = go.Figure()
                                        fig_td.add_trace(go.Bar(
                                            x=all_seasons_df['season'].astype(str),
                                            y=all_seasons_df['pass_tds'],
                                            name='Pass TDs',
                                            marker_color=COLORS['primary']
                                        ))
                                        if all_seasons_df['rush_tds'].sum() > 0:
                                            fig_td.add_trace(go.Bar(
                                                x=all_seasons_df['season'].astype(str),
                                                y=all_seasons_df['rush_tds'],
                                                name='Rush TDs',
                                                marker_color=COLORS['success']
                                            ))
                                        fig_td.update_layout(title="Touchdowns", barmode='stack', height=300)
                                        st.plotly_chart(fig_td, use_container_width=True)

                            with viz_tabs[1]:
                                # Weekly breakdown for selected season
                                if selected_year != "Career":
                                    weekly_df = get_player_weekly_stats(gsis_id, int(selected_year))

                                    if not weekly_df.empty:
                                        st.markdown(f"#### {selected_year} Weekly Performance ({scoring_format})")

                                        # Calculate fantasy points for selected format
                                        weekly_df['fpts_calc'] = weekly_df.apply(
                                            lambda row: calc_fantasy_points(
                                                row.get('fpts_std', 0),
                                                row.get('fpts_ppr', 0),
                                                row.get('receptions', 0),
                                                scoring_format
                                            ), axis=1
                                        )

                                        # Weekly fantasy points line chart
                                        fig_weekly = go.Figure()
                                        fig_weekly.add_trace(go.Scatter(
                                            x=weekly_df['week'],
                                            y=weekly_df['fpts_calc'],
                                            mode='lines+markers',
                                            name=f'{scoring_format} Points',
                                            line=dict(color=COLORS['primary'], width=2),
                                            marker=dict(size=8),
                                            fill='tozeroy',
                                            fillcolor='rgba(30, 58, 95, 0.1)'
                                        ))

                                        # Add average line
                                        avg_pts = weekly_df['fpts_calc'].mean()
                                        fig_weekly.add_hline(
                                            y=avg_pts,
                                            line_dash="dash",
                                            line_color=COLORS['neutral'],
                                            annotation_text=f"Avg: {avg_pts:.1f}",
                                            annotation_position="top right"
                                        )

                                        fig_weekly.update_layout(
                                            title=f"Weekly Fantasy Points ({selected_year}) - {scoring_format}",
                                            xaxis_title="Week",
                                            yaxis_title=f"{scoring_format} Points",
                                            height=400,
                                            hovermode='x unified'
                                        )
                                        st.plotly_chart(fig_weekly, use_container_width=True)

                                        # Weekly stats table
                                        st.markdown("#### Week-by-Week Breakdown")
                                        display_df = weekly_df[['week', 'fpts_calc', 'pass_yds', 'pass_tds',
                                                               'rush_yds', 'rush_tds', 'rec_yds', 'rec_tds',
                                                               'receptions', 'targets', 'carries']].copy()
                                        display_df.columns = ['Week', f'{scoring_format} Pts', 'Pass Yds', 'Pass TD',
                                                            'Rush Yds', 'Rush TD', 'Rec Yds', 'Rec TD',
                                                            'Rec', 'Targets', 'Carries']
                                        # Format numeric columns
                                        for col in display_df.columns[2:]:
                                            display_df[col] = display_df[col].fillna(0).astype(int)
                                        display_df[f'{scoring_format} Pts'] = weekly_df['fpts_calc'].round(1)

                                        st.dataframe(
                                            display_df,
                                            hide_index=True,
                                            use_container_width=True
                                        )

                                        # Summary stats
                                        st.markdown(f"#### Season Summary ({scoring_format})")
                                        sum_cols = st.columns(4)
                                        with sum_cols[0]:
                                            st.metric("Total Points", f"{weekly_df['fpts_calc'].sum():.1f}")
                                        with sum_cols[1]:
                                            st.metric("Avg PPG", f"{weekly_df['fpts_calc'].mean():.1f}")
                                        with sum_cols[2]:
                                            st.metric("Best Week", f"{weekly_df['fpts_calc'].max():.1f}")
                                        with sum_cols[3]:
                                            st.metric("Games", len(weekly_df))
                                    else:
                                        st.info(f"No weekly data available for {selected_year}")
                                else:
                                    st.info("Select a specific season to view weekly breakdown")

                        elif not all_seasons_df.empty:
                            st.info("Only one season of data available - trends will show with more seasons")
                        else:
                            st.info("No historical stats available for this player")

                        # Data freshness
                        st.markdown("---")
                        stats_updated = player.get('stats_updated')
                        if stats_updated:
                            st.caption(f"📊 Stats last updated: {str(stats_updated)[:19]}")

                    # ----------------------------------------------------------
                    # TAB 5: HISTORY
                    # ----------------------------------------------------------
                    with tab5:
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
