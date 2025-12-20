"""League analysis algorithms service."""

import asyncio
import random
from typing import Optional
from datetime import datetime

from ..models.league import (
    PlayerAnalysis,
    PositionalStrength,
    RosterAnalysis,
    TradeTarget,
    TradeSuggestion,
    TradePartner,
    PowerRanking,
    ChampionshipSimulation,
    DynastyHealthBreakdown,
    LeagueAnalysis,
    TeamClassification,
    ScoringType,
    LineupOptimization,
    StartSitRecommendation,
)
from .sleeper import SleeperClient, get_sleeper_client
from ..database import get_neo4j_client


# Position peak ages for dynasty analysis
POSITION_PEAKS = {
    "QB": {"start": 26, "end": 34, "decline_rate": 0.03},
    "RB": {"start": 22, "end": 26, "decline_rate": 0.08},
    "WR": {"start": 24, "end": 29, "decline_rate": 0.05},
    "TE": {"start": 25, "end": 30, "decline_rate": 0.04},
}

# Draft pick values (approximate KTC values)
DRAFT_PICK_VALUES = {
    2025: {1: 7500, 2: 4000, 3: 1800, 4: 800},
    2026: {1: 6500, 2: 3500, 3: 1500, 4: 600},
    2027: {1: 5500, 2: 3000, 3: 1200, 4: 500},
}


class LeagueAnalyzer:
    """Comprehensive league analysis engine."""

    def __init__(self):
        self.sleeper = get_sleeper_client()
        self.neo4j = get_neo4j_client()
        self._player_cache: dict = {}

    async def _load_player_data(self, player_ids: list[str]) -> dict[str, dict]:
        """Load player data from Neo4j for given Sleeper IDs."""
        if not player_ids:
            return {}

        # Query Neo4j for player data
        query = """
        MATCH (p:Player)
        WHERE p.sleeper_id IN $player_ids OR p.player_id IN $player_ids
        OPTIONAL MATCH (p)-[:HAS_SEASON_STATS]->(ss:HistoricalSeasonStats)
        WHERE ss.season >= 2023
        WITH p, ss ORDER BY ss.season DESC
        WITH p, head(collect(ss)) as latest_stats
        OPTIONAL MATCH (p)-[:HAS_VALUE]->(ktc:KTCSnapshot)
        WITH p, latest_stats, ktc ORDER BY ktc.snapshot_date DESC
        WITH p, latest_stats, head(collect(ktc)) as latest_ktc
        RETURN
            p.player_id as player_id,
            p.sleeper_id as sleeper_id,
            p.name as name,
            p.position as position,
            p.team as team,
            p.age as age,
            latest_stats.ppg_ppr as ppg,
            latest_stats.games as games,
            latest_ktc.value as ktc_value,
            latest_ktc.rank as ktc_rank,
            p.projected_ppg as projected_ppg
        """

        result = self.neo4j.execute_query(query, {"player_ids": player_ids})

        player_map = {}
        for record in result:
            # Map by both sleeper_id and player_id for flexible lookup
            if record.get("sleeper_id"):
                player_map[record["sleeper_id"]] = record
            if record.get("player_id"):
                player_map[record["player_id"]] = record

        return player_map

    async def _get_all_sleeper_players(self) -> dict:
        """Get Sleeper player database for name lookups."""
        if not self._player_cache:
            self._player_cache = await self.sleeper.get_all_players()
        return self._player_cache

    def _calculate_career_phase(self, age: float, position: str) -> dict:
        """Calculate career phase and peak window."""
        peak = POSITION_PEAKS.get(position, POSITION_PEAKS["WR"])

        if age < peak["start"]:
            phase = "Pre-Peak"
            years_until_peak = peak["start"] - age
            years_in_peak = peak["end"] - peak["start"]
        elif age <= peak["end"]:
            phase = "Peak"
            years_until_peak = 0
            years_in_peak = peak["end"] - age
        else:
            phase = "Post-Peak"
            years_until_peak = 0
            years_in_peak = 0

        return {
            "phase": phase,
            "years_until_peak": int(years_until_peak),
            "years_in_peak": int(years_in_peak),
            "peak_start": peak["start"],
            "peak_end": peak["end"],
        }

    def _build_player_analysis(
        self,
        sleeper_id: str,
        neo4j_data: Optional[dict],
        sleeper_players: dict,
        is_starter: bool = False,
    ) -> PlayerAnalysis:
        """Build PlayerAnalysis from combined Sleeper and Neo4j data."""
        sleeper_player = sleeper_players.get(sleeper_id, {})

        name = (
            neo4j_data.get("name") if neo4j_data
            else f"{sleeper_player.get('first_name', '')} {sleeper_player.get('last_name', '')}".strip()
        )
        position = (
            neo4j_data.get("position") if neo4j_data
            else sleeper_player.get("position", "")
        )
        team = (
            neo4j_data.get("team") if neo4j_data
            else sleeper_player.get("team", "")
        )
        age = (
            neo4j_data.get("age") if neo4j_data
            else sleeper_player.get("age")
        )

        ktc_value = neo4j_data.get("ktc_value", 0) if neo4j_data else 0
        ppg = neo4j_data.get("ppg") if neo4j_data else None
        projected_ppg = neo4j_data.get("projected_ppg") if neo4j_data else ppg

        # Calculate career phase
        career_info = self._calculate_career_phase(age or 25, position or "WR")

        return PlayerAnalysis(
            player_id=neo4j_data.get("player_id", sleeper_id) if neo4j_data else sleeper_id,
            sleeper_id=sleeper_id,
            name=name or "Unknown",
            position=position or "UNK",
            team=team,
            age=age,
            ktc_value=ktc_value or 0,
            projected_ppg=projected_ppg,
            years_until_peak=career_info["years_until_peak"],
            years_in_peak=career_info["years_in_peak"],
            career_phase=career_info["phase"],
            is_starter=is_starter,
            is_breakout_candidate=career_info["phase"] == "Pre-Peak" and (ktc_value or 0) > 3000,
            is_sell_candidate=career_info["phase"] == "Post-Peak" and (ktc_value or 0) > 5000,
        )

    def _calculate_positional_strength(
        self, players: list[PlayerAnalysis], position: str
    ) -> PositionalStrength:
        """Calculate strength at a single position."""
        pos_players = [p for p in players if p.position == position]
        if not pos_players:
            return PositionalStrength(position=position, grade="F")

        # Sort by KTC value
        pos_players.sort(key=lambda p: p.ktc_value, reverse=True)

        # Top 2 are "starters" for most positions
        starter_count = 2 if position in ["RB", "WR"] else 1
        starters = pos_players[:starter_count]
        bench = pos_players[starter_count:]

        starter_value = sum(p.ktc_value for p in starters)
        starter_ppg = sum(p.projected_ppg or 0 for p in starters)
        depth_value = sum(p.ktc_value for p in bench)
        depth_ppg = sum(p.projected_ppg or 0 for p in bench)
        total_value = starter_value + depth_value

        # Grade based on total value (position-adjusted thresholds)
        grade_thresholds = {
            "QB": [(20000, "A+"), (15000, "A"), (12000, "B+"), (9000, "B"), (6000, "C+"), (4000, "C"), (2000, "D")],
            "RB": [(25000, "A+"), (18000, "A"), (14000, "B+"), (10000, "B"), (7000, "C+"), (4000, "C"), (2000, "D")],
            "WR": [(30000, "A+"), (22000, "A"), (16000, "B+"), (12000, "B"), (8000, "C+"), (5000, "C"), (2500, "D")],
            "TE": [(15000, "A+"), (10000, "A"), (7000, "B+"), (5000, "B"), (3500, "C+"), (2000, "C"), (1000, "D")],
        }

        thresholds = grade_thresholds.get(position, grade_thresholds["WR"])
        grade = "F"
        for threshold, g in thresholds:
            if total_value >= threshold:
                grade = g
                break

        return PositionalStrength(
            position=position,
            starter_value=starter_value,
            starter_ppg=starter_ppg,
            depth_value=depth_value,
            depth_ppg=depth_ppg,
            total_value=total_value,
            player_count=len(pos_players),
            grade=grade,
        )

    def _classify_team(
        self, dynasty_health: float, championship_prob: float
    ) -> TeamClassification:
        """Classify team as Contender, Fringe, or Rebuilder."""
        if championship_prob >= 0.10 or dynasty_health >= 70:
            return TeamClassification.CONTENDER
        elif championship_prob >= 0.05 or dynasty_health >= 45:
            return TeamClassification.FRINGE
        else:
            return TeamClassification.REBUILDER

    def _calculate_draft_capital_value(
        self, traded_picks: list[dict], roster_id: int, total_rosters: int
    ) -> tuple[list[dict], int]:
        """Calculate draft capital value for a roster."""
        future_picks = []
        total_value = 0

        # Default picks (if not traded away)
        for year in [2025, 2026, 2027]:
            for rd in [1, 2, 3, 4]:
                # Check if this pick was traded away
                traded_away = any(
                    p["season"] == str(year)
                    and p["round"] == rd
                    and p["previous_owner_id"] == roster_id
                    for p in traded_picks
                )

                # Check if we acquired a pick
                acquired = [
                    p for p in traded_picks
                    if p["season"] == str(year)
                    and p["round"] == rd
                    and p["owner_id"] == roster_id
                ]

                if not traded_away:
                    # Still have our own pick
                    pick_value = DRAFT_PICK_VALUES.get(year, {}).get(rd, 500)
                    future_picks.append({
                        "year": year,
                        "round": rd,
                        "original_owner": roster_id,
                        "value": pick_value,
                    })
                    total_value += pick_value

                for acq in acquired:
                    pick_value = DRAFT_PICK_VALUES.get(year, {}).get(rd, 500)
                    future_picks.append({
                        "year": year,
                        "round": rd,
                        "original_owner": acq["previous_owner_id"],
                        "value": pick_value,
                    })
                    total_value += pick_value

        return future_picks, total_value

    async def analyze_roster(
        self,
        roster: dict,
        user_map: dict,
        traded_picks: list[dict],
        total_rosters: int,
        sleeper_players: dict,
        neo4j_player_data: dict,
    ) -> RosterAnalysis:
        """Analyze a single roster."""
        roster_id = roster["roster_id"]
        owner_id = roster.get("owner_id")

        # Get team name
        owner = user_map.get(owner_id, {})
        team_name = owner.get("display_name", f"Team {roster_id}")

        # Get player IDs
        player_ids = roster.get("players", []) or []
        starter_ids = set(roster.get("starters", []) or [])

        # Build player analyses
        players = []
        starters = []
        bench = []

        for pid in player_ids:
            if not pid or pid == "0":
                continue

            neo4j_data = neo4j_player_data.get(pid)
            is_starter = pid in starter_ids

            player = self._build_player_analysis(
                pid, neo4j_data, sleeper_players, is_starter
            )
            players.append(player)

            if is_starter:
                starters.append(player)
            else:
                bench.append(player)

        # Sort by KTC value
        players.sort(key=lambda p: p.ktc_value, reverse=True)
        starters.sort(key=lambda p: p.ktc_value, reverse=True)
        bench.sort(key=lambda p: p.ktc_value, reverse=True)

        # Calculate aggregates
        total_ktc = sum(p.ktc_value for p in players)
        total_ppg = sum(p.projected_ppg or 0 for p in players)
        starter_ppg = sum(p.projected_ppg or 0 for p in starters)

        # Positional strength
        positional_strength = [
            self._calculate_positional_strength(players, pos)
            for pos in ["QB", "RB", "WR", "TE"]
        ]

        # Age analysis
        ages = [p.age for p in players if p.age]
        average_age = sum(ages) / len(ages) if ages else 0

        # Draft capital
        future_picks, draft_capital_value = self._calculate_draft_capital_value(
            traded_picks, roster_id, total_rosters
        )

        return RosterAnalysis(
            roster_id=roster_id,
            owner_id=owner_id,
            team_name=team_name,
            players=players,
            starters=starters,
            bench=bench,
            total_ktc_value=total_ktc,
            total_projected_ppg=total_ppg,
            starter_ppg=starter_ppg,
            positional_strength=positional_strength,
            average_age=round(average_age, 1),
            future_picks=future_picks,
            draft_capital_value=draft_capital_value,
        )

    def calculate_dynasty_health(
        self, roster_analysis: RosterAnalysis
    ) -> DynastyHealthBreakdown:
        """Calculate dynasty health score (0-100) with component breakdown."""
        strengths = []
        weaknesses = []
        recommendations = []

        # 1. Age Score (0-25 points)
        # Younger is better for dynasty
        avg_age = roster_analysis.average_age
        if avg_age <= 24:
            age_score = 25
            strengths.append("Very young roster with long-term upside")
        elif avg_age <= 26:
            age_score = 22
            strengths.append("Young roster positioned for sustained success")
        elif avg_age <= 28:
            age_score = 18
        elif avg_age <= 30:
            age_score = 12
            weaknesses.append("Aging roster may decline soon")
        else:
            age_score = 6
            weaknesses.append("Roster is old and declining")
            recommendations.append("Consider trading aging assets for youth")

        # 2. Peak Overlap Score (0-20 points)
        # Do players peak at the same time?
        players = roster_analysis.players
        peak_players = [p for p in players if p.career_phase == "Peak" and p.ktc_value > 3000]
        pre_peak_studs = [p for p in players if p.career_phase == "Pre-Peak" and p.ktc_value > 5000]

        if len(peak_players) >= 4:
            peak_overlap_score = 20
            strengths.append(f"{len(peak_players)} players currently in their prime")
        elif len(peak_players) >= 2:
            peak_overlap_score = 15
        elif len(pre_peak_studs) >= 3:
            peak_overlap_score = 18
            strengths.append(f"{len(pre_peak_studs)} young stars haven't peaked yet")
        else:
            peak_overlap_score = 8
            weaknesses.append("Limited peak talent overlap")

        # 3. Injury Risk Score (0-15 points, inverted)
        # Lower risk = higher score
        # For now, estimate based on RB concentration
        rb_value_pct = sum(
            p.ktc_value for p in players if p.position == "RB"
        ) / max(roster_analysis.total_ktc_value, 1)

        if rb_value_pct > 0.4:
            injury_risk_score = 8
            weaknesses.append("Heavy RB investment increases injury risk")
        elif rb_value_pct > 0.3:
            injury_risk_score = 11
        else:
            injury_risk_score = 15
            strengths.append("Well-diversified positional investment")

        # 4. Position Wins Score (0-25 points)
        # Based on positional grades
        pos_grades = {ps.position: ps.grade for ps in roster_analysis.positional_strength}
        grade_values = {"A+": 6.5, "A": 6, "B+": 5, "B": 4, "C+": 3, "C": 2, "D": 1, "F": 0}

        position_wins_score = sum(
            grade_values.get(pos_grades.get(pos, "C"), 2)
            for pos in ["QB", "RB", "WR", "TE"]
        )

        weak_positions = [
            pos for pos, grade in pos_grades.items()
            if grade in ["D", "F"]
        ]
        if weak_positions:
            weaknesses.append(f"Weak at {', '.join(weak_positions)}")
            recommendations.append(f"Target {weak_positions[0]} in trades or draft")

        strong_positions = [
            pos for pos, grade in pos_grades.items()
            if grade in ["A+", "A"]
        ]
        if strong_positions:
            strengths.append(f"Elite {', '.join(strong_positions)} room")

        # 5. Draft Capital Score (0-15 points)
        pick_count = len(roster_analysis.future_picks)
        first_rounders = len([p for p in roster_analysis.future_picks if p["round"] == 1])

        if first_rounders >= 4:
            draft_capital_score = 15
            strengths.append(f"{first_rounders} first-round picks stockpiled")
        elif first_rounders >= 3:
            draft_capital_score = 12
        elif pick_count >= 10:
            draft_capital_score = 10
        elif pick_count >= 6:
            draft_capital_score = 7
        else:
            draft_capital_score = 4
            weaknesses.append("Limited draft capital")
            recommendations.append("Acquire future picks from contenders")

        total_score = (
            age_score + peak_overlap_score + injury_risk_score +
            position_wins_score + draft_capital_score
        )

        return DynastyHealthBreakdown(
            total_score=round(total_score, 1),
            age_score=age_score,
            peak_overlap_score=peak_overlap_score,
            injury_risk_score=injury_risk_score,
            position_wins_score=position_wins_score,
            draft_capital_score=draft_capital_score,
            strengths=strengths[:5],
            weaknesses=weaknesses[:5],
            recommendations=recommendations[:5],
        )

    def simulate_championship(
        self,
        roster_analysis: RosterAnalysis,
        all_rosters: list[RosterAnalysis],
        simulations: int = 10000,
    ) -> ChampionshipSimulation:
        """Monte Carlo simulation for championship probability."""
        num_teams = len(all_rosters)
        playoff_spots = min(6, num_teams // 2)

        # Sort rosters by projected PPG for seeding
        sorted_rosters = sorted(all_rosters, key=lambda r: r.starter_ppg, reverse=True)
        roster_ppg = {r.roster_id: r.starter_ppg for r in sorted_rosters}
        my_roster_id = roster_analysis.roster_id

        # Simulation results
        playoff_count = 0
        bye_count = 0
        championship_count = 0
        seed_counts = {i: 0 for i in range(1, num_teams + 1)}
        wins_total = 0

        for _ in range(simulations):
            # Simulate regular season (13 weeks)
            standings = {r.roster_id: {"wins": 0, "points": 0} for r in all_rosters}

            for week in range(13):
                for roster in all_rosters:
                    # Add variance to weekly scores (std dev ~15% of mean)
                    base_ppg = roster_ppg[roster.roster_id]
                    weekly_score = max(0, random.gauss(base_ppg, base_ppg * 0.15))
                    standings[roster.roster_id]["points"] += weekly_score

                # Simulate matchups (simplified: random pairings)
                shuffled = list(all_rosters)
                random.shuffle(shuffled)
                for i in range(0, len(shuffled) - 1, 2):
                    team1, team2 = shuffled[i], shuffled[i + 1]
                    score1 = random.gauss(roster_ppg[team1.roster_id], roster_ppg[team1.roster_id] * 0.15)
                    score2 = random.gauss(roster_ppg[team2.roster_id], roster_ppg[team2.roster_id] * 0.15)
                    if score1 > score2:
                        standings[team1.roster_id]["wins"] += 1
                    else:
                        standings[team2.roster_id]["wins"] += 1

            # Determine playoff seeds
            sorted_standings = sorted(
                standings.items(),
                key=lambda x: (x[1]["wins"], x[1]["points"]),
                reverse=True,
            )

            # Find my seed
            my_seed = next(
                i + 1 for i, (rid, _) in enumerate(sorted_standings)
                if rid == my_roster_id
            )
            seed_counts[my_seed] += 1
            wins_total += standings[my_roster_id]["wins"]

            # Made playoffs?
            if my_seed <= playoff_spots:
                playoff_count += 1

                # Got bye?
                if my_seed <= 2:
                    bye_count += 1

                # Simulate playoffs (simplified)
                # Higher seed has PPG advantage
                playoff_teams = [rid for rid, _ in sorted_standings[:playoff_spots]]

                # Championship probability based on seed
                if my_seed == 1:
                    champ_prob = 0.25
                elif my_seed == 2:
                    champ_prob = 0.20
                elif my_seed <= 4:
                    champ_prob = 0.12
                else:
                    champ_prob = 0.08

                if random.random() < champ_prob:
                    championship_count += 1

        # Calculate probabilities
        playoff_prob = playoff_count / simulations
        bye_prob = bye_count / simulations
        championship_prob = championship_count / simulations
        expected_wins = wins_total / simulations
        expected_ppf = roster_analysis.starter_ppg * 13

        # Seed probabilities
        seed_probs = {seed: count / simulations for seed, count in seed_counts.items()}

        # Most likely record
        most_likely_wins = round(expected_wins)
        most_likely_losses = 13 - most_likely_wins

        return ChampionshipSimulation(
            simulations_run=simulations,
            playoff_probability=round(playoff_prob, 3),
            bye_probability=round(bye_prob, 3),
            championship_probability=round(championship_prob, 3),
            seed_probabilities=seed_probs,
            expected_wins=round(expected_wins, 1),
            expected_points_for=round(expected_ppf, 1),
            best_case_record=f"{min(13, most_likely_wins + 3)}-{max(0, most_likely_losses - 3)}",
            worst_case_record=f"{max(0, most_likely_wins - 3)}-{min(13, most_likely_losses + 3)}",
            most_likely_record=f"{most_likely_wins}-{most_likely_losses}",
        )

    def find_trade_targets(
        self,
        my_roster: RosterAnalysis,
        all_rosters: list[RosterAnalysis],
    ) -> list[TradePartner]:
        """Find optimal trade partners and suggestions."""
        trade_partners = []

        # Identify my weak and strong positions
        my_weak = [
            ps.position for ps in my_roster.positional_strength
            if ps.grade in ["D", "F", "C"]
        ]
        my_strong = [
            ps.position for ps in my_roster.positional_strength
            if ps.grade in ["A+", "A", "B+"]
        ]

        for roster in all_rosters:
            if roster.roster_id == my_roster.roster_id:
                continue

            # Their weak/strong positions
            their_weak = [
                ps.position for ps in roster.positional_strength
                if ps.grade in ["D", "F", "C"]
            ]
            their_strong = [
                ps.position for ps in roster.positional_strength
                if ps.grade in ["A+", "A", "B+"]
            ]

            # Find complementary needs
            i_need_they_have = set(my_weak) & set(their_strong)
            they_need_i_have = set(their_weak) & set(my_strong)

            if not (i_need_they_have or they_need_i_have):
                continue

            # Find trade targets on their roster
            trade_targets = []
            for player in roster.players:
                if player.position in i_need_they_have and player.ktc_value > 2000:
                    # Calculate fit score (how much we need this player)
                    my_pos_strength = next(
                        (ps for ps in my_roster.positional_strength if ps.position == player.position),
                        None
                    )
                    fit_score = 100 - (my_pos_strength.total_value / 500) if my_pos_strength else 50
                    fit_score = max(0, min(100, fit_score))

                    # Availability: older players on contenders more likely to be moved
                    their_health = sum(ps.total_value for ps in roster.positional_strength)
                    availability = 50
                    if player.career_phase == "Post-Peak":
                        availability += 20
                    if roster.classification == TeamClassification.REBUILDER:
                        availability += 15

                    trade_targets.append(TradeTarget(
                        player=player,
                        owner_roster_id=roster.roster_id,
                        owner_team_name=roster.team_name,
                        trade_value=player.ktc_value,
                        fit_score=round(fit_score, 1),
                        availability_score=round(min(100, availability), 1),
                    ))

            # Generate trade suggestions
            suggestions = self._generate_trade_suggestions(
                my_roster, roster, trade_targets, they_need_i_have
            )

            # Calculate compatibility score
            compatibility = len(i_need_they_have) * 20 + len(they_need_i_have) * 20
            compatibility = min(100, compatibility)

            if trade_targets or suggestions:
                trade_partners.append(TradePartner(
                    roster_id=roster.roster_id,
                    team_name=roster.team_name,
                    owner_name=roster.team_name,
                    weak_positions=list(their_weak),
                    trade_targets=sorted(trade_targets, key=lambda t: t.fit_score, reverse=True)[:5],
                    suggestions=suggestions[:3],
                    compatibility_score=compatibility,
                ))

        # Sort by compatibility
        trade_partners.sort(key=lambda tp: tp.compatibility_score, reverse=True)
        return trade_partners[:5]

    def _generate_trade_suggestions(
        self,
        my_roster: RosterAnalysis,
        their_roster: RosterAnalysis,
        trade_targets: list[TradeTarget],
        positions_they_need: set[str],
    ) -> list[TradeSuggestion]:
        """Generate specific trade suggestions."""
        suggestions = []

        # Find my players that fill their needs
        my_tradeable = [
            p for p in my_roster.players
            if p.position in positions_they_need
            and p.ktc_value > 2000
            and not p.is_starter  # Prefer trading bench pieces
        ]

        if not my_tradeable:
            my_tradeable = [
                p for p in my_roster.players
                if p.position in positions_they_need
                and p.ktc_value > 2000
            ]

        for target in trade_targets[:3]:
            for my_player in my_tradeable[:3]:
                # Check if values are within 20%
                value_diff = target.trade_value - my_player.ktc_value
                if abs(value_diff) > target.trade_value * 0.3:
                    continue

                # Calculate PPG impact
                my_ppg_change = (target.player.projected_ppg or 0) - (my_player.projected_ppg or 0)
                their_ppg_change = (my_player.projected_ppg or 0) - (target.player.projected_ppg or 0)

                # Win-win if both teams improve at weak positions
                win_win = 50
                if my_ppg_change > 0:
                    win_win += 25
                if value_diff < 0:  # We're getting more value
                    win_win += 25

                # Build rationale
                rationale = f"Trade your {my_player.name} ({my_player.position}) for their {target.player.name}. "
                if value_diff < 0:
                    rationale += f"You gain {abs(value_diff):,} KTC value. "
                if my_ppg_change > 0:
                    rationale += f"Upgrades your {target.player.position} production by {my_ppg_change:.1f} PPG."

                suggestions.append(TradeSuggestion(
                    give_players=[my_player],
                    get_players=[target.player],
                    give_value=my_player.ktc_value,
                    get_value=target.trade_value,
                    value_differential=value_diff,
                    your_ppg_change=my_ppg_change,
                    their_ppg_change=their_ppg_change,
                    your_championship_change=my_ppg_change * 0.005,  # Rough estimate
                    rationale=rationale,
                    win_win_score=min(100, win_win),
                ))

        # Sort by win-win score
        suggestions.sort(key=lambda s: s.win_win_score, reverse=True)
        return suggestions

    def build_power_rankings(
        self,
        all_rosters: list[RosterAnalysis],
        dynasty_healths: dict[int, DynastyHealthBreakdown],
        championship_probs: dict[int, ChampionshipSimulation],
    ) -> list[PowerRanking]:
        """Build league power rankings."""
        rankings = []

        for roster in all_rosters:
            health = dynasty_healths.get(roster.roster_id)
            champ = championship_probs.get(roster.roster_id)

            classification = self._classify_team(
                health.total_score if health else 50,
                champ.championship_probability if champ else 0.05,
            )

            rankings.append(PowerRanking(
                rank=0,  # Set after sorting
                roster_id=roster.roster_id,
                team_name=roster.team_name,
                owner_name=roster.team_name,
                ktc_value=roster.total_ktc_value,
                projected_value=int(roster.total_projected_ppg * 1000),
                dynasty_health_score=health.total_score if health else 50,
                championship_probability=champ.championship_probability if champ else 0.05,
                classification=classification,
                value_trend="stable",
            ))

        # Sort by championship probability, then KTC value
        rankings.sort(
            key=lambda r: (r.championship_probability, r.ktc_value),
            reverse=True,
        )

        # Assign ranks
        for i, ranking in enumerate(rankings):
            ranking.rank = i + 1

        return rankings

    async def analyze_league(
        self,
        league_id: str,
        user_roster_id: Optional[int] = None,
    ) -> LeagueAnalysis:
        """Complete league analysis."""
        # Fetch all league data from Sleeper
        league_data = await self.sleeper.get_full_league_data(league_id)

        league = league_data["league"]
        rosters = league_data["rosters"]
        user_map = league_data["user_map"]
        traded_picks = league_data["traded_picks"]

        # Get Sleeper player database
        sleeper_players = await self._get_all_sleeper_players()

        # Collect all player IDs
        all_player_ids = []
        for roster in rosters:
            all_player_ids.extend(roster.get("players", []) or [])

        # Load Neo4j data for all players
        neo4j_data = await self._load_player_data(all_player_ids)

        # Analyze all rosters
        roster_analyses = []
        for roster in rosters:
            analysis = await self.analyze_roster(
                roster,
                user_map,
                traded_picks,
                len(rosters),
                sleeper_players,
                neo4j_data,
            )
            roster_analyses.append(analysis)

        # Determine user's roster if not specified
        if user_roster_id is None and roster_analyses:
            user_roster_id = roster_analyses[0].roster_id

        my_roster = next(
            (r for r in roster_analyses if r.roster_id == user_roster_id),
            roster_analyses[0] if roster_analyses else None,
        )

        # Calculate dynasty health for all teams
        dynasty_healths = {}
        for roster in roster_analyses:
            dynasty_healths[roster.roster_id] = self.calculate_dynasty_health(roster)

        # Simulate championships
        championship_probs = {}
        for roster in roster_analyses:
            championship_probs[roster.roster_id] = self.simulate_championship(
                roster, roster_analyses, simulations=5000
            )

        # Update classifications based on simulation
        for roster in roster_analyses:
            health = dynasty_healths[roster.roster_id]
            champ = championship_probs[roster.roster_id]
            roster.classification = self._classify_team(
                health.total_score, champ.championship_probability
            )
            roster.dynasty_health_score = health.total_score
            roster.championship_probability = champ.championship_probability

        # Build power rankings
        power_rankings = self.build_power_rankings(
            roster_analyses, dynasty_healths, championship_probs
        )

        # Find trade opportunities
        trade_partners = self.find_trade_targets(my_roster, roster_analyses)

        # Get all trade suggestions
        all_suggestions = []
        for partner in trade_partners:
            all_suggestions.extend(partner.suggestions)
        all_suggestions.sort(key=lambda s: s.win_win_score, reverse=True)

        # Identify buy-low and sell-high candidates
        buy_low = []
        sell_high = []
        for partner in trade_partners:
            for target in partner.trade_targets:
                if target.player.career_phase == "Pre-Peak" and target.availability_score > 60:
                    buy_low.append(target)

        for player in my_roster.players:
            if player.is_sell_candidate:
                sell_high.append(player)

        # Determine scoring type
        scoring_settings = league.get("scoring_settings", {})
        scoring_type = ScoringType.STANDARD
        rec_pts = scoring_settings.get("rec", 0)
        if rec_pts >= 1:
            scoring_type = ScoringType.PPR
        elif rec_pts >= 0.5:
            scoring_type = ScoringType.HALF_PPR

        return LeagueAnalysis(
            league_id=league_id,
            league_name=league.get("name", "Unknown League"),
            season=league.get("season", "2025"),
            scoring_type=scoring_type,
            total_teams=len(rosters),
            your_roster_id=my_roster.roster_id,
            your_analysis=my_roster,
            your_dynasty_health=dynasty_healths[my_roster.roster_id],
            your_championship_odds=championship_probs[my_roster.roster_id],
            power_rankings=power_rankings,
            trade_partners=trade_partners,
            top_trade_suggestions=all_suggestions[:5],
            buy_low_targets=buy_low[:5],
            sell_high_candidates=sell_high[:5],
            waiver_targets=[],
            analysis_timestamp=datetime.utcnow().isoformat(),
            data_freshness="live",
        )


# Singleton instance
_analyzer: Optional[LeagueAnalyzer] = None


def get_league_analyzer() -> LeagueAnalyzer:
    """Get or create league analyzer instance."""
    global _analyzer
    if _analyzer is None:
        _analyzer = LeagueAnalyzer()
    return _analyzer
