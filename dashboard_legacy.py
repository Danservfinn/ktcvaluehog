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
"""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

# Load environment variables from .env file (must be before other imports that use env vars)
from dotenv import load_dotenv
_env_path = Path(__file__).parent / ".env"
load_dotenv(_env_path)

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

try:
    from neo4j import GraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False

# Neo4j Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
NEO4J_AUTH_DISABLED = os.getenv("NEO4J_AUTH_DISABLED", "true").lower() == "true"

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

# =============================================================================
# DATA LOADING
# =============================================================================

def get_neo4j_driver():
    """Get Neo4j driver with proper authentication."""
    if not NEO4J_AVAILABLE:
        return None
    try:
        if NEO4J_AUTH_DISABLED:
            return GraphDatabase.driver(NEO4J_URI, auth=None)
        else:
            return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    except Exception as e:
        st.warning(f"Could not connect to Neo4j: {e}")
        return None

@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_ktc_data() -> pd.DataFrame:
    """Load KTC player values from Neo4j database."""

    # First try Neo4j
    if NEO4J_AVAILABLE:
        try:
            driver = get_neo4j_driver()
            if driver:
                with driver.session() as session:
                    result = session.run("""
                        MATCH (p:Player)
                        WHERE p.position IN ['QB', 'RB', 'WR', 'TE']
                        RETURN
                            p.name as name,
                            p.position as position,
                            p.team as team,
                            p.ktc_value as sf_value,
                            p.age as age,
                            p.years_exp as years_exp,
                            p.ecr_sf as ecr_sf,
                            CASE WHEN p.years_exp <= 1 THEN 1 ELSE 0 END as rookie
                        ORDER BY COALESCE(p.ktc_value, 0) DESC
                    """)
                    records = [dict(r) for r in result]
                    driver.close()

                    if records:
                        df = pd.DataFrame(records)
                        # Add pos_rank
                        df['pos_rank'] = df.groupby('position').cumcount() + 1
                        df['pos_rank'] = df['position'] + df['pos_rank'].astype(str)
                        # Fill nulls
                        df['sf_value'] = df['sf_value'].fillna(0).astype(int)
                        df['age'] = df['age'].fillna(25)
                        df['team'] = df['team'].fillna('FA')
                        return df
        except Exception as e:
            st.warning(f"Neo4j query failed: {e}")

    # Fallback to CSV
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

    st.error("No data source available. Please ensure Neo4j is running or ktc_values.csv exists.")
    return pd.DataFrame()

@st.cache_data(ttl=3600)
def load_nfl_stats() -> pd.DataFrame:
    """Load NFL player statistics for the current season."""
    if not NFL_DATA_AVAILABLE:
        return pd.DataFrame()

    try:
        # Get current season dynamically
        current_season = nfl.get_current_season()
        current_week = nfl.get_current_week()

        # Store season info in session state for display
        if 'nfl_season' not in st.session_state:
            st.session_state.nfl_season = current_season
            st.session_state.nfl_week = current_week

        stats = nfl.load_player_stats([current_season], summary_level='week').to_pandas()
        stats = stats[stats['position'].isin(['QB', 'RB', 'WR', 'TE'])]

        # Aggregate by player
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
            'passing_interceptions': 'sum',
            'fantasy_points_ppr': 'sum',
            'week': 'count'
        }).reset_index()

        agg.columns = ['name', 'position', 'targets', 'receptions', 'rec_yards', 'rec_tds',
                      'carries', 'rush_yards', 'rush_tds', 'pass_yards', 'pass_tds',
                      'pass_int', 'ppr_points', 'games']

        # Per-game metrics
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
            model="claude-opus-4-5-20251101",  # Claude Opus 4.5
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

    # Determine if we can use ppg for size (no NaN values)
    use_size = 'ppg' in data.columns and data['ppg'].sum() > 0 and not data['ppg'].isna().any()

    fig = px.scatter(
        data,
        x='age',
        y='sf_value',
        color='position',
        size='ppg' if use_size else None,
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
         "🤖 AI Assistant", "📅 Data Status", "⚙️ Settings"]
    )
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Data Status:**")

    ktc = load_ktc_data()
    nfl_stats = load_nfl_stats()

    # Show data source
    ktc_with_value = len(ktc[ktc['sf_value'] > 0]) if len(ktc) > 0 else 0
    data_source = "Neo4j" if NEO4J_AVAILABLE and len(ktc) > 100 else "CSV"

    st.sidebar.markdown(f"- Source: **{data_source}**")
    st.sidebar.markdown(f"- KTC Players: {ktc_with_value}")
    st.sidebar.markdown(f"- Total Players: {len(ktc)}")
    st.sidebar.markdown(f"- NFL Stats: {len(nfl_stats)}")
    st.sidebar.markdown(f"- Last Updated: {datetime.now().strftime('%Y-%m-%d')}")
    
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
        st.warning("No NFL stats loaded")
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

def render_ai_assistant():
    """Render AI assistant page."""
    st.title("🤖 AI Assistant")
    st.markdown("*Powered by Claude Opus 4.5*")
    
    if not ANTHROPIC_AVAILABLE:
        st.error("Anthropic library not installed. Run: pip install anthropic")
        st.code("pip install anthropic")
        return
    
    if not os.environ.get("ANTHROPIC_API_KEY"):
        st.warning("Please set ANTHROPIC_API_KEY environment variable")
        st.code("export ANTHROPIC_API_KEY='your-key-here'")
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

def render_data_status():
    """Render data status page showing age of each data source."""
    st.title("📅 Data Status")
    st.markdown("*Monitor the freshness of your data sources*")

    # Get file paths
    ktc_file = DATA_DIR / "ktc_values.csv"
    ktc_metadata_file = DATA_DIR / "ktc_metadata.json"

    st.markdown("---")

    # KTC Data Status
    st.markdown("### 🏈 KTC Player Values")

    # Source info
    st.markdown("**Source:** [KeepTradeCut.com](https://keeptradecut.com/dynasty-rankings) → Dynasty player rankings")
    st.markdown("**Data Provider:** Crowdsourced dynasty fantasy football valuations")

    col1, col2, col3 = st.columns(3)

    if ktc_file.exists():
        file_stat = ktc_file.stat()
        file_modified = datetime.fromtimestamp(file_stat.st_mtime)
        file_age = datetime.now() - file_modified
        age_hours = file_age.total_seconds() / 3600
        age_days = age_hours / 24

        with col1:
            st.metric("File Status", "✅ Available")
        with col2:
            st.metric("Last Modified", file_modified.strftime("%Y-%m-%d %H:%M"))
        with col3:
            if age_days < 1:
                st.metric("Data Age", f"{age_hours:.1f} hours")
            else:
                st.metric("Data Age", f"{age_days:.1f} days")

        # Show freshness indicator
        if age_days < 1:
            st.success("🟢 **Fresh** - Data is less than 24 hours old")
        elif age_days < 7:
            st.warning(f"🟡 **Aging** - Data is {age_days:.1f} days old. Consider refreshing.")
        else:
            st.error(f"🔴 **Stale** - Data is {age_days:.1f} days old. Refresh recommended!")

        # Check metadata
        if ktc_metadata_file.exists():
            with open(ktc_metadata_file, 'r') as f:
                metadata = json.load(f)
            st.markdown("**Metadata:**")
            st.json(metadata)
    else:
        with col1:
            st.metric("File Status", "❌ Missing")
        st.error("KTC data file not found. Run the fetch script to download data.")
        st.code("python scripts/fetch_ktc_data.py")

    st.markdown("---")

    # NFL Stats Status
    st.markdown("### 📈 NFL Statistics")

    # Source info
    st.markdown("**Source:** [nflreadpy](https://github.com/nflverse/nflverse-data) → nflverse GitHub data repository")
    st.markdown("**Data Provider:** NFL Next Gen Stats, Pro Football Reference, official NFL data")

    col1, col2, col3, col4 = st.columns(4)

    if NFL_DATA_AVAILABLE:
        nfl_stats = load_nfl_stats()

        # Track when data was loaded in session
        if 'nfl_data_loaded_at' not in st.session_state:
            st.session_state.nfl_data_loaded_at = datetime.now()

        # Get current season/week info
        current_season = nfl.get_current_season()
        current_week = nfl.get_current_week()

        with col1:
            st.metric("Library Status", "✅ Installed")
        with col2:
            st.metric("Players Loaded", len(nfl_stats))
        with col3:
            st.metric("Season", str(current_season), delta=f"Week {current_week}")
        with col4:
            # Check cache directory
            import platformdirs
            cache_dir = Path(platformdirs.user_cache_dir("nflreadpy"))
            if cache_dir.exists():
                cache_files = list(cache_dir.rglob("*.parquet"))
                if cache_files:
                    newest = max(cache_files, key=lambda f: f.stat().st_mtime)
                    cache_modified = datetime.fromtimestamp(newest.stat().st_mtime)
                    st.metric("Cache Updated", cache_modified.strftime("%Y-%m-%d %H:%M"))
                else:
                    st.metric("Session Loaded", st.session_state.nfl_data_loaded_at.strftime("%H:%M"))
            else:
                st.metric("Session Loaded", st.session_state.nfl_data_loaded_at.strftime("%H:%M"))

        if len(nfl_stats) > 0:
            st.success("🟢 **Available** - NFL stats loaded successfully")

            # More details
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Positions:** {', '.join(sorted(nfl_stats['position'].unique()))}")
            with col2:
                if 'games' in nfl_stats.columns:
                    total_games = nfl_stats['games'].sum()
                    st.markdown(f"**Total Player-Games:** {total_games:,}")

            st.info("ℹ️ NFL data is fetched from nflverse GitHub repository. Data typically updates within 24 hours of games completing.")
        else:
            st.warning("🟡 **Empty** - No stats loaded. Data may be updating.")
    else:
        with col1:
            st.metric("Library Status", "❌ Not Installed")
        st.error("nflreadpy not installed.")
        st.code("pip install nflreadpy polars pyarrow")

    st.markdown("---")

    # AI Agent Status
    st.markdown("### 🤖 AI Agent (Claude)")
    col1, col2 = st.columns(2)

    with col1:
        if ANTHROPIC_AVAILABLE:
            st.metric("Library Status", "✅ Installed")
        else:
            st.metric("Library Status", "❌ Not Installed")

    with col2:
        if os.environ.get("ANTHROPIC_API_KEY"):
            st.metric("API Key", "✅ Configured")
        else:
            st.metric("API Key", "❌ Missing")

    st.markdown("---")

    # Refresh actions
    st.markdown("### 🔄 Refresh Data")
    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔄 Clear Streamlit Cache"):
            st.cache_data.clear()
            st.success("Cache cleared! Refresh the page to reload data.")

    with col2:
        st.markdown("**Manual Refresh:**")
        st.code("python scripts/fetch_ktc_data.py")


def render_settings():
    """Render settings page."""
    st.title("⚙️ Settings")
    
    st.markdown("### Data Sources")
    st.markdown(f"- **KTC Data:** {'✅ Loaded' if len(load_ktc_data()) > 0 else '❌ Not found'}")
    st.markdown(f"- **NFL Stats:** {'✅ Available' if NFL_DATA_AVAILABLE else '❌ Not installed'}")
    st.markdown(f"- **AI Agent:** {'✅ Available' if ANTHROPIC_AVAILABLE else '❌ Not installed'}")
    
    st.markdown("### Installation")
    st.code("""
# Required
pip install streamlit pandas plotly

# NFL Data
pip install nflreadpy polars pyarrow

# AI Agent
pip install anthropic
    """)
    
    st.markdown("### Environment Variables")
    st.code("""
# For AI Agent
export ANTHROPIC_API_KEY='your-key-here'
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
    elif page == "📅 Data Status":
        render_data_status()
    elif page == "⚙️ Settings":
        render_settings()

if __name__ == "__main__":
    main()
