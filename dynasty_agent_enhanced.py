#!/usr/bin/env python3
"""
Dynasty Edge - Enhanced Claude Agent with AI Data Science Team Integration

This agent combines:
1. Neo4j graph queries for relationship-based insights
2. ai-data-science-team agents for automated analysis
3. Temporal causality tracking
4. Dynamic weight adjustment based on discovered correlations

Usage:
    python dynasty_agent_enhanced.py
"""

import os
import json
from typing import Any, List
from datetime import datetime
from neo4j import GraphDatabase
from anthropic import Anthropic
from dotenv import load_dotenv

# Import our integration module
from ai_ds_team_integration import (
    DynastyDataBridge,
    DynastyAIAgents,
    AI_DS_TEAM_AVAILABLE
)

load_dotenv()

# Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


# =============================================================================
# TOOL DEFINITIONS
# =============================================================================

TOOLS = [
    # ----- NEO4J GRAPH TOOLS -----
    {
        "name": "cypher_query",
        "description": """Execute a Cypher query against the Dynasty Edge Neo4j database.
        
Available node types:
- Player: player_id, name, position, team, age, ktc_value, edge_value, edge_score, edge_signal
- Team: team_id, name, conference, division
- FantasyTeam: roster_id, owner, team_name, wins, losses, fpts
- DraftPick: pick_id, season, round, projected_slot, ktc_value
- Snapshot: temporal player data with ktc_delta, targets_per_game, etc.
- Correlation: discovered metric-to-KTC correlations with pearson_r, strength

Relationships:
- (Player)-[:PLAYS_FOR]->(Team)
- (Player)-[:TARGETS_FROM]->(Player) - WR/TE to their QB
- (Player)-[:COMPETES_WITH]->(Player) - Same position on same team
- (Player)-[:ROSTERED_BY]->(FantasyTeam)
- (Player)-[:HAD_SNAPSHOT]->(Snapshot) - Temporal data
- (Snapshot)-[:PREVIOUS]->(Snapshot) - Linked snapshots""",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A valid Cypher query"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_edge_report",
        "description": """Get players with biggest discrepancies between KTC and calculated edge values.
        Use to find buy/sell opportunities.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "signal": {"type": "string", "enum": ["BUY", "SELL", "ALL"]},
                "position": {"type": "string", "enum": ["QB", "RB", "WR", "TE", "ALL"]},
                "limit": {"type": "integer", "description": "Number of results (default 10)"}
            }
        }
    },
    {
        "name": "analyze_roster",
        "description": """Analyze a fantasy team's roster composition, age distribution, and value.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Fantasy team owner username"}
            },
            "required": ["owner"]
        }
    },
    {
        "name": "get_player_history",
        "description": """Get historical snapshots for a player showing KTC and metric changes over time.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "player_name": {"type": "string"},
                "days": {"type": "integer", "description": "Days of history (default 30)"}
            },
            "required": ["player_name"]
        }
    },
    {
        "name": "get_stored_correlations",
        "description": """Get previously discovered correlations between metrics and KTC changes.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "position": {"type": "string", "enum": ["QB", "RB", "WR", "TE", "ALL"]},
                "min_strength": {"type": "string", "enum": ["Strong", "Moderate", "Weak"]}
            }
        }
    },
    
    # ----- AI DATA SCIENCE TEAM TOOLS -----
    {
        "name": "run_feature_engineering",
        "description": """Use AI to automatically engineer dynasty-relevant features from player data.
        Creates features like years_remaining, value_per_year, QB quality scores, trend indicators.
        The AI generates Python code that you can review and incorporate.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "position": {"type": "string", "enum": ["QB", "RB", "WR", "TE"], "description": "Position to analyze"},
                "days": {"type": "integer", "description": "Days of data to use (default 30)"},
                "custom_instructions": {"type": "string", "description": "Custom feature engineering instructions"}
            }
        }
    },
    {
        "name": "discover_correlations",
        "description": """Use AI EDA agent to discover what metrics actually drive KTC value changes.
        Performs statistical correlation analysis and identifies significant predictors.
        Results are stored in Neo4j for future reference and weight adjustments.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "position": {"type": "string", "enum": ["QB", "RB", "WR", "TE"], "description": "Position to analyze"},
                "days": {"type": "integer", "description": "Days of data to analyze (default 30)"}
            }
        }
    },
    {
        "name": "train_ktc_predictor",
        "description": """Train ML models to predict KTC value changes using H2O AutoML.
        Tries hundreds of models and returns the best one with feature importance rankings.
        Use this to understand what metrics most influence KTC movements.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "position": {"type": "string", "enum": ["QB", "RB", "WR", "TE"]},
                "days": {"type": "integer", "description": "Days of training data (default 60)"},
                "max_runtime_secs": {"type": "integer", "description": "Max training time (default 60)"}
            }
        }
    },
    {
        "name": "run_full_analysis",
        "description": """Run complete analysis pipeline: Feature Engineering → Correlation Discovery → ML Training.
        Use for comprehensive analysis of what drives KTC values for a position.
        Returns actionable insights for weight adjustments.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "position": {"type": "string", "enum": ["QB", "RB", "WR", "TE"]},
                "days": {"type": "integer", "description": "Lookback period (default 30)"},
                "include_ml": {"type": "boolean", "description": "Include ML training (default True)"}
            }
        }
    },
    {
        "name": "get_generated_code",
        "description": """Get the Python code generated by the last Feature Engineering run.
        Useful for reviewing, understanding, or incorporating into your pipeline.""",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    
    # ----- WEIGHT MANAGEMENT TOOLS -----
    {
        "name": "suggest_weight_adjustment",
        "description": """Based on discovered correlations, suggest adjustments to valuation model weights.
        Compares current weights to what correlations suggest they should be.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "position": {"type": "string", "enum": ["QB", "RB", "WR", "TE", "ALL"]}
            }
        }
    },
    {
        "name": "apply_weight_change",
        "description": """Apply a weight change to the valuation model. Logs the change with reasoning.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "metric_name": {"type": "string", "description": "e.g., 'w_targets_per_game'"},
                "new_weight": {"type": "number", "description": "New weight value (0.5 to 2.0)"},
                "reason": {"type": "string", "description": "Explanation for the change"}
            },
            "required": ["metric_name", "new_weight", "reason"]
        }
    }
]


# =============================================================================
# TOOL EXECUTOR
# =============================================================================

class ToolExecutor:
    """Executes tools for the Claude agent."""
    
    def __init__(self):
        self.bridge = DynastyDataBridge(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
        
        # Initialize AI agents if available
        self.ai_agents = None
        if AI_DS_TEAM_AVAILABLE and OPENAI_API_KEY:
            try:
                self.ai_agents = DynastyAIAgents(self.bridge)
                print("✅ AI Data Science Team agents initialized")
            except Exception as e:
                print(f"⚠️  Could not initialize AI agents: {e}")
    
    def close(self):
        self.bridge.close()
    
    def execute(self, tool_name: str, tool_input: dict) -> str:
        """Execute a tool and return JSON result."""
        
        try:
            # Neo4j Graph Tools
            if tool_name == "cypher_query":
                return self._cypher_query(tool_input)
            elif tool_name == "get_edge_report":
                return self._get_edge_report(tool_input)
            elif tool_name == "analyze_roster":
                return self._analyze_roster(tool_input)
            elif tool_name == "get_player_history":
                return self._get_player_history(tool_input)
            elif tool_name == "get_stored_correlations":
                return self._get_stored_correlations(tool_input)
            
            # AI Data Science Team Tools
            elif tool_name == "run_feature_engineering":
                return self._run_feature_engineering(tool_input)
            elif tool_name == "discover_correlations":
                return self._discover_correlations(tool_input)
            elif tool_name == "train_ktc_predictor":
                return self._train_ktc_predictor(tool_input)
            elif tool_name == "run_full_analysis":
                return self._run_full_analysis(tool_input)
            elif tool_name == "get_generated_code":
                return self._get_generated_code(tool_input)
            
            # Weight Management Tools
            elif tool_name == "suggest_weight_adjustment":
                return self._suggest_weight_adjustment(tool_input)
            elif tool_name == "apply_weight_change":
                return self._apply_weight_change(tool_input)
            
            else:
                return json.dumps({"error": f"Unknown tool: {tool_name}"})
                
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    # ----- Neo4j Tools -----
    
    def _cypher_query(self, input: dict) -> str:
        query = input.get("query", "")
        df = self.bridge.query_to_dataframe(query)
        return df.to_json(orient='records', date_format='iso')
    
    def _get_edge_report(self, input: dict) -> str:
        signal = input.get("signal", "ALL")
        position = input.get("position", "ALL")
        limit = input.get("limit", 10)
        
        query = """
            MATCH (p:Player)
            WHERE p.edge_signal IS NOT NULL AND p.ktc_value > 1000
        """
        if signal != "ALL":
            query += f" AND p.edge_signal = '{signal}'"
        if position != "ALL":
            query += f" AND p.position = '{position}'"
        
        query += """
            RETURN p.name as name, p.position as position, p.age as age,
                   p.ktc_value as ktc, p.edge_value as edge_value,
                   p.edge_score as edge_score, p.edge_signal as signal
        """
        query += " ORDER BY p.edge_score DESC" if signal == "SELL" else " ORDER BY p.edge_score ASC"
        query += f" LIMIT {limit}"
        
        df = self.bridge.query_to_dataframe(query)
        return df.to_json(orient='records')
    
    def _analyze_roster(self, input: dict) -> str:
        owner = input.get("owner", "")
        
        roster_query = """
            MATCH (p:Player)-[:ROSTERED_BY]->(f:FantasyTeam)
            WHERE f.owner = $owner
            RETURN p.name as name, p.position as position, p.age as age,
                   p.ktc_value as ktc, p.edge_signal as signal
            ORDER BY p.ktc_value DESC
        """
        
        team_query = """
            MATCH (f:FantasyTeam) WHERE f.owner = $owner
            RETURN f.team_name as team_name, f.wins as wins, f.losses as losses
        """
        
        roster_df = self.bridge.query_to_dataframe(roster_query.replace("$owner", f"'{owner}'"))
        team_df = self.bridge.query_to_dataframe(team_query.replace("$owner", f"'{owner}'"))
        
        result = {
            'team_info': team_df.to_dict('records')[0] if len(team_df) > 0 else {},
            'total_ktc': int(roster_df['ktc'].sum()) if 'ktc' in roster_df else 0,
            'avg_age': round(roster_df['age'].mean(), 1) if 'age' in roster_df else 0,
            'roster': roster_df.to_dict('records'),
            'by_position': roster_df.groupby('position').size().to_dict() if 'position' in roster_df else {}
        }
        return json.dumps(result, default=str)
    
    def _get_player_history(self, input: dict) -> str:
        player_name = input.get("player_name", "")
        days = input.get("days", 30)
        
        query = f"""
            MATCH (p:Player)-[:HAD_SNAPSHOT]->(s:Snapshot)
            WHERE p.name = '{player_name}'
              AND s.date > date() - duration('P{days}D')
            RETURN s.date as date, s.ktc_value as ktc, s.ktc_delta as ktc_delta,
                   s.targets_per_game as tpg, s.ppg as ppg
            ORDER BY s.date DESC
        """
        
        df = self.bridge.query_to_dataframe(query)
        return df.to_json(orient='records', date_format='iso')
    
    def _get_stored_correlations(self, input: dict) -> str:
        position = input.get("position", "ALL")
        min_strength = input.get("min_strength", "Weak")
        
        strength_order = {'Strong': 3, 'Moderate': 2, 'Weak': 1, 'None': 0}
        min_val = strength_order.get(min_strength, 0)
        
        strengths = [s for s, v in strength_order.items() if v >= min_val]
        strengths_str = "', '".join(strengths)
        
        query = f"""
            MATCH (c:Correlation)
            WHERE c.strength IN ['{strengths_str}']
        """
        if position != "ALL":
            query += f" AND c.position = '{position}'"
        
        query += """
            RETURN c.metric_name as metric, c.position as position,
                   c.pearson_r as correlation, c.strength as strength,
                   c.p_value as p_value, c.current_weight as current_weight
            ORDER BY abs(c.pearson_r) DESC
        """
        
        df = self.bridge.query_to_dataframe(query)
        return df.to_json(orient='records')
    
    # ----- AI Data Science Team Tools -----
    
    def _run_feature_engineering(self, input: dict) -> str:
        if not self.ai_agents:
            return json.dumps({"error": "AI agents not available. Set OPENAI_API_KEY."})
        
        result_df = self.ai_agents.engineer_features(
            position=input.get("position"),
            days=input.get("days", 30),
            custom_instructions=input.get("custom_instructions")
        )
        
        return json.dumps({
            "success": True,
            "rows": len(result_df),
            "new_features": list(result_df.columns),
            "sample": result_df.head(5).to_dict('records')
        }, default=str)
    
    def _discover_correlations(self, input: dict) -> str:
        if not self.ai_agents:
            return json.dumps({"error": "AI agents not available. Set OPENAI_API_KEY."})
        
        result = self.ai_agents.discover_correlations(
            position=input.get("position"),
            days=input.get("days", 30)
        )
        
        return json.dumps(result, default=str)
    
    def _train_ktc_predictor(self, input: dict) -> str:
        if not self.ai_agents:
            return json.dumps({"error": "AI agents not available. Set OPENAI_API_KEY."})
        
        result = self.ai_agents.train_ktc_predictor(
            position=input.get("position"),
            days=input.get("days", 60),
            max_runtime_secs=input.get("max_runtime_secs", 60)
        )
        
        return json.dumps(result, default=str)
    
    def _run_full_analysis(self, input: dict) -> str:
        if not self.ai_agents:
            return json.dumps({"error": "AI agents not available. Set OPENAI_API_KEY."})
        
        result = self.ai_agents.run_full_analysis(
            position=input.get("position"),
            days=input.get("days", 30),
            include_ml=input.get("include_ml", True)
        )
        
        return json.dumps(result, default=str)
    
    def _get_generated_code(self, input: dict) -> str:
        if not self.ai_agents:
            return json.dumps({"error": "AI agents not available."})
        
        code = self.ai_agents.get_feature_engineering_code()
        return json.dumps({"code": code})
    
    # ----- Weight Management Tools -----
    
    def _suggest_weight_adjustment(self, input: dict) -> str:
        position = input.get("position", "ALL")
        
        # Get current correlations
        corr_query = f"""
            MATCH (c:Correlation)
            WHERE c.strength IN ['Strong', 'Moderate']
              AND c.p_value < 0.05
        """
        if position != "ALL":
            corr_query += f" AND c.position = '{position}'"
        
        corr_query += """
            RETURN c.metric_name as metric, c.pearson_r as r,
                   c.current_weight as current_weight, c.position as position
        """
        
        df = self.bridge.query_to_dataframe(corr_query)
        
        suggestions = []
        for _, row in df.iterrows():
            r = abs(row['r'])
            current = row.get('current_weight', 1.0) or 1.0
            
            # Suggest weight based on correlation strength
            if r >= 0.7:
                suggested = 1.4
            elif r >= 0.5:
                suggested = 1.25
            elif r >= 0.3:
                suggested = 1.1
            else:
                suggested = 1.0
            
            if abs(suggested - current) > 0.05:
                suggestions.append({
                    'metric': f"w_{row['metric']}",
                    'position': row['position'],
                    'correlation': round(row['r'], 3),
                    'current_weight': current,
                    'suggested_weight': suggested,
                    'change': round(suggested - current, 2)
                })
        
        return json.dumps({
            'position': position,
            'suggestions': sorted(suggestions, key=lambda x: abs(x['change']), reverse=True)
        })
    
    def _apply_weight_change(self, input: dict) -> str:
        metric = input.get("metric_name", "")
        new_weight = input.get("new_weight", 1.0)
        reason = input.get("reason", "Manual adjustment")
        
        # Validate weight bounds
        if not 0.5 <= new_weight <= 2.0:
            return json.dumps({"error": "Weight must be between 0.5 and 2.0"})
        
        with self.bridge.driver.session() as session:
            # Get current weight
            result = session.run("""
                MATCH (m:ModelConfig {active: true})
                RETURN m[$metric] as current_weight
            """, metric=metric)
            record = result.single()
            old_weight = record['current_weight'] if record else 1.0
            
            # Update weight
            session.run(f"""
                MATCH (m:ModelConfig {{active: true}})
                SET m.{metric} = $new_weight
            """, new_weight=new_weight)
            
            # Log the change
            session.run("""
                CREATE (wc:WeightChange {
                    change_id: $change_id,
                    date: datetime(),
                    metric_name: $metric,
                    old_weight: $old_weight,
                    new_weight: $new_weight,
                    reason: $reason,
                    suggested_by: 'claude_agent'
                })
            """, {
                'change_id': f"{metric}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                'metric': metric,
                'old_weight': old_weight,
                'new_weight': new_weight,
                'reason': reason
            })
        
        return json.dumps({
            'success': True,
            'metric': metric,
            'old_weight': old_weight,
            'new_weight': new_weight,
            'reason': reason
        })


# =============================================================================
# CLAUDE AGENT
# =============================================================================

class DynastyEdgeAgent:
    """Enhanced Claude agent with AI Data Science Team integration."""
    
    def __init__(self):
        self.client = Anthropic(api_key=ANTHROPIC_API_KEY)
        self.executor = ToolExecutor()
        self.conversation_history = []
        
        ai_status = "enabled" if self.executor.ai_agents else "disabled (set OPENAI_API_KEY)"
        
        self.system_prompt = f"""You are Dynasty Edge, an advanced AI assistant for dynasty fantasy football analysis.

You have access to TWO types of analytical capabilities:

## 1. NEO4J GRAPH DATABASE
Query player relationships, temporal snapshots, and stored insights:
- Player nodes with KTC values, edge scores, age
- Relationships: QB→WR targets, depth chart competition, team context
- Temporal snapshots tracking metric and KTC changes over time
- Stored correlations from previous analysis

## 2. AI DATA SCIENCE AGENTS (Status: {ai_status})
Automated analysis powered by ai-data-science-team:
- **Feature Engineering Agent**: Auto-generates dynasty-relevant features
- **EDA Agent**: Discovers correlations between metrics and KTC changes  
- **H2O ML Agent**: Trains predictive models for KTC movements
- **Full Pipeline**: Runs complete analysis with actionable insights

## YOUR CAPABILITIES
1. **Find undervalued players** - Query edge scores, analyze situations
2. **Discover what drives KTC** - Use AI agents to find correlations
3. **Predict KTC changes** - Train ML models on historical data
4. **Adjust valuation weights** - Based on discovered correlations
5. **Analyze trades** - Compare true value vs KTC value
6. **Track player trends** - View temporal snapshots

## WORKFLOW RECOMMENDATIONS
- For quick lookups: Use cypher_query
- For understanding KTC drivers: Use discover_correlations or run_full_analysis
- For predictive modeling: Use train_ktc_predictor
- For weight optimization: Use suggest_weight_adjustment then apply_weight_change

## USER CONTEXT
The user is @danservfinn managing "Start Puffin Boy" in Lucid Losers league.
League: 10-team Superflex, 0.5 TE Premium

Be specific with player names, values, and recommendations.
Explain your reasoning based on data and relationships.
When suggesting weight changes, show the correlation evidence."""
    
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
        
        # Process tool calls in a loop
        while response.stop_reason == "tool_use":
            tool_uses = [block for block in response.content if block.type == "tool_use"]
            
            tool_results = []
            for tool_use in tool_uses:
                print(f"  🔧 Executing: {tool_use.name}")
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
                system=self.system_prompt,
                tools=TOOLS,
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
    
    def close(self):
        self.executor.close()


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Run the enhanced interactive agent."""
    print("\n" + "=" * 70)
    print("🏈 DYNASTY EDGE - Enhanced AI Agent")
    print("   with AI Data Science Team Integration")
    print("=" * 70)
    
    print("\nCapabilities:")
    print("  • Neo4j graph queries for relationship-based insights")
    print("  • AI-powered feature engineering")
    print("  • Automated correlation discovery")
    print("  • ML model training for KTC prediction")
    print("  • Dynamic weight adjustment")
    
    print("\nExample commands:")
    print('  • "Run a full analysis on WRs to see what drives their KTC"')
    print('  • "What correlations have you discovered for RBs?"')
    print('  • "Suggest weight adjustments based on the latest correlations"')
    print('  • "Train a model to predict KTC changes for TEs"')
    print('  • "Show me BUY signals for WRs under 25"')
    
    print("\nType 'quit' to exit.\n")
    
    agent = DynastyEdgeAgent()
    
    try:
        while True:
            user_input = input("\n🧑 You: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\nGoodbye! Good luck maximizing that KTC value. 🏆")
                break
            
            if not user_input:
                continue
            
            print("\n🤖 Dynasty Edge: ", end="", flush=True)
            response = agent.chat(user_input)
            print(response)
    
    except KeyboardInterrupt:
        print("\n\nGoodbye!")
    
    finally:
        agent.close()


if __name__ == "__main__":
    main()
