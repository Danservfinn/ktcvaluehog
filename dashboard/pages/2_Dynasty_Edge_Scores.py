"""
Thoth - Dynasty Edge Scores
============================
View all players ranked by Dynasty Edge Score with filtering.
"""

import streamlit as st
import pandas as pd
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.components.design_system import (
    apply_thoth_style, render_thoth_header, render_thoth_footer,
    get_signal_badge, COLORS, SIGNAL_COLORS
)

st.set_page_config(page_title="Dynasty Edge Scores - Thoth", page_icon="🔮", layout="wide")
apply_thoth_style()


@st.cache_resource
def get_driver():
    """Get Neo4j driver."""
    from neo4j import GraphDatabase
    uri = st.secrets.get("neo4j_uri", "bolt://localhost:7687")
    return GraphDatabase.driver(uri, auth=None)


@st.cache_data(ttl=300)
def get_dynasty_edge_scores(position: str = None, signal: str = None,
                            min_ktc: int = 0, max_ktc: int = 99999):
    """Get Dynasty Edge scores with filters."""
    driver = get_driver()

    position_filter = "AND p.position = $position" if position else ""
    signal_filter = "AND p.edge_signal = $signal" if signal else ""

    with driver.session() as session:
        result = session.run(f"""
            MATCH (p:Player)
            WHERE p.position IN ['QB', 'RB', 'WR', 'TE']
              AND p.ktc_value >= $min_ktc
              AND p.ktc_value <= $max_ktc
              AND (p.predicted_ktc_value IS NOT NULL OR p.dynasty_edge_score IS NOT NULL)
              {position_filter}
              {signal_filter}
            RETURN p.name as name,
                   p.position as position,
                   p.age as age,
                   p.current_team as team,
                   p.ktc_value as ktc_value,
                   COALESCE(p.predicted_ktc_value, p.dynasty_edge_score) as model_value,
                   COALESCE(p.value_delta, p.edge_delta) as delta,
                   COALESCE(p.value_delta_pct, (p.dynasty_edge_score - p.ktc_value) * 100.0 / p.ktc_value) as edge_pct,
                   p.edge_signal as signal
            ORDER BY
                CASE
                    WHEN p.edge_signal = 'STRONG_BUY' THEN 1
                    WHEN p.edge_signal = 'BUY' THEN 2
                    WHEN p.edge_signal = 'HOLD' THEN 3
                    WHEN p.edge_signal = 'SELL' THEN 4
                    WHEN p.edge_signal = 'STRONG_SELL' THEN 5
                END,
                COALESCE(p.value_delta, p.edge_delta) DESC
        """, {
            'position': position,
            'signal': signal,
            'min_ktc': min_ktc,
            'max_ktc': max_ktc
        })
        return pd.DataFrame([dict(r) for r in result])


def main():
    render_thoth_header("Dynasty Edge Scores", "All players ranked by ML-predicted value edge")

    # Filters in sidebar
    with st.sidebar:
        st.markdown("### Filters")

        position = st.selectbox(
            "Position",
            ["All", "QB", "RB", "WR", "TE"]
        )

        signal = st.selectbox(
            "Signal",
            ["All", "STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL"]
        )

        ktc_range = st.slider(
            "KTC Value Range",
            min_value=0,
            max_value=10000,
            value=(1000, 10000),
            step=100
        )

        st.markdown("---")
        st.markdown("### Signal Guide")
        for sig, colors in SIGNAL_COLORS.items():
            st.markdown(f"{colors['emoji']} **{sig}**: {'+15%' if 'STRONG_BUY' in sig else '+7-15%' if 'BUY' in sig else '-7% to +7%' if 'HOLD' in sig else '-7% to -15%' if 'SELL' == sig else '<-15%'}")

    # Get data
    pos_filter = None if position == "All" else position
    sig_filter = None if signal == "All" else signal

    df = get_dynasty_edge_scores(
        position=pos_filter,
        signal=sig_filter,
        min_ktc=ktc_range[0],
        max_ktc=ktc_range[1]
    )

    if not df.empty:
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Players", len(df))
        with col2:
            buys = len(df[df['signal'].isin(['BUY', 'STRONG_BUY'])])
            st.metric("Buy Signals", buys)
        with col3:
            sells = len(df[df['signal'].isin(['SELL', 'STRONG_SELL'])])
            st.metric("Sell Signals", sells)
        with col4:
            avg_edge = df['edge_pct'].mean() if 'edge_pct' in df.columns else 0
            st.metric("Avg Edge %", f"{avg_edge:.1f}%")

        st.divider()

        # Style the dataframe
        def color_signal(val):
            if val in ['BUY', 'STRONG_BUY']:
                return f'background-color: {SIGNAL_COLORS["BUY"]["bg"]}; color: {SIGNAL_COLORS["BUY"]["text"]}'
            elif val in ['SELL', 'STRONG_SELL']:
                return f'background-color: {SIGNAL_COLORS["SELL"]["bg"]}; color: {SIGNAL_COLORS["SELL"]["text"]}'
            return f'background-color: {SIGNAL_COLORS["HOLD"]["bg"]}; color: {SIGNAL_COLORS["HOLD"]["text"]}'

        def color_delta(val):
            if pd.isna(val):
                return ''
            if val > 0:
                return f'color: {COLORS["success"]}'
            elif val < 0:
                return f'color: {COLORS["danger"]}'
            return ''

        # Prepare display dataframe
        display_df = df.copy()
        display_df = display_df.rename(columns={
            'name': 'Player',
            'position': 'Pos',
            'team': 'Team',
            'age': 'Age',
            'ktc_value': 'KTC Value',
            'model_value': 'Model Value',
            'delta': 'Gap',
            'edge_pct': 'Edge %',
            'signal': 'Signal'
        })

        # Display dataframe
        st.dataframe(
            display_df.style.applymap(color_signal, subset=['Signal'])
                    .applymap(color_delta, subset=['Gap', 'Edge %'])
                    .format({
                        'KTC Value': '{:,.0f}',
                        'Model Value': '{:,.0f}',
                        'Gap': '{:+,.0f}',
                        'Edge %': '{:+.1f}%'
                    }),
            use_container_width=True,
            height=600
        )

        # Download button
        csv = df.to_csv(index=False)
        st.download_button(
            "Download CSV",
            csv,
            "thoth_edge_scores.csv",
            "text/csv"
        )

        st.divider()

        # Visualizations
        col1, col2 = st.columns(2)

        with col1:
            st.markdown('<h3 class="section-header">Signal Distribution</h3>', unsafe_allow_html=True)
            signal_counts = df['signal'].value_counts()

            import plotly.express as px
            fig = px.pie(
                values=signal_counts.values,
                names=signal_counts.index,
                color=signal_counts.index,
                color_discrete_map={
                    'STRONG_BUY': COLORS['success'],
                    'BUY': '#34D399',
                    'HOLD': COLORS['neutral'],
                    'SELL': COLORS['warning'],
                    'STRONG_SELL': COLORS['danger']
                }
            )
            fig.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.markdown('<h3 class="section-header">Avg Edge % by Position</h3>', unsafe_allow_html=True)
            if not df.empty and 'position' in df.columns:
                pos_avg = df.groupby('position')['edge_pct'].mean().sort_values(ascending=False)

                fig = px.bar(
                    x=pos_avg.index,
                    y=pos_avg.values,
                    color=pos_avg.values,
                    color_continuous_scale=['#EF4444', '#F59E0B', '#6B7280', '#34D399', '#10B981']
                )
                fig.update_layout(
                    showlegend=False,
                    xaxis_title="Position",
                    yaxis_title="Avg Edge %",
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)'
                )
                fig.update_coloraxes(showscale=False)
                st.plotly_chart(fig, use_container_width=True)

    else:
        st.info("No data found. Run the pipeline to generate Dynasty Edge scores.")

    render_thoth_footer()


if __name__ == "__main__":
    main()
