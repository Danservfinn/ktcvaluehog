"""
ML Training Dataset Builder
============================
Builds training datasets from historical NFL data for various ML models.

Supported Models:
1. Season-over-Season Fantasy Projection
2. Weekly Fantasy Prediction
3. Breakout Probability (250%+ production increase)
4. KTC Value Movement Classifier

Feature Tiers:
- Tier 1 (1999-2024): Core stats (all years)
- Tier 2 (2015-2024): Snap counts
- Tier 3 (2016-2024): Next Gen Stats
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class TrainingDatasetBuilder:
    """Build ML training datasets from historical NFL data in Neo4j."""

    def __init__(self, driver):
        self.driver = driver

    # =========================================================================
    # SEASON-OVER-SEASON DATASET (Primary Model)
    # =========================================================================

    def build_season_projection_dataset(
        self,
        positions: List[str] = ['QB', 'RB', 'WR', 'TE'],
        min_games: int = 8,
        start_year: int = 1999,
        end_year: int = 2023,  # Need N+1 year for target
        include_combine: bool = True,
        include_draft: bool = True,
        include_snaps: bool = True,
        include_team_shares: bool = True,
        include_age_curves: bool = True,
        include_surge: bool = True
    ) -> pd.DataFrame:
        """
        Build season-over-season projection training dataset.

        Features (Year N):
        - Season stats: games, fantasy points, ppg, position stats
        - Career context: years_in_league, career_ppg, best_season_ppg
        - Recent trend: year_over_year_change
        - Age proxy: draft year distance

        Target (Year N+1):
        - next_ppg_ppr: PPR points per game
        - next_total_fpts: Total fantasy points
        """
        logger.info(f"Building season projection dataset for {positions}")
        logger.info(f"Years: {start_year}-{end_year}, min games: {min_games}")

        # Main season pair query
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
          AND prev.games >= 8

        WITH curr, next, collect(prev) as prior_seasons

        // Calculate career stats
        WITH curr, next,
             size(prior_seasons) as years_prior,
             CASE WHEN size(prior_seasons) > 0
                  THEN reduce(s=0.0, p IN prior_seasons | s + p.ppg_ppr) / size(prior_seasons)
                  ELSE 0 END as career_ppg_prior,
             CASE WHEN size(prior_seasons) > 0
                  THEN reduce(mx=0.0, p IN prior_seasons | CASE WHEN p.ppg_ppr > mx THEN p.ppg_ppr ELSE mx END)
                  ELSE 0 END as best_prior_ppg

        RETURN curr.player_id as player_id,
               curr.player_name as player_name,
               curr.position as position,
               curr.season as season,
               curr.team as team,
               curr.games as games,

               // Fantasy stats
               curr.ppg_ppr as ppg_ppr,
               curr.ppg_std as ppg_std,
               curr.total_fantasy_points_ppr as total_fpts,

               // Passing
               curr.passing_yards as passing_yards,
               curr.passing_tds as passing_tds,
               curr.interceptions as interceptions,

               // Rushing
               curr.rushing_yards as rushing_yards,
               curr.rushing_tds as rushing_tds,
               curr.carries as carries,

               // Receiving
               curr.targets as targets,
               curr.receptions as receptions,
               curr.receiving_yards as receiving_yards,
               curr.receiving_tds as receiving_tds,

               // Advanced (may be null for older years)
               curr.avg_target_share as target_share,
               curr.avg_air_yards_share as air_yards_share,
               curr.avg_wopr as wopr,

               // Career context
               years_prior as years_in_league,
               career_ppg_prior as career_ppg,
               best_prior_ppg as best_season_ppg,

               // TARGETS
               next.season as next_season,
               next.games as next_games,
               next.ppg_ppr as next_ppg_ppr,
               next.ppg_std as next_ppg_std,
               next.total_fantasy_points_ppr as next_total_fpts

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

        if df.empty:
            logger.warning("No training data returned!")
            return df

        logger.info(f"Base dataset: {len(df):,} season pairs")

        # Add combine data if requested
        if include_combine:
            df = self._add_combine_features(df)

        # Add draft data if requested
        if include_draft:
            df = self._add_draft_features(df)

        # Engineer additional features
        df = self._engineer_season_features(df)

        # QUICK WIN #1: Add snap count features (2015+ data)
        if include_snaps:
            df = self._add_snap_features(df)

        # QUICK WIN #2: Add team share features
        if include_team_shares:
            df = self._add_team_share_features(df)

        # QUICK WIN #3: Add age curve features
        if include_age_curves:
            df = self._add_age_curve_features(df)

        # QUICK WIN #4: Add surge detection features
        if include_surge:
            df = self._add_surge_features(df)

        logger.info(f"Final dataset: {len(df):,} rows, {len(df.columns)} columns")
        return df

    def _add_combine_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add NFL Combine metrics to dataset."""
        query = """
        MATCH (c:CombineResult)
        WHERE c.player_id IN $player_ids
        RETURN c.player_id as player_id,
               c.height as height,
               c.weight as weight,
               c.forty_yard as forty_yard,
               c.vertical_jump as vertical_jump,
               c.broad_jump as broad_jump,
               c.three_cone as three_cone,
               c.shuttle as shuttle,
               c.bench_press as bench_press
        """

        player_ids = df['player_id'].dropna().unique().tolist()

        with self.driver.session() as session:
            result = session.run(query, {'player_ids': player_ids})
            records = [dict(r) for r in result]

        if records:
            combine_df = pd.DataFrame(records)
            df = df.merge(combine_df, on='player_id', how='left')
            logger.info(f"Added combine data for {len(combine_df)} players")
        else:
            # Add empty columns
            for col in ['height', 'weight', 'forty_yard', 'vertical_jump',
                       'broad_jump', 'three_cone', 'shuttle', 'bench_press']:
                df[col] = np.nan

        return df

    def _add_draft_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add draft information to dataset."""
        query = """
        MATCH (d:DraftPick)
        WHERE d.player_id IN $player_ids
        RETURN d.player_id as player_id,
               d.season as draft_year,
               d.round as draft_round,
               d.overall_pick as draft_overall
        """

        player_ids = df['player_id'].dropna().unique().tolist()

        with self.driver.session() as session:
            result = session.run(query, {'player_ids': player_ids})
            records = [dict(r) for r in result]

        if records:
            draft_df = pd.DataFrame(records)
            df = df.merge(draft_df, on='player_id', how='left')
            logger.info(f"Added draft data for {len(draft_df)} players")

            # Calculate years since draft (age proxy)
            df['years_since_draft'] = df['season'] - df['draft_year']
        else:
            df['draft_year'] = np.nan
            df['draft_round'] = np.nan
            df['draft_overall'] = np.nan
            df['years_since_draft'] = np.nan

        return df

    def _engineer_season_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Engineer additional features from raw stats."""
        # Per-game stats
        if 'targets' in df.columns:
            df['targets_per_game'] = df['targets'] / df['games'].replace(0, np.nan)
            df['receptions_per_game'] = df['receptions'] / df['games'].replace(0, np.nan)
            df['rec_yards_per_game'] = df['receiving_yards'] / df['games'].replace(0, np.nan)

        if 'carries' in df.columns:
            df['carries_per_game'] = df['carries'] / df['games'].replace(0, np.nan)
            df['rush_yards_per_game'] = df['rushing_yards'] / df['games'].replace(0, np.nan)

        # Efficiency metrics
        if 'receptions' in df.columns and 'targets' in df.columns:
            df['catch_rate'] = df['receptions'] / df['targets'].replace(0, np.nan)

        if 'receiving_yards' in df.columns and 'receptions' in df.columns:
            df['yards_per_catch'] = df['receiving_yards'] / df['receptions'].replace(0, np.nan)

        if 'rushing_yards' in df.columns and 'carries' in df.columns:
            df['yards_per_carry'] = df['rushing_yards'] / df['carries'].replace(0, np.nan)

        # Year-over-year change (if we have career history)
        if 'career_ppg' in df.columns:
            df['ppg_vs_career_avg'] = df['ppg_ppr'] - df['career_ppg']
            df['ppg_vs_best'] = df['ppg_ppr'] - df['best_season_ppg']

        # TD rates
        if 'receiving_tds' in df.columns:
            df['rec_td_rate'] = df['receiving_tds'] / df['targets'].replace(0, np.nan)
        if 'rushing_tds' in df.columns:
            df['rush_td_rate'] = df['rushing_tds'] / df['carries'].replace(0, np.nan)

        # Target variables for classification
        if 'next_ppg_ppr' in df.columns:
            df['ppg_change'] = df['next_ppg_ppr'] - df['ppg_ppr']
            df['ppg_change_pct'] = df['ppg_change'] / df['ppg_ppr'].replace(0, np.nan)

            # Breakout: 50%+ increase with min threshold
            df['is_breakout'] = (
                (df['ppg_change_pct'] >= 0.5) &
                (df['next_ppg_ppr'] >= 10)  # Must reach starter threshold
            ).astype(int)

            # Bust: 30%+ decline
            df['is_bust'] = (df['ppg_change_pct'] <= -0.3).astype(int)

        return df

    # =========================================================================
    # QUICK WIN #1: SNAP COUNT FEATURES
    # =========================================================================

    def _add_snap_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add snap count features from HistoricalSnapCount data."""
        logger.info("Adding snap count features...")

        query = """
        MATCH (h:HistoricalSnapCount)
        WHERE h.player_id IN $player_ids
          AND h.season IN $seasons
        WITH h.player_id as player_id, h.season as season,
             collect(h) as weeks
        WITH player_id, season,
             // Average snap percentage
             reduce(s=0.0, w IN weeks | s + coalesce(w.offense_pct, 0)) / size(weeks) as avg_snap_pct,
             // Total snaps
             reduce(s=0, w IN weeks | s + coalesce(w.offense_snaps, 0)) as total_snaps,
             // Snap trend (last 4 weeks vs first 4 weeks)
             CASE WHEN size(weeks) >= 8
                  THEN (reduce(s=0.0, w IN weeks[-4..] | s + coalesce(w.offense_pct, 0)) / 4) -
                       (reduce(s=0.0, w IN weeks[0..4] | s + coalesce(w.offense_pct, 0)) / 4)
                  ELSE null END as snap_trend,
             // Snap consistency (low std dev = more consistent)
             size(weeks) as weeks_with_snaps
        RETURN player_id, season, avg_snap_pct, total_snaps, snap_trend, weeks_with_snaps
        """

        player_ids = df['player_id'].dropna().unique().tolist()
        seasons = df['season'].dropna().unique().tolist()

        with self.driver.session() as session:
            result = session.run(query, {'player_ids': player_ids, 'seasons': seasons})
            records = [dict(r) for r in result]

        if records:
            snap_df = pd.DataFrame(records)
            df = df.merge(snap_df, on=['player_id', 'season'], how='left')
            logger.info(f"Added snap features for {len(snap_df)} player-seasons")

            # Calculate snap consistency score
            df['snap_consistency'] = 1 - (df['snap_trend'].abs() / 100).fillna(0.5)
        else:
            logger.warning("No snap count data found")
            df['avg_snap_pct'] = np.nan
            df['total_snaps'] = np.nan
            df['snap_trend'] = np.nan
            df['weeks_with_snaps'] = np.nan
            df['snap_consistency'] = np.nan

        return df

    # =========================================================================
    # QUICK WIN #2: TARGET/CARRY SHARE CALCULATIONS
    # =========================================================================

    def _add_team_share_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate target share and carry share relative to team totals."""
        logger.info("Adding team share features...")

        query = """
        MATCH (h:HistoricalSeasonStats)
        WHERE h.season IN $seasons
          AND h.position IN ['QB', 'RB', 'WR', 'TE']
        WITH h.team as team, h.season as season,
             sum(coalesce(h.targets, 0)) as team_targets,
             sum(coalesce(h.carries, 0)) as team_carries,
             sum(coalesce(h.receiving_yards, 0)) as team_rec_yards,
             sum(coalesce(h.rushing_yards, 0)) as team_rush_yards
        RETURN team, season, team_targets, team_carries, team_rec_yards, team_rush_yards
        """

        seasons = df['season'].dropna().unique().tolist()

        with self.driver.session() as session:
            result = session.run(query, {'seasons': seasons})
            records = [dict(r) for r in result]

        if records:
            team_df = pd.DataFrame(records)

            # Merge team totals
            df = df.merge(team_df, on=['team', 'season'], how='left')

            # Calculate shares
            df['target_share_calc'] = df['targets'] / df['team_targets'].replace(0, np.nan)
            df['carry_share'] = df['carries'] / df['team_carries'].replace(0, np.nan)
            df['rec_yards_share'] = df['receiving_yards'] / df['team_rec_yards'].replace(0, np.nan)
            df['rush_yards_share'] = df['rushing_yards'] / df['team_rush_yards'].replace(0, np.nan)

            # Combined opportunity share (weighted by position)
            df['opportunity_share'] = np.where(
                df['position'] == 'RB',
                df['carry_share'].fillna(0) * 0.6 + df['target_share_calc'].fillna(0) * 0.4,
                df['target_share_calc'].fillna(0)
            )

            # Drop team total columns (not needed for training)
            df = df.drop(columns=['team_targets', 'team_carries', 'team_rec_yards', 'team_rush_yards'], errors='ignore')

            logger.info("Added team share features")
        else:
            logger.warning("Could not calculate team shares")
            df['target_share_calc'] = np.nan
            df['carry_share'] = np.nan
            df['opportunity_share'] = np.nan

        return df

    # =========================================================================
    # QUICK WIN #3: POSITION-SPECIFIC AGE CURVES
    # =========================================================================

    def _add_age_curve_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add position-specific age curve features."""
        logger.info("Adding age curve features...")

        # Position peak ages (based on historical data)
        POSITION_PEAKS = {
            'QB': {'peak_start': 27, 'peak_end': 35, 'cliff_age': 38},
            'RB': {'peak_start': 23, 'peak_end': 26, 'cliff_age': 28},
            'WR': {'peak_start': 25, 'peak_end': 29, 'cliff_age': 31},
            'TE': {'peak_start': 26, 'peak_end': 30, 'cliff_age': 32}
        }

        # Calculate age from years_in_league (assuming average entry age of 22)
        if 'years_in_league' in df.columns:
            # years_in_league = 0 for rookies, so estimated age = 22 + years_in_league
            df['estimated_age'] = 22 + df['years_in_league'].fillna(0)
        else:
            df['estimated_age'] = np.nan

        def calculate_age_features(row):
            """Calculate age-related features for a player."""
            pos = row.get('position')
            age = row.get('estimated_age')

            if pd.isna(age) or pos not in POSITION_PEAKS:
                return pd.Series({
                    'years_to_peak': np.nan,
                    'years_from_cliff': np.nan,
                    'in_prime_window': np.nan,
                    'age_decline_risk': np.nan,
                    'age_score': np.nan
                })

            peaks = POSITION_PEAKS[pos]

            years_to_peak = peaks['peak_start'] - age
            years_from_cliff = peaks['cliff_age'] - age
            in_prime = 1 if peaks['peak_start'] <= age <= peaks['peak_end'] else 0

            # Age decline risk (0-1, higher = more risk)
            if age < peaks['peak_start']:
                decline_risk = 0
            elif age <= peaks['peak_end']:
                decline_risk = 0.1
            elif age <= peaks['cliff_age']:
                # Linear increase from peak_end to cliff
                decline_risk = 0.1 + 0.6 * (age - peaks['peak_end']) / (peaks['cliff_age'] - peaks['peak_end'])
            else:
                decline_risk = 0.7 + 0.3 * min((age - peaks['cliff_age']) / 3, 1)

            # Age score (higher = better dynasty value)
            # Young players before peak get highest scores
            if age < peaks['peak_start']:
                age_score = 100 - (peaks['peak_start'] - age) * 5  # Slight penalty for too young
            elif age <= peaks['peak_end']:
                age_score = 90 - (age - peaks['peak_start']) * 2  # Gradual decline in prime
            else:
                age_score = max(0, 80 - (age - peaks['peak_end']) * 10)

            return pd.Series({
                'years_to_peak': years_to_peak,
                'years_from_cliff': years_from_cliff,
                'in_prime_window': in_prime,
                'age_decline_risk': decline_risk,
                'age_score': age_score
            })

        age_features = df.apply(calculate_age_features, axis=1)
        df = pd.concat([df, age_features], axis=1)

        logger.info("Added age curve features")
        return df

    # =========================================================================
    # QUICK WIN #4: SECOND-HALF SURGE DETECTION
    # =========================================================================

    def _add_surge_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect second-half of season performance surges."""
        logger.info("Adding surge detection features...")

        query = """
        MATCH (h:HistoricalWeeklyStats)
        WHERE h.player_id IN $player_ids
          AND h.season IN $seasons
        WITH h.player_id as player_id, h.season as season,
             collect(h) as all_weeks

        // Split into first half (weeks 1-9) and second half (weeks 10+)
        WITH player_id, season, all_weeks,
             [w IN all_weeks WHERE w.week <= 9] as first_half,
             [w IN all_weeks WHERE w.week >= 10] as second_half

        // Calculate averages for each half
        WITH player_id, season, all_weeks, first_half, second_half,
             CASE WHEN size(first_half) > 0
                  THEN reduce(s=0.0, w IN first_half | s + coalesce(w.fantasy_points_ppr, 0)) / size(first_half)
                  ELSE null END as first_half_ppg,
             CASE WHEN size(second_half) > 0
                  THEN reduce(s=0.0, w IN second_half | s + coalesce(w.fantasy_points_ppr, 0)) / size(second_half)
                  ELSE null END as second_half_ppg,
             // Target trend
             CASE WHEN size(first_half) > 0
                  THEN reduce(s=0.0, w IN first_half | s + coalesce(w.targets, 0)) / size(first_half)
                  ELSE null END as first_half_targets,
             CASE WHEN size(second_half) > 0
                  THEN reduce(s=0.0, w IN second_half | s + coalesce(w.targets, 0)) / size(second_half)
                  ELSE null END as second_half_targets,
             size(first_half) as first_half_games,
             size(second_half) as second_half_games

        // Calculate last 4 weeks in final projection
        RETURN player_id, season, first_half_ppg, second_half_ppg,
               first_half_targets, second_half_targets,
               CASE WHEN size(all_weeks) >= 4
                    THEN reduce(s=0.0, w IN all_weeks[-4..] | s + coalesce(w.fantasy_points_ppr, 0)) / 4
                    ELSE null END as last_4_weeks_ppg,
               first_half_games, second_half_games
        """

        player_ids = df['player_id'].dropna().unique().tolist()
        seasons = df['season'].dropna().unique().tolist()

        with self.driver.session() as session:
            result = session.run(query, {'player_ids': player_ids, 'seasons': seasons})
            records = [dict(r) for r in result]

        if records:
            surge_df = pd.DataFrame(records)
            df = df.merge(surge_df, on=['player_id', 'season'], how='left')

            # Calculate surge metrics
            df['ppg_surge'] = df['second_half_ppg'] - df['first_half_ppg']
            df['ppg_surge_pct'] = df['ppg_surge'] / df['first_half_ppg'].replace(0, np.nan)
            df['target_surge'] = df['second_half_targets'] - df['first_half_targets']

            # Recent form vs season average
            df['recent_form_vs_avg'] = df['last_4_weeks_ppg'] - df['ppg_ppr']

            # Binary surge flags
            df['is_surging'] = ((df['ppg_surge_pct'] > 0.15) & (df['second_half_games'] >= 4)).astype(int)
            df['is_fading'] = ((df['ppg_surge_pct'] < -0.15) & (df['second_half_games'] >= 4)).astype(int)

            # Hot streak indicator
            df['hot_finish'] = (df['last_4_weeks_ppg'] > df['ppg_ppr'] * 1.2).astype(int)

            logger.info("Added surge detection features")
        else:
            logger.warning("Could not calculate surge features")
            for col in ['ppg_surge', 'ppg_surge_pct', 'target_surge', 'recent_form_vs_avg',
                       'is_surging', 'is_fading', 'hot_finish']:
                df[col] = np.nan

        return df

    # =========================================================================
    # WEEKLY PREDICTION DATASET
    # =========================================================================

    def build_weekly_prediction_dataset(
        self,
        positions: List[str] = ['QB', 'RB', 'WR', 'TE'],
        start_year: int = 2015,  # Need snaps for good prediction
        end_year: int = 2024,
        min_prior_weeks: int = 3
    ) -> pd.DataFrame:
        """
        Build weekly fantasy prediction dataset.

        Features:
        - Season-to-date stats (avg, trend)
        - Recent 3-week rolling average
        - Snap % and trend
        - Opponent context

        Target:
        - fantasy_points_ppr for the week
        """
        logger.info(f"Building weekly prediction dataset")

        query = """
        MATCH (h:HistoricalWeeklyStats)
        WHERE h.position IN $positions
          AND h.season >= $start_year
          AND h.season <= $end_year
          AND h.week >= $min_prior_weeks

        // Get prior weeks this season for rolling features
        OPTIONAL MATCH (prior:HistoricalWeeklyStats)
        WHERE prior.player_id = h.player_id
          AND prior.season = h.season
          AND prior.week < h.week
          AND prior.week >= h.week - 5

        WITH h, collect(prior) as prior_weeks

        // Calculate rolling stats
        WITH h,
             size(prior_weeks) as weeks_played,
             CASE WHEN size(prior_weeks) > 0
                  THEN reduce(s=0.0, w IN prior_weeks | s + w.fantasy_points_ppr) / size(prior_weeks)
                  ELSE 0 END as season_ppg,
             CASE WHEN size(prior_weeks) >= 3
                  THEN reduce(s=0.0, w IN prior_weeks[-3..] | s + w.fantasy_points_ppr) / 3
                  ELSE null END as rolling_3wk_ppg,
             CASE WHEN size(prior_weeks) > 0
                  THEN reduce(s=0.0, w IN prior_weeks | s + coalesce(w.targets, 0)) / size(prior_weeks)
                  ELSE 0 END as avg_targets

        // Get snap data if available
        OPTIONAL MATCH (snap:HistoricalSnapCount)
        WHERE snap.player_id = h.player_id
          AND snap.season = h.season
          AND snap.week = h.week - 1

        RETURN h.player_id as player_id,
               h.player_name as player_name,
               h.position as position,
               h.season as season,
               h.week as week,
               h.team as team,
               h.opponent as opponent,

               // Prior context
               weeks_played,
               season_ppg,
               rolling_3wk_ppg,
               avg_targets,

               // Last week snap
               snap.offense_pct as last_week_snap_pct,

               // TARGET
               h.fantasy_points_ppr as target_fpts_ppr

        ORDER BY h.season, h.week, h.player_name
        LIMIT 500000
        """

        with self.driver.session() as session:
            result = session.run(query, {
                'positions': positions,
                'start_year': start_year,
                'end_year': end_year,
                'min_prior_weeks': min_prior_weeks
            })
            records = [dict(r) for r in result]

        df = pd.DataFrame(records)
        logger.info(f"Weekly prediction dataset: {len(df):,} rows")
        return df

    # =========================================================================
    # BREAKOUT PROBABILITY DATASET
    # =========================================================================

    def build_breakout_dataset(
        self,
        positions: List[str] = ['RB', 'WR', 'TE'],  # Exclude QB - different breakout pattern
        min_games: int = 10,
        breakout_threshold: float = 0.5  # 50% PPG increase
    ) -> pd.DataFrame:
        """
        Build dataset for breakout probability prediction.

        Breakout defined as: 50%+ PPG increase AND reaching 10+ PPG.

        Focus features:
        - Age/experience
        - Draft capital
        - Snap % trend
        - Target share
        - Athletic profile
        """
        logger.info("Building breakout probability dataset")

        # Use season projection dataset as base
        df = self.build_season_projection_dataset(
            positions=positions,
            min_games=min_games,
            include_combine=True,
            include_draft=True
        )

        if df.empty:
            return df

        # Focus on potential breakout candidates (lower current production)
        df = df[df['ppg_ppr'] < 15]  # Not already elite

        # Add athletic percentiles
        df = self._add_athletic_percentiles(df)

        # Target is already calculated
        logger.info(f"Breakout dataset: {len(df):,} rows, {df['is_breakout'].sum()} breakouts")

        return df

    def _add_athletic_percentiles(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add position-relative athletic percentiles."""
        athletic_cols = ['forty_yard', 'vertical_jump', 'broad_jump', 'three_cone']

        for col in athletic_cols:
            if col in df.columns:
                # Calculate percentile within position
                df[f'{col}_pctl'] = df.groupby('position')[col].transform(
                    lambda x: x.rank(pct=True, ascending=(col == 'forty_yard'))
                )

        # Composite athletic score
        pctl_cols = [f'{c}_pctl' for c in athletic_cols if f'{c}_pctl' in df.columns]
        if pctl_cols:
            df['athletic_score'] = df[pctl_cols].mean(axis=1)

        return df

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def get_feature_importance_by_position(self, position: str) -> Dict[str, Any]:
        """Get suggested feature importance for a position."""
        importance = {
            'QB': {
                'high': ['passing_yards', 'passing_tds', 'years_since_draft', 'games'],
                'medium': ['interceptions', 'rushing_yards', 'draft_round'],
                'low': ['athletic_metrics']
            },
            'RB': {
                'high': ['carries', 'targets', 'snap_pct', 'years_since_draft'],
                'medium': ['yards_per_carry', 'catch_rate', 'draft_round'],
                'low': ['forty_yard', 'weight']
            },
            'WR': {
                'high': ['targets', 'target_share', 'air_yards_share', 'years_since_draft'],
                'medium': ['catch_rate', 'yards_per_catch', 'snap_pct'],
                'low': ['forty_yard', 'height', 'weight']
            },
            'TE': {
                'high': ['targets', 'snap_pct', 'years_since_draft'],
                'medium': ['catch_rate', 'draft_round', 'height'],
                'low': ['forty_yard', 'weight']
            }
        }
        return importance.get(position, importance['WR'])

    def get_dataset_summary(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Get summary statistics for a dataset."""
        return {
            'rows': len(df),
            'columns': len(df.columns),
            'years': f"{df['season'].min()}-{df['season'].max()}" if 'season' in df.columns else 'N/A',
            'positions': df['position'].value_counts().to_dict() if 'position' in df.columns else {},
            'null_pct': (df.isnull().sum() / len(df) * 100).to_dict(),
            'target_stats': {
                'mean': df['next_ppg_ppr'].mean() if 'next_ppg_ppr' in df.columns else None,
                'std': df['next_ppg_ppr'].std() if 'next_ppg_ppr' in df.columns else None,
                'min': df['next_ppg_ppr'].min() if 'next_ppg_ppr' in df.columns else None,
                'max': df['next_ppg_ppr'].max() if 'next_ppg_ppr' in df.columns else None,
            }
        }

    def export_dataset(
        self,
        df: pd.DataFrame,
        filepath: str,
        include_metadata: bool = True
    ):
        """Export dataset to file with optional metadata."""
        import json
        from pathlib import Path

        path = Path(filepath)

        # Export main data
        if path.suffix == '.csv':
            df.to_csv(path, index=False)
        elif path.suffix == '.parquet':
            df.to_parquet(path, index=False)
        else:
            df.to_csv(path, index=False)

        # Export metadata
        if include_metadata:
            metadata = {
                'created_at': datetime.now().isoformat(),
                'summary': self.get_dataset_summary(df),
                'columns': list(df.columns)
            }
            meta_path = path.with_suffix('.meta.json')
            with open(meta_path, 'w') as f:
                json.dump(metadata, f, indent=2, default=str)

        logger.info(f"Exported dataset to {filepath}")


# =============================================================================
# STANDALONE DATASET BUILDER SCRIPT
# =============================================================================

def build_all_datasets(driver, output_dir: str = 'data/ml_training'):
    """Build all ML training datasets."""
    from pathlib import Path

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    builder = TrainingDatasetBuilder(driver)

    # 1. Season Projection Dataset
    logger.info("\n" + "=" * 60)
    logger.info("Building Season Projection Dataset")
    logger.info("=" * 60)

    season_df = builder.build_season_projection_dataset(
        positions=['QB', 'RB', 'WR', 'TE'],
        min_games=8,
        start_year=1999,
        end_year=2023
    )
    builder.export_dataset(season_df, str(output_path / 'season_projection.parquet'))

    # 2. Weekly Prediction Dataset (2015+)
    logger.info("\n" + "=" * 60)
    logger.info("Building Weekly Prediction Dataset")
    logger.info("=" * 60)

    weekly_df = builder.build_weekly_prediction_dataset(
        positions=['QB', 'RB', 'WR', 'TE'],
        start_year=2015,
        end_year=2024
    )
    builder.export_dataset(weekly_df, str(output_path / 'weekly_prediction.parquet'))

    # 3. Breakout Probability Dataset
    logger.info("\n" + "=" * 60)
    logger.info("Building Breakout Probability Dataset")
    logger.info("=" * 60)

    breakout_df = builder.build_breakout_dataset(
        positions=['RB', 'WR', 'TE']
    )
    builder.export_dataset(breakout_df, str(output_path / 'breakout_probability.parquet'))

    logger.info("\n" + "=" * 60)
    logger.info("All datasets built successfully!")
    logger.info(f"Output directory: {output_path}")
    logger.info("=" * 60)

    return {
        'season_projection': len(season_df),
        'weekly_prediction': len(weekly_df),
        'breakout_probability': len(breakout_df)
    }
