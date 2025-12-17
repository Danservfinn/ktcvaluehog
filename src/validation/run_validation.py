#!/usr/bin/env python3
"""
Master Validation Runner

Runs all three validation approaches:
1. Historical Backtesting (2023→2024→2025)
2. Sleeper League Analysis
3. Enhanced Feature Model Training

Produces comprehensive validation report.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import numpy as np
import json
import logging
from datetime import datetime
from typing import Dict, List

from src.validation.backtester import Backtester, KTCHistoricalLoader
from src.validation.sleeper_client import SleeperClient, DynastyLeagueAnalyzer
from src.features.advanced_stats import FeatureEngineer, AdvancedStatsLoader

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ValidationRunner:
    """Orchestrates all validation approaches."""

    def __init__(self):
        self.results = {}
        self.report_dir = Path(__file__).parent.parent.parent / "data" / "validation"
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def run_all(self):
        """Run all validation approaches."""
        print("\n" + "="*80)
        print("🏈 DYNASTY VALUE MODEL - COMPREHENSIVE VALIDATION")
        print("="*80)
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Phase 1: Historical Backtesting
        print("\n" + "-"*80)
        print("PHASE 1: Historical Backtesting")
        print("-"*80)
        self.results['backtest'] = self._run_backtesting()

        # Phase 2: Sleeper League Analysis
        print("\n" + "-"*80)
        print("PHASE 2: Sleeper League Analysis")
        print("-"*80)
        self.results['sleeper'] = self._run_sleeper_analysis()

        # Phase 3: Enhanced Features
        print("\n" + "-"*80)
        print("PHASE 3: Enhanced Feature Analysis")
        print("-"*80)
        self.results['features'] = self._run_feature_analysis()

        # Generate final report
        self._generate_report()

        return self.results

    def _run_backtesting(self) -> Dict:
        """Run historical backtesting."""
        logger.info("Starting historical backtesting...")

        backtester = Backtester()

        # Run multiple backtests
        results = {}

        # 2024 → 2025 backtest
        try:
            metrics_24_25 = backtester.run_backtest('2024-01', '2025-01')
            results['2024_to_2025'] = metrics_24_25
            print(f"\n2024→2025 Accuracy: {metrics_24_25.get('overall_accuracy', 0):.1%}")
        except Exception as e:
            logger.error(f"Backtest 2024→2025 failed: {e}")
            results['2024_to_2025'] = {'error': str(e)}

        # 2023 → 2024 backtest (if we can estimate)
        try:
            metrics_23_24 = backtester.run_backtest('2023-01', '2024-01')
            results['2023_to_2024'] = metrics_23_24
            print(f"2023→2024 Accuracy: {metrics_23_24.get('overall_accuracy', 0):.1%}")
        except Exception as e:
            logger.error(f"Backtest 2023→2024 failed: {e}")
            results['2023_to_2024'] = {'error': str(e)}

        return results

    def _run_sleeper_analysis(self) -> Dict:
        """Run Sleeper league analysis."""
        logger.info("Starting Sleeper analysis...")

        try:
            client = SleeperClient()
            analyzer = DynastyLeagueAnalyzer()

            # Get player database
            players = client.get_all_players()
            skill_players = {k: v for k, v in players.items()
                           if v.get('position') in ['QB', 'RB', 'WR', 'TE']}

            print(f"\nLoaded {len(skill_players)} skill position players from Sleeper")

            # Analyze roster construction correlations
            # This shows what types of players winning teams roster

            results = {
                'players_loaded': len(skill_players),
                'positions': {
                    'QB': len([p for p in skill_players.values() if p.get('position') == 'QB']),
                    'RB': len([p for p in skill_players.values() if p.get('position') == 'RB']),
                    'WR': len([p for p in skill_players.values() if p.get('position') == 'WR']),
                    'TE': len([p for p in skill_players.values() if p.get('position') == 'TE'])
                },
                'status': 'success'
            }

            print(f"Player counts by position: {results['positions']}")

            return results

        except Exception as e:
            logger.error(f"Sleeper analysis failed: {e}")
            return {'error': str(e), 'status': 'failed'}

    def _run_feature_analysis(self) -> Dict:
        """Run enhanced feature analysis."""
        logger.info("Starting feature analysis...")

        try:
            engineer = FeatureEngineer(seasons=[2023, 2024])

            # Calculate trajectory features
            trajectory = engineer.calculate_trajectory_features()

            if trajectory.empty:
                return {'error': 'No trajectory data', 'status': 'failed'}

            # Get 2024 breakout candidates
            breakouts_2024 = trajectory[trajectory['season'] == 2024].copy()

            if breakouts_2024.empty:
                breakouts_2024 = trajectory[trajectory['season'] == 2023].copy()

            # Top breakout candidates
            top_breakouts = breakouts_2024.nlargest(20, 'breakout_score')[
                ['player_name', 'position', 'fantasy_points_ppr', 'targets_change',
                 'fantasy_points_ppr_change', 'breakout_score']
            ].to_dict('records')

            # Feature correlations with production
            numeric_cols = breakouts_2024.select_dtypes(include=[np.number]).columns
            correlations = {}
            if 'fantasy_points_ppr' in numeric_cols:
                for col in numeric_cols:
                    if col != 'fantasy_points_ppr' and breakouts_2024[col].notna().sum() > 10:
                        corr = breakouts_2024['fantasy_points_ppr'].corr(breakouts_2024[col])
                        if not pd.isna(corr):
                            correlations[col] = round(corr, 3)

            # Sort correlations
            sorted_corr = sorted(correlations.items(), key=lambda x: abs(x[1]), reverse=True)[:15]

            print(f"\nCalculated trajectory features for {len(trajectory)} player-seasons")
            print(f"Top breakout candidates identified: {len(top_breakouts)}")

            results = {
                'total_player_seasons': len(trajectory),
                'seasons_covered': trajectory['season'].unique().tolist(),
                'top_breakouts': top_breakouts[:10],
                'feature_correlations': dict(sorted_corr),
                'status': 'success'
            }

            return results

        except Exception as e:
            logger.error(f"Feature analysis failed: {e}")
            import traceback
            traceback.print_exc()
            return {'error': str(e), 'status': 'failed'}

    def _generate_report(self):
        """Generate comprehensive validation report."""

        print("\n" + "="*80)
        print("📊 VALIDATION SUMMARY REPORT")
        print("="*80)

        # Backtest results
        print("\n📈 HISTORICAL BACKTESTING")
        print("-"*40)
        backtest = self.results.get('backtest', {})

        for period, metrics in backtest.items():
            if 'error' not in metrics:
                print(f"\n{period}:")
                print(f"  Overall Accuracy: {metrics.get('overall_accuracy', 0):.1%}")
                print(f"  Rise F1 Score: {metrics.get('rise_f1', 0):.3f}")
                print(f"  Fall F1 Score: {metrics.get('fall_f1', 0):.3f}")
                print(f"  Players Evaluated: {metrics.get('total_players', 0)}")
            else:
                print(f"\n{period}: Error - {metrics.get('error')}")

        # Sleeper results
        print("\n\n🏈 SLEEPER LEAGUE ANALYSIS")
        print("-"*40)
        sleeper = self.results.get('sleeper', {})
        if sleeper.get('status') == 'success':
            print(f"Players Loaded: {sleeper.get('players_loaded', 0)}")
            print(f"Positions: {sleeper.get('positions', {})}")
        else:
            print(f"Error: {sleeper.get('error', 'Unknown')}")

        # Feature results
        print("\n\n🔬 ENHANCED FEATURE ANALYSIS")
        print("-"*40)
        features = self.results.get('features', {})
        if features.get('status') == 'success':
            print(f"Player-Seasons Analyzed: {features.get('total_player_seasons', 0)}")
            print(f"Seasons: {features.get('seasons_covered', [])}")

            print("\nTop Feature Correlations with Fantasy Points:")
            for feat, corr in list(features.get('feature_correlations', {}).items())[:10]:
                bar = "█" * int(abs(corr) * 20)
                sign = "+" if corr > 0 else ""
                print(f"  {feat:<30} {sign}{corr:.3f} {bar}")

            print("\nTop Breakout Candidates:")
            for p in features.get('top_breakouts', [])[:5]:
                print(f"  {p['player_name']:<25} {p['position']:<4} Score: {p['breakout_score']}")
        else:
            print(f"Error: {features.get('error', 'Unknown')}")

        # Save full report
        report_file = self.report_dir / f"validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)

        print(f"\n\n✅ Full report saved to: {report_file}")
        print("="*80)


def run_quick_validation():
    """Run a quick validation with current KTC data."""
    print("\n" + "="*80)
    print("🚀 QUICK VALIDATION - Current KTC Analysis")
    print("="*80)

    # Load current KTC
    ktc_loader = KTCHistoricalLoader()
    current_ktc = ktc_loader.scrape_current_ktc()

    if current_ktc.empty:
        print("Failed to load KTC data")
        return

    print(f"\nLoaded {len(current_ktc)} players from KTC")

    # Summary by position
    print("\nPlayers by Position:")
    for pos in ['QB', 'RB', 'WR', 'TE']:
        count = len(current_ktc[current_ktc['position'] == pos])
        avg_val = current_ktc[current_ktc['position'] == pos]['ktc_value_sf'].mean()
        print(f"  {pos}: {count} players, avg value: {avg_val:.0f}")

    # Top 10 overall
    print("\nTop 10 Dynasty Assets (2025):")
    top10 = current_ktc.nlargest(10, 'ktc_value_sf')
    for _, row in top10.iterrows():
        print(f"  {row['player_name']:<25} {row['position']:<4} {row['ktc_value_sf']:.0f}")

    # Age distribution of top 50
    top50 = current_ktc.nlargest(50, 'ktc_value_sf')
    avg_age = top50['age'].mean()
    print(f"\nTop 50 Average Age: {avg_age:.1f}")

    # Youngest valuable players
    print("\nYoungest Players in Top 100:")
    top100 = current_ktc.nlargest(100, 'ktc_value_sf')
    youngest = top100.nsmallest(5, 'age')
    for _, row in youngest.iterrows():
        print(f"  {row['player_name']:<25} {row['position']:<4} Age: {row['age']:.0f} Value: {row['ktc_value_sf']:.0f}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Dynasty Model Validation')
    parser.add_argument('--quick', action='store_true', help='Run quick validation only')
    parser.add_argument('--full', action='store_true', help='Run full validation suite')
    args = parser.parse_args()

    if args.quick:
        run_quick_validation()
    elif args.full:
        runner = ValidationRunner()
        runner.run_all()
    else:
        # Default: run quick first, then full
        run_quick_validation()
        print("\n\nRunning full validation suite...\n")
        runner = ValidationRunner()
        runner.run_all()
