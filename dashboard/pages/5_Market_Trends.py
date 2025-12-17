"""
Thoth - Market Trends
======================
Track market momentum and value changes over time.
"""

import streamlit as st
import pandas as pd
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.components.design_system import (
    apply_thoth_style, render_thoth_header, render_thoth_footer,
    COLORS, SIGNAL_COLORS
)

st.set_page_config(page_title="Market Trends - Thoth", page_icon="🔮", layout="wide")
apply_thoth_style()


@st.cache_resource
def get_driver():
    """Get Neo4j driver."""
    from neo4j import GraphDatabase
    uri = st.secrets.get("neo4j_uri", "bolt://localhost:7687")
    return GraphDatabase.driver(uri, auth=None)


@st.cache_data(ttl=300)
def get_biggest_movers(days: int = 7, direction: str = 'up'):
    """Get biggest value movers."""
    driver = get_driver()

    order = "DESC" if direction == 'up' else "ASC"

    with driver.session() as session:
        result = session.run(f"""
            MATCH (p:Player)-[:HAD_SNAPSHOT]->(s1:Snapshot)
            MATCH (p)-[:HAD_SNAPSHOT]->(s2:Snapshot)
            WHERE s1.date < s2.date
              AND s2.date >= date() - duration({{days: $days}})
              AND p.position IN ['QB', 'RB', 'WR', 'TE']
              AND p.ktc_value > 1000
            WITH p, s1, s2
            ORDER BY s1.date ASC
            WITH p, head(collect(s1)) as oldest, last(collect(s2)) as newest
            WHERE oldest IS NOT NULL AND newest IS NOT NULL
            WITH p,
                 oldest.ktc_value as start_value,
                 newest.ktc_value as end_value,
                 newest.ktc_value - oldest.ktc_value as absolute_change,
                 (newest.ktc_value - oldest.ktc_value) * 100.0 / oldest.ktc_value as pct_change
            WHERE ABS(absolute_change) > 50
            RETURN p.name as name,
                   p.position as position,
                   p.current_team as team,
                   p.age as age,
                   start_value,
                   end_value,
                   absolute_change,
                   pct_change
            ORDER BY pct_change {order}
            LIMIT 20
        """, {'days': days})
        return pd.DataFrame([dict(r) for r in result])


@st.cache_data(ttl=300)
def get_market_momentum():
    """Get overall market momentum indicators."""
    driver = get_driver()

    with driver.session() as session:
        result = session.run("""
            MATCH (p:Player)
            WHERE p.position IN ['QB', 'RB', 'WR', 'TE']
              AND p.ktc_value > 1000
            WITH p.position as position,
                 avg(p.ktc_value) as avg_value,
                 count(CASE WHEN p.edge_signal IN ['BUY', 'STRONG_BUY'] THEN 1 END) as buy_signals,
                 count(CASE WHEN p.edge_signal IN ['SELL', 'STRONG_SELL'] THEN 1 END) as sell_signals,
                 count(p) as total
            RETURN position, avg_value, buy_signals, sell_signals, total,
                   toFloat(buy_signals) / total as buy_pct,
                   toFloat(sell_signals) / total as sell_pct
            ORDER BY position
        """)
        return pd.DataFrame([dict(r) for r in result])


@st.cache_data(ttl=3600)
def get_correlation_insights():
    """Get discovered correlations from temporal tracking."""
    driver = get_driver()

    with driver.session() as session:
        result = session.run("""
            MATCH (c:Correlation)
            WHERE c.confidence IN ['High', 'Medium']
            RETURN c.metric_name as metric,
                   c.position as position,
                   c.pearson_r as correlation,
                   c.strength as strength,
                   c.direction as direction,
                   c.confidence as confidence,
                   c.sample_size as samples
            ORDER BY ABS(c.pearson_r) DESC
        """)
        return pd.DataFrame([dict(r) for r in result])


@st.cache_data(ttl=3600)
def get_value_distribution():
    """Get KTC value distribution by position."""
    driver = get_driver()

    with driver.session() as session:
        result = session.run("""
            MATCH (p:Player)
            WHERE p.position IN ['QB', 'RB', 'WR', 'TE']
              AND p.ktc_value > 500
            WITH p.position as position,
                 CASE
                     WHEN p.ktc_value > 7000 THEN 'Elite (7000+)'
                     WHEN p.ktc_value > 4500 THEN 'Tier 1 (4500-7000)'
                     WHEN p.ktc_value > 2500 THEN 'Tier 2 (2500-4500)'
                     WHEN p.ktc_value > 1000 THEN 'Tier 3 (1000-2500)'
                     ELSE 'Depth (<1000)'
                 END as tier,
                 count(*) as count
            RETURN position, tier, count
            ORDER BY position, tier
        """)
        return pd.DataFrame([dict(r) for r in result])


def main():
    render_thoth_header("Market Trends", "Track market momentum and value changes")

    # Market momentum overview
    st.markdown('<h3 class="section-header">Market Momentum by Position</h3>', unsafe_allow_html=True)
    momentum_df = get_market_momentum()

    if not momentum_df.empty:
        col1, col2, col3, col4 = st.columns(4)

        for i, pos in enumerate(['QB', 'RB', 'WR', 'TE']):
            pos_data = momentum_df[momentum_df['position'] == pos]
            if not pos_data.empty:
                row = pos_data.iloc[0]
                with [col1, col2, col3, col4][i]:
                    st.markdown(f"**{pos}**")
                    st.metric("Avg Value", f"{row['avg_value']:,.0f}")
                    buy_pct = row['buy_pct'] * 100
                    sell_pct = row['sell_pct'] * 100

                    if buy_pct > sell_pct * 1.5:
                        st.markdown(f"<span class='value-positive'>{SIGNAL_COLORS['BUY']['emoji']} {row['buy_signals']} buys</span>", unsafe_allow_html=True)
                    elif sell_pct > buy_pct * 1.5:
                        st.markdown(f"<span class='value-negative'>{SIGNAL_COLORS['SELL']['emoji']} {row['sell_signals']} sells</span>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"{SIGNAL_COLORS['HOLD']['emoji']} Balanced")

    st.divider()

    # Biggest movers
    st.markdown('<h3 class="section-header">Biggest Value Movers</h3>', unsafe_allow_html=True)

    timeframe = st.selectbox("Timeframe", [7, 14, 30, 60], format_func=lambda x: f"{x} days")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Risers")
        risers = get_biggest_movers(days=timeframe, direction='up')
        if not risers.empty:
            for _, row in risers.head(10).iterrows():
                st.markdown(f"""
                <div class="player-card">
                    <span class="player-name">{row['name']}</span>
                    <span class="player-meta"> ({row['position']}, {row.get('team', 'FA')})</span>
                    <div style="margin-top: 0.25rem;">
                        {row['start_value']:,.0f} → {row['end_value']:,.0f}
                        <span class="value-positive">+{row['pct_change']:.1f}%</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No significant risers. Run daily tracking to accumulate data.")

    with col2:
        st.markdown("#### Fallers")
        fallers = get_biggest_movers(days=timeframe, direction='down')
        if not fallers.empty:
            for _, row in fallers.head(10).iterrows():
                st.markdown(f"""
                <div class="player-card">
                    <span class="player-name">{row['name']}</span>
                    <span class="player-meta"> ({row['position']}, {row.get('team', 'FA')})</span>
                    <div style="margin-top: 0.25rem;">
                        {row['start_value']:,.0f} → {row['end_value']:,.0f}
                        <span class="value-negative">{row['pct_change']:.1f}%</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No significant fallers. Run daily tracking to accumulate data.")

    st.divider()

    # Value Distribution
    st.markdown('<h3 class="section-header">Value Distribution by Position</h3>', unsafe_allow_html=True)
    dist_df = get_value_distribution()

    if not dist_df.empty:
        import plotly.express as px

        # Pivot for visualization
        dist_pivot = dist_df.pivot_table(
            values='count',
            index='tier',
            columns='position',
            aggfunc='sum'
        ).fillna(0)

        # Reorder tiers
        tier_order = ['Elite (7000+)', 'Tier 1 (4500-7000)', 'Tier 2 (2500-4500)',
                     'Tier 3 (1000-2500)', 'Depth (<1000)']
        dist_pivot = dist_pivot.reindex([t for t in tier_order if t in dist_pivot.index])

        fig = px.bar(
            dist_pivot,
            barmode='group',
            color_discrete_sequence=[COLORS['primary'], COLORS['success'], COLORS['warning'], COLORS['danger']]
        )
        fig.update_layout(
            xaxis_title="Value Tier",
            yaxis_title="Player Count",
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            legend_title="Position"
        )
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Discovered Correlations
    st.markdown('<h3 class="section-header">Discovered Correlations</h3>', unsafe_allow_html=True)
    st.markdown("*Relationships between stats and KTC value changes*")

    correlations = get_correlation_insights()

    if not correlations.empty:
        st.dataframe(correlations, use_container_width=True)
    else:
        st.info("No correlations discovered yet. Run weekly retrain to discover patterns.")

    st.divider()

    # Market Insights
    st.markdown('<h3 class="section-header">Market Insights</h3>', unsafe_allow_html=True)

    if not momentum_df.empty:
        total_buys = momentum_df['buy_signals'].sum()
        total_sells = momentum_df['sell_signals'].sum()

        if total_buys > total_sells * 1.5:
            st.markdown(f"""
            <div class="success-box">
                {SIGNAL_COLORS['BUY']['emoji']} <strong>Bullish Market</strong> - More buy signals ({total_buys}) than sells ({total_sells}) across positions.
                The model sees more undervalued players than overvalued ones.
            </div>
            """, unsafe_allow_html=True)
        elif total_sells > total_buys * 1.5:
            st.markdown(f"""
            <div class="warning-box">
                {SIGNAL_COLORS['SELL']['emoji']} <strong>Bearish Market</strong> - More sell signals ({total_sells}) than buys ({total_buys}) across positions.
                Many players appear overvalued relative to fundamentals.
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="info-box">
                {SIGNAL_COLORS['HOLD']['emoji']} <strong>Neutral Market</strong> - Balanced buy ({total_buys}) and sell ({total_sells}) signals.
                Market valuations are roughly aligned with model predictions.
            </div>
            """, unsafe_allow_html=True)

        # Position-specific insights
        st.markdown("#### Position Insights")
        for _, row in momentum_df.iterrows():
            pos = row['position']
            buy_pct = row['buy_pct'] * 100
            sell_pct = row['sell_pct'] * 100

            if buy_pct > 40:
                st.markdown(f"- **{pos}**: {SIGNAL_COLORS['BUY']['emoji']} Many undervalued players ({buy_pct:.0f}% buy signals)")
            elif sell_pct > 40:
                st.markdown(f"- **{pos}**: {SIGNAL_COLORS['SELL']['emoji']} Many overvalued players ({sell_pct:.0f}% sell signals)")
            else:
                st.markdown(f"- **{pos}**: {SIGNAL_COLORS['HOLD']['emoji']} Fair valuations ({buy_pct:.0f}% buy / {sell_pct:.0f}% sell)")

    render_thoth_footer()


if __name__ == "__main__":
    main()
