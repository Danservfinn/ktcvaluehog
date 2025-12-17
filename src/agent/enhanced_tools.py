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
    {
        "name": "find_breakout_candidates",
        "description": """Find players with high breakout potential based on ML model scores.
        Uses 25-year trained model analyzing trajectory, efficiency, ceiling, and situation.
        Great for dynasty rebuilds and finding buy-low targets before value rises.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "position": {"type": "string", "enum": ["QB", "RB", "WR", "TE", "ALL"]},
                "min_breakout_score": {"type": "number", "description": "Minimum breakout score (0-100, default 60)"},
                "max_age": {"type": "integer", "description": "Maximum age to filter (default 27)"},
                "sort_by": {"type": "string", "enum": ["breakout_score", "value_rise_score", "trajectory_score", "rise_probability"], "description": "Which score to sort by"},
                "limit": {"type": "integer", "default": 15}
            }
        }
    },
    {
        "name": "get_production_projections",
        "description": """Get ML-projected fantasy production for 2025 season.
        Uses 25-year historical model trained on 7,171 season-over-season pairs.
        Returns predicted fantasy points, projected PPG, and confidence levels.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "position": {"type": "string", "enum": ["QB", "RB", "WR", "TE", "ALL"]},
                "min_projected_ppg": {"type": "number", "description": "Minimum projected PPG threshold"},
                "min_confidence": {"type": "number", "description": "Minimum production confidence (0-100)"},
                "limit": {"type": "integer", "default": 20}
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

    # ----- COLLEGE/DEVY TOOLS -----
    {
        "name": "get_prospect_profile",
        "description": """Get comprehensive profile for a college prospect/devy player including:
        - Recruiting data (stars, ranking, college)
        - College stats (dominator rating, breakout age)
        - Athletic profile (combine metrics, speed score)
        - KTC devy value and trend
        - Prospect score and NFL comparison profile""",
        "input_schema": {
            "type": "object",
            "properties": {
                "prospect_name": {
                    "type": "string",
                    "description": "Name of the college prospect"
                }
            },
            "required": ["prospect_name"]
        }
    },
    {
        "name": "search_prospects",
        "description": """Search devy prospects with flexible filters. Use for queries like:
        - 'Top WR prospects in 2025 draft class'
        - '5-star recruits with high dominator ratings'
        - 'Prospects with elite speed scores'""",
        "input_schema": {
            "type": "object",
            "properties": {
                "position": {"type": "string", "enum": ["QB", "RB", "WR", "TE", "ALL"]},
                "min_stars": {"type": "integer", "description": "Minimum recruiting stars (1-5)"},
                "draft_class": {"type": "integer", "description": "Expected draft year"},
                "min_dominator": {"type": "number", "description": "Minimum dominator rating"},
                "max_breakout_age": {"type": "number", "description": "Maximum breakout age"},
                "min_speed_score": {"type": "number", "description": "Minimum speed score"},
                "college": {"type": "string", "description": "College/team filter"},
                "conference": {"type": "string", "description": "Conference filter (SEC, Big Ten, etc.)"},
                "limit": {"type": "integer", "default": 20}
            }
        }
    },
    {
        "name": "get_top_devy_prospects",
        "description": """Get top dynasty devy prospects ranked by KTC devy value or prospect score.
        Great for devy drafts and rookie draft preparation.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "position": {"type": "string", "enum": ["QB", "RB", "WR", "TE", "ALL"]},
                "rank_by": {"type": "string", "enum": ["ktc_value", "prospect_score", "dominator_rating", "athleticism"], "default": "ktc_value"},
                "draft_class": {"type": "integer", "description": "Filter to specific draft class"},
                "limit": {"type": "integer", "default": 25}
            }
        }
    },
    {
        "name": "compare_prospect_to_nfl_comps",
        "description": """Compare a prospect's profile to similar NFL players.
        Uses recruiting, college production, and athletic metrics to find NFL comps.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "prospect_name": {
                    "type": "string",
                    "description": "Name of the prospect to find comps for"
                },
                "comp_count": {"type": "integer", "default": 5}
            },
            "required": ["prospect_name"]
        }
    },
    {
        "name": "find_college_breakout_profiles",
        "description": """Find college players with profiles that historically predict NFL success:
        - Early breakout age (<20 years old)
        - High dominator rating (>30%)
        - Elite athleticism
        Use to identify undervalued devy prospects.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "position": {"type": "string", "enum": ["QB", "RB", "WR", "TE", "ALL"]},
                "min_prospect_score": {"type": "number", "default": 70},
                "limit": {"type": "integer", "default": 15}
            }
        }
    },
    {
        "name": "predict_rookie_ktc",
        "description": """Predict future KTC value for a prospect based on draft capital and profile.
        Uses historical draft pick to KTC correlations.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "prospect_name": {"type": "string"},
                "expected_draft_round": {"type": "integer", "description": "Expected draft round (1-7)"},
                "expected_draft_pick": {"type": "integer", "description": "Expected overall pick"}
            },
            "required": ["prospect_name"]
        }
    },
    {
        "name": "get_college_production_leaders",
        "description": """Get college players leading in key production metrics.
        Useful for identifying breakout college performers.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "season": {"type": "integer", "description": "College season year"},
                "stat": {"type": "string", "enum": ["rec_yards", "rec_tds", "dominator_rating", "rush_yards", "pass_yards"]},
                "position": {"type": "string", "enum": ["QB", "RB", "WR", "TE", "ALL"]},
                "limit": {"type": "integer", "default": 20}
            },
            "required": ["season"]
        }
    },
    {
        "name": "get_prospect_value_trend",
        "description": """Get KTC devy value history for a prospect to identify rising/falling values.
        Useful for timing devy trades.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "prospect_name": {"type": "string"}
            },
            "required": ["prospect_name"]
        }
    },

    # ----- 2025 PRODUCTION TOOLS -----
    {
        "name": "get_2025_production_leaders",
        "description": """Get 2025 fantasy production leaders by position.
        Shows PPG, total points, and comparison to KTC value.
        Great for identifying who's actually producing this season.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "position": {"type": "string", "enum": ["QB", "RB", "WR", "TE", "ALL"]},
                "stat": {"type": "string", "enum": ["ppg_ppr", "total_points", "targets", "receptions"], "default": "ppg_ppr"},
                "limit": {"type": "integer", "default": 20}
            }
        }
    },
    {
        "name": "get_player_production_edge",
        "description": """Get detailed 2025 production edge analysis for a specific player.
        Compares actual production to KTC value, identifies buy/sell signals,
        shows weekly performance trend and production efficiency.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "player_name": {"type": "string", "description": "Player to analyze"}
            },
            "required": ["player_name"]
        }
    },
    {
        "name": "find_2025_buy_targets",
        "description": """Find players outperforming their KTC value in 2025.
        These are undervalued based on actual production - buy low opportunities.
        Uses production efficiency and positional rank discrepancy.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "position": {"type": "string", "enum": ["QB", "RB", "WR", "TE", "ALL"]},
                "min_edge_score": {"type": "number", "description": "Minimum edge score (default 15)"},
                "limit": {"type": "integer", "default": 15}
            }
        }
    },
    {
        "name": "find_2025_sell_candidates",
        "description": """Find players underperforming their KTC value in 2025.
        These are overvalued based on actual production - sell high opportunities.
        Identifies players whose value may regress.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "position": {"type": "string", "enum": ["QB", "RB", "WR", "TE", "ALL"]},
                "max_edge_score": {"type": "number", "description": "Maximum edge score (default -15)"},
                "limit": {"type": "integer", "default": 15}
            }
        }
    },
    {
        "name": "get_2025_usage_trends",
        "description": """Find players with rising or falling snap share in 2025.
        Rising snap share often precedes fantasy breakouts and KTC increases.
        Falling snap share may signal sell-high opportunities.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "position": {"type": "string", "enum": ["QB", "RB", "WR", "TE", "ALL"]},
                "trend": {"type": "string", "enum": ["rising", "falling", "all"], "default": "rising"},
                "min_snap_change": {"type": "number", "description": "Minimum snap share change % (default 10)"},
                "limit": {"type": "integer", "default": 15}
            }
        }
    },
    {
        "name": "get_weekly_breakdown",
        "description": """Get week-by-week fantasy point breakdown for a player in 2025.
        Shows performance consistency, ceiling/floor, and recent trend.
        Useful for evaluating player reliability and trajectory.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "player_name": {"type": "string", "description": "Player to analyze"}
            },
            "required": ["player_name"]
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
        - Performance: fantasy_points_season, targets, receptions, receiving_yards

        Available Prospect properties:
        - Basic: name, position, college, recruiting_class
        - Recruiting: stars, recruiting_rating, national_rank
        - College: dominator_rating, breakout_age, peak_dominator_rating
        - Athletic: speed_score, burst_score, athleticism_score, forty_yard
        - Value: ktc_devy_value, ktc_devy_rank, prospect_score""",
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
                p.draft_year as draft_year,

                // ML Breakout Scores (25-year model)
                p.breakout_score as breakout_score,
                p.trajectory_score as trajectory_score,
                p.efficiency_gap as efficiency_gap,
                p.ceiling_ratio as ceiling_ratio,
                p.athletic_upside as athletic_upside,
                p.situation_score as situation_score,

                // ML Value Rise Predictions
                p.value_rise_score as value_rise_score,
                p.rise_probability as rise_probability,
                p.predicted_value_gap as ml_value_gap,

                // ML Production Predictions (2025)
                p.predicted_fpts_next_season as predicted_fpts_2025,
                p.projected_ppg_next_season as projected_ppg_2025,
                p.production_confidence as production_confidence
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

    def _tool_find_breakout_candidates(self, input: dict) -> str:
        """Find players with high breakout potential based on ML scores."""
        position = input.get("position", "ALL")
        min_breakout = input.get("min_breakout_score", 60)
        max_age = input.get("max_age", 27)
        sort_by = input.get("sort_by", "breakout_score")
        limit = input.get("limit", 15)

        conditions = [
            "p.breakout_score IS NOT NULL",
            f"p.breakout_score >= {min_breakout}",
            f"p.age <= {max_age}"
        ]

        if position != "ALL":
            conditions.append(f"p.position = '{position}'")

        # Map sort_by to actual property
        sort_map = {
            "breakout_score": "p.breakout_score",
            "value_rise_score": "p.value_rise_score",
            "trajectory_score": "p.trajectory_score",
            "rise_probability": "p.rise_probability"
        }
        order_col = sort_map.get(sort_by, "p.breakout_score")

        query = f"""
            MATCH (p:Player)
            WHERE {' AND '.join(conditions)}
            RETURN p.name as name, p.position as position, p.age as age,
                   p.ktc_value as ktc_value, p.edge_signal as signal,
                   p.breakout_score as breakout_score,
                   p.trajectory_score as trajectory_score,
                   p.efficiency_gap as efficiency_gap,
                   p.ceiling_ratio as ceiling_ratio,
                   p.value_rise_score as value_rise_score,
                   p.rise_probability as rise_probability
            ORDER BY {order_col} DESC
            LIMIT {limit}
        """

        df = self._query(query)
        return df.to_json(orient="records")

    def _tool_get_production_projections(self, input: dict) -> str:
        """Get ML-projected fantasy production for 2025 season."""
        position = input.get("position", "ALL")
        min_ppg = input.get("min_projected_ppg")
        min_confidence = input.get("min_confidence")
        limit = input.get("limit", 20)

        conditions = [
            "p.predicted_fpts_next_season IS NOT NULL"
        ]

        if position != "ALL":
            conditions.append(f"p.position = '{position}'")

        if min_ppg:
            conditions.append(f"p.projected_ppg_next_season >= {min_ppg}")

        if min_confidence:
            conditions.append(f"p.production_confidence >= {min_confidence}")

        query = f"""
            MATCH (p:Player)
            WHERE {' AND '.join(conditions)}
            RETURN p.name as name, p.position as position, p.age as age,
                   p.ktc_value as ktc_value, p.edge_signal as signal,
                   p.predicted_fpts_next_season as projected_fpts_2025,
                   p.projected_ppg_next_season as projected_ppg_2025,
                   p.production_confidence as confidence,
                   p.breakout_score as breakout_score
            ORDER BY p.predicted_fpts_next_season DESC
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
    # COLLEGE/DEVY TOOLS
    # -------------------------------------------------------------------------

    def _tool_get_prospect_profile(self, input: dict) -> str:
        """Get comprehensive prospect profile."""
        name = input.get("prospect_name", "")

        query = """
            MATCH (p:Prospect)
            WHERE toLower(p.name) CONTAINS toLower($name)

            OPTIONAL MATCH (p)-[:HAS_DEVY_VALUE]->(d:DevySnapshot)
            WITH p, d ORDER BY d.date DESC
            WITH p, collect(d)[0] as latest_devy

            OPTIONAL MATCH (p)-[:HAS_COMBINE]->(c:CombineResult)
            OPTIONAL MATCH (p)-[:HAS_COLLEGE_STATS]->(s:CollegeStats)
            WITH p, latest_devy, c, collect(s) as all_stats

            RETURN
                p.name as name,
                p.position as position,
                p.college as college,
                p.recruiting_class as recruiting_class,

                // Recruiting
                p.stars as stars,
                p.recruiting_rating as recruiting_rating,
                p.national_rank as national_rank,
                p.position_rank as position_rank,
                p.state as state,

                // College Production
                p.peak_dominator_rating as peak_dominator,
                p.breakout_age as breakout_age,
                [s IN all_stats | {season: s.season, rec_yards: s.rec_yards, rec_tds: s.rec_tds, dominator: s.dominator_rating}] as college_stats,

                // Athletic
                c.forty_yard as forty,
                c.vertical_jump as vertical,
                c.broad_jump as broad_jump,
                c.three_cone as three_cone,
                c.shuttle as shuttle,
                c.speed_score as speed_score,
                c.burst_score as burst_score,
                p.athleticism_score as athleticism_score,

                // Draft
                p.draft_year as draft_year,
                p.draft_round as draft_round,
                p.draft_pick as draft_pick,
                p.was_drafted as was_drafted,

                // Value
                latest_devy.ktc_devy_value as ktc_devy_value,
                latest_devy.ktc_devy_rank as ktc_devy_rank,
                p.prospect_score as prospect_score

            LIMIT 1
        """

        df = self._query(query, {"name": name})
        if df.empty:
            return json.dumps({"error": f"Prospect '{name}' not found"})

        return df.iloc[0].to_json()

    def _tool_search_prospects(self, input: dict) -> str:
        """Search prospects with filters."""
        conditions = []
        params = {}

        if input.get("position") and input["position"] != "ALL":
            conditions.append("p.position = $position")
            params["position"] = input["position"]

        if input.get("min_stars"):
            conditions.append("p.stars >= $min_stars")
            params["min_stars"] = input["min_stars"]

        if input.get("draft_class"):
            # Estimate draft class from recruiting class (typically recruit year + 3-4)
            conditions.append("(p.recruiting_class + 3 = $draft_class OR p.recruiting_class + 4 = $draft_class)")
            params["draft_class"] = input["draft_class"]

        if input.get("min_dominator"):
            conditions.append("p.peak_dominator_rating >= $min_dominator")
            params["min_dominator"] = input["min_dominator"]

        if input.get("max_breakout_age"):
            conditions.append("p.breakout_age <= $max_breakout_age")
            params["max_breakout_age"] = input["max_breakout_age"]

        if input.get("min_speed_score"):
            conditions.append("p.speed_score >= $min_speed_score")
            params["min_speed_score"] = input["min_speed_score"]

        if input.get("college"):
            conditions.append("toLower(p.college) CONTAINS toLower($college)")
            params["college"] = input["college"]

        limit = input.get("limit", 20)
        where_clause = " AND ".join(conditions) if conditions else "true"

        query = f"""
            MATCH (p:Prospect)
            WHERE {where_clause}

            OPTIONAL MATCH (p)-[:HAS_DEVY_VALUE]->(d:DevySnapshot)
            WITH p, d ORDER BY d.date DESC
            WITH p, collect(d)[0] as latest_devy

            RETURN p.name as name, p.position as position, p.college as college,
                   p.recruiting_class as recruit_year, p.stars as stars,
                   p.peak_dominator_rating as dominator,
                   p.breakout_age as breakout_age,
                   p.speed_score as speed_score,
                   latest_devy.ktc_devy_value as ktc_value,
                   p.prospect_score as prospect_score
            ORDER BY latest_devy.ktc_devy_value DESC NULLS LAST
            LIMIT {limit}
        """

        df = self._query(query, params)
        return df.to_json(orient="records")

    def _tool_get_top_devy_prospects(self, input: dict) -> str:
        """Get top devy prospects."""
        position = input.get("position", "ALL")
        rank_by = input.get("rank_by", "ktc_value")
        draft_class = input.get("draft_class")
        limit = input.get("limit", 25)

        conditions = []
        params = {}

        if position != "ALL":
            conditions.append("p.position = $position")
            params["position"] = position

        if draft_class:
            conditions.append("(p.recruiting_class + 3 = $draft_class OR p.recruiting_class + 4 = $draft_class)")
            params["draft_class"] = draft_class

        where_clause = " AND ".join(conditions) if conditions else "true"

        # Map rank_by to order clause
        order_map = {
            "ktc_value": "latest_devy.ktc_devy_value DESC NULLS LAST",
            "prospect_score": "p.prospect_score DESC NULLS LAST",
            "dominator_rating": "p.peak_dominator_rating DESC NULLS LAST",
            "athleticism": "p.athleticism_score DESC NULLS LAST"
        }
        order = order_map.get(rank_by, order_map["ktc_value"])

        query = f"""
            MATCH (p:Prospect)
            WHERE {where_clause}

            OPTIONAL MATCH (p)-[:HAS_DEVY_VALUE]->(d:DevySnapshot)
            WITH p, d ORDER BY d.date DESC
            WITH p, collect(d)[0] as latest_devy

            RETURN p.name as name, p.position as position, p.college as college,
                   p.recruiting_class as recruit_year, p.stars as stars,
                   round(p.peak_dominator_rating, 1) as dominator,
                   p.breakout_age as breakout_age,
                   round(p.speed_score, 1) as speed_score,
                   round(p.athleticism_score, 1) as athleticism,
                   latest_devy.ktc_devy_value as ktc_value,
                   latest_devy.ktc_devy_rank as ktc_rank,
                   round(p.prospect_score, 1) as prospect_score
            ORDER BY {order}
            LIMIT {limit}
        """

        df = self._query(query, params)
        return df.to_json(orient="records")

    def _tool_compare_prospect_to_nfl_comps(self, input: dict) -> str:
        """Find NFL player comparisons for a prospect."""
        name = input.get("prospect_name", "")
        comp_count = input.get("comp_count", 5)

        # First get prospect profile
        prospect_query = """
            MATCH (p:Prospect)
            WHERE toLower(p.name) CONTAINS toLower($name)
            OPTIONAL MATCH (p)-[:HAS_COMBINE]->(c:CombineResult)
            RETURN p.name as name, p.position as position,
                   p.stars as stars, p.recruiting_rating as rating,
                   p.peak_dominator_rating as dominator,
                   p.breakout_age as breakout_age,
                   c.speed_score as speed_score,
                   c.forty_yard as forty
            LIMIT 1
        """

        prospect_df = self._query(prospect_query, {"name": name})
        if prospect_df.empty:
            return json.dumps({"error": f"Prospect '{name}' not found"})

        prospect = prospect_df.iloc[0]

        # Find NFL players with similar profiles
        comp_query = """
            MATCH (pl:Player)
            WHERE pl.position = $position
              AND pl.college IS NOT NULL

            // Use college profile for drafted NFL players
            OPTIONAL MATCH (pl)<-[:BECAME_NFL_PLAYER]-(pr:Prospect)

            WITH pl, pr,
                 // Calculate similarity score
                 CASE WHEN pr.stars IS NOT NULL AND $stars IS NOT NULL
                      THEN 1 - abs(pr.stars - $stars) / 5.0
                      ELSE 0.5 END as star_sim,
                 CASE WHEN pr.peak_dominator_rating IS NOT NULL AND $dominator IS NOT NULL
                      THEN 1 - abs(pr.peak_dominator_rating - $dominator) / 50.0
                      ELSE 0.5 END as dom_sim,
                 CASE WHEN pl.combine_forty IS NOT NULL AND $forty IS NOT NULL
                      THEN 1 - abs(pl.combine_forty - $forty) / 0.5
                      ELSE 0.5 END as forty_sim

            WITH pl, pr, (star_sim * 0.3 + dom_sim * 0.4 + forty_sim * 0.3) as similarity
            WHERE similarity > 0.5

            RETURN pl.name as nfl_comp, pl.position as position,
                   pl.current_team as team, pl.age as age,
                   pl.ktc_value as ktc_value,
                   pr.stars as college_stars, pr.peak_dominator_rating as college_dominator,
                   pl.combine_forty as forty,
                   round(similarity * 100, 1) as similarity_pct,
                   pl.fantasy_points_season as fpts
            ORDER BY similarity DESC
            LIMIT $limit
        """

        comp_df = self._query(comp_query, {
            "position": prospect.get("position"),
            "stars": prospect.get("stars"),
            "dominator": prospect.get("dominator"),
            "forty": prospect.get("forty"),
            "limit": comp_count
        })

        result = {
            "prospect": prospect.to_dict(),
            "nfl_comps": comp_df.to_dict("records") if not comp_df.empty else []
        }

        return json.dumps(result, default=str)

    def _tool_find_college_breakout_profiles(self, input: dict) -> str:
        """Find prospects with breakout profile indicators."""
        position = input.get("position", "ALL")
        min_score = input.get("min_prospect_score", 70)
        limit = input.get("limit", 15)

        conditions = [f"p.prospect_score >= {min_score}"]

        if position != "ALL":
            conditions.append(f"p.position = '{position}'")

        where_clause = " AND ".join(conditions)

        query = f"""
            MATCH (p:Prospect)
            WHERE {where_clause}

            OPTIONAL MATCH (p)-[:HAS_DEVY_VALUE]->(d:DevySnapshot)
            WITH p, d ORDER BY d.date DESC
            WITH p, collect(d)[0] as latest_devy

            // Flag breakout indicators
            WITH p, latest_devy,
                 CASE WHEN p.breakout_age < 20 THEN 'EARLY_BREAKOUT' ELSE '' END as early_breakout,
                 CASE WHEN p.peak_dominator_rating > 30 THEN 'ELITE_DOMINATOR' ELSE '' END as elite_dom,
                 CASE WHEN p.speed_score > 100 THEN 'ELITE_ATHLETE' ELSE '' END as elite_athlete

            RETURN p.name as name, p.position as position, p.college as college,
                   p.recruiting_class as recruit_year, p.stars as stars,
                   round(p.prospect_score, 1) as prospect_score,
                   round(p.peak_dominator_rating, 1) as dominator,
                   p.breakout_age as breakout_age,
                   round(p.speed_score, 1) as speed_score,
                   latest_devy.ktc_devy_value as ktc_value,
                   [x IN [early_breakout, elite_dom, elite_athlete] WHERE x <> ''] as breakout_flags
            ORDER BY p.prospect_score DESC
            LIMIT {limit}
        """

        df = self._query(query)
        return df.to_json(orient="records")

    def _tool_predict_rookie_ktc(self, input: dict) -> str:
        """Predict rookie KTC value based on draft capital."""
        name = input.get("prospect_name", "")
        expected_round = input.get("expected_draft_round")
        expected_pick = input.get("expected_draft_pick")

        # Draft pick to KTC baseline mapping (from historical data)
        pick_to_ktc = {
            (1, 1): 9500, (1, 5): 8500, (1, 10): 7500, (1, 15): 6500,
            (1, 20): 5500, (1, 25): 4800, (1, 32): 4200,
            (2, 1): 3800, (2, 16): 3200, (2, 32): 2800,
            (3, 1): 2500, (3, 32): 2000,
            (4, 1): 1800, (5, 1): 1500, (6, 1): 1200, (7, 1): 1000
        }

        # Get prospect profile
        query = """
            MATCH (p:Prospect)
            WHERE toLower(p.name) CONTAINS toLower($name)
            OPTIONAL MATCH (p)-[:HAS_DEVY_VALUE]->(d:DevySnapshot)
            WITH p, d ORDER BY d.date DESC
            WITH p, collect(d)[0] as latest_devy
            RETURN p.name as name, p.position as position, p.college as college,
                   p.stars as stars, p.peak_dominator_rating as dominator,
                   p.prospect_score as prospect_score,
                   latest_devy.ktc_devy_value as current_devy_value
            LIMIT 1
        """

        df = self._query(query, {"name": name})
        if df.empty:
            return json.dumps({"error": f"Prospect '{name}' not found"})

        prospect = df.iloc[0]

        # Estimate KTC based on draft position
        base_ktc = 3000  # Default if no draft info
        if expected_pick and expected_round:
            # Find closest pick mapping
            closest_key = min(pick_to_ktc.keys(),
                            key=lambda x: abs(x[0] - expected_round) * 100 + abs(x[1] - expected_pick))
            base_ktc = pick_to_ktc[closest_key]

            # Adjust for pick difference
            pick_diff = expected_pick - closest_key[1]
            if expected_round == 1:
                base_ktc -= pick_diff * 100
            else:
                base_ktc -= pick_diff * 30
        elif expected_round:
            round_baselines = {1: 6000, 2: 3200, 3: 2200, 4: 1700, 5: 1400, 6: 1100, 7: 900}
            base_ktc = round_baselines.get(expected_round, 2000)

        # Apply profile adjustments
        prospect_score = prospect.get("prospect_score") or 50
        profile_multiplier = 0.8 + (prospect_score / 100) * 0.4  # 0.8 to 1.2

        predicted_ktc = int(base_ktc * profile_multiplier)

        result = {
            "prospect": prospect.get("name"),
            "position": prospect.get("position"),
            "college": prospect.get("college"),
            "current_devy_value": prospect.get("current_devy_value"),
            "expected_draft_round": expected_round,
            "expected_draft_pick": expected_pick,
            "predicted_rookie_ktc": predicted_ktc,
            "profile_multiplier": round(profile_multiplier, 2),
            "prospect_score": round(prospect_score, 1),
            "confidence": "HIGH" if expected_pick and expected_pick <= 32 else "MEDIUM"
        }

        return json.dumps(result, default=str)

    def _tool_get_college_production_leaders(self, input: dict) -> str:
        """Get college production leaders by stat."""
        season = input.get("season", 2024)
        stat = input.get("stat", "rec_yards")
        position = input.get("position", "ALL")
        limit = input.get("limit", 20)

        stat_map = {
            "rec_yards": "s.rec_yards",
            "rec_tds": "s.rec_tds",
            "dominator_rating": "s.dominator_rating",
            "rush_yards": "s.rush_yards",
            "pass_yards": "s.pass_yards"
        }

        order_col = stat_map.get(stat, stat_map["rec_yards"])

        conditions = [f"s.season = {season}"]
        if position != "ALL":
            conditions.append(f"p.position = '{position}'")

        where_clause = " AND ".join(conditions)

        query = f"""
            MATCH (p:Prospect)-[:HAS_COLLEGE_STATS]->(s:CollegeStats)
            WHERE {where_clause}

            OPTIONAL MATCH (p)-[:HAS_DEVY_VALUE]->(d:DevySnapshot)
            WITH p, s, d ORDER BY d.date DESC
            WITH p, s, collect(d)[0] as latest_devy

            RETURN p.name as name, p.position as position, s.team as college,
                   s.rec_yards as rec_yards, s.rec_tds as rec_tds,
                   round(s.dominator_rating, 1) as dominator,
                   s.rush_yards as rush_yards, s.pass_yards as pass_yards,
                   latest_devy.ktc_devy_value as ktc_value
            ORDER BY {order_col} DESC NULLS LAST
            LIMIT {limit}
        """

        df = self._query(query)
        return df.to_json(orient="records")

    def _tool_get_prospect_value_trend(self, input: dict) -> str:
        """Get KTC devy value history for a prospect."""
        name = input.get("prospect_name", "")

        query = """
            MATCH (p:Prospect)-[:HAS_DEVY_VALUE]->(d:DevySnapshot)
            WHERE toLower(p.name) CONTAINS toLower($name)

            WITH p, d
            ORDER BY d.date ASC

            WITH p, collect({
                date: toString(d.date),
                value: d.ktc_devy_value,
                rank: d.ktc_devy_rank
            }) as history

            // Calculate trend
            WITH p, history,
                 history[0].value as first_value,
                 history[size(history)-1].value as last_value

            RETURN p.name as name, p.position as position, p.college as college,
                   history as value_history,
                   first_value as earliest_value,
                   last_value as current_value,
                   CASE WHEN first_value > 0
                        THEN round((last_value - first_value) / first_value * 100, 1)
                        ELSE 0 END as value_change_pct,
                   size(history) as data_points
        """

        df = self._query(query, {"name": name})
        if df.empty:
            return json.dumps({"error": f"No value history found for '{name}'"})

        result = df.iloc[0].to_dict()

        # Determine trend
        change_pct = result.get("value_change_pct", 0)
        if change_pct > 10:
            result["trend"] = "RISING"
        elif change_pct < -10:
            result["trend"] = "FALLING"
        else:
            result["trend"] = "STABLE"

        return json.dumps(result, default=str)

    # -------------------------------------------------------------------------
    # 2025 PRODUCTION TOOLS
    # -------------------------------------------------------------------------

    def _tool_get_2025_production_leaders(self, input: dict) -> str:
        """Get 2025 fantasy production leaders."""
        position = input.get("position", "ALL")
        stat = input.get("stat", "ppg_ppr")
        limit = input.get("limit", 20)

        stat_map = {
            "ppg_ppr": "ss.ppg_ppr",
            "total_points": "ss.total_fantasy_points_ppr",
            "targets": "ss.targets",
            "receptions": "ss.receptions"
        }
        order_col = stat_map.get(stat, stat_map["ppg_ppr"])

        conditions = ["ss.season = 2025", "ss.games >= 3"]
        if position != "ALL":
            conditions.append(f"ss.position = '{position}'")

        query = f"""
            MATCH (ss:SeasonStats)
            WHERE {' AND '.join(conditions)}
            OPTIONAL MATCH (p:Player)
            WHERE toLower(p.name) = toLower(ss.player_name)
            RETURN ss.player_name as player, ss.position as position,
                   ss.team as team, ss.games as games,
                   round(ss.ppg_ppr, 1) as ppg,
                   round(ss.total_fantasy_points_ppr, 1) as total_points,
                   ss.targets as targets, ss.receptions as receptions,
                   ss.receiving_yards as rec_yards,
                   p.ktc_value as ktc_value,
                   p.production_signal as signal,
                   round(p.production_edge_score, 1) as edge_score
            ORDER BY {order_col} DESC
            LIMIT {limit}
        """

        df = self._query(query)
        return df.to_json(orient="records")

    def _tool_get_player_production_edge(self, input: dict) -> str:
        """Get detailed 2025 production edge analysis for a player."""
        name = input.get("player_name", "")

        query = """
            MATCH (p:Player)-[:HAD_SEASON]->(ss:SeasonStats {season: 2025})
            WHERE toLower(p.name) CONTAINS toLower($name)

            OPTIONAL MATCH (p)-[:HAD_WEEK]->(ws:WeeklyStats {season: 2025})
            WITH p, ss, ws ORDER BY ws.week
            WITH p, ss, collect({week: ws.week, points: ws.fantasy_points_ppr,
                                 targets: ws.targets, opponent: ws.opponent}) as weekly

            RETURN p.name as player, p.position as position, p.current_team as team,
                   p.age as age,
                   ss.games as games,
                   round(ss.ppg_ppr, 1) as ppg,
                   round(ss.total_fantasy_points_ppr, 1) as total_points,
                   ss.targets as targets, ss.receptions as receptions,
                   ss.receiving_yards as rec_yards, ss.receiving_tds as rec_tds,
                   ss.rushing_yards as rush_yards, ss.rushing_tds as rush_tds,
                   p.ktc_value as ktc_value,
                   p.production_edge_score as edge_score,
                   p.production_signal as signal,
                   p.production_efficiency as efficiency,
                   p.value_gap_2025 as value_gap,
                   weekly as weekly_breakdown
            LIMIT 1
        """

        df = self._query(query, {"name": name})
        if df.empty:
            return json.dumps({"error": f"No 2025 stats found for '{name}'"})

        result = df.iloc[0].to_dict()

        # Calculate additional insights
        weekly = result.get("weekly_breakdown", [])
        if weekly and len(weekly) >= 3:
            points = [w["points"] for w in weekly if w.get("points") is not None]
            if points:
                result["ceiling"] = max(points)
                result["floor"] = min(points)
                result["consistency"] = round(sum(points) / len(points) / max(max(points), 1) * 100, 1)

                # Trend
                if len(points) >= 4:
                    first_half = sum(points[:len(points)//2]) / (len(points)//2)
                    second_half = sum(points[len(points)//2:]) / (len(points) - len(points)//2)
                    if second_half > first_half * 1.1:
                        result["trend"] = "RISING"
                    elif second_half < first_half * 0.9:
                        result["trend"] = "FALLING"
                    else:
                        result["trend"] = "STABLE"

        return json.dumps(result, default=str)

    def _tool_find_2025_buy_targets(self, input: dict) -> str:
        """Find players outperforming their KTC value in 2025."""
        position = input.get("position", "ALL")
        min_edge = input.get("min_edge_score", 15)
        limit = input.get("limit", 15)

        conditions = [
            "ss.season = 2025",
            "ss.games >= 3",
            "p.ktc_value IS NOT NULL",
            f"p.production_edge_score >= {min_edge}"
        ]

        if position != "ALL":
            conditions.append(f"ss.position = '{position}'")

        query = f"""
            MATCH (p:Player)-[:HAD_SEASON]->(ss:SeasonStats)
            WHERE {' AND '.join(conditions)}
            RETURN p.name as player, ss.position as position,
                   ss.team as team, p.age as age,
                   ss.games as games,
                   round(ss.ppg_ppr, 1) as ppg,
                   p.ktc_value as ktc_value,
                   round(p.value_gap_2025, 0) as value_gap,
                   round(p.production_edge_score, 1) as edge_score,
                   p.production_signal as signal,
                   round(p.production_efficiency, 2) as efficiency
            ORDER BY p.production_edge_score DESC
            LIMIT {limit}
        """

        df = self._query(query)
        return df.to_json(orient="records")

    def _tool_find_2025_sell_candidates(self, input: dict) -> str:
        """Find players underperforming their KTC value in 2025."""
        position = input.get("position", "ALL")
        max_edge = input.get("max_edge_score", -15)
        limit = input.get("limit", 15)

        conditions = [
            "ss.season = 2025",
            "ss.games >= 3",
            "p.ktc_value IS NOT NULL",
            f"p.production_edge_score <= {max_edge}"
        ]

        if position != "ALL":
            conditions.append(f"ss.position = '{position}'")

        query = f"""
            MATCH (p:Player)-[:HAD_SEASON]->(ss:SeasonStats)
            WHERE {' AND '.join(conditions)}
            RETURN p.name as player, ss.position as position,
                   ss.team as team, p.age as age,
                   ss.games as games,
                   round(ss.ppg_ppr, 1) as ppg,
                   p.ktc_value as ktc_value,
                   round(p.value_gap_2025, 0) as value_gap,
                   round(p.production_edge_score, 1) as edge_score,
                   p.production_signal as signal,
                   round(p.production_efficiency, 2) as efficiency
            ORDER BY p.production_edge_score ASC
            LIMIT {limit}
        """

        df = self._query(query)
        return df.to_json(orient="records")

    def _tool_get_2025_usage_trends(self, input: dict) -> str:
        """Find players with rising or falling snap share in 2025."""
        position = input.get("position", "ALL")
        trend = input.get("trend", "rising")
        min_change = input.get("min_snap_change", 10)
        limit = input.get("limit", 15)

        pos_filter = ""
        if position != "ALL":
            pos_filter = f"AND sc.position = '{position}'"

        # Determine trend direction
        if trend == "rising":
            change_filter = f"late_avg > early_avg + {min_change}"
            order = "snap_increase DESC"
        elif trend == "falling":
            change_filter = f"early_avg > late_avg + {min_change}"
            order = "snap_decrease DESC"
        else:
            change_filter = f"abs(late_avg - early_avg) >= {min_change}"
            order = "abs(late_avg - early_avg) DESC"

        query = f"""
            MATCH (p:Player)-[:HAD_SNAPS]->(sc:SnapCount)
            WHERE sc.season = 2025 AND sc.position IN ['QB', 'RB', 'WR', 'TE']
            {pos_filter}
            WITH p, sc ORDER BY sc.week
            WITH p, collect({{week: sc.week, pct: sc.offense_pct}}) as snaps
            WHERE size(snaps) >= 4

            WITH p, snaps,
                 [s IN snaps WHERE s.week <= 4 | s.pct] as early_snaps,
                 [s IN snaps WHERE s.week > 4 | s.pct] as late_snaps

            WHERE size(early_snaps) > 0 AND size(late_snaps) > 0

            WITH p,
                 reduce(s=0.0, x IN early_snaps | s+x) / size(early_snaps) as early_avg,
                 reduce(s=0.0, x IN late_snaps | s+x) / size(late_snaps) as late_avg

            WHERE {change_filter}

            OPTIONAL MATCH (p)-[:HAD_SEASON]->(ss:SeasonStats {{season: 2025}})

            RETURN p.name as player, p.position as position, p.current_team as team,
                   round(early_avg, 1) as early_snap_pct,
                   round(late_avg, 1) as recent_snap_pct,
                   round(late_avg - early_avg, 1) as snap_increase,
                   round(early_avg - late_avg, 1) as snap_decrease,
                   round(ss.ppg_ppr, 1) as ppg,
                   p.ktc_value as ktc_value,
                   p.production_signal as signal
            ORDER BY {order}
            LIMIT {limit}
        """

        df = self._query(query)
        return df.to_json(orient="records")

    def _tool_get_weekly_breakdown(self, input: dict) -> str:
        """Get week-by-week fantasy breakdown for a player."""
        name = input.get("player_name", "")

        query = """
            MATCH (p:Player)-[:HAD_WEEK]->(ws:WeeklyStats {season: 2025})
            WHERE toLower(p.name) CONTAINS toLower($name)
            WITH p, ws ORDER BY ws.week
            WITH p, collect({
                week: ws.week,
                opponent: ws.opponent,
                points_ppr: round(ws.fantasy_points_ppr, 1),
                targets: ws.targets,
                receptions: ws.receptions,
                rec_yards: ws.receiving_yards,
                rec_tds: ws.receiving_tds,
                carries: ws.carries,
                rush_yards: ws.rushing_yards,
                rush_tds: ws.rushing_tds
            }) as games

            WITH p, games,
                 [g IN games | g.points_ppr] as points

            RETURN p.name as player, p.position as position,
                   p.current_team as team, p.age as age,
                   size(games) as games_played,
                   games as weekly_games,
                   round(reduce(s=0.0, x IN points | s+x) / size(points), 1) as avg_ppg,
                   reduce(mx=0.0, x IN points | CASE WHEN x > mx THEN x ELSE mx END) as ceiling,
                   reduce(mn=100.0, x IN points | CASE WHEN x < mn THEN x ELSE mn END) as floor,
                   p.ktc_value as ktc_value
        """

        df = self._query(query, {"name": name})
        if df.empty:
            return json.dumps({"error": f"No 2025 weekly stats found for '{name}'"})

        result = df.iloc[0].to_dict()

        # Add consistency score
        games = result.get("weekly_games", [])
        if games:
            points = [g["points_ppr"] for g in games if g.get("points_ppr") is not None]
            if points and len(points) > 1:
                import statistics
                std_dev = statistics.stdev(points)
                mean = statistics.mean(points)
                cv = (std_dev / mean * 100) if mean > 0 else 0
                result["consistency_score"] = round(100 - cv, 1)
                result["std_dev"] = round(std_dev, 1)

                # Identify boom/bust weeks
                boom_threshold = mean + std_dev
                bust_threshold = mean - std_dev
                result["boom_games"] = sum(1 for p in points if p >= boom_threshold)
                result["bust_games"] = sum(1 for p in points if p <= bust_threshold)

        return json.dumps(result, default=str)

    # -------------------------------------------------------------------------
    # FALLBACK
    # -------------------------------------------------------------------------

    def _tool_cypher_query(self, input: dict) -> str:
        """Execute direct Cypher query."""
        query = input.get("query", "")
        df = self._query(query)
        return df.to_json(orient="records")
