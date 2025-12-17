#!/usr/bin/env python3
"""
Dynasty Edge - AI Data Science Team Integration Module

Bridges your Neo4j graph database with the ai-data-science-team library
for automated feature engineering, correlation discovery, and ML modeling.

This module:
1. Exports temporal snapshot data from Neo4j to pandas
2. Runs ai-data-science-team agents for analysis
3. Stores discovered insights back into Neo4j
4. Provides tools for your Claude agent to orchestrate

Prerequisites:
    pip install ai-data-science-team neo4j pandas langchain-openai h2o
"""

import os
from datetime import datetime
from typing import Optional, Dict, List, Any
import pandas as pd
import numpy as np
from neo4j import GraphDatabase
from dotenv import load_dotenv

# AI Data Science Team imports
try:
    from ai_data_science_team.agents import (
        FeatureEngineeringAgent,
        DataCleaningAgent,
        DataWranglingAgent,
        DataVisualizationAgent
    )
    from ai_data_science_team.ds_agents import EDAToolsAgent
    from ai_data_science_team.ml_agents import H2OMLAgent
    AI_DS_TEAM_AVAILABLE = True
except ImportError:
    AI_DS_TEAM_AVAILABLE = False
    print("⚠️  ai-data-science-team not installed. Install with: pip install ai-data-science-team")

from langchain_openai import ChatOpenAI

load_dotenv()

# Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


class DynastyDataBridge:
    """
    Bridges Neo4j graph data with pandas DataFrames for use with
    ai-data-science-team agents.
    """
    
    def __init__(self, uri: str = NEO4J_URI, user: str = NEO4J_USER, password: str = NEO4J_PASSWORD):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        print(f"✅ Connected to Neo4j at {uri}")
    
    def close(self):
        self.driver.close()
    
    def query_to_dataframe(self, query: str, params: dict = None) -> pd.DataFrame:
        """Execute a Cypher query and return results as a pandas DataFrame."""
        with self.driver.session() as session:
            result = session.run(query, params or {})
            records = [dict(record) for record in result]
            return pd.DataFrame(records)
    
    # =========================================================================
    # PRE-BUILT QUERIES FOR COMMON DATA EXPORTS
    # =========================================================================
    
    def get_player_snapshots(
        self, 
        position: str = None, 
        days: int = 30,
        include_qb_data: bool = True
    ) -> pd.DataFrame:
        """
        Export player snapshots with optional QB relationship data.
        Perfect for correlation analysis and feature engineering.
        """
        position_filter = f"p.position = '{position}'" if position else "p.position IN ['QB', 'RB', 'WR', 'TE']"
        
        qb_match = """
            OPTIONAL MATCH (p)-[:TARGETS_FROM]->(qb:Player)
        """ if include_qb_data else ""
        
        qb_return = """
            , qb.name as qb_name
            , qb.age as qb_age
            , qb.ktc_value as qb_ktc
        """ if include_qb_data else ""
        
        query = f"""
            MATCH (p:Player)-[:HAD_SNAPSHOT]->(s:Snapshot)
            WHERE {position_filter}
              AND s.date > date() - duration('P{days}D')
            {qb_match}
            RETURN 
                p.player_id as player_id,
                p.name as player_name,
                p.position as position,
                p.team as team,
                s.date as snapshot_date,
                s.ktc_value as ktc_value,
                s.ktc_delta as ktc_delta,
                s.ktc_delta_pct as ktc_delta_pct,
                p.age as age,
                s.targets_per_game as targets_per_game,
                s.targets_per_game_delta as tpg_delta,
                s.target_share as target_share,
                s.snap_share as snap_share,
                s.ppg as ppg,
                s.ppg_delta as ppg_delta,
                s.games_played as games_played
                {qb_return}
            ORDER BY p.name, s.date
        """
        
        df = self.query_to_dataframe(query)
        print(f"✅ Exported {len(df)} snapshots for {position or 'all positions'} (last {days} days)")
        return df
    
    def get_correlation_training_data(self, position: str = None, days: int = 30) -> pd.DataFrame:
        """
        Get data specifically formatted for correlation analysis.
        Includes deltas for all metrics to correlate with KTC changes.
        """
        df = self.get_player_snapshots(position, days, include_qb_data=True)
        
        # Only keep rows with valid ktc_delta (not first snapshot)
        df = df[df['ktc_delta'].notna()]
        
        # Add derived features useful for correlation
        if 'age' in df.columns:
            career_endpoints = {'QB': 38, 'RB': 30, 'WR': 33, 'TE': 34}
            df['years_remaining'] = df.apply(
                lambda r: max(1, career_endpoints.get(r['position'], 32) - r['age']) 
                if pd.notna(r['age']) else 5,
                axis=1
            )
        
        if 'qb_age' in df.columns:
            df['qb_is_young'] = (df['qb_age'] < 26).astype(int)
            df['qb_is_old'] = (df['qb_age'] > 32).astype(int)
        
        print(f"✅ Prepared {len(df)} records for correlation analysis")
        return df
    
    def get_current_roster(self, owner: str) -> pd.DataFrame:
        """Get current roster for a fantasy team owner."""
        query = """
            MATCH (p:Player)-[:ROSTERED_BY]->(f:FantasyTeam)
            WHERE f.owner = $owner
            RETURN 
                p.player_id as player_id,
                p.name as player_name,
                p.position as position,
                p.age as age,
                p.team as team,
                p.ktc_value as ktc_value,
                p.edge_value as edge_value,
                p.edge_score as edge_score,
                p.edge_signal as edge_signal
            ORDER BY p.ktc_value DESC
        """
        return self.query_to_dataframe(query, {'owner': owner})
    
    # =========================================================================
    # STORE RESULTS BACK TO NEO4J
    # =========================================================================
    
    def store_correlation(self, correlation: dict):
        """Store a discovered correlation in Neo4j."""
        correlation_id = f"{correlation['metric']}_{correlation['position']}"
        
        with self.driver.session() as session:
            session.run("""
                MERGE (c:Correlation {correlation_id: $correlation_id})
                SET c.metric_name = $metric,
                    c.position = $position,
                    c.pearson_r = $pearson_r,
                    c.p_value = $p_value,
                    c.strength = $strength,
                    c.direction = $direction,
                    c.sample_size = $sample_size,
                    c.discovered_date = date(),
                    c.discovered_by = 'ai_ds_team',
                    c.current_weight = coalesce(c.current_weight, 1.0)
            """, {
                'correlation_id': correlation_id,
                'metric': correlation.get('metric', correlation.get('feature')),
                'position': correlation.get('position', 'ALL'),
                'pearson_r': correlation.get('pearson_r', correlation.get('correlation')),
                'p_value': correlation.get('p_value'),
                'strength': correlation.get('strength', 'Unknown'),
                'direction': 'Positive' if correlation.get('pearson_r', 0) > 0 else 'Negative',
                'sample_size': correlation.get('sample_size', 0)
            })
        
        return correlation_id
    
    def store_feature_importance(self, importances: List[dict], model_name: str):
        """Store ML model feature importances in Neo4j."""
        with self.driver.session() as session:
            for imp in importances:
                session.run("""
                    MERGE (fi:FeatureImportance {
                        feature_name: $feature,
                        model_name: $model_name
                    })
                    SET fi.importance = $importance,
                        fi.rank = $rank,
                        fi.discovered_date = date()
                """, {
                    'feature': imp['feature'],
                    'model_name': model_name,
                    'importance': imp['importance'],
                    'rank': imp.get('rank', 0)
                })
        
        print(f"✅ Stored {len(importances)} feature importances from {model_name}")
    
    def store_engineered_features(self, df: pd.DataFrame, feature_columns: List[str]):
        """Store engineered feature values back to player snapshots."""
        with self.driver.session() as session:
            for _, row in df.iterrows():
                if 'player_id' not in row or 'snapshot_date' not in row:
                    continue
                
                feature_updates = {col: row[col] for col in feature_columns if col in row and pd.notna(row[col])}
                
                if feature_updates:
                    set_clauses = ', '.join([f"s.feat_{k} = ${k}" for k in feature_updates.keys()])
                    session.run(f"""
                        MATCH (p:Player {{player_id: $player_id}})-[:HAD_SNAPSHOT]->(s:Snapshot)
                        WHERE s.date = date($snapshot_date)
                        SET {set_clauses}
                    """, {
                        'player_id': row['player_id'],
                        'snapshot_date': str(row['snapshot_date']),
                        **feature_updates
                    })
        
        print(f"✅ Stored {len(feature_columns)} engineered features for {len(df)} records")


class DynastyAIAgents:
    """
    Wrapper around ai-data-science-team agents configured for dynasty fantasy football.
    """
    
    def __init__(
        self, 
        bridge: DynastyDataBridge,
        llm_model: str = "gpt-4o",
        log_path: str = "./logs/ai_agents/"
    ):
        if not AI_DS_TEAM_AVAILABLE:
            raise ImportError("ai-data-science-team is not installed")
        
        self.bridge = bridge
        self.llm = ChatOpenAI(model=llm_model, api_key=OPENAI_API_KEY)
        self.log_path = log_path
        os.makedirs(log_path, exist_ok=True)
        
        # Store agent outputs for later use
        self.last_feature_engineering_result = None
        self.last_eda_result = None
        self.last_ml_result = None
        
        print(f"✅ Initialized Dynasty AI Agents with {llm_model}")
    
    # =========================================================================
    # FEATURE ENGINEERING
    # =========================================================================
    
    def engineer_features(
        self, 
        position: str = None,
        days: int = 30,
        custom_instructions: str = None
    ) -> pd.DataFrame:
        """
        Use Feature Engineering Agent to create dynasty-relevant features.
        """
        # Get data from Neo4j
        df = self.bridge.get_correlation_training_data(position, days)
        
        if len(df) < 10:
            print("⚠️  Not enough data for feature engineering")
            return df
        
        # Default dynasty-specific instructions
        default_instructions = """
        Create features to predict ktc_delta (KTC value changes):
        
        1. AGE-BASED FEATURES:
           - years_remaining: Career endpoint minus current age
             (QB: 38, RB: 30, WR: 33, TE: 34)
           - age_bucket: Young (<24), Prime (24-27), Aging (27-30), Old (>30)
           - value_per_year: ktc_value / years_remaining
        
        2. TREND FEATURES:
           - tpg_trend: Is targets_per_game increasing or decreasing?
           - ppg_momentum: Recent PPG vs season average
        
        3. SITUATION FEATURES (if qb_age available):
           - qb_youth_score: Higher for younger QBs (good for WR/TE)
           - qb_stability: 1 if QB is established (high KTC), 0 otherwise
        
        4. RELATIVE VALUE:
           - position_rank_value: Rank within position by KTC
        
        Keep original columns and add new engineered features.
        Handle missing values appropriately (fill with median or 0).
        """
        
        instructions = custom_instructions or default_instructions
        
        print("\n🔧 Running Feature Engineering Agent...")
        agent = FeatureEngineeringAgent(
            model=self.llm,
            log=True,
            log_path=self.log_path
        )
        
        agent.invoke_agent(
            data_raw=df,
            user_instructions=instructions,
            target_variable="ktc_delta",
            max_retries=3
        )
        
        # Get results
        self.last_feature_engineering_result = {
            'data': agent.get_data_engineered(),
            'code': agent.get_data_engineer_function(),
            'workflow': agent.get_workflow_summary() if hasattr(agent, 'get_workflow_summary') else None
        }
        
        result_df = self.last_feature_engineering_result['data']
        new_features = [c for c in result_df.columns if c not in df.columns]
        
        print(f"✅ Created {len(new_features)} new features: {new_features}")
        
        return result_df
    
    def get_feature_engineering_code(self) -> str:
        """Get the generated Python code from feature engineering."""
        if self.last_feature_engineering_result:
            return self.last_feature_engineering_result.get('code', 'No code available')
        return "No feature engineering has been run yet"
    
    # =========================================================================
    # EXPLORATORY DATA ANALYSIS
    # =========================================================================
    
    def discover_correlations(
        self,
        position: str = None,
        days: int = 30,
        target_column: str = "ktc_delta",
        custom_instructions: str = None
    ) -> Dict[str, Any]:
        """
        Use EDA Tools Agent to discover correlations between metrics and KTC changes.
        """
        # Use feature-engineered data if available, otherwise get fresh data
        if self.last_feature_engineering_result:
            df = self.last_feature_engineering_result['data']
            print("📊 Using feature-engineered data for EDA")
        else:
            df = self.bridge.get_correlation_training_data(position, days)
        
        if len(df) < 10:
            print("⚠️  Not enough data for correlation analysis")
            return {}
        
        # Default dynasty-specific instructions
        default_instructions = f"""
        Analyze what drives {target_column} (KTC value changes):
        
        1. CORRELATION ANALYSIS:
           - Calculate Pearson correlation between all numeric features and {target_column}
           - Rank features by absolute correlation strength
           - Identify statistically significant correlations (p < 0.05)
        
        2. KEY QUESTIONS TO ANSWER:
           - Which metrics most strongly predict KTC increases?
           - Does age have a significant relationship with KTC changes?
           - For WRs/TEs: Does QB age/quality correlate with their KTC changes?
           - Are there any surprising correlations?
        
        3. MULTICOLLINEARITY CHECK:
           - Identify highly correlated feature pairs (r > 0.7)
           - Flag potential redundant features
        
        4. DISTRIBUTION ANALYSIS:
           - Show distribution of {target_column}
           - Identify outliers in KTC changes
        
        Present findings in a clear summary with actionable insights.
        """
        
        instructions = custom_instructions or default_instructions
        
        print("\n📊 Running EDA Tools Agent...")
        agent = EDAToolsAgent(
            model=self.llm,
            log=True,
            log_path=self.log_path
        )
        
        agent.invoke_agent(
            data_raw=df,
            user_instructions=instructions
        )
        
        # Store and parse results
        self.last_eda_result = {
            'summary': agent.get_workflow_summary() if hasattr(agent, 'get_workflow_summary') else None,
            'data': df
        }
        
        # Try to extract correlations and store in Neo4j
        correlations = self._extract_correlations(df, target_column)
        for corr in correlations:
            corr['position'] = position or 'ALL'
            self.bridge.store_correlation(corr)
        
        print(f"✅ Discovered and stored {len(correlations)} correlations")
        
        return {
            'correlations': correlations,
            'summary': self.last_eda_result['summary'],
            'sample_size': len(df)
        }
    
    def _extract_correlations(self, df: pd.DataFrame, target: str) -> List[dict]:
        """Extract correlations from dataframe."""
        from scipy import stats
        
        correlations = []
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        
        for col in numeric_cols:
            if col == target or df[col].isna().all():
                continue
            
            # Drop rows with NaN in either column
            valid_data = df[[col, target]].dropna()
            if len(valid_data) < 10:
                continue
            
            try:
                r, p_value = stats.pearsonr(valid_data[col], valid_data[target])
                
                # Determine strength
                abs_r = abs(r)
                if abs_r >= 0.7:
                    strength = 'Strong'
                elif abs_r >= 0.4:
                    strength = 'Moderate'
                elif abs_r >= 0.2:
                    strength = 'Weak'
                else:
                    strength = 'None'
                
                correlations.append({
                    'metric': col,
                    'pearson_r': round(r, 4),
                    'p_value': round(p_value, 6),
                    'strength': strength,
                    'sample_size': len(valid_data),
                    'significant': p_value < 0.05
                })
            except Exception as e:
                continue
        
        # Sort by absolute correlation
        correlations.sort(key=lambda x: abs(x['pearson_r']), reverse=True)
        return correlations
    
    # =========================================================================
    # MACHINE LEARNING
    # =========================================================================
    
    def train_ktc_predictor(
        self,
        position: str = None,
        days: int = 60,
        max_runtime_secs: int = 60,
        custom_instructions: str = None
    ) -> Dict[str, Any]:
        """
        Use H2O ML Agent to train models predicting KTC changes.
        """
        # Use feature-engineered data if available
        if self.last_feature_engineering_result:
            df = self.last_feature_engineering_result['data']
            print("🤖 Using feature-engineered data for ML")
        else:
            df = self.bridge.get_correlation_training_data(position, days)
        
        # Remove non-numeric and identifier columns
        exclude_cols = ['player_id', 'player_name', 'team', 'snapshot_date', 'qb_name']
        feature_df = df.drop(columns=[c for c in exclude_cols if c in df.columns], errors='ignore')
        
        # Remove rows with missing target
        feature_df = feature_df[feature_df['ktc_delta'].notna()]
        
        if len(feature_df) < 50:
            print("⚠️  Not enough data for ML training (need 50+ rows)")
            return {}
        
        default_instructions = f"""
        Build a regression model to predict ktc_delta (KTC value changes).
        
        Use max runtime of {max_runtime_secs} seconds.
        
        Focus on interpretability - we want to understand what drives KTC changes.
        
        After training, provide:
        1. Model performance metrics (RMSE, MAE, R²)
        2. Feature importance rankings
        3. Top 5 most predictive features
        """
        
        instructions = custom_instructions or default_instructions
        
        print("\n🤖 Running H2O ML Agent...")
        print(f"   Training on {len(feature_df)} samples with {len(feature_df.columns)} features")
        
        try:
            agent = H2OMLAgent(
                model=self.llm,
                log=True,
                log_path=self.log_path,
                enable_mlflow=False  # Set True if you have MLflow configured
            )
            
            agent.invoke_agent(
                data_raw=feature_df,
                user_instructions=instructions,
                target_variable="ktc_delta"
            )
            
            # Get leaderboard
            leaderboard = agent.get_leaderboard()
            
            self.last_ml_result = {
                'leaderboard': leaderboard,
                'best_model': leaderboard.iloc[0].to_dict() if len(leaderboard) > 0 else None,
                'feature_importance': self._get_h2o_feature_importance(agent)
            }
            
            # Store feature importances in Neo4j
            if self.last_ml_result['feature_importance']:
                self.bridge.store_feature_importance(
                    self.last_ml_result['feature_importance'],
                    model_name=f"h2o_ktc_predictor_{position or 'all'}_{datetime.now().strftime('%Y%m%d')}"
                )
            
            print(f"✅ Trained {len(leaderboard)} models")
            print(f"   Best model: {self.last_ml_result['best_model']}")
            
            return self.last_ml_result
            
        except Exception as e:
            print(f"❌ ML training failed: {e}")
            return {'error': str(e)}
    
    def _get_h2o_feature_importance(self, agent) -> List[dict]:
        """Extract feature importance from H2O model."""
        try:
            # This depends on the H2O agent's implementation
            # May need to adapt based on actual API
            importance = agent.get_feature_importance() if hasattr(agent, 'get_feature_importance') else []
            return importance
        except Exception:
            return []
    
    # =========================================================================
    # FULL ANALYSIS PIPELINE
    # =========================================================================
    
    def run_full_analysis(
        self,
        position: str = None,
        days: int = 30,
        include_ml: bool = True
    ) -> Dict[str, Any]:
        """
        Run the complete analysis pipeline:
        1. Feature Engineering
        2. Correlation Discovery (EDA)
        3. ML Model Training (optional)
        
        Returns comprehensive results for Claude to interpret.
        """
        print("\n" + "=" * 70)
        print(f"🚀 RUNNING FULL ANALYSIS PIPELINE")
        print(f"   Position: {position or 'ALL'}")
        print(f"   Lookback: {days} days")
        print("=" * 70)
        
        results = {
            'position': position,
            'days': days,
            'timestamp': datetime.now().isoformat()
        }
        
        # Step 1: Feature Engineering
        print("\n📍 Step 1/3: Feature Engineering")
        try:
            fe_df = self.engineer_features(position, days)
            results['feature_engineering'] = {
                'success': True,
                'new_features': [c for c in fe_df.columns if c not in self.bridge.get_correlation_training_data(position, days).columns],
                'sample_size': len(fe_df)
            }
        except Exception as e:
            results['feature_engineering'] = {'success': False, 'error': str(e)}
        
        # Step 2: Correlation Discovery
        print("\n📍 Step 2/3: Correlation Discovery")
        try:
            eda_results = self.discover_correlations(position, days)
            results['correlations'] = {
                'success': True,
                'top_correlations': eda_results['correlations'][:10],
                'significant_count': len([c for c in eda_results['correlations'] if c.get('significant')])
            }
        except Exception as e:
            results['correlations'] = {'success': False, 'error': str(e)}
        
        # Step 3: ML Training (optional)
        if include_ml:
            print("\n📍 Step 3/3: ML Model Training")
            try:
                ml_results = self.train_ktc_predictor(position, days)
                results['ml_model'] = {
                    'success': True,
                    'best_model': ml_results.get('best_model'),
                    'feature_importance': ml_results.get('feature_importance', [])[:10]
                }
            except Exception as e:
                results['ml_model'] = {'success': False, 'error': str(e)}
        
        print("\n" + "=" * 70)
        print("✅ ANALYSIS COMPLETE")
        print("=" * 70)
        
        return results


# =============================================================================
# CLAUDE AGENT TOOLS
# =============================================================================

def create_claude_tools(bridge: DynastyDataBridge, ai_agents: DynastyAIAgents) -> List[dict]:
    """
    Create tool definitions for your Claude agent to use.
    These wrap the ai-data-science-team functionality.
    """
    
    tools = [
        {
            "name": "run_feature_engineering",
            "description": """Run the Feature Engineering Agent to create dynasty-relevant features
            from player snapshot data. Creates features like years_remaining, value_per_year,
            QB quality scores, and trend indicators. Stores results for subsequent analysis.""",
            "input_schema": {
                "type": "object",
                "properties": {
                    "position": {
                        "type": "string",
                        "enum": ["QB", "RB", "WR", "TE", None],
                        "description": "Filter to specific position (optional)"
                    },
                    "days": {
                        "type": "integer",
                        "description": "Number of days of data to use (default 30)"
                    },
                    "custom_instructions": {
                        "type": "string",
                        "description": "Custom instructions for the feature engineering agent"
                    }
                }
            }
        },
        {
            "name": "discover_ktc_correlations",
            "description": """Run the EDA Agent to discover correlations between player metrics
            and KTC value changes. Finds what actually drives KTC movements. Results are
            stored in Neo4j for weight adjustment suggestions.""",
            "input_schema": {
                "type": "object",
                "properties": {
                    "position": {
                        "type": "string",
                        "enum": ["QB", "RB", "WR", "TE", None],
                        "description": "Filter to specific position (optional)"
                    },
                    "days": {
                        "type": "integer",
                        "description": "Number of days of data to analyze (default 30)"
                    }
                }
            }
        },
        {
            "name": "train_ktc_predictor",
            "description": """Train ML models to predict KTC value changes. Uses H2O AutoML
            to try hundreds of models and find the best predictor. Returns feature importance
            rankings that show what metrics most influence KTC.""",
            "input_schema": {
                "type": "object",
                "properties": {
                    "position": {
                        "type": "string",
                        "enum": ["QB", "RB", "WR", "TE", None],
                        "description": "Filter to specific position (optional)"
                    },
                    "days": {
                        "type": "integer",
                        "description": "Number of days of training data (default 60)"
                    },
                    "max_runtime_secs": {
                        "type": "integer",
                        "description": "Maximum training time in seconds (default 60)"
                    }
                }
            }
        },
        {
            "name": "run_full_analysis",
            "description": """Run the complete analysis pipeline: Feature Engineering → 
            Correlation Discovery → ML Training. Use this for comprehensive analysis
            of what drives KTC values for a position.""",
            "input_schema": {
                "type": "object",
                "properties": {
                    "position": {
                        "type": "string",
                        "enum": ["QB", "RB", "WR", "TE", None],
                        "description": "Position to analyze (optional)"
                    },
                    "days": {
                        "type": "integer",
                        "description": "Lookback period in days (default 30)"
                    },
                    "include_ml": {
                        "type": "boolean",
                        "description": "Whether to include ML training (default True)"
                    }
                }
            }
        },
        {
            "name": "get_generated_code",
            "description": """Get the Python code generated by the Feature Engineering Agent.
            Useful for reviewing, modifying, or incorporating into your pipeline.""",
            "input_schema": {
                "type": "object",
                "properties": {}
            }
        }
    ]
    
    return tools


def execute_claude_tool(
    tool_name: str, 
    tool_input: dict,
    bridge: DynastyDataBridge,
    ai_agents: DynastyAIAgents
) -> str:
    """Execute a Claude tool and return JSON result."""
    import json
    
    if tool_name == "run_feature_engineering":
        result = ai_agents.engineer_features(
            position=tool_input.get('position'),
            days=tool_input.get('days', 30),
            custom_instructions=tool_input.get('custom_instructions')
        )
        return json.dumps({
            'success': True,
            'rows': len(result),
            'columns': list(result.columns)
        })
    
    elif tool_name == "discover_ktc_correlations":
        result = ai_agents.discover_correlations(
            position=tool_input.get('position'),
            days=tool_input.get('days', 30)
        )
        return json.dumps(result, default=str)
    
    elif tool_name == "train_ktc_predictor":
        result = ai_agents.train_ktc_predictor(
            position=tool_input.get('position'),
            days=tool_input.get('days', 60),
            max_runtime_secs=tool_input.get('max_runtime_secs', 60)
        )
        return json.dumps(result, default=str)
    
    elif tool_name == "run_full_analysis":
        result = ai_agents.run_full_analysis(
            position=tool_input.get('position'),
            days=tool_input.get('days', 30),
            include_ml=tool_input.get('include_ml', True)
        )
        return json.dumps(result, default=str)
    
    elif tool_name == "get_generated_code":
        code = ai_agents.get_feature_engineering_code()
        return json.dumps({'code': code})
    
    return json.dumps({'error': f'Unknown tool: {tool_name}'})


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Example usage of the integration module."""
    print("\n" + "=" * 70)
    print("🏈 DYNASTY EDGE - AI Data Science Team Integration")
    print("=" * 70 + "\n")
    
    # Initialize bridge
    bridge = DynastyDataBridge()
    
    try:
        # Test Neo4j connection with a simple query
        test_df = bridge.query_to_dataframe("MATCH (p:Player) RETURN count(p) as count")
        print(f"📊 Found {test_df['count'].iloc[0]} players in Neo4j")
        
        if AI_DS_TEAM_AVAILABLE and OPENAI_API_KEY:
            # Initialize AI agents
            ai_agents = DynastyAIAgents(bridge)
            
            # Run example analysis
            print("\n🔬 Running example analysis on WRs...")
            results = ai_agents.run_full_analysis(
                position='WR',
                days=30,
                include_ml=False  # Set True if you have enough data
            )
            
            # Print summary
            print("\n📋 RESULTS SUMMARY:")
            print(f"   Feature Engineering: {results.get('feature_engineering', {}).get('success', False)}")
            print(f"   Correlations Found: {results.get('correlations', {}).get('significant_count', 0)}")
            
            if results.get('correlations', {}).get('top_correlations'):
                print("\n   Top 5 Correlations with KTC Changes:")
                for i, corr in enumerate(results['correlations']['top_correlations'][:5], 1):
                    print(f"   {i}. {corr['metric']}: r={corr['pearson_r']:.3f} ({corr['strength']})")
        else:
            print("\n⚠️  AI agents not available. Set OPENAI_API_KEY and install ai-data-science-team")
            print("   You can still use the DynastyDataBridge for Neo4j ↔ pandas operations")
        
    finally:
        bridge.close()


if __name__ == "__main__":
    main()
