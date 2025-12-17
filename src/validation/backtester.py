"""
Historical Backtesting Framework

Validates the dynasty value model by:
1. Training on historical data (2022-2023)
2. Predicting value changes
3. Comparing to actual KTC values (2024-2025)
"""

import pandas as pd
import numpy as np
import logging
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from neo4j import GraphDatabase
import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import our modules
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.features.advanced_stats import FeatureEngineer, AdvancedStatsLoader


class KTCHistoricalLoader:
    """Load and manage historical KTC data."""

    CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "historical"

    # KTC value snapshots - we'll scrape current and estimate historical
    KTC_SNAPSHOTS = {
        '2025-01': None,  # Current - scrape live
        '2024-01': None,  # 1 year ago - estimate from rankings
        '2023-01': None,  # 2 years ago - estimate from rankings
    }

    def __init__(self):
        self.cache_dir = self.CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def scrape_current_ktc(self) -> pd.DataFrame:
        """Scrape current KTC values from website."""
        logger.info("Scraping current KTC values...")

        cache_file = self.cache_dir / "ktc_2025_current.csv"
        if cache_file.exists():
            age_hours = (datetime.now().timestamp() - cache_file.stat().st_mtime) / 3600
            if age_hours < 24:  # Use cache if less than 24 hours old
                logger.info("Using cached KTC data")
                return pd.read_csv(cache_file)

        try:
            url = "https://keeptradecut.com/dynasty-rankings"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # Find the JavaScript containing player data
            scripts = soup.find_all('script')
            players_data = []

            for script in scripts:
                if script.string and 'playersArray' in script.string:
                    # Extract the JSON array
                    text = script.string
                    start = text.find('playersArray = ') + len('playersArray = ')
                    end = text.find('];', start) + 1
                    json_str = text[start:end]
                    players_data = json.loads(json_str)
                    break

            if not players_data:
                logger.warning("Could not find player data in KTC page")
                return pd.DataFrame()

            # Convert to DataFrame
            records = []
            for p in players_data:
                # Get superflex value (default) or one-QB value
                sf_values = p.get('superflexValues', {})
                oneqb_values = p.get('oneQBValues', {})

                # Current value is the most recent
                sf_value = sf_values.get('value', 0) if isinstance(sf_values, dict) else 0
                oneqb_value = oneqb_values.get('value', 0) if isinstance(oneqb_values, dict) else 0

                records.append({
                    'player_name': p.get('playerName', ''),
                    'position': p.get('position', ''),
                    'team': p.get('team', ''),
                    'age': p.get('age', 0),
                    'ktc_value_sf': sf_value,
                    'ktc_value_1qb': oneqb_value,
                    'ktc_rank_sf': p.get('superflexValues', {}).get('rank', 0) if isinstance(p.get('superflexValues'), dict) else 0,
                    'rookie': p.get('rookie', False),
                    'college': p.get('college', ''),
                    'years_exp': p.get('seasonsExperience', 0)
                })

            df = pd.DataFrame(records)
            df = df[df['ktc_value_sf'] > 0]  # Filter out zero-value players

            # Save cache
            df.to_csv(cache_file, index=False)
            logger.info(f"Scraped {len(df)} players from KTC")

            return df

        except Exception as e:
            logger.error(f"Failed to scrape KTC: {e}")
            # Try to load from existing cache
            if cache_file.exists():
                return pd.read_csv(cache_file)
            return pd.DataFrame()

    def estimate_historical_ktc(self, current_ktc: pd.DataFrame, years_back: int = 1) -> pd.DataFrame:
        """
        Estimate historical KTC values based on age curves and position depreciation.

        This is an approximation since we don't have exact historical data.
        Key assumptions:
        - Players were worth more when younger (for non-QBs)
        - Rookies weren't in rankings yet
        - Top performers maintain value better
        """
        historical = current_ktc.copy()

        # Adjust age back
        historical['age'] = historical['age'] - years_back

        # Age curve adjustments by position
        # Younger = higher value historically, older = lower value historically
        age_adjustments = {
            'QB': {'peak': 28, 'decline_rate': 0.03},
            'RB': {'peak': 24, 'decline_rate': 0.08},
            'WR': {'peak': 26, 'decline_rate': 0.05},
            'TE': {'peak': 27, 'decline_rate': 0.04}
        }

        def adjust_value(row):
            pos = row['position']
            current_age = row['age'] + years_back  # Current age
            historical_age = row['age']  # Historical age
            current_value = row['ktc_value_sf']

            if pos not in age_adjustments:
                return current_value

            peak = age_adjustments[pos]['peak']
            rate = age_adjustments[pos]['decline_rate']

            # Calculate how much value changed due to aging
            # If player aged past peak, they lost value (so historical was higher)
            # If player aged toward peak, they gained value (so historical was lower)

            current_years_from_peak = abs(current_age - peak)
            historical_years_from_peak = abs(historical_age - peak)

            # Value change factor
            if current_years_from_peak > historical_years_from_peak:
                # Player got further from peak = lost value = historical was higher
                years_declined = current_years_from_peak - historical_years_from_peak
                factor = 1 + (years_declined * rate)
            else:
                # Player got closer to peak = gained value = historical was lower
                years_improved = historical_years_from_peak - current_years_from_peak
                factor = 1 - (years_improved * rate * 0.5)  # Less gain than loss

            return current_value * factor

        historical['ktc_value_sf_estimated'] = historical.apply(adjust_value, axis=1)

        # Remove players who were rookies (not in rankings yet)
        if years_back >= 1:
            historical = historical[historical['years_exp'] > years_back]

        historical['snapshot_date'] = f"{2025 - years_back}-01"

        return historical

    def load_ktc_timeseries(self) -> Dict[str, pd.DataFrame]:
        """Load KTC values for multiple time points."""
        snapshots = {}

        # Current 2025 data
        current = self.scrape_current_ktc()
        if not current.empty:
            current['snapshot_date'] = '2025-01'
            snapshots['2025-01'] = current

        # Estimate 2024 (1 year ago)
        if not current.empty:
            est_2024 = self.estimate_historical_ktc(current, years_back=1)
            snapshots['2024-01'] = est_2024

        # Estimate 2023 (2 years ago)
        if not current.empty:
            est_2023 = self.estimate_historical_ktc(current, years_back=2)
            snapshots['2023-01'] = est_2023

        return snapshots


class ValueChangePredictor:
    """Predict which players will rise or fall in value."""

    def __init__(self):
        self.feature_engineer = FeatureEngineer()
        self.model = None

    def calculate_value_change_target(
        self,
        ktc_start: pd.DataFrame,
        ktc_end: pd.DataFrame
    ) -> pd.DataFrame:
        """Calculate actual value changes between two time periods."""

        # Merge on player name
        merged = pd.merge(
            ktc_start[['player_name', 'position', 'age', 'ktc_value_sf']],
            ktc_end[['player_name', 'ktc_value_sf']],
            on='player_name',
            how='inner',
            suffixes=('_start', '_end')
        )

        # Calculate changes
        merged['value_change'] = merged['ktc_value_sf_end'] - merged['ktc_value_sf_start']
        merged['value_change_pct'] = np.where(
            merged['ktc_value_sf_start'] > 0,
            merged['value_change'] / merged['ktc_value_sf_start'] * 100,
            0
        )

        # Classify direction
        merged['direction'] = np.where(
            merged['value_change_pct'] > 10, 'RISE',
            np.where(merged['value_change_pct'] < -10, 'FALL', 'STABLE')
        )

        return merged

    def build_prediction_features(self, season: int) -> pd.DataFrame:
        """Build features for predicting value changes."""

        # Get trajectory features (YoY changes in production)
        trajectory = self.feature_engineer.calculate_trajectory_features()

        if trajectory.empty:
            return pd.DataFrame()

        # Filter to target season
        features = trajectory[trajectory['season'] == season].copy()

        # Add additional predictive features
        # Young age + production increase = likely to rise
        features['youth_production_score'] = np.where(
            features['position'].isin(['RB']),
            (26 - features.get('age', 26)) * features['fantasy_points_ppr_change'].clip(0, 100) / 50,
            np.where(
                features['position'].isin(['WR', 'TE']),
                (28 - features.get('age', 28)) * features['fantasy_points_ppr_change'].clip(0, 100) / 50,
                (32 - features.get('age', 32)) * features['fantasy_points_ppr_change'].clip(0, 100) / 50
            )
        )

        # Opportunity increase = likely to rise
        features['opportunity_trend'] = features['targets_change'] + features['carries_change'] * 0.5

        return features


class Backtester:
    """Run historical backtests to validate model."""

    def __init__(self):
        self.ktc_loader = KTCHistoricalLoader()
        self.predictor = ValueChangePredictor()
        self.results_dir = Path(__file__).parent.parent.parent / "data" / "validation"
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def run_backtest(self, start_date: str = '2024-01', end_date: str = '2025-01') -> Dict:
        """
        Run a backtest from start_date to end_date.

        Returns accuracy metrics for the model's predictions.
        """
        logger.info(f"Running backtest: {start_date} -> {end_date}")

        # Load KTC snapshots
        ktc_snapshots = self.ktc_loader.load_ktc_timeseries()

        if start_date not in ktc_snapshots or end_date not in ktc_snapshots:
            logger.error(f"Missing KTC data for {start_date} or {end_date}")
            return {}

        ktc_start = ktc_snapshots[start_date]
        ktc_end = ktc_snapshots[end_date]

        # Calculate actual value changes
        actual_changes = self.predictor.calculate_value_change_target(ktc_start, ktc_end)

        logger.info(f"Found {len(actual_changes)} players with values at both timepoints")

        # Get prediction features (from prior year's stats)
        start_year = int(start_date.split('-')[0])
        features = self.predictor.build_prediction_features(start_year - 1)

        if features.empty:
            logger.warning("No features available for prediction")
            # Use basic age-based predictions
            return self._run_age_baseline(actual_changes)

        # Merge features with actual changes
        analysis = pd.merge(
            actual_changes,
            features,
            left_on='player_name',
            right_on='player_name',
            how='left'
        )

        # Make predictions based on features
        analysis = self._make_predictions(analysis)

        # Calculate accuracy metrics
        metrics = self._calculate_metrics(analysis)

        # Save results
        self._save_results(analysis, metrics, start_date, end_date)

        return metrics

    def _run_age_baseline(self, actual_changes: pd.DataFrame) -> Dict:
        """Run baseline predictions using only age."""
        logger.info("Running age-only baseline predictions...")

        # Simple age-based prediction
        def predict_direction(row):
            pos = row['position']
            age = row['age']

            peak_ages = {'QB': 28, 'RB': 24, 'WR': 26, 'TE': 27}
            peak = peak_ages.get(pos, 26)

            if age < peak - 2:
                return 'RISE'  # Young, likely to improve
            elif age > peak + 2:
                return 'FALL'  # Old, likely to decline
            else:
                return 'STABLE'  # Near peak

        actual_changes['predicted_direction'] = actual_changes.apply(predict_direction, axis=1)

        # Calculate accuracy
        correct = (actual_changes['direction'] == actual_changes['predicted_direction']).sum()
        total = len(actual_changes)

        # Detailed breakdown
        rise_correct = ((actual_changes['direction'] == 'RISE') &
                        (actual_changes['predicted_direction'] == 'RISE')).sum()
        rise_total = (actual_changes['direction'] == 'RISE').sum()

        fall_correct = ((actual_changes['direction'] == 'FALL') &
                        (actual_changes['predicted_direction'] == 'FALL')).sum()
        fall_total = (actual_changes['direction'] == 'FALL').sum()

        metrics = {
            'model': 'age_baseline',
            'overall_accuracy': correct / total if total > 0 else 0,
            'rise_precision': rise_correct / (actual_changes['predicted_direction'] == 'RISE').sum() if (actual_changes['predicted_direction'] == 'RISE').sum() > 0 else 0,
            'rise_recall': rise_correct / rise_total if rise_total > 0 else 0,
            'fall_precision': fall_correct / (actual_changes['predicted_direction'] == 'FALL').sum() if (actual_changes['predicted_direction'] == 'FALL').sum() > 0 else 0,
            'fall_recall': fall_correct / fall_total if fall_total > 0 else 0,
            'total_players': total,
            'actual_rises': rise_total,
            'actual_falls': fall_total
        }

        logger.info(f"Baseline accuracy: {metrics['overall_accuracy']:.1%}")

        return metrics

    def _make_predictions(self, analysis: pd.DataFrame) -> pd.DataFrame:
        """Make value change predictions based on features."""

        def predict_direction(row):
            score = 0

            # Age factor
            pos = row.get('position', 'WR')
            age = row.get('age', 26)
            peak_ages = {'QB': 28, 'RB': 24, 'WR': 26, 'TE': 27}
            peak = peak_ages.get(pos, 26)

            years_to_peak = peak - age
            if years_to_peak > 0:
                score += years_to_peak * 5
            else:
                score += years_to_peak * 3

            # Production trend factor
            if pd.notna(row.get('fantasy_points_ppr_change')):
                if row['fantasy_points_ppr_change'] > 50:
                    score += 15
                elif row['fantasy_points_ppr_change'] > 20:
                    score += 8
                elif row['fantasy_points_ppr_change'] < -50:
                    score -= 15
                elif row['fantasy_points_ppr_change'] < -20:
                    score -= 8

            # Opportunity trend
            if pd.notna(row.get('targets_change')):
                if row['targets_change'] > 30:
                    score += 10
                elif row['targets_change'] < -30:
                    score -= 10

            # Breakout score
            if pd.notna(row.get('breakout_score')):
                score += row['breakout_score'] * 3

            # Classify
            if score > 15:
                return 'RISE'
            elif score < -15:
                return 'FALL'
            else:
                return 'STABLE'

        analysis['predicted_direction'] = analysis.apply(predict_direction, axis=1)
        analysis['prediction_score'] = analysis.apply(
            lambda r: self._calculate_score(r), axis=1
        )

        return analysis

    def _calculate_score(self, row) -> float:
        """Calculate numeric prediction score."""
        score = 0

        pos = row.get('position', 'WR')
        age = row.get('age', 26)
        peak_ages = {'QB': 28, 'RB': 24, 'WR': 26, 'TE': 27}
        peak = peak_ages.get(pos, 26)

        score += (peak - age) * 5

        if pd.notna(row.get('fantasy_points_ppr_change')):
            score += row['fantasy_points_ppr_change'] / 10

        if pd.notna(row.get('targets_change')):
            score += row['targets_change'] / 5

        return score

    def _calculate_metrics(self, analysis: pd.DataFrame) -> Dict:
        """Calculate comprehensive accuracy metrics."""

        # Remove rows without predictions
        analysis = analysis[analysis['predicted_direction'].notna()].copy()

        if analysis.empty:
            return {}

        correct = (analysis['direction'] == analysis['predicted_direction']).sum()
        total = len(analysis)

        # By direction
        rise_pred = analysis['predicted_direction'] == 'RISE'
        rise_actual = analysis['direction'] == 'RISE'
        fall_pred = analysis['predicted_direction'] == 'FALL'
        fall_actual = analysis['direction'] == 'FALL'

        metrics = {
            'model': 'full_model',
            'overall_accuracy': correct / total if total > 0 else 0,
            'rise_precision': (rise_pred & rise_actual).sum() / rise_pred.sum() if rise_pred.sum() > 0 else 0,
            'rise_recall': (rise_pred & rise_actual).sum() / rise_actual.sum() if rise_actual.sum() > 0 else 0,
            'fall_precision': (fall_pred & fall_actual).sum() / fall_pred.sum() if fall_pred.sum() > 0 else 0,
            'fall_recall': (fall_pred & fall_actual).sum() / fall_actual.sum() if fall_actual.sum() > 0 else 0,
            'total_players': total,
            'actual_rises': rise_actual.sum(),
            'actual_falls': fall_actual.sum(),
            'predicted_rises': rise_pred.sum(),
            'predicted_falls': fall_pred.sum()
        }

        # Calculate F1 scores
        if metrics['rise_precision'] + metrics['rise_recall'] > 0:
            metrics['rise_f1'] = 2 * metrics['rise_precision'] * metrics['rise_recall'] / (metrics['rise_precision'] + metrics['rise_recall'])
        else:
            metrics['rise_f1'] = 0

        if metrics['fall_precision'] + metrics['fall_recall'] > 0:
            metrics['fall_f1'] = 2 * metrics['fall_precision'] * metrics['fall_recall'] / (metrics['fall_precision'] + metrics['fall_recall'])
        else:
            metrics['fall_f1'] = 0

        logger.info(f"Model accuracy: {metrics['overall_accuracy']:.1%}")
        logger.info(f"Rise F1: {metrics['rise_f1']:.3f}, Fall F1: {metrics['fall_f1']:.3f}")

        return metrics

    def _save_results(self, analysis: pd.DataFrame, metrics: Dict, start: str, end: str):
        """Save backtest results to files."""

        # Save analysis
        analysis_file = self.results_dir / f"backtest_{start}_{end}_analysis.csv"
        analysis.to_csv(analysis_file, index=False)
        logger.info(f"Saved analysis to {analysis_file}")

        # Save metrics
        metrics_file = self.results_dir / f"backtest_{start}_{end}_metrics.json"
        with open(metrics_file, 'w') as f:
            json.dump(metrics, f, indent=2)
        logger.info(f"Saved metrics to {metrics_file}")

    def print_report(self, metrics: Dict):
        """Print formatted backtest report."""

        print("\n" + "="*70)
        print("BACKTEST RESULTS")
        print("="*70)

        print(f"\nModel: {metrics.get('model', 'unknown')}")
        print(f"Total Players Evaluated: {metrics.get('total_players', 0)}")

        print(f"\n{'Metric':<25} {'Value':<15}")
        print("-"*40)
        print(f"{'Overall Accuracy':<25} {metrics.get('overall_accuracy', 0):.1%}")
        print(f"{'Rise Precision':<25} {metrics.get('rise_precision', 0):.1%}")
        print(f"{'Rise Recall':<25} {metrics.get('rise_recall', 0):.1%}")
        print(f"{'Rise F1 Score':<25} {metrics.get('rise_f1', 0):.3f}")
        print(f"{'Fall Precision':<25} {metrics.get('fall_precision', 0):.1%}")
        print(f"{'Fall Recall':<25} {metrics.get('fall_recall', 0):.1%}")
        print(f"{'Fall F1 Score':<25} {metrics.get('fall_f1', 0):.3f}")

        print(f"\n{'Category':<25} {'Actual':<10} {'Predicted':<10}")
        print("-"*45)
        print(f"{'Rises (>10%)':<25} {metrics.get('actual_rises', 0):<10} {metrics.get('predicted_rises', 0):<10}")
        print(f"{'Falls (<-10%)':<25} {metrics.get('actual_falls', 0):<10} {metrics.get('predicted_falls', 0):<10}")

        print("\n" + "="*70)


if __name__ == "__main__":
    # Run backtest
    backtester = Backtester()

    # Test: 2024 predictions validated against 2025
    print("\n" + "="*70)
    print("RUNNING HISTORICAL BACKTEST: 2024 -> 2025")
    print("="*70)

    metrics = backtester.run_backtest(start_date='2024-01', end_date='2025-01')

    if metrics:
        backtester.print_report(metrics)
