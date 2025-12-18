#!/usr/bin/env python3
"""
Expanded Training Dataset Builder
=================================

Builds comprehensive ML training datasets by combining:
1. Historical season stats (14K records)
2. Weekly stats aggregations (143K -> season-level features)
3. Snap count trends (249K records)
4. Next Gen Stats / athletic metrics (24K records)
5. Combine results (6.8K records)
6. Draft capital

This expands training data significantly and adds high-value features.
"""

import os
import sys
import logging
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

import pandas as pd
import numpy as np
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ExpandedDatasetBuilder:
    """Builds expanded ML training datasets from all available data sources."""

    def __init__(self):
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER")
        password = os.getenv("NEO4J_PASSWORD")
        auth = (user, password) if user and password else None
        self.driver = GraphDatabase.driver(uri, auth=auth)
        self._player_name_cache = None

    def close(self):
        self.driver.close()

    def _build_player_name_mapping(self) -> Dict[str, str]:
        """Build player_id -> full_name mapping using NGS data as primary source.

        NGS has full player names like 'Drew Brees', while SeasonStats has
        abbreviated names like 'D.Brees'. We prioritize NGS names.
        """
        if self._player_name_cache is not None:
            return self._player_name_cache

        logger.info("Building player name mapping from NGS data...")

        # First get NGS names (full names like "Drew Brees")
        ngs_query = """
        MATCH (n:HistoricalNGS)
        WHERE n.player_id IS NOT NULL AND n.player_name IS NOT NULL
        WITH DISTINCT n.player_id as pid, n.player_name as pname
        RETURN pid, pname
        """

        with self.driver.session() as session:
            result = session.run(ngs_query)
            mapping = {}
            for r in result:
                pid = r['pid']
                pname = r['pname']
                if pid and pname:
                    mapping[pid] = pname

        # For players not in NGS, fall back to SeasonStats (abbreviated names)
        # but only if we don't already have a name
        fallback_query = """
        MATCH (ss:SeasonStats)
        WHERE ss.player_id IS NOT NULL AND ss.player_name IS NOT NULL
        WITH DISTINCT ss.player_id as pid, ss.player_name as pname
        RETURN pid, pname
        """

        with self.driver.session() as session:
            result = session.run(fallback_query)
            fallback_count = 0
            for r in result:
                pid = r['pid']
                pname = r['pname']
                if pid and pname and pid not in mapping:
                    mapping[pid] = pname
                    fallback_count += 1

        logger.info(f"  Built mapping for {len(mapping):,} players ({fallback_count} from SeasonStats fallback)")
        self._player_name_cache = mapping
        return mapping

    # =========================================================================
    # CORE SEASON DATA
    # =========================================================================

    def get_season_pairs(self, positions: List[str], min_games: int = 8,
                         start_year: int = 2015, end_year: int = 2023) -> pd.DataFrame:
        """Get consecutive season pairs for prediction target.

        Uses pre-built player name mapping to get full names.
        """
        # Build name mapping first
        name_mapping = self._build_player_name_mapping()

        query = """
        MATCH (curr:HistoricalSeasonStats)-[:NEXT_SEASON]->(next:HistoricalSeasonStats)
        WHERE curr.position IN $positions
          AND curr.games >= $min_games
          AND next.games >= $min_games
          AND curr.season >= $start_year
          AND curr.season <= $end_year

        // Get career history
        OPTIONAL MATCH (prev:HistoricalSeasonStats)
        WHERE prev.player_id = curr.player_id
          AND prev.season < curr.season
          AND prev.games >= 6

        WITH curr, next, collect(prev) as prior_seasons

        RETURN curr.player_id as player_id,
               curr.position as position,
               curr.season as season,
               curr.team as team,
               curr.games as games,

               // Fantasy stats
               curr.ppg_ppr as ppg_ppr,
               curr.ppg_std as ppg_std,
               curr.total_fantasy_points_ppr as total_fpts,

               // Volume stats
               curr.passing_yards as passing_yards,
               curr.passing_tds as passing_tds,
               curr.interceptions as interceptions,
               curr.rushing_yards as rushing_yards,
               curr.rushing_tds as rushing_tds,
               curr.carries as carries,
               curr.targets as targets,
               curr.receptions as receptions,
               curr.receiving_yards as receiving_yards,
               curr.receiving_tds as receiving_tds,

               // Advanced
               curr.avg_target_share as target_share,
               curr.avg_air_yards_share as air_yards_share,
               curr.avg_wopr as wopr,

               // Career context
               size(prior_seasons) as years_in_league,
               CASE WHEN size(prior_seasons) > 0
                    THEN reduce(s=0.0, p IN prior_seasons | s + p.ppg_ppr) / size(prior_seasons)
                    ELSE 0 END as career_ppg,
               CASE WHEN size(prior_seasons) > 0
                    THEN reduce(mx=0.0, p IN prior_seasons |
                         CASE WHEN p.ppg_ppr > mx THEN p.ppg_ppr ELSE mx END)
                    ELSE 0 END as best_season_ppg,

               // Target
               next.ppg_ppr as next_ppg_ppr,
               next.ppg_std as next_ppg_std,
               next.games as next_games

        ORDER BY curr.season, curr.ppg_ppr DESC
        """

        with self.driver.session() as session:
            result = session.run(query, {
                'positions': positions,
                'min_games': min_games,
                'start_year': start_year,
                'end_year': end_year
            })
            records = [dict(r) for r in result]

        df = pd.DataFrame(records)

        # Apply name mapping
        df['player_name'] = df['player_id'].map(name_mapping)
        names_found = df['player_name'].notna().sum()
        logger.info(f"Base dataset: {len(df):,} season pairs, {names_found:,} with names")
        return df

    # =========================================================================
    # SNAP COUNT FEATURES
    # =========================================================================

    def add_snap_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add snap count trend features from HistoricalSnapCount.

        Note: HistoricalSnapCount uses player_name as the key.
        Since we now have full names from the NGS mapping, we can match directly.
        """
        logger.info("Adding snap count features...")

        # Get player names from our data (now full names via NGS mapping)
        player_names = df['player_name'].dropna().unique().tolist()
        seasons = df['season'].dropna().unique().tolist()

        query = """
        MATCH (s:HistoricalSnapCount)
        WHERE s.player_name IN $player_names
          AND s.season IN $seasons
          AND s.position IN ['QB', 'RB', 'WR', 'TE']
        WITH s.player_name as snap_player_name, s.season as season,
             collect(s) as weeks

        // Calculate snap metrics
        WITH snap_player_name, season, weeks,
             size(weeks) as weeks_played,
             reduce(s=0.0, w IN weeks | s + coalesce(w.offense_pct, 0)) / size(weeks) as avg_snap_pct,
             reduce(s=0, w IN weeks | s + coalesce(w.offense_snaps, 0)) as total_snaps,

             // Trend: compare last 4 weeks to first 4 weeks
             CASE WHEN size(weeks) >= 8
                  THEN (reduce(s=0.0, w IN weeks[-4..] | s + coalesce(w.offense_pct, 0)) / 4) -
                       (reduce(s=0.0, w IN weeks[0..4] | s + coalesce(w.offense_pct, 0)) / 4)
                  ELSE null END as snap_trend,

             // Max snap pct (peak usage)
             reduce(mx=0.0, w IN weeks |
                    CASE WHEN coalesce(w.offense_pct, 0) > mx
                         THEN w.offense_pct ELSE mx END) as max_snap_pct,

             // Consistency (weeks with >50% snaps)
             size([w IN weeks WHERE w.offense_pct >= 0.5]) as high_snap_weeks

        RETURN snap_player_name, season, avg_snap_pct, total_snaps, snap_trend,
               max_snap_pct, high_snap_weeks, weeks_played
        """

        with self.driver.session() as session:
            result = session.run(query, {'player_names': player_names, 'seasons': seasons})
            records = [dict(r) for r in result]

        if records:
            snap_df = pd.DataFrame(records)

            # Direct merge on full player name
            df = df.merge(
                snap_df,
                left_on=['player_name', 'season'],
                right_on=['snap_player_name', 'season'],
                how='left'
            )
            df.drop(columns=['snap_player_name'], errors='ignore', inplace=True)

            matched = df['avg_snap_pct'].notna().sum()
            logger.info(f"  Added snap features for {matched:,} player-seasons")
        else:
            logger.warning("  No snap count data found")
            for col in ['avg_snap_pct', 'total_snaps', 'snap_trend', 'max_snap_pct', 'high_snap_weeks']:
                df[col] = np.nan

        return df

    # =========================================================================
    # NEXT GEN STATS FEATURES
    # =========================================================================

    def add_ngs_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add Next Gen Stats features (2016+).

        Note: NGS metrics are stored as JSON strings, not maps.
        We need to parse them in Python.
        """
        import json
        logger.info("Adding Next Gen Stats features...")

        # Get NGS season totals (week=0), not weekly data
        query = """
        MATCH (n:HistoricalNGS)
        WHERE n.player_id IN $player_ids
          AND n.season IN $seasons
          AND n.week = 0  // Season totals only, not weekly
        RETURN n.player_id as ngs_player_id,
               n.player_name as ngs_name,
               n.season as season,
               n.stat_type as stat_type,
               n.metrics as metrics_json
        """

        player_ids = df['player_id'].dropna().unique().tolist()
        seasons = df['season'].dropna().unique().tolist()

        with self.driver.session() as session:
            result = session.run(query, {'player_ids': player_ids, 'seasons': seasons})
            records = [dict(r) for r in result]

        if not records:
            logger.warning("  No NGS data found")
            return df

        # Parse JSON metrics
        passing_records = []
        rushing_records = []
        receiving_records = []

        for r in records:
            try:
                # Parse metrics JSON string
                if r['metrics_json']:
                    # Handle both string and dict formats
                    metrics = r['metrics_json']
                    if isinstance(metrics, str):
                        metrics = json.loads(metrics.replace("'", '"'))

                    base = {
                        'ngs_player_id': r['ngs_player_id'],
                        'ngs_name': r['ngs_name'],
                        'season': r['season']
                    }

                    if r['stat_type'] == 'passing':
                        passing_records.append({
                            **base,
                            'avg_time_to_throw': metrics.get('avg_time_to_throw'),
                            'avg_completed_air_yards': metrics.get('avg_completed_air_yards'),
                            'avg_intended_air_yards': metrics.get('avg_intended_air_yards'),
                            'cpoe': metrics.get('completion_percentage_above_expectation'),
                            'aggressiveness': metrics.get('aggressiveness'),
                            'ngs_passer_rating': metrics.get('passer_rating')
                        })
                    elif r['stat_type'] == 'rushing':
                        rushing_records.append({
                            **base,
                            'rush_efficiency': metrics.get('efficiency'),
                            'avg_time_to_los': metrics.get('avg_time_to_los'),
                            'ryoe_per_att': metrics.get('rush_yards_over_expected_per_att'),
                            'ngs_avg_rush_yards': metrics.get('avg_rush_yards')
                        })
                    elif r['stat_type'] == 'receiving':
                        receiving_records.append({
                            **base,
                            'avg_cushion': metrics.get('avg_cushion'),
                            'avg_separation': metrics.get('avg_separation'),
                            'recv_avg_intended_air_yards': metrics.get('avg_intended_air_yards'),
                            'ngs_catch_pct': metrics.get('catch_percentage'),
                            'avg_yac': metrics.get('avg_yac'),
                            'yac_above_expected': metrics.get('avg_yac_above_expectation')
                        })
            except (json.JSONDecodeError, TypeError) as e:
                continue  # Skip malformed records

        # Merge by player_id (both have GSIS format)
        if passing_records:
            pass_df = pd.DataFrame(passing_records)
            df = df.merge(pass_df, left_on=['player_id', 'season'],
                         right_on=['ngs_player_id', 'season'], how='left')
            df.drop(columns=['ngs_player_id', 'ngs_name'], errors='ignore', inplace=True)
            matched = df['cpoe'].notna().sum()
            logger.info(f"  Added passing NGS for {matched:,} player-seasons")

        if rushing_records:
            rush_df = pd.DataFrame(rushing_records)
            df = df.merge(rush_df, left_on=['player_id', 'season'],
                         right_on=['ngs_player_id', 'season'], how='left', suffixes=('', '_rush'))
            df.drop(columns=['ngs_player_id', 'ngs_name'], errors='ignore', inplace=True)
            matched = df['rush_efficiency'].notna().sum()
            logger.info(f"  Added rushing NGS for {matched:,} player-seasons")

        if receiving_records:
            recv_df = pd.DataFrame(receiving_records)
            df = df.merge(recv_df, left_on=['player_id', 'season'],
                         right_on=['ngs_player_id', 'season'], how='left', suffixes=('', '_recv'))
            df.drop(columns=['ngs_player_id', 'ngs_name'], errors='ignore', inplace=True)
            matched = df['avg_separation'].notna().sum()
            logger.info(f"  Added receiving NGS for {matched:,} player-seasons")

        return df

    # =========================================================================
    # COMBINE / ATHLETIC FEATURES
    # =========================================================================

    def add_combine_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add NFL Combine athletic measurements."""
        logger.info("Adding combine features...")

        query = """
        MATCH (c:CombineResult)
        WHERE c.position IN ['QB', 'RB', 'WR', 'TE', 'FB']
        RETURN c.player_name as combine_name,
               c.position as combine_position,
               c.season as combine_year,
               c.forty_yard as forty_yard,
               c.vertical_jump as vertical_jump,
               c.broad_jump as broad_jump,
               c.bench_press as bench_press,
               c.shuttle as shuttle,
               c.three_cone as three_cone,
               c.height as height,
               c.weight as weight
        """

        with self.driver.session() as session:
            result = session.run(query)
            records = [dict(r) for r in result]

        if records:
            combine_df = pd.DataFrame(records)

            # Convert height to inches
            def height_to_inches(h):
                if pd.isna(h) or not isinstance(h, str):
                    return np.nan
                try:
                    parts = h.split('-')
                    return int(parts[0]) * 12 + int(parts[1])
                except:
                    return np.nan

            combine_df['height_inches'] = combine_df['height'].apply(height_to_inches)

            # Calculate athletic score
            combine_df['athletic_score'] = (
                (4.5 - combine_df['forty_yard'].fillna(4.5)) * 20 +  # Speed
                combine_df['vertical_jump'].fillna(30) / 2 +         # Explosiveness
                combine_df['broad_jump'].fillna(110) / 10 +          # Power
                combine_df['bench_press'].fillna(15)                  # Strength
            ).fillna(50)

            # Merge by name (combine data is at career level)
            df = df.merge(
                combine_df[['combine_name', 'forty_yard', 'vertical_jump', 'broad_jump',
                           'bench_press', 'shuttle', 'three_cone', 'height_inches',
                           'weight', 'athletic_score']],
                left_on='player_name',
                right_on='combine_name',
                how='left'
            )
            df.drop(columns=['combine_name'], errors='ignore', inplace=True)

            matched = df['forty_yard'].notna().sum()
            logger.info(f"  Matched combine data for {matched:,} records")
        else:
            logger.warning("  No combine data found")

        return df

    # =========================================================================
    # WEEKLY AGGREGATION FEATURES
    # =========================================================================

    def add_weekly_aggregations(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add features aggregated from weekly data."""
        logger.info("Adding weekly aggregation features...")

        query = """
        MATCH (w:HistoricalWeeklyStats)
        WHERE w.player_id IN $player_ids
          AND w.season IN $seasons
          AND w.position IN ['QB', 'RB', 'WR', 'TE']
          AND w.week <= 18  // Regular season only (exclude playoffs)
        WITH w.player_id as player_id, w.season as season,
             collect(w) as weeks

        // Calculate weekly-level metrics
        WITH player_id, season, weeks,
             size(weeks) as weeks_played,

             // Consistency: standard deviation of fantasy points
             reduce(s=0.0, w IN weeks | s + coalesce(w.fantasy_points_ppr, 0)) / size(weeks) as avg_weekly_fpts,

             // Boom weeks (>20 PPR points)
             size([w IN weeks WHERE w.fantasy_points_ppr >= 20]) as boom_weeks,

             // Bust weeks (<5 PPR points)
             size([w IN weeks WHERE w.fantasy_points_ppr < 5]) as bust_weeks,

             // Target consistency
             reduce(s=0.0, w IN weeks | s + coalesce(w.targets, 0)) / size(weeks) as avg_weekly_targets,

             // First half vs second half
             [w IN weeks WHERE w.week <= 9] as first_half,
             [w IN weeks WHERE w.week >= 10] as second_half,

             // Peak week
             reduce(mx=0.0, w IN weeks |
                    CASE WHEN coalesce(w.fantasy_points_ppr, 0) > mx
                         THEN w.fantasy_points_ppr ELSE mx END) as peak_weekly_fpts

        WITH player_id, season, weeks_played, avg_weekly_fpts, boom_weeks, bust_weeks,
             avg_weekly_targets, peak_weekly_fpts,
             CASE WHEN size(first_half) > 0
                  THEN reduce(s=0.0, w IN first_half | s + coalesce(w.fantasy_points_ppr, 0)) / size(first_half)
                  ELSE null END as first_half_ppg,
             CASE WHEN size(second_half) > 0
                  THEN reduce(s=0.0, w IN second_half | s + coalesce(w.fantasy_points_ppr, 0)) / size(second_half)
                  ELSE null END as second_half_ppg

        RETURN player_id, season, weeks_played as weekly_games,
               avg_weekly_fpts, boom_weeks, bust_weeks, avg_weekly_targets,
               peak_weekly_fpts, first_half_ppg, second_half_ppg,
               second_half_ppg - first_half_ppg as ppg_surge,
               toFloat(boom_weeks) / weeks_played as boom_rate,
               toFloat(bust_weeks) / weeks_played as bust_rate
        """

        player_ids = df['player_id'].dropna().unique().tolist()
        seasons = df['season'].dropna().unique().tolist()

        with self.driver.session() as session:
            result = session.run(query, {'player_ids': player_ids, 'seasons': seasons})
            records = [dict(r) for r in result]

        if records:
            weekly_df = pd.DataFrame(records)
            df = df.merge(weekly_df, on=['player_id', 'season'], how='left')
            logger.info(f"  Added weekly aggregations for {len(weekly_df):,} player-seasons")

        return df

    # =========================================================================
    # DRAFT CAPITAL FEATURES
    # =========================================================================

    def add_draft_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add draft capital information."""
        logger.info("Adding draft features...")

        query = """
        MATCH (d:DraftPick)
        WHERE d.position IN ['QB', 'RB', 'WR', 'TE', 'FB']
        RETURN d.player_name as draft_name,
               d.season as draft_year,
               d.round as draft_round,
               d.pick as draft_pick,
               d.team as draft_team
        """

        with self.driver.session() as session:
            result = session.run(query)
            records = [dict(r) for r in result]

        if records:
            draft_df = pd.DataFrame(records)

            # Calculate draft capital score
            draft_df['draft_capital'] = np.where(
                draft_df['draft_round'].notna(),
                100 - (draft_df['draft_round'] - 1) * 12 - draft_df['draft_pick'].fillna(15) / 3,
                50  # UDFA baseline
            )

            df = df.merge(
                draft_df[['draft_name', 'draft_year', 'draft_round', 'draft_pick', 'draft_capital']],
                left_on='player_name',
                right_on='draft_name',
                how='left'
            )
            df.drop(columns=['draft_name'], errors='ignore', inplace=True)

            # Years since draft
            df['years_since_draft'] = df['season'] - df['draft_year']

            logger.info(f"  Matched draft data for {df['draft_round'].notna().sum():,} records")

        return df

    # =========================================================================
    # TEMPORAL MOMENTUM FEATURES (KTC VALUE TRENDS)
    # =========================================================================

    def add_ktc_momentum_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add KTC dynasty value momentum features from KTCSnapshot history.

        Calculates:
        - 7-day, 30-day, and 90-day value changes
        - Trend direction classification
        - Value volatility metrics

        Expected R² gain: +0.01-0.02
        """
        logger.info("Adding KTC momentum features...")

        # Get player names for the query
        player_names = df['player_name'].dropna().unique().tolist()

        if not player_names:
            logger.warning("  No player names available for KTC momentum lookup")
            return df

        # Query KTCSnapshot data for value trends
        query = """
        MATCH (s:KTCSnapshot)
        WHERE s.player_name IN $player_names
        WITH s.player_name as name, s.snapshot_date as date, s.value as value
        ORDER BY date DESC
        WITH name, collect({date: date, value: value})[0..90] as snapshots

        // Calculate momentum metrics
        WITH name, snapshots,
             CASE WHEN size(snapshots) > 0 THEN snapshots[0].value ELSE null END as current_value,
             CASE WHEN size(snapshots) >= 7 THEN snapshots[6].value ELSE null END as value_7d_ago,
             CASE WHEN size(snapshots) >= 30 THEN snapshots[29].value ELSE null END as value_30d_ago,
             CASE WHEN size(snapshots) >= 60 THEN snapshots[59].value ELSE null END as value_60d_ago

        RETURN name,
               current_value,
               current_value - value_7d_ago as ktc_7d_delta,
               current_value - value_30d_ago as ktc_30d_delta,
               current_value - value_60d_ago as ktc_60d_delta,
               CASE WHEN value_7d_ago > 0
                    THEN (current_value - value_7d_ago) / value_7d_ago * 100
                    ELSE null END as ktc_7d_pct_change,
               CASE WHEN value_30d_ago > 0
                    THEN (current_value - value_30d_ago) / value_30d_ago * 100
                    ELSE null END as ktc_30d_pct_change,
               size(snapshots) as ktc_data_points
        """

        with self.driver.session() as session:
            result = session.run(query, {'player_names': player_names})
            records = [dict(r) for r in result]

        if records:
            ktc_df = pd.DataFrame(records)

            # Calculate trend direction
            ktc_df['ktc_trend_direction'] = ktc_df['ktc_30d_delta'].apply(
                lambda x: 'rising' if pd.notna(x) and x > 50 else
                          ('falling' if pd.notna(x) and x < -50 else 'stable')
            )

            # Encode trend as numeric
            trend_map = {'rising': 1, 'stable': 0, 'falling': -1}
            ktc_df['ktc_trend_numeric'] = ktc_df['ktc_trend_direction'].map(trend_map)

            # Merge with main dataframe
            df = df.merge(
                ktc_df[['name', 'ktc_7d_delta', 'ktc_30d_delta', 'ktc_60d_delta',
                       'ktc_7d_pct_change', 'ktc_30d_pct_change',
                       'ktc_trend_numeric', 'ktc_data_points']],
                left_on='player_name',
                right_on='name',
                how='left'
            )
            df.drop(columns=['name'], errors='ignore', inplace=True)

            matched = df['ktc_30d_delta'].notna().sum()
            logger.info(f"  Added KTC momentum for {matched:,} players")
        else:
            logger.warning("  No KTC snapshot data found")
            # Add empty columns
            for col in ['ktc_7d_delta', 'ktc_30d_delta', 'ktc_60d_delta',
                       'ktc_7d_pct_change', 'ktc_30d_pct_change',
                       'ktc_trend_numeric', 'ktc_data_points']:
                df[col] = np.nan

        return df

    def add_injury_recency_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add injury recency features from InjuryReport nodes.

        Calculates:
        - Days since last injury listing
        - Total injury reports in current season
        - Injury frequency (reports per season)
        """
        logger.info("Adding injury recency features...")

        player_ids = df['player_id'].dropna().unique().tolist()
        seasons = df['season'].dropna().unique().tolist()

        if not player_ids:
            logger.warning("  No player IDs for injury lookup")
            return df

        query = """
        MATCH (ir:InjuryReport)
        WHERE ir.player_id IN $player_ids
          AND ir.season IN $seasons
        WITH ir.player_id as pid, ir.season as season,
             collect(ir) as reports

        // Calculate injury metrics
        RETURN pid, season,
               size(reports) as injury_reports_this_season,
               size([r IN reports WHERE r.status IN ['Out', 'IR', 'PUP']]) as severe_injury_count,
               size([r IN reports WHERE r.body_part CONTAINS 'knee' OR r.body_part CONTAINS 'Knee']) as knee_injury_count,
               size([r IN reports WHERE r.body_part CONTAINS 'ankle' OR r.body_part CONTAINS 'Ankle']) as ankle_injury_count,
               size([r IN reports WHERE r.body_part CONTAINS 'hamstring' OR r.body_part CONTAINS 'Hamstring']) as soft_tissue_count
        """

        with self.driver.session() as session:
            result = session.run(query, {'player_ids': player_ids, 'seasons': seasons})
            records = [dict(r) for r in result]

        if records:
            injury_df = pd.DataFrame(records)

            df = df.merge(
                injury_df,
                left_on=['player_id', 'season'],
                right_on=['pid', 'season'],
                how='left'
            )
            df.drop(columns=['pid'], errors='ignore', inplace=True)

            # Fill NaN with 0 (no injury reports = healthy)
            injury_cols = ['injury_reports_this_season', 'severe_injury_count',
                          'knee_injury_count', 'ankle_injury_count', 'soft_tissue_count']
            for col in injury_cols:
                if col in df.columns:
                    df[col] = df[col].fillna(0)

            matched = (df['injury_reports_this_season'] > 0).sum()
            logger.info(f"  Added injury features for {matched:,} player-seasons with injury history")
        else:
            logger.warning("  No injury report data found")
            for col in ['injury_reports_this_season', 'severe_injury_count',
                       'knee_injury_count', 'ankle_injury_count', 'soft_tissue_count']:
                df[col] = 0

        return df

    def add_team_strength_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add team offensive strength features from Game Elo data.

        Calculates:
        - Team average Elo rating for the season
        - Offensive ranking metrics
        - Pace/tempo indicators
        """
        logger.info("Adding team strength features...")

        teams = df['team'].dropna().unique().tolist()
        seasons = df['season'].dropna().unique().tolist()

        if not teams:
            logger.warning("  No team data available")
            return df

        query = """
        MATCH (g:Game)
        WHERE g.season IN $seasons
        WITH g.home_team as team, g.season as season,
             collect({
                 elo: g.home_elo_pre,
                 pts_scored: g.home_score,
                 pts_allowed: g.away_score,
                 total: g.total_points
             }) as home_games

        MATCH (g2:Game)
        WHERE g2.away_team = team AND g2.season = season
        WITH team, season, home_games,
             collect({
                 elo: g2.away_elo_pre,
                 pts_scored: g2.away_score,
                 pts_allowed: g2.home_score,
                 total: g2.total_points
             }) as away_games

        WITH team, season, home_games + away_games as all_games
        WHERE size(all_games) >= 8

        UNWIND all_games as g
        WITH team, season,
             avg(g.elo) as team_avg_elo,
             avg(g.pts_scored) as team_ppg,
             avg(g.pts_allowed) as team_ppg_allowed,
             avg(g.total) as avg_game_total,
             count(g) as games_counted

        RETURN team, season, team_avg_elo, team_ppg, team_ppg_allowed,
               avg_game_total,
               team_ppg - team_ppg_allowed as team_point_diff
        """

        with self.driver.session() as session:
            result = session.run(query, {'teams': teams, 'seasons': seasons})
            records = [dict(r) for r in result]

        if records:
            team_df = pd.DataFrame(records)

            # Calculate offensive rank within season
            team_df['team_off_rank'] = team_df.groupby('season')['team_ppg'].rank(
                ascending=False, method='min'
            )

            # Normalize Elo (1500 is average)
            team_df['team_elo_above_avg'] = team_df['team_avg_elo'] - 1500

            df = df.merge(
                team_df[['team', 'season', 'team_avg_elo', 'team_ppg', 'team_ppg_allowed',
                        'avg_game_total', 'team_point_diff', 'team_off_rank', 'team_elo_above_avg']],
                on=['team', 'season'],
                how='left'
            )

            matched = df['team_avg_elo'].notna().sum()
            logger.info(f"  Added team strength features for {matched:,} player-seasons")
        else:
            logger.warning("  No game/Elo data found")
            for col in ['team_avg_elo', 'team_ppg', 'team_ppg_allowed', 'avg_game_total',
                       'team_point_diff', 'team_off_rank', 'team_elo_above_avg']:
                df[col] = np.nan

        return df

    # =========================================================================
    # PLAY-BY-PLAY AGGREGATE FEATURES (NEW - December 2024)
    # =========================================================================

    def add_pbp_aggregate_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add Play-by-Play aggregate features from PlayByPlayAggregates nodes.

        Includes:
        - EPA per target/carry (efficiency metrics)
        - aDOT (average depth of target)
        - WOPR (Weighted Opportunity Rating)
        - Red zone and goal line usage
        - Target share metrics

        Expected R² gain: +0.01-0.02
        """
        logger.info("Adding PBP aggregate features...")

        player_ids = df['player_id'].dropna().unique().tolist()
        seasons = df['season'].dropna().unique().tolist()

        if not player_ids:
            logger.warning("  No player IDs for PBP lookup")
            return df

        # Get season totals (week=0) from PlayByPlayAggregates
        query = """
        MATCH (p:PlayByPlayAggregates)
        WHERE p.player_id IN $player_ids
          AND p.season IN $seasons
          AND p.week = 0  // Season totals only
        RETURN p.player_id as player_id,
               p.season as season,
               p.stat_type as stat_type,

               // Receiving metrics
               p.adot as adot,
               p.wopr as wopr,
               p.target_share as pbp_target_share,
               p.air_yards_share as pbp_air_yards_share,
               p.epa_per_target as epa_per_target,
               p.catch_rate as pbp_catch_rate,

               // Rushing metrics
               p.epa_per_carry as epa_per_carry,
               p.ypc as pbp_ypc,

               // Red zone / goal line
               p.rz_targets as rz_targets,
               p.rz_carries as rz_carries,
               p.gl_carries as gl_carries,
               p.rz_td_rate as rz_td_rate,
               p.gl_td_rate as gl_td_rate,

               // Situational
               p.third_down_targets as third_down_targets,
               p.neutral_script_targets as neutral_script_targets,
               p.neutral_script_carries as neutral_script_carries
        """

        with self.driver.session() as session:
            result = session.run(query, {'player_ids': player_ids, 'seasons': seasons})
            records = [dict(r) for r in result]

        if records:
            pbp_df = pd.DataFrame(records)

            # Separate receiving and rushing stats
            recv_cols = ['adot', 'wopr', 'pbp_target_share', 'pbp_air_yards_share',
                        'epa_per_target', 'pbp_catch_rate', 'rz_targets',
                        'third_down_targets', 'neutral_script_targets']
            rush_cols = ['epa_per_carry', 'pbp_ypc', 'rz_carries', 'gl_carries',
                        'rz_td_rate', 'gl_td_rate', 'neutral_script_carries']

            # Get receiving stats
            recv_df = pbp_df[pbp_df['stat_type'] == 'receiving'][
                ['player_id', 'season'] + [c for c in recv_cols if c in pbp_df.columns]
            ].drop_duplicates(['player_id', 'season'])

            # Get rushing stats
            rush_df = pbp_df[pbp_df['stat_type'] == 'rushing'][
                ['player_id', 'season'] + [c for c in rush_cols if c in pbp_df.columns]
            ].drop_duplicates(['player_id', 'season'])

            # Merge receiving
            if not recv_df.empty:
                df = df.merge(recv_df, on=['player_id', 'season'], how='left')
                matched = df['epa_per_target'].notna().sum()
                logger.info(f"  Added receiving PBP features for {matched:,} player-seasons")

            # Merge rushing
            if not rush_df.empty:
                df = df.merge(rush_df, on=['player_id', 'season'], how='left')
                matched = df['epa_per_carry'].notna().sum()
                logger.info(f"  Added rushing PBP features for {matched:,} player-seasons")

            # Calculate combined opportunity metrics
            if 'rz_targets' in df.columns and 'rz_carries' in df.columns:
                df['total_rz_opps'] = df['rz_targets'].fillna(0) + df['rz_carries'].fillna(0)
                df['total_gl_opps'] = df['gl_carries'].fillna(0)

        else:
            logger.warning("  No PBP aggregate data found")
            # Add empty columns
            for col in ['adot', 'wopr', 'epa_per_target', 'epa_per_carry',
                       'rz_targets', 'rz_carries', 'gl_carries',
                       'rz_td_rate', 'gl_td_rate', 'total_rz_opps']:
                df[col] = np.nan

        return df

    # =========================================================================
    # DEPTH CHART / ROLE FEATURES (NEW - December 2024)
    # =========================================================================

    def add_depth_chart_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add depth chart and player role features from PlayerRoleProfile nodes.

        Includes:
        - Starter rate (0-1 scale)
        - WR alignment (slot vs outside)
        - Role classification (established starter, committee, etc.)

        Expected R² gain: +0.01
        """
        logger.info("Adding depth chart/role features...")

        player_ids = df['player_id'].dropna().unique().tolist()

        if not player_ids:
            logger.warning("  No player IDs for role lookup")
            return df

        query = """
        MATCH (r:PlayerRoleProfile)
        WHERE r.player_id IN $player_ids
        RETURN r.player_id as player_id,
               r.starter_rate as starter_rate,
               r.starter_weeks as starter_weeks,
               r.backup_weeks as backup_weeks,
               r.total_depth_chart_weeks as total_depth_chart_weeks,

               // WR alignment
               r.slot_weeks as slot_weeks,
               r.outside_weeks as outside_weeks,
               r.alignment as wr_alignment,

               // Classification
               r.primary_role as primary_role
        """

        with self.driver.session() as session:
            result = session.run(query, {'player_ids': player_ids})
            records = [dict(r) for r in result]

        if records:
            role_df = pd.DataFrame(records)

            # Calculate slot rate for WRs
            role_df['slot_rate'] = role_df.apply(
                lambda r: r['slot_weeks'] / (r['slot_weeks'] + r['outside_weeks'])
                if pd.notna(r['slot_weeks']) and (r['slot_weeks'] + r['outside_weeks']) > 0
                else np.nan,
                axis=1
            )

            # Encode role as numeric
            role_map = {
                'established_starter': 4,
                'starter': 3,
                'starter_backup_mix': 2,
                'backup': 1,
                'depth': 0
            }
            role_df['role_numeric'] = role_df['primary_role'].map(role_map).fillna(1)

            # Encode alignment
            align_map = {'slot_primary': 1, 'outside_primary': 0, 'versatile': 0.5}
            role_df['alignment_numeric'] = role_df['wr_alignment'].map(align_map)

            # Merge with main dataframe
            df = df.merge(
                role_df[['player_id', 'starter_rate', 'slot_rate', 'role_numeric',
                        'alignment_numeric', 'total_depth_chart_weeks']],
                on='player_id',
                how='left'
            )

            matched = df['starter_rate'].notna().sum()
            logger.info(f"  Added role features for {matched:,} players")

            # Fill defaults
            df['starter_rate'] = df['starter_rate'].fillna(0.5)
            df['role_numeric'] = df['role_numeric'].fillna(2)  # Default to starter_backup_mix
        else:
            logger.warning("  No PlayerRoleProfile data found")
            df['starter_rate'] = 0.5
            df['slot_rate'] = np.nan
            df['role_numeric'] = 2
            df['alignment_numeric'] = np.nan
            df['total_depth_chart_weeks'] = np.nan

        return df

    # =========================================================================
    # GAME WEATHER FEATURES (NEW - December 2024)
    # =========================================================================

    def add_weather_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add weather-related features from GameWeather nodes.

        Includes:
        - Average game temperature for season
        - Dome game percentage
        - Cold/windy game counts
        - Weather impact score

        Expected R² gain: +0.005-0.01
        """
        logger.info("Adding weather features...")

        teams = df['team'].dropna().unique().tolist()
        seasons = df['season'].dropna().unique().tolist()

        if not teams:
            logger.warning("  No team data for weather lookup")
            return df

        query = """
        MATCH (w:GameWeather)
        WHERE w.home_team IN $teams AND w.season IN $seasons
        WITH w.home_team as team, w.season as season,
             collect(w) as games

        // Calculate seasonal weather metrics
        WITH team, season,
             size(games) as home_games,
             size([g IN games WHERE g.is_dome = 1]) as dome_games,
             size([g IN games WHERE g.is_cold = 1]) as cold_games,
             size([g IN games WHERE g.is_windy = 1]) as windy_games,
             size([g IN games WHERE g.has_precipitation = 1]) as precip_games,
             reduce(t=0.0, g IN games | t + coalesce(g.temperature, 60)) / size(games) as avg_temp,
             reduce(w=0.0, g IN games | w + coalesce(g.wind_speed, 5)) / size(games) as avg_wind

        RETURN team, season, home_games,
               toFloat(dome_games) / home_games as dome_game_pct,
               toFloat(cold_games) / home_games as cold_game_pct,
               toFloat(windy_games) / home_games as windy_game_pct,
               toFloat(precip_games) / home_games as precip_game_pct,
               avg_temp, avg_wind
        """

        with self.driver.session() as session:
            result = session.run(query, {'teams': teams, 'seasons': seasons})
            records = [dict(r) for r in result]

        if records:
            weather_df = pd.DataFrame(records)

            # Calculate weather favorability score (higher = better for passing/fantasy)
            weather_df['weather_favorability'] = (
                weather_df['dome_game_pct'].fillna(0) * 30 +  # Domes are favorable
                (1 - weather_df['cold_game_pct'].fillna(0)) * 25 +  # Cold is bad
                (1 - weather_df['windy_game_pct'].fillna(0)) * 25 +  # Wind is bad
                (1 - weather_df['precip_game_pct'].fillna(0)) * 20   # Precip is bad
            )

            df = df.merge(
                weather_df[['team', 'season', 'dome_game_pct', 'cold_game_pct',
                           'windy_game_pct', 'avg_temp', 'avg_wind', 'weather_favorability']],
                on=['team', 'season'],
                how='left'
            )

            matched = df['dome_game_pct'].notna().sum()
            logger.info(f"  Added weather features for {matched:,} player-seasons")
        else:
            logger.warning("  No GameWeather data found")
            for col in ['dome_game_pct', 'cold_game_pct', 'windy_game_pct',
                       'avg_temp', 'avg_wind', 'weather_favorability']:
                df[col] = np.nan

        return df

    # =========================================================================
    # PLAYER INJURY PROFILE FEATURES (NEW - December 2024)
    # =========================================================================

    def add_injury_profile_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add player injury profile features from PlayerInjuryProfile nodes.

        Includes:
        - Overall injury risk score
        - Soft tissue / structural risk
        - Historical injury counts by type
        - Games listed out

        Expected R² gain: +0.01
        """
        logger.info("Adding injury profile features...")

        player_ids = df['player_id'].dropna().unique().tolist()

        if not player_ids:
            logger.warning("  No player IDs for injury profile lookup")
            return df

        query = """
        MATCH (ip:PlayerInjuryProfile)
        WHERE ip.player_id IN $player_ids
        RETURN ip.player_id as player_id,

               // Injury counts
               ip.soft_tissue_leg_count as soft_tissue_leg_count,
               ip.soft_tissue_upper_count as soft_tissue_upper_count,
               ip.knee_injury_count as knee_injury_count,
               ip.ankle_foot_count as ankle_foot_count,
               ip.concussion_count as concussion_count,
               ip.back_neck_count as back_neck_count,

               // Severity
               ip.games_listed_out as games_listed_out,
               ip.games_questionable as games_questionable,
               ip.total_injury_reports as total_injury_reports,

               // Risk scores (low/medium/high)
               ip.soft_tissue_risk as soft_tissue_risk,
               ip.structural_risk as structural_risk,
               ip.concussion_risk as concussion_risk,
               ip.overall_injury_risk as overall_injury_risk
        """

        with self.driver.session() as session:
            result = session.run(query, {'player_ids': player_ids})
            records = [dict(r) for r in result]

        if records:
            profile_df = pd.DataFrame(records)

            # Encode risk levels as numeric
            risk_map = {'low': 0, 'medium': 1, 'high': 2}
            for risk_col in ['soft_tissue_risk', 'structural_risk',
                            'concussion_risk', 'overall_injury_risk']:
                if risk_col in profile_df.columns:
                    profile_df[f'{risk_col}_numeric'] = profile_df[risk_col].map(risk_map).fillna(0)

            # Calculate injury burden score
            profile_df['injury_burden_score'] = (
                profile_df['soft_tissue_leg_count'].fillna(0) * 2 +  # Most impactful for fantasy
                profile_df['knee_injury_count'].fillna(0) * 3 +
                profile_df['ankle_foot_count'].fillna(0) * 2 +
                profile_df['concussion_count'].fillna(0) * 2 +
                profile_df['games_listed_out'].fillna(0) * 0.5
            )

            # Merge with main dataframe
            merge_cols = ['player_id', 'soft_tissue_leg_count', 'knee_injury_count',
                         'concussion_count', 'games_listed_out', 'total_injury_reports',
                         'overall_injury_risk_numeric', 'soft_tissue_risk_numeric',
                         'injury_burden_score']
            available_cols = ['player_id'] + [c for c in merge_cols[1:] if c in profile_df.columns]

            df = df.merge(profile_df[available_cols], on='player_id', how='left')

            # Fill defaults (no injury history = low risk)
            df['injury_burden_score'] = df['injury_burden_score'].fillna(0)
            df['overall_injury_risk_numeric'] = df['overall_injury_risk_numeric'].fillna(0)
            df['total_injury_reports'] = df['total_injury_reports'].fillna(0)

            matched = (df['total_injury_reports'] > 0).sum()
            logger.info(f"  Added injury profile for {matched:,} players with history")
        else:
            logger.warning("  No PlayerInjuryProfile data found")
            df['injury_burden_score'] = 0
            df['overall_injury_risk_numeric'] = 0
            df['soft_tissue_risk_numeric'] = 0
            df['total_injury_reports'] = 0

        return df

    # =========================================================================
    # KTC TREND FEATURES (NEW - December 2024)
    # =========================================================================

    def add_ktc_trend_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add KTC trend features from pre-computed KTCTrend nodes.

        These are more detailed than the momentum features calculated from
        raw KTCSnapshot data. Includes:
        - Trend slope and direction
        - Momentum percentage
        - Days since peak/trough
        - Value signal classification

        Expected R² gain: +0.01
        """
        logger.info("Adding KTC trend features...")

        player_names = df['player_name'].dropna().unique().tolist()

        if not player_names:
            logger.warning("  No player names for KTC trend lookup")
            return df

        query = """
        MATCH (kt:KTCTrend)
        WHERE kt.player_name IN $player_names
        RETURN kt.player_name as player_name,
               kt.current_ktc as current_ktc_value,

               // Value changes
               kt.change_7d as ktc_change_7d,
               kt.change_30d as ktc_change_30d,
               kt.change_7d_pct as ktc_change_7d_pct,
               kt.change_30d_pct as ktc_change_30d_pct,

               // Volatility
               kt.ktc_std as ktc_volatility,
               kt.ktc_range as ktc_range,

               // Trend analysis
               kt.trend_slope as trend_slope,
               kt.trend_direction as trend_direction,
               kt.momentum as ktc_momentum,
               kt.momentum_pct as ktc_momentum_pct,

               // Peak/trough
               kt.days_since_peak as days_since_peak,
               kt.days_since_trough as days_since_trough,
               kt.pct_off_peak as pct_off_peak,
               kt.pct_above_trough as pct_above_trough,

               // Value signal
               kt.value_signal as value_signal,
               kt.days_tracked as ktc_days_tracked
        """

        with self.driver.session() as session:
            result = session.run(query, {'player_names': player_names})
            records = [dict(r) for r in result]

        if records:
            trend_df = pd.DataFrame(records)

            # Encode trend direction
            trend_map = {'rising': 1, 'stable': 0, 'falling': -1}
            trend_df['trend_direction_numeric'] = trend_df['trend_direction'].map(trend_map).fillna(0)

            # Encode value signal (more granular)
            signal_map = {
                'strong_buy': 2, 'buy': 1, 'hold': 0, 'sell': -1, 'strong_sell': -2
            }
            trend_df['value_signal_numeric'] = trend_df['value_signal'].map(signal_map).fillna(0)

            # Calculate "buy-the-dip" opportunity score
            trend_df['dip_opportunity'] = trend_df.apply(
                lambda r: min(100, (r['pct_off_peak'] or 0) * 2 + (r['days_since_trough'] or 30) / 3)
                if pd.notna(r['pct_off_peak']) else 50,
                axis=1
            )

            # Merge with main dataframe
            df = df.merge(
                trend_df[['player_name', 'current_ktc_value', 'ktc_change_7d', 'ktc_change_30d',
                         'ktc_volatility', 'trend_slope', 'trend_direction_numeric',
                         'ktc_momentum', 'days_since_peak', 'pct_off_peak',
                         'value_signal_numeric', 'dip_opportunity', 'ktc_days_tracked']],
                on='player_name',
                how='left'
            )

            matched = df['current_ktc_value'].notna().sum()
            logger.info(f"  Added KTC trend features for {matched:,} players")
        else:
            logger.warning("  No KTCTrend data found")
            for col in ['current_ktc_value', 'ktc_change_7d', 'ktc_change_30d',
                       'ktc_volatility', 'trend_slope', 'trend_direction_numeric',
                       'ktc_momentum', 'days_since_peak', 'pct_off_peak',
                       'value_signal_numeric', 'dip_opportunity']:
                df[col] = np.nan

        return df

    # =========================================================================
    # FEATURE ENGINEERING
    # =========================================================================

    def engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add engineered features."""
        logger.info("Engineering features...")

        df = df.copy()

        # Per-game rates
        df['targets_per_game'] = df['targets'] / df['games'].replace(0, np.nan)
        df['receptions_per_game'] = df['receptions'] / df['games'].replace(0, np.nan)
        df['rec_yards_per_game'] = df['receiving_yards'] / df['games'].replace(0, np.nan)
        df['carries_per_game'] = df['carries'] / df['games'].replace(0, np.nan)
        df['rush_yards_per_game'] = df['rushing_yards'] / df['games'].replace(0, np.nan)

        # Efficiency metrics
        df['catch_rate'] = df['receptions'] / df['targets'].replace(0, np.nan)
        df['yards_per_catch'] = df['receiving_yards'] / df['receptions'].replace(0, np.nan)
        df['yards_per_carry'] = df['rushing_yards'] / df['carries'].replace(0, np.nan)
        df['yards_per_target'] = df['receiving_yards'] / df['targets'].replace(0, np.nan)

        # Career comparisons
        df['ppg_vs_career'] = df['ppg_ppr'] - df['career_ppg']
        df['ppg_vs_best'] = df['ppg_ppr'] - df['best_season_ppg']

        # TD rates
        df['rec_td_rate'] = df['receiving_tds'] / df['targets'].replace(0, np.nan)
        df['rush_td_rate'] = df['rushing_tds'] / df['carries'].replace(0, np.nan)

        # Age estimation
        df['estimated_age'] = 22 + df['years_in_league'].fillna(0)

        # Position-specific age curves
        POSITION_PEAKS = {
            'QB': {'peak': 30, 'cliff': 38},
            'RB': {'peak': 25, 'cliff': 28},
            'WR': {'peak': 27, 'cliff': 31},
            'TE': {'peak': 28, 'cliff': 32}
        }

        def calc_age_score(row):
            pos = row.get('position')
            age = row.get('estimated_age', 25)
            if pos not in POSITION_PEAKS:
                return 70
            peak = POSITION_PEAKS[pos]['peak']
            cliff = POSITION_PEAKS[pos]['cliff']
            if age <= peak:
                return 100 - (peak - age) * 2
            elif age <= cliff:
                return 90 - (age - peak) * 5
            else:
                return max(0, 70 - (age - cliff) * 15)

        df['age_score'] = df.apply(calc_age_score, axis=1)

        # Opportunity score (combined targets + carries)
        df['opportunities'] = df['targets'].fillna(0) + df['carries'].fillna(0)
        df['opps_per_game'] = df['opportunities'] / df['games'].replace(0, np.nan)

        # Consistency score (inverse of bust rate)
        if 'bust_rate' in df.columns:
            df['consistency_score'] = 100 * (1 - df['bust_rate'].fillna(0.3))

        logger.info(f"  Engineered {len(df.columns)} total features")
        return df

    # =========================================================================
    # MAIN BUILD METHOD
    # =========================================================================

    def build_expanded_dataset(
        self,
        positions: List[str] = ['QB', 'RB', 'WR', 'TE'],
        min_games: int = 6,
        start_year: int = 2016,  # Limited by NGS data
        end_year: int = 2023
    ) -> pd.DataFrame:
        """Build the full expanded dataset."""
        logger.info("="*60)
        logger.info("BUILDING EXPANDED TRAINING DATASET")
        logger.info("="*60)

        # Step 1: Get base season pairs
        df = self.get_season_pairs(positions, min_games, start_year, end_year)

        # Step 2: Add snap count features
        df = self.add_snap_features(df)

        # Step 3: Add Next Gen Stats
        df = self.add_ngs_features(df)

        # Step 4: Add combine/athletic features
        df = self.add_combine_features(df)

        # Step 5: Add weekly aggregations
        df = self.add_weekly_aggregations(df)

        # Step 6: Add draft features
        df = self.add_draft_features(df)

        # Step 7: Add temporal momentum features (NEW for R² improvement)
        df = self.add_ktc_momentum_features(df)

        # Step 8: Add injury recency features
        df = self.add_injury_recency_features(df)

        # Step 9: Add team strength features
        df = self.add_team_strength_features(df)

        # Step 10: Add PBP aggregate features (EPA, aDOT, WOPR, red zone)
        df = self.add_pbp_aggregate_features(df)

        # Step 11: Add depth chart/role features (starter rate, alignment)
        df = self.add_depth_chart_features(df)

        # Step 12: Add weather features (dome %, cold game %)
        df = self.add_weather_features(df)

        # Step 13: Add injury profile features (risk scores, burden)
        df = self.add_injury_profile_features(df)

        # Step 14: Add KTC trend features (momentum, volatility, signals)
        df = self.add_ktc_trend_features(df)

        # Step 15: Engineer features
        df = self.engineer_features(df)

        logger.info("="*60)
        logger.info(f"FINAL DATASET: {len(df):,} rows, {len(df.columns)} columns")
        logger.info("="*60)

        return df


def main():
    """Build and export expanded dataset."""
    builder = ExpandedDatasetBuilder()

    try:
        # Build dataset
        df = builder.build_expanded_dataset(
            positions=['QB', 'RB', 'WR', 'TE'],
            min_games=6,
            start_year=2016,
            end_year=2023
        )

        # Export
        output_dir = Path('data/ml_training')
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / 'expanded_season_projection.parquet'
        df.to_parquet(output_path, index=False)
        logger.info(f"Exported to {output_path}")

        # Summary statistics
        print("\n" + "="*60)
        print("DATASET SUMMARY")
        print("="*60)
        print(f"Total samples: {len(df):,}")
        print(f"Total features: {len(df.columns)}")
        print(f"\nPosition breakdown:")
        print(df['position'].value_counts().to_string())
        print(f"\nYear range: {df['season'].min()} - {df['season'].max()}")
        print(f"\nTarget (next_ppg_ppr) stats:")
        print(f"  Mean: {df['next_ppg_ppr'].mean():.2f}")
        print(f"  Std:  {df['next_ppg_ppr'].std():.2f}")

        # Feature coverage
        print("\nFeature coverage (% non-null):")
        key_features = [
            # Original features
            'avg_snap_pct', 'cpoe', 'avg_separation', 'forty_yard',
            'boom_rate', 'draft_capital', 'athletic_score',
            'ktc_30d_delta', 'ktc_trend_numeric', 'team_avg_elo',
            'injury_reports_this_season', 'team_off_rank',
            # New features (December 2024)
            'epa_per_target', 'epa_per_carry', 'adot', 'wopr',  # PBP
            'total_rz_opps', 'rz_td_rate', 'gl_td_rate',  # Red zone
            'starter_rate', 'slot_rate', 'role_numeric',  # Depth chart
            'dome_game_pct', 'weather_favorability',  # Weather
            'injury_burden_score', 'overall_injury_risk_numeric',  # Injury profile
            'current_ktc_value', 'trend_slope', 'value_signal_numeric',  # KTC trend
        ]
        for feat in key_features:
            if feat in df.columns:
                coverage = df[feat].notna().mean() * 100
                print(f"  {feat:35}: {coverage:5.1f}%")

    finally:
        builder.close()


if __name__ == '__main__':
    main()
