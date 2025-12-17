#!/usr/bin/env python3
"""
Dynasty Edge - Comprehensive Fantasy Football Dashboard

A full-featured Streamlit dashboard for dynasty fantasy football analysis
with integrated Claude Opus 4.5 AI agent.

Run with: streamlit run dashboard.py

Features:
- Player rankings & valuations
- Trade analyzer
- Roster analysis
- Buy/Sell signals
- NFL stats integration
- AI-powered chat assistant (Claude Opus 4.5)
- One-click data refresh
"""

import os
import sys
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Try to import optional dependencies
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    import nflreadpy as nfl
    NFL_DATA_AVAILABLE = True
except ImportError:
    NFL_DATA_AVAILABLE = False

# =============================================================================
# CONFIGURATION
# =============================================================================

st.set_page_config(
    page_title="Dynasty Edge",
    page_icon="🏈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Data paths
DATA_DIR = Path("data")
PROJECT_DIR = Path("/mnt/project") if Path("/mnt/project").exists() else Path(".")
SCRIPTS_DIR = Path("scripts")

# =============================================================================
# DATA REFRESH FUNCTIONS
# =============================================================================

def refresh_nfl_data():
    """Refresh NFL data from nflverse."""
    if not NFL_DATA_AVAILABLE:
        return False, "nflreadpy not installed"
    
    try:
        # Ensure data directory exists
        (DATA_DIR / "nfl").mkdir(parents=True, exist_ok=True)
        
        # Fetch weekly stats
        stats = nfl.load_player_stats([2024], summary_level='week').to_pandas()
        stats = stats[stats['position'].isin(['QB', 'RB', 'WR', 'TE'])]
        stats.to_csv(DATA_DIR / "nfl" / "weekly_stats.csv", index=False)
        
        # Fetch rosters
        rosters = nfl.load_rosters([2024]).to_pandas()
        rosters.to_csv(DATA_DIR / "nfl" / "rosters.csv", index=False)
        
        # Fetch player IDs
        players = nfl.load_players().to_pandas()
        players.to_csv(DATA_DIR / "nfl" / "player_ids.csv", index=False)
        
        # Save metadata
        metadata = {
            'last_updated': datetime.utcnow().isoformat(),
            'season': 2024,
            'source': 'nflverse/nflreadpy'
        }
        with open(DATA_DIR / "nfl" / "metadata.json", 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return True, f"Updated {len(stats)} weekly stat records"
    except Exception as e:
        return False, str(e)

def refresh_sleeper_data():
    """Refresh Sleeper league data."""
    import requests
    
    league_id = os.environ.get("SLEEPER_LEAGUE_ID", "1180199027998867456")
    base_url = "https://api.sleeper.app/v1"
    
    try:
        (DATA_DIR / "sleeper").mkdir(parents=True, exist_ok=True)
        
        # Fetch league info
        resp = requests.get(f"{base_url}/league/{league_id}", timeout=30)
        league = resp.json()
        with open(DATA_DIR / "sleeper" / "league_info.json", 'w') as f:
            json.dump(league, f, indent=2)
        
        # Fetch users
        resp = requests.get(f"{base_url}/league/{league_id}/users", timeout=30)
        users = resp.json()
        users_df = pd.DataFrame([{
            'user_id': u.get('user_id'),
            'display_name': u.get('display_name'),
            'team_name': u.get('metadata', {}).get('team_name', u.get('display_name'))
        } for u in users])
        users_df.to_csv(DATA_DIR / "sleeper" / "users.csv", index=False)
        
        # Fetch rosters
        resp = requests.get(f"{base_url}/league/{league_id}/rosters", timeout=30)
        rosters = resp.json()
        with open(DATA_DIR / "sleeper" / "rosters.json", 'w') as f:
            json.dump(rosters, f, indent=2)
        
        # Fetch traded picks
        resp = requests.get(f"{base_url}/league/{league_id}/traded_picks", timeout=30)
        picks = resp.json()
        picks_df = pd.DataFrame(picks)
        picks_df.to_csv(DATA_DIR / "sleeper" / "traded_picks.csv", index=False)
        
        # Fetch all players
        resp = requests.get(f"{base_url}/players/nfl", timeout=60)
        players = resp.json()
        players_list = [{
            'sleeper_id': pid,
            'name': p.get('full_name', ''),
            'position': p.get('position'),
            'team': p.get('team'),
            'age': p.get('age')
        } for pid, p in players.items() if p.get('position') in ['QB', 'RB', 'WR', 'TE', 'K', 'DEF']]
        pd.DataFrame(players_list).to_csv(DATA_DIR / "sleeper" / "players.csv", index=False)
        
        # Save metadata
        metadata = {
            'last_updated': datetime.utcnow().isoformat(),
            'league_id': league_id,
            'league_name': league.get('name', 'Unknown')
        }
        with open(DATA_DIR / "sleeper" / "metadata.json", 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return True, f"Updated league: {league.get('name', league_id)}"
    except Exception as e:
        return False, str(e)

def refresh_ktc_data():
    """Refresh KTC values (placeholder - KTC doesn't have a public API)."""
    # KTC requires scraping which is unreliable
    # For now, return instructions
    return False, "KTC requires manual CSV upload. Download from keeptradecut.com"

def get_last_update_time(source: str) -> str:
    """Get last update time for a data source."""
    metadata_paths = {
        'nfl': DATA_DIR / "nfl" / "metadata.json",
        'sleeper': DATA_DIR / "sleeper" / "metadata.json",
        'ktc': DATA_DIR / "ktc_metadata.json"
    }
    
    path = metadata_paths.get(source)
    if path and path.exists():
        try:
            with open(path) as f:
                data = json.load(f)
                ts = data.get('last_updated', '')
                if ts:
                    dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                    return dt.strftime('%Y-%m-%d %H:%M')
        except:
            pass
    return "Never"

# =============================================================================
# DATA LOADING
# =============================================================================

@st.cache_data(ttl=3600)
def load_ktc_data() -> pd.DataFrame:
    """Load KTC player values."""
    paths = [
        DATA_DIR / "ktc_values.csv",
        PROJECT_DIR / "ktc_lucid_losers.csv",
        Path("ktc_lucid_losers.csv")
    ]
    
    for path in paths:
        if path.exists():
            df = pd.read_csv(path)
            if 'Updated' in df.columns[0] or df.columns[0].startswith('Updated'):
                df.columns = ['name', 'pos_rank', 'position', 'team', 'sf_value', 'age', 
                             'rookie', 'oneqb_rank', 'oneqb_value', 'redraft_rank', 'redraft_value']
            return df
    
    st.error("KTC data not found. Please upload ktc_values.csv to the data folder.")
    return pd.DataFrame()

@st.cache_data(ttl=3600)
def load_nfl_stats() -> pd.DataFrame:
    """Load NFL player statistics."""
    # Try local CSV first
    csv_path = DATA_DIR / "nfl" / "weekly_stats.csv"
    if csv_path.exists():
        stats = pd.read_csv(csv_path)
        stats = stats[stats['position'].isin(['QB', 'RB', 'WR', 'TE'])]
        
        agg = stats.groupby(['player_display_name', 'position']).agg({
            'targets': 'sum',
            'receptions': 'sum',
            'receiving_yards': 'sum',
            'receiving_tds': 'sum',
            'carries': 'sum',
            'rushing_yards': 'sum',
            'rushing_tds': 'sum',
            'passing_yards': 'sum',
            'passing_tds': 'sum',
            'interceptions': 'sum',
            'fantasy_points_ppr': 'sum',
            'week': 'count'
        }).reset_index()
        
        agg.columns = ['name', 'position', 'targets', 'receptions', 'rec_yards', 'rec_tds',
                      'carries', 'rush_yards', 'rush_tds', 'pass_yards', 'pass_tds', 
                      'interceptions', 'ppr_points', 'games']
        
        agg['tpg'] = (agg['targets'] / agg['games']).round(1)
        agg['ppg'] = (agg['ppr_points'] / agg['games']).round(1)
        
        return agg
    
    # Fall back to live fetch
    if not NFL_DATA_AVAILABLE:
        return pd.DataFrame()
    
    try:
        stats = nfl.load_player_stats([2024], summary_level='week').to_pandas()
        stats = stats[stats['position'].isin(['QB', 'RB', 'WR', 'TE'])]
        
        agg = stats.groupby(['player_display_name', 'position']).agg({
            'targets': 'sum',
            'receptions': 'sum',
            'receiving_yards': 'sum',
            'receiving_tds': 'sum',
            'carries': 'sum',
            'rushing_yards': 'sum',
            'rushing_tds': 'sum',
            'passing_yards': 'sum',
            'passing_tds': 'sum',
            'interceptions': 'sum',
            'fantasy_points_ppr': 'sum',
            'week': 'count'
        }).reset_index()
        
        agg.columns = ['name', 'position', 'targets', 'receptions', 'rec_yards', 'rec_tds',
                      'carries', 'rush_yards', 'rush_tds', 'pass_yards', 'pass_tds', 
                      'interceptions', 'ppr_points', 'games']
        
        agg['tpg'] = (agg['targets'] / agg['games']).round(1)
        agg['ppg'] = (agg['ppr_points'] / agg['games']).round(1)
        
        return agg
    except Exception as e:
        st.warning(f"Could not load NFL stats: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def load_merged_data() -> pd.DataFrame:
    """Load and merge KTC with NFL stats."""
    ktc = load_ktc_data()
    nfl_stats = load_nfl_stats()
    
    if len(ktc) == 0:
        return pd.DataFrame()
    
    if len(nfl_stats) > 0:
        merged = ktc.merge(nfl_stats, on='name', how='left', suffixes=('', '_nfl'))
        merged['value_efficiency'] = (merged['ppg'] * 1000 / merged['sf_value'].replace(0, 1)).round(2)
    else:
        merged = ktc.copy()
        merged['ppg'] = 0
        merged['tpg'] = 0
        merged['games'] = 0
        merged['value_efficiency'] = 0
    
    return merged

# =============================================================================
# AI AGENT
# =============================================================================

def get_ai_response(prompt: str, data_context: str = "") -> str:
    """Get response from Claude Opus 4.5."""
    if not ANTHROPIC_AVAILABLE:
        return "⚠️ Anthropic library not installed. Run: pip install anthropic"
    
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return "⚠️ Please set ANTHROPIC_API_KEY environment variable"
    
    try:
        client = anthropic.Anthropic(api_key=api_key)
        
        system_prompt = f"""You are Dynasty Edge, an expert dynasty fantasy football analyst. 
You have access to KeepTradeCut (KTC) valuations and NFL statistics.

Your capabilities:
- Analyze player values and identify buy/sell opportunities
- Evaluate trades for dynasty leagues
- Provide roster construction advice
- Explain NFL stats and their fantasy implications
- Help with draft strategy

Current data context:
{data_context}

Be concise but thorough. Use specific numbers when available.
Format responses with markdown for readability."""

        message = client.messages.create(
            model="claude-opus-4-5-20251101",
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return message.content[0].text
    except Exception as e:
        return f"⚠️ Error: {str(e)}"

# =============================================================================
# VISUALIZATION HELPERS
# =============================================================================

def create_value_chart(df: pd.DataFrame, position: str = None) -> go.Figure:
    """Create player value distribution chart."""
    data = df.copy()
    if position and position != "All":
        data = data[data['position'] == position]
    
    data = data[data['position'].isin(['QB', 'RB', 'WR', 'TE'])].head(50)
    
    fig = px.bar(
        data,
        x='name',
        y='sf_value',
        color='position',
        title=f"Top Player Values{f' - {position}' if position and position != 'All' else ''}",
        color_discrete_map={'QB': '#E74C3C', 'RB': '#3498DB', 'WR': '#2ECC71', 'TE': '#9B59B6'}
    )
    fig.update_layout(xaxis_tickangle=-45, height=500)
    return fig

def create_age_value_scatter(df: pd.DataFrame) -> go.Figure:
    """Create age vs value scatter plot."""
    data = df[df['position'].isin(['QB', 'RB', 'WR', 'TE'])].copy()
    data = data[data['sf_value'] > 1000]
    
    fig = px.scatter(
        data,
        x='age',
        y='sf_value',
        color='position',
        size='ppg' if 'ppg' in data.columns and data['ppg'].sum() > 0 else None,
        hover_data=['name', 'team'],
        title="Age vs KTC Value",
        color_discrete_map={'QB': '#E74C3C', 'RB': '#3498DB', 'WR': '#2ECC71', 'TE': '#9B59B6'}
    )
    fig.update_layout(height=500)
    return fig

def create_efficiency_chart(df: pd.DataFrame, position: str = None) -> go.Figure:
    """Create value efficiency chart."""
    data = df.copy()
    if position and position != "All":
        data = data[data['position'] == position]
    
    data = data[
        (data['games'] >= 5) & 
        (data['sf_value'] > 1000) &
        (data['position'].isin(['QB', 'RB', 'WR', 'TE']))
    ].copy()
    
    data = data.sort_values('value_efficiency', ascending=False).head(30)
    
    fig = px.bar(
        data,
        x='name',
        y='value_efficiency',
        color='position',
        title="Value Efficiency (PPG per 1000 KTC)",
        color_discrete_map={'QB': '#E74C3C', 'RB': '#3498DB', 'WR': '#2ECC71', 'TE': '#9B59B6'}
    )
    fig.update_layout(xaxis_tickangle=-45, height=500)
    return fig

# =============================================================================
# PAGE COMPONENTS
# =============================================================================

def render_sidebar():
    """Render sidebar navigation."""
    st.sidebar.title("🏈 Dynasty Edge")
    st.sidebar.markdown("---")
    
    page = st.sidebar.radio(
        "Navigation",
        ["🏠 Dashboard", "📊 Player Rankings", "💱 Trade Analyzer", 
         "🟢 Buy Signals", "🔴 Sell Signals", "📈 NFL Stats",
         "🤖 AI Assistant", "🔄 Update Data", "⚙️ Settings"]
    )
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Data Status:**")
    
    ktc = load_ktc_data()
    nfl_stats = load_nfl_stats()
    
    st.sidebar.markdown(f"- KTC Players: {len(ktc)}")
    st.sidebar.markdown(f"- NFL Stats: {len(nfl_stats)}")
    
    # Show last update times
    st.sidebar.markdown(f"- NFL Updated: {get_last_update_time('nfl')}")
    st.sidebar.markdown(f"- Sleeper Updated: {get_last_update_time('sleeper')}")
    
    # Quick refresh button in sidebar
    st.sidebar.markdown("---")
    if st.sidebar.button("🔄 Quick Refresh", use_container_width=True):
        with st.sidebar.status("Refreshing...", expanded=True) as status:
            st.write("Updating NFL data...")
            success, msg = refresh_nfl_data()
            st.write(f"{'✅' if success else '❌'} {msg}")
            
            st.write("Updating Sleeper data...")
            success, msg = refresh_sleeper_data()
            st.write(f"{'✅' if success else '❌'} {msg}")
            
            status.update(label="Refresh complete!", state="complete")
        
        # Clear cache to reload data
        st.cache_data.clear()
        st.rerun()
    
    return page

def render_dashboard():
    """Render main dashboard page."""
    st.title("🏈 Dynasty Edge Dashboard")
    st.markdown("*AI-Powered Dynasty Fantasy Football Analysis*")
    
    df = load_merged_data()
    if len(df) == 0:
        st.error("No data available")
        return
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Players", len(df[df['position'].isin(['QB', 'RB', 'WR', 'TE'])]))
    
    with col2:
        avg_value = df[df['position'].isin(['QB', 'RB', 'WR', 'TE'])]['sf_value'].mean()
        st.metric("Avg KTC Value", f"{avg_value:,.0f}")
    
    with col3:
        top_player = df[df['sf_value'] == df['sf_value'].max()]['name'].values[0]
        st.metric("Top Player", top_player)
    
    with col4:
        if 'ppg' in df.columns and df['ppg'].sum() > 0:
            top_scorer = df[df['ppg'] == df['ppg'].max()]['name'].values[0]
            st.metric("Top PPG", top_scorer)
        else:
            st.metric("NFL Data", "Not loaded")
    
    st.markdown("---")
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.plotly_chart(create_value_chart(df), use_container_width=True)
    
    with col2:
        st.plotly_chart(create_age_value_scatter(df), use_container_width=True)
    
    # Position breakdown
    st.markdown("### Position Breakdown")
    
    pos_summary = df[df['position'].isin(['QB', 'RB', 'WR', 'TE'])].groupby('position').agg({
        'sf_value': ['count', 'mean', 'max'],
        'age': 'mean'
    }).round(1)
    pos_summary.columns = ['Count', 'Avg Value', 'Max Value', 'Avg Age']
    
    st.dataframe(pos_summary, use_container_width=True)

def render_player_rankings():
    """Render player rankings page."""
    st.title("📊 Player Rankings")
    
    df = load_merged_data()
    if len(df) == 0:
        return
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        position = st.selectbox("Position", ["All", "QB", "RB", "WR", "TE"])
    
    with col2:
        min_value = st.slider("Min KTC Value", 0, 10000, 0, 500)
    
    with col3:
        max_age = st.slider("Max Age", 20, 40, 40)
    
    # Filter data
    filtered = df[df['position'].isin(['QB', 'RB', 'WR', 'TE'])].copy()
    if position != "All":
        filtered = filtered[filtered['position'] == position]
    filtered = filtered[(filtered['sf_value'] >= min_value) & (filtered['age'] <= max_age)]
    
    # Sort options
    sort_by = st.selectbox("Sort By", ["sf_value", "age", "ppg", "tpg", "value_efficiency"])
    filtered = filtered.sort_values(sort_by, ascending=False)
    
    # Display
    display_cols = ['name', 'position', 'team', 'sf_value', 'age', 'rookie']
    if 'ppg' in filtered.columns:
        display_cols.extend(['ppg', 'tpg', 'games', 'value_efficiency'])
    
    st.dataframe(
        filtered[display_cols].head(100),
        use_container_width=True,
        height=600
    )

def render_trade_analyzer():
    """Render trade analyzer page."""
    st.title("💱 Trade Analyzer")
    
    df = load_merged_data()
    if len(df) == 0:
        return
    
    player_names = df[df['position'].isin(['QB', 'RB', 'WR', 'TE', 'PI'])]['name'].tolist()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🏠 You Give")
        give_players = st.multiselect("Select players to give", player_names, key="give")
    
    with col2:
        st.subheader("📥 You Get")
        get_players = st.multiselect("Select players to get", player_names, key="get")
    
    if give_players or get_players:
        st.markdown("---")
        
        # Calculate values
        give_df = df[df['name'].isin(give_players)]
        get_df = df[df['name'].isin(get_players)]
        
        give_total = give_df['sf_value'].sum()
        get_total = get_df['sf_value'].sum()
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("You Give (KTC)", f"{give_total:,.0f}")
            for _, row in give_df.iterrows():
                st.markdown(f"- **{row['name']}** ({row['position']}): {row['sf_value']:,.0f}")
        
        with col2:
            st.metric("You Get (KTC)", f"{get_total:,.0f}")
            for _, row in get_df.iterrows():
                st.markdown(f"- **{row['name']}** ({row['position']}): {row['sf_value']:,.0f}")
        
        with col3:
            diff = get_total - give_total
            if diff > 0:
                st.metric("Net Value", f"+{diff:,.0f}", delta=f"+{diff:,.0f}")
                st.success("✅ You WIN this trade!")
            elif diff < 0:
                st.metric("Net Value", f"{diff:,.0f}", delta=f"{diff:,.0f}")
                st.error("❌ You LOSE this trade")
            else:
                st.metric("Net Value", "0")
                st.info("➡️ Even trade")
        
        # AI Analysis
        if st.button("🤖 Get AI Analysis"):
            context = f"""
Trade Analysis:
Give: {', '.join([f"{r['name']} ({r['position']}, KTC: {r['sf_value']:.0f}, Age: {r['age']:.1f})" for _, r in give_df.iterrows()])}
Get: {', '.join([f"{r['name']} ({r['position']}, KTC: {r['sf_value']:.0f}, Age: {r['age']:.1f})" for _, r in get_df.iterrows()])}
Give Total: {give_total:.0f}
Get Total: {get_total:.0f}
Net: {diff:.0f}
"""
            with st.spinner("Analyzing trade..."):
                response = get_ai_response(
                    "Analyze this dynasty trade. Consider age, position value, and long-term outlook.",
                    context
                )
            st.markdown("### AI Analysis")
            st.markdown(response)

def render_buy_signals():
    """Render buy signals page."""
    st.title("🟢 Buy Signals")
    st.markdown("*Players with high production relative to their KTC value*")
    
    df = load_merged_data()
    if len(df) == 0 or 'value_efficiency' not in df.columns:
        st.warning("NFL stats not available for efficiency calculation")
        return
    
    # Filter to buy candidates
    buys = df[
        (df['games'] >= 5) & 
        (df['sf_value'] > 1500) &
        (df['sf_value'] < 8000) &
        (df['position'].isin(['WR', 'RB', 'TE']))
    ].sort_values('value_efficiency', ascending=False).head(25)
    
    st.plotly_chart(create_efficiency_chart(df), use_container_width=True)
    
    st.markdown("### Top Buy Candidates")
    st.dataframe(
        buys[['name', 'position', 'team', 'sf_value', 'age', 'ppg', 'tpg', 'games', 'value_efficiency']],
        use_container_width=True
    )

def render_sell_signals():
    """Render sell signals page."""
    st.title("🔴 Sell Signals")
    st.markdown("*Players with declining production or overvalued on KTC*")
    
    df = load_merged_data()
    if len(df) == 0:
        return
    
    # High value, low efficiency
    sells = df[
        (df['games'] >= 5) & 
        (df['sf_value'] > 4000) &
        (df['position'].isin(['WR', 'RB', 'TE']))
    ].sort_values('value_efficiency', ascending=True).head(25)
    
    st.markdown("### Low Efficiency (High Value, Lower Production)")
    st.dataframe(
        sells[['name', 'position', 'team', 'sf_value', 'age', 'ppg', 'tpg', 'games', 'value_efficiency']],
        use_container_width=True
    )
    
    # Aging assets
    st.markdown("### Aging Assets to Monitor")
    aging = df[
        (df['age'] >= 29) & 
        (df['sf_value'] > 3000) &
        (df['position'].isin(['QB', 'WR', 'RB', 'TE']))
    ].sort_values('sf_value', ascending=False).head(20)
    
    st.dataframe(
        aging[['name', 'position', 'team', 'sf_value', 'age', 'ppg']],
        use_container_width=True
    )

def render_nfl_stats():
    """Render NFL stats page."""
    st.title("📈 NFL Statistics")
    
    if not NFL_DATA_AVAILABLE:
        st.error("NFL data library not available. Install with: pip install nflreadpy polars")
        return
    
    nfl_stats = load_nfl_stats()
    if len(nfl_stats) == 0:
        st.warning("No NFL stats loaded. Click 'Update Data' to fetch.")
        return
    
    # Position filter
    position = st.selectbox("Position", ["All", "QB", "RB", "WR", "TE"])
    
    data = nfl_stats.copy()
    if position != "All":
        data = data[data['position'] == position]
    
    # Metric selection
    metric = st.selectbox("Sort By", ["ppg", "ppr_points", "targets", "receptions", "rec_yards", 
                                       "carries", "rush_yards", "pass_yards"])
    
    data = data.sort_values(metric, ascending=False)
    
    st.dataframe(data.head(50), use_container_width=True)
    
    # Visualization
    fig = px.bar(
        data.head(20),
        x='name',
        y=metric,
        color='position',
        title=f"Top 20 by {metric}"
    )
    fig.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)

def render_update_data():
    """Render data update page."""
    st.title("🔄 Update Data")
    st.markdown("*Refresh your data sources*")
    
    # Current status
    st.markdown("### Current Data Status")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**NFL Stats (nflverse)**")
        st.markdown(f"Last updated: {get_last_update_time('nfl')}")
        if st.button("🔄 Refresh NFL Data", key="refresh_nfl", use_container_width=True):
            with st.spinner("Fetching NFL data..."):
                success, msg = refresh_nfl_data()
            if success:
                st.success(f"✅ {msg}")
                st.cache_data.clear()
            else:
                st.error(f"❌ {msg}")
    
    with col2:
        st.markdown("**Sleeper League**")
        st.markdown(f"Last updated: {get_last_update_time('sleeper')}")
        if st.button("🔄 Refresh Sleeper", key="refresh_sleeper", use_container_width=True):
            with st.spinner("Fetching Sleeper data..."):
                success, msg = refresh_sleeper_data()
            if success:
                st.success(f"✅ {msg}")
                st.cache_data.clear()
            else:
                st.error(f"❌ {msg}")
    
    with col3:
        st.markdown("**KTC Values**")
        st.markdown(f"Last updated: {get_last_update_time('ktc')}")
        st.info("Upload CSV manually")
    
    st.markdown("---")
    
    # Refresh all button
    st.markdown("### Refresh All Data")
    if st.button("🔄 REFRESH ALL DATA", type="primary", use_container_width=True):
        with st.status("Refreshing all data sources...", expanded=True) as status:
            st.write("📊 Updating NFL stats...")
            success, msg = refresh_nfl_data()
            st.write(f"{'✅' if success else '❌'} NFL: {msg}")
            
            st.write("😴 Updating Sleeper data...")
            success, msg = refresh_sleeper_data()
            st.write(f"{'✅' if success else '❌'} Sleeper: {msg}")
            
            status.update(label="✅ All data refreshed!", state="complete")
        
        st.cache_data.clear()
        st.success("Data refreshed! Navigate to other pages to see updated data.")
        st.balloons()
    
    st.markdown("---")
    
    # Manual KTC upload
    st.markdown("### Upload KTC Data")
    st.markdown("Download your KTC rankings from [keeptradecut.com](https://keeptradecut.com/dynasty-rankings) and upload here.")
    
    uploaded_file = st.file_uploader("Upload KTC CSV", type=['csv'])
    if uploaded_file:
        try:
            df = pd.read_csv(uploaded_file)
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            df.to_csv(DATA_DIR / "ktc_values.csv", index=False)
            
            # Save metadata
            metadata = {
                'last_updated': datetime.utcnow().isoformat(),
                'source': 'manual_upload',
                'filename': uploaded_file.name
            }
            with open(DATA_DIR / "ktc_metadata.json", 'w') as f:
                json.dump(metadata, f, indent=2)
            
            st.success(f"✅ Uploaded {len(df)} players!")
            st.cache_data.clear()
        except Exception as e:
            st.error(f"Error uploading file: {e}")

def render_ai_assistant():
    """Render AI assistant page."""
    st.title("🤖 AI Assistant")
    st.markdown("*Powered by Claude Opus 4.5*")
    
    if not ANTHROPIC_AVAILABLE:
        st.error("Anthropic library not installed. Run: pip install anthropic")
        st.code("pip install anthropic")
        return
    
    if not os.environ.get("ANTHROPIC_API_KEY"):
        st.warning("Please set ANTHROPIC_API_KEY in your .env file")
        st.code("ANTHROPIC_API_KEY=your-key-here")
        return
    
    # Chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Ask about dynasty fantasy football..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Get AI response
        df = load_merged_data()
        context = f"""
Top 10 players by KTC value:
{df.nlargest(10, 'sf_value')[['name', 'position', 'sf_value', 'age']].to_string()}

Top buy candidates (high efficiency):
{df[df['value_efficiency'] > 4].nlargest(5, 'value_efficiency')[['name', 'position', 'sf_value', 'ppg', 'value_efficiency']].to_string() if 'value_efficiency' in df.columns else 'N/A'}
"""
        
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = get_ai_response(prompt, context)
            st.markdown(response)
        
        st.session_state.messages.append({"role": "assistant", "content": response})
    
    # Quick action buttons
    st.markdown("---")
    st.markdown("**Quick Actions:**")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📊 Top Buy Candidates"):
            st.session_state.messages.append({"role": "user", "content": "What are the top buy candidates right now?"})
            st.rerun()
    
    with col2:
        if st.button("⚠️ Sell High Players"):
            st.session_state.messages.append({"role": "user", "content": "Which players should I be looking to sell high on?"})
            st.rerun()
    
    with col3:
        if st.button("🌟 Young Studs"):
            st.session_state.messages.append({"role": "user", "content": "Who are the best young assets under 25 to build around?"})
            st.rerun()

def render_settings():
    """Render settings page."""
    st.title("⚙️ Settings")
    
    st.markdown("### Data Sources")
    st.markdown(f"- **KTC Data:** {'✅ Loaded' if len(load_ktc_data()) > 0 else '❌ Not found'}")
    st.markdown(f"- **NFL Stats:** {'✅ Available' if NFL_DATA_AVAILABLE else '❌ Not installed'}")
    st.markdown(f"- **AI Agent:** {'✅ Available' if ANTHROPIC_AVAILABLE else '❌ Not installed'}")
    
    st.markdown("### League Configuration")
    league_id = os.environ.get("SLEEPER_LEAGUE_ID", "1180199027998867456")
    st.code(f"SLEEPER_LEAGUE_ID={league_id}")
    
    st.markdown("### Installation")
    st.code("""
# Required
pip install streamlit pandas plotly

# NFL Data
pip install nflreadpy polars pyarrow

# AI Agent
pip install anthropic
    """)
    
    st.markdown("### Environment Variables (.env file)")
    st.code("""
ANTHROPIC_API_KEY=your-key-here
SLEEPER_LEAGUE_ID=1180199027998867456
    """)
    
    st.markdown("### Run Dashboard")
    st.code("streamlit run dashboard.py")

# =============================================================================
# MAIN
# =============================================================================

def main():
    """Main application entry point."""
    page = render_sidebar()
    
    if page == "🏠 Dashboard":
        render_dashboard()
    elif page == "📊 Player Rankings":
        render_player_rankings()
    elif page == "💱 Trade Analyzer":
        render_trade_analyzer()
    elif page == "🟢 Buy Signals":
        render_buy_signals()
    elif page == "🔴 Sell Signals":
        render_sell_signals()
    elif page == "📈 NFL Stats":
        render_nfl_stats()
    elif page == "🤖 AI Assistant":
        render_ai_assistant()
    elif page == "🔄 Update Data":
        render_update_data()
    elif page == "⚙️ Settings":
        render_settings()

if __name__ == "__main__":
    main()
