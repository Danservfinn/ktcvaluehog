"""
Thoth Agent Enhanced Tools
==========================
14 specialized tools for dynasty fantasy football analysis.
"""

import json
from typing import Optional, List, Dict, Any
import pandas as pd

# =============================================================================
# TOOL DEFINITIONS
# =============================================================================

THOTH_TOOLS = [
    # ----- PLAYER QUERIES -----
    {
        "name": "get_player_profile",
        "description": """Get comprehensive player profile with all enriched data including:
        - Basic info (age, team, position)
        - KTC value and model prediction
        - Athletic profile (combine metrics)
        - Contract details (APY, guaranteed)
        - Playing time (snap %, trend)
        - Injury history
        - Buy/Sell signal and value gap""",
        "input_schema": {
            "type": "object",
            "properties": {
                "player_name": {
                    "type": "string",
                    "description": "Player name to look up"
                }
            },
            "required": ["player_name"]
        }
    },
    {
        "name": "search_players",
        "description": """Search players with flexible filters. Use for queries like:
        - 'WRs under 25 with BUY signals'
        - 'RBs with snap percentage over 70%'
        - 'Players with contract expiring'""",
        "input_schema": {
            "type": "object",
            "properties": {
                "position": {"type": "string", "enum": ["QB", "RB", "WR", "TE", "ALL"]},
                "min_age": {"type": "integer"},
                "max_age": {"type": "integer"},
                "signal": {"type": "string", "enum": ["BUY", "STRONG_BUY", "SELL", "STRONG_SELL", "HOLD", "ALL"]},
                "min_ktc": {"type": "integer"},
                "max_ktc": {"type": "integer"},
                "min_snap_pct": {"type": "number"},
                "has_combine": {"type": "boolean", "description": "Only players with combine data"},
                "limit": {"type": "integer", "default": 20}
            }
        }
    },
    {
        "name": "get_edge_report",
        "description": """Get players with biggest value discrepancies - buy low, sell high opportunities.
        Returns players sorted by value gap between model prediction and KTC market value.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "signal": {"type": "string", "enum": ["BUY", "STRONG_BUY", "SELL", "STRONG_SELL", "ALL"]},
                "position": {"type": "string", "enum": ["QB", "RB", "WR", "TE", "ALL"]},
                "limit": {"type": "integer", "default": 15}
            }
        }
    },

    # ----- ANALYSIS -----
    {
        "name": "compare_players",
        "description": """Compare multiple players side-by-side across all metrics.
        Great for trade evaluation or tier comparisons.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "player_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of player names to compare (2-5 players)"
                }
            },
            "required": ["player_names"]
        }
    },
    {
        "name": "find_trade_targets",
        "description": """Find trade targets based on roster needs or strategy.
        Can filter by position, age range, budget, and signal preference.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "position": {"type": "string", "enum": ["QB", "RB", "WR", "TE"]},
                "strategy": {"type": "string", "enum": ["rebuild", "contend", "balanced"]},
                "max_ktc": {"type": "integer", "description": "Budget ceiling"},
                "prefer_signal": {"type": "string", "enum": ["BUY", "HOLD"]},
                "limit": {"type": "integer", "default": 10}
            },
            "required": ["position"]
        }
    },
    {
        "name": "analyze_roster",
        "description": """Analyze a roster's composition, strengths, and weaknesses.
        Provides position breakdown, age analysis, and recommendations.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "player_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of player names on the roster"
                }
            },
            "required": ["player_names"]
        }
    },
    {
        "name": "assess_injury_risk",
        "description": """Assess injury risk for a player or roster.
        Uses historical injury data to flag durability concerns.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "player_name": {"type": "string"},
                "player_names": {"type": "array", "items": {"type": "string"}}
            }
        }
    },

    # ----- DISCOVERY -----
    {
        "name": "find_undervalued_athletes",
        "description": """Find athletic freaks who may be undervalued.
        Identifies players with elite combine metrics but BUY signals.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "position": {"type": "string", "enum": ["QB", "RB", "WR", "TE", "ALL"]},
                "max_forty": {"type": "number", "description": "Max 40 time (e.g., 4.5)"},
                "min_vertical": {"type": "number", "description": "Min vertical jump"},
                "limit": {"type": "integer", "default": 15}
            }
        }
    },
    {
        "name": "find_contract_mismatches",
        "description": """Find players where contract status doesn't match dynasty value.
        High paid + low KTC = sell, Low paid + high KTC = buy.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "mismatch_type": {"type": "string", "enum": ["overpaid", "underpaid", "all"]},
                "position": {"type": "string", "enum": ["QB", "RB", "WR", "TE", "ALL"]},
                "limit": {"type": "integer", "default": 15}
            }
        }
    },
    {
        "name": "get_playing_time_breakout",
        "description": """Find players with increasing snap share - potential breakout candidates.
        Rising snap trends often precede KTC increases.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "position": {"type": "string", "enum": ["QB", "RB", "WR", "TE", "ALL"]},
                "min_snap_trend": {"type": "number", "description": "Minimum snap trend % (e.g., 5)"},
                "limit": {"type": "integer", "default": 15}
            }
        }
    },

    # ----- EXPLANATION -----
    {
        "name": "explain_recommendation",
        "description": """Explain why a player has their current BUY/SELL/HOLD signal.
        Provides factor-by-factor breakdown of the model's reasoning.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "player_name": {"type": "string"}
            },
            "required": ["player_name"]
        }
    },
    {
        "name": "explain_methodology",
        "description": """Explain how the Thoth model works.
        Covers features, importance rankings, and how predictions are made.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "enum": ["features", "importance", "signals", "all"]}
            }
        }
    },
    {
        "name": "get_model_predictions",
        "description": """Get detailed ML model predictions for a player or position.
        Shows predicted value, confidence, and contributing factors.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "player_name": {"type": "string"},
                "position": {"type": "string", "enum": ["QB", "RB", "WR", "TE"]}
            }
        }
    },

    # ----- FALLBACK -----
    {
        "name": "cypher_query",
        "description": """Execute a direct Cypher query against Neo4j.
        Use as fallback for complex queries not covered by other tools.

        Available Player properties:
        - Basic: name, position, current_team, age, years_exp
        - Value: ktc_value, predicted_ktc_value, value_delta, edge_signal
        - Athletic: combine_forty, combine_vertical, combine_broad_jump, combine_cone, combine_shuttle
        - Contract: contract_apy, contract_guaranteed, contract_years
        - Playing time: total_snaps, avg_snap_pct, snap_trend, games_played
        - Injury: injury_risk_score, injuries_per_season
        - Performance: fantasy_points_season, targets, receptions, receiving_yards""",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Valid Cypher query"}
            },
            "required": ["query"]
        }
    }
]


# =============================================================================
# TOOL EXECUTOR
# =============================================================================

class ThothToolExecutor:
    """Executes Thoth agent tools against Neo4j database."""

    def __init__(self, driver):
        self.driver = driver

    def execute(self, tool_name: str, tool_input: dict) -> str:
        """Execute a tool and return JSON result."""
        try:
            method = getattr(self, f"_tool_{tool_name}", None)
            if method:
                return method(tool_input)
            else:
                return json.dumps({"error": f"Unknown tool: {tool_name}"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _query(self, cypher: str, params: dict = None) -> pd.DataFrame:
        """Execute Cypher query and return DataFrame."""
        with self.driver.session() as session:
            result = session.run(cypher, params or {})
            return pd.DataFrame([dict(r) for r in result])

    # -------------------------------------------------------------------------
    # PLAYER QUERIES
    # -------------------------------------------------------------------------

    def _tool_get_player_profile(self, input: dict) -> str:
        """Get comprehensive player profile."""
        name = input.get("player_name", "")

        query = """
            MATCH (p:Player)
            WHERE toLower(p.name) CONTAINS toLower($name)
            RETURN
                p.name as name,
                p.position as position,
                p.current_team as team,
                p.age as age,
                p.years_exp as experience,
                p.college as college,

                p.ktc_value as ktc_value,
                p.predicted_ktc_value as predicted_value,
                p.value_delta as value_gap,
                p.value_delta_pct as value_gap_pct,
                p.edge_signal as signal,

                p.combine_forty as forty,
                p.combine_vertical as vertical,
                p.combine_broad_jump as broad_jump,
                p.combine_cone as cone,
                p.combine_shuttle as shuttle,

                p.contract_apy as contract_apy,
                p.contract_guaranteed as contract_guaranteed,
                p.contract_years as contract_years,

                p.total_snaps as total_snaps,
                p.avg_snap_pct as snap_pct,
                p.snap_trend as snap_trend,
                p.games_played as games_played,

                p.injury_risk_score as injury_risk,
                p.injuries_per_season as injuries_per_season,

                p.fantasy_points_season as fantasy_points,
                p.targets as targets,
                p.receptions as receptions,
                p.receiving_yards as receiving_yards,
                p.carries as carries,
                p.rushing_yards as rushing_yards,

                p.draft_round as draft_round,
                p.draft_pick as draft_pick,
                p.draft_year as draft_year
            LIMIT 1
        """

        df = self._query(query, {"name": name})
        if df.empty:
            return json.dumps({"error": f"Player '{name}' not found"})

        return df.iloc[0].to_json()

    def _tool_search_players(self, input: dict) -> str:
        """Search players with flexible filters."""
        conditions = ["p.position IN ['QB', 'RB', 'WR', 'TE']"]
        params = {}

        if input.get("position") and input["position"] != "ALL":
            conditions.append("p.position = $position")
            params["position"] = input["position"]

        if input.get("min_age"):
            conditions.append("p.age >= $min_age")
            params["min_age"] = input["min_age"]

        if input.get("max_age"):
            conditions.append("p.age <= $max_age")
            params["max_age"] = input["max_age"]

        if input.get("signal") and input["signal"] != "ALL":
            if input["signal"] == "BUY":
                conditions.append("p.edge_signal IN ['BUY', 'STRONG_BUY']")
            elif input["signal"] == "SELL":
                conditions.append("p.edge_signal IN ['SELL', 'STRONG_SELL']")
            else:
                conditions.append("p.edge_signal = $signal")
                params["signal"] = input["signal"]

        if input.get("min_ktc"):
            conditions.append("p.ktc_value >= $min_ktc")
            params["min_ktc"] = input["min_ktc"]

        if input.get("max_ktc"):
            conditions.append("p.ktc_value <= $max_ktc")
            params["max_ktc"] = input["max_ktc"]

        if input.get("min_snap_pct"):
            conditions.append("p.avg_snap_pct >= $min_snap_pct")
            params["min_snap_pct"] = input["min_snap_pct"]

        if input.get("has_combine"):
            conditions.append("p.combine_forty IS NOT NULL")

        limit = input.get("limit", 20)

        query = f"""
            MATCH (p:Player)
            WHERE {' AND '.join(conditions)}
            RETURN p.name as name, p.position as position, p.current_team as team,
                   p.age as age, p.ktc_value as ktc_value,
                   p.predicted_ktc_value as predicted_value,
                   p.edge_signal as signal, p.avg_snap_pct as snap_pct
            ORDER BY p.ktc_value DESC
            LIMIT {limit}
        """

        df = self._query(query, params)
        return df.to_json(orient="records")

    def _tool_get_edge_report(self, input: dict) -> str:
        """Get buy/sell edge report."""
        signal = input.get("signal", "ALL")
        position = input.get("position", "ALL")
        limit = input.get("limit", 15)

        conditions = ["p.ktc_value > 500", "p.predicted_ktc_value IS NOT NULL"]

        if signal != "ALL":
            if signal in ["BUY", "STRONG_BUY"]:
                conditions.append("p.edge_signal IN ['BUY', 'STRONG_BUY']")
            else:
                conditions.append(f"p.edge_signal = '{signal}'")

        if position != "ALL":
            conditions.append(f"p.position = '{position}'")

        order = "DESC" if signal in ["BUY", "STRONG_BUY", "ALL"] else "ASC"

        query = f"""
            MATCH (p:Player)
            WHERE {' AND '.join(conditions)}
            RETURN p.name as name, p.position as position, p.current_team as team,
                   p.age as age, p.ktc_value as ktc_value,
                   p.predicted_ktc_value as predicted_value,
                   p.value_delta as value_gap,
                   p.edge_signal as signal
            ORDER BY p.value_delta {order}
            LIMIT {limit}
        """

        df = self._query(query)
        return df.to_json(orient="records")

    # -------------------------------------------------------------------------
    # ANALYSIS
    # -------------------------------------------------------------------------

    def _tool_compare_players(self, input: dict) -> str:
        """Compare multiple players."""
        names = input.get("player_names", [])
        if len(names) < 2:
            return json.dumps({"error": "Need at least 2 players to compare"})

        name_list = "', '".join(names)

        query = f"""
            MATCH (p:Player)
            WHERE toLower(p.name) IN ['{name_list.lower()}']
            RETURN p.name as name, p.position as position, p.age as age,
                   p.ktc_value as ktc_value, p.predicted_ktc_value as predicted,
                   p.edge_signal as signal, p.combine_forty as forty,
                   p.contract_apy as apy, p.avg_snap_pct as snap_pct,
                   p.fantasy_points_season as fpts, p.injury_risk_score as injury_risk
        """

        df = self._query(query)
        return df.to_json(orient="records")

    def _tool_find_trade_targets(self, input: dict) -> str:
        """Find trade targets based on criteria."""
        position = input.get("position")
        strategy = input.get("strategy", "balanced")
        max_ktc = input.get("max_ktc")
        prefer_signal = input.get("prefer_signal", "BUY")
        limit = input.get("limit", 10)

        conditions = [f"p.position = '{position}'", "p.ktc_value > 500"]

        if max_ktc:
            conditions.append(f"p.ktc_value <= {max_ktc}")

        if strategy == "rebuild":
            conditions.append("p.age <= 25")
            order = "p.age ASC, p.value_delta DESC"
        elif strategy == "contend":
            conditions.append("p.fantasy_points_season > 100")
            order = "p.fantasy_points_season DESC"
        else:
            order = "p.value_delta DESC"

        if prefer_signal == "BUY":
            conditions.append("p.edge_signal IN ['BUY', 'STRONG_BUY']")

        query = f"""
            MATCH (p:Player)
            WHERE {' AND '.join(conditions)}
            RETURN p.name as name, p.position as position, p.age as age,
                   p.ktc_value as ktc_value, p.predicted_ktc_value as predicted,
                   p.value_delta as value_gap, p.edge_signal as signal,
                   p.fantasy_points_season as fpts
            ORDER BY {order}
            LIMIT {limit}
        """

        df = self._query(query)
        return df.to_json(orient="records")

    def _tool_analyze_roster(self, input: dict) -> str:
        """Analyze a roster."""
        names = input.get("player_names", [])
        if not names:
            return json.dumps({"error": "Need player names to analyze"})

        name_list = "', '".join(names)

        query = f"""
            MATCH (p:Player)
            WHERE toLower(p.name) IN ['{name_list.lower()}']
            RETURN p.name as name, p.position as position, p.age as age,
                   p.ktc_value as ktc_value, p.edge_signal as signal,
                   p.fantasy_points_season as fpts, p.injury_risk_score as injury_risk
        """

        df = self._query(query)

        if df.empty:
            return json.dumps({"error": "No players found"})

        result = {
            "total_ktc": int(df["ktc_value"].sum()) if "ktc_value" in df else 0,
            "avg_age": round(df["age"].mean(), 1) if "age" in df else 0,
            "total_fpts": round(df["fpts"].sum(), 1) if "fpts" in df else 0,
            "position_breakdown": df["position"].value_counts().to_dict() if "position" in df else {},
            "signals": df["signal"].value_counts().to_dict() if "signal" in df else {},
            "buy_candidates": df[df["signal"].isin(["BUY", "STRONG_BUY"])]["name"].tolist() if "signal" in df else [],
            "sell_candidates": df[df["signal"].isin(["SELL", "STRONG_SELL"])]["name"].tolist() if "signal" in df else [],
            "players": df.to_dict("records")
        }

        return json.dumps(result, default=str)

    def _tool_assess_injury_risk(self, input: dict) -> str:
        """Assess injury risk."""
        player_name = input.get("player_name")
        player_names = input.get("player_names", [])

        if player_name:
            names = [player_name]
        elif player_names:
            names = player_names
        else:
            return json.dumps({"error": "Need player name(s)"})

        name_list = "', '".join(names)

        query = f"""
            MATCH (p:Player)
            WHERE toLower(p.name) IN ['{name_list.lower()}']
            RETURN p.name as name, p.position as position,
                   p.injury_risk_score as injury_risk,
                   p.injuries_per_season as injuries_per_season,
                   p.games_played as games_played
        """

        df = self._query(query)

        results = []
        for _, row in df.iterrows():
            risk = row.get("injury_risk", 0) or 0
            if risk > 60:
                assessment = "HIGH RISK - Significant injury history, apply value discount"
            elif risk > 40:
                assessment = "ELEVATED - Monitor closely, some durability concerns"
            elif risk > 20:
                assessment = "MODERATE - Typical injury exposure"
            else:
                assessment = "LOW - Generally durable"

            results.append({
                "name": row["name"],
                "injury_risk_score": risk,
                "assessment": assessment,
                "injuries_per_season": row.get("injuries_per_season"),
                "games_played": row.get("games_played")
            })

        return json.dumps(results)

    # -------------------------------------------------------------------------
    # DISCOVERY
    # -------------------------------------------------------------------------

    def _tool_find_undervalued_athletes(self, input: dict) -> str:
        """Find athletic players who are undervalued."""
        position = input.get("position", "ALL")
        max_forty = input.get("max_forty", 4.55)
        min_vertical = input.get("min_vertical")
        limit = input.get("limit", 15)

        conditions = [
            "p.combine_forty IS NOT NULL",
            f"p.combine_forty <= {max_forty}",
            "p.edge_signal IN ['BUY', 'STRONG_BUY']"
        ]

        if position != "ALL":
            conditions.append(f"p.position = '{position}'")

        if min_vertical:
            conditions.append(f"p.combine_vertical >= {min_vertical}")

        query = f"""
            MATCH (p:Player)
            WHERE {' AND '.join(conditions)}
            RETURN p.name as name, p.position as position, p.age as age,
                   p.ktc_value as ktc_value, p.value_delta as value_gap,
                   p.edge_signal as signal, p.combine_forty as forty,
                   p.combine_vertical as vertical, p.avg_snap_pct as snap_pct
            ORDER BY p.value_delta DESC
            LIMIT {limit}
        """

        df = self._query(query)
        return df.to_json(orient="records")

    def _tool_find_contract_mismatches(self, input: dict) -> str:
        """Find contract/value mismatches."""
        mismatch_type = input.get("mismatch_type", "all")
        position = input.get("position", "ALL")
        limit = input.get("limit", 15)

        conditions = ["p.contract_apy IS NOT NULL", "p.contract_apy > 0"]

        if position != "ALL":
            conditions.append(f"p.position = '{position}'")

        if mismatch_type == "overpaid":
            conditions.append("p.edge_signal IN ['SELL', 'STRONG_SELL']")
            conditions.append("p.contract_apy > 10000000")
            order = "p.contract_apy DESC"
        elif mismatch_type == "underpaid":
            conditions.append("p.edge_signal IN ['BUY', 'STRONG_BUY']")
            conditions.append("p.ktc_value > 3000")
            order = "p.value_delta DESC"
        else:
            order = "abs(p.value_delta) DESC"

        query = f"""
            MATCH (p:Player)
            WHERE {' AND '.join(conditions)}
            RETURN p.name as name, p.position as position, p.age as age,
                   p.ktc_value as ktc_value, p.contract_apy as apy,
                   p.contract_guaranteed as guaranteed,
                   p.value_delta as value_gap, p.edge_signal as signal
            ORDER BY {order}
            LIMIT {limit}
        """

        df = self._query(query)
        return df.to_json(orient="records")

    def _tool_get_playing_time_breakout(self, input: dict) -> str:
        """Find players with rising snap share."""
        position = input.get("position", "ALL")
        min_snap_trend = input.get("min_snap_trend", 5)
        limit = input.get("limit", 15)

        conditions = [
            "p.snap_trend IS NOT NULL",
            f"p.snap_trend >= {min_snap_trend}"
        ]

        if position != "ALL":
            conditions.append(f"p.position = '{position}'")

        query = f"""
            MATCH (p:Player)
            WHERE {' AND '.join(conditions)}
            RETURN p.name as name, p.position as position, p.age as age,
                   p.ktc_value as ktc_value, p.edge_signal as signal,
                   p.avg_snap_pct as snap_pct, p.snap_trend as snap_trend,
                   p.fantasy_points_season as fpts
            ORDER BY p.snap_trend DESC
            LIMIT {limit}
        """

        df = self._query(query)
        return df.to_json(orient="records")

    # -------------------------------------------------------------------------
    # EXPLANATION
    # -------------------------------------------------------------------------

    def _tool_explain_recommendation(self, input: dict) -> str:
        """Explain why a player has their signal."""
        name = input.get("player_name", "")

        query = """
            MATCH (p:Player)
            WHERE toLower(p.name) CONTAINS toLower($name)
            RETURN p.name as name, p.position as position, p.age as age,
                   p.ktc_value as ktc_value, p.predicted_ktc_value as predicted,
                   p.value_delta as value_gap, p.value_delta_pct as gap_pct,
                   p.edge_signal as signal,
                   p.contract_guaranteed as contract, p.contract_apy as apy,
                   p.avg_snap_pct as snap_pct, p.snap_trend as snap_trend,
                   p.injury_risk_score as injury_risk, p.draft_value as draft_value
            LIMIT 1
        """

        df = self._query(query, {"name": name})
        if df.empty:
            return json.dumps({"error": f"Player '{name}' not found"})

        p = df.iloc[0].to_dict()

        factors = []

        # Signal explanation
        signal = p.get("signal", "HOLD")
        gap_pct = p.get("gap_pct", 0) or 0

        if signal in ["BUY", "STRONG_BUY"]:
            factors.append(f"Model predicts {abs(gap_pct):.1f}% more value than KTC market price")
        elif signal in ["SELL", "STRONG_SELL"]:
            factors.append(f"Model predicts {abs(gap_pct):.1f}% less value than KTC market price")

        # Contributing factors
        age = p.get("age")
        position = p.get("position")
        if age and position:
            endpoints = {"QB": 40, "RB": 29, "WR": 32, "TE": 34}
            years_left = endpoints.get(position, 32) - age
            if years_left > 8:
                factors.append(f"Youth premium: {years_left} productive years estimated")
            elif years_left < 4:
                factors.append(f"Age concern: Only ~{years_left} productive years left")

        contract = p.get("contract")
        if contract and contract > 50000000:
            factors.append(f"Elite contract (${contract/1e6:.0f}M guaranteed) signals NFL confidence")
        elif contract and contract < 5000000:
            factors.append("Minimal NFL investment in guaranteed money")

        snap_pct = p.get("snap_pct")
        snap_trend = p.get("snap_trend")
        if snap_trend and snap_trend > 5:
            factors.append(f"Role expanding: Snap share up {snap_trend:.1f}% second half of season")
        elif snap_trend and snap_trend < -5:
            factors.append(f"Role declining: Snap share down {abs(snap_trend):.1f}%")

        injury = p.get("injury_risk")
        if injury and injury > 50:
            factors.append(f"Elevated injury history (risk score: {injury:.0f}/100)")

        result = {
            "player": p.get("name"),
            "signal": signal,
            "ktc_value": p.get("ktc_value"),
            "predicted_value": p.get("predicted"),
            "value_gap": p.get("value_gap"),
            "explanation": factors
        }

        return json.dumps(result, default=str)

    def _tool_explain_methodology(self, input: dict) -> str:
        """Explain model methodology."""
        topic = input.get("topic", "all")

        methodology = {
            "model_type": "H2O Gradient Boosting Machine (GBM)",
            "r_squared": 0.87,
            "rmse": 735.55,
            "training_size": 976,
            "features": {
                "contract": ["contract_guaranteed (100% importance)", "contract_total (55%)", "apy_percentile (16%)"],
                "playing_time": ["total_snaps (21%)", "snap_pct (19%)", "snap_trend (9%)"],
                "draft": ["draft_value (12%)", "draft_round"],
                "demographics": ["age", "years_exp", "years_remaining"],
                "athletic": ["combine_forty", "combine_vertical", "combine_cone", "combine_shuttle"],
                "injury": ["injury_risk_score", "injuries_per_season"]
            },
            "signal_thresholds": {
                "STRONG_BUY": "> +15% value gap",
                "BUY": "+7% to +15%",
                "HOLD": "-7% to +7%",
                "SELL": "-15% to -7%",
                "STRONG_SELL": "< -15%"
            },
            "key_insight": "Contract guaranteed money is the #1 predictor - NFL teams vote with their dollars"
        }

        if topic == "features":
            return json.dumps({"features": methodology["features"]})
        elif topic == "importance":
            return json.dumps({
                "top_features": methodology["features"]["contract"] + methodology["features"]["playing_time"]
            })
        elif topic == "signals":
            return json.dumps({"signal_thresholds": methodology["signal_thresholds"]})
        else:
            return json.dumps(methodology)

    def _tool_get_model_predictions(self, input: dict) -> str:
        """Get model predictions."""
        player_name = input.get("player_name")
        position = input.get("position")

        if player_name:
            query = """
                MATCH (p:Player)
                WHERE toLower(p.name) CONTAINS toLower($name)
                RETURN p.name as name, p.position as position,
                       p.ktc_value as ktc_value, p.predicted_ktc_value as predicted,
                       p.value_delta as value_gap, p.value_delta_pct as gap_pct,
                       p.edge_signal as signal
                LIMIT 1
            """
            df = self._query(query, {"name": player_name})
        elif position:
            query = f"""
                MATCH (p:Player)
                WHERE p.position = '{position}' AND p.predicted_ktc_value IS NOT NULL
                RETURN p.name as name, p.position as position,
                       p.ktc_value as ktc_value, p.predicted_ktc_value as predicted,
                       p.value_delta as value_gap, p.edge_signal as signal
                ORDER BY p.ktc_value DESC
                LIMIT 20
            """
            df = self._query(query)
        else:
            return json.dumps({"error": "Need player_name or position"})

        return df.to_json(orient="records")

    # -------------------------------------------------------------------------
    # FALLBACK
    # -------------------------------------------------------------------------

    def _tool_cypher_query(self, input: dict) -> str:
        """Execute direct Cypher query."""
        query = input.get("query", "")
        df = self._query(query)
        return df.to_json(orient="records")
