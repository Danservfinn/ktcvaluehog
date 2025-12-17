"""
Thoth - League Analysis
========================
Analyze your Sleeper dynasty league with Thoth insights.
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

st.set_page_config(page_title="League Analysis - Thoth", page_icon="🔮", layout="wide")
apply_thoth_style()


def get_sleeper_client(league_id: str):
    """Get Sleeper client for league."""
    try:
        from src.api.sleeper_client import SleeperClient
        return SleeperClient(league_id)
    except Exception as e:
        st.error(f"Error initializing Sleeper client: {e}")
        return None


@st.cache_resource
def get_driver():
    """Get Neo4j driver."""
    from neo4j import GraphDatabase
    uri = st.secrets.get("neo4j_uri", "bolt://localhost:7687")
    return GraphDatabase.driver(uri, auth=None)


def enrich_roster_with_edge(roster_df: pd.DataFrame) -> pd.DataFrame:
    """Add Dynasty Edge scores to roster data."""
    driver = get_driver()

    with driver.session() as session:
        result = session.run("""
            MATCH (p:Player)
            WHERE p.position IN ['QB', 'RB', 'WR', 'TE']
            RETURN p.name as name,
                   p.ktc_value as ktc_value,
                   COALESCE(p.predicted_ktc_value, p.dynasty_edge_score) as model_value,
                   p.edge_signal as signal
        """)
        edge_df = pd.DataFrame([dict(r) for r in result])

    if edge_df.empty:
        return roster_df

    def find_edge_data(player_name):
        if not player_name:
            return None, None, None
        matches = edge_df[edge_df['name'].str.lower().str.contains(player_name.lower().split()[0])]
        if not matches.empty:
            match = matches.iloc[0]
            return match.get('ktc_value'), match.get('model_value'), match.get('signal')
        return None, None, None

    roster_df['ktc_value'] = roster_df['player_name'].apply(lambda x: find_edge_data(x)[0])
    roster_df['model_value'] = roster_df['player_name'].apply(lambda x: find_edge_data(x)[1])
    roster_df['edge_signal'] = roster_df['player_name'].apply(lambda x: find_edge_data(x)[2])

    return roster_df


def main():
    render_thoth_header("League Analysis", "Analyze your Sleeper dynasty league")

    # League ID input
    league_id = st.text_input(
        "Enter Sleeper League ID",
        placeholder="123456789012345678",
        help="Find your league ID in your Sleeper league URL"
    )

    if league_id:
        client = get_sleeper_client(league_id)

        if client:
            try:
                # Get league info
                league = client.get_league()
                st.success(f"Connected to: **{league.get('name', 'Unknown League')}**")

                # League settings
                with st.expander("League Settings"):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Rosters", league.get('total_rosters', 0))
                    with col2:
                        st.metric("Season", league.get('season', 'N/A'))
                    with col3:
                        st.metric("Status", league.get('status', 'N/A'))

                st.divider()

                # Standings
                st.markdown('<h3 class="section-header">League Standings</h3>', unsafe_allow_html=True)
                summary = client.get_league_summary()
                standings = summary.get('standings', [])

                if standings:
                    standings_df = pd.DataFrame(standings)
                    standings_df['win_pct'] = standings_df['wins'] / (standings_df['wins'] + standings_df['losses'] + 0.001)
                    standings_df = standings_df.sort_values('win_pct', ascending=False)
                    st.dataframe(standings_df[['owner', 'team_name', 'wins', 'losses', 'fpts']],
                               use_container_width=True)

                st.divider()

                # Roster Analysis
                st.markdown('<h3 class="section-header">Roster Analysis</h3>', unsafe_allow_html=True)

                rosters_df = client.rosters_to_dataframe()

                if not rosters_df.empty:
                    rosters_df = enrich_roster_with_edge(rosters_df)

                    # Team selector
                    teams = rosters_df['owner'].unique().tolist()
                    selected_team = st.selectbox("Select Team", teams)

                    if selected_team:
                        team_roster = rosters_df[rosters_df['owner'] == selected_team]

                        # Calculate team totals
                        team_ktc = team_roster['ktc_value'].sum()
                        team_model = team_roster['model_value'].sum()

                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Total KTC Value", f"{team_ktc:,.0f}" if pd.notna(team_ktc) else "N/A")
                        with col2:
                            st.metric("Total Model Value", f"{team_model:,.0f}" if pd.notna(team_model) else "N/A")
                        with col3:
                            if pd.notna(team_ktc) and pd.notna(team_model):
                                diff = team_model - team_ktc
                                st.metric("Value Edge", f"{diff:+,.0f}")

                        # Roster by position
                        st.markdown("#### Roster Breakdown")

                        for pos in ['QB', 'RB', 'WR', 'TE']:
                            pos_players = team_roster[team_roster['position'] == pos]
                            if not pos_players.empty:
                                st.markdown(f"**{pos}s**")
                                for _, player in pos_players.iterrows():
                                    signal = player.get('edge_signal', '')
                                    signal_info = SIGNAL_COLORS.get(signal, SIGNAL_COLORS['HOLD'])
                                    ktc = f"{player['ktc_value']:,.0f}" if pd.notna(player.get('ktc_value')) else "?"
                                    model = f"{player['model_value']:,.0f}" if pd.notna(player.get('model_value')) else "?"
                                    st.markdown(f"- {signal_info['emoji']} {player['player_name']} - KTC: {ktc} | Model: {model}")

                        # Recommendations
                        st.markdown("#### Thoth Recommendations")
                        buys = team_roster[team_roster['edge_signal'].isin(['BUY', 'STRONG_BUY'])]
                        sells = team_roster[team_roster['edge_signal'].isin(['SELL', 'STRONG_SELL'])]

                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown("**Hold These (Buy Signals):**")
                            if not buys.empty:
                                for _, p in buys.iterrows():
                                    st.markdown(f"- {SIGNAL_COLORS['BUY']['emoji']} {p['player_name']}")
                            else:
                                st.markdown("*No buy signals on roster*")
                        with col2:
                            st.markdown("**Consider Trading (Sell Signals):**")
                            if not sells.empty:
                                for _, p in sells.iterrows():
                                    st.markdown(f"- {SIGNAL_COLORS['SELL']['emoji']} {p['player_name']}")
                            else:
                                st.markdown("*No sell signals on roster*")

                st.divider()

                # Trending players
                st.markdown('<h3 class="section-header">Trending Players</h3>', unsafe_allow_html=True)
                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("**Hot Adds (24h)**")
                    try:
                        trending_adds = client.get_trending_players(type='add', hours=24, limit=10)
                        for player in trending_adds[:10]:
                            st.markdown(f"- {player.get('player_id', 'Unknown')} (+{player.get('count', 0)})")
                    except:
                        st.info("Trending data unavailable")

                with col2:
                    st.markdown("**Hot Drops (24h)**")
                    try:
                        trending_drops = client.get_trending_players(type='drop', hours=24, limit=10)
                        for player in trending_drops[:10]:
                            st.markdown(f"- {player.get('player_id', 'Unknown')} ({player.get('count', 0)})")
                    except:
                        st.info("Trending data unavailable")

            except Exception as e:
                st.error(f"Error loading league data: {e}")
                st.info("Make sure the league ID is correct and the league is public.")
    else:
        st.info("Enter your Sleeper league ID to analyze your league.")

        st.markdown("""
        ### How to find your League ID:
        1. Open your Sleeper app or go to sleeper.app
        2. Navigate to your league
        3. The league ID is in the URL: `sleeper.app/leagues/[LEAGUE_ID]`
        """)

    render_thoth_footer()


if __name__ == "__main__":
    main()
