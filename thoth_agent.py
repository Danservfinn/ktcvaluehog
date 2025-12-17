#!/usr/bin/env python3
"""
Thoth - Dynasty Fantasy Football AI Agent
==========================================
The world's most powerful dynasty fantasy football analytics assistant.

Powered by:
- Claude AI for natural language understanding
- Neo4j graph database for relationship queries
- ML model trained on 40+ features (R²=0.87)

Usage:
    python thoth_agent.py
"""

import os
import json
from typing import List
from neo4j import GraphDatabase
from anthropic import Anthropic
from dotenv import load_dotenv

from src.agent.enhanced_tools import THOTH_TOOLS, ThothToolExecutor

load_dotenv()

# Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


# =============================================================================
# THOTH SYSTEM PROMPT
# =============================================================================

THOTH_SYSTEM_PROMPT = """You are **Thoth**, the AI god of dynasty fantasy football wisdom.

Named after the Egyptian god of knowledge, writing, and magic, you possess unparalleled insight into dynasty player values, market inefficiencies, and strategic opportunities.

## YOUR CAPABILITIES

You have access to 14 specialized tools that query a Neo4j graph database containing:
- **3,700+ NFL players** with 40+ data points each
- **ML predictions** comparing model value vs KTC market value
- **Athletic profiles** from NFL Combine testing
- **Contract data** including guaranteed money and APY
- **Playing time trends** including snap share changes
- **Injury history** and risk scores

## YOUR KNOWLEDGE

**Model Performance**: R² = 0.87, meaning 87% of dynasty value variance is explained

**Feature Importance** (what drives value):
1. **Contract Guaranteed** (100%) - NFL teams vote with dollars
2. **Contract Total** (55%) - Overall investment
3. **Total Snaps** (21%) - Opportunity matters most
4. **Snap Percentage** (19%) - Role clarity
5. **APY Percentile** (16%) - Market position
6. **ADOT** (15%) - Role type indicator
7. **Draft Value** (12%) - Pedigree persistence
8. **Snap Trend** (9%) - Leading indicator

**Signal Thresholds**:
- STRONG_BUY: Model predicts >15% more value than KTC
- BUY: +7% to +15%
- HOLD: -7% to +7%
- SELL: -15% to -7%
- STRONG_SELL: <-15%

**Age Curves**:
- QB: Peak 26-34, productive until ~40
- RB: Peak 22-26, cliff at 28, done by 30
- WR: Peak 24-28, decline after 30, done by 34
- TE: Peak 25-29, late bloomers, done by 35

## YOUR PERSONALITY

- **Authoritative but approachable** - You know your stuff but explain clearly
- **Data-driven** - Every recommendation backed by specific numbers
- **Actionable** - Don't just describe, recommend actions
- **Concise** - Get to the point, then elaborate if needed

## RESPONSE FORMAT

When answering questions:
1. **Lead with the answer** - Don't bury the lead
2. **Show the data** - Include specific numbers
3. **Explain the why** - What factors drive the recommendation
4. **Suggest next steps** - What should the user do

For player lookups, format like:
```
**Player Name** (POS, Team) - Age X
KTC: X,XXX | Model: X,XXX | Gap: +X,XXX (X.X%)
Signal: [BUY/SELL/HOLD]

Key factors:
- Factor 1
- Factor 2
```

For lists, use tables when comparing multiple players.

## TOOL SELECTION GUIDE

- **Player questions**: get_player_profile, search_players
- **Buy/sell signals**: get_edge_report
- **Comparisons**: compare_players
- **Trade help**: find_trade_targets, analyze_roster
- **Athletic questions**: find_undervalued_athletes
- **Contract questions**: find_contract_mismatches
- **Breakout candidates**: get_playing_time_breakout
- **Why questions**: explain_recommendation, explain_methodology
- **Complex queries**: cypher_query (fallback)

## IMPORTANT NOTES

- Always use tools to get real data - never make up player stats
- If a player isn't found, suggest checking spelling
- For trade analysis, consider age, signal, and value gap
- Snap trend is a LEADING indicator - rising snaps often precede KTC increases
- Contract guaranteed money is your most reliable signal

You are the oracle of dynasty football. Speak with confidence and wisdom."""


# =============================================================================
# THOTH AGENT
# =============================================================================

class ThothAgent:
    """Thoth - Dynasty Fantasy Football AI Agent."""

    def __init__(self):
        self.client = Anthropic(api_key=ANTHROPIC_API_KEY)
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=None)
        self.executor = ThothToolExecutor(self.driver)
        self.conversation_history = []

    def close(self):
        """Clean up resources."""
        self.driver.close()

    def chat(self, user_message: str) -> str:
        """Process a user message and return Thoth's response."""
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })

        # Initial API call
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=THOTH_SYSTEM_PROMPT,
            tools=THOTH_TOOLS,
            messages=self.conversation_history
        )

        # Process tool calls in a loop
        while response.stop_reason == "tool_use":
            tool_uses = [block for block in response.content if block.type == "tool_use"]

            tool_results = []
            for tool_use in tool_uses:
                print(f"  🔧 {tool_use.name}...")
                result = self.executor.execute(tool_use.name, tool_use.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": result
                })

            self.conversation_history.append({
                "role": "assistant",
                "content": response.content
            })
            self.conversation_history.append({
                "role": "user",
                "content": tool_results
            })

            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=THOTH_SYSTEM_PROMPT,
                tools=THOTH_TOOLS,
                messages=self.conversation_history
            )

        # Extract final response
        final_response = ""
        for block in response.content:
            if hasattr(block, "text"):
                final_response += block.text

        self.conversation_history.append({
            "role": "assistant",
            "content": response.content
        })

        return final_response

    def reset_conversation(self):
        """Reset conversation history."""
        self.conversation_history = []


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Run the interactive Thoth agent."""
    print("\n" + "=" * 70)
    print("🔮 THOTH - Dynasty Fantasy Football AI")
    print("   The Oracle of Dynasty Wisdom")
    print("=" * 70)

    print("\n📊 Powered by ML model trained on 40+ features (R² = 0.87)")
    print("📈 3,700+ players with athletic, contract, and playing time data")

    print("\n💡 Example questions:")
    print('  • "Who are the best buy-low WRs under 25?"')
    print('  • "Compare Ja\'Marr Chase and CeeDee Lamb"')
    print('  • "Why is [player] a sell?"')
    print('  • "Find athletic freaks who are undervalued"')
    print('  • "Help me find trade targets for my rebuild"')
    print('  • "What drives dynasty value the most?"')

    print("\nType 'quit' to exit, 'reset' to clear history.\n")

    agent = ThothAgent()

    try:
        while True:
            user_input = input("\n🧑 You: ").strip()

            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\n🔮 May Thoth's wisdom guide your dynasty. Farewell!")
                break

            if user_input.lower() == 'reset':
                agent.reset_conversation()
                print("💫 Conversation reset. Fresh wisdom awaits.")
                continue

            if not user_input:
                continue

            print("\n🔮 Thoth: ", end="", flush=True)
            response = agent.chat(user_input)
            print(response)

    except KeyboardInterrupt:
        print("\n\n🔮 Interrupted. Farewell!")

    finally:
        agent.close()


if __name__ == "__main__":
    main()
