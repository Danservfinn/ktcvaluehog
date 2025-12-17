"""
Thoth - Dynasty Fantasy Football Intelligence
==============================================
Main entry point for the Thoth analytics platform.
"""

import streamlit as st
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.components.design_system import (
    COLORS, apply_thoth_style, render_thoth_header,
    render_thoth_footer, get_signal_badge, SIGNAL_COLORS
)

# Page config
st.set_page_config(
    page_title="Thoth - Dynasty Intelligence",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply Thoth styling
apply_thoth_style()


@st.cache_resource
def get_neo4j_driver():
    """Get Neo4j driver from session state or create new."""
    from neo4j import GraphDatabase
    uri = st.secrets.get("neo4j_uri", "bolt://localhost:7687")
    auth = None
    if "neo4j_user" in st.secrets and "neo4j_password" in st.secrets:
        auth = (st.secrets["neo4j_user"], st.secrets["neo4j_password"])
    return GraphDatabase.driver(uri, auth=auth)


def main():
    """Main dashboard page."""
    render_thoth_header("Thoth", "Dynasty Fantasy Football Intelligence")

    # Sidebar navigation
    with st.sidebar:
        st.markdown("### Navigation")
        st.markdown("""
        **Analytics**
        - 🔍 Player Intelligence
        - 📈 Dynasty Edge Scores
        - 🔄 Trade Analyzer

        **League Tools**
        - 🏆 League Analysis
        - 📉 Market Trends

        **Advanced**
        - 🧬 Graph Explorer
        - 💬 AI Assistant
        - 🧠 Model Insights
        - 🏃 Athletic Profiles
        - 💰 Contract Intel
        """)

        st.markdown("---")
        st.markdown("### Model Info")
        st.markdown("""
        <span class="model-stat">R² = 0.84</span>
        <span class="model-stat">3,700+ Players</span>
        """, unsafe_allow_html=True)

    # Quick stats
    try:
        driver = get_neo4j_driver()
        with driver.session() as session:
            # Get counts
            result = session.run("""
                MATCH (p:Player)
                WHERE p.position IN ['QB', 'RB', 'WR', 'TE']
                WITH count(p) as total_players,
                     count(CASE WHEN p.edge_signal = 'BUY' OR p.edge_signal = 'STRONG_BUY' THEN 1 END) as buy_signals,
                     count(CASE WHEN p.edge_signal = 'SELL' OR p.edge_signal = 'STRONG_SELL' THEN 1 END) as sell_signals
                MATCH (t:Team)
                WITH total_players, buy_signals, sell_signals, count(t) as teams
                RETURN total_players, buy_signals, sell_signals, teams
            """)
            record = result.single()

            if record:
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Players Tracked", f"{record['total_players']:,}")
                with col2:
                    st.metric("NFL Teams", record['teams'])
                with col3:
                    st.metric("Buy Signals", record['buy_signals'], delta="opportunities")
                with col4:
                    st.metric("Sell Signals", record['sell_signals'], delta="alerts", delta_color="inverse")
    except Exception as e:
        st.warning(f"Could not connect to Neo4j: {e}")
        st.info("Make sure Neo4j is running on localhost:7687")

    st.divider()

    # Top Dynasty Edge Opportunities
    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<h3 class="section-header">Top Buy Opportunities</h3>', unsafe_allow_html=True)

        try:
            driver = get_neo4j_driver()
            with driver.session() as session:
                buy_result = session.run("""
                    MATCH (p:Player)
                    WHERE p.edge_signal IN ['BUY', 'STRONG_BUY']
                      AND p.ktc_value > 1000
                    RETURN p.name as player,
                           p.position as position,
                           p.current_team as team,
                           p.ktc_value as ktc_value,
                           p.predicted_ktc_value as predicted,
                           p.value_delta as delta,
                           p.edge_signal as signal,
                           p.age as age
                    ORDER BY p.value_delta DESC
                    LIMIT 8
                """)
                buys = [dict(r) for r in buy_result]

                if buys:
                    for player in buys:
                        signal_badge = get_signal_badge(player['signal'])
                        delta = player.get('delta', 0) or 0
                        predicted = player.get('predicted', player['ktc_value']) or player['ktc_value']

                        st.markdown(f"""
                        <div class="player-card">
                            <div style="display: flex; justify-content: space-between; align-items: start;">
                                <div>
                                    <span class="player-name">{player['player']}</span>
                                    <span class="player-meta"> ({player['position']}, {player.get('team', 'FA')}) - Age {player.get('age', '?')}</span>
                                </div>
                                {signal_badge}
                            </div>
                            <div style="margin-top: 0.5rem; font-size: 0.875rem;">
                                KTC: {player['ktc_value']:,} | Model: {predicted:,.0f} |
                                <span class="value-positive">+{delta:,.0f}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.info("No buy signals found. Run the pipeline first.")

        except Exception as e:
            st.error(f"Error loading buy signals: {e}")

    with col2:
        st.markdown('<h3 class="section-header">Top Sell Candidates</h3>', unsafe_allow_html=True)

        try:
            driver = get_neo4j_driver()
            with driver.session() as session:
                sell_result = session.run("""
                    MATCH (p:Player)
                    WHERE p.edge_signal IN ['SELL', 'STRONG_SELL']
                      AND p.ktc_value > 1000
                    RETURN p.name as player,
                           p.position as position,
                           p.current_team as team,
                           p.ktc_value as ktc_value,
                           p.predicted_ktc_value as predicted,
                           p.value_delta as delta,
                           p.edge_signal as signal,
                           p.age as age
                    ORDER BY p.value_delta ASC
                    LIMIT 8
                """)
                sells = [dict(r) for r in sell_result]

                if sells:
                    for player in sells:
                        signal_badge = get_signal_badge(player['signal'])
                        delta = player.get('delta', 0) or 0
                        predicted = player.get('predicted', player['ktc_value']) or player['ktc_value']

                        st.markdown(f"""
                        <div class="player-card">
                            <div style="display: flex; justify-content: space-between; align-items: start;">
                                <div>
                                    <span class="player-name">{player['player']}</span>
                                    <span class="player-meta"> ({player['position']}, {player.get('team', 'FA')}) - Age {player.get('age', '?')}</span>
                                </div>
                                {signal_badge}
                            </div>
                            <div style="margin-top: 0.5rem; font-size: 0.875rem;">
                                KTC: {player['ktc_value']:,} | Model: {predicted:,.0f} |
                                <span class="value-negative">{delta:,.0f}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.info("No sell signals found. Run the pipeline first.")

        except Exception as e:
            st.error(f"Error loading sell signals: {e}")

    st.divider()

    # Quick Start Guide
    st.markdown('<h3 class="section-header">Quick Start</h3>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        **Player Analysis**

        Search any player to see:
        - ML-predicted value vs market
        - Athletic profile & combine data
        - Contract details & situation
        - Historical value trends
        """)

    with col2:
        st.markdown("""
        **Trade Analysis**

        Evaluate trades with:
        - Side-by-side comparisons
        - Age curve analysis
        - Factor-by-factor breakdown
        - ML confidence scoring
        """)

    with col3:
        st.markdown("""
        **AI Assistant**

        Ask Thoth anything:
        - "Who should I buy at WR?"
        - "Compare Chase and Lamb"
        - "Why is X a sell?"
        - "Find undervalued athletes"
        """)

    st.divider()

    # System Status
    with st.expander("System Status & Data Sources"):
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### Pipeline Status")
            st.markdown("""
            - **Daily Refresh**: Updates KTC values and signals
            - **Weekly Retrain**: Retrains ML model with new data
            - **Temporal Tracking**: Monitors value changes over time
            """)

        with col2:
            st.markdown("#### Data Sources")
            st.markdown("""
            - **NFLverse**: Player stats, combine, contracts, injuries
            - **KeepTradeCut**: Dynasty player valuations
            - **ML Model**: H2O AutoML GBM (R²=0.84)
            """)

    # Footer
    render_thoth_footer()


if __name__ == "__main__":
    main()
