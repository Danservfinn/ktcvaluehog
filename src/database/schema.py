"""Neo4j schema definition for Dynasty Edge with novel valuation framework.

This schema implements the hybrid architecture:
- Core nodes for players, teams, games
- Novel valuation nodes: CareerStage, SkillProfile, Scheme, OpportunityPool
- Rich relationships: CHEMISTRY_WITH, CANNIBALIZES, FITS, LEADS_TO
"""

# Constraints ensure data integrity
CONSTRAINTS = [
    # Core entities
    "CREATE CONSTRAINT player_gsis IF NOT EXISTS FOR (p:Player) REQUIRE p.gsis_id IS UNIQUE",
    "CREATE CONSTRAINT player_sleeper IF NOT EXISTS FOR (p:Player) REQUIRE p.sleeper_id IS UNIQUE",
    "CREATE CONSTRAINT team_abbr IF NOT EXISTS FOR (t:Team) REQUIRE t.team_abbr IS UNIQUE",
    "CREATE CONSTRAINT game_id IF NOT EXISTS FOR (g:Game) REQUIRE g.game_id IS UNIQUE",

    # Seasonal aggregates
    "CREATE CONSTRAINT player_season IF NOT EXISTS FOR (ps:PlayerSeason) REQUIRE ps.id IS UNIQUE",
    "CREATE CONSTRAINT team_season IF NOT EXISTS FOR (ts:TeamSeason) REQUIRE ts.id IS UNIQUE",

    # Fantasy entities
    "CREATE CONSTRAINT fantasy_league IF NOT EXISTS FOR (fl:FantasyLeague) REQUIRE fl.league_id IS UNIQUE",
    "CREATE CONSTRAINT fantasy_team IF NOT EXISTS FOR (ft:FantasyTeam) REQUIRE ft.roster_id IS UNIQUE",
    "CREATE CONSTRAINT draft_pick IF NOT EXISTS FOR (dp:DraftPick) REQUIRE dp.pick_id IS UNIQUE",

    # Novel valuation framework
    "CREATE CONSTRAINT career_stage IF NOT EXISTS FOR (cs:CareerStage) REQUIRE cs.id IS UNIQUE",
    "CREATE CONSTRAINT skill_profile IF NOT EXISTS FOR (sp:SkillProfile) REQUIRE sp.id IS UNIQUE",
    "CREATE CONSTRAINT scheme IF NOT EXISTS FOR (s:Scheme) REQUIRE s.id IS UNIQUE",
    "CREATE CONSTRAINT opp_pool IF NOT EXISTS FOR (op:OpportunityPool) REQUIRE op.id IS UNIQUE",
    "CREATE CONSTRAINT value_snapshot IF NOT EXISTS FOR (vs:ValueSnapshot) REQUIRE vs.id IS UNIQUE",
]

# Indexes for query performance
INDEXES = [
    # Player lookups
    "CREATE INDEX player_position IF NOT EXISTS FOR (p:Player) ON (p.position)",
    "CREATE INDEX player_team IF NOT EXISTS FOR (p:Player) ON (p.current_team)",
    "CREATE INDEX player_name IF NOT EXISTS FOR (p:Player) ON (p.name)",
    "CREATE INDEX player_age IF NOT EXISTS FOR (p:Player) ON (p.age)",

    # Value-based lookups
    "CREATE INDEX player_ktc IF NOT EXISTS FOR (p:Player) ON (p.ktc_value_sf)",
    "CREATE INDEX player_edge IF NOT EXISTS FOR (p:Player) ON (p.edge_signal)",
    "CREATE INDEX player_predicted IF NOT EXISTS FOR (p:Player) ON (p.predicted_ktc_value)",

    # Seasonal data
    "CREATE INDEX ps_season IF NOT EXISTS FOR (ps:PlayerSeason) ON (ps.season)",
    "CREATE INDEX ts_season IF NOT EXISTS FOR (ts:TeamSeason) ON (ts.season)",

    # Game data
    "CREATE INDEX game_season IF NOT EXISTS FOR (g:Game) ON (g.season)",
    "CREATE INDEX game_week IF NOT EXISTS FOR (g:Game) ON (g.week)",

    # Novel framework
    "CREATE INDEX career_stage_type IF NOT EXISTS FOR (cs:CareerStage) ON (cs.stage_type)",
    "CREATE INDEX scheme_type IF NOT EXISTS FOR (s:Scheme) ON (s.scheme_type)",
    "CREATE INDEX value_snap_date IF NOT EXISTS FOR (vs:ValueSnapshot) ON (vs.date)",
]

# Combine all schema queries
SCHEMA_QUERIES = CONSTRAINTS + INDEXES


def create_schema(client) -> dict:
    """Create all constraints and indexes.

    Args:
        client: Neo4jClient instance

    Returns:
        dict with created/skipped counts
    """
    created = 0
    skipped = 0
    errors = []

    for query in SCHEMA_QUERIES:
        try:
            client.run_write(query)
            created += 1
        except Exception as e:
            if "already exists" in str(e).lower():
                skipped += 1
            else:
                errors.append(f"{query[:50]}...: {e}")

    return {
        'created': created,
        'skipped': skipped,
        'errors': errors,
        'total': len(SCHEMA_QUERIES)
    }


# Node creation templates for batch loading
NODE_TEMPLATES = {
    'Player': """
        MERGE (p:Player {gsis_id: $gsis_id})
        SET p.name = $name,
            p.display_name = $display_name,
            p.position = $position,
            p.current_team = $current_team,
            p.age = $age,
            p.birth_date = $birth_date,
            p.height = $height,
            p.weight = $weight,
            p.college = $college,
            p.draft_year = $draft_year,
            p.draft_round = $draft_round,
            p.draft_pick = $draft_pick,
            p.sleeper_id = $sleeper_id,
            p.espn_id = $espn_id,
            p.pfr_id = $pfr_id,
            p.forty_time = $forty_time,
            p.bench_press = $bench_press,
            p.vertical_jump = $vertical_jump,
            p.broad_jump = $broad_jump,
            p.three_cone = $three_cone,
            p.updated_at = datetime()
    """,

    'Team': """
        MERGE (t:Team {team_abbr: $team_abbr})
        SET t.team_name = $team_name,
            t.team_nick = $team_nick,
            t.conference = $conference,
            t.division = $division,
            t.team_color = $team_color,
            t.team_color2 = $team_color2
    """,

    'PlayerSeason': """
        MERGE (ps:PlayerSeason {id: $id})
        SET ps.player_gsis_id = $player_gsis_id,
            ps.season = $season,
            ps.games_played = $games_played,
            ps.fantasy_points_ppr = $fantasy_points_ppr,
            ps.ppg = $ppg,
            ps.targets = $targets,
            ps.receptions = $receptions,
            ps.receiving_yards = $receiving_yards,
            ps.receiving_tds = $receiving_tds,
            ps.carries = $carries,
            ps.rushing_yards = $rushing_yards,
            ps.rushing_tds = $rushing_tds,
            ps.passing_yards = $passing_yards,
            ps.passing_tds = $passing_tds,
            ps.interceptions = $interceptions,
            ps.snap_share = $snap_share,
            ps.target_share = $target_share,
            ps.updated_at = datetime()
    """,

    'Game': """
        MERGE (g:Game {game_id: $game_id})
        SET g.season = $season,
            g.week = $week,
            g.game_type = $game_type,
            g.home_team = $home_team,
            g.away_team = $away_team,
            g.home_score = $home_score,
            g.away_score = $away_score,
            g.game_date = date($game_date)
    """,

    'CareerStage': """
        MERGE (cs:CareerStage {id: $id})
        SET cs.stage_type = $stage_type,
            cs.position = $position,
            cs.age_range_start = $age_range_start,
            cs.age_range_end = $age_range_end,
            cs.expected_production_pct = $expected_production_pct,
            cs.transition_probability = $transition_probability
    """,

    'SkillProfile': """
        MERGE (sp:SkillProfile {id: $id})
        SET sp.player_gsis_id = $player_gsis_id,
            sp.season = $season,
            sp.speed_score = $speed_score,
            sp.route_running = $route_running,
            sp.separation_ability = $separation_ability,
            sp.yac_ability = $yac_ability,
            sp.contested_catch = $contested_catch,
            sp.deep_threat = $deep_threat,
            sp.slot_ability = $slot_ability,
            sp.rush_efficiency = $rush_efficiency,
            sp.elusiveness = $elusiveness,
            sp.pass_blocking = $pass_blocking
    """,

    'Scheme': """
        MERGE (s:Scheme {id: $id})
        SET s.team_abbr = $team_abbr,
            s.season = $season,
            s.scheme_type = $scheme_type,
            s.pass_rate = $pass_rate,
            s.play_action_rate = $play_action_rate,
            s.rpo_rate = $rpo_rate,
            s.screen_rate = $screen_rate,
            s.shotgun_rate = $shotgun_rate,
            s.motion_rate = $motion_rate,
            s.early_down_pass_rate = $early_down_pass_rate,
            s.pace_rank = $pace_rank
    """,

    'OpportunityPool': """
        MERGE (op:OpportunityPool {id: $id})
        SET op.team_abbr = $team_abbr,
            op.season = $season,
            op.total_targets = $total_targets,
            op.total_carries = $total_carries,
            op.total_snaps = $total_snaps,
            op.pass_attempts = $pass_attempts,
            op.rush_attempts = $rush_attempts,
            op.target_elasticity = $target_elasticity,
            op.carry_elasticity = $carry_elasticity
    """,

    'ValueSnapshot': """
        MERGE (vs:ValueSnapshot {id: $id})
        SET vs.player_gsis_id = $player_gsis_id,
            vs.date = date($date),
            vs.ktc_value_sf = $ktc_value_sf,
            vs.ktc_value_1qb = $ktc_value_1qb,
            vs.predicted_value = $predicted_value,
            vs.delta_pct = $delta_pct,
            vs.edge_signal = $edge_signal,
            vs.momentum_score = $momentum_score,
            vs.hype_index = $hype_index
    """
}


# Relationship creation templates
RELATIONSHIP_TEMPLATES = {
    'PLAYS_FOR': """
        MATCH (p:Player {gsis_id: $player_gsis_id})
        MATCH (t:Team {team_abbr: $team_abbr})
        MERGE (p)-[r:PLAYS_FOR]->(t)
        SET r.season = $season,
            r.joined_date = $joined_date
    """,

    'TARGETS_FROM': """
        MATCH (rec:Player {gsis_id: $receiver_gsis_id})
        MATCH (qb:Player {gsis_id: $qb_gsis_id})
        MERGE (rec)-[r:TARGETS_FROM]->(qb)
        SET r.season = $season,
            r.targets = $targets,
            r.receptions = $receptions,
            r.yards = $yards,
            r.tds = $tds,
            r.epa_per_target = $epa_per_target,
            r.target_share = $target_share
    """,

    'CHEMISTRY_WITH': """
        MATCH (rec:Player {gsis_id: $receiver_gsis_id})
        MATCH (qb:Player {gsis_id: $qb_gsis_id})
        MERGE (rec)-[r:CHEMISTRY_WITH]->(qb)
        SET r.season = $season,
            r.cqi_score = $cqi_score,
            r.trust_score = $trust_score,
            r.pressure_target_rate = $pressure_target_rate,
            r.red_zone_target_rate = $red_zone_target_rate,
            r.contested_target_rate = $contested_target_rate,
            r.expected_target_share = $expected_target_share,
            r.actual_vs_expected = $actual_vs_expected
    """,

    'COMPETES_WITH': """
        MATCH (p1:Player {gsis_id: $player1_gsis_id})
        MATCH (p2:Player {gsis_id: $player2_gsis_id})
        MERGE (p1)-[r:COMPETES_WITH]->(p2)
        SET r.team_abbr = $team_abbr,
            r.season = $season,
            r.position = $position,
            r.combined_snap_share = $combined_snap_share
    """,

    'CANNIBALIZES': """
        MATCH (p1:Player {gsis_id: $player1_gsis_id})
        MATCH (p2:Player {gsis_id: $player2_gsis_id})
        MERGE (p1)-[r:CANNIBALIZES]->(p2)
        SET r.team_abbr = $team_abbr,
            r.season = $season,
            r.opportunity_type = $opportunity_type,
            r.elasticity = $elasticity,
            r.correlation = $correlation
    """,

    'FITS': """
        MATCH (sp:SkillProfile {id: $skill_profile_id})
        MATCH (s:Scheme {id: $scheme_id})
        MERGE (sp)-[r:FITS]->(s)
        SET r.fit_score = $fit_score,
            r.primary_fit = $primary_fit,
            r.ceiling_boost = $ceiling_boost
    """,

    'WAS_AT': """
        MATCH (p:Player {gsis_id: $player_gsis_id})
        MATCH (cs:CareerStage {id: $career_stage_id})
        MERGE (p)-[r:WAS_AT]->(cs)
        SET r.season = $season,
            r.production_pct = $production_pct
    """,

    'LEADS_TO': """
        MATCH (cs1:CareerStage {id: $from_stage_id})
        MATCH (cs2:CareerStage {id: $to_stage_id})
        MERGE (cs1)-[r:LEADS_TO]->(cs2)
        SET r.transition_probability = $transition_probability,
            r.position = $position
    """,

    'CAPTURES_OPPORTUNITY': """
        MATCH (p:Player {gsis_id: $player_gsis_id})
        MATCH (op:OpportunityPool {id: $opp_pool_id})
        MERGE (p)-[r:CAPTURES_OPPORTUNITY]->(op)
        SET r.season = $season,
            r.target_share = $target_share,
            r.carry_share = $carry_share,
            r.snap_share = $snap_share,
            r.opportunity_score = $opportunity_score
    """,

    'SIMILAR_TO': """
        MATCH (p1:Player {gsis_id: $player1_gsis_id})
        MATCH (p2:Player {gsis_id: $player2_gsis_id})
        MERGE (p1)-[r:SIMILAR_TO]->(p2)
        SET r.similarity_score = $similarity_score,
            r.comparison_season = $comparison_season,
            r.p1_current_age = $p1_current_age,
            r.p2_comparison_age = $p2_comparison_age
    """
}
