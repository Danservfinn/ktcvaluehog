#!/usr/bin/env python3
"""
Update Neo4j Player Nodes with ML Projections
==============================================

Loads trained ensemble models and updates Railway Neo4j with projections.

Usage:
    python scripts/update_neo4j_projections.py              # Update all players
    python scripts/update_neo4j_projections.py --dry-run    # Preview without updating
    python scripts/update_neo4j_projections.py --position WR  # Update specific position
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import numpy as np
import torch
import joblib
import requests
from dotenv import load_dotenv

load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Neo4j Railway config
NEO4J_HTTP_URL = os.getenv(
    "NEO4J_HTTP_URL",
    "https://sparkling-commitment-production.up.railway.app/db/neo4j/tx/commit"
)
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "dynastyedge2025")

MODELS_DIR = project_root / 'data' / 'models'


class ProjectionUpdater:
    """Load trained models and generate projections for Neo4j update."""

    def __init__(self, models_dir: Path = MODELS_DIR):
        self.models_dir = Path(models_dir)
        self.models = {}
        self.scalers = None
        self.meta_model = None
        self.feature_cols = []
        self.device = self._get_device()

    def _get_device(self) -> torch.device:
        if torch.backends.mps.is_available():
            return torch.device('mps')
        elif torch.cuda.is_available():
            return torch.device('cuda')
        return torch.device('cpu')

    def load_models(self):
        """Load all trained ensemble components."""
        logger.info(f"Loading models from {self.models_dir}...")

        # Load sklearn models
        self.models['gbm'] = joblib.load(self.models_dir / 'optimized_gbm.pkl')
        self.models['rf'] = joblib.load(self.models_dir / 'optimized_rf.pkl')
        self.models['ridge'] = joblib.load(self.models_dir / 'optimized_ridge.pkl')

        # Load meta-model
        meta_path = self.models_dir / 'stacking_meta.pkl'
        if meta_path.exists():
            self.meta_model = joblib.load(meta_path)
            logger.info("Loaded stacking meta-model")

        # Load scalers
        self.scalers = joblib.load(self.models_dir / 'scalers.pkl')

        # Load neural network
        nn_checkpoint = torch.load(self.models_dir / 'optimized_nn.pt', map_location=self.device)
        from src.ml.neural_network_models import FeatureAttentionNN, SimpleFFN

        input_dim = nn_checkpoint['input_dim']
        if nn_checkpoint.get('model_type') == 'attention':
            self.models['nn'] = FeatureAttentionNN(input_dim, n_positions=4)
        else:
            self.models['nn'] = SimpleFFN(input_dim, n_positions=4)
        self.models['nn'].load_state_dict(nn_checkpoint['model_state'])
        self.models['nn'].to(self.device)
        self.models['nn'].eval()

        # Load feature columns
        with open(self.models_dir / 'feature_cols.json') as f:
            self.feature_cols = json.load(f)

        logger.info(f"Loaded {len(self.models)} base models + meta-model")
        logger.info(f"Features: {len(self.feature_cols)}")

    def neo4j_query(self, query: str, params: dict = None) -> list:
        """Execute Neo4j query via HTTP API."""
        data = {"statements": [{"statement": query, "parameters": params or {}}]}
        resp = requests.post(
            NEO4J_HTTP_URL,
            json=data,
            auth=(NEO4J_USER, NEO4J_PASSWORD),
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        result = resp.json()

        if result.get('errors'):
            raise RuntimeError(f"Neo4j error: {result['errors']}")

        # Parse results
        rows = []
        for r in result.get('results', []):
            columns = r.get('columns', [])
            for row_data in r.get('data', []):
                rows.append(dict(zip(columns, row_data['row'])))
        return rows

    def get_player_features_from_training_data(self, position: str = None) -> pd.DataFrame:
        """Load training data and use most recent season per player for prediction."""
        logger.info("Loading training data for prediction features...")

        # Load the training dataset
        data_path = project_root / 'data' / 'ml_training' / 'expanded_season_projection.parquet'
        if not data_path.exists():
            raise FileNotFoundError(f"Training data not found at {data_path}")

        df = pd.read_parquet(data_path)
        logger.info(f"Loaded training data: {len(df)} rows")

        # Filter by position if specified
        if position:
            df = df[df['position'] == position]

        # Get most recent season for each player
        df_latest = df.sort_values('season', ascending=False).groupby('player_id').first().reset_index()
        logger.info(f"Players with latest season data: {len(df_latest)}")

        return df_latest

    def get_neo4j_player_mapping(self) -> pd.DataFrame:
        """Get player ID mapping and KTC values from Neo4j."""
        logger.info("Fetching player mapping from Neo4j...")

        query = """
        MATCH (p:Player)
        WHERE p.position IN ['QB', 'RB', 'WR', 'TE']
          AND p.ktc_value IS NOT NULL
          AND p.ktc_value > 0
        RETURN
            p.gsis_id as gsis_id,
            p.sleeper_id as sleeper_id,
            p.name as name,
            p.position as position,
            p.ktc_value as ktc_value
        ORDER BY p.ktc_value DESC
        """

        results = self.neo4j_query(query)
        df = pd.DataFrame(results)
        logger.info(f"Retrieved {len(df)} player mappings from Neo4j")
        return df

    def build_features(self, df: pd.DataFrame) -> np.ndarray:
        """Build feature matrix matching training features."""
        logger.info("Building features...")

        # Create feature dataframe with zeros for missing features
        feature_df = pd.DataFrame(0, index=range(len(df)), columns=self.feature_cols)

        # Map available columns
        col_mappings = {
            'current_ppg': ['ppg_ppr', 'current_ppg'],
            'age': ['age'],
            'years_exp': ['years_exp'],
            'games_played': ['games', 'games_played'],
            'targets': ['targets'],
            'receptions': ['receptions'],
            'rec_yards': ['receiving_yards', 'rec_yards'],
            'rec_tds': ['receiving_tds', 'rec_tds'],
            'carries': ['carries'],
            'rush_yards': ['rushing_yards', 'rush_yards'],
            'rush_tds': ['rushing_tds', 'rush_tds'],
            'pass_yards': ['passing_yards', 'pass_yards'],
            'pass_tds': ['passing_tds', 'pass_tds'],
            'career_ppg': ['career_ppg'],
            'best_ppg': ['best_ppg'],
            'snap_pct': ['snap_pct', 'snap_percentage'],
            'ktc_value': ['ktc_value'],
        }

        # Fill in available features
        for feature_name in self.feature_cols:
            # Direct match
            if feature_name in df.columns:
                feature_df[feature_name] = df[feature_name].fillna(0).values
            else:
                # Try mapped columns
                for src, targets in col_mappings.items():
                    if feature_name in targets and src in df.columns:
                        feature_df[feature_name] = df[src].fillna(0).values
                        break

        # Calculate derived features if columns exist
        games = df['games_played'].fillna(1).replace(0, 1) if 'games_played' in df.columns else pd.Series([1]*len(df))

        if 'targets_per_game' in self.feature_cols and 'targets' in df.columns:
            feature_df['targets_per_game'] = df['targets'].fillna(0) / games

        if 'rec_yards_per_game' in self.feature_cols and 'rec_yards' in df.columns:
            feature_df['rec_yards_per_game'] = df['rec_yards'].fillna(0) / games

        if 'catch_rate' in self.feature_cols and 'targets' in df.columns and 'receptions' in df.columns:
            targets_safe = df['targets'].fillna(0).replace(0, np.nan)
            feature_df['catch_rate'] = (df['receptions'].fillna(0) / targets_safe).fillna(0)

        # Age curve features
        if 'age_score' in self.feature_cols and 'age' in df.columns:
            feature_df['age_score'] = 100 - (df['age'].fillna(25) - 25).abs() * 3

        # Log feature coverage
        non_zero_features = (feature_df != 0).any().sum()
        logger.info(f"Feature coverage: {non_zero_features}/{len(self.feature_cols)} features have non-zero values")

        X = feature_df.values.astype(np.float32)
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

        logger.info(f"Feature matrix: {X.shape}")
        return X

    def predict(self, X: np.ndarray, positions: np.ndarray) -> dict:
        """Generate ensemble predictions."""
        logger.info("Generating predictions...")

        # Scale features
        X_scaled = self.scalers['main'].transform(X)

        # Encode positions
        pos_encoder = self.scalers['pos_encoder']
        pos_encoded = pos_encoder.transform(positions)

        # Base model predictions
        gbm_preds = self.models['gbm'].predict(X_scaled)
        rf_preds = self.models['rf'].predict(X_scaled)
        ridge_preds = self.models['ridge'].predict(X_scaled)

        # Neural network prediction
        with torch.no_grad():
            X_tensor = torch.FloatTensor(X_scaled).to(self.device)
            pos_tensor = torch.LongTensor(pos_encoded).to(self.device)
            nn_preds = self.models['nn'](X_tensor, pos_tensor).cpu().numpy().flatten()

        # Ensemble with meta-model
        if self.meta_model is not None:
            meta_features = np.column_stack([nn_preds, gbm_preds, rf_preds, ridge_preds])
            ensemble_preds = self.meta_model.predict(meta_features)
        else:
            # Fixed weights fallback
            ensemble_preds = (
                0.3 * nn_preds + 0.35 * gbm_preds + 0.2 * rf_preds + 0.15 * ridge_preds
            )

        # Calculate confidence and range (Monte Carlo approximation)
        pred_std = np.std([nn_preds, gbm_preds, rf_preds, ridge_preds], axis=0)
        confidence = 1 - np.clip(pred_std / ensemble_preds.clip(1), 0, 1)

        # Floor/ceiling estimates (based on model spread)
        floor = ensemble_preds - 1.5 * pred_std
        ceiling = ensemble_preds + 1.5 * pred_std

        return {
            'ppg': ensemble_preds,
            'confidence': confidence,
            'floor': floor.clip(0),
            'ceiling': ceiling,
            'nn': nn_preds,
            'gbm': gbm_preds,
            'rf': rf_preds,
            'ridge': ridge_preds
        }

    def update_neo4j(self, df: pd.DataFrame, predictions: dict, dry_run: bool = False):
        """Update Neo4j Player nodes with projections."""
        logger.info(f"Updating Neo4j with {len(df)} projections...")

        # Calculate total points (17 game season)
        total_points = predictions['ppg'] * 17

        updates = []
        for idx, (_, row) in enumerate(df.iterrows()):
            player_id = row.get('gsis_id') or row.get('sleeper_id')
            if not player_id:
                continue

            update = {
                'id': player_id,
                'projected_ppg': round(float(predictions['ppg'][idx]), 2),
                'projected_points': round(float(total_points[idx]), 1),
                'projection_confidence': round(float(predictions['confidence'][idx]), 3),
                'projection_floor': round(float(predictions['floor'][idx] * 17), 1),
                'projection_ceiling': round(float(predictions['ceiling'][idx] * 17), 1),
                'games_projected': 17
            }
            updates.append(update)

        if dry_run:
            logger.info("DRY RUN - Would update these players:")
            for u in updates[:20]:
                logger.info(f"  {u['id']}: PPG={u['projected_ppg']:.1f}, Total={u['projected_points']:.0f}")
            logger.info(f"  ... and {len(updates) - 20} more")
            return 0

        # Batch update Neo4j
        updated = 0
        batch_size = 50

        for i in range(0, len(updates), batch_size):
            batch = updates[i:i+batch_size]

            query = """
            UNWIND $updates AS u
            MATCH (p:Player)
            WHERE p.gsis_id = u.id OR p.sleeper_id = u.id
            SET p.projected_ppg = u.projected_ppg,
                p.projected_points = u.projected_points,
                p.projection_confidence = u.projection_confidence,
                p.projection_floor = u.projection_floor,
                p.projection_ceiling = u.projection_ceiling,
                p.games_projected = u.games_projected,
                p.projection_updated = datetime()
            RETURN count(p) as updated
            """

            try:
                result = self.neo4j_query(query, {"updates": batch})
                batch_updated = result[0].get('updated', 0) if result else 0
                updated += batch_updated
                logger.info(f"  Batch {i//batch_size + 1}: {batch_updated} players updated")
            except Exception as e:
                logger.error(f"  Batch {i//batch_size + 1} failed: {e}")

        logger.info(f"Total updated: {updated} players")
        return updated


def main():
    parser = argparse.ArgumentParser(description='Update Neo4j with ML projections')
    parser.add_argument('--dry-run', action='store_true', help='Preview without updating')
    parser.add_argument('--position', type=str, help='Filter by position (QB, RB, WR, TE)')
    args = parser.parse_args()

    updater = ProjectionUpdater()

    # Load models
    updater.load_models()

    # Get player data from training dataset (has all features)
    df = updater.get_player_features_from_training_data(position=args.position)

    if len(df) == 0:
        logger.error("No players found in training data!")
        return

    # Use training data columns directly
    feature_cols = updater.feature_cols
    missing_cols = [c for c in feature_cols if c not in df.columns]
    available_cols = [c for c in feature_cols if c in df.columns]
    logger.info(f"Features: {len(available_cols)} available, {len(missing_cols)} missing")

    # Build feature matrix from training data
    X = df[feature_cols].fillna(0).values.astype(np.float32)
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    logger.info(f"Feature matrix: {X.shape}")

    # Generate predictions
    positions = df['position'].fillna('WR').values
    predictions = updater.predict(X, positions)

    # Get player mappings from Neo4j (only current players with KTC values)
    neo4j_mapping = updater.get_neo4j_player_mapping()
    neo4j_ids = set(neo4j_mapping['gsis_id'].dropna().tolist() + neo4j_mapping['sleeper_id'].dropna().tolist())
    id_to_name = {}
    for _, row in neo4j_mapping.iterrows():
        if row['gsis_id']:
            id_to_name[str(row['gsis_id'])] = row['name']
        if row['sleeper_id']:
            id_to_name[str(row['sleeper_id'])] = row['name']

    # Filter to only players currently in Neo4j
    df['in_neo4j'] = df['player_id'].astype(str).isin(neo4j_ids)
    df_current = df[df['in_neo4j']].copy()
    logger.info(f"Matched {len(df_current)} players to current Neo4j records")

    # Clip predictions at 0
    predictions['ppg'] = np.clip(predictions['ppg'], 0, None)
    predictions['floor'] = np.clip(predictions['floor'], 0, None)

    # Get corresponding predictions for current players
    current_mask = df['in_neo4j'].values
    current_predictions = {
        'ppg': predictions['ppg'][current_mask],
        'confidence': predictions['confidence'][current_mask],
        'floor': predictions['floor'][current_mask],
        'ceiling': predictions['ceiling'][current_mask],
    }

    # Add player names to df
    df_current['name'] = df_current['player_id'].astype(str).map(id_to_name)

    # Show top predictions
    logger.info("\nTop 15 Projected Players:")
    # Sort by ppg predictions within df_current
    df_current_with_preds = df_current.copy()
    df_current_with_preds['pred_ppg'] = current_predictions['ppg']
    df_current_with_preds['conf'] = current_predictions['confidence']
    top_players = df_current_with_preds.nlargest(15, 'pred_ppg')

    for _, row in top_players.iterrows():
        player_name = row.get('name') or row.get('player_name', 'Unknown')
        pos = row.get('position', '?')
        ppg = row['pred_ppg']
        conf = row['conf']
        curr_ppg = row.get('ppg_ppr', 0) or 0
        logger.info(f"  {str(player_name)[:25]:25} {pos:3} Curr={curr_ppg:.1f} -> Proj={ppg:.1f} Conf={conf:.2f}")

    # Map predictions to player IDs
    df_current['gsis_id'] = df_current['player_id'].astype(str)

    # Update Neo4j
    updated = updater.update_neo4j(df_current, current_predictions, dry_run=args.dry_run)

    if not args.dry_run:
        logger.info(f"\nSuccessfully updated {updated} player projections in Neo4j!")


if __name__ == "__main__":
    main()
