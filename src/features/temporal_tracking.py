"""
Temporal Tracking System for Dynasty Edge
From: temporal_causality_architecture.md

Tracks player value changes over time and discovers correlations
between metrics and KTC value movements.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Tuple
from pathlib import Path

import pandas as pd
import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)


class TemporalTracker:
    """
    Track player snapshots over time to discover value drivers.

    Key concepts:
    - Snapshot: Player state at a point in time (KTC, stats, etc.)
    - Correlation: Discovered relationship between metric change and KTC change
    - ModelConfig: Current valuation model weights
    """

    def __init__(self, driver):
        """
        Initialize tracker with Neo4j driver.

        Args:
            driver: Neo4j driver instance
        """
        self.driver = driver

    def create_snapshot(self, player_data: Dict[str, Any], date: datetime = None) -> str:
        """
        Create a temporal snapshot for a player.

        Args:
            player_data: Dict with player metrics
            date: Snapshot date (defaults to now)

        Returns:
            Snapshot ID
        """
        date = date or datetime.now()
        date_str = date.strftime('%Y-%m-%d')
        gsis_id = player_data.get('gsis_id')

        if not gsis_id:
            raise ValueError("player_data must contain 'gsis_id'")

        snapshot_id = f"{gsis_id}_{date_str}"

        with self.driver.session() as session:
            # Get previous snapshot for delta calculation
            prev_result = session.run("""
                MATCH (p:Player {gsis_id: $gsis_id})-[:HAD_SNAPSHOT]->(s:Snapshot)
                RETURN s ORDER BY s.date DESC LIMIT 1
            """, gsis_id=gsis_id)

            prev = prev_result.single()
            prev_ktc = prev['s']['ktc_value'] if prev else player_data.get('ktc_value', 0)
            current_ktc = player_data.get('ktc_value', 0)

            ktc_delta = current_ktc - prev_ktc
            ktc_delta_pct = (ktc_delta / prev_ktc * 100) if prev_ktc > 0 else 0

            # Create snapshot
            session.run("""
                MATCH (p:Player {gsis_id: $gsis_id})
                MERGE (s:Snapshot {snapshot_id: $snapshot_id})
                SET s.gsis_id = $gsis_id,
                    s.date = date($date),
                    s.ktc_value = $ktc_value,
                    s.ktc_delta = $ktc_delta,
                    s.ktc_delta_pct = $ktc_delta_pct,
                    s.targets = $targets,
                    s.targets_per_game = $targets_per_game,
                    s.receptions = $receptions,
                    s.fantasy_ppg = $fantasy_ppg,
                    s.snap_share = $snap_share,
                    s.target_share = $target_share,
                    s.air_yards_share = $air_yards_share,
                    s.games_played = $games_played,
                    s.injury_status = $injury_status,
                    s.created_at = datetime()
                MERGE (p)-[:HAD_SNAPSHOT]->(s)
            """, {
                'gsis_id': gsis_id,
                'snapshot_id': snapshot_id,
                'date': date_str,
                'ktc_value': current_ktc,
                'ktc_delta': ktc_delta,
                'ktc_delta_pct': round(ktc_delta_pct, 2),
                'targets': player_data.get('targets', 0),
                'targets_per_game': player_data.get('targets_per_game', 0),
                'receptions': player_data.get('receptions', 0),
                'fantasy_ppg': player_data.get('fantasy_ppg', 0),
                'snap_share': player_data.get('snap_share', 0),
                'target_share': player_data.get('target_share', 0),
                'air_yards_share': player_data.get('air_yards_share', 0),
                'games_played': player_data.get('games_played', 0),
                'injury_status': player_data.get('injury_status', 'Active'),
            })

            # Link to previous snapshot
            if prev:
                days_between = (date - datetime.strptime(str(prev['s']['date']), '%Y-%m-%d')).days
                session.run("""
                    MATCH (prev:Snapshot {snapshot_id: $prev_id})
                    MATCH (curr:Snapshot {snapshot_id: $curr_id})
                    MERGE (prev)-[:SNAPSHOT_NEXT {days_between: $days}]->(curr)
                """, {
                    'prev_id': prev['s']['snapshot_id'],
                    'curr_id': snapshot_id,
                    'days': days_between
                })

        logger.debug(f"Created snapshot {snapshot_id}: KTC {current_ktc} (delta: {ktc_delta:+d})")
        return snapshot_id

    def create_bulk_snapshots(self, players_df: pd.DataFrame, date: datetime = None) -> int:
        """
        Create snapshots for multiple players.

        Args:
            players_df: DataFrame with player data
            date: Snapshot date

        Returns:
            Number of snapshots created
        """
        date = date or datetime.now()
        count = 0

        for _, row in players_df.iterrows():
            try:
                self.create_snapshot(row.to_dict(), date)
                count += 1
            except Exception as e:
                logger.warning(f"Failed to create snapshot for {row.get('name', 'unknown')}: {e}")

        logger.info(f"Created {count} snapshots for {date.strftime('%Y-%m-%d')}")
        return count

    def get_player_history(self, gsis_id: str, days: int = 90) -> pd.DataFrame:
        """
        Get snapshot history for a player.

        Args:
            gsis_id: Player ID
            days: Number of days of history

        Returns:
            DataFrame with snapshot history
        """
        with self.driver.session() as session:
            result = session.run("""
                MATCH (p:Player {gsis_id: $gsis_id})-[:HAD_SNAPSHOT]->(s:Snapshot)
                WHERE s.date >= date() - duration({days: $days})
                RETURN s.date as date, s.ktc_value as ktc_value,
                       s.ktc_delta as ktc_delta, s.ktc_delta_pct as ktc_delta_pct,
                       s.targets_per_game as targets_per_game,
                       s.fantasy_ppg as fantasy_ppg,
                       s.snap_share as snap_share,
                       s.target_share as target_share
                ORDER BY s.date
            """, gsis_id=gsis_id, days=days)

            data = [dict(r) for r in result]

        return pd.DataFrame(data) if data else pd.DataFrame()


class CorrelationDiscovery:
    """
    Discover correlations between metrics and KTC value changes.

    Uses temporal snapshot data to identify what drives value changes.
    """

    # Metrics to analyze
    METRICS = [
        'targets_per_game',
        'fantasy_ppg',
        'snap_share',
        'target_share',
        'air_yards_share',
    ]

    def __init__(self, driver):
        self.driver = driver

    def discover_correlations(self, lookback_days: int = 60,
                              position: str = 'ALL',
                              min_samples: int = 30) -> List[Dict[str, Any]]:
        """
        Discover correlations between metric changes and KTC changes.

        Args:
            lookback_days: Days of history to analyze
            position: Position to filter (or 'ALL')
            min_samples: Minimum samples for statistical significance

        Returns:
            List of discovered correlations
        """
        correlations = []

        with self.driver.session() as session:
            # Get snapshot pairs with deltas
            position_filter = "AND p.position = $position" if position != 'ALL' else ""

            result = session.run(f"""
                MATCH (p:Player)-[:HAD_SNAPSHOT]->(s1:Snapshot)-[:SNAPSHOT_NEXT]->(s2:Snapshot)
                WHERE s2.date >= date() - duration({{days: $days}})
                {position_filter}
                RETURN p.position as position,
                       s2.ktc_delta_pct as ktc_delta_pct,
                       s2.targets_per_game - s1.targets_per_game as targets_delta,
                       s2.fantasy_ppg - s1.fantasy_ppg as fantasy_delta,
                       s2.snap_share - s1.snap_share as snap_delta,
                       s2.target_share - s1.target_share as target_share_delta
            """, days=lookback_days, position=position if position != 'ALL' else None)

            data = [dict(r) for r in result]

        if len(data) < min_samples:
            logger.warning(f"Insufficient samples ({len(data)}) for correlation discovery")
            return correlations

        df = pd.DataFrame(data)

        # Calculate correlations for each metric
        metric_deltas = {
            'targets_per_game': 'targets_delta',
            'fantasy_ppg': 'fantasy_delta',
            'snap_share': 'snap_delta',
            'target_share': 'target_share_delta',
        }

        for metric_name, delta_col in metric_deltas.items():
            if delta_col not in df.columns:
                continue

            # Filter out NaN
            valid = df[[delta_col, 'ktc_delta_pct']].dropna()

            if len(valid) < min_samples:
                continue

            # Calculate Pearson correlation
            r, p_value = stats.pearsonr(valid[delta_col], valid['ktc_delta_pct'])

            # Determine strength
            if abs(r) >= 0.7:
                strength = 'Strong'
            elif abs(r) >= 0.4:
                strength = 'Moderate'
            elif abs(r) >= 0.2:
                strength = 'Weak'
            else:
                strength = 'None'

            correlation = {
                'correlation_id': f"{metric_name}_{position}_{lookback_days}d",
                'metric_name': metric_name,
                'position': position,
                'pearson_r': round(r, 4),
                'p_value': round(p_value, 6),
                'sample_size': len(valid),
                'lookback_days': lookback_days,
                'discovered_date': datetime.now().strftime('%Y-%m-%d'),
                'strength': strength,
                'direction': 'Positive' if r > 0 else 'Negative',
                'confidence': 'High' if p_value < 0.01 else ('Medium' if p_value < 0.05 else 'Low'),
            }

            correlations.append(correlation)
            logger.info(f"Discovered: {metric_name} → KTC (r={r:.3f}, p={p_value:.4f}, {strength})")

        return correlations

    def save_correlations_to_neo4j(self, correlations: List[Dict[str, Any]]):
        """Save discovered correlations to Neo4j."""
        with self.driver.session() as session:
            for corr in correlations:
                session.run("""
                    MERGE (c:Correlation {correlation_id: $id})
                    SET c.metric_name = $metric,
                        c.position = $position,
                        c.pearson_r = $r,
                        c.p_value = $p,
                        c.sample_size = $samples,
                        c.lookback_days = $days,
                        c.discovered_date = date($date),
                        c.strength = $strength,
                        c.direction = $direction,
                        c.confidence = $confidence,
                        c.updated_at = datetime()
                """, {
                    'id': corr['correlation_id'],
                    'metric': corr['metric_name'],
                    'position': corr['position'],
                    'r': corr['pearson_r'],
                    'p': corr['p_value'],
                    'samples': corr['sample_size'],
                    'days': corr['lookback_days'],
                    'date': corr['discovered_date'],
                    'strength': corr['strength'],
                    'direction': corr['direction'],
                    'confidence': corr['confidence'],
                })

        logger.info(f"Saved {len(correlations)} correlations to Neo4j")

    def discover_and_save(self, lookback_days: int = 60) -> List[Dict[str, Any]]:
        """Discover correlations for all positions and save."""
        all_correlations = []

        # Overall
        correlations = self.discover_correlations(lookback_days, 'ALL')
        all_correlations.extend(correlations)

        # By position
        for position in ['QB', 'RB', 'WR', 'TE']:
            correlations = self.discover_correlations(lookback_days, position)
            all_correlations.extend(correlations)

        if all_correlations:
            self.save_correlations_to_neo4j(all_correlations)

        return all_correlations


class ModelConfigManager:
    """
    Manage valuation model configurations.

    Allows dynamic adjustment of feature weights based on discovered correlations.
    """

    DEFAULT_WEIGHTS = {
        'age_factor': 0.25,
        'production': 0.30,
        'opportunity': 0.20,
        'draft_capital': 0.10,
        'situation': 0.15,
    }

    def __init__(self, driver):
        self.driver = driver

    def get_active_config(self) -> Dict[str, Any]:
        """Get currently active model configuration."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (mc:ModelConfig {is_active: true})
                RETURN mc
            """)

            record = result.single()
            if record:
                return dict(record['mc'])

        # Return default if no active config
        return {
            'config_id': 'default',
            'weights': self.DEFAULT_WEIGHTS,
            'is_active': True,
        }

    def create_config(self, weights: Dict[str, float],
                      created_by: str = 'system',
                      activate: bool = False) -> str:
        """
        Create a new model configuration.

        Args:
            weights: Feature weights dict
            created_by: Who created this config
            activate: Whether to make this the active config

        Returns:
            Config ID
        """
        config_id = f"config_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        with self.driver.session() as session:
            # Deactivate current active config if activating new one
            if activate:
                session.run("MATCH (mc:ModelConfig {is_active: true}) SET mc.is_active = false")

            # Create new config
            session.run("""
                CREATE (mc:ModelConfig {
                    config_id: $id,
                    created_date: datetime(),
                    created_by: $by,
                    is_active: $active,
                    weights_age_factor: $w_age,
                    weights_production: $w_prod,
                    weights_opportunity: $w_opp,
                    weights_draft_capital: $w_draft,
                    weights_situation: $w_sit
                })
            """, {
                'id': config_id,
                'by': created_by,
                'active': activate,
                'w_age': weights.get('age_factor', 0.25),
                'w_prod': weights.get('production', 0.30),
                'w_opp': weights.get('opportunity', 0.20),
                'w_draft': weights.get('draft_capital', 0.10),
                'w_sit': weights.get('situation', 0.15),
            })

        logger.info(f"Created config {config_id} (active: {activate})")
        return config_id

    def suggest_weights_from_correlations(self) -> Dict[str, float]:
        """
        Suggest new weights based on discovered correlations.

        Uses correlation strengths to adjust feature weights.
        """
        with self.driver.session() as session:
            result = session.run("""
                MATCH (c:Correlation)
                WHERE c.confidence IN ['High', 'Medium']
                RETURN c.metric_name as metric, c.pearson_r as r, c.strength as strength
            """)

            correlations = [dict(r) for r in result]

        if not correlations:
            return self.DEFAULT_WEIGHTS.copy()

        # Adjust weights based on correlation strength
        weights = self.DEFAULT_WEIGHTS.copy()

        metric_to_weight = {
            'fantasy_ppg': 'production',
            'targets_per_game': 'opportunity',
            'target_share': 'opportunity',
            'snap_share': 'opportunity',
        }

        for corr in correlations:
            metric = corr['metric']
            r = abs(corr['r'])

            if metric in metric_to_weight:
                weight_key = metric_to_weight[metric]
                # Increase weight for strongly correlated metrics
                if r >= 0.5:
                    weights[weight_key] = min(0.40, weights[weight_key] * 1.2)
                elif r >= 0.3:
                    weights[weight_key] = min(0.35, weights[weight_key] * 1.1)

        # Normalize weights to sum to 1
        total = sum(weights.values())
        weights = {k: round(v / total, 3) for k, v in weights.items()}

        logger.info(f"Suggested weights: {weights}")
        return weights


def run_daily_tracking(driver, players_df: pd.DataFrame):
    """
    Run daily tracking routine.

    1. Create snapshots for all players
    2. Discover correlations
    3. Optionally update model config
    """
    logger.info("Starting daily tracking routine...")

    # 1. Create snapshots
    tracker = TemporalTracker(driver)
    snapshot_count = tracker.create_bulk_snapshots(players_df)
    logger.info(f"Created {snapshot_count} snapshots")

    # 2. Discover correlations
    discovery = CorrelationDiscovery(driver)
    correlations = discovery.discover_and_save(lookback_days=60)
    logger.info(f"Discovered {len(correlations)} correlations")

    # 3. Suggest weight updates
    config_mgr = ModelConfigManager(driver)
    suggested_weights = config_mgr.suggest_weights_from_correlations()

    return {
        'snapshots_created': snapshot_count,
        'correlations_discovered': len(correlations),
        'suggested_weights': suggested_weights,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    from neo4j import GraphDatabase

    driver = GraphDatabase.driver("bolt://localhost:7687", auth=None)

    # Test creating a snapshot
    tracker = TemporalTracker(driver)

    test_player = {
        'gsis_id': '00-0033873',  # Example
        'ktc_value': 9998,
        'targets_per_game': 8.5,
        'fantasy_ppg': 22.3,
        'snap_share': 0.92,
        'target_share': 0.28,
    }

    try:
        snapshot_id = tracker.create_snapshot(test_player)
        print(f"Created snapshot: {snapshot_id}")
    except Exception as e:
        print(f"Error: {e}")

    driver.close()
