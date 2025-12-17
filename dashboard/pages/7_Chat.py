"""
Thoth AI Assistant
==================
AI-powered dynasty fantasy football analysis chat.
"""

import streamlit as st
import pandas as pd
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

st.set_page_config(page_title="AI Assistant - Thoth", layout="wide")

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


def get_driver():
    """Get Neo4j driver."""
    if 'neo4j_driver' not in st.session_state:
        from neo4j import GraphDatabase
        uri = st.secrets.get("neo4j_uri", "bolt://localhost:7687")
        st.session_state.neo4j_driver = GraphDatabase.driver(uri, auth=None)
    return st.session_state.neo4j_driver


def get_anthropic_client():
    """Get Anthropic client."""
    if 'anthropic_client' not in st.session_state:
        try:
            from anthropic import Anthropic
            api_key = os.getenv("ANTHROPIC_API_KEY") or st.secrets.get("anthropic_api_key")
            if api_key:
                st.session_state.anthropic_client = Anthropic(api_key=api_key)
            else:
                st.session_state.anthropic_client = None
        except Exception as e:
            st.session_state.anthropic_client = None
    return st.session_state.anthropic_client


def get_tool_executor():
    """Get Thoth tool executor."""
    if 'tool_executor' not in st.session_state:
        try:
            from src.agent.enhanced_tools import ThothToolExecutor
            driver = get_driver()
            st.session_state.tool_executor = ThothToolExecutor(driver)
        except Exception as e:
            st.session_state.tool_executor = None
    return st.session_state.tool_executor


# =============================================================================
# THOTH SYSTEM PROMPT (abbreviated for dashboard)
# =============================================================================

THOTH_SYSTEM_PROMPT = """You are **Thoth**, the AI god of dynasty fantasy football wisdom.

You have access to specialized tools that query a Neo4j database containing 3,700+ NFL players with 40+ data points.

**Your Knowledge:**
- ML model with R² = 0.87
- Top predictors: contract_guaranteed (100%), total_snaps (21%), snap_pct (19%)
- Signals: STRONG_BUY (>15% gap), BUY (7-15%), HOLD (-7% to 7%), SELL (-7% to -15%), STRONG_SELL (<-15%)

**Response Style:**
- Lead with the answer
- Include specific numbers
- Explain the reasoning
- Be concise but complete

**Format for player lookups:**
```
**Player Name** (POS, Team) - Age X
KTC: X,XXX | Model: X,XXX | Gap: +X,XXX
Signal: [BUY/SELL/HOLD]
```

Use tools to get real data - never make up stats."""


# =============================================================================
# TOOL DEFINITIONS (for Claude)
# =============================================================================

from src.agent.enhanced_tools import THOTH_TOOLS


# =============================================================================
# CHAT FUNCTIONS
# =============================================================================

def process_with_ai(user_message: str, conversation_history: list) -> tuple:
    """
    Process user message with Claude AI and tool use.
    Returns (response_text, updated_history)
    """
    client = get_anthropic_client()
    executor = get_tool_executor()

    if not client:
        return "API key not configured. Set ANTHROPIC_API_KEY in environment or secrets.", conversation_history

    if not executor:
        return "Tool executor not available. Check Neo4j connection.", conversation_history

    # Add user message to history
    conversation_history.append({
        "role": "user",
        "content": user_message
    })

    try:
        # Initial API call
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system=THOTH_SYSTEM_PROMPT,
            tools=THOTH_TOOLS,
            messages=conversation_history
        )

        # Process tool calls
        tool_calls_made = []
        while response.stop_reason == "tool_use":
            tool_uses = [block for block in response.content if block.type == "tool_use"]

            tool_results = []
            for tool_use in tool_uses:
                tool_calls_made.append(tool_use.name)
                result = executor.execute(tool_use.name, tool_use.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": result
                })

            conversation_history.append({
                "role": "assistant",
                "content": response.content
            })
            conversation_history.append({
                "role": "user",
                "content": tool_results
            })

            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2048,
                system=THOTH_SYSTEM_PROMPT,
                tools=THOTH_TOOLS,
                messages=conversation_history
            )

        # Extract final response
        final_response = ""
        for block in response.content:
            if hasattr(block, "text"):
                final_response += block.text

        conversation_history.append({
            "role": "assistant",
            "content": response.content
        })

        return final_response, conversation_history, tool_calls_made

    except Exception as e:
        return f"Error: {str(e)}", conversation_history, []


def process_with_fallback(user_message: str) -> str:
    """
    Fallback processing when AI is not available.
    Uses pattern matching to run direct queries.
    """
    executor = get_tool_executor()
    if not executor:
        return "Database connection not available."

    message_lower = user_message.lower()

    try:
        # Pattern matching for common queries
        if any(word in message_lower for word in ["buy", "undervalued", "opportunity"]):
            result = executor.execute("get_edge_report", {"signal": "BUY", "limit": 10})
            data = json.loads(result)
            if isinstance(data, list) and data:
                response = "**Top Buy Opportunities:**\n\n"
                for p in data[:10]:
                    gap = p.get('value_gap', 0) or 0
                    response += f"• **{p['name']}** ({p['position']}) - KTC: {p.get('ktc_value', 0):,} | Gap: +{gap:,.0f}\n"
                return response

        elif any(word in message_lower for word in ["sell", "overvalued"]):
            result = executor.execute("get_edge_report", {"signal": "SELL", "limit": 10})
            data = json.loads(result)
            if isinstance(data, list) and data:
                response = "**Top Sell Candidates:**\n\n"
                for p in data[:10]:
                    gap = p.get('value_gap', 0) or 0
                    response += f"• **{p['name']}** ({p['position']}) - KTC: {p.get('ktc_value', 0):,} | Gap: {gap:,.0f}\n"
                return response

        elif any(word in message_lower for word in ["athletic", "combine", "fast", "speed"]):
            result = executor.execute("find_undervalued_athletes", {"limit": 10})
            data = json.loads(result)
            if isinstance(data, list) and data:
                response = "**Undervalued Athletes:**\n\n"
                for p in data[:10]:
                    forty = p.get('forty', 0) or 0
                    response += f"• **{p['name']}** ({p['position']}) - 40: {forty:.2f}s | Signal: {p.get('signal', 'N/A')}\n"
                return response

        elif any(word in message_lower for word in ["breakout", "rising", "snap"]):
            result = executor.execute("get_playing_time_breakout", {"min_snap_trend": 5, "limit": 10})
            data = json.loads(result)
            if isinstance(data, list) and data:
                response = "**Rising Snap Share Players:**\n\n"
                for p in data[:10]:
                    trend = p.get('snap_trend', 0) or 0
                    response += f"• **{p['name']}** ({p['position']}) - Snap Trend: +{trend:.1f}%\n"
                return response

        # Default: try to find a player
        else:
            # Extract potential player name
            words = user_message.split()
            if len(words) >= 2:
                # Try first two capitalized words as player name
                potential_name = " ".join(words[:2])
                result = executor.execute("get_player_profile", {"player_name": potential_name})
                data = json.loads(result)
                if data and "error" not in data:
                    response = f"**{data.get('name', potential_name)}** ({data.get('position', 'N/A')}, {data.get('team', 'FA')})\n\n"
                    response += f"**Age:** {data.get('age', 'N/A')}\n"
                    response += f"**KTC Value:** {data.get('ktc_value', 0):,}\n"
                    if data.get('predicted_value'):
                        gap = data.get('value_gap', 0) or 0
                        response += f"**Model Value:** {data['predicted_value']:,.0f} (Gap: {gap:+,.0f})\n"
                    response += f"**Signal:** {data.get('signal', 'N/A')}\n"
                    return response

            return """I can help you with:
• **Buy/Sell signals** - "Who should I buy?"
• **Player lookups** - "[Player name]"
• **Athletic analysis** - "Find athletic undervalued players"
• **Breakout candidates** - "Rising snap share players"

Try asking about a specific player or topic!"""

    except Exception as e:
        return f"Error processing request: {str(e)}"


# =============================================================================
# MAIN PAGE
# =============================================================================

def main():
    st.title("🔮 Thoth AI Assistant")
    st.markdown("Ask anything about dynasty fantasy football")

    # Initialize session state
    if 'chat_messages' not in st.session_state:
        st.session_state.chat_messages = []
    if 'conversation_history' not in st.session_state:
        st.session_state.conversation_history = []

    # Check for AI availability
    client = get_anthropic_client()
    ai_available = client is not None

    # Sidebar controls
    with st.sidebar:
        st.markdown("### Settings")

        mode = st.radio(
            "Mode",
            ["AI Assistant", "Quick Queries"],
            help="AI uses Claude for natural conversation. Quick Queries uses pattern matching."
        )

        if mode == "AI Assistant" and not ai_available:
            st.warning("API key not configured. Using Quick Queries mode.")
            mode = "Quick Queries"

        if st.button("Clear Chat"):
            st.session_state.chat_messages = []
            st.session_state.conversation_history = []
            st.rerun()

        st.markdown("---")
        st.markdown("### Quick Actions")

        if st.button("Show Buy Signals"):
            st.session_state.pending_query = "Who should I buy?"

        if st.button("Show Sell Signals"):
            st.session_state.pending_query = "Who should I sell?"

        if st.button("Athletic Bargains"):
            st.session_state.pending_query = "Find undervalued athletic players"

        if st.button("Breakout Candidates"):
            st.session_state.pending_query = "Show rising snap share players"

    # Display chat messages
    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"], avatar="🧑" if message["role"] == "user" else "🔮"):
            st.markdown(message["content"])
            if message.get("tools_used"):
                st.caption(f"Tools: {', '.join(message['tools_used'])}")

    # Example questions
    if not st.session_state.chat_messages:
        st.markdown("### Example Questions")

        example_cols = st.columns(2)

        examples = [
            ("🏈 Player Analysis", [
                "Tell me about Ja'Marr Chase",
                "Compare CeeDee Lamb and Amon-Ra St. Brown",
                "Why is Jonathan Taylor a sell?"
            ]),
            ("📊 Discovery", [
                "Who are the best buy-low WRs under 25?",
                "Find athletic freaks who are undervalued",
                "Show me players with rising snap share"
            ])
        ]

        for i, (category, questions) in enumerate(examples):
            with example_cols[i]:
                st.markdown(f"**{category}**")
                for q in questions:
                    if st.button(q, key=f"ex_{q}"):
                        st.session_state.pending_query = q

    # Handle pending query from buttons
    if 'pending_query' in st.session_state:
        user_input = st.session_state.pending_query
        del st.session_state.pending_query
    else:
        user_input = st.chat_input("Ask Thoth anything about dynasty fantasy football...")

    # Process user input
    if user_input:
        # Add user message
        st.session_state.chat_messages.append({
            "role": "user",
            "content": user_input
        })

        with st.chat_message("user", avatar="🧑"):
            st.markdown(user_input)

        # Generate response
        with st.chat_message("assistant", avatar="🔮"):
            with st.spinner("Consulting the oracle..."):
                if mode == "AI Assistant" and ai_available:
                    response, st.session_state.conversation_history, tools_used = process_with_ai(
                        user_input,
                        st.session_state.conversation_history
                    )
                else:
                    response = process_with_fallback(user_input)
                    tools_used = []

                st.markdown(response)
                if tools_used:
                    st.caption(f"Tools: {', '.join(tools_used)}")

                # Save response
                st.session_state.chat_messages.append({
                    "role": "assistant",
                    "content": response,
                    "tools_used": tools_used
                })

    # Footer
    st.markdown("---")
    mode_label = "AI" if mode == "AI Assistant" and ai_available else "Quick"
    st.caption(f"Mode: {mode_label} | Model: Thoth ML (R²=0.87) | Data: 3,700+ players")


if __name__ == "__main__":
    main()
