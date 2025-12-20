#!/usr/bin/env python3
"""
Neural Network Training Pipeline for Dynasty Fantasy Football
================================================================

Trains neural network models to predict:
1. Future fantasy production (PPG 0.5 PPR)
2. Future KTC dynasty trade value

Integrates all available data sources:
- Historical stats (season, weekly)
- Athletic/combine data
- Injury history
- Depth chart/role data
- Betting data (Elo, spreads, O/U)
- KTC value trends

Usage:
    python scripts/train_neural_networks.py                # Train all models
    python scripts/train_neural_networks.py --production   # Fantasy production only
    python scripts/train_neural_networks.py --ktc          # KTC value only
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split
from datetime import datetime
import argparse
import logging
import warnings
warnings.filterwarnings('ignore')

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# DATA EXTRACTION FROM NEO4J
# =============================================================================

def get_driver():
    """Get Neo4j driver."""
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")
    auth = (user, password) if user and password else None
    return GraphDatabase.driver(uri, auth=auth)


def fetch_comprehensive_training_data():
    """Fetch all data needed for neural network training."""
    logger.info("Fetching comprehensive training data from Neo4j...")
    driver = get_driver()

    with driver.session() as session:
        # Main query: season stats with career context
        result = session.run("""
            MATCH (s:HistoricalSeasonStats)
            WHERE s.position IN ['QB', 'RB', 'WR', 'TE']
              AND s.games >= 4
              AND s.season >= 2016

            // Get player info
            OPTIONAL MATCH (p:Player {gsis_id: s.player_id})

            // Get combine data
            OPTIONAL MATCH (c:CombineResult {player_id: s.player_id})

            // Get draft data
            OPTIONAL MATCH (d:DraftPick {player_id: s.player_id})

            // Get injury profile
            OPTIONAL MATCH (ip:PlayerInjuryProfile {player_id: s.player_id})

            // Get role profile
            OPTIONAL MATCH (rp:PlayerRoleProfile {player_id: s.player_id})

            RETURN
                s.player_id as player_id,
                coalesce(p.name, s.player_name) as player_name,
                s.position as position,
                s.team as team,
                s.season as season,
                s.games as games,

                // Fantasy production
                s.ppg_ppr as ppg_ppr,
                s.ppg_std as ppg_std,
                coalesce(s.ppg_half_ppr, (coalesce(s.ppg_ppr, 0) + coalesce(s.ppg_std, 0)) / 2) as ppg_half_ppr,

                // Passing
                s.passing_yards as passing_yards,
                s.passing_tds as passing_tds,
                s.interceptions as interceptions,
                s.completions as completions,
                s.pass_attempts as pass_attempts,

                // Rushing
                s.rushing_yards as rushing_yards,
                s.rushing_tds as rushing_tds,
                s.carries as carries,

                // Receiving
                s.receiving_yards as receiving_yards,
                s.receiving_tds as receiving_tds,
                s.receptions as receptions,
                s.targets as targets,

                // Player metadata
                p.age as current_age,
                p.years_exp as years_exp,

                // Combine
                c.forty_yard as forty_time,
                c.vertical_jump as vertical,
                c.broad_jump as broad_jump,
                c.three_cone as three_cone,
                c.bench_press as bench,
                c.height as height,
                c.weight as weight,

                // Draft
                d.round as draft_round,
                d.pick as draft_pick,

                // Injury
                ip.overall_injury_risk as injury_risk,
                ip.games_listed_out as career_games_out,
                ip.soft_tissue_leg_count as soft_tissue_injuries,
                ip.concussion_count as concussions,

                // Role
                rp.starter_rate as starter_rate,
                rp.primary_role as primary_role

            ORDER BY s.player_id, s.season
        """)

        data = [dict(r) for r in result]
        logger.info(f"  Fetched {len(data):,} season records")

    driver.close()
    return pd.DataFrame(data)


def fetch_ktc_data():
    """Fetch KTC value data for value prediction."""
    logger.info("Fetching KTC value data...")
    driver = get_driver()

    with driver.session() as session:
        result = session.run("""
            MATCH (kt:KTCTrend)
            OPTIONAL MATCH (p:Player)
            WHERE toLower(p.name) = toLower(kt.player_name)
            RETURN
                kt.player_name as player_name,
                kt.position as position,
                kt.team as team,
                kt.current_ktc as ktc_value,
                kt.change_30d as change_30d,
                kt.change_30d_pct as change_30d_pct,
                kt.momentum_pct as momentum_pct,
                kt.trend_direction as trend_direction,
                kt.value_signal as value_signal,
                kt.pct_off_peak as pct_off_peak,
                p.gsis_id as player_id
        """)

        data = [dict(r) for r in result]
        logger.info(f"  Fetched {len(data):,} KTC records")

    driver.close()
    return pd.DataFrame(data)


def fetch_team_elo_data():
    """Fetch team Elo ratings from Game nodes."""
    logger.info("Fetching team Elo data...")
    driver = get_driver()

    with driver.session() as session:
        # Get average Elo by team and season
        result = session.run("""
            MATCH (g:Game)
            WHERE g.home_elo_pre IS NOT NULL
              AND g.season >= 2016
            WITH g.season as season,
                 g.home_team as team,
                 avg(g.home_elo_pre) as avg_elo
            RETURN season, team, avg_elo

            UNION ALL

            MATCH (g:Game)
            WHERE g.away_elo_pre IS NOT NULL
              AND g.season >= 2016
            WITH g.season as season,
                 g.away_team as team,
                 avg(g.away_elo_pre) as avg_elo
            RETURN season, team, avg_elo
        """)

        data = [dict(r) for r in result]
        logger.info(f"  Fetched {len(data):,} team-season Elo records")

    driver.close()

    # Aggregate to team-season level
    df = pd.DataFrame(data)
    if len(df) > 0:
        elo_df = df.groupby(['season', 'team']).agg({'avg_elo': 'mean'}).reset_index()
        return elo_df
    return pd.DataFrame()


# =============================================================================
# FEATURE ENGINEERING
# =============================================================================

def engineer_features(df: pd.DataFrame, elo_df: pd.DataFrame = None) -> pd.DataFrame:
    """Engineer comprehensive features for neural network."""
    logger.info("Engineering features...")

    df = df.copy()

    # Calculate age at season
    if 'current_age' in df.columns and 'years_exp' in df.columns:
        # Estimate age at season based on current age and experience
        df['age_at_season'] = df.apply(
            lambda r: r['current_age'] - (2024 - r['season']) if pd.notna(r['current_age']) else None,
            axis=1
        )

    # Games played rate
    df['games_rate'] = df['games'] / 17

    # Per-game stats
    df['pass_yards_pg'] = df['passing_yards'].fillna(0) / df['games'].replace(0, 1)
    df['rush_yards_pg'] = df['rushing_yards'].fillna(0) / df['games'].replace(0, 1)
    df['rec_yards_pg'] = df['receiving_yards'].fillna(0) / df['games'].replace(0, 1)
    df['targets_pg'] = df['targets'].fillna(0) / df['games'].replace(0, 1)
    df['carries_pg'] = df['carries'].fillna(0) / df['games'].replace(0, 1)
    df['receptions_pg'] = df['receptions'].fillna(0) / df['games'].replace(0, 1)

    # Efficiency metrics
    df['yards_per_carry'] = df['rushing_yards'].fillna(0) / df['carries'].replace(0, 1)
    df['yards_per_target'] = df['receiving_yards'].fillna(0) / df['targets'].replace(0, 1)
    df['catch_rate'] = df['receptions'].fillna(0) / df['targets'].replace(0, 1)
    df['td_rate'] = (
        df['passing_tds'].fillna(0) +
        df['rushing_tds'].fillna(0) +
        df['receiving_tds'].fillna(0)
    ) / df['games'].replace(0, 1)

    # Total opportunity
    df['total_touches'] = df['carries'].fillna(0) + df['receptions'].fillna(0)
    df['total_yards'] = (
        df['passing_yards'].fillna(0) +
        df['rushing_yards'].fillna(0) +
        df['receiving_yards'].fillna(0)
    )
    df['total_tds'] = (
        df['passing_tds'].fillna(0) +
        df['rushing_tds'].fillna(0) +
        df['receiving_tds'].fillna(0)
    )

    # Athletic metrics
    if 'forty_time' in df.columns:
        # Speed score (weight-adjusted 40 time)
        df['speed_score'] = df.apply(
            lambda r: (r['weight'] * 200) / (r['forty_time'] ** 4)
            if pd.notna(r['forty_time']) and pd.notna(r['weight']) and r['forty_time'] > 0
            else None,
            axis=1
        )

        # Explosion score
        df['explosion_score'] = df['vertical'].fillna(0) + df['broad_jump'].fillna(0) / 10

    # Draft capital (inverse pick number)
    df['draft_capital'] = 1 / (df['draft_pick'].fillna(256) + 1) * 100

    # Injury risk encoding
    injury_risk_map = {'low': 0, 'medium': 1, 'high': 2}
    df['injury_risk_score'] = df['injury_risk'].map(injury_risk_map).fillna(0)

    # Role encoding
    role_map = {
        'established_starter': 3,
        'starter_backup_mix': 2,
        'primary_backup': 1,
        'depth': 0
    }
    df['role_score'] = df['primary_role'].map(role_map).fillna(0)

    # Merge team Elo if available
    if elo_df is not None and len(elo_df) > 0:
        df = df.merge(
            elo_df.rename(columns={'avg_elo': 'team_elo'}),
            on=['season', 'team'],
            how='left'
        )
        df['team_elo'] = df['team_elo'].fillna(1500)  # Default Elo
    else:
        df['team_elo'] = 1500

    # Career features (computed per player)
    df = df.sort_values(['player_id', 'season'])

    career_features = []
    for player_id in df['player_id'].unique():
        player_df = df[df['player_id'] == player_id].sort_values('season')

        for i, (idx, row) in enumerate(player_df.iterrows()):
            history = player_df.iloc[:i+1]

            career_features.append({
                'idx': idx,
                'seasons_played': len(history),
                'career_ppg': history['ppg_half_ppr'].mean() if 'ppg_half_ppr' in history else 0,
                'peak_ppg': history['ppg_half_ppr'].max() if 'ppg_half_ppr' in history else 0,
                'career_games': history['games'].sum(),
                'ppg_trend': np.polyfit(range(len(history)), history['ppg_half_ppr'].fillna(0).values, 1)[0] if len(history) > 1 else 0,
                'ppg_std': history['ppg_half_ppr'].std() if len(history) > 1 else 0,
            })

    career_df = pd.DataFrame(career_features).set_index('idx')
    # Rename overlapping columns
    career_df = career_df.rename(columns={'ppg_std': 'career_ppg_std'})
    df = df.join(career_df, rsuffix='_career')

    # Current vs peak ratio
    df['curr_vs_peak'] = df['ppg_half_ppr'] / df['peak_ppg'].replace(0, 1)

    logger.info(f"  Created {len(df.columns)} total features")
    return df


def create_training_pairs(df: pd.DataFrame) -> pd.DataFrame:
    """Create year-over-year training pairs (features from Y -> target Y+1)."""
    logger.info("Creating year-over-year training pairs...")

    pairs = []

    for player_id in df['player_id'].unique():
        player_df = df[df['player_id'] == player_id].sort_values('season')

        for i in range(len(player_df) - 1):
            curr = player_df.iloc[i]
            next_season = player_df.iloc[i + 1]

            # Only consecutive seasons
            if next_season['season'] - curr['season'] != 1:
                continue

            pair = curr.to_dict()
            pair['target_ppg_half_ppr'] = next_season['ppg_half_ppr']
            pair['target_games'] = next_season['games']
            pair['target_season'] = next_season['season']
            pairs.append(pair)

    pairs_df = pd.DataFrame(pairs)
    logger.info(f"  Created {len(pairs_df):,} training pairs")
    return pairs_df


# =============================================================================
# NEURAL NETWORK MODELS
# =============================================================================

class FantasyDataset(Dataset):
    """PyTorch Dataset for fantasy prediction."""

    def __init__(self, X: np.ndarray, y: np.ndarray, positions: np.ndarray):
        self.X = torch.FloatTensor(X)
        self.y = torch.FloatTensor(y)
        self.positions = torch.LongTensor(positions)

    def __len__(self):
        return len(self.X)

    def __getitem__(self, idx):
        return self.X[idx], self.positions[idx], self.y[idx]


class ProductionNN(nn.Module):
    """Neural network for fantasy production prediction."""

    def __init__(self, input_dim: int, n_positions: int = 4):
        super().__init__()

        self.pos_embedding = nn.Embedding(n_positions, 16)

        self.network = nn.Sequential(
            nn.Linear(input_dim + 16, 256),
            nn.ReLU(),
            nn.BatchNorm1d(256),
            nn.Dropout(0.3),

            nn.Linear(256, 128),
            nn.ReLU(),
            nn.BatchNorm1d(128),
            nn.Dropout(0.3),

            nn.Linear(128, 64),
            nn.ReLU(),
            nn.BatchNorm1d(64),
            nn.Dropout(0.2),

            nn.Linear(64, 32),
            nn.ReLU(),

            nn.Linear(32, 1)
        )

    def forward(self, x, position):
        pos_emb = self.pos_embedding(position)
        x = torch.cat([x, pos_emb], dim=1)
        return self.network(x).squeeze(-1)


class KTCValueNN(nn.Module):
    """Neural network for KTC dynasty value prediction."""

    def __init__(self, input_dim: int, n_positions: int = 4):
        super().__init__()

        self.pos_embedding = nn.Embedding(n_positions, 32)

        self.network = nn.Sequential(
            nn.Linear(input_dim + 32, 512),
            nn.ReLU(),
            nn.BatchNorm1d(512),
            nn.Dropout(0.3),

            nn.Linear(512, 256),
            nn.ReLU(),
            nn.BatchNorm1d(256),
            nn.Dropout(0.3),

            nn.Linear(256, 128),
            nn.ReLU(),
            nn.BatchNorm1d(128),
            nn.Dropout(0.2),

            nn.Linear(128, 64),
            nn.ReLU(),

            nn.Linear(64, 1)
        )

    def forward(self, x, position):
        pos_emb = self.pos_embedding(position)
        x = torch.cat([x, pos_emb], dim=1)
        # Output is log(KTC) for better scaling
        return self.network(x).squeeze(-1)


# =============================================================================
# TRAINING FUNCTIONS
# =============================================================================

def train_production_model(df: pd.DataFrame, device: str = 'cpu') -> dict:
    """Train neural network for fantasy production prediction."""
    logger.info("\n" + "=" * 70)
    logger.info("TRAINING FANTASY PRODUCTION NEURAL NETWORK")
    logger.info("=" * 70)

    # Feature columns
    feature_cols = [
        'ppg_half_ppr', 'games', 'games_rate',
        'pass_yards_pg', 'rush_yards_pg', 'rec_yards_pg',
        'targets_pg', 'carries_pg', 'receptions_pg',
        'yards_per_carry', 'yards_per_target', 'catch_rate', 'td_rate',
        'total_touches', 'total_yards', 'total_tds',
        'speed_score', 'explosion_score', 'draft_capital',
        'injury_risk_score', 'role_score', 'team_elo',
        'seasons_played', 'career_ppg', 'peak_ppg', 'career_games',
        'ppg_trend', 'career_ppg_std', 'curr_vs_peak',
        'age_at_season', 'starter_rate'
    ]

    # Filter to available columns
    available_cols = [c for c in feature_cols if c in df.columns]
    logger.info(f"Using {len(available_cols)} features")

    # Prepare data
    X = df[available_cols].fillna(0).values
    y = df['target_ppg_half_ppr'].fillna(0).values

    # Encode positions
    pos_encoder = LabelEncoder()
    pos_encoder.fit(['QB', 'RB', 'WR', 'TE'])
    positions = pos_encoder.transform(df['position'].fillna('RB').values)

    # Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Split data
    X_train, X_test, y_train, y_test, pos_train, pos_test = train_test_split(
        X_scaled, y, positions, test_size=0.2, random_state=42
    )

    # Create datasets
    train_dataset = FantasyDataset(X_train, y_train, pos_train)
    test_dataset = FantasyDataset(X_test, y_test, pos_test)

    train_loader = DataLoader(train_dataset, batch_size=64, shuffle=True)
    test_loader = DataLoader(test_dataset, batch_size=64)

    # Create model
    model = ProductionNN(len(available_cols), n_positions=4).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=0.01)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5, factor=0.5)
    criterion = nn.MSELoss()

    # Training loop
    best_val_loss = float('inf')
    patience_counter = 0
    history = {'train_loss': [], 'val_loss': [], 'val_r2': []}

    logger.info(f"Training on {len(train_dataset):,} samples, validating on {len(test_dataset):,}")

    for epoch in range(100):
        # Train
        model.train()
        train_loss = 0
        for X_batch, pos_batch, y_batch in train_loader:
            X_batch = X_batch.to(device)
            pos_batch = pos_batch.to(device)
            y_batch = y_batch.to(device)

            optimizer.zero_grad()
            pred = model(X_batch, pos_batch)
            loss = criterion(pred, y_batch)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            train_loss += loss.item()

        train_loss /= len(train_loader)

        # Validate
        model.eval()
        val_loss = 0
        preds, actuals = [], []
        with torch.no_grad():
            for X_batch, pos_batch, y_batch in test_loader:
                X_batch = X_batch.to(device)
                pos_batch = pos_batch.to(device)
                y_batch = y_batch.to(device)

                pred = model(X_batch, pos_batch)
                val_loss += criterion(pred, y_batch).item()
                preds.extend(pred.cpu().numpy())
                actuals.extend(y_batch.cpu().numpy())

        val_loss /= len(test_loader)

        # Calculate R²
        preds = np.array(preds)
        actuals = np.array(actuals)
        ss_res = np.sum((actuals - preds) ** 2)
        ss_tot = np.sum((actuals - np.mean(actuals)) ** 2)
        r2 = 1 - (ss_res / ss_tot)

        history['train_loss'].append(train_loss)
        history['val_loss'].append(val_loss)
        history['val_r2'].append(r2)

        scheduler.step(val_loss)

        if (epoch + 1) % 10 == 0:
            logger.info(f"Epoch {epoch+1}: Train Loss={train_loss:.4f}, Val Loss={val_loss:.4f}, R²={r2:.4f}")

        # Early stopping
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            best_state = model.state_dict().copy()
        else:
            patience_counter += 1
            if patience_counter >= 15:
                logger.info(f"Early stopping at epoch {epoch+1}")
                break

    # Restore best model
    model.load_state_dict(best_state)

    # Final metrics
    rmse = np.sqrt(np.mean((preds - actuals) ** 2))
    mae = np.mean(np.abs(preds - actuals))

    logger.info(f"\nFinal Results:")
    logger.info(f"  R² Score: {r2:.4f}")
    logger.info(f"  RMSE: {rmse:.2f} PPG")
    logger.info(f"  MAE: {mae:.2f} PPG")

    # Save model
    model_dir = Path('data/models')
    model_dir.mkdir(parents=True, exist_ok=True)

    torch.save({
        'model_state': model.state_dict(),
        'scaler': scaler,
        'pos_encoder': pos_encoder,
        'feature_cols': available_cols,
        'metrics': {'r2': r2, 'rmse': rmse, 'mae': mae}
    }, model_dir / 'production_nn.pt')

    logger.info(f"  Model saved to {model_dir / 'production_nn.pt'}")

    return {
        'model': model,
        'scaler': scaler,
        'pos_encoder': pos_encoder,
        'feature_cols': available_cols,
        'metrics': {'r2': r2, 'rmse': rmse, 'mae': mae}
    }


def train_ktc_model(df: pd.DataFrame, ktc_df: pd.DataFrame, device: str = 'cpu') -> dict:
    """Train neural network for KTC value prediction."""
    logger.info("\n" + "=" * 70)
    logger.info("TRAINING KTC VALUE NEURAL NETWORK")
    logger.info("=" * 70)

    # Merge KTC data with latest season stats
    latest_season = df.groupby('player_id').apply(lambda x: x.loc[x['season'].idxmax()]).reset_index(drop=True)

    # Normalize names for matching
    latest_season['name_normalized'] = latest_season['player_name'].str.lower().str.strip()
    ktc_df['name_normalized'] = ktc_df['player_name'].str.lower().str.strip()

    # Match by normalized name (KTC uses player names)
    merged = latest_season.merge(
        ktc_df[['name_normalized', 'ktc_value', 'position']].rename(columns={'position': 'ktc_position'}),
        on='name_normalized',
        how='inner'
    )

    # Filter to valid KTC values
    merged = merged[merged['ktc_value'] > 0].copy()

    logger.info(f"Matched {len(merged):,} players with KTC values")

    if len(merged) < 50:
        logger.warning("Not enough matched players for KTC training")
        return None

    # Feature columns
    feature_cols = [
        'ppg_half_ppr', 'games', 'games_rate',
        'pass_yards_pg', 'rush_yards_pg', 'rec_yards_pg',
        'targets_pg', 'carries_pg', 'receptions_pg',
        'yards_per_carry', 'yards_per_target', 'catch_rate', 'td_rate',
        'total_touches', 'total_yards', 'total_tds',
        'speed_score', 'explosion_score', 'draft_capital',
        'injury_risk_score', 'role_score', 'team_elo',
        'seasons_played', 'career_ppg', 'peak_ppg', 'career_games',
        'ppg_trend', 'career_ppg_std', 'curr_vs_peak',
        'age_at_season', 'starter_rate'
    ]

    available_cols = [c for c in feature_cols if c in merged.columns]
    logger.info(f"Using {len(available_cols)} features")

    # Prepare data
    X = merged[available_cols].fillna(0).values
    y = np.log1p(merged['ktc_value'].values)  # Log transform for better scaling

    # Encode positions
    pos_encoder = LabelEncoder()
    pos_encoder.fit(['QB', 'RB', 'WR', 'TE'])
    positions = pos_encoder.transform(merged['position'].fillna('RB').values)

    # Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Split data
    X_train, X_test, y_train, y_test, pos_train, pos_test = train_test_split(
        X_scaled, y, positions, test_size=0.2, random_state=42
    )

    # Create datasets
    train_dataset = FantasyDataset(X_train, y_train, pos_train)
    test_dataset = FantasyDataset(X_test, y_test, pos_test)

    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
    test_loader = DataLoader(test_dataset, batch_size=32)

    # Create model
    model = KTCValueNN(len(available_cols), n_positions=4).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=5e-4, weight_decay=0.01)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5, factor=0.5)
    criterion = nn.MSELoss()

    # Training loop
    best_val_loss = float('inf')
    patience_counter = 0

    logger.info(f"Training on {len(train_dataset):,} samples, validating on {len(test_dataset):,}")

    for epoch in range(100):
        # Train
        model.train()
        train_loss = 0
        for X_batch, pos_batch, y_batch in train_loader:
            X_batch = X_batch.to(device)
            pos_batch = pos_batch.to(device)
            y_batch = y_batch.to(device)

            optimizer.zero_grad()
            pred = model(X_batch, pos_batch)
            loss = criterion(pred, y_batch)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            train_loss += loss.item()

        train_loss /= len(train_loader)

        # Validate
        model.eval()
        val_loss = 0
        preds, actuals = [], []
        with torch.no_grad():
            for X_batch, pos_batch, y_batch in test_loader:
                X_batch = X_batch.to(device)
                pos_batch = pos_batch.to(device)
                y_batch = y_batch.to(device)

                pred = model(X_batch, pos_batch)
                val_loss += criterion(pred, y_batch).item()
                preds.extend(pred.cpu().numpy())
                actuals.extend(y_batch.cpu().numpy())

        val_loss /= len(test_loader)

        # Calculate R² on log scale
        preds = np.array(preds)
        actuals = np.array(actuals)
        ss_res = np.sum((actuals - preds) ** 2)
        ss_tot = np.sum((actuals - np.mean(actuals)) ** 2)
        r2 = 1 - (ss_res / ss_tot)

        scheduler.step(val_loss)

        if (epoch + 1) % 10 == 0:
            logger.info(f"Epoch {epoch+1}: Train Loss={train_loss:.4f}, Val Loss={val_loss:.4f}, R²={r2:.4f}")

        # Early stopping
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            best_state = model.state_dict().copy()
        else:
            patience_counter += 1
            if patience_counter >= 15:
                logger.info(f"Early stopping at epoch {epoch+1}")
                break

    # Restore best model
    model.load_state_dict(best_state)

    # Convert back to original scale for metrics
    preds_original = np.expm1(preds)
    actuals_original = np.expm1(actuals)

    rmse = np.sqrt(np.mean((preds_original - actuals_original) ** 2))
    mae = np.mean(np.abs(preds_original - actuals_original))

    logger.info(f"\nFinal Results:")
    logger.info(f"  R² Score (log): {r2:.4f}")
    logger.info(f"  RMSE: {rmse:.0f} KTC points")
    logger.info(f"  MAE: {mae:.0f} KTC points")

    # Save model
    model_dir = Path('data/models')
    model_dir.mkdir(parents=True, exist_ok=True)

    torch.save({
        'model_state': model.state_dict(),
        'scaler': scaler,
        'pos_encoder': pos_encoder,
        'feature_cols': available_cols,
        'metrics': {'r2': r2, 'rmse': rmse, 'mae': mae}
    }, model_dir / 'ktc_nn.pt')

    logger.info(f"  Model saved to {model_dir / 'ktc_nn.pt'}")

    return {
        'model': model,
        'scaler': scaler,
        'pos_encoder': pos_encoder,
        'feature_cols': available_cols,
        'metrics': {'r2': r2, 'rmse': rmse, 'mae': mae}
    }


# =============================================================================
# PROJECTION GENERATION
# =============================================================================

def generate_projections(
    df: pd.DataFrame,
    production_result: dict,
    ktc_result: dict,
    device: str = 'cpu'
) -> pd.DataFrame:
    """Generate projections for all current players."""
    logger.info("\n" + "=" * 70)
    logger.info("GENERATING 2025 PROJECTIONS")
    logger.info("=" * 70)

    # Get latest season for each player
    latest = df.groupby('player_id').apply(
        lambda x: x.loc[x['season'].idxmax()]
    ).reset_index(drop=True)

    logger.info(f"Generating projections for {len(latest):,} players")

    projections = []

    for _, row in latest.iterrows():
        proj = {
            'player_id': row['player_id'],
            'player_name': row['player_name'],
            'position': row['position'],
            'team': row['team'],
            'season': 2024,  # Base season
            'projected_season': 2025
        }

        # Production prediction
        if production_result is not None:
            model = production_result['model']
            scaler = production_result['scaler']
            pos_encoder = production_result['pos_encoder']
            feature_cols = production_result['feature_cols']

            X = row[feature_cols].fillna(0).values.reshape(1, -1)
            X_scaled = scaler.transform(X)
            pos = pos_encoder.transform([row['position']])[0]

            model.eval()
            with torch.no_grad():
                X_tensor = torch.FloatTensor(X_scaled).to(device)
                pos_tensor = torch.LongTensor([pos]).to(device)
                pred = model(X_tensor, pos_tensor).cpu().numpy()[0]

            proj['projected_ppg_2025'] = max(0, pred)
            proj['projected_fpts_2025'] = proj['projected_ppg_2025'] * 17

        # KTC prediction
        if ktc_result is not None:
            model = ktc_result['model']
            scaler = ktc_result['scaler']
            pos_encoder = ktc_result['pos_encoder']
            feature_cols = ktc_result['feature_cols']

            X = row[feature_cols].fillna(0).values.reshape(1, -1)
            X_scaled = scaler.transform(X)
            pos = pos_encoder.transform([row['position']])[0]

            model.eval()
            with torch.no_grad():
                X_tensor = torch.FloatTensor(X_scaled).to(device)
                pos_tensor = torch.LongTensor([pos]).to(device)
                pred = model(X_tensor, pos_tensor).cpu().numpy()[0]

            proj['projected_ktc_2025'] = max(0, np.expm1(pred))

        projections.append(proj)

    proj_df = pd.DataFrame(projections)

    # Save projections
    proj_df.to_csv('data/models/nn_projections_2025.csv', index=False)
    logger.info(f"  Saved projections to data/models/nn_projections_2025.csv")

    return proj_df


def store_projections_to_neo4j(proj_df: pd.DataFrame):
    """Store projections to Neo4j Player nodes."""
    logger.info("Storing projections to Neo4j...")

    driver = get_driver()

    with driver.session() as session:
        # Prepare records
        records = proj_df.to_dict('records')

        session.run("""
            UNWIND $records as r
            MATCH (p:Player)
            WHERE p.gsis_id = r.player_id OR toLower(p.name) = toLower(r.player_name)
            SET p.nn_projected_ppg_2025 = r.projected_ppg_2025,
                p.nn_projected_fpts_2025 = r.projected_fpts_2025,
                p.nn_projected_ktc_2025 = r.projected_ktc_2025,
                p.nn_projection_updated = datetime()
        """, {'records': records})

        # Verify
        result = session.run("""
            MATCH (p:Player)
            WHERE p.nn_projected_ppg_2025 IS NOT NULL
            RETURN count(p) as updated
        """)
        updated = result.single()['updated']
        logger.info(f"  Updated {updated:,} players with projections")

    driver.close()


def print_top_projections(proj_df: pd.DataFrame):
    """Print top projections by position."""
    print("\n" + "=" * 70)
    print("TOP 2025 PROJECTIONS BY POSITION (Neural Network)")
    print("=" * 70)

    for pos in ['QB', 'RB', 'WR', 'TE']:
        pos_df = proj_df[proj_df['position'] == pos]

        if 'projected_ppg_2025' in pos_df.columns:
            top = pos_df.nlargest(10, 'projected_ppg_2025')

            print(f"\n{pos} - Top 10 Projected PPG (0.5 PPR):")
            print("-" * 60)
            for rank, (_, row) in enumerate(top.iterrows(), 1):
                name = row.get('player_name', 'Unknown')
                if name is None:
                    name = 'Unknown'
                ppg = row.get('projected_ppg_2025', 0) or 0
                fpts = row.get('projected_fpts_2025', 0) or 0
                ktc = row.get('projected_ktc_2025', 0) or 0
                print(f"  {rank:2}. {name:<25} "
                      f"PPG: {ppg:5.1f} | FPTS: {fpts:5.0f} | KTC: {ktc:,.0f}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Train Neural Network Models')
    parser.add_argument('--production', action='store_true', help='Train only production model')
    parser.add_argument('--ktc', action='store_true', help='Train only KTC model')
    parser.add_argument('--no-projections', action='store_true', help='Skip projection generation')

    args = parser.parse_args()

    # Device selection
    if torch.cuda.is_available():
        device = 'cuda'
    elif torch.backends.mps.is_available():
        device = 'mps'
    else:
        device = 'cpu'

    logger.info(f"Using device: {device}")

    start_time = datetime.now()

    print("=" * 70)
    print("NEURAL NETWORK TRAINING PIPELINE")
    print(f"Started: {start_time}")
    print("=" * 70)

    # Fetch data
    season_df = fetch_comprehensive_training_data()
    ktc_df = fetch_ktc_data()
    elo_df = fetch_team_elo_data()

    # Engineer features
    df = engineer_features(season_df, elo_df)

    # Create training pairs
    pairs_df = create_training_pairs(df)

    production_result = None
    ktc_result = None

    # Train models
    if not args.ktc:
        production_result = train_production_model(pairs_df, device)

    if not args.production:
        ktc_result = train_ktc_model(df, ktc_df, device)

    # Generate projections
    if not args.no_projections:
        proj_df = generate_projections(df, production_result, ktc_result, device)
        store_projections_to_neo4j(proj_df)
        print_top_projections(proj_df)

    duration = datetime.now() - start_time

    print("\n" + "=" * 70)
    print("TRAINING COMPLETE")
    print("=" * 70)
    print(f"Duration: {duration}")

    if production_result:
        print(f"\nProduction Model: R²={production_result['metrics']['r2']:.4f}, "
              f"RMSE={production_result['metrics']['rmse']:.2f} PPG")

    if ktc_result:
        print(f"KTC Value Model: R²={ktc_result['metrics']['r2']:.4f}, "
              f"RMSE={ktc_result['metrics']['rmse']:.0f} pts")


if __name__ == "__main__":
    main()
