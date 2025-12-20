#!/usr/bin/env python3
"""
Neural Network Models for Fantasy Football Prediction
======================================================

This module implements various neural network architectures for predicting:
1. Next season fantasy PPG (regression)
2. KTC dynasty trade value (regression)
3. Breakout probability (classification)

Architectures:
- SimpleFFN: Feedforward network (baseline)
- CareerLSTM: LSTM for career trajectory modeling
- MultiTaskNN: Multi-task learning for PPG + KTC + Breakout
- TransformerModel: Self-attention over career history

Author: Thoth AI Platform
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# DATA PREPARATION
# =============================================================================

class FantasyDataset(Dataset):
    """PyTorch Dataset for fantasy football prediction."""

    def __init__(
        self,
        df: pd.DataFrame,
        feature_cols: List[str],
        target_col: str = 'next_ppg_ppr',
        categorical_cols: List[str] = None,
        scaler: StandardScaler = None,
        label_encoders: Dict = None,
        fit: bool = True
    ):
        self.df = df.copy()
        self.feature_cols = feature_cols
        self.target_col = target_col
        self.categorical_cols = categorical_cols or ['position']

        # Prepare features
        X_numeric = self.df[feature_cols].select_dtypes(include=[np.number]).fillna(0)

        # Scale numeric features
        if fit:
            self.scaler = StandardScaler()
            X_scaled = self.scaler.fit_transform(X_numeric)
        else:
            self.scaler = scaler
            X_scaled = self.scaler.transform(X_numeric)

        # Encode categorical features
        self.label_encoders = label_encoders or {}
        cat_encoded = []
        for col in self.categorical_cols:
            if col in self.df.columns:
                if fit:
                    le = LabelEncoder()
                    encoded = le.fit_transform(self.df[col].fillna('UNKNOWN'))
                    self.label_encoders[col] = le
                else:
                    le = self.label_encoders.get(col)
                    encoded = le.transform(self.df[col].fillna('UNKNOWN'))
                cat_encoded.append(encoded)

        self.X_numeric = torch.FloatTensor(X_scaled)
        self.X_categorical = torch.LongTensor(np.column_stack(cat_encoded)) if cat_encoded else None
        self.y = torch.FloatTensor(self.df[target_col].values)

        self.numeric_dim = X_scaled.shape[1]
        self.n_categories = {col: len(self.label_encoders[col].classes_)
                           for col in self.categorical_cols if col in self.label_encoders}

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        if self.X_categorical is not None:
            return self.X_numeric[idx], self.X_categorical[idx], self.y[idx]
        return self.X_numeric[idx], self.y[idx]


class CareerSequenceDataset(Dataset):
    """Dataset for sequence models - groups player careers."""

    def __init__(
        self,
        df: pd.DataFrame,
        feature_cols: List[str],
        target_col: str = 'next_ppg_ppr',
        max_seq_len: int = 5,
        scaler: StandardScaler = None,
        fit: bool = True
    ):
        self.feature_cols = feature_cols
        self.target_col = target_col
        self.max_seq_len = max_seq_len

        # Scale features
        X_numeric = df[feature_cols].select_dtypes(include=[np.number]).fillna(0)
        if fit:
            self.scaler = StandardScaler()
            df_scaled = pd.DataFrame(
                self.scaler.fit_transform(X_numeric),
                columns=X_numeric.columns,
                index=df.index
            )
        else:
            self.scaler = scaler
            df_scaled = pd.DataFrame(
                self.scaler.transform(X_numeric),
                columns=X_numeric.columns,
                index=df.index
            )

        df_scaled['player_id'] = df['player_id'].values
        df_scaled['season'] = df['season'].values
        df_scaled['position'] = df['position'].values
        df_scaled[target_col] = df[target_col].values

        # Group by player and create sequences
        self.sequences = []
        self.targets = []
        self.positions = []

        position_encoder = LabelEncoder()
        position_encoder.fit(['QB', 'RB', 'WR', 'TE'])

        for player_id, player_df in df_scaled.groupby('player_id'):
            player_df = player_df.sort_values('season')

            for i in range(len(player_df)):
                # Get up to max_seq_len previous seasons
                start_idx = max(0, i - max_seq_len + 1)
                seq = player_df.iloc[start_idx:i+1][feature_cols].values

                # Pad if necessary
                if len(seq) < max_seq_len:
                    padding = np.zeros((max_seq_len - len(seq), len(feature_cols)))
                    seq = np.vstack([padding, seq])

                self.sequences.append(seq)
                self.targets.append(player_df.iloc[i][target_col])
                pos = player_df.iloc[i]['position']
                self.positions.append(position_encoder.transform([pos])[0])

        self.sequences = torch.FloatTensor(np.array(self.sequences))
        self.targets = torch.FloatTensor(np.array(self.targets))
        self.positions = torch.LongTensor(np.array(self.positions))

        self.feature_dim = len(feature_cols)
        self.n_positions = 4

    def __len__(self):
        return len(self.sequences)

    def __getitem__(self, idx):
        return self.sequences[idx], self.positions[idx], self.targets[idx]


# =============================================================================
# MODEL ARCHITECTURES
# =============================================================================

class SimpleFFN(nn.Module):
    """
    Simple Feedforward Neural Network (Baseline)

    Architecture:
    Input -> Dense(256) -> ReLU -> Dropout -> Dense(128) -> ReLU -> Dropout -> Output

    With position embedding concatenated.
    """

    def __init__(
        self,
        input_dim: int,
        n_positions: int = 4,
        embedding_dim: int = 8,
        hidden_dims: List[int] = [256, 128, 64],
        dropout: float = 0.15  # Reduced from 0.3 for better fit
    ):
        super().__init__()

        self.position_embedding = nn.Embedding(n_positions, embedding_dim)

        layers = []
        prev_dim = input_dim + embedding_dim

        for hidden_dim in hidden_dims:
            layers.extend([
                nn.Linear(prev_dim, hidden_dim),
                nn.ReLU(),
                nn.BatchNorm1d(hidden_dim),
                nn.Dropout(dropout)
            ])
            prev_dim = hidden_dim

        self.backbone = nn.Sequential(*layers)
        self.output = nn.Linear(prev_dim, 1)

    def forward(self, x_numeric, x_position):
        pos_emb = self.position_embedding(x_position)
        x = torch.cat([x_numeric, pos_emb], dim=1)
        x = self.backbone(x)
        return self.output(x).squeeze(-1)


class CareerLSTM(nn.Module):
    """
    LSTM for Career Trajectory Modeling

    Processes sequence of past seasons to predict next season.

    Architecture:
    Career Sequence -> LSTM -> Last Hidden -> Dense -> Output
    """

    def __init__(
        self,
        input_dim: int,
        hidden_dim: int = 128,
        n_layers: int = 2,
        n_positions: int = 4,
        embedding_dim: int = 16,
        dropout: float = 0.15,  # Reduced from 0.3
        bidirectional: bool = True
    ):
        super().__init__()

        self.position_embedding = nn.Embedding(n_positions, embedding_dim)

        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=n_layers,
            batch_first=True,
            dropout=dropout if n_layers > 1 else 0,
            bidirectional=bidirectional
        )

        lstm_output_dim = hidden_dim * 2 if bidirectional else hidden_dim

        self.fc = nn.Sequential(
            nn.Linear(lstm_output_dim + embedding_dim, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 1)
        )

    def forward(self, x_seq, x_position):
        # x_seq: (batch, seq_len, features)
        lstm_out, (h_n, c_n) = self.lstm(x_seq)

        # Use last timestep output
        last_output = lstm_out[:, -1, :]

        # Add position embedding
        pos_emb = self.position_embedding(x_position)
        combined = torch.cat([last_output, pos_emb], dim=1)

        return self.fc(combined).squeeze(-1)


class MultiTaskNN(nn.Module):
    """
    Multi-Task Neural Network

    Shared backbone with separate heads for:
    1. Fantasy PPG prediction (regression)
    2. KTC value prediction (regression)
    3. Breakout probability (classification)

    Architecture:
    Input -> Shared Backbone -> [PPG Head, KTC Head, Breakout Head]
    """

    def __init__(
        self,
        input_dim: int,
        n_positions: int = 4,
        embedding_dim: int = 16,
        backbone_dims: List[int] = [256, 128],
        head_dims: List[int] = [64, 32],
        dropout: float = 0.3
    ):
        super().__init__()

        self.position_embedding = nn.Embedding(n_positions, embedding_dim)

        # Shared backbone
        backbone_layers = []
        prev_dim = input_dim + embedding_dim
        for dim in backbone_dims:
            backbone_layers.extend([
                nn.Linear(prev_dim, dim),
                nn.ReLU(),
                nn.BatchNorm1d(dim),
                nn.Dropout(dropout)
            ])
            prev_dim = dim
        self.backbone = nn.Sequential(*backbone_layers)
        self.backbone_dim = prev_dim

        # Task-specific heads
        self.ppg_head = self._make_head(prev_dim, head_dims, 1, dropout)
        self.ktc_head = self._make_head(prev_dim, head_dims, 1, dropout)
        self.breakout_head = self._make_head(prev_dim, head_dims, 1, dropout, final_activation='sigmoid')

    def _make_head(self, input_dim, hidden_dims, output_dim, dropout, final_activation=None):
        layers = []
        prev_dim = input_dim
        for dim in hidden_dims:
            layers.extend([
                nn.Linear(prev_dim, dim),
                nn.ReLU(),
                nn.Dropout(dropout)
            ])
            prev_dim = dim
        layers.append(nn.Linear(prev_dim, output_dim))
        if final_activation == 'sigmoid':
            layers.append(nn.Sigmoid())
        return nn.Sequential(*layers)

    def forward(self, x_numeric, x_position, return_all=True):
        pos_emb = self.position_embedding(x_position)
        x = torch.cat([x_numeric, pos_emb], dim=1)

        # Shared representation
        shared = self.backbone(x)

        # Task outputs
        ppg = self.ppg_head(shared).squeeze(-1)
        ktc = self.ktc_head(shared).squeeze(-1)
        breakout = self.breakout_head(shared).squeeze(-1)

        if return_all:
            return {'ppg': ppg, 'ktc': ktc, 'breakout': breakout}
        return ppg


class TransformerModel(nn.Module):
    """
    Transformer for Career Trajectory Modeling

    Uses self-attention over career history to weight importance
    of different past seasons.

    Architecture:
    Career Sequence -> Positional Encoding -> Transformer Encoder -> Pool -> Dense -> Output
    """

    def __init__(
        self,
        input_dim: int,
        d_model: int = 64,
        n_heads: int = 4,
        n_layers: int = 2,
        n_positions: int = 4,
        pos_embedding_dim: int = 16,
        dropout: float = 0.3,
        max_seq_len: int = 10
    ):
        super().__init__()

        self.input_projection = nn.Linear(input_dim, d_model)

        # Learnable positional encoding for sequence position
        self.seq_pos_encoding = nn.Parameter(torch.randn(1, max_seq_len, d_model))

        # Position (QB/RB/WR/TE) embedding
        self.position_embedding = nn.Embedding(n_positions, pos_embedding_dim)

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=n_heads,
            dim_feedforward=d_model * 4,
            dropout=dropout,
            batch_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=n_layers)

        self.fc = nn.Sequential(
            nn.Linear(d_model + pos_embedding_dim, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 1)
        )

    def forward(self, x_seq, x_position, mask=None):
        batch_size, seq_len, _ = x_seq.shape

        # Project input
        x = self.input_projection(x_seq)

        # Add positional encoding
        x = x + self.seq_pos_encoding[:, :seq_len, :]

        # Transformer encoding
        x = self.transformer(x, src_key_padding_mask=mask)

        # Pool (use last position or mean)
        x = x[:, -1, :]  # Last position

        # Add position embedding
        pos_emb = self.position_embedding(x_position)
        x = torch.cat([x, pos_emb], dim=1)

        return self.fc(x).squeeze(-1)


# =============================================================================
# PHASE 6: NEURAL NETWORK IMPROVEMENTS (R² IMPROVEMENT PLAN)
# =============================================================================

class MultiHeadFeatureAttentionNN(nn.Module):
    """
    Phase 6.1: Multi-Head Feature Attention Neural Network.

    Uses multiple attention heads to capture different feature importance patterns.
    Each head learns to weight features differently, then outputs are combined.

    Expected R² gain: +0.01-0.02

    Architecture:
    Input -> [Head1, Head2, Head3, Head4] -> Head Combiner -> FFN -> Output
    """

    def __init__(
        self,
        input_dim: int,
        n_positions: int = 4,
        embedding_dim: int = 16,
        n_heads: int = 4,
        hidden_dims: List[int] = [256, 128, 64],
        dropout: float = 0.15,
        attention_hidden: int = 64
    ):
        super().__init__()

        self.input_dim = input_dim
        self.n_heads = n_heads
        self.position_embedding = nn.Embedding(n_positions, embedding_dim)

        # Multiple attention heads
        self.attention_heads = nn.ModuleList([
            nn.Sequential(
                nn.Linear(input_dim, attention_hidden),
                nn.GELU(),
                nn.Linear(attention_hidden, input_dim),
                nn.Softmax(dim=-1)
            )
            for _ in range(n_heads)
        ])

        # Combine attention head outputs
        self.head_combiner = nn.Sequential(
            nn.Linear(n_heads * input_dim, hidden_dims[0]),
            nn.LayerNorm(hidden_dims[0]),
            nn.GELU()
        )

        # Position embedding projection
        self.pos_proj = nn.Linear(embedding_dim, hidden_dims[0])

        # Main backbone
        self.blocks = nn.ModuleList()
        for i in range(len(hidden_dims) - 1):
            self.blocks.append(self._make_block(hidden_dims[i], hidden_dims[i + 1], dropout))

        # Output layer
        self.output = nn.Sequential(
            nn.Linear(hidden_dims[-1], 32),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(32, 1)
        )

        # Store attention weights for interpretability
        self._attention_weights = None

    def _make_block(self, in_dim: int, out_dim: int, dropout: float):
        """Create a residual block."""
        return nn.ModuleDict({
            'main': nn.Sequential(
                nn.Linear(in_dim, out_dim),
                nn.LayerNorm(out_dim),
                nn.GELU(),
                nn.Dropout(dropout)
            ),
            'shortcut': nn.Linear(in_dim, out_dim) if in_dim != out_dim else nn.Identity()
        })

    def forward(self, x_numeric, x_position):
        # Apply each attention head
        attended_features = []
        attention_weights = []

        for head in self.attention_heads:
            attention = head(x_numeric)  # (batch, input_dim)
            weighted = x_numeric * attention * self.input_dim  # Scale to maintain magnitude
            attended_features.append(weighted)
            attention_weights.append(attention)

        # Stack attention weights for interpretability
        self._attention_weights = torch.stack(attention_weights, dim=1)  # (batch, n_heads, input_dim)

        # Concatenate all head outputs
        multi_head_features = torch.cat(attended_features, dim=1)  # (batch, n_heads * input_dim)

        # Combine heads
        x = self.head_combiner(multi_head_features)

        # Add position embedding
        pos_emb = self.position_embedding(x_position)
        pos_proj = self.pos_proj(pos_emb)
        x = x + pos_proj  # Residual connection

        # Pass through blocks
        for block in self.blocks:
            identity = block['shortcut'](x)
            x = block['main'](x) + identity

        return self.output(x).squeeze(-1)

    def get_attention_weights(self) -> Optional[torch.Tensor]:
        """Return attention weights from all heads (batch, n_heads, input_dim)."""
        return self._attention_weights


class PositionAwareNN(nn.Module):
    """
    Phase 6.2: Position-Specific Output Heads Neural Network.

    Shared backbone learns common patterns, then position-specific heads
    capture unique dynamics for QB/RB/WR/TE.

    Expected R² gain: +0.02-0.03

    Architecture:
    Input -> Shared Backbone -> [QB Head | RB Head | WR Head | TE Head] -> Output
    """

    def __init__(
        self,
        input_dim: int,
        n_positions: int = 4,
        embedding_dim: int = 16,
        backbone_dims: List[int] = [256, 128],
        head_hidden_dim: int = 64,
        dropout: float = 0.15
    ):
        super().__init__()

        self.position_embedding = nn.Embedding(n_positions, embedding_dim)

        # Shared backbone
        backbone_layers = []
        prev_dim = input_dim + embedding_dim
        for dim in backbone_dims:
            backbone_layers.extend([
                nn.Linear(prev_dim, dim),
                nn.LayerNorm(dim),
                nn.GELU(),
                nn.Dropout(dropout)
            ])
            prev_dim = dim
        self.backbone = nn.Sequential(*backbone_layers)
        self.backbone_dim = prev_dim

        # Position-specific output heads
        # Position encoding: 0=QB, 1=RB, 2=WR, 3=TE
        self.position_heads = nn.ModuleDict({
            '0': self._make_position_head(prev_dim, head_hidden_dim, dropout),  # QB
            '1': self._make_position_head(prev_dim, head_hidden_dim, dropout),  # RB
            '2': self._make_position_head(prev_dim, head_hidden_dim, dropout),  # WR
            '3': self._make_position_head(prev_dim, head_hidden_dim, dropout),  # TE
        })

    def _make_position_head(self, input_dim: int, hidden_dim: int, dropout: float):
        """Create a position-specific output head."""
        return nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, 32),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(32, 1)
        )

    def forward(self, x_numeric, x_position):
        # Add position embedding
        pos_emb = self.position_embedding(x_position)
        x = torch.cat([x_numeric, pos_emb], dim=1)

        # Shared backbone
        shared = self.backbone(x)

        # Route to position-specific heads
        batch_size = x_numeric.size(0)
        outputs = torch.zeros(batch_size, device=x_numeric.device)

        for i, pos_idx in enumerate(x_position):
            head = self.position_heads[str(pos_idx.item())]
            outputs[i] = head(shared[i:i+1]).squeeze()

        return outputs


class CareerTrajectoryLSTM(nn.Module):
    """
    Phase 6.3: Career Trajectory LSTM (Experimental).

    Enhanced version of the existing CareerLSTM with:
    - Deeper LSTM layers
    - Attention over timesteps
    - Career arc features

    Expected R² gain: +0.01-0.02

    Architecture:
    Career Sequence -> LSTM -> Attention -> Dense -> Output
    """

    def __init__(
        self,
        input_dim: int,
        hidden_dim: int = 128,
        n_layers: int = 3,  # Deeper than original
        n_positions: int = 4,
        embedding_dim: int = 16,
        dropout: float = 0.15,
        bidirectional: bool = True,
        use_attention: bool = True
    ):
        super().__init__()

        self.use_attention = use_attention
        self.position_embedding = nn.Embedding(n_positions, embedding_dim)

        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=n_layers,
            batch_first=True,
            dropout=dropout if n_layers > 1 else 0,
            bidirectional=bidirectional
        )

        lstm_output_dim = hidden_dim * 2 if bidirectional else hidden_dim

        # Optional temporal attention
        if use_attention:
            self.attention = nn.Sequential(
                nn.Linear(lstm_output_dim, 64),
                nn.Tanh(),
                nn.Linear(64, 1)
            )

        self.fc = nn.Sequential(
            nn.Linear(lstm_output_dim + embedding_dim, 128),
            nn.LayerNorm(128),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(128, 64),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(64, 1)
        )

    def forward(self, x_seq, x_position):
        # x_seq: (batch, seq_len, features)
        lstm_out, (h_n, c_n) = self.lstm(x_seq)

        # Apply attention over timesteps if enabled
        if self.use_attention:
            # Compute attention scores for each timestep
            attention_scores = self.attention(lstm_out)  # (batch, seq_len, 1)
            attention_weights = F.softmax(attention_scores, dim=1)

            # Weighted sum of LSTM outputs
            context = (lstm_out * attention_weights).sum(dim=1)  # (batch, lstm_output_dim)
        else:
            # Use last timestep output
            context = lstm_out[:, -1, :]

        # Add position embedding
        pos_emb = self.position_embedding(x_position)
        combined = torch.cat([context, pos_emb], dim=1)

        return self.fc(combined).squeeze(-1)


# =============================================================================
# TRAINING UTILITIES
# =============================================================================

class FeatureAttentionNN(nn.Module):
    """
    Feedforward Neural Network with Learnable Feature Attention.

    This model learns to weight different input features based on their
    importance for prediction. The attention mechanism helps identify
    which features matter most for each prediction.

    Expected R² gain: +0.01

    Architecture:
    Input -> Feature Attention -> Weighted Features -> FFN Backbone -> Output
    """

    def __init__(
        self,
        input_dim: int,
        n_positions: int = 4,
        embedding_dim: int = 16,
        hidden_dims: List[int] = [256, 128, 64],
        dropout: float = 0.15,  # Reduced from 0.3 for better fit with 9K samples
        attention_hidden: int = 64
    ):
        super().__init__()

        self.input_dim = input_dim
        self.position_embedding = nn.Embedding(n_positions, embedding_dim)

        # Feature attention mechanism
        # Learns which features are most important
        self.feature_attention = nn.Sequential(
            nn.Linear(input_dim, attention_hidden),
            nn.GELU(),  # Phase 3.3: GELU activation for better gradients
            nn.Linear(attention_hidden, input_dim),
            nn.Softmax(dim=-1)
        )

        # Main backbone with residual connections
        self.input_proj = nn.Linear(input_dim + embedding_dim, hidden_dims[0])

        self.blocks = nn.ModuleList()
        for i in range(len(hidden_dims) - 1):
            self.blocks.append(self._make_block(hidden_dims[i], hidden_dims[i + 1], dropout))

        # Output layer
        self.output = nn.Sequential(
            nn.Linear(hidden_dims[-1], 32),
            nn.GELU(),  # Phase 3.3: GELU activation
            nn.Dropout(dropout),
            nn.Linear(32, 1)
        )

        # Store attention weights for interpretability
        self._attention_weights = None

    def _make_block(self, in_dim: int, out_dim: int, dropout: float):
        """Create a residual block with LayerNorm and GELU."""
        return nn.ModuleDict({
            'main': nn.Sequential(
                nn.Linear(in_dim, out_dim),
                nn.LayerNorm(out_dim),
                nn.GELU(),  # Phase 3.3: GELU activation
                nn.Dropout(dropout)
            ),
            'shortcut': nn.Linear(in_dim, out_dim) if in_dim != out_dim else nn.Identity()
        })

    def forward(self, x_numeric, x_position):
        # Compute feature attention weights
        attention = self.feature_attention(x_numeric)  # (batch, input_dim)
        self._attention_weights = attention.detach()  # Store for interpretability

        # Apply attention to features (element-wise multiply)
        x_weighted = x_numeric * attention * self.input_dim  # Scale to maintain magnitude

        # Add position embedding
        pos_emb = self.position_embedding(x_position)
        x = torch.cat([x_weighted, pos_emb], dim=1)

        # Project to hidden dimension
        x = self.input_proj(x)

        # Pass through residual blocks (Phase 3.1: proper residual connections)
        for block in self.blocks:
            identity = block['shortcut'](x)
            x = block['main'](x) + identity  # Residual connection

        return self.output(x).squeeze(-1)

    def get_attention_weights(self) -> Optional[torch.Tensor]:
        """Return the most recent attention weights for interpretability."""
        return self._attention_weights

    def get_feature_importance(self, feature_names: List[str]) -> Dict[str, float]:
        """
        Get average feature importance across all predictions.

        Args:
            feature_names: List of feature names in order

        Returns:
            Dict mapping feature names to importance scores
        """
        if self._attention_weights is None:
            return {}

        avg_weights = self._attention_weights.mean(dim=0).cpu().numpy()
        return {name: float(weight) for name, weight in zip(feature_names, avg_weights)}


class DynastyWeightedHuberLoss(nn.Module):
    """
    Huber Loss with Dynasty Value Weighting.

    Combines Huber loss (robust to outliers) with optional weighting
    that emphasizes errors on high-value players.

    Benefits:
    - Huber loss reduces impact of outlier predictions
    - Dynasty weighting penalizes errors on elite players more heavily
    - Expected R² gain: +0.01
    """

    def __init__(
        self,
        delta: float = 5.0,  # Huber loss threshold
        dynasty_weight: bool = True,  # Whether to apply dynasty weighting
        elite_threshold: float = 15.0,  # PPG threshold for "elite" players
        elite_weight: float = 1.5  # Weight multiplier for elite players
    ):
        super().__init__()
        self.delta = delta
        self.dynasty_weight = dynasty_weight
        self.elite_threshold = elite_threshold
        self.elite_weight = elite_weight
        self.huber = nn.HuberLoss(delta=delta, reduction='none')

    def forward(self, predictions: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        # Compute element-wise Huber loss
        loss = self.huber(predictions, targets)

        if self.dynasty_weight:
            # Apply higher weight to elite player predictions
            weights = torch.where(
                targets >= self.elite_threshold,
                torch.full_like(targets, self.elite_weight),
                torch.ones_like(targets)
            )
            loss = loss * weights

        return loss.mean()


class MultiTaskLoss(nn.Module):
    """
    Combined loss for multi-task learning.

    L_total = w_ppg * L_ppg + w_ktc * L_ktc + w_breakout * L_breakout
    """

    def __init__(
        self,
        ppg_weight: float = 1.0,
        ktc_weight: float = 0.5,
        breakout_weight: float = 0.3
    ):
        super().__init__()
        self.ppg_weight = ppg_weight
        self.ktc_weight = ktc_weight
        self.breakout_weight = breakout_weight

        self.mse = nn.MSELoss()
        self.bce = nn.BCELoss()

    def forward(self, outputs, targets):
        """
        Args:
            outputs: dict with 'ppg', 'ktc', 'breakout' predictions
            targets: dict with 'ppg', 'ktc', 'breakout' ground truth
        """
        loss = 0.0

        if 'ppg' in targets and targets['ppg'] is not None:
            loss += self.ppg_weight * self.mse(outputs['ppg'], targets['ppg'])

        if 'ktc' in targets and targets['ktc'] is not None:
            # Log-transform KTC for better scaling
            loss += self.ktc_weight * self.mse(
                torch.log1p(outputs['ktc']),
                torch.log1p(targets['ktc'])
            )

        if 'breakout' in targets and targets['breakout'] is not None:
            loss += self.breakout_weight * self.bce(outputs['breakout'], targets['breakout'])

        return loss


def train_epoch(model, dataloader, optimizer, criterion, device):
    """Train for one epoch."""
    model.train()
    total_loss = 0.0

    for batch in dataloader:
        if len(batch) == 3:
            x_numeric, x_cat, y = batch
            x_numeric = x_numeric.to(device)
            x_cat = x_cat.to(device)
            y = y.to(device)

            optimizer.zero_grad()
            outputs = model(x_numeric, x_cat[:, 0])  # First cat is position
            loss = criterion(outputs, y)
        else:
            x_seq, x_pos, y = batch
            x_seq = x_seq.to(device)
            x_pos = x_pos.to(device)
            y = y.to(device)

            optimizer.zero_grad()
            outputs = model(x_seq, x_pos)
            loss = criterion(outputs, y)

        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()

        total_loss += loss.item()

    return total_loss / len(dataloader)


def evaluate(model, dataloader, criterion, device):
    """Evaluate model."""
    model.eval()
    total_loss = 0.0
    predictions = []
    actuals = []

    with torch.no_grad():
        for batch in dataloader:
            if len(batch) == 3:
                x_numeric, x_cat, y = batch
                x_numeric = x_numeric.to(device)
                x_cat = x_cat.to(device)
                y = y.to(device)
                outputs = model(x_numeric, x_cat[:, 0])
            else:
                x_seq, x_pos, y = batch
                x_seq = x_seq.to(device)
                x_pos = x_pos.to(device)
                y = y.to(device)
                outputs = model(x_seq, x_pos)

            loss = criterion(outputs, y)
            total_loss += loss.item()

            predictions.extend(outputs.cpu().numpy())
            actuals.extend(y.cpu().numpy())

    predictions = np.array(predictions)
    actuals = np.array(actuals)

    # Calculate R²
    ss_res = np.sum((actuals - predictions) ** 2)
    ss_tot = np.sum((actuals - np.mean(actuals)) ** 2)
    r2 = 1 - (ss_res / ss_tot)

    rmse = np.sqrt(np.mean((predictions - actuals) ** 2))

    return {
        'loss': total_loss / len(dataloader),
        'r2': r2,
        'rmse': rmse,
        'predictions': predictions,
        'actuals': actuals
    }


# =============================================================================
# HIGH-LEVEL TRAINING API
# =============================================================================

class NeuralNetworkTrainer:
    """
    High-level API for training neural network models.

    Usage:
        trainer = NeuralNetworkTrainer(model_type='lstm')
        trainer.fit(df, target='next_ppg_ppr')
        predictions = trainer.predict(new_df)
    """

    FEATURE_COLS = [
        'ppg_ppr', 'ppg_std', 'games',
        'passing_yards', 'passing_tds', 'interceptions',
        'rushing_yards', 'rushing_tds', 'carries',
        'targets', 'receptions', 'receiving_yards', 'receiving_tds',
        'years_in_league', 'career_ppg', 'best_season_ppg',
        'targets_per_game', 'receptions_per_game', 'rec_yards_per_game',
        'carries_per_game', 'rush_yards_per_game',
        'catch_rate', 'yards_per_catch', 'yards_per_carry',
        'ppg_vs_career_avg', 'ppg_vs_best',
        'target_share_calc', 'carry_share', 'opportunity_share',
        'estimated_age', 'years_to_peak', 'age_decline_risk',
        'first_half_ppg', 'second_half_ppg', 'ppg_surge'
    ]

    def __init__(
        self,
        model_type: str = 'ffn',  # 'ffn', 'lstm', 'transformer', 'multitask', 'attention',
                                  # 'multihead_attention', 'position_aware', 'career_trajectory'
        device: str = 'auto',
        loss_type: str = 'mse',  # 'mse', 'huber', 'dynasty_huber'
        **model_kwargs
    ):
        self.model_type = model_type
        self.loss_type = loss_type
        self.device = torch.device(
            'cuda' if device == 'auto' and torch.cuda.is_available()
            else 'mps' if device == 'auto' and torch.backends.mps.is_available()
            else 'cpu'
        )
        self.model_kwargs = model_kwargs
        self.model = None
        self.scaler = None
        self.label_encoders = {}
        self.feature_importance = None  # For attention models

    def fit(
        self,
        df: pd.DataFrame,
        target: str = 'next_ppg_ppr',
        epochs: int = 100,
        batch_size: int = 64,
        lr: float = 1e-3,
        patience: int = 10,
        validation_split: float = 0.2
    ):
        """Train the model."""
        logger.info(f"Training {self.model_type} model on {len(df)} samples")

        # Filter to available features
        available_features = [f for f in self.FEATURE_COLS if f in df.columns]

        # Split data
        train_df, val_df = train_test_split(df, test_size=validation_split, random_state=42)

        # Create datasets
        if self.model_type in ['lstm', 'transformer']:
            train_dataset = CareerSequenceDataset(
                train_df, available_features, target, fit=True
            )
            val_dataset = CareerSequenceDataset(
                val_df, available_features, target,
                scaler=train_dataset.scaler, fit=False
            )
            self.scaler = train_dataset.scaler
            input_dim = train_dataset.feature_dim
        else:
            train_dataset = FantasyDataset(
                train_df, available_features, target, fit=True
            )
            val_dataset = FantasyDataset(
                val_df, available_features, target,
                scaler=train_dataset.scaler,
                label_encoders=train_dataset.label_encoders,
                fit=False
            )
            self.scaler = train_dataset.scaler
            self.label_encoders = train_dataset.label_encoders
            input_dim = train_dataset.numeric_dim

        # Create model
        if self.model_type == 'ffn':
            self.model = SimpleFFN(input_dim, **self.model_kwargs)
        elif self.model_type == 'lstm':
            self.model = CareerLSTM(input_dim, **self.model_kwargs)
        elif self.model_type == 'transformer':
            self.model = TransformerModel(input_dim, **self.model_kwargs)
        elif self.model_type == 'multitask':
            self.model = MultiTaskNN(input_dim, **self.model_kwargs)
        elif self.model_type == 'attention':
            self.model = FeatureAttentionNN(input_dim, **self.model_kwargs)
        elif self.model_type == 'multihead_attention':
            # Phase 6.1: Multi-Head Feature Attention
            self.model = MultiHeadFeatureAttentionNN(input_dim, **self.model_kwargs)
        elif self.model_type == 'position_aware':
            # Phase 6.2: Position-Specific Output Heads
            self.model = PositionAwareNN(input_dim, **self.model_kwargs)
        elif self.model_type == 'career_trajectory':
            # Phase 6.3: Career Trajectory LSTM
            self.model = CareerTrajectoryLSTM(input_dim, **self.model_kwargs)
        else:
            raise ValueError(f"Unknown model_type: {self.model_type}")

        self.model.to(self.device)

        # Store feature names for attention interpretability
        self._feature_names = available_features

        # Create dataloaders
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=batch_size)

        # Training setup
        optimizer = torch.optim.AdamW(self.model.parameters(), lr=lr, weight_decay=0.01)
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode='min', factor=0.5, patience=5
        )

        # Select loss function
        if self.loss_type == 'mse':
            criterion = nn.MSELoss()
        elif self.loss_type == 'huber':
            criterion = nn.HuberLoss(delta=5.0)
        elif self.loss_type == 'dynasty_huber':
            criterion = DynastyWeightedHuberLoss(delta=5.0, dynasty_weight=True)
        else:
            logger.warning(f"Unknown loss_type '{self.loss_type}', defaulting to MSE")
            criterion = nn.MSELoss()

        logger.info(f"Using loss function: {self.loss_type}")

        # Training loop
        best_val_loss = float('inf')
        patience_counter = 0
        history = {'train_loss': [], 'val_loss': [], 'val_r2': []}

        for epoch in range(epochs):
            train_loss = train_epoch(self.model, train_loader, optimizer, criterion, self.device)
            val_metrics = evaluate(self.model, val_loader, criterion, self.device)

            history['train_loss'].append(train_loss)
            history['val_loss'].append(val_metrics['loss'])
            history['val_r2'].append(val_metrics['r2'])

            scheduler.step(val_metrics['loss'])

            if val_metrics['loss'] < best_val_loss:
                best_val_loss = val_metrics['loss']
                patience_counter = 0
                # Save best model
                self.best_state = self.model.state_dict().copy()
            else:
                patience_counter += 1

            if (epoch + 1) % 10 == 0:
                logger.info(f"Epoch {epoch+1}: Train Loss={train_loss:.4f}, "
                          f"Val Loss={val_metrics['loss']:.4f}, Val R²={val_metrics['r2']:.4f}")

            if patience_counter >= patience:
                logger.info(f"Early stopping at epoch {epoch+1}")
                break

        # Restore best model
        self.model.load_state_dict(self.best_state)

        # Final evaluation
        final_metrics = evaluate(self.model, val_loader, criterion, self.device)
        logger.info(f"Final Val R²: {final_metrics['r2']:.4f}, RMSE: {final_metrics['rmse']:.2f}")

        return history, final_metrics

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        """Make predictions."""
        self.model.eval()
        available_features = [f for f in self.FEATURE_COLS if f in df.columns]

        if self.model_type in ['lstm', 'transformer']:
            dataset = CareerSequenceDataset(
                df, available_features, 'next_ppg_ppr',
                scaler=self.scaler, fit=False
            )
        else:
            dataset = FantasyDataset(
                df, available_features, 'next_ppg_ppr',
                scaler=self.scaler,
                label_encoders=self.label_encoders,
                fit=False
            )

        loader = DataLoader(dataset, batch_size=64)
        predictions = []

        with torch.no_grad():
            for batch in loader:
                if len(batch) == 3:
                    x_numeric, x_cat, _ = batch
                    x_numeric = x_numeric.to(self.device)
                    x_cat = x_cat.to(self.device)
                    out = self.model(x_numeric, x_cat[:, 0])
                else:
                    x_seq, x_pos, _ = batch
                    x_seq = x_seq.to(self.device)
                    x_pos = x_pos.to(self.device)
                    out = self.model(x_seq, x_pos)
                predictions.extend(out.cpu().numpy())

        return np.array(predictions)

    def save(self, path: str):
        """Save model."""
        torch.save({
            'model_state': self.model.state_dict(),
            'model_type': self.model_type,
            'model_kwargs': self.model_kwargs,
            'scaler': self.scaler,
            'label_encoders': self.label_encoders
        }, path)

    @classmethod
    def load(cls, path: str):
        """Load model."""
        checkpoint = torch.load(path, map_location='cpu')
        trainer = cls(model_type=checkpoint['model_type'], **checkpoint['model_kwargs'])
        trainer.scaler = checkpoint['scaler']
        trainer.label_encoders = checkpoint['label_encoders']
        # Model will be created when predict is called
        return trainer


# =============================================================================
# COMPARISON SCRIPT
# =============================================================================

def compare_architectures():
    """Compare different neural network architectures."""
    import pandas as pd

    # Load data
    df = pd.read_parquet('data/ml_training/season_projection.parquet')

    results = {}

    # 1. Simple FFN
    print("\n" + "="*60)
    print("Training Simple FFN...")
    print("="*60)
    ffn_trainer = NeuralNetworkTrainer(model_type='ffn')
    _, ffn_metrics = ffn_trainer.fit(df, epochs=50)
    results['FFN'] = ffn_metrics

    # 2. LSTM
    print("\n" + "="*60)
    print("Training Career LSTM...")
    print("="*60)
    lstm_trainer = NeuralNetworkTrainer(model_type='lstm')
    _, lstm_metrics = lstm_trainer.fit(df, epochs=50)
    results['LSTM'] = lstm_metrics

    # 3. Transformer
    print("\n" + "="*60)
    print("Training Transformer...")
    print("="*60)
    transformer_trainer = NeuralNetworkTrainer(model_type='transformer')
    _, transformer_metrics = transformer_trainer.fit(df, epochs=50)
    results['Transformer'] = transformer_metrics

    # Summary
    print("\n" + "="*60)
    print("ARCHITECTURE COMPARISON RESULTS")
    print("="*60)
    print(f"{'Model':<15} {'Val R²':>10} {'Val RMSE':>10}")
    print("-"*35)
    for name, metrics in results.items():
        print(f"{name:<15} {metrics['r2']:>10.4f} {metrics['rmse']:>10.2f}")

    return results


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    compare_architectures()
