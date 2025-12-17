"""
Novel Valuation Framework for Dynasty Edge
From: NOVEL_VALUATION_FRAMEWORK.md

Implements 8 advanced valuation concepts:
1. Opportunity Flow Networks
2. Career Trajectory Graphs
3. Chemistry Quantification Index (CQI)
4. Scheme Fit Matrix
5. Market Momentum & Sentiment Cycles
6. Injury Cascade Modeling
7. Positional Ecosystem Modeling
8. Graph Centrality (PageRank)
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class CareerStage:
    """Represents a stage in a player's career trajectory."""
    position: str
    age_bucket: str  # "21-23", "24-26", etc.
    production_tier: str  # "Elite", "WR1", "WR2", "WR3", "Depth"
    situation_quality: str  # "Great", "Good", "Average", "Poor"


@dataclass
class ChemistryScore:
    """QB-WR chemistry quantification."""
    target_quality_differential: float
    trust_score: float
    depth_preference: float
    contested_confidence: float
    chemistry_index: float
    percentile: int


@dataclass
class DynastyEdgeScore:
    """Final composite dynasty valuation."""
    base_ktc: int
    trajectory_multiplier: float
    chemistry_adjustment: float
    scheme_fit_multiplier: float
    ecosystem_factor: float
    market_timing_signal: float
    injury_risk_discount: float
    opportunity_premium: float
    final_score: int
    components: Dict[str, float]


# =============================================================================
# 1. Opportunity Flow Networks
# =============================================================================

class OpportunityFlowAnalyzer:
    """Analyzes opportunity flow and cannibalization between players."""

    def __init__(self, driver):
        self.driver = driver

    def create_opportunity_pools(self, season: int = 2025):
        """Create OpportunityPool nodes for each team."""
        query = """
        MATCH (p:Player)-[:PLAYS_FOR]->(t:Team)
        WHERE p.position IN ['QB', 'RB', 'WR', 'TE']
        WITH t,
             sum(CASE WHEN p.position IN ['WR', 'TE'] THEN COALESCE(p.targets, 0) ELSE 0 END) as total_targets,
             sum(CASE WHEN p.position = 'RB' THEN COALESCE(p.carries, 0) ELSE 0 END) as total_carries,
             sum(COALESCE(p.air_yards, 0)) as total_air_yards
        MERGE (op:OpportunityPool {team_abbr: t.team_abbr, season: $season})
        SET op.total_targets = total_targets,
            op.total_carries = total_carries,
            op.total_air_yards = total_air_yards,
            op.updated_at = datetime()
        RETURN count(op) as pools_created
        """
        with self.driver.session() as session:
            result = session.run(query, {'season': season})
            count = result.single()['pools_created']
            logger.info(f"Created/updated {count} opportunity pools")
            return count

    def create_captures_opportunity_relationships(self, season: int = 2025):
        """Create CAPTURES_OPPORTUNITY relationships."""
        query = """
        MATCH (p:Player)-[:PLAYS_FOR]->(t:Team)
        MATCH (op:OpportunityPool {team_abbr: t.team_abbr, season: $season})
        WHERE p.position IN ['RB', 'WR', 'TE']
        WITH p, op,
             CASE WHEN op.total_targets > 0 THEN toFloat(COALESCE(p.targets, 0)) / op.total_targets ELSE 0 END as target_share,
             CASE WHEN op.total_carries > 0 THEN toFloat(COALESCE(p.carries, 0)) / op.total_carries ELSE 0 END as carry_share,
             CASE WHEN op.total_air_yards > 0 THEN toFloat(COALESCE(p.air_yards, 0)) / op.total_air_yards ELSE 0 END as air_yards_share
        MERGE (p)-[c:CAPTURES_OPPORTUNITY]->(op)
        SET c.target_share = target_share,
            c.carry_share = carry_share,
            c.air_yards_share = air_yards_share,
            c.season = $season
        RETURN count(c) as relationships_created
        """
        with self.driver.session() as session:
            result = session.run(query, {'season': season})
            count = result.single()['relationships_created']
            logger.info(f"Created {count} CAPTURES_OPPORTUNITY relationships")
            return count

    def calculate_cannibalization(self, team: str, season: int = 2025) -> pd.DataFrame:
        """Calculate opportunity elasticity between teammates.

        When Player A's targets increase by 10%, how much do B, C, D decrease?
        """
        query = """
        MATCH (p1:Player)-[:PLAYS_FOR]->(t:Team {team_abbr: $team})
        MATCH (p2:Player)-[:PLAYS_FOR]->(t)
        WHERE p1.position IN ['WR', 'TE', 'RB']
          AND p2.position IN ['WR', 'TE', 'RB']
          AND p1.gsis_id <> p2.gsis_id
        MATCH (p1)-[c1:CAPTURES_OPPORTUNITY]->(op:OpportunityPool)
        MATCH (p2)-[c2:CAPTURES_OPPORTUNITY]->(op)
        WHERE op.season = $season
        WITH p1, p2, c1.target_share as share1, c2.target_share as share2,
             // Elasticity: if p1 share goes up 10%, p2 share goes down by elasticity * 10%
             -1.0 * (c2.target_share / (1 - c1.target_share)) as elasticity
        RETURN p1.name as player_a,
               p1.position as pos_a,
               p2.name as player_b,
               p2.position as pos_b,
               share1 as player_a_share,
               share2 as player_b_share,
               elasticity
        ORDER BY ABS(elasticity) DESC
        """
        with self.driver.session() as session:
            result = session.run(query, {'team': team, 'season': season})
            return pd.DataFrame([dict(r) for r in result])

    def project_redistribution(self, leaving_player: str, season: int = 2025) -> pd.DataFrame:
        """Project opportunity redistribution if a player leaves/gets injured."""
        query = """
        MATCH (leaving:Player {name: $player})-[c:CAPTURES_OPPORTUNITY]->(op:OpportunityPool)
        WHERE op.season = $season
        MATCH (teammate:Player)-[tc:CAPTURES_OPPORTUNITY]->(op)
        WHERE teammate <> leaving
        WITH leaving, teammate, op, c, tc,
             // Redistribute proportionally to existing shares
             tc.target_share + (c.target_share * tc.target_share / (1 - c.target_share)) as projected_share
        RETURN teammate.name as player,
               teammate.position as position,
               tc.target_share as current_share,
               projected_share,
               projected_share - tc.target_share as share_gain,
               (projected_share - tc.target_share) / tc.target_share * 100 as pct_increase
        ORDER BY share_gain DESC
        """
        with self.driver.session() as session:
            result = session.run(query, {'player': leaving_player, 'season': season})
            return pd.DataFrame([dict(r) for r in result])


# =============================================================================
# 2. Career Trajectory Graphs
# =============================================================================

class CareerTrajectoryAnalyzer:
    """Models player career paths and predicts trajectories."""

    # Age buckets by position
    AGE_BUCKETS = {
        'QB': ['21-24', '25-28', '29-32', '33-36', '37+'],
        'RB': ['21-22', '23-24', '25-26', '27-28', '29+'],
        'WR': ['21-23', '24-26', '27-29', '30-32', '33+'],
        'TE': ['21-24', '25-27', '28-30', '31-33', '34+']
    }

    PRODUCTION_TIERS = ['Elite', 'Tier1', 'Tier2', 'Tier3', 'Depth', 'Injured']

    def __init__(self, driver):
        self.driver = driver

    def get_age_bucket(self, position: str, age: int) -> str:
        """Get age bucket for position and age."""
        buckets = self.AGE_BUCKETS.get(position, self.AGE_BUCKETS['WR'])
        for bucket in buckets:
            if '+' in bucket:
                min_age = int(bucket.replace('+', ''))
                if age >= min_age:
                    return bucket
            else:
                min_age, max_age = map(int, bucket.split('-'))
                if min_age <= age <= max_age:
                    return bucket
        return buckets[-1]

    def get_production_tier(self, position: str, fantasy_ppg: float) -> str:
        """Classify production tier based on fantasy PPG."""
        thresholds = {
            'QB': {'Elite': 22, 'Tier1': 18, 'Tier2': 14, 'Tier3': 10},
            'RB': {'Elite': 18, 'Tier1': 14, 'Tier2': 10, 'Tier3': 6},
            'WR': {'Elite': 18, 'Tier1': 14, 'Tier2': 10, 'Tier3': 6},
            'TE': {'Elite': 14, 'Tier1': 10, 'Tier2': 7, 'Tier3': 4}
        }
        pos_thresholds = thresholds.get(position, thresholds['WR'])

        for tier, threshold in pos_thresholds.items():
            if fantasy_ppg >= threshold:
                return tier
        return 'Depth'

    def create_career_stage_nodes(self):
        """Create all possible CareerStage nodes."""
        query = """
        UNWIND $stages as stage
        MERGE (cs:CareerStage {
            stage_id: stage.position + '_' + stage.age_bucket + '_' + stage.production_tier + '_' + stage.situation
        })
        SET cs.position = stage.position,
            cs.age_bucket = stage.age_bucket,
            cs.production_tier = stage.production_tier,
            cs.situation_quality = stage.situation
        """
        stages = []
        situations = ['Great', 'Good', 'Average', 'Poor']

        for position in ['QB', 'RB', 'WR', 'TE']:
            for bucket in self.AGE_BUCKETS[position]:
                for tier in self.PRODUCTION_TIERS:
                    for situation in situations:
                        stages.append({
                            'position': position,
                            'age_bucket': bucket,
                            'production_tier': tier,
                            'situation': situation
                        })

        with self.driver.session() as session:
            session.run(query, {'stages': stages})
            logger.info(f"Created {len(stages)} CareerStage nodes")
            return len(stages)

    def assign_player_stages(self, season: int = 2025):
        """Assign players to their current career stage."""
        query = """
        MATCH (p:Player)
        WHERE p.position IN ['QB', 'RB', 'WR', 'TE'] AND p.age IS NOT NULL
        WITH p,
             // Determine age bucket
             CASE p.position
                 WHEN 'RB' THEN
                     CASE
                         WHEN p.age <= 22 THEN '21-22'
                         WHEN p.age <= 24 THEN '23-24'
                         WHEN p.age <= 26 THEN '25-26'
                         WHEN p.age <= 28 THEN '27-28'
                         ELSE '29+'
                     END
                 WHEN 'WR' THEN
                     CASE
                         WHEN p.age <= 23 THEN '21-23'
                         WHEN p.age <= 26 THEN '24-26'
                         WHEN p.age <= 29 THEN '27-29'
                         WHEN p.age <= 32 THEN '30-32'
                         ELSE '33+'
                     END
                 ELSE
                     CASE
                         WHEN p.age <= 24 THEN '21-24'
                         WHEN p.age <= 27 THEN '25-27'
                         WHEN p.age <= 30 THEN '28-30'
                         WHEN p.age <= 33 THEN '31-33'
                         ELSE '34+'
                     END
             END as age_bucket,
             // Determine production tier based on KTC value as proxy
             CASE
                 WHEN p.ktc_value > 7000 THEN 'Elite'
                 WHEN p.ktc_value > 4500 THEN 'Tier1'
                 WHEN p.ktc_value > 2500 THEN 'Tier2'
                 WHEN p.ktc_value > 1000 THEN 'Tier3'
                 ELSE 'Depth'
             END as production_tier,
             // Situation quality (simplified)
             CASE
                 WHEN p.ktc_value > 5000 AND p.age < 27 THEN 'Great'
                 WHEN p.ktc_value > 3000 THEN 'Good'
                 WHEN p.ktc_value > 1500 THEN 'Average'
                 ELSE 'Poor'
             END as situation
        MATCH (cs:CareerStage {
            position: p.position,
            age_bucket: age_bucket,
            production_tier: production_tier,
            situation_quality: situation
        })
        MERGE (p)-[r:AT_CAREER_STAGE]->(cs)
        SET r.season = $season, r.ktc_value = p.ktc_value
        RETURN count(r) as assignments
        """
        with self.driver.session() as session:
            result = session.run(query, {'season': season})
            count = result.single()['assignments']
            logger.info(f"Assigned {count} players to career stages")
            return count

    def calculate_transition_probabilities(self) -> pd.DataFrame:
        """Calculate probabilities of transitioning between career stages."""
        query = """
        // Get historical transitions
        MATCH (p:Player)-[r1:AT_CAREER_STAGE]->(cs1:CareerStage)
        MATCH (p)-[r2:AT_CAREER_STAGE]->(cs2:CareerStage)
        WHERE r2.season = r1.season + 1
        WITH cs1, cs2, count(*) as transitions
        WITH cs1, collect({to_stage: cs2.stage_id, count: transitions}) as outgoing
        UNWIND outgoing as out
        WITH cs1, out,
             reduce(total = 0, x IN outgoing | total + x.count) as total_from_stage
        RETURN cs1.stage_id as from_stage,
               cs1.position as position,
               cs1.age_bucket as age_bucket,
               cs1.production_tier as from_tier,
               out.to_stage as to_stage,
               out.count as transitions,
               toFloat(out.count) / total_from_stage as probability
        ORDER BY cs1.position, probability DESC
        """
        with self.driver.session() as session:
            result = session.run(query)
            return pd.DataFrame([dict(r) for r in result])

    def predict_trajectory(self, player_name: str, years_ahead: int = 3) -> Dict[str, Any]:
        """Predict a player's career trajectory probabilities."""
        query = """
        MATCH (p:Player {name: $name})-[:AT_CAREER_STAGE]->(cs:CareerStage)
        OPTIONAL MATCH (cs)-[t:TYPICALLY_LEADS_TO]->(next:CareerStage)
        WITH p, cs, next, t
        ORDER BY t.probability DESC
        RETURN p.name as player,
               p.age as age,
               p.position as position,
               p.ktc_value as current_ktc,
               cs.stage_id as current_stage,
               cs.production_tier as current_tier,
               collect({
                   next_stage: next.stage_id,
                   next_tier: next.production_tier,
                   probability: t.probability,
                   avg_seasons: t.avg_seasons
               })[0..5] as likely_paths
        """
        with self.driver.session() as session:
            result = session.run(query, {'name': player_name})
            record = result.single()
            if record:
                return dict(record)
            return {}


# =============================================================================
# 3. Chemistry Quantification Index (CQI)
# =============================================================================

class ChemistryAnalyzer:
    """Quantifies QB-WR chemistry from FTN charting data."""

    def __init__(self, driver):
        self.driver = driver

    def calculate_chemistry_scores(self, season: int = 2025):
        """Calculate CQI for all QB-receiver pairs."""
        query = """
        // Get QB-receiver stats
        MATCH (rec:Player)-[t:TARGETS_FROM]->(qb:Player)
        WHERE t.season = $season AND rec.position IN ['WR', 'TE']

        // Get team averages for comparison
        MATCH (teammate:Player)-[tt:TARGETS_FROM]->(qb)
        WHERE tt.season = $season AND teammate.position IN ['WR', 'TE']
        WITH qb, rec, t,
             avg(tt.catchable_rate) as team_avg_catchable,
             avg(tt.contested_rate) as team_avg_contested

        // Calculate chemistry components
        WITH qb, rec, t, team_avg_catchable, team_avg_contested,
             // Target Quality Differential
             COALESCE(t.catchable_rate, 0.7) - COALESCE(team_avg_catchable, 0.7) as target_quality_diff,
             // Trust Score (high-leverage targets)
             (COALESCE(t.red_zone_share, 0) + COALESCE(t.third_down_share, 0) + COALESCE(t.two_min_share, 0)) / 3.0 as trust_score,
             // Air yards preference
             COALESCE(t.avg_depth_of_target, 8) as depth_preference,
             // Contested confidence
             COALESCE(t.contested_rate, 0) * COALESCE(t.contested_catch_rate, 0) as contested_confidence

        // Calculate composite CQI
        WITH qb, rec, target_quality_diff, trust_score, depth_preference, contested_confidence,
             // Weighted combination
             (0.3 * (50 + target_quality_diff * 100) +
              0.25 * (trust_score * 100) +
              0.25 * (depth_preference / 15 * 100) +
              0.20 * (contested_confidence * 100)) as cqi_raw

        MERGE (rec)-[c:CHEMISTRY_WITH]->(qb)
        SET c.season = $season,
            c.target_quality_differential = target_quality_diff,
            c.trust_score = trust_score,
            c.depth_preference = depth_preference,
            c.contested_confidence = contested_confidence,
            c.cqi_score = cqi_raw

        RETURN rec.name as receiver,
               qb.name as qb,
               c.cqi_score as chemistry_index
        ORDER BY c.cqi_score DESC
        """
        with self.driver.session() as session:
            result = session.run(query, {'season': season})
            return pd.DataFrame([dict(r) for r in result])

    def get_chemistry_percentiles(self, season: int = 2025) -> pd.DataFrame:
        """Get chemistry scores with percentile rankings."""
        query = """
        MATCH (rec:Player)-[c:CHEMISTRY_WITH]->(qb:Player)
        WHERE c.season = $season
        WITH rec, qb, c,
             c.cqi_score as score
        ORDER BY score
        WITH collect({
            receiver: rec.name,
            qb: qb.name,
            position: rec.position,
            score: score
        }) as all_scores
        UNWIND range(0, size(all_scores)-1) as idx
        WITH all_scores[idx] as data, idx, size(all_scores) as total
        RETURN data.receiver as receiver,
               data.qb as qb,
               data.position as position,
               data.score as cqi_score,
               toInteger((idx + 1.0) / total * 100) as percentile
        ORDER BY percentile DESC
        """
        with self.driver.session() as session:
            result = session.run(query, {'season': season})
            return pd.DataFrame([dict(r) for r in result])

    def identify_chemistry_mismatches(self, season: int = 2025) -> pd.DataFrame:
        """Find receivers with high volume but low chemistry (regression candidates)."""
        query = """
        MATCH (rec:Player)-[c:CHEMISTRY_WITH]->(qb:Player)
        MATCH (rec)-[t:TARGETS_FROM]->(qb)
        WHERE c.season = $season AND t.season = $season
        WITH rec, qb, c.cqi_score as chemistry, t.target_share as volume
        WHERE volume > 0.15  // Significant target share
        RETURN rec.name as receiver,
               rec.position as position,
               qb.name as qb,
               volume as target_share,
               chemistry as cqi_score,
               CASE
                   WHEN chemistry > 60 AND volume > 0.2 THEN 'TRUE_ALPHA'
                   WHEN chemistry < 40 AND volume > 0.2 THEN 'REGRESSION_RISK'
                   WHEN chemistry > 60 AND volume < 0.15 THEN 'BREAKOUT_CANDIDATE'
                   ELSE 'NEUTRAL'
               END as category
        ORDER BY
            CASE
                WHEN chemistry < 40 AND volume > 0.2 THEN 1  // Most interesting
                WHEN chemistry > 60 AND volume < 0.15 THEN 2
                ELSE 3
            END,
            chemistry DESC
        """
        with self.driver.session() as session:
            result = session.run(query, {'season': season})
            return pd.DataFrame([dict(r) for r in result])


# =============================================================================
# 4. Scheme Fit Matrix
# =============================================================================

class SchemeFitAnalyzer:
    """Analyzes player-scheme fit for counterfactual valuation."""

    SCHEME_TYPES = {
        'west_coast': {
            'route_diversity': 0.8, 'separation': 0.9, 'contested': 0.3,
            'yac': 0.9, 'speed': 0.6, 'size': 0.4
        },
        'air_raid': {
            'route_diversity': 0.9, 'separation': 0.7, 'contested': 0.5,
            'yac': 0.6, 'speed': 0.8, 'size': 0.5
        },
        'shanahan': {
            'route_diversity': 0.6, 'separation': 0.6, 'contested': 0.4,
            'yac': 1.0, 'speed': 0.9, 'size': 0.5
        },
        'power_run': {
            'route_diversity': 0.4, 'separation': 0.5, 'contested': 0.7,
            'yac': 0.5, 'speed': 0.5, 'size': 0.9
        },
        'spread': {
            'route_diversity': 0.7, 'separation': 0.8, 'contested': 0.4,
            'yac': 0.7, 'speed': 0.9, 'size': 0.3
        }
    }

    def __init__(self, driver):
        self.driver = driver

    def create_scheme_nodes(self):
        """Create Scheme nodes for each scheme type."""
        query = """
        UNWIND $schemes as scheme
        MERGE (s:Scheme {scheme_id: scheme.id})
        SET s.name = scheme.name,
            s.route_diversity_weight = scheme.weights.route_diversity,
            s.separation_weight = scheme.weights.separation,
            s.contested_weight = scheme.weights.contested,
            s.yac_weight = scheme.weights.yac,
            s.speed_weight = scheme.weights.speed,
            s.size_weight = scheme.weights.size
        """
        schemes = [
            {'id': k, 'name': k.replace('_', ' ').title(), 'weights': v}
            for k, v in self.SCHEME_TYPES.items()
        ]
        with self.driver.session() as session:
            session.run(query, {'schemes': schemes})
            logger.info(f"Created {len(schemes)} Scheme nodes")

    def create_skill_profiles(self, season: int = 2025):
        """Create SkillProfile nodes from player metrics."""
        query = """
        MATCH (p:Player)
        WHERE p.position IN ['WR', 'TE', 'RB']
        WITH p,
             // Normalize metrics to 0-1 scale
             COALESCE(p.route_diversity, 0.5) as route_diversity,
             COALESCE(p.separation, 0.5) as separation,
             COALESCE(p.contested_catch_rate, 0.5) as contested,
             COALESCE(p.yac_per_reception, 5) / 10.0 as yac,
             CASE WHEN p.forty_time IS NOT NULL
                  THEN 1 - (p.forty_time - 4.2) / 0.8
                  ELSE 0.5 END as speed,
             CASE WHEN p.height IS NOT NULL AND p.weight IS NOT NULL
                  THEN (p.height * p.weight) / 20000.0
                  ELSE 0.5 END as size
        MERGE (sp:SkillProfile {player_id: p.gsis_id})
        SET sp.route_diversity = route_diversity,
            sp.separation = separation,
            sp.contested_catch = contested,
            sp.yac_ability = yac,
            sp.speed = speed,
            sp.size = size
        MERGE (p)-[:HAS_PROFILE]->(sp)
        RETURN count(sp) as profiles_created
        """
        with self.driver.session() as session:
            result = session.run(query, {'season': season})
            count = result.single()['profiles_created']
            logger.info(f"Created {count} skill profiles")
            return count

    def calculate_scheme_fits(self):
        """Calculate fit scores for all player-scheme combinations."""
        query = """
        MATCH (p:Player)-[:HAS_PROFILE]->(sp:SkillProfile)
        MATCH (s:Scheme)
        WITH p, sp, s,
             // Dot product of skill profile and scheme requirements
             sp.route_diversity * s.route_diversity_weight +
             sp.separation * s.separation_weight +
             sp.contested_catch * s.contested_weight +
             sp.yac_ability * s.yac_weight +
             sp.speed * s.speed_weight +
             sp.size * s.size_weight as fit_score
        MERGE (sp)-[f:FITS]->(s)
        SET f.fit_score = fit_score,
            f.normalized_score = fit_score /
                (s.route_diversity_weight + s.separation_weight + s.contested_weight +
                 s.yac_weight + s.speed_weight + s.size_weight)
        RETURN count(f) as fits_calculated
        """
        with self.driver.session() as session:
            result = session.run(query)
            count = result.single()['fits_calculated']
            logger.info(f"Calculated {count} scheme fit scores")
            return count

    def find_scheme_trapped_players(self) -> pd.DataFrame:
        """Find players who would be worth more in a different scheme."""
        query = """
        MATCH (p:Player)-[:HAS_PROFILE]->(sp:SkillProfile)
        MATCH (p)-[:PLAYS_FOR]->(t:Team)-[:RUNS_SCHEME]->(current:Scheme)
        MATCH (sp)-[current_fit:FITS]->(current)
        MATCH (sp)-[better_fit:FITS]->(better:Scheme)
        WHERE better <> current AND better_fit.normalized_score > current_fit.normalized_score + 0.1
        WITH p, current, current_fit.normalized_score as current_score,
             better, better_fit.normalized_score as better_score,
             better_fit.normalized_score - current_fit.normalized_score as upside
        ORDER BY upside DESC
        RETURN p.name as player,
               p.position as position,
               p.ktc_value as current_ktc,
               current.name as current_scheme,
               current_score,
               better.name as ideal_scheme,
               better_score,
               upside,
               toInteger(p.ktc_value * (1 + upside)) as scheme_optimized_value
        LIMIT 25
        """
        with self.driver.session() as session:
            result = session.run(query)
            return pd.DataFrame([dict(r) for r in result])


# =============================================================================
# 5. Market Momentum & Cycles
# =============================================================================

class MarketMomentumAnalyzer:
    """Detects market cycles and momentum in player values."""

    CYCLE_PHASES = ['discovery', 'hype', 'peak', 'disillusionment', 'recovery', 'plateau']

    def __init__(self, driver):
        self.driver = driver

    def detect_market_cycle(self, gsis_id: str, lookback_days: int = 90) -> Dict[str, Any]:
        """Detect current market cycle phase for a player."""
        query = """
        MATCH (p:Player {gsis_id: $gsis_id})-[:HAD_SNAPSHOT]->(s:Snapshot)
        WHERE s.date >= datetime() - duration({days: $days})
        WITH p, s ORDER BY s.date
        WITH p, collect(s.ktc_value) as values, collect(s.date) as dates
        WHERE size(values) > 7
        WITH p, values, dates,
             // Calculate momentum (recent vs older)
             reduce(recent = 0.0, i IN range(size(values)-7, size(values)-1) |
                    recent + values[i]) / 7.0 as recent_avg,
             reduce(older = 0.0, i IN range(0, 6) |
                    older + values[i]) / 7.0 as older_avg
        WITH p, values,
             (recent_avg - older_avg) / older_avg as momentum,
             stdev(values) as volatility
        RETURN p.name as player,
               p.ktc_value as current_value,
               momentum,
               volatility,
               CASE
                   WHEN momentum > 0.15 THEN 'HYPE'
                   WHEN momentum < -0.15 THEN 'DISILLUSIONMENT'
                   WHEN momentum > 0.05 THEN 'RECOVERY'
                   WHEN momentum < -0.05 THEN 'DECLINING'
                   ELSE 'PLATEAU'
               END as cycle_phase,
               CASE
                   WHEN momentum < -0.15 THEN 'BUY_SIGNAL'
                   WHEN momentum > 0.15 THEN 'SELL_SIGNAL'
                   ELSE 'HOLD'
               END as market_signal
        """
        with self.driver.session() as session:
            result = session.run(query, {'gsis_id': gsis_id, 'days': lookback_days})
            record = result.single()
            return dict(record) if record else {}

    def find_buy_opportunities(self, min_ktc: int = 2000) -> pd.DataFrame:
        """Find players in 'disillusionment' phase (buy low)."""
        query = """
        MATCH (p:Player)-[:HAD_SNAPSHOT]->(s:Snapshot)
        WHERE p.ktc_value >= $min_ktc
          AND p.position IN ['QB', 'RB', 'WR', 'TE']
          AND s.date >= datetime() - duration({days: 60})
        WITH p, s ORDER BY s.date
        WITH p, collect(s.ktc_value) as values
        WHERE size(values) > 14
        WITH p, values,
             reduce(recent = 0.0, i IN range(size(values)-7, size(values)-1) |
                    recent + values[i]) / 7.0 as recent_avg,
             reduce(older = 0.0, i IN range(0, 6) |
                    older + values[i]) / 7.0 as older_avg
        WITH p, (recent_avg - older_avg) / older_avg as momentum
        WHERE momentum < -0.10  // Value dropped 10%+
        RETURN p.name as player,
               p.position as position,
               p.age as age,
               p.ktc_value as current_ktc,
               momentum * 100 as pct_change,
               'DISILLUSIONMENT' as phase,
               'BUY' as signal
        ORDER BY momentum ASC
        LIMIT 20
        """
        with self.driver.session() as session:
            result = session.run(query, {'min_ktc': min_ktc})
            return pd.DataFrame([dict(r) for r in result])


# =============================================================================
# 6. Injury Cascade Modeling
# =============================================================================

class InjuryCascadeAnalyzer:
    """Models cascade effects of injuries through the roster."""

    def __init__(self, driver):
        self.driver = driver

    def calculate_injury_beta(self) -> pd.DataFrame:
        """Calculate how much each player's value swings based on teammate injuries."""
        query = """
        // Find backup players
        MATCH (backup:Player)-[:COMPETES_WITH]-(starter:Player)
        WHERE starter.ktc_value > backup.ktc_value
          AND starter.position = backup.position
          AND starter.position IN ['RB', 'WR', 'TE']
        WITH backup, starter,
             starter.ktc_value - backup.ktc_value as value_gap,
             // Assume injured starter would lose 70% value temporarily
             (starter.ktc_value * 0.7) - backup.ktc_value as upside_if_injured,
             COALESCE(starter.injury_history, 0) / 10.0 as injury_risk
        WITH backup, starter, value_gap, upside_if_injured, injury_risk,
             upside_if_injured * injury_risk as expected_injury_value
        RETURN backup.name as handcuff,
               backup.position as position,
               backup.ktc_value as current_value,
               starter.name as starter,
               starter.ktc_value as starter_value,
               upside_if_injured,
               injury_risk,
               expected_injury_value as injury_beta
        ORDER BY expected_injury_value DESC
        LIMIT 30
        """
        with self.driver.session() as session:
            result = session.run(query)
            return pd.DataFrame([dict(r) for r in result])

    def model_injury_cascade(self, injured_player: str) -> pd.DataFrame:
        """Model cascade effects if a specific player gets injured."""
        query = """
        MATCH (injured:Player {name: $player})-[:PLAYS_FOR]->(t:Team)

        // Direct beneficiaries (same position)
        OPTIONAL MATCH (backup:Player)-[:COMPETES_WITH]-(injured)
        WHERE backup.position = injured.position

        // Indirect beneficiaries (other positions benefit from scheme changes)
        OPTIONAL MATCH (teammate:Player)-[:PLAYS_FOR]->(t)
        WHERE teammate <> injured AND teammate.position IN ['WR', 'TE', 'RB']

        WITH injured, t, collect(DISTINCT backup) as backups, collect(DISTINCT teammate) as teammates

        UNWIND backups + teammates as beneficiary
        WITH injured, beneficiary,
             CASE
                 WHEN beneficiary.position = injured.position THEN 'DIRECT_BACKUP'
                 ELSE 'INDIRECT_BENEFICIARY'
             END as benefit_type,
             CASE
                 WHEN beneficiary.position = injured.position
                 THEN injured.ktc_value * 0.5  // Direct backup gets most
                 ELSE injured.ktc_value * 0.1  // Others get less
             END as value_gain_estimate

        RETURN beneficiary.name as player,
               beneficiary.position as position,
               beneficiary.ktc_value as current_value,
               benefit_type,
               toInteger(value_gain_estimate) as value_gain_if_injured,
               injured.name as if_injured
        ORDER BY value_gain_estimate DESC
        """
        with self.driver.session() as session:
            result = session.run(query, {'player': injured_player})
            return pd.DataFrame([dict(r) for r in result])


# =============================================================================
# 7. Positional Ecosystem Modeling
# =============================================================================

class EcosystemAnalyzer:
    """Models team offensive ecosystems."""

    def __init__(self, driver):
        self.driver = driver

    def create_ecosystem_nodes(self, season: int = 2025):
        """Create OffensiveEcosystem nodes for each team."""
        query = """
        MATCH (t:Team)<-[:PLAYS_FOR]-(p:Player)
        WHERE p.position IN ['QB', 'RB', 'WR', 'TE']
        WITH t, collect(p) as players,
             sum(COALESCE(p.fantasy_points_season, 0)) as total_fpts,
             max(COALESCE(p.fantasy_points_season, 0)) as alpha_fpts,
             count(p) as player_count
        WITH t, players, total_fpts, alpha_fpts, player_count,
             alpha_fpts / total_fpts as alpha_dependency,
             // Gini coefficient approximation for concentration
             stdev([p IN players | p.fantasy_points_season]) /
             avg([p IN players | p.fantasy_points_season]) as concentration

        MERGE (eco:OffensiveEcosystem {team_abbr: t.team_abbr, season: $season})
        SET eco.total_fantasy_points = total_fpts,
            eco.alpha_dependency = alpha_dependency,
            eco.point_concentration = COALESCE(concentration, 0),
            eco.robustness = 1 - alpha_dependency,
            eco.depth_score = (player_count - 1) / 10.0

        // Create ROLE_IN relationships
        WITH eco, players
        UNWIND players as p
        WITH eco, p,
             CASE
                 WHEN p.fantasy_points_season = max([x IN players | x.fantasy_points_season])
                 THEN 'alpha'
                 WHEN p.fantasy_points_season >= 0.7 * max([x IN players | x.fantasy_points_season])
                 THEN 'beta'
                 WHEN p.fantasy_points_season >= 0.4 * max([x IN players | x.fantasy_points_season])
                 THEN 'gamma'
                 ELSE 'specialist'
             END as role

        MERGE (p)-[r:ROLE_IN]->(eco)
        SET r.role = role,
            r.ecosystem_share = p.fantasy_points_season / eco.total_fantasy_points

        RETURN count(eco) as ecosystems_created
        """
        with self.driver.session() as session:
            result = session.run(query, {'season': season})
            logger.info(f"Created ecosystem nodes")

    def get_ecosystem_analysis(self) -> pd.DataFrame:
        """Get ecosystem robustness analysis for all teams."""
        query = """
        MATCH (eco:OffensiveEcosystem)
        OPTIONAL MATCH (p:Player)-[r:ROLE_IN]->(eco)
        WHERE r.role = 'alpha'
        RETURN eco.team_abbr as team,
               eco.total_fantasy_points as total_fpts,
               eco.alpha_dependency as alpha_dependency,
               eco.robustness as robustness,
               eco.depth_score as depth_score,
               p.name as alpha_player,
               CASE
                   WHEN eco.robustness > 0.7 THEN 'ROBUST'
                   WHEN eco.robustness > 0.5 THEN 'MODERATE'
                   ELSE 'FRAGILE'
               END as ecosystem_health
        ORDER BY eco.robustness DESC
        """
        with self.driver.session() as session:
            result = session.run(query)
            return pd.DataFrame([dict(r) for r in result])

    def get_ecosystem_adjusted_values(self) -> pd.DataFrame:
        """Calculate ecosystem-adjusted player values."""
        query = """
        MATCH (p:Player)-[r:ROLE_IN]->(eco:OffensiveEcosystem)
        WHERE p.ktc_value > 1000
        WITH p, eco, r,
             // Ecosystem multiplier
             (1 + eco.robustness * 0.1) *
             (1 - eco.alpha_dependency * 0.15) *
             (1 + eco.depth_score * 0.05) as eco_multiplier
        RETURN p.name as player,
               p.position as position,
               p.ktc_value as base_ktc,
               eco.team_abbr as team,
               r.role as role,
               eco.robustness as ecosystem_robustness,
               eco_multiplier,
               toInteger(p.ktc_value * eco_multiplier) as ecosystem_adjusted_value,
               toInteger(p.ktc_value * eco_multiplier) - p.ktc_value as value_delta
        ORDER BY value_delta DESC
        LIMIT 50
        """
        with self.driver.session() as session:
            result = session.run(query)
            return pd.DataFrame([dict(r) for r in result])


# =============================================================================
# 8. Dynasty Edge Score (Composite)
# =============================================================================

class DynastyEdgeCalculator:
    """Calculates the composite Dynasty Edge Score."""

    def __init__(self, driver):
        self.driver = driver

    def calculate_dynasty_edge_score(self, gsis_id: str) -> Optional[DynastyEdgeScore]:
        """Calculate comprehensive Dynasty Edge Score for a player."""
        query = """
        MATCH (p:Player {gsis_id: $gsis_id})

        // Career trajectory
        OPTIONAL MATCH (p)-[:AT_CAREER_STAGE]->(cs:CareerStage)

        // Chemistry
        OPTIONAL MATCH (p)-[chem:CHEMISTRY_WITH]->(qb:Player)

        // Scheme fit
        OPTIONAL MATCH (p)-[:HAS_PROFILE]->(sp:SkillProfile)
        OPTIONAL MATCH (p)-[:PLAYS_FOR]->(t:Team)-[:RUNS_SCHEME]->(scheme:Scheme)
        OPTIONAL MATCH (sp)-[fit:FITS]->(scheme)

        // Ecosystem
        OPTIONAL MATCH (p)-[role:ROLE_IN]->(eco:OffensiveEcosystem)

        // Market momentum
        OPTIONAL MATCH (p)-[:HAD_SNAPSHOT]->(snap:Snapshot)
        WHERE snap.date >= datetime() - duration({days: 30})
        WITH p, cs, chem, fit, role, eco,
             collect(snap.ktc_value) as recent_values

        // Calculate components
        WITH p,
             // Base value
             p.ktc_value as base_ktc,

             // Trajectory multiplier (based on career stage)
             CASE
                 WHEN cs.production_tier = 'Elite' AND cs.age_bucket CONTAINS '21' THEN 1.15
                 WHEN cs.production_tier = 'Elite' THEN 1.05
                 WHEN cs.production_tier = 'Tier1' AND cs.age_bucket CONTAINS '21' THEN 1.10
                 WHEN cs.production_tier = 'Tier1' THEN 1.02
                 WHEN cs.age_bucket CONTAINS '29' OR cs.age_bucket CONTAINS '30' THEN 0.90
                 ELSE 1.0
             END as trajectory_mult,

             // Chemistry adjustment
             1 + (COALESCE(chem.cqi_score, 50) - 50) * 0.005 as chemistry_adj,

             // Scheme fit
             COALESCE(fit.normalized_score, 0.5) as scheme_fit_mult,

             // Ecosystem factor
             COALESCE(eco.robustness, 0.5) as ecosystem_factor,

             // Market timing (momentum)
             CASE
                 WHEN size(recent_values) > 7 THEN
                     CASE
                         WHEN (recent_values[-1] - recent_values[0]) / recent_values[0] < -0.1
                         THEN 1.05  // Buy signal
                         WHEN (recent_values[-1] - recent_values[0]) / recent_values[0] > 0.15
                         THEN 0.95  // Sell signal
                         ELSE 1.0
                     END
                 ELSE 1.0
             END as market_signal,

             // Injury discount (placeholder)
             CASE WHEN p.injury_history > 5 THEN 0.95 ELSE 1.0 END as injury_discount

        RETURN p.name as player,
               p.position as position,
               base_ktc,
               trajectory_mult,
               chemistry_adj,
               scheme_fit_mult,
               ecosystem_factor,
               market_signal,
               injury_discount,
               toInteger(base_ktc * trajectory_mult * chemistry_adj *
                        (0.5 + scheme_fit_mult * 0.5) *
                        (0.8 + ecosystem_factor * 0.2) *
                        market_signal / injury_discount) as dynasty_edge_score
        """
        with self.driver.session() as session:
            result = session.run(query, {'gsis_id': gsis_id})
            record = result.single()
            if record:
                data = dict(record)
                return DynastyEdgeScore(
                    base_ktc=data['base_ktc'],
                    trajectory_multiplier=data['trajectory_mult'],
                    chemistry_adjustment=data['chemistry_adj'],
                    scheme_fit_multiplier=data['scheme_fit_mult'],
                    ecosystem_factor=data['ecosystem_factor'],
                    market_timing_signal=data['market_signal'],
                    injury_risk_discount=data['injury_discount'],
                    opportunity_premium=0,  # Calculated separately
                    final_score=data['dynasty_edge_score'],
                    components=data
                )
            return None

    def calculate_all_dynasty_edge_scores(self) -> pd.DataFrame:
        """Calculate Dynasty Edge Score for all relevant players."""
        query = """
        MATCH (p:Player)
        WHERE p.ktc_value > 1000 AND p.position IN ['QB', 'RB', 'WR', 'TE']

        // Career trajectory
        OPTIONAL MATCH (p)-[:AT_CAREER_STAGE]->(cs:CareerStage)

        // Chemistry
        OPTIONAL MATCH (p)-[chem:CHEMISTRY_WITH]->(qb:Player)

        // Scheme fit
        OPTIONAL MATCH (p)-[:HAS_PROFILE]->(sp:SkillProfile)
        OPTIONAL MATCH (p)-[:PLAYS_FOR]->(t:Team)-[:RUNS_SCHEME]->(scheme:Scheme)
        OPTIONAL MATCH (sp)-[fit:FITS]->(scheme)

        // Ecosystem
        OPTIONAL MATCH (p)-[role:ROLE_IN]->(eco:OffensiveEcosystem)

        // Calculate components
        WITH p, cs, chem, fit, eco,
             p.ktc_value as base_ktc,
             CASE
                 WHEN cs.production_tier = 'Elite' AND p.age < 25 THEN 1.15
                 WHEN cs.production_tier = 'Elite' THEN 1.05
                 WHEN cs.production_tier = 'Tier1' AND p.age < 25 THEN 1.10
                 WHEN p.age >= 29 THEN 0.90
                 ELSE 1.0
             END as trajectory_mult,
             1 + (COALESCE(chem.cqi_score, 50) - 50) * 0.005 as chemistry_adj,
             COALESCE(fit.normalized_score, 0.5) as scheme_fit_mult,
             COALESCE(eco.robustness, 0.5) as ecosystem_factor

        WITH p, base_ktc, trajectory_mult, chemistry_adj, scheme_fit_mult, ecosystem_factor,
             toInteger(base_ktc * trajectory_mult * chemistry_adj *
                      (0.5 + scheme_fit_mult * 0.5) *
                      (0.8 + ecosystem_factor * 0.2)) as dynasty_edge_score

        RETURN p.gsis_id as gsis_id,
               p.name as player,
               p.position as position,
               p.age as age,
               base_ktc,
               dynasty_edge_score,
               dynasty_edge_score - base_ktc as edge_delta,
               (dynasty_edge_score - base_ktc) * 100.0 / base_ktc as edge_pct,
               CASE
                   WHEN dynasty_edge_score > base_ktc * 1.1 THEN 'STRONG_BUY'
                   WHEN dynasty_edge_score > base_ktc * 1.05 THEN 'BUY'
                   WHEN dynasty_edge_score < base_ktc * 0.9 THEN 'STRONG_SELL'
                   WHEN dynasty_edge_score < base_ktc * 0.95 THEN 'SELL'
                   ELSE 'HOLD'
               END as edge_signal
        ORDER BY edge_pct DESC
        """
        with self.driver.session() as session:
            result = session.run(query)
            return pd.DataFrame([dict(r) for r in result])

    def update_player_edge_scores(self):
        """Update Player nodes with Dynasty Edge Scores."""
        query = """
        MATCH (p:Player)
        WHERE p.ktc_value > 1000 AND p.position IN ['QB', 'RB', 'WR', 'TE']

        OPTIONAL MATCH (p)-[:AT_CAREER_STAGE]->(cs:CareerStage)
        OPTIONAL MATCH (p)-[chem:CHEMISTRY_WITH]->(qb:Player)
        OPTIONAL MATCH (p)-[:HAS_PROFILE]->(sp:SkillProfile)
        OPTIONAL MATCH (p)-[:PLAYS_FOR]->(t:Team)-[:RUNS_SCHEME]->(scheme:Scheme)
        OPTIONAL MATCH (sp)-[fit:FITS]->(scheme)
        OPTIONAL MATCH (p)-[role:ROLE_IN]->(eco:OffensiveEcosystem)

        WITH p, cs, chem, fit, eco,
             p.ktc_value as base_ktc,
             CASE
                 WHEN cs.production_tier = 'Elite' AND p.age < 25 THEN 1.15
                 WHEN cs.production_tier = 'Elite' THEN 1.05
                 WHEN cs.production_tier = 'Tier1' AND p.age < 25 THEN 1.10
                 WHEN p.age >= 29 THEN 0.90
                 ELSE 1.0
             END as trajectory_mult,
             1 + (COALESCE(chem.cqi_score, 50) - 50) * 0.005 as chemistry_adj,
             COALESCE(fit.normalized_score, 0.5) as scheme_fit_mult,
             COALESCE(eco.robustness, 0.5) as ecosystem_factor

        WITH p, base_ktc, trajectory_mult, chemistry_adj, scheme_fit_mult, ecosystem_factor,
             toInteger(base_ktc * trajectory_mult * chemistry_adj *
                      (0.5 + scheme_fit_mult * 0.5) *
                      (0.8 + ecosystem_factor * 0.2)) as dynasty_edge_score

        SET p.dynasty_edge_score = dynasty_edge_score,
            p.edge_delta = dynasty_edge_score - base_ktc,
            p.edge_signal = CASE
                WHEN dynasty_edge_score > base_ktc * 1.1 THEN 'STRONG_BUY'
                WHEN dynasty_edge_score > base_ktc * 1.05 THEN 'BUY'
                WHEN dynasty_edge_score < base_ktc * 0.9 THEN 'STRONG_SELL'
                WHEN dynasty_edge_score < base_ktc * 0.95 THEN 'SELL'
                ELSE 'HOLD'
            END,
            p.edge_updated = datetime()

        RETURN count(p) as players_updated
        """
        with self.driver.session() as session:
            result = session.run(query)
            count = result.single()['players_updated']
            logger.info(f"Updated Dynasty Edge Score for {count} players")
            return count


# =============================================================================
# Master Framework Class
# =============================================================================

class NovelValuationFramework:
    """Master class for running the complete Novel Valuation Framework."""

    def __init__(self, driver):
        self.driver = driver
        self.opportunity = OpportunityFlowAnalyzer(driver)
        self.trajectory = CareerTrajectoryAnalyzer(driver)
        self.chemistry = ChemistryAnalyzer(driver)
        self.scheme = SchemeFitAnalyzer(driver)
        self.momentum = MarketMomentumAnalyzer(driver)
        self.injury = InjuryCascadeAnalyzer(driver)
        self.ecosystem = EcosystemAnalyzer(driver)
        self.edge = DynastyEdgeCalculator(driver)

    def initialize_framework(self, season: int = 2025):
        """Initialize all framework components."""
        logger.info("Initializing Novel Valuation Framework...")

        # Create foundational nodes
        logger.info("Creating career stage nodes...")
        self.trajectory.create_career_stage_nodes()

        logger.info("Creating scheme nodes...")
        self.scheme.create_scheme_nodes()

        logger.info("Creating opportunity pools...")
        self.opportunity.create_opportunity_pools(season)

        logger.info("Creating skill profiles...")
        self.scheme.create_skill_profiles(season)

        logger.info("Framework initialization complete")

    def run_full_analysis(self, season: int = 2025) -> Dict[str, pd.DataFrame]:
        """Run complete novel valuation analysis."""
        results = {}

        logger.info("Running full Novel Valuation analysis...")

        # Opportunity flow
        logger.info("Analyzing opportunity flow...")
        self.opportunity.create_captures_opportunity_relationships(season)

        # Career trajectories
        logger.info("Assigning career stages...")
        self.trajectory.assign_player_stages(season)

        # Chemistry
        logger.info("Calculating chemistry scores...")
        results['chemistry'] = self.chemistry.calculate_chemistry_scores(season)
        results['chemistry_mismatches'] = self.chemistry.identify_chemistry_mismatches(season)

        # Scheme fit
        logger.info("Calculating scheme fits...")
        self.scheme.calculate_scheme_fits()
        results['scheme_trapped'] = self.scheme.find_scheme_trapped_players()

        # Ecosystems
        logger.info("Analyzing team ecosystems...")
        self.ecosystem.create_ecosystem_nodes(season)
        results['ecosystems'] = self.ecosystem.get_ecosystem_analysis()

        # Market momentum
        logger.info("Finding buy opportunities...")
        results['buy_opportunities'] = self.momentum.find_buy_opportunities()

        # Injury cascades
        logger.info("Calculating injury beta...")
        results['injury_beta'] = self.injury.calculate_injury_beta()

        # Dynasty Edge Scores
        logger.info("Calculating Dynasty Edge Scores...")
        self.edge.update_player_edge_scores()
        results['dynasty_edge'] = self.edge.calculate_all_dynasty_edge_scores()

        logger.info("Novel Valuation analysis complete")
        return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from neo4j import GraphDatabase

    # Test with local Neo4j
    driver = GraphDatabase.driver("bolt://localhost:7687", auth=None)

    framework = NovelValuationFramework(driver)
    framework.initialize_framework()
    results = framework.run_full_analysis()

    # Print sample results
    print("\n=== Dynasty Edge Top 20 ===")
    print(results['dynasty_edge'].head(20).to_string())

    driver.close()
