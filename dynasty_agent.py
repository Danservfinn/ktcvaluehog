#!/usr/bin/env python3
"""
Dynasty Edge - Conversational AI Agent
Uses Claude API with tool use to query Neo4j and provide insights.

Prerequisites:
    pip install anthropic neo4j python-dotenv

Usage:
    python dynasty_agent.py
"""

import os
import json
from typing import Any
from neo4j import GraphDatabase
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

# Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


# =============================================================================
# TOOL DEFINITIONS
# =============================================================================

TOOLS = [
    {
        "name": "cypher_query",
        "description": """Execute a Cypher query against the Dynasty Edge Neo4j database.
        
Available node types:
- Player: player_id, name, position, team, age, ktc_value, edge_value, edge_score, edge_signal, years_remaining, rookie
- Team: team_id, name, conference, division
- FantasyTeam: roster_id, owner, team_name, wins, losses, fpts
- DraftPick: pick_id, season, round, projected_slot, ktc_value

Available relationships:
- (Player)-[:PLAYS_FOR]->(Team)
- (Player)-[:TARGETS_FROM]->(Player) - WR/TE to their QB
- (Player)-[:COMPETES_WITH]->(Player) - Same position on same team
- (Player)-[:ROSTERED_BY]->(FantasyTeam)
- (FantasyTeam)-[:OWNS]->(DraftPick)
- (DraftPick)-[:ORIGINALLY_OWNED_BY]->(FantasyTeam)

Example queries:
- Find all WRs with young QBs: MATCH (wr:Player)-[:TARGETS_FROM]->(qb:Player) WHERE qb.age < 26 RETURN wr.name, qb.name, qb.age
- Find BUY signals: MATCH (p:Player) WHERE p.edge_signal = 'BUY' RETURN p.name, p.position, p.ktc_value, p.edge_score
- Find depth chart competition: MATCH (p1:Player)-[:COMPETES_WITH]-(p2:Player) WHERE p1.position = 'RB' RETURN p1.name, p2.name, p1.ktc_value, p2.ktc_value""",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A valid Cypher query to execute against the Neo4j database"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_edge_report",
        "description": """Get a report of players with the biggest value discrepancies between KTC and calculated edge values.
        Use this to find buy and sell opportunities.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "signal": {
                    "type": "string",
                    "enum": ["BUY", "SELL", "ALL"],
                    "description": "Filter by signal type"
                },
                "position": {
                    "type": "string",
                    "enum": ["QB", "RB", "WR", "TE", "ALL"],
                    "description": "Filter by position"
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of results to return (default 10)"
                }
            }
        }
    },
    {
        "name": "analyze_roster",
        "description": """Analyze a fantasy team's roster composition, strengths, and weaknesses.
        Provides insights on age distribution, positional depth, and value concentration.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {
                    "type": "string",
                    "description": "The fantasy team owner's username (e.g., 'danservfinn')"
                }
            },
            "required": ["owner"]
        }
    },
    {
        "name": "find_trade_targets",
        "description": """Find players on other fantasy teams that would be good trade targets
        based on the owner's competitive window and your needs.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "from_owner": {
                    "type": "string",
                    "description": "Target owner to find trade candidates from"
                },
                "positions_needed": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Positions you're looking to acquire (e.g., ['WR', 'TE'])"
                },
                "max_age": {
                    "type": "number",
                    "description": "Maximum age of players to target (default 26)"
                }
            },
            "required": ["from_owner"]
        }
    }
]


# =============================================================================
# TOOL IMPLEMENTATIONS
# =============================================================================

class Neo4jClient:
    """Neo4j database client for tool execution."""
    
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
    
    def close(self):
        self.driver.close()
    
    def run_query(self, query: str) -> list[dict]:
        """Execute a Cypher query and return results."""
        with self.driver.session() as session:
            result = session.run(query)
            return [dict(record) for record in result]
    
    def get_edge_report(self, signal: str = "ALL", position: str = "ALL", limit: int = 10) -> list[dict]:
        """Get edge value discrepancy report."""
        query = """
            MATCH (p:Player)
            WHERE p.edge_signal IS NOT NULL
              AND p.ktc_value > 1000
        """
        
        if signal != "ALL":
            query += f" AND p.edge_signal = '{signal}'"
        if position != "ALL":
            query += f" AND p.position = '{position}'"
        
        query += """
            RETURN p.name as name, 
                   p.position as position,
                   p.age as age,
                   p.team as team,
                   p.ktc_value as ktc_value,
                   p.edge_value as edge_value,
                   p.edge_score as edge_score,
                   p.edge_signal as signal
        """
        
        if signal == "BUY":
            query += " ORDER BY p.edge_score ASC"
        else:
            query += " ORDER BY p.edge_score DESC"
        
        query += f" LIMIT {limit}"
        
        return self.run_query(query)
    
    def analyze_roster(self, owner: str) -> dict:
        """Analyze a fantasy team's roster."""
        # Get roster composition
        roster_query = f"""
            MATCH (p:Player)-[:ROSTERED_BY]->(f:FantasyTeam)
            WHERE f.owner = '{owner}'
            RETURN p.name as name, 
                   p.position as position,
                   p.age as age,
                   p.ktc_value as ktc_value,
                   p.edge_value as edge_value,
                   p.edge_signal as signal
            ORDER BY p.ktc_value DESC
        """
        players = self.run_query(roster_query)
        
        # Get team info
        team_query = f"""
            MATCH (f:FantasyTeam)
            WHERE f.owner = '{owner}'
            RETURN f.team_name as team_name, f.wins as wins, f.losses as losses, f.fpts as fpts
        """
        team_info = self.run_query(team_query)
        
        # Calculate stats
        total_ktc = sum(p['ktc_value'] or 0 for p in players)
        avg_age = sum(p['age'] or 25 for p in players) / len(players) if players else 0
        
        by_position = {}
        for p in players:
            pos = p['position']
            if pos not in by_position:
                by_position[pos] = []
            by_position[pos].append(p)
        
        return {
            'team_info': team_info[0] if team_info else {},
            'total_players': len(players),
            'total_ktc_value': total_ktc,
            'average_age': round(avg_age, 1),
            'by_position': {pos: len(plist) for pos, plist in by_position.items()},
            'top_players': players[:10],
            'sell_candidates': [p for p in players if p.get('signal') == 'SELL'],
            'buy_holds': [p for p in players if p.get('signal') in ['BUY', 'HOLD']]
        }
    
    def find_trade_targets(self, from_owner: str, positions_needed: list = None, max_age: float = 26) -> list[dict]:
        """Find trade targets from a specific owner."""
        positions_needed = positions_needed or ['WR', 'TE', 'RB']
        positions_str = "', '".join(positions_needed)
        
        query = f"""
            MATCH (p:Player)-[:ROSTERED_BY]->(f:FantasyTeam)
            WHERE f.owner = '{from_owner}'
              AND p.position IN ['{positions_str}']
              AND p.age <= {max_age}
              AND p.ktc_value > 2000
            RETURN p.name as name,
                   p.position as position,
                   p.age as age,
                   p.ktc_value as ktc_value,
                   p.edge_value as edge_value,
                   p.edge_signal as signal,
                   f.wins as team_wins,
                   f.losses as team_losses
            ORDER BY p.ktc_value DESC
        """
        return self.run_query(query)


# =============================================================================
# AGENT CLASS
# =============================================================================

class DynastyEdgeAgent:
    """Conversational AI agent for dynasty fantasy football analysis."""
    
    def __init__(self):
        self.client = Anthropic(api_key=ANTHROPIC_API_KEY)
        self.neo4j = Neo4jClient(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
        self.conversation_history = []
        
        self.system_prompt = """You are Dynasty Edge, an expert AI assistant for dynasty fantasy football analysis.
        
You have access to a Neo4j graph database containing:
- Player valuations (KTC values and calculated "edge" values)
- NFL team information
- Player relationships (who targets from which QB, depth chart competition)
- Fantasy league rosters and standings
- Draft pick ownership

Your goal is to help the user maximize their roster's KTC value by:
1. Finding undervalued players (BUY signals)
2. Identifying overvalued players to sell (SELL signals)
3. Analyzing trade opportunities
4. Providing strategic roster advice

When answering:
- Use the tools to query real data, don't make up values
- Explain your reasoning based on relationships and factors
- Be specific with player names, values, and recommendations
- Consider age, situation (QB, team), and competition when evaluating players

The user is @danservfinn who manages the "Start Puffin Boy" team in the Lucid Losers league (10-team Superflex, 0.5 TE Premium)."""
    
    def execute_tool(self, tool_name: str, tool_input: dict) -> Any:
        """Execute a tool and return the result."""
        if tool_name == "cypher_query":
            try:
                results = self.neo4j.run_query(tool_input["query"])
                return json.dumps(results, default=str, indent=2)
            except Exception as e:
                return f"Error executing query: {str(e)}"
        
        elif tool_name == "get_edge_report":
            results = self.neo4j.get_edge_report(
                signal=tool_input.get("signal", "ALL"),
                position=tool_input.get("position", "ALL"),
                limit=tool_input.get("limit", 10)
            )
            return json.dumps(results, default=str, indent=2)
        
        elif tool_name == "analyze_roster":
            results = self.neo4j.analyze_roster(tool_input["owner"])
            return json.dumps(results, default=str, indent=2)
        
        elif tool_name == "find_trade_targets":
            results = self.neo4j.find_trade_targets(
                from_owner=tool_input["from_owner"],
                positions_needed=tool_input.get("positions_needed"),
                max_age=tool_input.get("max_age", 26)
            )
            return json.dumps(results, default=str, indent=2)
        
        return "Unknown tool"
    
    def chat(self, user_message: str) -> str:
        """Process a user message and return the agent's response."""
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })
        
        # Initial API call
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=self.system_prompt,
            tools=TOOLS,
            messages=self.conversation_history
        )
        
        # Process tool calls in a loop until we get a final response
        while response.stop_reason == "tool_use":
            # Extract tool use blocks
            tool_uses = [block for block in response.content if block.type == "tool_use"]
            
            # Execute tools and build results
            tool_results = []
            for tool_use in tool_uses:
                result = self.execute_tool(tool_use.name, tool_use.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": result
                })
            
            # Add assistant response and tool results to history
            self.conversation_history.append({
                "role": "assistant",
                "content": response.content
            })
            self.conversation_history.append({
                "role": "user",
                "content": tool_results
            })
            
            # Continue the conversation
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=self.system_prompt,
                tools=TOOLS,
                messages=self.conversation_history
            )
        
        # Extract final text response
        final_response = ""
        for block in response.content:
            if hasattr(block, "text"):
                final_response += block.text
        
        # Add to history
        self.conversation_history.append({
            "role": "assistant",
            "content": response.content
        })
        
        return final_response
    
    def close(self):
        """Clean up resources."""
        self.neo4j.close()


# =============================================================================
# MAIN INTERACTIVE LOOP
# =============================================================================

def main():
    """Run the interactive agent."""
    print("\n" + "=" * 60)
    print("🏈 DYNASTY EDGE - AI Agent")
    print("=" * 60)
    print("\nI'm your dynasty fantasy football analyst with access to")
    print("the graph database. Ask me anything about player values,")
    print("trade targets, or roster strategy.")
    print("\nType 'quit' to exit.\n")
    
    agent = DynastyEdgeAgent()
    
    try:
        while True:
            user_input = input("\n🧑 You: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\nGoodbye! Good luck with your trades. 🏆")
                break
            
            if not user_input:
                continue
            
            print("\n🤖 Dynasty Edge: ", end="")
            response = agent.chat(user_input)
            print(response)
    
    except KeyboardInterrupt:
        print("\n\nGoodbye!")
    
    finally:
        agent.close()


if __name__ == "__main__":
    main()
