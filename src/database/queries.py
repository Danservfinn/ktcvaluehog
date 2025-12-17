"""Common Cypher queries for Dynasty Edge analysis."""

from typing import List, Dict, Any, Optional
import pandas as pd

from .neo4j_client import Neo4jClient


class DynastyQueries:
    """Pre-built queries for dynasty fantasy football analysis."""

    def __init__(self, client: Neo4jClient = None):
        self.client = client or Neo4jClient()

    def get_edge_signals(self, signal: str = None, position: str = None,
                         limit: int = 50) -> pd.DataFrame:
        """Get players with edge buy/sell signals."""
        query = """
            MATCH (p:Player)
            WHERE p.edge_signal IS NOT NULL
              AND p.ktc_value_sf > 1000
        """

        if signal:
            query += f" AND p.edge_signal = '{signal}'"
        if position:
            query += f" AND p.position = '{position}'"

        query += """
            RETURN p.name as name,
                   p.position as position,
                   p.age as age,
                   p.current_team as team,
                   p.ktc_value_sf as ktc_value,
                   p.predicted_ktc_value as predicted,
                   p.value_delta_pct as delta_pct,
                   p.edge_signal as signal,
                   p.confidence_score as confidence
            ORDER BY ABS(p.value_delta_pct) DESC
            LIMIT $limit
        """

        return self.client.to_dataframe(query, {'limit': limit})

    def get_qb_receiver_connections(self, season: int = 2025,
                                     min_targets: int = 20) -> pd.DataFrame:
        """Get QB-receiver target relationships with chemistry scores."""
        query = """
            MATCH (rec:Player)-[t:TARGETS_FROM]->(qb:Player)
            WHERE t.season = $season AND t.targets >= $min_targets
            OPTIONAL MATCH (rec)-[c:CHEMISTRY_WITH]->(qb)
            RETURN rec.name as receiver,
                   rec.position as pos,
                   qb.name as qb,
                   t.targets as targets,
                   t.receptions as receptions,
                   t.yards as yards,
                   t.tds as tds,
                   t.target_share as target_share,
                   c.cqi_score as chemistry_score,
                   c.trust_score as trust_score
            ORDER BY t.targets DESC
        """

        return self.client.to_dataframe(query, {'season': season, 'min_targets': min_targets})

    def get_positional_competition(self, team: str = None, position: str = None,
                                    season: int = 2025) -> pd.DataFrame:
        """Get same-position competition on teams."""
        query = """
            MATCH (p1:Player)-[c:COMPETES_WITH]-(p2:Player)
            WHERE c.season = $season
        """

        if team:
            query += f" AND c.team_abbr = '{team}'"
        if position:
            query += f" AND c.position = '{position}'"

        query += """
              AND p1.name < p2.name  // Avoid duplicates
            RETURN c.team_abbr as team,
                   c.position as position,
                   p1.name as player1,
                   p1.ktc_value_sf as p1_value,
                   p2.name as player2,
                   p2.ktc_value_sf as p2_value,
                   c.combined_snap_share as combined_snaps
            ORDER BY c.team_abbr, c.position
        """

        return self.client.to_dataframe(query, {'season': season})

    def get_scheme_fits(self, player_gsis_id: str = None, min_fit_score: float = 0.7) -> pd.DataFrame:
        """Get player scheme fit scores."""
        query = """
            MATCH (p:Player)-[:HAS_SKILL_PROFILE]->(sp:SkillProfile)-[f:FITS]->(s:Scheme)
            WHERE f.fit_score >= $min_fit_score
        """

        if player_gsis_id:
            query += f" AND p.gsis_id = '{player_gsis_id}'"

        query += """
            RETURN p.name as player,
                   p.position as position,
                   s.team_abbr as team,
                   s.scheme_type as scheme,
                   f.fit_score as fit_score,
                   f.ceiling_boost as ceiling_boost,
                   s.pass_rate as team_pass_rate,
                   s.play_action_rate as play_action_rate
            ORDER BY f.fit_score DESC
        """

        return self.client.to_dataframe(query, {'min_fit_score': min_fit_score})

    def get_career_trajectory(self, player_gsis_id: str) -> pd.DataFrame:
        """Get player's career stage progression."""
        query = """
            MATCH (p:Player {gsis_id: $gsis_id})-[w:WAS_AT]->(cs:CareerStage)
            RETURN p.name as player,
                   w.season as season,
                   cs.stage_type as stage,
                   w.production_pct as production_pct,
                   cs.expected_production_pct as expected_pct
            ORDER BY w.season
        """

        return self.client.to_dataframe(query, {'gsis_id': player_gsis_id})

    def get_opportunity_distribution(self, team: str, season: int = 2025) -> pd.DataFrame:
        """Get opportunity distribution within a team."""
        query = """
            MATCH (p:Player)-[c:CAPTURES_OPPORTUNITY]->(op:OpportunityPool)
            WHERE op.team_abbr = $team AND op.season = $season
            RETURN p.name as player,
                   p.position as position,
                   c.target_share as target_share,
                   c.carry_share as carry_share,
                   c.snap_share as snap_share,
                   c.opportunity_score as opp_score,
                   op.total_targets as team_targets,
                   op.total_carries as team_carries
            ORDER BY c.opportunity_score DESC
        """

        return self.client.to_dataframe(query, {'team': team, 'season': season})

    def get_cannibalization_risk(self, player_gsis_id: str, season: int = 2025) -> pd.DataFrame:
        """Get players who might cannibalize opportunities."""
        query = """
            MATCH (p:Player {gsis_id: $gsis_id})-[c:CANNIBALIZES]-(comp:Player)
            WHERE c.season = $season
            RETURN p.name as player,
                   comp.name as competitor,
                   c.opportunity_type as opp_type,
                   c.elasticity as elasticity,
                   c.correlation as correlation,
                   comp.ktc_value_sf as comp_value
            ORDER BY c.elasticity DESC
        """

        return self.client.to_dataframe(query, {'gsis_id': player_gsis_id, 'season': season})

    def find_similar_players(self, player_gsis_id: str, min_similarity: float = 0.8) -> pd.DataFrame:
        """Find historically similar players for trajectory prediction."""
        query = """
            MATCH (p:Player {gsis_id: $gsis_id})-[s:SIMILAR_TO]->(comp:Player)
            WHERE s.similarity_score >= $min_similarity
            RETURN p.name as player,
                   p.age as current_age,
                   comp.name as comparison,
                   s.p2_comparison_age as comp_age_at_comparison,
                   s.similarity_score as similarity,
                   comp.ktc_value_sf as comp_current_value
            ORDER BY s.similarity_score DESC
            LIMIT 10
        """

        return self.client.to_dataframe(query, {'gsis_id': player_gsis_id, 'min_similarity': min_similarity})

    def get_value_history(self, player_gsis_id: str, days: int = 90) -> pd.DataFrame:
        """Get player's value history over time."""
        query = """
            MATCH (p:Player {gsis_id: $gsis_id})-[:HAS_VALUE_SNAPSHOT]->(vs:ValueSnapshot)
            WHERE vs.date >= date() - duration({days: $days})
            RETURN p.name as player,
                   vs.date as date,
                   vs.ktc_value_sf as ktc_value,
                   vs.predicted_value as predicted,
                   vs.delta_pct as delta_pct,
                   vs.momentum_score as momentum,
                   vs.hype_index as hype
            ORDER BY vs.date DESC
        """

        return self.client.to_dataframe(query, {'gsis_id': player_gsis_id, 'days': days})

    def get_roster_analysis(self, fantasy_team_id: str) -> Dict[str, Any]:
        """Comprehensive roster analysis for a fantasy team."""
        # Get roster with player details
        roster_query = """
            MATCH (p:Player)-[:ROSTERED_BY]->(ft:FantasyTeam {roster_id: $team_id})
            RETURN p.name as name,
                   p.position as position,
                   p.age as age,
                   p.current_team as nfl_team,
                   p.ktc_value_sf as ktc_value,
                   p.predicted_ktc_value as predicted,
                   p.edge_signal as signal
            ORDER BY p.ktc_value_sf DESC
        """

        players = self.client.run_query(roster_query, {'team_id': fantasy_team_id})

        if not players:
            return {'error': 'Team not found or no players'}

        # Calculate aggregate stats
        total_value = sum(p.get('ktc_value', 0) or 0 for p in players)
        avg_age = sum(p.get('age', 25) or 25 for p in players) / len(players)

        by_position = {}
        for p in players:
            pos = p.get('position', 'UNK')
            if pos not in by_position:
                by_position[pos] = {'count': 0, 'value': 0, 'players': []}
            by_position[pos]['count'] += 1
            by_position[pos]['value'] += p.get('ktc_value', 0) or 0
            by_position[pos]['players'].append(p)

        return {
            'total_players': len(players),
            'total_value': total_value,
            'average_age': round(avg_age, 1),
            'by_position': by_position,
            'buy_signals': [p for p in players if p.get('signal') in ['BUY', 'STRONG_BUY']],
            'sell_signals': [p for p in players if p.get('signal') in ['SELL', 'STRONG_SELL']],
            'top_10': players[:10]
        }

    def get_trade_analysis(self, give_player_ids: List[str],
                           get_player_ids: List[str]) -> Dict[str, Any]:
        """Analyze a potential trade."""
        def get_players(ids):
            query = """
                MATCH (p:Player)
                WHERE p.gsis_id IN $ids
                RETURN p.gsis_id as id,
                       p.name as name,
                       p.position as position,
                       p.age as age,
                       p.ktc_value_sf as ktc_value,
                       p.predicted_ktc_value as predicted,
                       p.edge_signal as signal
            """
            return self.client.run_query(query, {'ids': ids})

        give_players = get_players(give_player_ids)
        get_players_data = get_players(get_player_ids)

        give_value = sum(p.get('ktc_value', 0) or 0 for p in give_players)
        get_value = sum(p.get('ktc_value', 0) or 0 for p in get_players_data)

        give_predicted = sum(p.get('predicted', 0) or 0 for p in give_players)
        get_predicted = sum(p.get('predicted', 0) or 0 for p in get_players_data)

        give_avg_age = sum(p.get('age', 25) or 25 for p in give_players) / max(len(give_players), 1)
        get_avg_age = sum(p.get('age', 25) or 25 for p in get_players_data) / max(len(get_players_data), 1)

        return {
            'give': {
                'players': give_players,
                'total_ktc': give_value,
                'total_predicted': give_predicted,
                'avg_age': round(give_avg_age, 1)
            },
            'get': {
                'players': get_players_data,
                'total_ktc': get_value,
                'total_predicted': get_predicted,
                'avg_age': round(get_avg_age, 1)
            },
            'ktc_difference': get_value - give_value,
            'predicted_difference': get_predicted - give_predicted,
            'age_difference': round(give_avg_age - get_avg_age, 1),
            'recommendation': self._trade_recommendation(
                give_value, get_value,
                give_predicted, get_predicted,
                give_avg_age, get_avg_age
            )
        }

    def _trade_recommendation(self, give_ktc, get_ktc, give_pred, get_pred,
                              give_age, get_age) -> str:
        """Generate trade recommendation."""
        ktc_diff_pct = (get_ktc - give_ktc) / max(give_ktc, 1) * 100
        pred_diff_pct = (get_pred - give_pred) / max(give_pred, 1) * 100
        age_benefit = give_age - get_age  # Positive = getting younger

        score = 0
        reasons = []

        # KTC value
        if ktc_diff_pct > 10:
            score += 2
            reasons.append("Winning on KTC value")
        elif ktc_diff_pct < -10:
            score -= 2
            reasons.append("Losing on KTC value")

        # Predicted value (model-based edge)
        if pred_diff_pct > 10:
            score += 3
            reasons.append("Model predicts value gain")
        elif pred_diff_pct < -10:
            score -= 3
            reasons.append("Model predicts value loss")

        # Age
        if age_benefit > 2:
            score += 1
            reasons.append("Getting younger")
        elif age_benefit < -2:
            score -= 1
            reasons.append("Getting older")

        if score >= 3:
            return f"STRONG ACCEPT: {', '.join(reasons)}"
        elif score >= 1:
            return f"ACCEPT: {', '.join(reasons)}"
        elif score <= -3:
            return f"STRONG DECLINE: {', '.join(reasons)}"
        elif score <= -1:
            return f"DECLINE: {', '.join(reasons)}"
        else:
            return f"FAIR TRADE: {', '.join(reasons) or 'Even value exchange'}"
