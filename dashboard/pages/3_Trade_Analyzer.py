"""
Thoth Trade Command Center
==========================
ML-powered trade analysis with factor breakdowns,
confidence scores, and roster impact analysis.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.components.tooltips import get_signal_color, get_signal_emoji

st.set_page_config(page_title="Trade Command Center - Thoth", layout="wide")

# =============================================================================
# THOTH DESIGN SYSTEM
# =============================================================================
COLORS = {
    'primary': '#1E3A5F',
    'success': '#10B981',
    'danger': '#EF4444',
    'warning': '#F59E0B',
    'neutral': '#6B7280'
}

# Position age curves (expected productive years remaining)
AGE_CURVES = {
    'QB': {'peak_start': 26, 'peak_end': 34, 'cliff': 38, 'endpoint': 42},
    'RB': {'peak_start': 22, 'peak_end': 26, 'cliff': 28, 'endpoint': 30},
    'WR': {'peak_start': 24, 'peak_end': 28, 'cliff': 30, 'endpoint': 34},
    'TE': {'peak_start': 25, 'peak_end': 29, 'cliff': 31, 'endpoint': 35}
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
def get_all_players():
    """Get all players with full data for selection."""
    driver = get_driver()

    with driver.session() as session:
        result = session.run("""
            MATCH (p:Player)
            WHERE p.position IN ['QB', 'RB', 'WR', 'TE']
              AND p.ktc_value > 500
            RETURN p.gsis_id as gsis_id,
                   p.name as name,
                   p.position as position,
                   p.current_team as team,
                   p.ktc_value as ktc_value,
                   p.predicted_ktc_value as predicted_value,
                   p.value_delta as value_delta,
                   p.value_delta_pct as value_delta_pct,
                   p.dynasty_edge_score as edge_score,
                   p.edge_signal as signal,
                   p.age as age,
                   p.years_exp as experience,
                   p.contract_guaranteed as contract_guaranteed,
                   p.avg_snap_pct as snap_pct,
                   p.snap_trend as snap_trend,
                   p.injury_risk_score as injury_risk,
                   p.fantasy_points_season as fpts
            ORDER BY p.ktc_value DESC
        """)
        return [dict(r) for r in result]


# =============================================================================
# ANALYSIS FUNCTIONS
# =============================================================================

def calculate_years_remaining(position: str, age: int) -> int:
    """Calculate expected productive years remaining."""
    if not age or not position:
        return 5
    curve = AGE_CURVES.get(position, AGE_CURVES['WR'])
    return max(0, curve['endpoint'] - age)


def calculate_career_phase(position: str, age: int) -> str:
    """Determine career phase."""
    if not age or not position:
        return "Unknown"
    curve = AGE_CURVES.get(position, AGE_CURVES['WR'])

    if age < curve['peak_start']:
        return "Rising"
    elif age <= curve['peak_end']:
        return "Prime"
    elif age <= curve['cliff']:
        return "Declining"
    else:
        return "Twilight"


def calculate_confidence(player: dict) -> tuple:
    """Calculate prediction confidence score (0-100) and factors."""
    score = 70  # Base confidence
    factors = []

    # More data = higher confidence
    if player.get('fpts') and player['fpts'] > 0:
        score += 10
        factors.append("Has production data")
    else:
        score -= 10
        factors.append("Limited production data")

    if player.get('contract_guaranteed'):
        score += 10
        factors.append("Contract data available")

    if player.get('snap_pct'):
        score += 5
        factors.append("Snap data available")

    # Young players = more uncertainty
    age = player.get('age', 25)
    if age and age < 23:
        score -= 10
        factors.append("Young player (higher variance)")
    elif age and age > 30:
        score -= 5
        factors.append("Aging player")

    return min(100, max(30, score)), factors


def analyze_trade_ml(give_players: list, get_players: list) -> dict:
    """Analyze trade using ML predictions and multiple factors."""

    # Calculate totals
    give_ktc = sum(p.get('ktc_value', 0) or 0 for p in give_players)
    give_predicted = sum(p.get('predicted_value', 0) or p.get('ktc_value', 0) or 0 for p in give_players)

    get_ktc = sum(p.get('ktc_value', 0) or 0 for p in get_players)
    get_predicted = sum(p.get('predicted_value', 0) or p.get('ktc_value', 0) or 0 for p in get_players)

    # Value differences
    ktc_diff = get_ktc - give_ktc
    predicted_diff = get_predicted - give_predicted

    # Age analysis
    give_ages = [p.get('age', 25) or 25 for p in give_players]
    get_ages = [p.get('age', 25) or 25 for p in get_players]
    give_avg_age = sum(give_ages) / len(give_ages) if give_ages else 25
    get_avg_age = sum(get_ages) / len(get_ages) if get_ages else 25

    # Years remaining analysis
    give_years = sum(calculate_years_remaining(p.get('position'), p.get('age'))
                     for p in give_players)
    get_years = sum(calculate_years_remaining(p.get('position'), p.get('age'))
                    for p in get_players)

    # Signal analysis
    give_buy_signals = len([p for p in give_players if p.get('signal') in ['BUY', 'STRONG_BUY']])
    give_sell_signals = len([p for p in give_players if p.get('signal') in ['SELL', 'STRONG_SELL']])
    get_buy_signals = len([p for p in get_players if p.get('signal') in ['BUY', 'STRONG_BUY']])
    get_sell_signals = len([p for p in get_players if p.get('signal') in ['SELL', 'STRONG_SELL']])

    # Production analysis
    give_fpts = sum(p.get('fpts', 0) or 0 for p in give_players)
    get_fpts = sum(p.get('fpts', 0) or 0 for p in get_players)

    # Risk analysis
    give_risk = sum(p.get('injury_risk', 0) or 0 for p in give_players) / len(give_players) if give_players else 0
    get_risk = sum(p.get('injury_risk', 0) or 0 for p in get_players) / len(get_players) if get_players else 0

    # Calculate weighted trade score
    # Positive = favors YOU (getting side)
    trade_score = 0
    score_factors = []

    # KTC value difference (weight: 25%)
    ktc_factor = ktc_diff / 1000 * 25
    trade_score += ktc_factor
    if ktc_diff > 500:
        score_factors.append(("KTC Value", ktc_factor, f"+{ktc_diff:,} in market value"))
    elif ktc_diff < -500:
        score_factors.append(("KTC Value", ktc_factor, f"{ktc_diff:,} market value loss"))

    # Model prediction difference (weight: 35%)
    pred_factor = predicted_diff / 1000 * 35
    trade_score += pred_factor
    if predicted_diff > 500:
        score_factors.append(("Model Prediction", pred_factor, f"Model sees +{predicted_diff:,.0f} value"))
    elif predicted_diff < -500:
        score_factors.append(("Model Prediction", pred_factor, f"Model sees {predicted_diff:,.0f} risk"))

    # Age/longevity (weight: 20%)
    years_diff = get_years - give_years
    age_factor = years_diff * 2  # 2 points per year
    trade_score += age_factor
    if years_diff > 3:
        score_factors.append(("Age Curve", age_factor, f"Gaining {years_diff:.0f} productive years"))
    elif years_diff < -3:
        score_factors.append(("Age Curve", age_factor, f"Losing {abs(years_diff):.0f} productive years"))

    # Signal alignment (weight: 10%)
    signal_score = (get_buy_signals - give_buy_signals) * 5 - (get_sell_signals - give_sell_signals) * 5
    trade_score += signal_score
    if get_buy_signals > give_buy_signals:
        score_factors.append(("Buy Signals", signal_score, f"Acquiring {get_buy_signals} BUY signal(s)"))
    if give_sell_signals > get_sell_signals:
        score_factors.append(("Sell Signals", signal_score * 0.5, f"Selling {give_sell_signals} SELL signal(s)"))

    # Production (weight: 10%)
    fpts_diff = get_fpts - give_fpts
    if give_fpts > 0:
        fpts_pct = fpts_diff / give_fpts * 10
    else:
        fpts_pct = 0
    trade_score += fpts_pct
    if fpts_diff > 50:
        score_factors.append(("Production", fpts_pct, f"Gaining {fpts_diff:.0f} fantasy points"))

    # Generate recommendation
    if trade_score > 15:
        recommendation = "STRONG ACCEPT"
        color = COLORS['success']
    elif trade_score > 5:
        recommendation = "ACCEPT"
        color = COLORS['success']
    elif trade_score > -5:
        recommendation = "FAIR TRADE"
        color = COLORS['neutral']
    elif trade_score > -15:
        recommendation = "DECLINE"
        color = COLORS['warning']
    else:
        recommendation = "STRONG DECLINE"
        color = COLORS['danger']

    # Generate reason
    reasons = []
    if predicted_diff > 1000:
        reasons.append("Model sees significant upside")
    elif predicted_diff < -1000:
        reasons.append("Model sees significant downside")
    if get_avg_age < give_avg_age - 2:
        reasons.append("Getting younger")
    elif get_avg_age > give_avg_age + 2:
        reasons.append("Getting older")
    if get_buy_signals > 0 and give_sell_signals > 0:
        reasons.append("Good signal swap")
    if give_buy_signals > 0:
        reasons.append("Giving up BUY signals")

    return {
        'give_ktc': give_ktc,
        'give_predicted': give_predicted,
        'get_ktc': get_ktc,
        'get_predicted': get_predicted,
        'ktc_diff': ktc_diff,
        'predicted_diff': predicted_diff,
        'give_avg_age': give_avg_age,
        'get_avg_age': get_avg_age,
        'give_years': give_years,
        'get_years': get_years,
        'give_fpts': give_fpts,
        'get_fpts': get_fpts,
        'give_risk': give_risk,
        'get_risk': get_risk,
        'trade_score': trade_score,
        'score_factors': score_factors,
        'recommendation': recommendation,
        'recommendation_color': color,
        'reasons': reasons,
        'give_buy_signals': give_buy_signals,
        'give_sell_signals': give_sell_signals,
        'get_buy_signals': get_buy_signals,
        'get_sell_signals': get_sell_signals
    }


# =============================================================================
# VISUALIZATIONS
# =============================================================================

def create_trade_comparison_bar(analysis: dict):
    """Create horizontal bar chart comparing trade sides."""
    categories = ['KTC Value', 'Model Value', 'Production', 'Years Left']
    give_values = [
        analysis['give_ktc'],
        analysis['give_predicted'],
        analysis['give_fpts'],
        analysis['give_years'] * 1000
    ]
    get_values = [
        analysis['get_ktc'],
        analysis['get_predicted'],
        analysis['get_fpts'],
        analysis['get_years'] * 1000
    ]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        name='You Give',
        x=give_values,
        y=categories,
        orientation='h',
        marker=dict(color=COLORS['danger']),
        text=[f"{v:,.0f}" for v in give_values],
        textposition='inside'
    ))

    fig.add_trace(go.Bar(
        name='You Get',
        x=get_values,
        y=categories,
        orientation='h',
        marker=dict(color=COLORS['success']),
        text=[f"{v:,.0f}" for v in get_values],
        textposition='inside'
    ))

    fig.update_layout(
        title="Trade Comparison",
        barmode='group',
        height=350,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    return fig


def create_age_curve_chart(give_players: list, get_players: list):
    """Create age curve visualization."""
    fig = go.Figure()

    # Position age curves
    for position, curve in AGE_CURVES.items():
        ages = list(range(20, curve['endpoint'] + 2))
        values = []
        for age in ages:
            if age < curve['peak_start']:
                val = 0.5 + (age - 20) / (curve['peak_start'] - 20) * 0.5
            elif age <= curve['peak_end']:
                val = 1.0
            elif age <= curve['cliff']:
                val = 1.0 - (age - curve['peak_end']) / (curve['cliff'] - curve['peak_end']) * 0.3
            elif age <= curve['endpoint']:
                val = 0.7 - (age - curve['cliff']) / (curve['endpoint'] - curve['cliff']) * 0.7
            else:
                val = 0
            values.append(val * 100)

        fig.add_trace(go.Scatter(
            x=ages,
            y=values,
            mode='lines',
            name=position,
            line=dict(dash='dot', width=1),
            opacity=0.5
        ))

    # Plot players you're giving
    for p in give_players:
        age = p.get('age', 25)
        if age:
            phase = calculate_career_phase(p.get('position'), age)
            phase_val = {'Rising': 75, 'Prime': 100, 'Declining': 60, 'Twilight': 30}.get(phase, 50)
            fig.add_trace(go.Scatter(
                x=[age],
                y=[phase_val],
                mode='markers+text',
                name=f"Give: {p['name']}",
                marker=dict(size=15, color=COLORS['danger'], symbol='circle'),
                text=[p['name'][:10]],
                textposition='top center',
                showlegend=False
            ))

    # Plot players you're getting
    for p in get_players:
        age = p.get('age', 25)
        if age:
            phase = calculate_career_phase(p.get('position'), age)
            phase_val = {'Rising': 75, 'Prime': 100, 'Declining': 60, 'Twilight': 30}.get(phase, 50)
            fig.add_trace(go.Scatter(
                x=[age],
                y=[phase_val],
                mode='markers+text',
                name=f"Get: {p['name']}",
                marker=dict(size=15, color=COLORS['success'], symbol='diamond'),
                text=[p['name'][:10]],
                textposition='top center',
                showlegend=False
            ))

    fig.update_layout(
        title="Age Curve Position",
        xaxis_title="Age",
        yaxis_title="Career Value %",
        height=350,
        showlegend=True
    )

    return fig


def create_factor_breakdown_chart(score_factors: list):
    """Create waterfall chart of score factors."""
    if not score_factors:
        return None

    names = [f[0] for f in score_factors]
    values = [f[1] for f in score_factors]

    colors = [COLORS['success'] if v > 0 else COLORS['danger'] for v in values]

    fig = go.Figure(go.Bar(
        x=values,
        y=names,
        orientation='h',
        marker_color=colors,
        text=[f"{v:+.1f}" for v in values],
        textposition='outside'
    ))

    fig.add_vline(x=0, line_width=2, line_color=COLORS['neutral'])

    fig.update_layout(
        title="Trade Score Factors",
        xaxis_title="Impact on Trade Score",
        height=300
    )

    return fig


# =============================================================================
# MAIN PAGE
# =============================================================================

def main():
    st.title("🔄 Trade Command Center")
    st.markdown("ML-powered trade analysis with confidence scoring")

    # Get all players
    all_players = get_all_players()

    if not all_players:
        st.warning("No player data available. Run the pipeline first.")
        return

    # Create player options with signal indicators
    player_options = {}
    for p in all_players:
        signal = p.get('signal', 'HOLD') or 'HOLD'
        emoji = get_signal_emoji(signal)
        ktc = p.get('ktc_value', 0) or 0
        label = f"{p['name']} ({p['position']}) - {ktc:,} {emoji}"
        player_options[label] = p

    st.divider()

    # ==========================================================================
    # TRADE INPUT
    # ==========================================================================
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📤 You Give")
        give_selections = st.multiselect(
            "Select players to give",
            options=list(player_options.keys()),
            key="give",
            help="Players you're trading away"
        )
        give_players = [player_options[s] for s in give_selections]

        if give_players:
            for p in give_players:
                signal = p.get('signal', 'HOLD') or 'HOLD'
                signal_color = get_signal_color(signal)
                emoji = get_signal_emoji(signal)

                with st.container():
                    st.markdown(f"**{p['name']}** {emoji}")
                    info_cols = st.columns(4)
                    with info_cols[0]:
                        st.caption(f"{p['position']}, Age {p.get('age', '?')}")
                    with info_cols[1]:
                        st.caption(f"KTC: {p.get('ktc_value', 0):,}")
                    with info_cols[2]:
                        predicted = p.get('predicted_value')
                        st.caption(f"Model: {predicted:,.0f}" if predicted else "Model: N/A")
                    with info_cols[3]:
                        phase = calculate_career_phase(p.get('position'), p.get('age'))
                        st.caption(f"Phase: {phase}")

            give_total = sum(p.get('ktc_value', 0) or 0 for p in give_players)
            st.metric("Total KTC", f"{give_total:,}")

    with col2:
        st.subheader("📥 You Get")
        get_selections = st.multiselect(
            "Select players to get",
            options=list(player_options.keys()),
            key="get",
            help="Players you're receiving"
        )
        get_players = [player_options[s] for s in get_selections]

        if get_players:
            for p in get_players:
                signal = p.get('signal', 'HOLD') or 'HOLD'
                emoji = get_signal_emoji(signal)

                with st.container():
                    st.markdown(f"**{p['name']}** {emoji}")
                    info_cols = st.columns(4)
                    with info_cols[0]:
                        st.caption(f"{p['position']}, Age {p.get('age', '?')}")
                    with info_cols[1]:
                        st.caption(f"KTC: {p.get('ktc_value', 0):,}")
                    with info_cols[2]:
                        predicted = p.get('predicted_value')
                        st.caption(f"Model: {predicted:,.0f}" if predicted else "Model: N/A")
                    with info_cols[3]:
                        phase = calculate_career_phase(p.get('position'), p.get('age'))
                        st.caption(f"Phase: {phase}")

            get_total = sum(p.get('ktc_value', 0) or 0 for p in get_players)
            st.metric("Total KTC", f"{get_total:,}")

    st.divider()

    # ==========================================================================
    # TRADE ANALYSIS
    # ==========================================================================
    if give_players and get_players:
        analysis = analyze_trade_ml(give_players, get_players)

        # Recommendation header
        rec_cols = st.columns([2, 1, 1])

        with rec_cols[0]:
            st.markdown(
                f"<h2 style='color: {analysis['recommendation_color']};'>"
                f"{analysis['recommendation']}</h2>",
                unsafe_allow_html=True
            )
            if analysis['reasons']:
                st.markdown("*" + " | ".join(analysis['reasons']) + "*")

        with rec_cols[1]:
            st.metric(
                "Trade Score",
                f"{analysis['trade_score']:+.1f}",
                help="Positive favors you, negative favors them"
            )

        with rec_cols[2]:
            # Calculate average confidence
            all_trade_players = give_players + get_players
            confidences = [calculate_confidence(p)[0] for p in all_trade_players]
            avg_confidence = sum(confidences) / len(confidences)
            st.metric(
                "Confidence",
                f"{avg_confidence:.0f}%",
                help="Prediction reliability based on data availability"
            )

        st.divider()

        # ==========================================================================
        # DETAILED ANALYSIS TABS
        # ==========================================================================
        tab1, tab2, tab3, tab4 = st.tabs([
            "📊 Value Comparison",
            "📈 Age Analysis",
            "🎯 Factor Breakdown",
            "📋 Player Details"
        ])

        # --------------------------------------------------------------------------
        # TAB 1: VALUE COMPARISON
        # --------------------------------------------------------------------------
        with tab1:
            val_cols = st.columns([1.5, 1])

            with val_cols[0]:
                fig = create_trade_comparison_bar(analysis)
                st.plotly_chart(fig, use_container_width=True)

            with val_cols[1]:
                st.markdown("### Value Summary")

                # KTC
                st.markdown("**Market Value (KTC)**")
                ktc_cols = st.columns(3)
                with ktc_cols[0]:
                    st.metric("Give", f"{analysis['give_ktc']:,}")
                with ktc_cols[1]:
                    st.metric("Get", f"{analysis['get_ktc']:,}")
                with ktc_cols[2]:
                    st.metric("Diff", f"{analysis['ktc_diff']:+,}")

                st.markdown("---")

                # Model
                st.markdown("**Model Prediction**")
                model_cols = st.columns(3)
                with model_cols[0]:
                    st.metric("Give", f"{analysis['give_predicted']:,.0f}")
                with model_cols[1]:
                    st.metric("Get", f"{analysis['get_predicted']:,.0f}")
                with model_cols[2]:
                    diff = analysis['predicted_diff']
                    color = "normal" if diff >= 0 else "inverse"
                    st.metric("Diff", f"{diff:+,.0f}", delta_color=color)

                if analysis['predicted_diff'] > analysis['ktc_diff']:
                    st.success("Model sees more upside than market")
                elif analysis['predicted_diff'] < analysis['ktc_diff']:
                    st.warning("Model sees more risk than market")

        # --------------------------------------------------------------------------
        # TAB 2: AGE ANALYSIS
        # --------------------------------------------------------------------------
        with tab2:
            age_cols = st.columns([1.5, 1])

            with age_cols[0]:
                fig = create_age_curve_chart(give_players, get_players)
                st.plotly_chart(fig, use_container_width=True)

            with age_cols[1]:
                st.markdown("### Age Summary")

                st.metric("Avg Age (Give)", f"{analysis['give_avg_age']:.1f}")
                st.metric("Avg Age (Get)", f"{analysis['get_avg_age']:.1f}")

                age_diff = analysis['get_avg_age'] - analysis['give_avg_age']
                if age_diff < -2:
                    st.success(f"Getting {abs(age_diff):.1f} years younger on average")
                elif age_diff > 2:
                    st.warning(f"Getting {age_diff:.1f} years older on average")
                else:
                    st.info("Age neutral trade")

                st.markdown("---")

                st.markdown("### Productive Years")
                st.metric("Give Total", f"{analysis['give_years']} years")
                st.metric("Get Total", f"{analysis['get_years']} years")

                years_diff = analysis['get_years'] - analysis['give_years']
                if years_diff > 0:
                    st.success(f"Gaining {years_diff} expected productive years")
                elif years_diff < 0:
                    st.warning(f"Losing {abs(years_diff)} expected productive years")

        # --------------------------------------------------------------------------
        # TAB 3: FACTOR BREAKDOWN
        # --------------------------------------------------------------------------
        with tab3:
            st.markdown("### What's Driving the Recommendation?")

            if analysis['score_factors']:
                fig = create_factor_breakdown_chart(analysis['score_factors'])
                if fig:
                    st.plotly_chart(fig, use_container_width=True)

                st.markdown("### Factor Details")
                for name, value, description in analysis['score_factors']:
                    icon = "+" if value > 0 else "-"
                    color = COLORS['success'] if value > 0 else COLORS['danger']
                    st.markdown(
                        f"**{name}** ({value:+.1f}): {description}",
                    )
            else:
                st.info("Trade is relatively balanced across all factors")

            # Warnings
            st.markdown("---")
            st.markdown("### Warnings")
            warnings = []

            if analysis['give_buy_signals'] > 0:
                warnings.append(f"You're giving up {analysis['give_buy_signals']} player(s) with BUY signals")
            if analysis['get_sell_signals'] > 0:
                warnings.append(f"You're acquiring {analysis['get_sell_signals']} player(s) with SELL signals")
            if analysis['get_risk'] > analysis['give_risk'] + 10:
                warnings.append("Injury risk increasing significantly")
            if analysis['get_fpts'] < analysis['give_fpts'] * 0.7:
                warnings.append("Significant drop in current production")

            if warnings:
                for w in warnings:
                    st.warning(w)
            else:
                st.success("No major warnings")

        # --------------------------------------------------------------------------
        # TAB 4: PLAYER DETAILS
        # --------------------------------------------------------------------------
        with tab4:
            detail_cols = st.columns(2)

            with detail_cols[0]:
                st.markdown("### Players You're Giving")
                for p in give_players:
                    with st.expander(f"{p['name']} ({p['position']})"):
                        conf, conf_factors = calculate_confidence(p)

                        st.markdown(f"**Team:** {p.get('team', 'FA')}")
                        st.markdown(f"**Age:** {p.get('age', '?')}")
                        st.markdown(f"**KTC Value:** {p.get('ktc_value', 0):,}")

                        predicted = p.get('predicted_value')
                        if predicted:
                            delta = p.get('value_delta', 0) or 0
                            st.markdown(f"**Model Value:** {predicted:,.0f} ({delta:+,.0f})")

                        st.markdown(f"**Signal:** {p.get('signal', 'HOLD')}")
                        st.markdown(f"**Prediction Confidence:** {conf}%")

                        if p.get('fpts'):
                            st.markdown(f"**Fantasy Points:** {p['fpts']:.1f}")
                        if p.get('snap_pct'):
                            st.markdown(f"**Snap %:** {p['snap_pct']:.1f}%")

            with detail_cols[1]:
                st.markdown("### Players You're Getting")
                for p in get_players:
                    with st.expander(f"{p['name']} ({p['position']})"):
                        conf, conf_factors = calculate_confidence(p)

                        st.markdown(f"**Team:** {p.get('team', 'FA')}")
                        st.markdown(f"**Age:** {p.get('age', '?')}")
                        st.markdown(f"**KTC Value:** {p.get('ktc_value', 0):,}")

                        predicted = p.get('predicted_value')
                        if predicted:
                            delta = p.get('value_delta', 0) or 0
                            st.markdown(f"**Model Value:** {predicted:,.0f} ({delta:+,.0f})")

                        st.markdown(f"**Signal:** {p.get('signal', 'HOLD')}")
                        st.markdown(f"**Prediction Confidence:** {conf}%")

                        if p.get('fpts'):
                            st.markdown(f"**Fantasy Points:** {p['fpts']:.1f}")
                        if p.get('snap_pct'):
                            st.markdown(f"**Snap %:** {p['snap_pct']:.1f}%")

    else:
        # Empty state
        st.info("Select players on both sides to analyze the trade")

        st.markdown("""
        ### How It Works

        1. **Select players** you're giving and getting
        2. **Instant analysis** compares:
           - Market value (KTC) vs Model predictions
           - Age curves and productive years remaining
           - Buy/Sell signals for each player
           - Production and injury risk

        3. **Trade Score** indicates who wins:
           - **Positive** = trade favors you
           - **Negative** = trade favors them
           - **Near zero** = fair trade

        *Powered by Thoth's ML model trained on 40+ features*
        """)


if __name__ == "__main__":
    main()
