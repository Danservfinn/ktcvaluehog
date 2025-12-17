"""
2025 Production Edge Calculator
================================
Calculates value discrepancies between current 2025 production
and dynasty market values (KTC).

Key Metrics:
- Production Efficiency: PPG relative to KTC value
- Value Gap: Predicted value based on production vs actual value
- Edge Score: Composite signal for buy/sell opportunities
- Trend Momentum: Recent performance trajectory

Buy signals: High production, low KTC value
Sell signals: Low production, high KTC value
"""

import os
import logging
from typing import Optional, List, Dict, Tuple
from datetime import datetime
import math

import pandas as pd
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class ProductionEdgeCalculator:
    """
    Calculate edge scores comparing 2025 production to dynasty values.

    The edge score identifies buy/sell opportunities based on:
    1. Production efficiency (points per KTC dollar)
    2. Positional rank vs value rank discrepancy
    3. Recent trend momentum
    4. Usage/opportunity metrics
    """

    # Position-specific PPG benchmarks (PPR)
    POSITION_PPG_BENCHMARKS = {
        'QB': {'elite': 22.0, 'starter': 18.0, 'average': 15.0, 'replacement': 12.0},
        'RB': {'elite': 18.0, 'starter': 14.0, 'average': 10.0, 'replacement': 6.0},
        'WR': {'elite': 18.0, 'starter': 14.0, 'average': 10.0, 'replacement': 6.0},
        'TE': {'elite': 14.0, 'starter': 10.0, 'average': 7.0, 'replacement': 4.0},
    }

    # Expected KTC value per PPG by position (superflex)
    VALUE_PER_PPG = {
        'QB': 350,   # QBs valued higher per point
        'RB': 450,   # RBs valued high due to scarcity
        'WR': 400,
        'TE': 500,   # TEs premium for elite production
    }

    # Age curve multipliers
    AGE_MULTIPLIERS = {
        'QB': {21: 1.3, 22: 1.25, 23: 1.2, 24: 1.15, 25: 1.1, 26: 1.05, 27: 1.0,
               28: 0.95, 29: 0.9, 30: 0.85, 31: 0.8, 32: 0.75, 33: 0.7, 34: 0.65},
        'RB': {21: 1.4, 22: 1.35, 23: 1.25, 24: 1.15, 25: 1.0, 26: 0.9, 27: 0.75,
               28: 0.6, 29: 0.5, 30: 0.4},
        'WR': {21: 1.35, 22: 1.3, 23: 1.2, 24: 1.1, 25: 1.05, 26: 1.0, 27: 0.95,
               28: 0.9, 29: 0.85, 30: 0.75, 31: 0.65, 32: 0.55},
        'TE': {21: 1.2, 22: 1.15, 23: 1.1, 24: 1.1, 25: 1.05, 26: 1.0, 27: 0.95,
               28: 0.9, 29: 0.85, 30: 0.75, 31: 0.65},
    }

    def __init__(self, driver=None):
        """Initialize with Neo4j driver."""
        if driver:
            self.driver = driver
            self._owns_driver = False
        else:
            uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
            user = os.getenv("NEO4J_USER")
            password = os.getenv("NEO4J_PASSWORD")
            auth = (user, password) if user and password else None
            self.driver = GraphDatabase.driver(uri, auth=auth)
            self._owns_driver = True

    def close(self):
        """Close driver if owned."""
        if self._owns_driver and self.driver:
            self.driver.close()

    # =========================================================================
    # CORE EDGE CALCULATIONS
    # =========================================================================

    def calculate_production_edge(
        self,
        positions: Optional[List[str]] = None,
        min_games: int = 3,
        superflex: bool = True
    ) -> pd.DataFrame:
        """
        Calculate production edge for all players with 2025 data.

        Args:
            positions: Filter to specific positions (default: QB, RB, WR, TE)
            min_games: Minimum games played
            superflex: Use superflex KTC values

        Returns:
            DataFrame with edge scores and signals
        """
        positions = positions or ['QB', 'RB', 'WR', 'TE']

        query = """
        MATCH (p:Player)-[:HAD_SEASON]->(ss:SeasonStats {season: 2025})
        WHERE ss.position IN $positions
        AND ss.games >= $min_games
        RETURN p.name as player,
               p.sleeper_id as sleeper_id,
               ss.position as position,
               ss.team as team,
               p.age as age,
               ss.games as games,
               ss.ppg_ppr as ppg,
               ss.total_fantasy_points_ppr as total_points,
               ss.targets as targets,
               ss.receptions as receptions,
               ss.receiving_yards as rec_yards,
               ss.carries as carries,
               ss.rushing_yards as rush_yards,
               p.ktc_value as ktc_value
        ORDER BY ss.ppg_ppr DESC
        """

        with self.driver.session() as session:
            result = session.run(query, {
                'positions': positions,
                'min_games': min_games,
                'superflex': superflex
            })

            data = []
            for record in result:
                row = dict(record)

                # Skip players without KTC value
                if not row.get('ktc_value'):
                    continue

                # Calculate edge metrics
                edge_data = self._calculate_player_edge(row)
                row.update(edge_data)
                data.append(row)

            df = pd.DataFrame(data)

            if df.empty:
                return df

            # Calculate positional ranks
            df = self._add_positional_ranks(df)

            # Calculate final edge score
            df['edge_score'] = df.apply(self._calculate_edge_score, axis=1)

            # Determine signal
            df['signal'] = df['edge_score'].apply(self._edge_to_signal)

            # Sort by edge score
            df = df.sort_values('edge_score', ascending=False)

            return df

    def _calculate_player_edge(self, row: Dict) -> Dict:
        """Calculate edge metrics for a single player."""
        position = row.get('position', '')
        ppg = row.get('ppg', 0) or 0
        ktc_value = row.get('ktc_value', 0) or 1  # Avoid division by zero
        age = row.get('age')

        # Production efficiency (points per KTC dollar)
        production_efficiency = (ppg * 1000) / ktc_value if ktc_value > 0 else 0

        # Expected KTC value based on production
        base_value_per_ppg = self.VALUE_PER_PPG.get(position, 400)
        age_mult = self._get_age_multiplier(position, age)
        production_value = ppg * base_value_per_ppg * age_mult

        # Value gap (positive = undervalued, negative = overvalued)
        value_gap = production_value - ktc_value
        value_gap_pct = (value_gap / ktc_value * 100) if ktc_value > 0 else 0

        # Production tier
        benchmarks = self.POSITION_PPG_BENCHMARKS.get(position, {})
        if ppg >= benchmarks.get('elite', 999):
            production_tier = 'ELITE'
        elif ppg >= benchmarks.get('starter', 999):
            production_tier = 'STARTER'
        elif ppg >= benchmarks.get('average', 999):
            production_tier = 'AVERAGE'
        else:
            production_tier = 'REPLACEMENT'

        return {
            'production_efficiency': round(production_efficiency, 2),
            'production_value': round(production_value, 0),
            'value_gap': round(value_gap, 0),
            'value_gap_pct': round(value_gap_pct, 1),
            'production_tier': production_tier,
            'age_multiplier': round(age_mult, 2),
        }

    def _get_age_multiplier(self, position: str, age: Optional[int]) -> float:
        """Get age-based value multiplier."""
        if age is None:
            return 1.0

        age_map = self.AGE_MULTIPLIERS.get(position, {})

        # Find closest age in map
        if age in age_map:
            return age_map[age]

        # Extrapolate for ages outside range
        ages = sorted(age_map.keys())
        if age < ages[0]:
            return age_map[ages[0]] * 1.05  # Slight premium for very young
        if age > ages[-1]:
            return age_map[ages[-1]] * 0.5  # Heavy discount for old

        # Interpolate
        for i, a in enumerate(ages[:-1]):
            if ages[i] < age < ages[i + 1]:
                ratio = (age - ages[i]) / (ages[i + 1] - ages[i])
                return age_map[ages[i]] * (1 - ratio) + age_map[ages[i + 1]] * ratio

        return 1.0

    def _add_positional_ranks(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add positional rank columns."""
        df['ppg_rank'] = df.groupby('position')['ppg'].rank(ascending=False, method='min')
        df['ktc_rank'] = df.groupby('position')['ktc_value'].rank(ascending=False, method='min')
        df['rank_gap'] = df['ktc_rank'] - df['ppg_rank']  # Positive = undervalued
        return df

    def _calculate_edge_score(self, row) -> float:
        """
        Calculate composite edge score (-100 to +100).

        Components:
        - Value gap percentage (40%)
        - Rank gap (30%)
        - Production efficiency (20%)
        - Age trajectory (10%)
        """
        value_gap_pct = row.get('value_gap_pct', 0)
        rank_gap = row.get('rank_gap', 0)
        prod_eff = row.get('production_efficiency', 0)
        age_mult = row.get('age_multiplier', 1.0)

        # Normalize components to -50 to +50 range
        # Value gap: cap at +/- 50%
        value_component = max(min(value_gap_pct * 0.8, 40), -40)

        # Rank gap: ~2.5 points per rank discrepancy, capped
        rank_component = max(min(rank_gap * 2.5, 30), -30)

        # Production efficiency: centered around 1.0, scaled
        eff_component = max(min((prod_eff - 1.0) * 10, 20), -20)

        # Age trajectory: bonus/penalty based on age curve
        age_component = max(min((age_mult - 1.0) * 30, 10), -10)

        edge_score = value_component + rank_component + eff_component + age_component

        return round(edge_score, 1)

    def _edge_to_signal(self, edge_score: float) -> str:
        """Convert edge score to buy/sell signal."""
        if edge_score >= 30:
            return 'STRONG_BUY'
        elif edge_score >= 15:
            return 'BUY'
        elif edge_score >= -15:
            return 'HOLD'
        elif edge_score >= -30:
            return 'SELL'
        else:
            return 'STRONG_SELL'

    # =========================================================================
    # SPECIALIZED FINDERS
    # =========================================================================

    def find_buy_targets(
        self,
        position: Optional[str] = None,
        limit: int = 20,
        min_edge: float = 15
    ) -> pd.DataFrame:
        """Find best buy targets based on 2025 production."""
        df = self.calculate_production_edge()

        if df.empty:
            return df

        # Filter to buys
        df = df[df['edge_score'] >= min_edge]

        if position:
            df = df[df['position'] == position]

        columns = ['player', 'position', 'team', 'age', 'games', 'ppg',
                   'ktc_value', 'value_gap', 'ppg_rank', 'ktc_rank',
                   'edge_score', 'signal', 'production_tier']

        return df.head(limit)[[c for c in columns if c in df.columns]]

    def find_sell_candidates(
        self,
        position: Optional[str] = None,
        limit: int = 20,
        max_edge: float = -15
    ) -> pd.DataFrame:
        """Find sell candidates underperforming their value."""
        df = self.calculate_production_edge()

        if df.empty:
            return df

        # Filter to sells
        df = df[df['edge_score'] <= max_edge]

        if position:
            df = df[df['position'] == position]

        df = df.sort_values('edge_score')

        columns = ['player', 'position', 'team', 'age', 'games', 'ppg',
                   'ktc_value', 'value_gap', 'ppg_rank', 'ktc_rank',
                   'edge_score', 'signal', 'production_tier']

        return df.head(limit)[[c for c in columns if c in df.columns]]

    def find_usage_risers(self, min_snap_increase: float = 10) -> pd.DataFrame:
        """Find players with increasing snap share (breakout candidates)."""
        query = """
        MATCH (p:Player)-[:HAD_SNAPS]->(sc:SnapCount)
        WHERE sc.season = 2025 AND sc.position IN ['RB', 'WR', 'TE']
        WITH p, collect({week: sc.week, pct: sc.offense_pct}) as snaps
        WHERE size(snaps) >= 4
        WITH p, snaps,
             [s IN snaps WHERE s.week <= 4 | s.pct] as early,
             [s IN snaps WHERE s.week > 4 | s.pct] as late
        WHERE size(early) > 0 AND size(late) > 0
        WITH p,
             reduce(sum = 0.0, x IN early | sum + x) / size(early) as early_avg,
             reduce(sum = 0.0, x IN late | sum + x) / size(late) as late_avg
        WHERE late_avg > early_avg + $min_increase
        MATCH (p)-[:HAD_SEASON]->(ss:SeasonStats {season: 2025})
        RETURN p.name as player, p.position as position, p.current_team as team,
               round(early_avg, 1) as early_snap_pct, round(late_avg, 1) as late_snap_pct,
               round(late_avg - early_avg, 1) as snap_increase,
               ss.ppg_ppr as ppg,
               p.ktc_value as ktc_value
        ORDER BY snap_increase DESC
        LIMIT 20
        """

        with self.driver.session() as session:
            result = session.run(query, {'min_increase': min_snap_increase})
            data = [dict(r) for r in result]

        return pd.DataFrame(data)

    def find_efficiency_outliers(self, min_games: int = 4) -> Dict[str, pd.DataFrame]:
        """Find players with outlier efficiency (positive or negative)."""
        df = self.calculate_production_edge(min_games=min_games)

        if df.empty:
            return {'positive': pd.DataFrame(), 'negative': pd.DataFrame()}

        # Calculate z-scores for production efficiency
        df['eff_zscore'] = (df['production_efficiency'] - df['production_efficiency'].mean()) / df['production_efficiency'].std()

        positive = df[df['eff_zscore'] >= 1.5].sort_values('eff_zscore', ascending=False)
        negative = df[df['eff_zscore'] <= -1.5].sort_values('eff_zscore')

        cols = ['player', 'position', 'team', 'ppg', 'ktc_value',
                'production_efficiency', 'eff_zscore', 'edge_score', 'signal']

        return {
            'positive': positive[[c for c in cols if c in positive.columns]].head(15),
            'negative': negative[[c for c in cols if c in negative.columns]].head(15)
        }

    # =========================================================================
    # PLAYER-SPECIFIC ANALYSIS
    # =========================================================================

    def get_player_edge_report(self, player_name: str) -> Dict:
        """Get detailed edge analysis for a specific player."""
        query = """
        MATCH (p:Player)-[:HAD_SEASON]->(ss:SeasonStats {season: 2025})
        WHERE p.name =~ $pattern
        OPTIONAL MATCH (p)-[:HAD_WEEK]->(ws:WeeklyStats {season: 2025})
        WITH p, ss, collect(ws) as weeks ORDER BY ws.week
        RETURN p.name as player,
               p.position as position,
               p.current_team as team,
               p.age as age,
               p.ktc_value as ktc_sf,
               p.ktc_value as ktc_1qb,
               ss.games as games,
               ss.ppg_ppr as ppg,
               ss.total_fantasy_points_ppr as total_points,
               ss.targets as targets,
               ss.receptions as receptions,
               ss.receiving_yards as rec_yards,
               ss.rushing_yards as rush_yards,
               ss.carries as carries,
               [w IN weeks | {week: w.week, points: w.fantasy_points_ppr}] as weekly_points
        LIMIT 1
        """

        with self.driver.session() as session:
            result = session.run(query, {'pattern': f'(?i).*{player_name}.*'})
            record = result.single()

            if not record:
                return {'error': f'Player not found: {player_name}'}

            row = dict(record)

        # Calculate edge metrics
        row['ktc_value'] = row.get('ktc_sf')
        edge_data = self._calculate_player_edge(row)
        row.update(edge_data)

        # Get positional context
        position = row.get('position', '')
        ppg = row.get('ppg', 0)

        pos_query = """
        MATCH (ss:SeasonStats {season: 2025, position: $position})
        WHERE ss.games >= 3
        WITH ss ORDER BY ss.ppg_ppr DESC
        WITH collect(ss.player_name) as rankings, collect(ss.ppg_ppr) as ppgs
        RETURN rankings, ppgs
        """

        with self.driver.session() as session:
            pos_result = session.run(pos_query, {'position': position})
            pos_record = pos_result.single()

            if pos_record:
                rankings = pos_record['rankings']
                ppgs = pos_record['ppgs']
                try:
                    player_idx = rankings.index(row['player'])
                    row['ppg_rank'] = player_idx + 1
                    row['position_context'] = {
                        'rank': player_idx + 1,
                        'total_players': len(rankings),
                        'top_5_avg': sum(ppgs[:5]) / 5 if len(ppgs) >= 5 else None,
                        'position_avg': sum(ppgs) / len(ppgs) if ppgs else None
                    }
                except ValueError:
                    row['ppg_rank'] = None
                    row['position_context'] = None

        # Weekly trend analysis
        weekly_points = row.get('weekly_points', [])
        if weekly_points and len(weekly_points) >= 4:
            points = [w['points'] for w in weekly_points if w.get('points') is not None]
            if len(points) >= 4:
                first_half = points[:len(points)//2]
                second_half = points[len(points)//2:]
                row['trend'] = {
                    'first_half_avg': round(sum(first_half) / len(first_half), 1),
                    'second_half_avg': round(sum(second_half) / len(second_half), 1),
                    'momentum': 'RISING' if sum(second_half)/len(second_half) > sum(first_half)/len(first_half) * 1.1 else
                               'FALLING' if sum(second_half)/len(second_half) < sum(first_half)/len(first_half) * 0.9 else
                               'STABLE'
                }

        # Calculate final edge score
        edge_score = self._calculate_edge_score(row)
        row['edge_score'] = edge_score
        row['signal'] = self._edge_to_signal(edge_score)

        # Generate recommendation
        row['recommendation'] = self._generate_recommendation(row)

        return row

    def _generate_recommendation(self, row: Dict) -> str:
        """Generate natural language recommendation."""
        signal = row.get('signal', 'HOLD')
        player = row.get('player', 'Unknown')
        position = row.get('position', '')
        ppg = row.get('ppg', 0)
        ktc_value = row.get('ktc_value', 0)
        value_gap = row.get('value_gap', 0)
        production_tier = row.get('production_tier', '')
        age = row.get('age')
        trend = row.get('trend', {})

        if signal == 'STRONG_BUY':
            rec = f"STRONG BUY: {player} is significantly undervalued. "
            rec += f"Producing at {production_tier} level ({ppg:.1f} PPG) but priced {abs(value_gap):.0f} below production value. "
            if trend.get('momentum') == 'RISING':
                rec += "Trending up makes this even more attractive."

        elif signal == 'BUY':
            rec = f"BUY: {player} offers good value. "
            rec += f"Production ({ppg:.1f} PPG) exceeds market valuation by {abs(value_gap):.0f}. "
            if age and position in ['RB', 'WR'] and age <= 25:
                rec += "Youth provides additional upside."

        elif signal == 'SELL':
            rec = f"SELL: {player} is overvalued relative to production. "
            rec += f"At {ppg:.1f} PPG ({production_tier}), value exceeds production by {abs(value_gap):.0f}. "
            if trend.get('momentum') == 'FALLING':
                rec += "Declining trend adds urgency to sell."

        elif signal == 'STRONG_SELL':
            rec = f"STRONG SELL: {player} is significantly overvalued. "
            rec += f"Production ({ppg:.1f} PPG) doesn't support current valuation. "
            rec += f"Gap of {abs(value_gap):.0f} suggests price regression coming."

        else:  # HOLD
            rec = f"HOLD: {player} is fairly valued at current production level. "
            rec += f"{ppg:.1f} PPG ({production_tier}) aligns with market price."

        return rec

    # =========================================================================
    # UPDATE NEO4J
    # =========================================================================

    def update_player_edge_scores(self) -> int:
        """Calculate and store edge scores on Player nodes."""
        df = self.calculate_production_edge()

        if df.empty:
            logger.warning("No production edge data to update")
            return 0

        count = 0
        with self.driver.session() as session:
            for _, row in df.iterrows():
                try:
                    # Match by name since sleeper_id may not be set
                    result = session.run("""
                        MATCH (p:Player)-[:HAD_SEASON]->(ss:SeasonStats {season: 2025})
                        WHERE toLower(p.name) = toLower($player_name)
                        SET p.production_edge_score = $edge_score,
                            p.production_signal = $signal,
                            p.ppg_2025 = $ppg,
                            p.production_efficiency = $efficiency,
                            p.value_gap_2025 = $value_gap,
                            p.edge_updated_at = datetime()
                        RETURN count(p) as updated
                    """, {
                        'player_name': row.get('player'),
                        'edge_score': row.get('edge_score'),
                        'signal': row.get('signal'),
                        'ppg': row.get('ppg'),
                        'efficiency': row.get('production_efficiency'),
                        'value_gap': row.get('value_gap')
                    })
                    updated = result.single()['updated']
                    if updated > 0:
                        count += 1
                except Exception as e:
                    logger.warning(f"Error updating edge for {row.get('player')}: {e}")

        logger.info(f"Updated edge scores for {count} players")
        return count


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description='Calculate 2025 production edge scores')
    parser.add_argument('--player', type=str, help='Get edge report for specific player')
    parser.add_argument('--buys', action='store_true', help='Show buy targets')
    parser.add_argument('--sells', action='store_true', help='Show sell candidates')
    parser.add_argument('--update', action='store_true', help='Update edge scores in Neo4j')
    parser.add_argument('--position', type=str, help='Filter by position')

    args = parser.parse_args()

    calc = ProductionEdgeCalculator()

    try:
        if args.player:
            print(f"\nEdge Report: {args.player}")
            print("=" * 60)
            report = calc.get_player_edge_report(args.player)
            if 'error' in report:
                print(report['error'])
            else:
                print(f"Player: {report['player']} ({report['position']}) - {report['team']}")
                print(f"Age: {report.get('age')}")
                print(f"Games: {report.get('games')}")
                print(f"\n2025 Production:")
                print(f"  PPG (PPR): {report.get('ppg', 0):.1f}")
                print(f"  Total Points: {report.get('total_points', 0):.1f}")
                print(f"  Tier: {report.get('production_tier')}")
                print(f"\nValuation:")
                print(f"  KTC Value: {report.get('ktc_value', 0):,.0f}")
                print(f"  Production Value: {report.get('production_value', 0):,.0f}")
                print(f"  Value Gap: {report.get('value_gap', 0):+,.0f}")
                print(f"\nEdge Score: {report.get('edge_score', 0):+.1f}")
                print(f"Signal: {report.get('signal')}")
                print(f"\nRecommendation: {report.get('recommendation')}")

        elif args.buys:
            print("\nBuy Targets (2025 Production Edge)")
            print("=" * 80)
            df = calc.find_buy_targets(position=args.position)
            if not df.empty:
                print(df.to_string(index=False))
            else:
                print("No buy targets found")

        elif args.sells:
            print("\nSell Candidates (2025 Production Edge)")
            print("=" * 80)
            df = calc.find_sell_candidates(position=args.position)
            if not df.empty:
                print(df.to_string(index=False))
            else:
                print("No sell candidates found")

        elif args.update:
            count = calc.update_player_edge_scores()
            print(f"Updated edge scores for {count} players")

        else:
            print("\n2025 Production Edge Analysis")
            print("=" * 80)
            df = calc.calculate_production_edge()
            if not df.empty:
                cols = ['player', 'position', 'team', 'games', 'ppg',
                        'ktc_value', 'value_gap', 'edge_score', 'signal']
                print(df.head(30)[[c for c in cols if c in df.columns]].to_string(index=False))
            else:
                print("No 2025 production data available")

    finally:
        calc.close()
