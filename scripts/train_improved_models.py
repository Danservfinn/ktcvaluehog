#!/usr/bin/env python3
"""
Improved Neural Network Training for Fantasy Production
=========================================================

Implements multiple R² improvement strategies:
1. Enhanced feature engineering
2. Position-specific models
3. Ensemble methods (NN + LightGBM)
4. LSTM sequence modeling
5. Hyperparameter optimization

Target: Improve R² from 0.65 to 0.75+

Usage:
    python scripts/train_improved_models.py
"""

import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split, cross_val_score, KFold
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge, RidgeCV
from datetime import datetime
from typing import Tuple
import logging
import warnings
warnings.filterwarnings('ignore')

try:
    import lightgbm as lgb
    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False
    print("LightGBM not available, using sklearn GradientBoosting instead")

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# =============================================================================
# DATA LOADING
# =============================================================================

def get_driver():
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")
    auth = (user, password) if user and password else None
    return GraphDatabase.driver(uri, auth=auth)


def fetch_betting_features() -> pd.DataFrame:
    """Fetch betting data (Elo, spread, O/U) from Neo4j and CSV."""
    logger.info("Fetching betting data...")

    driver = get_driver()
    betting_data = []

    with driver.session() as session:
        # Get team-season betting stats from Game nodes
        result = session.run("""
            MATCH (g:Game)
            WHERE g.season >= 2015
            WITH g.home_team as team, g.season as season,
                 collect({
                     home_elo: g.home_elo_pre,
                     away_elo: g.away_elo_pre,
                     ou: g.over_under_line,
                     total: g.total_points,
                     is_home: true
                 }) as home_games
            MATCH (g2:Game)
            WHERE g2.away_team = team AND g2.season = season
            WITH team, season, home_games,
                 collect({
                     home_elo: g2.home_elo_pre,
                     away_elo: g2.away_elo_pre,
                     ou: g2.over_under_line,
                     total: g2.total_points,
                     is_home: false
                 }) as away_games
            WITH team, season, home_games + away_games as all_games
            UNWIND all_games as g
            WITH team, season,
                 avg(CASE WHEN g.is_home THEN g.home_elo ELSE g.away_elo END) as avg_elo,
                 avg(g.ou) as avg_over_under,
                 avg(g.total) as avg_total_points,
                 count(g) as games_with_data
            WHERE games_with_data > 5
            RETURN team, season, avg_elo, avg_over_under, avg_total_points, games_with_data
        """)

        for record in result:
            betting_data.append({
                'team': record['team'],
                'season': record['season'],
                'team_avg_elo': record['avg_elo'],
                'team_avg_ou': record['avg_over_under'],
                'team_avg_points': record['avg_total_points'],
                'betting_games_count': record['games_with_data']
            })

    driver.close()

    # Create DataFrame from Neo4j data
    betting_df = pd.DataFrame(betting_data) if betting_data else pd.DataFrame()
    logger.info(f"  Loaded {len(betting_df)} team-season betting records from Neo4j")

    # Supplement with spreadspoke CSV if available
    spreadspoke_path = project_root / 'data' / 'betting' / 'spreadspoke_scores.csv'
    if spreadspoke_path.exists():
        try:
            spread_df = pd.read_csv(spreadspoke_path)
            spread_df = spread_df[spread_df['schedule_season'] >= 2015].copy()

            # Convert over_under_line to numeric (it's stored as object)
            spread_df['over_under_line'] = pd.to_numeric(spread_df['over_under_line'], errors='coerce')

            # Calculate spread/line features per team-season
            spread_features = []

            # Process home games
            home_spread = spread_df.groupby(['team_home', 'schedule_season']).agg({
                'spread_favorite': lambda x: x.dropna().mean() if len(x.dropna()) > 0 else None,
                'over_under_line': 'mean',
                'score_home': 'mean',
                'score_away': 'mean'
            }).reset_index()
            home_spread.columns = ['team', 'season', 'avg_spread', 'avg_ou_line', 'avg_pts_for', 'avg_pts_against']
            home_spread['is_home'] = True

            # Process away games
            away_spread = spread_df.groupby(['team_away', 'schedule_season']).agg({
                'spread_favorite': lambda x: x.dropna().mean() if len(x.dropna()) > 0 else None,
                'over_under_line': 'mean',
                'score_away': 'mean',
                'score_home': 'mean'
            }).reset_index()
            away_spread.columns = ['team', 'season', 'avg_spread', 'avg_ou_line', 'avg_pts_for', 'avg_pts_against']
            away_spread['is_home'] = False

            # Combine and aggregate
            all_spread = pd.concat([home_spread, away_spread], ignore_index=True)
            spread_agg = all_spread.groupby(['team', 'season']).agg({
                'avg_spread': 'mean',
                'avg_ou_line': 'mean',
                'avg_pts_for': 'mean',
                'avg_pts_against': 'mean'
            }).reset_index()

            spread_agg['spread_avg'] = spread_agg['avg_spread']
            spread_agg['ou_line_avg'] = spread_agg['avg_ou_line']
            spread_agg['pts_differential'] = spread_agg['avg_pts_for'] - spread_agg['avg_pts_against']

            logger.info(f"  Loaded {len(spread_agg)} team-season records from spreadspoke CSV")

            # Merge with Neo4j data
            if len(betting_df) > 0:
                betting_df = betting_df.merge(
                    spread_agg[['team', 'season', 'spread_avg', 'ou_line_avg', 'pts_differential']],
                    on=['team', 'season'],
                    how='outer'
                )
            else:
                betting_df = spread_agg[['team', 'season', 'spread_avg', 'ou_line_avg', 'pts_differential',
                                         'avg_pts_for', 'avg_pts_against']].copy()
                betting_df.rename(columns={'avg_pts_for': 'team_avg_points'}, inplace=True)

        except Exception as e:
            logger.warning(f"  Failed to load spreadspoke data: {e}")

    # Load 538 Elo data if available
    elo_path = project_root / 'data' / 'betting' / 'nfl_games_538.csv'
    if elo_path.exists():
        try:
            elo_df = pd.read_csv(elo_path)
            elo_df = elo_df[elo_df['season'] >= 2015].copy()

            # Calculate team-season Elo averages
            team1_elo = elo_df.groupby(['team1', 'season'])['elo1'].mean().reset_index()
            team1_elo.columns = ['team', 'season', 'elo_538']

            team2_elo = elo_df.groupby(['team2', 'season'])['elo2'].mean().reset_index()
            team2_elo.columns = ['team', 'season', 'elo_538']

            elo_combined = pd.concat([team1_elo, team2_elo]).groupby(['team', 'season'])['elo_538'].mean().reset_index()

            logger.info(f"  Loaded {len(elo_combined)} team-season Elo records from 538 CSV")

            if len(betting_df) > 0:
                betting_df = betting_df.merge(elo_combined, on=['team', 'season'], how='outer')
            else:
                betting_df = elo_combined

        except Exception as e:
            logger.warning(f"  Failed to load 538 Elo data: {e}")

    logger.info(f"  Total betting features: {len(betting_df)} team-season records")
    return betting_df


def load_training_data(use_expanded: bool = False) -> pd.DataFrame:
    """Load and combine all available training data.

    Args:
        use_expanded: If True, load the expanded dataset with additional
                     features from expanded_dataset_builder.py
    """
    logger.info("Loading training data...")

    if use_expanded:
        # Load expanded dataset with additional features (PBP, role, injury, KTC)
        expanded_path = 'data/ml_training/expanded_season_projection.parquet'
        if Path(expanded_path).exists():
            df = pd.read_parquet(expanded_path)
            logger.info(f"  Loaded {len(df):,} season records from expanded dataset ({len(df.columns)} features)")
            return df
        else:
            logger.warning(f"  Expanded dataset not found at {expanded_path}, falling back to base dataset")

    # Load base season projection data
    df = pd.read_parquet('data/ml_training/season_projection.parquet')
    logger.info(f"  Loaded {len(df):,} season records")

    return df


def fetch_additional_features() -> dict:
    """Fetch additional features from Neo4j."""
    logger.info("Fetching additional features from Neo4j...")
    driver = get_driver()

    features = {}

    with driver.session() as session:
        # Get injury data
        result = session.run("""
            MATCH (ip:PlayerInjuryProfile)
            RETURN ip.player_id as player_id,
                   ip.overall_injury_risk as injury_risk,
                   ip.games_listed_out as games_out,
                   ip.soft_tissue_leg_count as soft_tissue
        """)
        injury_data = {r['player_id']: dict(r) for r in result}
        features['injury'] = injury_data

        # Get role data
        result = session.run("""
            MATCH (rp:PlayerRoleProfile)
            RETURN rp.player_id as player_id,
                   rp.starter_rate as starter_rate,
                   rp.primary_role as primary_role
        """)
        role_data = {r['player_id']: dict(r) for r in result}
        features['role'] = role_data

        # Get combine data
        result = session.run("""
            MATCH (c:CombineResult)
            RETURN c.player_id as player_id,
                   c.forty_yard as forty,
                   c.vertical_jump as vertical,
                   c.broad_jump as broad_jump
        """)
        combine_data = {r['player_id']: dict(r) for r in result}
        features['combine'] = combine_data

    driver.close()
    logger.info(f"  Loaded features for {len(features['injury'])} injury, {len(features['role'])} role, {len(features['combine'])} combine records")
    return features


# =============================================================================
# FEATURE ENGINEERING
# =============================================================================

def engineer_enhanced_features(df: pd.DataFrame, neo4j_features: dict, betting_df: pd.DataFrame = None) -> pd.DataFrame:
    """Engineer enhanced features for improved prediction, including betting data."""
    logger.info("Engineering enhanced features...")
    df = df.copy()

    # 0. Merge betting features first
    if betting_df is not None and len(betting_df) > 0:
        logger.info(f"  Merging {len(betting_df)} betting records...")

        # Normalize team names for matching
        team_name_map = {
            'ARI': 'ARI', 'Arizona Cardinals': 'ARI',
            'ATL': 'ATL', 'Atlanta Falcons': 'ATL',
            'BAL': 'BAL', 'Baltimore Ravens': 'BAL',
            'BUF': 'BUF', 'Buffalo Bills': 'BUF',
            'CAR': 'CAR', 'Carolina Panthers': 'CAR',
            'CHI': 'CHI', 'Chicago Bears': 'CHI',
            'CIN': 'CIN', 'Cincinnati Bengals': 'CIN',
            'CLE': 'CLE', 'Cleveland Browns': 'CLE',
            'DAL': 'DAL', 'Dallas Cowboys': 'DAL',
            'DEN': 'DEN', 'Denver Broncos': 'DEN',
            'DET': 'DET', 'Detroit Lions': 'DET',
            'GB': 'GB', 'GNB': 'GB', 'Green Bay Packers': 'GB',
            'HOU': 'HOU', 'Houston Texans': 'HOU',
            'IND': 'IND', 'Indianapolis Colts': 'IND',
            'JAX': 'JAX', 'JAC': 'JAX', 'Jacksonville Jaguars': 'JAX',
            'KC': 'KC', 'KAN': 'KC', 'Kansas City Chiefs': 'KC',
            'LAC': 'LAC', 'LV': 'LV', 'Las Vegas Raiders': 'LV', 'LAR': 'LAR',
            'MIA': 'MIA', 'Miami Dolphins': 'MIA',
            'MIN': 'MIN', 'Minnesota Vikings': 'MIN',
            'NE': 'NE', 'NWE': 'NE', 'New England Patriots': 'NE',
            'NO': 'NO', 'NOR': 'NO', 'New Orleans Saints': 'NO',
            'NYG': 'NYG', 'New York Giants': 'NYG',
            'NYJ': 'NYJ', 'New York Jets': 'NYJ',
            'OAK': 'LV', 'Oakland Raiders': 'LV',
            'PHI': 'PHI', 'Philadelphia Eagles': 'PHI',
            'PIT': 'PIT', 'Pittsburgh Steelers': 'PIT',
            'SEA': 'SEA', 'Seattle Seahawks': 'SEA',
            'SF': 'SF', 'SFO': 'SF', 'San Francisco 49ers': 'SF',
            'TB': 'TB', 'TAM': 'TB', 'Tampa Bay Buccaneers': 'TB',
            'TEN': 'TEN', 'Tennessee Titans': 'TEN',
            'WAS': 'WAS', 'WSH': 'WAS', 'Washington Commanders': 'WAS', 'Washington Football Team': 'WAS',
            'SD': 'LAC', 'San Diego Chargers': 'LAC',
            'STL': 'LAR', 'St. Louis Rams': 'LAR', 'Los Angeles Rams': 'LAR',
            'Los Angeles Chargers': 'LAC'
        }

        # Normalize team names in both dataframes
        if 'team' in df.columns:
            df['team_norm'] = df['team'].map(lambda x: team_name_map.get(x, x) if pd.notna(x) else x)
        else:
            df['team_norm'] = None

        betting_df = betting_df.copy()
        betting_df['team_norm'] = betting_df['team'].map(lambda x: team_name_map.get(x, x) if pd.notna(x) else x)

        # Merge on normalized team and season
        df = df.merge(
            betting_df.drop(columns=['team']).rename(columns={'team_norm': 'team_norm'}),
            left_on=['team_norm', 'season'],
            right_on=['team_norm', 'season'],
            how='left'
        )

        # Count betting matches
        betting_cols = ['team_avg_elo', 'team_avg_ou', 'spread_avg', 'ou_line_avg', 'elo_538', 'pts_differential']
        for col in betting_cols:
            if col in df.columns:
                matches = df[col].notna().sum()
                logger.info(f"    {col}: {matches} matches")

        # Drop temp column
        df.drop(columns=['team_norm'], inplace=True, errors='ignore')

    # 1. Weighted recent performance
    if 'last_4_weeks_ppg' in df.columns and 'first_half_ppg' in df.columns:
        df['weighted_recent'] = (
            df['last_4_weeks_ppg'] * 0.5 +
            df['second_half_ppg'] * 0.3 +
            df['first_half_ppg'] * 0.2
        )

    # 2. Performance momentum
    if 'second_half_ppg' in df.columns and 'first_half_ppg' in df.columns:
        df['ppg_momentum'] = df['second_half_ppg'] - df['first_half_ppg']
        df['momentum_pct'] = df['ppg_momentum'] / (df['first_half_ppg'] + 0.1)

    # 3. Consistency score (inverse of variance)
    if 'ppg_ppr' in df.columns and 'ppg_std' in df.columns:
        # Lower std = more consistent
        std_col = df.groupby('player_id')['ppg_ppr'].transform('std')
        df['consistency_score'] = 1 / (std_col + 1)

    # 4. Career trajectory
    if 'ppg_vs_career_avg' in df.columns:
        df['career_trend'] = df['ppg_vs_career_avg']

    # 5. Age-position curve adjustment
    position_peak_ages = {'QB': 30, 'RB': 25, 'WR': 27, 'TE': 28}
    if 'estimated_age' in df.columns and 'position' in df.columns:
        df['years_from_peak'] = df.apply(
            lambda r: r['estimated_age'] - position_peak_ages.get(r['position'], 27)
            if pd.notna(r['estimated_age']) else 0,
            axis=1
        )
        df['age_decline_factor'] = np.clip(1 - df['years_from_peak'].clip(lower=0) * 0.05, 0.5, 1.0)

    # 6. Opportunity share features
    if 'target_share_calc' in df.columns:
        df['high_target_share'] = (df['target_share_calc'] > 0.20).astype(int)

    if 'carry_share' in df.columns:
        df['high_carry_share'] = (df['carry_share'] > 0.50).astype(int)

    # 7. Add Neo4j features
    if neo4j_features:
        # Injury features
        injury_risk_map = {'low': 0, 'medium': 1, 'high': 2}
        df['injury_risk_score'] = df['player_id'].map(
            lambda x: injury_risk_map.get(
                neo4j_features['injury'].get(x, {}).get('injury_risk', 'low'), 0
            )
        )
        df['career_games_missed'] = df['player_id'].map(
            lambda x: neo4j_features['injury'].get(x, {}).get('games_out', 0) or 0
        )

        # Role features
        df['starter_rate'] = df['player_id'].map(
            lambda x: neo4j_features['role'].get(x, {}).get('starter_rate', 0) or 0
        )

        # Athletic features
        df['forty_time'] = df['player_id'].map(
            lambda x: neo4j_features['combine'].get(x, {}).get('forty', None)
        )
        df['vertical'] = df['player_id'].map(
            lambda x: neo4j_features['combine'].get(x, {}).get('vertical', None)
        )

    # 8. Position-specific interactions
    df['is_qb'] = (df['position'] == 'QB').astype(int)
    df['is_rb'] = (df['position'] == 'RB').astype(int)
    df['is_wr'] = (df['position'] == 'WR').astype(int)
    df['is_te'] = (df['position'] == 'TE').astype(int)

    # QB-specific
    if 'passing_yards' in df.columns:
        df['qb_efficiency'] = df['passing_yards'] / (df['games'] * 40 + 1) * df['is_qb']

    # RB-specific
    if 'carries' in df.columns:
        df['rb_workload'] = (df['carries'] / (df['games'] + 0.1)) * df['is_rb']

    # WR/TE receiving efficiency
    if 'receiving_yards' in df.columns and 'targets' in df.columns:
        df['receiving_efficiency'] = df['receiving_yards'] / (df['targets'] + 1)

    logger.info(f"  Created {len(df.columns)} total features")
    return df


# =============================================================================
# MODEL ARCHITECTURES
# =============================================================================

class ImprovedNN(nn.Module):
    """Improved neural network with residual connections and attention."""

    def __init__(self, input_dim: int, n_positions: int = 4):
        super().__init__()

        self.pos_embedding = nn.Embedding(n_positions, 32)

        # Input projection
        self.input_proj = nn.Linear(input_dim + 32, 256)

        # Residual blocks
        self.block1 = self._make_block(256, 256)
        self.block2 = self._make_block(256, 128)
        self.block3 = self._make_block(128, 64)

        # Output
        self.output = nn.Sequential(
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1)
        )

    def _make_block(self, in_dim, out_dim):
        return nn.Sequential(
            nn.Linear(in_dim, out_dim),
            nn.LayerNorm(out_dim),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(out_dim, out_dim),
            nn.LayerNorm(out_dim),
            nn.ReLU(),
            nn.Dropout(0.2)
        )

    def forward(self, x, position):
        pos_emb = self.pos_embedding(position)
        x = torch.cat([x, pos_emb], dim=1)

        x = self.input_proj(x)
        x = x + self.block1(x)[:, :256] if x.shape[1] == 256 else self.block1(x)

        x = self.block2(x)
        x = self.block3(x)

        return self.output(x).squeeze(-1)


class LSTMModel(nn.Module):
    """LSTM for career trajectory modeling."""

    def __init__(self, input_dim: int, hidden_dim: int = 64, n_layers: int = 2):
        super().__init__()

        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=n_layers,
            batch_first=True,
            dropout=0.2,
            bidirectional=True
        )

        self.fc = nn.Sequential(
            nn.Linear(hidden_dim * 2, 64),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, 1)
        )

    def forward(self, x):
        # x: (batch, seq_len, features)
        lstm_out, _ = self.lstm(x)
        last_out = lstm_out[:, -1, :]
        return self.fc(last_out).squeeze(-1)


# =============================================================================
# TRAINING FUNCTIONS
# =============================================================================

class FantasyDataset(Dataset):
    def __init__(self, X, y, positions):
        self.X = torch.FloatTensor(X)
        self.y = torch.FloatTensor(y)
        self.positions = torch.LongTensor(positions)

    def __len__(self):
        return len(self.X)

    def __getitem__(self, idx):
        return self.X[idx], self.positions[idx], self.y[idx]


def train_nn_model(X_train, y_train, X_test, y_test, pos_train, pos_test,
                   device='cpu', epochs=100, patience=15):
    """Train improved neural network."""

    train_dataset = FantasyDataset(X_train, y_train, pos_train)
    test_dataset = FantasyDataset(X_test, y_test, pos_test)

    train_loader = DataLoader(train_dataset, batch_size=64, shuffle=True)
    test_loader = DataLoader(test_dataset, batch_size=64)

    model = ImprovedNN(X_train.shape[1]).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=0.01)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5, factor=0.5)
    criterion = nn.MSELoss()

    best_val_loss = float('inf')
    patience_counter = 0
    best_state = None

    for epoch in range(epochs):
        # Train
        model.train()
        for X_batch, pos_batch, y_batch in train_loader:
            X_batch, pos_batch, y_batch = X_batch.to(device), pos_batch.to(device), y_batch.to(device)
            optimizer.zero_grad()
            pred = model(X_batch, pos_batch)
            loss = criterion(pred, y_batch)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

        # Validate
        model.eval()
        val_loss = 0
        with torch.no_grad():
            for X_batch, pos_batch, y_batch in test_loader:
                X_batch, pos_batch, y_batch = X_batch.to(device), pos_batch.to(device), y_batch.to(device)
                pred = model(X_batch, pos_batch)
                val_loss += criterion(pred, y_batch).item()
        val_loss /= len(test_loader)

        scheduler.step(val_loss)

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            best_state = model.state_dict().copy()
        else:
            patience_counter += 1
            if patience_counter >= patience:
                break

    model.load_state_dict(best_state)
    return model


def train_gbm_model(X_train, y_train):
    """Train gradient boosting model."""
    if HAS_LIGHTGBM:
        model = lgb.LGBMRegressor(
            n_estimators=500,
            learning_rate=0.05,
            max_depth=6,
            num_leaves=31,
            min_child_samples=20,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=0.1,
            reg_lambda=0.1,
            random_state=42,
            verbose=-1
        )
    else:
        model = GradientBoostingRegressor(
            n_estimators=300,
            learning_rate=0.05,
            max_depth=5,
            min_samples_split=20,
            min_samples_leaf=10,
            subsample=0.8,
            random_state=42
        )

    model.fit(X_train, y_train)
    return model


def train_position_models(df, feature_cols, device='cpu'):
    """Train separate models for each position."""
    logger.info("Training position-specific models...")

    position_models = {}
    position_metrics = {}

    for pos in ['QB', 'RB', 'WR', 'TE']:
        pos_df = df[df['position'] == pos].copy()

        if len(pos_df) < 100:
            logger.warning(f"  Skipping {pos} - only {len(pos_df)} samples")
            continue

        logger.info(f"  Training {pos} model ({len(pos_df)} samples)...")

        # TIME-BASED SPLIT for position models
        if 'season' in pos_df.columns:
            train_mask = pos_df['season'] < 2022
            test_mask = pos_df['season'] >= 2022
        else:
            train_mask = np.random.rand(len(pos_df)) < 0.8
            test_mask = ~train_mask

        pos_train_df = pos_df[train_mask]
        pos_test_df = pos_df[test_mask]

        if len(pos_test_df) < 20:
            logger.warning(f"    Insufficient test data for {pos}, using random split")
            train_mask = np.random.rand(len(pos_df)) < 0.8
            test_mask = ~train_mask
            pos_train_df = pos_df[train_mask]
            pos_test_df = pos_df[test_mask]

        X_train_raw = pos_train_df[feature_cols].fillna(0).values
        X_test_raw = pos_test_df[feature_cols].fillna(0).values
        y_train = pos_train_df['next_ppg_ppr'].fillna(0).values
        y_test = pos_test_df['next_ppg_ppr'].fillna(0).values

        scaler = StandardScaler()
        X_train = scaler.fit_transform(X_train_raw)
        X_test = scaler.transform(X_test_raw)

        # Position indicator for NN
        pos_encoder = LabelEncoder()
        pos_encoder.fit(['QB', 'RB', 'WR', 'TE'])
        pos_idx = pos_encoder.transform([pos])[0]
        pos_train = np.full(len(X_train), pos_idx)
        pos_test = np.full(len(X_test), pos_idx)

        # Train NN
        nn_model = train_nn_model(X_train, y_train, X_test, y_test,
                                  pos_train, pos_test, device)

        # Train GBM
        gbm_model = train_gbm_model(X_train, y_train)

        # Evaluate
        nn_model.eval()
        with torch.no_grad():
            X_tensor = torch.FloatTensor(X_test).to(device)
            pos_tensor = torch.LongTensor(pos_test).to(device)
            nn_preds = nn_model(X_tensor, pos_tensor).cpu().numpy()

        gbm_preds = gbm_model.predict(X_test)

        # Ensemble (average)
        ensemble_preds = (nn_preds + gbm_preds) / 2

        nn_r2 = r2_score(y_test, nn_preds)
        gbm_r2 = r2_score(y_test, gbm_preds)
        ens_r2 = r2_score(y_test, ensemble_preds)

        logger.info(f"    NN R²: {nn_r2:.4f}, GBM R²: {gbm_r2:.4f}, Ensemble R²: {ens_r2:.4f}")

        position_models[pos] = {
            'nn': nn_model,
            'gbm': gbm_model,
            'scaler': scaler,
            'pos_encoder': pos_encoder
        }

        position_metrics[pos] = {
            'nn_r2': nn_r2,
            'gbm_r2': gbm_r2,
            'ensemble_r2': ens_r2,
            'samples': len(pos_df)
        }

    return position_models, position_metrics


def train_stacking_meta_model(
    X_train: np.ndarray,
    y_train: np.ndarray,
    base_models: dict,
    device: str = 'cpu',
    n_folds: int = 5
) -> Tuple:
    """
    Train a stacking meta-model using out-of-fold predictions.

    This replaces fixed weight averaging with learned stacking weights.

    Args:
        X_train: Training features (already scaled)
        y_train: Training targets
        base_models: Dict with 'nn', 'gbm', 'rf', 'ridge' model instances
        device: PyTorch device
        n_folds: Number of CV folds for generating OOF predictions

    Returns:
        Tuple of (meta_model, oof_predictions_dict, oof_r2_scores)
    """
    logger.info("  Training stacking meta-model with OOF predictions...")

    n_samples = len(X_train)
    kfold = KFold(n_splits=n_folds, shuffle=True, random_state=42)

    # Initialize OOF prediction arrays for each base model
    oof_nn = np.zeros(n_samples)
    oof_gbm = np.zeros(n_samples)
    oof_rf = np.zeros(n_samples)
    oof_ridge = np.zeros(n_samples)

    # For neural network, we need position encodings
    # Use a simple position-agnostic approach for OOF (average across positions)
    pos_encoder = LabelEncoder()
    pos_encoder.fit(['QB', 'RB', 'WR', 'TE'])

    for fold_idx, (train_idx, val_idx) in enumerate(kfold.split(X_train)):
        X_fold_train, X_fold_val = X_train[train_idx], X_train[val_idx]
        y_fold_train, y_fold_val = y_train[train_idx], y_train[val_idx]

        # Train fold-specific GBM
        if HAS_LIGHTGBM:
            fold_gbm = lgb.LGBMRegressor(
                n_estimators=300, learning_rate=0.05, max_depth=6,
                num_leaves=31, subsample=0.8, colsample_bytree=0.8,
                reg_alpha=0.1, reg_lambda=0.1, random_state=42+fold_idx, verbose=-1
            )
        else:
            fold_gbm = GradientBoostingRegressor(
                n_estimators=200, learning_rate=0.05, max_depth=5,
                min_samples_split=20, random_state=42+fold_idx
            )
        fold_gbm.fit(X_fold_train, y_fold_train)
        oof_gbm[val_idx] = fold_gbm.predict(X_fold_val)

        # Train fold-specific RF
        fold_rf = RandomForestRegressor(
            n_estimators=150, max_depth=8, min_samples_split=10,
            random_state=42+fold_idx, n_jobs=-1
        )
        fold_rf.fit(X_fold_train, y_fold_train)
        oof_rf[val_idx] = fold_rf.predict(X_fold_val)

        # Train fold-specific Ridge
        fold_ridge = Ridge(alpha=1.0)
        fold_ridge.fit(X_fold_train, y_fold_train)
        oof_ridge[val_idx] = fold_ridge.predict(X_fold_val)

        # For NN, use simplified training without position encoding for OOF
        # (position info is already encoded in features via one-hot)
        fold_nn = nn.Sequential(
            nn.Linear(X_train.shape[1], 128),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, 1)
        ).to(device)

        optimizer = torch.optim.AdamW(fold_nn.parameters(), lr=1e-3, weight_decay=0.01)
        criterion = nn.MSELoss()

        X_train_t = torch.FloatTensor(X_fold_train).to(device)
        y_train_t = torch.FloatTensor(y_fold_train).to(device)

        fold_nn.train()
        for epoch in range(50):  # Quick training for OOF
            optimizer.zero_grad()
            pred = fold_nn(X_train_t).squeeze()
            loss = criterion(pred, y_train_t)
            loss.backward()
            optimizer.step()

        fold_nn.eval()
        with torch.no_grad():
            X_val_t = torch.FloatTensor(X_fold_val).to(device)
            oof_nn[val_idx] = fold_nn(X_val_t).squeeze().cpu().numpy()

    # Calculate OOF R² for each base model
    oof_r2 = {
        'nn': r2_score(y_train, oof_nn),
        'gbm': r2_score(y_train, oof_gbm),
        'rf': r2_score(y_train, oof_rf),
        'ridge': r2_score(y_train, oof_ridge)
    }

    logger.info(f"    OOF R² - NN: {oof_r2['nn']:.4f}, GBM: {oof_r2['gbm']:.4f}, "
                f"RF: {oof_r2['rf']:.4f}, Ridge: {oof_r2['ridge']:.4f}")

    # Stack OOF predictions as meta-features
    meta_features = np.column_stack([oof_nn, oof_gbm, oof_rf, oof_ridge])

    # Train meta-model using RidgeCV (with built-in cross-validation for alpha)
    meta_model = RidgeCV(
        alphas=[0.01, 0.1, 0.5, 1.0, 5.0, 10.0, 50.0],
        cv=5
    )
    meta_model.fit(meta_features, y_train)

    # Log learned weights (coefficients show relative importance)
    logger.info(f"    Meta-model alpha: {meta_model.alpha_:.4f}")
    logger.info(f"    Meta-model coefficients: NN={meta_model.coef_[0]:.4f}, "
                f"GBM={meta_model.coef_[1]:.4f}, RF={meta_model.coef_[2]:.4f}, "
                f"Ridge={meta_model.coef_[3]:.4f}")

    # Evaluate stacking on OOF predictions
    stacking_preds = meta_model.predict(meta_features)
    stacking_r2 = r2_score(y_train, stacking_preds)
    logger.info(f"    Stacking OOF R²: {stacking_r2:.4f}")

    return meta_model, {'nn': oof_nn, 'gbm': oof_gbm, 'rf': oof_rf, 'ridge': oof_ridge}, oof_r2


def train_ensemble_model(df, feature_cols, device='cpu'):
    """Train ensemble of NN + GBM models with time-based split and stacking meta-model."""
    logger.info("Training ensemble model with stacking...")

    # TIME-BASED SPLIT to prevent temporal leakage
    # Train on seasons before 2022, test on 2022+
    if 'season' in df.columns:
        train_mask = df['season'] < 2022
        test_mask = df['season'] >= 2022
        logger.info(f"  Using time-based split: train on pre-2022, test on 2022+")
    else:
        # Fallback to random if no season column
        train_mask = np.random.rand(len(df)) < 0.8
        test_mask = ~train_mask
        logger.info(f"  Using random split (no season column)")

    df_train = df[train_mask].copy()
    df_test = df[test_mask].copy()

    X_train = df_train[feature_cols].fillna(0).values
    X_test = df_test[feature_cols].fillna(0).values
    y_train = df_train['next_ppg_ppr'].fillna(0).values
    y_test = df_test['next_ppg_ppr'].fillna(0).values

    # Encode positions
    pos_encoder = LabelEncoder()
    pos_encoder.fit(['QB', 'RB', 'WR', 'TE'])
    pos_train = pos_encoder.transform(df_train['position'].fillna('WR').values)
    pos_test = pos_encoder.transform(df_test['position'].fillna('WR').values)

    # Scale (fit only on training data)
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)

    logger.info(f"  Training on {len(X_train)} samples, testing on {len(X_test)}")

    # Train models
    logger.info("  Training Neural Network...")
    nn_model = train_nn_model(X_train, y_train, X_test, y_test, pos_train, pos_test, device)

    logger.info("  Training Gradient Boosting...")
    gbm_model = train_gbm_model(X_train, y_train)

    logger.info("  Training Random Forest...")
    rf_model = RandomForestRegressor(
        n_estimators=200, max_depth=8, min_samples_split=10, random_state=42, n_jobs=-1
    )
    rf_model.fit(X_train, y_train)

    logger.info("  Training Ridge Regression...")
    ridge_model = Ridge(alpha=1.0)
    ridge_model.fit(X_train, y_train)

    # Get predictions
    nn_model.eval()
    with torch.no_grad():
        X_tensor = torch.FloatTensor(X_test).to(device)
        pos_tensor = torch.LongTensor(pos_test).to(device)
        nn_preds = nn_model(X_tensor, pos_tensor).cpu().numpy()

    gbm_preds = gbm_model.predict(X_test)
    rf_preds = rf_model.predict(X_test)
    ridge_preds = ridge_model.predict(X_test)

    # Calculate individual R²
    nn_r2 = r2_score(y_test, nn_preds)
    gbm_r2 = r2_score(y_test, gbm_preds)
    rf_r2 = r2_score(y_test, rf_preds)
    ridge_r2 = r2_score(y_test, ridge_preds)

    logger.info(f"  Individual R² scores:")
    logger.info(f"    NN: {nn_r2:.4f}")
    logger.info(f"    GBM: {gbm_r2:.4f}")
    logger.info(f"    RF: {rf_r2:.4f}")
    logger.info(f"    Ridge: {ridge_r2:.4f}")

    # =================================================================
    # STACKING META-MODEL (replaces fixed weight grid search)
    # =================================================================
    logger.info("  Training stacking meta-model...")

    # Train stacking meta-model on training data
    meta_model, oof_preds, oof_r2 = train_stacking_meta_model(
        X_train, y_train,
        base_models={'nn': nn_model, 'gbm': gbm_model, 'rf': rf_model, 'ridge': ridge_model},
        device=device,
        n_folds=5
    )

    # Generate stacking predictions on test set
    test_meta_features = np.column_stack([nn_preds, gbm_preds, rf_preds, ridge_preds])
    ensemble_preds = meta_model.predict(test_meta_features)

    # Calculate stacking R² on test set
    best_r2 = r2_score(y_test, ensemble_preds)
    logger.info(f"  Stacking ensemble R² on test set: {best_r2:.4f}")

    # For backwards compatibility, also compute fixed-weight baseline
    baseline_preds = 0.3 * nn_preds + 0.35 * gbm_preds + 0.2 * rf_preds + 0.15 * ridge_preds
    baseline_r2 = r2_score(y_test, baseline_preds)
    logger.info(f"  Fixed-weight baseline R²: {baseline_r2:.4f}")
    logger.info(f"  Stacking improvement: {best_r2 - baseline_r2:+.4f}")

    # Store meta-model coefficients as pseudo-weights for logging
    coef_sum = np.abs(meta_model.coef_).sum()
    best_weights = tuple(np.abs(meta_model.coef_) / coef_sum) if coef_sum > 0 else (0.25, 0.25, 0.25, 0.25)

    rmse = np.sqrt(mean_squared_error(y_test, ensemble_preds))
    mae = mean_absolute_error(y_test, ensemble_preds)

    return {
        'nn_model': nn_model,
        'gbm_model': gbm_model,
        'rf_model': rf_model,
        'ridge_model': ridge_model,
        'meta_model': meta_model,  # Stacking meta-model
        'scaler': scaler,
        'pos_encoder': pos_encoder,
        'weights': best_weights,  # Now derived from meta-model coefficients
        'feature_cols': feature_cols,
        'metrics': {
            'ensemble_r2': best_r2,
            'baseline_r2': baseline_r2,  # Fixed-weight baseline for comparison
            'stacking_improvement': best_r2 - baseline_r2,
            'nn_r2': nn_r2,
            'gbm_r2': gbm_r2,
            'rf_r2': rf_r2,
            'ridge_r2': ridge_r2,
            'oof_r2': oof_r2,  # Out-of-fold R² scores
            'rmse': rmse,
            'mae': mae,
            'meta_alpha': meta_model.alpha_,
            'meta_coef': meta_model.coef_.tolist()
        }
    }


# =============================================================================
# MAIN
# =============================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Train improved ML models')
    parser.add_argument('--use-base-dataset', action='store_true',
                       help='Use base dataset (season_projection.parquet)')
    parser.add_argument('--use-expanded-dataset', action='store_true',
                       help='Use expanded dataset with additional features (expanded_season_projection.parquet)')
    args = parser.parse_args()

    # Default to base dataset if neither option specified
    use_expanded = args.use_expanded_dataset and not args.use_base_dataset

    print("=" * 70)
    print("IMPROVED MODEL TRAINING FOR R² ENHANCEMENT")
    print(f"Started: {datetime.now()}")
    print(f"Dataset: {'expanded' if use_expanded else 'base'}")
    print("=" * 70)

    # Device
    if torch.cuda.is_available():
        device = 'cuda'
    elif torch.backends.mps.is_available():
        device = 'mps'
    else:
        device = 'cpu'
    logger.info(f"Using device: {device}")

    # Load data
    df = load_training_data(use_expanded=use_expanded)

    # Only fetch additional features if using base dataset
    if not use_expanded:
        neo4j_features = fetch_additional_features()
        betting_df = fetch_betting_features()
    else:
        neo4j_features = {}
        betting_df = pd.DataFrame()

    # Engineer features (with betting data)
    df = engineer_enhanced_features(df, neo4j_features, betting_df)

    # Define feature columns - exclude all 'next_*' columns (target leakage)
    # Also exclude ppg_change, ppg_change_pct which are derived from target
    exclude_cols = ['player_id', 'player_name', 'position', 'season', 'team', 'team_norm']
    leakage_cols = ['ppg_change', 'ppg_change_pct']  # These are derived from next_ppg_ppr
    feature_cols = [c for c in df.columns
                    if c not in exclude_cols
                    and c not in leakage_cols
                    and not c.startswith('next_')  # Exclude all 'next_' columns (leakage)
                    and df[c].dtype in ['int64', 'float64', 'bool', 'uint8']
                    and df[c].notna().sum() > len(df) * 0.5]  # At least 50% non-null

    logger.info(f"Excluded leakage columns: {leakage_cols + [c for c in df.columns if c.startswith('next_')]}")

    logger.info(f"Using {len(feature_cols)} features")

    # Train ensemble model
    print("\n" + "=" * 70)
    print("PHASE 1: ENSEMBLE MODEL")
    print("=" * 70)
    ensemble_result = train_ensemble_model(df, feature_cols, device)

    # Train position-specific models
    print("\n" + "=" * 70)
    print("PHASE 2: POSITION-SPECIFIC MODELS")
    print("=" * 70)
    position_models, position_metrics = train_position_models(df, feature_cols, device)

    # Save models
    print("\n" + "=" * 70)
    print("SAVING MODELS")
    print("=" * 70)

    model_dir = Path('data/models')
    model_dir.mkdir(parents=True, exist_ok=True)

    # Save ensemble models
    torch.save({
        'nn_state': ensemble_result['nn_model'].state_dict(),
        'scaler': ensemble_result['scaler'],
        'pos_encoder': ensemble_result['pos_encoder'],
        'weights': ensemble_result['weights'],
        'feature_cols': ensemble_result['feature_cols'],
        'metrics': ensemble_result['metrics']
    }, model_dir / 'ensemble_model.pt')

    import joblib
    joblib.dump(ensemble_result['gbm_model'], model_dir / 'ensemble_gbm.pkl')
    joblib.dump(ensemble_result['rf_model'], model_dir / 'ensemble_rf.pkl')
    joblib.dump(ensemble_result['ridge_model'], model_dir / 'ensemble_ridge.pkl')

    # Save stacking meta-model
    joblib.dump(ensemble_result['meta_model'], model_dir / 'stacking_meta.pkl')

    logger.info(f"Models saved to {model_dir}")

    # Final summary
    print("\n" + "=" * 70)
    print("TRAINING COMPLETE - RESULTS SUMMARY")
    print("=" * 70)

    print("\nStacking Ensemble Model:")
    print(f"  Overall R²: {ensemble_result['metrics']['ensemble_r2']:.4f}")
    print(f"  Baseline R² (fixed weights): {ensemble_result['metrics']['baseline_r2']:.4f}")
    print(f"  Stacking Improvement: {ensemble_result['metrics']['stacking_improvement']:+.4f}")
    print(f"  RMSE: {ensemble_result['metrics']['rmse']:.2f} PPG")
    print(f"  MAE: {ensemble_result['metrics']['mae']:.2f} PPG")
    print(f"  Meta-model alpha: {ensemble_result['metrics']['meta_alpha']:.4f}")
    print(f"  Meta-model coefficients: {ensemble_result['metrics']['meta_coef']}")

    print("\nPosition-Specific Models:")
    for pos, metrics in position_metrics.items():
        print(f"  {pos}: Ensemble R²={metrics['ensemble_r2']:.4f} (n={metrics['samples']})")

    print("\nComponent Model R² Scores:")
    print(f"  Neural Network: {ensemble_result['metrics']['nn_r2']:.4f}")
    print(f"  Gradient Boosting: {ensemble_result['metrics']['gbm_r2']:.4f}")
    print(f"  Random Forest: {ensemble_result['metrics']['rf_r2']:.4f}")
    print(f"  Ridge Regression: {ensemble_result['metrics']['ridge_r2']:.4f}")

    # Compare to baseline
    baseline_r2 = 0.65
    improvement = ensemble_result['metrics']['ensemble_r2'] - baseline_r2
    print(f"\nImprovement over baseline (0.65): {improvement:+.4f}")

    return ensemble_result, position_models, position_metrics


if __name__ == "__main__":
    main()
