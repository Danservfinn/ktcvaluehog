"""
College Feature Engineering Module
===================================
Calculates dynasty-relevant features from college football data.

Key Features:
- Dominator Rating: Share of team's receiving production
- Breakout Age: Age when first dominating at college level
- Speed Score: Weight-adjusted 40-yard dash
- Burst Score: Explosive athleticism composite
- Agility Score: Quickness composite
- RAS: Relative Athletic Score
- Prospect Score: Overall dynasty prospect rating

Reference: Research shows these metrics correlate with NFL success for skill positions.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from neo4j import GraphDatabase

logger = logging.getLogger(__name__)


class CollegeFeatureEngineer:
    """
    Calculate advanced features for college prospects.

    All calculations are based on research correlating college
    metrics to NFL dynasty fantasy success.
    """

    # Athletic testing percentiles by position (based on historical combine data)
    COMBINE_PERCENTILES = {
        'WR': {
            'forty': {'p25': 4.55, 'p50': 4.48, 'p75': 4.40, 'elite': 4.35},
            'vertical': {'p25': 33.0, 'p50': 35.5, 'p75': 38.0, 'elite': 40.0},
            'broad': {'p25': 118, 'p50': 123, 'p75': 128, 'elite': 132},
            'three_cone': {'p25': 7.10, 'p50': 6.95, 'p75': 6.80, 'elite': 6.65},
            'shuttle': {'p25': 4.35, 'p50': 4.22, 'p75': 4.10, 'elite': 4.00}
        },
        'RB': {
            'forty': {'p25': 4.55, 'p50': 4.50, 'p75': 4.45, 'elite': 4.40},
            'vertical': {'p25': 33.0, 'p50': 35.0, 'p75': 37.0, 'elite': 39.0},
            'broad': {'p25': 116, 'p50': 120, 'p75': 124, 'elite': 128},
            'three_cone': {'p25': 7.15, 'p50': 7.00, 'p75': 6.85, 'elite': 6.70},
            'shuttle': {'p25': 4.35, 'p50': 4.25, 'p75': 4.15, 'elite': 4.05}
        },
        'TE': {
            'forty': {'p25': 4.75, 'p50': 4.65, 'p75': 4.55, 'elite': 4.50},
            'vertical': {'p25': 31.0, 'p50': 33.5, 'p75': 36.0, 'elite': 38.0},
            'broad': {'p25': 114, 'p50': 119, 'p75': 124, 'elite': 128},
            'three_cone': {'p25': 7.25, 'p50': 7.10, 'p75': 6.95, 'elite': 6.80},
            'shuttle': {'p25': 4.45, 'p50': 4.35, 'p75': 4.25, 'elite': 4.15}
        },
        'QB': {
            'forty': {'p25': 4.90, 'p50': 4.75, 'p75': 4.60, 'elite': 4.50},
            'vertical': {'p25': 29.0, 'p50': 32.0, 'p75': 35.0, 'elite': 37.0},
            'broad': {'p25': 106, 'p50': 112, 'p75': 118, 'elite': 122},
            'three_cone': {'p25': 7.30, 'p50': 7.10, 'p75': 6.90, 'elite': 6.75},
            'shuttle': {'p25': 4.45, 'p50': 4.30, 'p75': 4.15, 'elite': 4.05}
        }
    }

    # Prospect score weights by position
    PROSPECT_WEIGHTS = {
        'WR': {
            'dominator_rating': 0.25,
            'breakout_age': 0.20,
            'recruiting_rating': 0.15,
            'speed_score': 0.15,
            'athleticism': 0.15,
            'production_trajectory': 0.10
        },
        'RB': {
            'dominator_rating': 0.15,
            'breakout_age': 0.15,
            'recruiting_rating': 0.20,
            'speed_score': 0.20,
            'athleticism': 0.15,
            'production_trajectory': 0.15
        },
        'TE': {
            'dominator_rating': 0.20,
            'breakout_age': 0.25,
            'recruiting_rating': 0.15,
            'speed_score': 0.15,
            'athleticism': 0.15,
            'production_trajectory': 0.10
        },
        'QB': {
            'recruiting_rating': 0.25,
            'production_trajectory': 0.25,
            'athleticism': 0.15,
            'breakout_age': 0.20,
            'draft_capital': 0.15
        }
    }

    def __init__(self, driver=None):
        """
        Initialize feature engineer.

        Args:
            driver: Neo4j driver instance
        """
        self.driver = driver

    # =========================================================================
    # DOMINATOR RATING
    # =========================================================================

    def calculate_dominator_rating(
        self,
        rec_yards: float,
        rec_tds: float,
        team_rec_yards: float,
        team_rec_tds: float
    ) -> Optional[float]:
        """
        Calculate Dominator Rating - share of team's receiving production.

        Formula: (Player Rec Yards / Team Rec Yards + Player Rec TDs / Team Rec TDs) / 2 * 100

        Alternatively: (rec_yards + rec_tds * 20) / (team_rec_yards + team_rec_tds * 20)

        Thresholds:
        - Elite: 35%+
        - Good: 25-35%
        - Average: 15-25%
        - Concern: <15%

        Args:
            rec_yards: Player's receiving yards
            rec_tds: Player's receiving TDs
            team_rec_yards: Team's total receiving yards
            team_rec_tds: Team's total receiving TDs

        Returns:
            Dominator rating as percentage (0-100)
        """
        if not team_rec_yards or team_rec_yards == 0:
            return None

        # Use yardage-weighted formula
        player_value = rec_yards + (rec_tds * 20)
        team_value = team_rec_yards + (team_rec_tds * 20)

        if team_value == 0:
            return None

        return (player_value / team_value) * 100

    def calculate_rushing_dominator(
        self,
        rush_yards: float,
        rush_tds: float,
        team_rush_yards: float,
        team_rush_tds: float
    ) -> Optional[float]:
        """Calculate rushing dominator rating for RBs."""
        if not team_rush_yards or team_rush_yards == 0:
            return None

        player_value = rush_yards + (rush_tds * 20)
        team_value = team_rush_yards + (team_rush_tds * 20)

        if team_value == 0:
            return None

        return (player_value / team_value) * 100

    # =========================================================================
    # BREAKOUT AGE
    # =========================================================================

    def calculate_breakout_age(
        self,
        birth_date: datetime,
        season_stats: List[Dict]
    ) -> Optional[Dict]:
        """
        Calculate Breakout Age - age at first dominating college season.

        Breakout defined as:
        - WR/TE: 20%+ dominator rating
        - RB: 15%+ rushing dominator
        - QB: N/A (different criteria)

        Lower breakout age correlates with NFL success.

        Args:
            birth_date: Player's birth date
            season_stats: List of {season, dominator_rating, age} dicts

        Returns:
            Dict with breakout_age, breakout_season, dominator_rating
        """
        if not birth_date or not season_stats:
            return None

        # Sort by season
        sorted_stats = sorted(season_stats, key=lambda x: x.get('season', 0))

        for stats in sorted_stats:
            dom_rating = stats.get('dominator_rating', 0)
            if dom_rating and dom_rating >= 20:
                # Calculate age at start of that season
                season = stats.get('season', 2024)
                # Assume season starts in September
                season_start = datetime(season, 9, 1)
                age = (season_start - birth_date).days / 365.25

                return {
                    'breakout_age': round(age, 2),
                    'breakout_season': season,
                    'breakout_dominator': round(dom_rating, 1),
                    'college_year': stats.get('college_year', 'Unknown')
                }

        return None

    # =========================================================================
    # ATHLETIC SCORES
    # =========================================================================

    def calculate_speed_score(
        self,
        weight: float,
        forty_time: float
    ) -> Optional[float]:
        """
        Calculate Bill Kelley's Speed Score.

        Formula: (Weight * 200) / (40 Time ^ 4)

        This normalizes 40 time by weight - a 4.4 at 225 lbs is more
        impressive than a 4.4 at 185 lbs.

        Thresholds:
        - Elite: 105+
        - Good: 95-105
        - Average: 85-95
        - Below: <85

        Args:
            weight: Player weight in pounds
            forty_time: 40-yard dash time in seconds

        Returns:
            Speed score
        """
        if not weight or not forty_time or forty_time <= 0:
            return None

        return (weight * 200) / (forty_time ** 4)

    def calculate_burst_score(
        self,
        vertical: float,
        broad_jump: float,
        position: str = 'WR'
    ) -> Optional[float]:
        """
        Calculate Burst Score - explosive power composite.

        Combines vertical jump and broad jump into percentile-based score.

        Args:
            vertical: Vertical jump in inches
            broad_jump: Broad jump in inches
            position: Player position for percentile lookup

        Returns:
            Burst score (0-100 scale)
        """
        if not vertical and not broad_jump:
            return None

        position = position.upper() if position else 'WR'
        if position not in self.COMBINE_PERCENTILES:
            position = 'WR'  # Default

        scores = []

        if vertical:
            vert_pct = self._calculate_percentile(
                vertical,
                self.COMBINE_PERCENTILES[position]['vertical'],
                higher_is_better=True
            )
            scores.append(vert_pct)

        if broad_jump:
            broad_pct = self._calculate_percentile(
                broad_jump,
                self.COMBINE_PERCENTILES[position]['broad'],
                higher_is_better=True
            )
            scores.append(broad_pct)

        return np.mean(scores) if scores else None

    def calculate_agility_score(
        self,
        three_cone: float,
        shuttle: float,
        position: str = 'WR'
    ) -> Optional[float]:
        """
        Calculate Agility Score - quickness composite.

        Combines 3-cone and shuttle into percentile-based score.

        Args:
            three_cone: 3-cone drill time in seconds
            shuttle: Shuttle time in seconds
            position: Player position for percentile lookup

        Returns:
            Agility score (0-100 scale)
        """
        if not three_cone and not shuttle:
            return None

        position = position.upper() if position else 'WR'
        if position not in self.COMBINE_PERCENTILES:
            position = 'WR'

        scores = []

        if three_cone:
            cone_pct = self._calculate_percentile(
                three_cone,
                self.COMBINE_PERCENTILES[position]['three_cone'],
                higher_is_better=False
            )
            scores.append(cone_pct)

        if shuttle:
            shuttle_pct = self._calculate_percentile(
                shuttle,
                self.COMBINE_PERCENTILES[position]['shuttle'],
                higher_is_better=False
            )
            scores.append(shuttle_pct)

        return np.mean(scores) if scores else None

    def calculate_athleticism_score(
        self,
        forty: float,
        vertical: float,
        broad_jump: float,
        three_cone: float,
        shuttle: float,
        bench: float,
        position: str = 'WR',
        weight: float = None
    ) -> Dict[str, float]:
        """
        Calculate comprehensive athleticism composite (RAS-style).

        Returns breakdown and overall score.

        Args:
            forty: 40-yard dash
            vertical: Vertical jump
            broad_jump: Broad jump
            three_cone: 3-cone drill
            shuttle: Shuttle
            bench: Bench press reps
            position: Player position
            weight: Player weight (for speed score)

        Returns:
            Dict with component scores and overall athleticism
        """
        results = {
            'speed_score': None,
            'burst_score': None,
            'agility_score': None,
            'athleticism_score': None,
            'combine_grade': None
        }

        # Speed Score
        if weight and forty:
            results['speed_score'] = self.calculate_speed_score(weight, forty)

        # Burst Score
        results['burst_score'] = self.calculate_burst_score(vertical, broad_jump, position)

        # Agility Score
        results['agility_score'] = self.calculate_agility_score(three_cone, shuttle, position)

        # Calculate 40-yard percentile
        forty_pct = None
        if forty and position in self.COMBINE_PERCENTILES:
            forty_pct = self._calculate_percentile(
                forty,
                self.COMBINE_PERCENTILES[position]['forty'],
                higher_is_better=False
            )

        # Overall Athleticism Score (weighted average)
        components = []
        weights = []

        if forty_pct is not None:
            components.append(forty_pct)
            weights.append(0.25)

        if results['burst_score'] is not None:
            components.append(results['burst_score'])
            weights.append(0.35)

        if results['agility_score'] is not None:
            components.append(results['agility_score'])
            weights.append(0.25)

        if results['speed_score'] is not None:
            # Normalize speed score to 0-100 (typical range 70-120)
            normalized_speed = min(100, max(0, (results['speed_score'] - 70) * 2))
            components.append(normalized_speed)
            weights.append(0.15)

        if components:
            # Weighted average
            total_weight = sum(weights[:len(components)])
            results['athleticism_score'] = sum(
                c * w for c, w in zip(components, weights)
            ) / total_weight

            # Grade
            if results['athleticism_score'] >= 90:
                results['combine_grade'] = 'ELITE'
            elif results['athleticism_score'] >= 75:
                results['combine_grade'] = 'GOOD'
            elif results['athleticism_score'] >= 50:
                results['combine_grade'] = 'AVERAGE'
            else:
                results['combine_grade'] = 'BELOW_AVERAGE'

        return results

    def _calculate_percentile(
        self,
        value: float,
        benchmarks: Dict[str, float],
        higher_is_better: bool = True
    ) -> float:
        """Calculate percentile score based on benchmark values."""
        p25 = benchmarks['p25']
        p50 = benchmarks['p50']
        p75 = benchmarks['p75']
        elite = benchmarks['elite']

        if higher_is_better:
            if value >= elite:
                return 95 + (value - elite) / (elite * 0.1) * 5
            elif value >= p75:
                return 75 + (value - p75) / (elite - p75) * 20
            elif value >= p50:
                return 50 + (value - p50) / (p75 - p50) * 25
            elif value >= p25:
                return 25 + (value - p25) / (p50 - p25) * 25
            else:
                return max(0, 25 * value / p25)
        else:
            # Lower is better (like 40 time)
            if value <= elite:
                return 95 + (elite - value) / (elite * 0.05) * 5
            elif value <= p75:
                return 75 + (p75 - value) / (p75 - elite) * 20
            elif value <= p50:
                return 50 + (p50 - value) / (p50 - p75) * 25
            elif value <= p25:
                return 25 + (p25 - value) / (p25 - p50) * 25
            else:
                return max(0, 25 * p25 / value)

    # =========================================================================
    # PROSPECT SCORE
    # =========================================================================

    def calculate_prospect_score(
        self,
        position: str,
        dominator_rating: float = None,
        breakout_age: float = None,
        recruiting_stars: int = None,
        recruiting_rating: float = None,
        speed_score: float = None,
        athleticism_score: float = None,
        production_trajectory: float = None,
        draft_capital: float = None
    ) -> Dict:
        """
        Calculate overall Prospect Score - composite dynasty ranking.

        Weights vary by position based on research correlations.

        Args:
            position: Player position
            dominator_rating: College dominator rating
            breakout_age: Age at first 20% dominator season
            recruiting_stars: 247 star rating (1-5)
            recruiting_rating: 247 composite rating
            speed_score: Bill Kelley speed score
            athleticism_score: Composite athletic score
            production_trajectory: Year-over-year production trend
            draft_capital: Expected/actual draft position value

        Returns:
            Dict with prospect_score, component_scores, grade
        """
        position = position.upper() if position else 'WR'
        if position not in self.PROSPECT_WEIGHTS:
            position = 'WR'

        weights = self.PROSPECT_WEIGHTS[position]
        components = {}

        # Normalize each component to 0-100 scale

        # Dominator Rating (already 0-100 ish, cap at 50)
        if dominator_rating is not None and 'dominator_rating' in weights:
            components['dominator_rating'] = min(100, dominator_rating * 2.5)

        # Breakout Age (18-23 scale, lower is better)
        if breakout_age is not None and 'breakout_age' in weights:
            # 18 = 100, 23 = 0
            components['breakout_age'] = max(0, (23 - breakout_age) / 5 * 100)

        # Recruiting Rating (scale varies by source)
        if recruiting_rating is not None and 'recruiting_rating' in weights:
            # Typical range 0.8-1.0
            components['recruiting_rating'] = (recruiting_rating - 0.8) / 0.2 * 100
        elif recruiting_stars is not None and 'recruiting_rating' in weights:
            components['recruiting_rating'] = (recruiting_stars / 5) * 100

        # Speed Score (typical range 70-120)
        if speed_score is not None and 'speed_score' in weights:
            components['speed_score'] = min(100, max(0, (speed_score - 70) * 2))

        # Athleticism (already 0-100)
        if athleticism_score is not None and 'athleticism' in weights:
            components['athleticism'] = athleticism_score

        # Production Trajectory (-50 to +50 typical, normalize)
        if production_trajectory is not None and 'production_trajectory' in weights:
            components['production_trajectory'] = 50 + production_trajectory

        # Draft Capital (round 1 = 100, undrafted = 20)
        if draft_capital is not None and 'draft_capital' in weights:
            components['draft_capital'] = draft_capital

        # Calculate weighted score
        total_weight = 0
        weighted_sum = 0

        for component_name, score in components.items():
            weight = weights.get(component_name, 0)
            weighted_sum += score * weight
            total_weight += weight

        if total_weight == 0:
            return {
                'prospect_score': None,
                'components': components,
                'grade': 'INSUFFICIENT_DATA'
            }

        prospect_score = weighted_sum / total_weight

        # Assign grade
        if prospect_score >= 85:
            grade = 'ELITE'
        elif prospect_score >= 70:
            grade = 'GOOD'
        elif prospect_score >= 55:
            grade = 'AVERAGE'
        elif prospect_score >= 40:
            grade = 'BELOW_AVERAGE'
        else:
            grade = 'POOR'

        return {
            'prospect_score': round(prospect_score, 1),
            'components': {k: round(v, 1) for k, v in components.items()},
            'grade': grade,
            'position': position
        }

    # =========================================================================
    # NEO4J INTEGRATION
    # =========================================================================

    def update_prospect_features(self, prospect_name: str = None):
        """
        Calculate and update all features for prospects in Neo4j.

        Args:
            prospect_name: Optional - update single prospect. If None, update all.
        """
        if self.driver is None:
            raise ValueError("Neo4j driver required")

        with self.driver.session() as session:
            # Get prospects with stats
            if prospect_name:
                where_clause = "WHERE p.name = $name"
                params = {'name': prospect_name}
            else:
                where_clause = ""
                params = {}

            # Calculate dominator ratings from stats
            session.run(f"""
                MATCH (p:Prospect)-[:HAS_COLLEGE_STATS]->(s:CollegeStats)
                {where_clause}
                WITH p, s
                WHERE s.rec_yards IS NOT NULL

                // Get team stats for the same season
                OPTIONAL MATCH (t:CollegeTeam {{name: s.team}})<-[:FOR_TEAM]-(ts:CollegeStats)
                WHERE ts.season = s.season AND ts <> s

                WITH p, s,
                     sum(ts.rec_yards) + s.rec_yards as team_rec_yards,
                     sum(ts.rec_tds) + s.rec_tds as team_rec_tds

                // Calculate dominator rating
                WITH p, s,
                     CASE WHEN team_rec_yards > 0
                          THEN ((s.rec_yards + s.rec_tds * 20.0) /
                                (team_rec_yards + team_rec_tds * 20.0)) * 100
                          ELSE null END as dominator

                SET s.dominator_rating = dominator

                WITH p, max(dominator) as peak_dominator
                SET p.peak_dominator_rating = peak_dominator
            """, **params)

            # Calculate speed scores from combine
            session.run(f"""
                MATCH (p:Prospect)-[:HAS_COMBINE]->(c:CombineResult)
                {where_clause}
                WHERE c.forty_yard IS NOT NULL AND c.weight IS NOT NULL

                WITH p, c,
                     (c.weight * 200.0) / (c.forty_yard ^ 4) as speed_score

                SET c.speed_score = speed_score,
                    p.speed_score = speed_score
            """, **params)

            # Calculate burst scores
            session.run(f"""
                MATCH (p:Prospect)-[:HAS_COMBINE]->(c:CombineResult)
                {where_clause}
                WHERE c.vertical_jump IS NOT NULL OR c.broad_jump IS NOT NULL

                WITH p, c,
                     CASE WHEN c.vertical_jump IS NOT NULL AND c.broad_jump IS NOT NULL
                          THEN (c.vertical_jump * 2 + c.broad_jump / 3) / 2
                          WHEN c.vertical_jump IS NOT NULL
                          THEN c.vertical_jump * 2
                          ELSE c.broad_jump / 3
                     END as burst_score

                SET c.burst_score = burst_score,
                    p.burst_score = burst_score
            """, **params)

            # Calculate overall athleticism score
            session.run(f"""
                MATCH (p:Prospect)-[:HAS_COMBINE]->(c:CombineResult)
                {where_clause}

                WITH p, c,
                     coalesce(c.speed_score, 0) as ss,
                     coalesce(c.burst_score, 0) as bs,
                     CASE WHEN c.three_cone IS NOT NULL
                          THEN (7.2 - c.three_cone) * 20
                          ELSE 0 END as agility

                WITH p, c, ss, bs, agility,
                     (ss * 0.3 + bs * 0.4 + agility * 0.3) as athleticism

                SET c.athleticism_score = athleticism,
                    p.athleticism_score = athleticism
            """, **params)

            # Calculate prospect score
            session.run(f"""
                MATCH (p:Prospect)
                {where_clause}

                WITH p,
                     coalesce(p.peak_dominator_rating, 0) * 2.5 as dom_component,
                     CASE WHEN p.breakout_age IS NOT NULL
                          THEN (23 - p.breakout_age) / 5 * 100
                          ELSE 50 END as age_component,
                     coalesce(p.recruiting_rating, 0.85) * 100 as recruit_component,
                     coalesce(p.athleticism_score, 50) as athletic_component

                WITH p,
                     (dom_component * 0.25 + age_component * 0.20 +
                      recruit_component * 0.15 + athletic_component * 0.15) as prospect_score

                SET p.prospect_score = prospect_score,
                    p.features_updated_at = datetime()
            """, **params)

            logger.info("Prospect features updated in Neo4j")

    def get_top_prospects(
        self,
        position: str = None,
        min_prospect_score: float = 60,
        limit: int = 50
    ) -> pd.DataFrame:
        """
        Get top prospects by prospect score from Neo4j.

        Args:
            position: Optional position filter
            min_prospect_score: Minimum prospect score threshold
            limit: Maximum results

        Returns:
            DataFrame with prospect rankings
        """
        if self.driver is None:
            raise ValueError("Neo4j driver required")

        where_clauses = ["p.prospect_score >= $min_score"]
        if position:
            where_clauses.append("p.position = $position")

        where_str = " AND ".join(where_clauses)

        query = f"""
            MATCH (p:Prospect)
            WHERE {where_str}
            OPTIONAL MATCH (p)-[:HAS_DEVY_VALUE]->(d:DevySnapshot)
            WITH p, d ORDER BY d.date DESC
            WITH p, collect(d)[0] as latest_devy

            RETURN p.name as name,
                   p.position as position,
                   p.college as college,
                   p.recruiting_class as recruit_year,
                   p.stars as stars,
                   round(p.prospect_score, 1) as prospect_score,
                   round(p.peak_dominator_rating, 1) as peak_dominator,
                   p.breakout_age as breakout_age,
                   round(p.speed_score, 1) as speed_score,
                   round(p.athleticism_score, 1) as athleticism,
                   latest_devy.ktc_devy_value as ktc_devy_value,
                   latest_devy.ktc_devy_rank as ktc_rank
            ORDER BY p.prospect_score DESC
            LIMIT $limit
        """

        with self.driver.session() as session:
            result = session.run(
                query,
                min_score=min_prospect_score,
                position=position,
                limit=limit
            )

            return pd.DataFrame([dict(r) for r in result])


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    # Test calculations without database
    engineer = CollegeFeatureEngineer()

    print("\n=== Testing Feature Calculations ===\n")

    # Test Dominator Rating
    dom = engineer.calculate_dominator_rating(1200, 12, 3000, 25)
    print(f"Dominator Rating (1200 yds, 12 TDs out of 3000/25): {dom:.1f}%")

    # Test Speed Score
    speed = engineer.calculate_speed_score(215, 4.42)
    print(f"Speed Score (215 lbs, 4.42 forty): {speed:.1f}")

    # Test Athleticism
    athleticism = engineer.calculate_athleticism_score(
        forty=4.42,
        vertical=38.0,
        broad_jump=128,
        three_cone=6.85,
        shuttle=4.15,
        bench=15,
        position='WR',
        weight=215
    )
    print(f"Athleticism: {athleticism}")

    # Test Prospect Score
    prospect = engineer.calculate_prospect_score(
        position='WR',
        dominator_rating=35,
        breakout_age=19.5,
        recruiting_stars=5,
        speed_score=105,
        athleticism_score=85
    )
    print(f"Prospect Score: {prospect}")
