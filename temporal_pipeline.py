#!/usr/bin/env python3
"""
Dynasty Edge - Temporal Data Pipeline
Captures point-in-time snapshots and calculates correlations between
player metrics and KTC value changes.

This module enables causal analysis: "Did KTC rise because targets increased?"
"""

import os
from datetime import datetime, timedelta
from typing import Optional
import pandas as pd
import numpy as np
from scipy import stats
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")


class TemporalDataPipeline:
    """Manages temporal snapshots and correlation analysis."""
    
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        print(f"✅ Connected to Neo4j at {uri}")
    
    def close(self):
        self.driver.close()
    
    # =========================================================================
    # SNAPSHOT CREATION
    # =========================================================================
    
    def create_temporal_constraints(self):
        """Create constraints for temporal nodes."""
        constraints = [
            "CREATE CONSTRAINT snapshot_id IF NOT EXISTS FOR (s:Snapshot) REQUIRE s.snapshot_id IS UNIQUE",
            "CREATE CONSTRAINT correlation_id IF NOT EXISTS FOR (c:Correlation) REQUIRE c.correlation_id IS UNIQUE",
            "CREATE CONSTRAINT model_config_id IF NOT EXISTS FOR (m:ModelConfig) REQUIRE m.config_id IS UNIQUE",
            "CREATE CONSTRAINT prediction_id IF NOT EXISTS FOR (p:Prediction) REQUIRE p.prediction_id IS UNIQUE",
            "CREATE INDEX snapshot_date IF NOT EXISTS FOR (s:Snapshot) ON (s.date)",
            "CREATE INDEX snapshot_player IF NOT EXISTS FOR (s:Snapshot) ON (s.player_id)",
        ]
        with self.driver.session() as session:
            for constraint in constraints:
                try:
                    session.run(constraint)
                except Exception:
                    pass
        print("✅ Created temporal constraints and indexes")
    
    def create_player_snapshot(self, player_data: dict, stats_data: dict = None):
        """
        Create a point-in-time snapshot for a player.
        
        player_data: {player_id, name, position, ktc_value, age, team}
        stats_data: {targets, receptions, yards, tds, snap_share, target_share, games_played, ppg}
        """
        today = datetime.now().strftime('%Y-%m-%d')
        snapshot_id = f"{player_data['player_id']}_{today}"
        
        stats_data = stats_data or {}
        
        with self.driver.session() as session:
            # Get previous snapshot for delta calculation
            prev_result = session.run("""
                MATCH (p:Player {player_id: $player_id})-[:HAD_SNAPSHOT]->(s:Snapshot)
                RETURN s ORDER BY s.date DESC LIMIT 1
            """, player_id=player_data['player_id'])
            
            prev_snapshot = prev_result.single()
            prev_ktc = prev_snapshot['s']['ktc_value'] if prev_snapshot else None
            prev_tpg = prev_snapshot['s'].get('targets_per_game') if prev_snapshot else None
            prev_ppg = prev_snapshot['s'].get('ppg') if prev_snapshot else None
            
            # Calculate deltas
            ktc_delta = (player_data['ktc_value'] - prev_ktc) if prev_ktc else None
            ktc_delta_pct = (ktc_delta / prev_ktc * 100) if prev_ktc and ktc_delta else None
            
            games = stats_data.get('games_played', 1) or 1
            tpg = stats_data.get('targets', 0) / games if stats_data.get('targets') else None
            tpg_delta = (tpg - prev_tpg) if tpg and prev_tpg else None
            
            ppg = stats_data.get('ppg')
            ppg_delta = (ppg - prev_ppg) if ppg and prev_ppg else None
            
            # Create snapshot
            session.run("""
                // Create or get player
                MERGE (p:Player {player_id: $player_id})
                SET p.name = $name,
                    p.position = $position,
                    p.ktc_value = $ktc_value,
                    p.age = $age,
                    p.team = $team
                
                // Create snapshot
                CREATE (s:Snapshot {
                    snapshot_id: $snapshot_id,
                    player_id: $player_id,
                    date: date($date),
                    
                    ktc_value: $ktc_value,
                    ktc_delta: $ktc_delta,
                    ktc_delta_pct: $ktc_delta_pct,
                    
                    targets: $targets,
                    targets_per_game: $tpg,
                    targets_per_game_delta: $tpg_delta,
                    receptions: $receptions,
                    yards: $yards,
                    tds: $tds,
                    
                    snap_share: $snap_share,
                    target_share: $target_share,
                    games_played: $games_played,
                    ppg: $ppg,
                    ppg_delta: $ppg_delta
                })
                
                // Link snapshot to player
                CREATE (p)-[:HAD_SNAPSHOT]->(s)
                
                // Link to previous snapshot
                WITH p, s
                MATCH (p)-[:HAD_SNAPSHOT]->(prev:Snapshot)
                WHERE prev.snapshot_id <> s.snapshot_id
                WITH s, prev ORDER BY prev.date DESC LIMIT 1
                CREATE (s)-[:PREVIOUS]->(prev)
            """, {
                'player_id': player_data['player_id'],
                'name': player_data['name'],
                'position': player_data['position'],
                'ktc_value': player_data['ktc_value'],
                'age': player_data.get('age'),
                'team': player_data.get('team'),
                'snapshot_id': snapshot_id,
                'date': today,
                'ktc_delta': ktc_delta,
                'ktc_delta_pct': ktc_delta_pct,
                'targets': stats_data.get('targets'),
                'tpg': tpg,
                'tpg_delta': tpg_delta,
                'receptions': stats_data.get('receptions'),
                'yards': stats_data.get('yards'),
                'tds': stats_data.get('tds'),
                'snap_share': stats_data.get('snap_share'),
                'target_share': stats_data.get('target_share'),
                'games_played': stats_data.get('games_played'),
                'ppg': ppg,
                'ppg_delta': ppg_delta
            })
        
        return snapshot_id
    
    def batch_create_snapshots(self, ktc_df: pd.DataFrame, stats_df: pd.DataFrame = None):
        """Create snapshots for all players from dataframes."""
        stats_dict = {}
        if stats_df is not None:
            for _, row in stats_df.iterrows():
                stats_dict[row['player_id']] = row.to_dict()
        
        count = 0
        for _, row in ktc_df.iterrows():
            player_data = {
                'player_id': row.get('player_id', row['player_name'].lower().replace(' ', '_')),
                'name': row['player_name'],
                'position': row['position'],
                'ktc_value': int(row['value']) if pd.notna(row['value']) else 0,
                'age': float(row['age']) if pd.notna(row['age']) else None,
                'team': row.get('team')
            }
            
            stats_data = stats_dict.get(player_data['player_id'], {})
            
            try:
                self.create_player_snapshot(player_data, stats_data)
                count += 1
            except Exception as e:
                print(f"  ⚠️ Error creating snapshot for {player_data['name']}: {e}")
        
        print(f"✅ Created {count} player snapshots")
        return count
    
    # =========================================================================
    # CORRELATION ANALYSIS
    # =========================================================================
    
    def calculate_correlation(
        self, 
        metric_name: str, 
        position: str = 'ALL',
        lookback_days: int = 30,
        min_snapshots: int = 2
    ) -> dict:
        """
        Calculate correlation between a metric's change and KTC change.
        
        Returns: {metric, position, pearson_r, p_value, strength, sample_size}
        """
        position_filter = f"p.position = '{position}'" if position != 'ALL' else "p.position IN ['QB', 'RB', 'WR', 'TE']"
        
        query = f"""
            MATCH (p:Player)-[:HAD_SNAPSHOT]->(s:Snapshot)
            WHERE {position_filter}
              AND s.date > date() - duration('P{lookback_days}D')
              AND s.{metric_name} IS NOT NULL
              AND s.ktc_delta IS NOT NULL
            WITH p, s ORDER BY s.date
            WITH p, collect(s) as snapshots
            WHERE size(snapshots) >= {min_snapshots}
            UNWIND range(1, size(snapshots)-1) as i
            WITH snapshots[i] as curr
            WHERE curr.ktc_delta IS NOT NULL
              AND curr.{metric_name}_delta IS NOT NULL
            RETURN curr.{metric_name}_delta as metric_delta,
                   curr.ktc_delta as ktc_delta
        """
        
        with self.driver.session() as session:
            result = session.run(query)
            data = [dict(record) for record in result]
        
        if len(data) < 10:
            return {
                'metric': metric_name,
                'position': position,
                'pearson_r': None,
                'p_value': None,
                'sample_size': len(data),
                'strength': 'Insufficient data',
                'direction': None,
                'confidence': 'None'
            }
        
        df = pd.DataFrame(data)
        df = df.dropna()
        
        if len(df) < 10:
            return {
                'metric': metric_name,
                'position': position,
                'pearson_r': None,
                'p_value': None,
                'sample_size': len(df),
                'strength': 'Insufficient data',
                'direction': None,
                'confidence': 'None'
            }
        
        r, p_value = stats.pearsonr(df['metric_delta'], df['ktc_delta'])
        
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
        
        # Determine confidence based on p-value
        if p_value < 0.01:
            confidence = 'High'
        elif p_value < 0.05:
            confidence = 'Medium'
        else:
            confidence = 'Low'
        
        return {
            'metric': metric_name,
            'position': position,
            'pearson_r': round(r, 3),
            'p_value': round(p_value, 4),
            'sample_size': len(df),
            'strength': strength,
            'direction': 'Positive' if r > 0 else 'Negative',
            'confidence': confidence,
            'lookback_days': lookback_days
        }
    
    def store_correlation(self, correlation: dict):
        """Store a correlation result in Neo4j."""
        correlation_id = f"{correlation['metric']}_{correlation['position']}"
        
        with self.driver.session() as session:
            session.run("""
                MERGE (c:Correlation {correlation_id: $correlation_id})
                SET c.metric_name = $metric,
                    c.position = $position,
                    c.pearson_r = $pearson_r,
                    c.p_value = $p_value,
                    c.sample_size = $sample_size,
                    c.lookback_days = $lookback_days,
                    c.strength = $strength,
                    c.direction = $direction,
                    c.confidence = $confidence,
                    c.discovered_date = date(),
                    c.current_weight = coalesce(c.current_weight, 1.0)
            """, {
                'correlation_id': correlation_id,
                **correlation
            })
        
        return correlation_id
    
    def run_full_correlation_analysis(self, positions: list = None, metrics: list = None):
        """Run correlation analysis for all positions and metrics."""
        positions = positions or ['QB', 'RB', 'WR', 'TE']
        metrics = metrics or ['targets_per_game', 'ppg']  # Add more as you collect them
        
        results = []
        for position in positions:
            for metric in metrics:
                try:
                    corr = self.calculate_correlation(metric, position)
                    if corr['pearson_r'] is not None:
                        self.store_correlation(corr)
                        results.append(corr)
                        print(f"  {position} {metric}: r={corr['pearson_r']:.3f} ({corr['strength']})")
                except Exception as e:
                    print(f"  ⚠️ Error calculating {position} {metric}: {e}")
        
        return results
    
    # =========================================================================
    # MODEL WEIGHT MANAGEMENT
    # =========================================================================
    
    def get_current_weights(self) -> dict:
        """Get the currently active model weights."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (m:ModelConfig {active: true})
                RETURN m
            """)
            record = result.single()
            
            if record:
                config = dict(record['m'])
                return {k: v for k, v in config.items() if k.startswith('w_')}
            
            # Return defaults if no config exists
            return {
                'w_age': 1.0,
                'w_targets_per_game': 1.0,
                'w_snap_share': 1.0,
                'w_target_share': 1.0,
                'w_qb_age': 1.0,
                'w_injury_history': 1.0,
                'w_competition': 1.0,
                'w_rookie_premium': 0.9
            }
    
    def apply_weights(self, weights: dict, reason: str, suggested_by: str = 'user'):
        """Apply new model weights and log the change."""
        config_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        with self.driver.session() as session:
            # Deactivate current config
            session.run("MATCH (m:ModelConfig {active: true}) SET m.active = false")
            
            # Create new config
            weight_props = ', '.join([f'm.{k} = ${k}' for k in weights.keys()])
            session.run(f"""
                CREATE (m:ModelConfig {{
                    config_id: $config_id,
                    created_date: datetime(),
                    created_by: $suggested_by,
                    active: true
                }})
                SET {weight_props}
            """, {
                'config_id': config_id,
                'suggested_by': suggested_by,
                **weights
            })
            
            # Log weight changes
            old_weights = self.get_current_weights()
            for metric, new_weight in weights.items():
                old_weight = old_weights.get(metric, 1.0)
                if old_weight != new_weight:
                    session.run("""
                        CREATE (wc:WeightChange {
                            change_id: $change_id,
                            date: datetime(),
                            metric_name: $metric,
                            old_weight: $old_weight,
                            new_weight: $new_weight,
                            reason: $reason,
                            suggested_by: $suggested_by
                        })
                    """, {
                        'change_id': f"{config_id}_{metric}",
                        'metric': metric,
                        'old_weight': old_weight,
                        'new_weight': new_weight,
                        'reason': reason,
                        'suggested_by': suggested_by
                    })
        
        print(f"✅ Applied new weights (config: {config_id})")
        return config_id
    
    def suggest_weight_from_correlation(self, correlation_id: str) -> Optional[dict]:
        """Suggest a weight adjustment based on a correlation."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (c:Correlation {correlation_id: $correlation_id})
                RETURN c
            """, correlation_id=correlation_id)
            
            record = result.single()
            if not record:
                return None
            
            corr = dict(record['c'])
            
            # Suggest weight based on correlation strength
            r = corr.get('pearson_r', 0)
            if r is None:
                return None
            
            # Stronger correlations get higher weights
            # r=0.7 → weight=1.3, r=0.4 → weight=1.15, r=0.2 → weight=1.05
            suggested_weight = 1.0 + (abs(r) * 0.5)
            
            # Cap at reasonable bounds
            suggested_weight = max(0.5, min(2.0, suggested_weight))
            
            return {
                'metric': f"w_{corr['metric_name']}",
                'current_weight': corr.get('current_weight', 1.0),
                'suggested_weight': round(suggested_weight, 2),
                'correlation_r': r,
                'reasoning': f"{corr['strength']} {corr['direction'].lower()} correlation (r={r:.2f}) suggests increasing weight"
            }
    
    # =========================================================================
    # PREDICTION TRACKING
    # =========================================================================
    
    def create_prediction(
        self, 
        player_id: str, 
        predicted_ktc_delta: int,
        horizon_days: int = 7,
        reasoning: str = ''
    ):
        """Create a prediction for future KTC change."""
        prediction_id = f"{player_id}_{datetime.now().strftime('%Y%m%d')}"
        target_date = (datetime.now() + timedelta(days=horizon_days)).strftime('%Y-%m-%d')
        
        with self.driver.session() as session:
            # Get current model config
            config_result = session.run("MATCH (m:ModelConfig {active: true}) RETURN m.config_id as config_id")
            config = config_result.single()
            config_id = config['config_id'] if config else 'default'
            
            # Get current KTC for reference
            player_result = session.run("""
                MATCH (p:Player {player_id: $player_id})
                RETURN p.ktc_value as ktc, p.name as name
            """, player_id=player_id)
            player = player_result.single()
            current_ktc = player['ktc'] if player else 0
            
            predicted_ktc_delta_pct = (predicted_ktc_delta / current_ktc * 100) if current_ktc else 0
            
            session.run("""
                MATCH (p:Player {player_id: $player_id})
                CREATE (pred:Prediction {
                    prediction_id: $prediction_id,
                    player_id: $player_id,
                    predicted_date: date(),
                    target_date: date($target_date),
                    current_ktc: $current_ktc,
                    predicted_ktc_delta: $predicted_ktc_delta,
                    predicted_ktc_delta_pct: $predicted_ktc_delta_pct,
                    model_config_id: $config_id,
                    reasoning: $reasoning,
                    evaluated: false
                })
                CREATE (pred)-[:PREDICTED_FOR]->(p)
            """, {
                'prediction_id': prediction_id,
                'player_id': player_id,
                'target_date': target_date,
                'current_ktc': current_ktc,
                'predicted_ktc_delta': predicted_ktc_delta,
                'predicted_ktc_delta_pct': predicted_ktc_delta_pct,
                'config_id': config_id,
                'reasoning': reasoning
            })
        
        return prediction_id
    
    def evaluate_predictions(self):
        """Evaluate past predictions against actual outcomes."""
        with self.driver.session() as session:
            # Find predictions that are due for evaluation
            result = session.run("""
                MATCH (pred:Prediction)-[:PREDICTED_FOR]->(p:Player)
                WHERE pred.target_date <= date()
                  AND pred.evaluated = false
                RETURN pred, p.ktc_value as current_ktc, p.name as player_name
            """)
            
            evaluated = 0
            for record in result:
                pred = dict(record['pred'])
                current_ktc = record['current_ktc']
                
                # Calculate actual delta
                original_ktc = pred.get('current_ktc', current_ktc)
                actual_delta = current_ktc - original_ktc
                actual_delta_pct = (actual_delta / original_ktc * 100) if original_ktc else 0
                
                predicted_delta = pred.get('predicted_ktc_delta', 0)
                prediction_error = actual_delta - predicted_delta
                
                # Update prediction with actual results
                session.run("""
                    MATCH (pred:Prediction {prediction_id: $prediction_id})
                    SET pred.actual_ktc_delta = $actual_delta,
                        pred.actual_ktc_delta_pct = $actual_delta_pct,
                        pred.prediction_error = $prediction_error,
                        pred.evaluated = true,
                        pred.evaluated_date = date()
                """, {
                    'prediction_id': pred['prediction_id'],
                    'actual_delta': actual_delta,
                    'actual_delta_pct': actual_delta_pct,
                    'prediction_error': prediction_error
                })
                
                evaluated += 1
                print(f"  {record['player_name']}: Predicted {predicted_delta:+d}, Actual {actual_delta:+d}, Error {prediction_error:+d}")
        
        print(f"✅ Evaluated {evaluated} predictions")
        return evaluated
    
    def get_model_accuracy(self, days: int = 30) -> dict:
        """Calculate accuracy metrics for recent predictions."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (pred:Prediction)
                WHERE pred.evaluated = true
                  AND pred.evaluated_date > date() - duration($days)
                RETURN pred.predicted_ktc_delta as predicted,
                       pred.actual_ktc_delta as actual,
                       pred.prediction_error as error
            """, days=f'P{days}D')
            
            data = [dict(r) for r in result]
        
        if not data:
            return {'error': 'No evaluated predictions found'}
        
        df = pd.DataFrame(data)
        
        mae = df['error'].abs().mean()
        
        # Directional accuracy (did we predict the right direction?)
        df['predicted_direction'] = df['predicted'].apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
        df['actual_direction'] = df['actual'].apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
        directional_accuracy = (df['predicted_direction'] == df['actual_direction']).mean()
        
        # Within 5% accuracy
        df['within_5pct'] = df.apply(
            lambda r: abs(r['error']) <= abs(r['actual'] * 0.05) if r['actual'] != 0 else abs(r['error']) <= 50,
            axis=1
        )
        pct_5_accuracy = df['within_5pct'].mean()
        
        return {
            'sample_size': len(df),
            'mean_absolute_error': round(mae, 1),
            'directional_accuracy': round(directional_accuracy * 100, 1),
            'within_5pct_accuracy': round(pct_5_accuracy * 100, 1),
            'evaluation_period_days': days
        }


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def main():
    """Run the temporal data pipeline."""
    print("\n" + "=" * 60)
    print("🏈 DYNASTY EDGE - Temporal Data Pipeline")
    print("=" * 60 + "\n")
    
    pipeline = TemporalDataPipeline(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    
    try:
        # Setup
        pipeline.create_temporal_constraints()
        
        # Load KTC data and create snapshots
        ktc_path = os.path.join(os.getenv('DATA_PATH', './data'), 'ktc_lucid_losers.csv')
        if os.path.exists(ktc_path):
            ktc_df = pd.read_csv(ktc_path)
            ktc_df.columns = ['player_name', 'position_rank', 'position', 'team', 'value', 
                              'age', 'rookie', 'oneqb_rank', 'oneqb_value', 'rdraft_rank', 'rdraft_value']
            ktc_df = ktc_df[ktc_df['position'].isin(['QB', 'RB', 'WR', 'TE'])]
            
            print("\n📸 Creating player snapshots...")
            pipeline.batch_create_snapshots(ktc_df)
        
        # Run correlation analysis
        print("\n📊 Running correlation analysis...")
        correlations = pipeline.run_full_correlation_analysis()
        
        # Evaluate past predictions
        print("\n🎯 Evaluating past predictions...")
        pipeline.evaluate_predictions()
        
        # Show model accuracy
        print("\n📈 Model accuracy (last 30 days):")
        accuracy = pipeline.get_model_accuracy(30)
        for key, value in accuracy.items():
            print(f"  {key}: {value}")
        
        print("\n✅ Pipeline complete!")
        
    finally:
        pipeline.close()


if __name__ == "__main__":
    main()
