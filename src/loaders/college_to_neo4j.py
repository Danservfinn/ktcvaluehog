"""
College Football Data ETL Pipeline
===================================
Loads college football data into Neo4j for dynasty devy analysis.

Sources:
- CFBD (CollegeFootballData.com): Recruiting, stats, draft picks, portal
- KTC Devy: College prospect dynasty values
- NFLverse Combine: Athletic testing results

Pipeline Steps:
1. Extract: Fetch data from CFBD API and KTC
2. Transform: Engineer features (dominator rating, breakout age, etc.)
3. Load: Merge into Neo4j graph with Prospect, CollegeTeam, CollegeStats nodes
4. Link: Connect Prospects to NFL Players via draft picks
"""

import os
import logging
import hashlib
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

import pandas as pd
import numpy as np
from neo4j import GraphDatabase
from dotenv import load_dotenv

from ..api.cfbd_client import CFBDClient
from .ktc_devy_loader import KTCDevyLoader
from ..database.college_schema import CollegeSchemaManager
from ..config import RAW_DIR

load_dotenv()
logger = logging.getLogger(__name__)


class CollegeToNeo4jETL:
    """
    ETL pipeline for loading college football data into Neo4j.

    Creates and populates:
    - Prospect nodes (college players)
    - CollegeTeam nodes
    - Conference nodes
    - CollegeStats nodes (season-by-season)
    - CombineResult nodes
    - DevySnapshot nodes (time-series values)
    - DraftClass nodes

    Relationships:
    - (Prospect)-[:PLAYED_FOR]->(CollegeTeam)
    - (Prospect)-[:HAS_COLLEGE_STATS]->(CollegeStats)
    - (Prospect)-[:HAS_COMBINE]->(CombineResult)
    - (Prospect)-[:BECAME_NFL_PLAYER]->(Player)
    - (CollegeTeam)-[:IN_CONFERENCE]->(Conference)
    """

    # Years to fetch for historical analysis
    DEFAULT_RECRUITING_YEARS = list(range(2018, 2026))  # 2018-2025
    DEFAULT_STATS_YEARS = list(range(2019, 2025))  # 2019-2024
    DEFAULT_DRAFT_YEARS = list(range(2019, 2026))  # 2019-2025

    # Position mappings
    POSITION_GROUPS = {
        'QB': ['QB'],
        'RB': ['RB', 'FB'],
        'WR': ['WR'],
        'TE': ['TE'],
        'FLEX': ['RB', 'WR', 'TE'],
        'ATH': ['ATH']
    }

    def __init__(
        self,
        neo4j_uri: str = None,
        neo4j_user: str = None,
        neo4j_password: str = None,
        cfbd_api_key: str = None,
        cache_dir: Path = None
    ):
        """
        Initialize the ETL pipeline.

        Args:
            neo4j_uri: Neo4j connection URI
            neo4j_user: Neo4j username (optional - None for no auth)
            neo4j_password: Neo4j password (optional)
            cfbd_api_key: CFBD API key
            cache_dir: Directory for caching data
        """
        self.neo4j_uri = neo4j_uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_user = neo4j_user or os.getenv("NEO4J_USER")
        self.neo4j_password = neo4j_password or os.getenv("NEO4J_PASSWORD")

        # Initialize Neo4j driver
        auth = None
        if self.neo4j_user and self.neo4j_password:
            auth = (self.neo4j_user, self.neo4j_password)
        self.driver = GraphDatabase.driver(self.neo4j_uri, auth=auth)

        # Initialize CFBD client
        self.cfbd = CFBDClient(api_key=cfbd_api_key)

        # Initialize KTC Devy loader
        self.ktc_devy = KTCDevyLoader(driver=self.driver)

        # Initialize schema manager
        self.schema_manager = CollegeSchemaManager(self.driver)

        # Cache directory
        self.cache_dir = Path(cache_dir or RAW_DIR / "college")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # ETL statistics
        self.stats = {
            'prospects_created': 0,
            'teams_created': 0,
            'stats_created': 0,
            'combine_created': 0,
            'draft_links': 0,
            'devy_snapshots': 0,
            'errors': []
        }

    def close(self):
        """Clean up resources."""
        self.driver.close()

    # =========================================================================
    # MAIN ETL METHODS
    # =========================================================================

    def run_full_etl(
        self,
        recruiting_years: List[int] = None,
        stats_years: List[int] = None,
        draft_years: List[int] = None,
        include_devy: bool = True,
        include_combine: bool = True
    ) -> Dict[str, int]:
        """
        Run the full ETL pipeline.

        Args:
            recruiting_years: Years of recruiting classes to load
            stats_years: Years of college stats to load
            draft_years: Years of NFL draft picks to load
            include_devy: Whether to load KTC devy values
            include_combine: Whether to load combine data

        Returns:
            Dictionary with counts of created/updated records
        """
        logger.info("=" * 60)
        logger.info("Starting College Football ETL Pipeline")
        logger.info("=" * 60)

        recruiting_years = recruiting_years or self.DEFAULT_RECRUITING_YEARS
        stats_years = stats_years or self.DEFAULT_STATS_YEARS
        draft_years = draft_years or self.DEFAULT_DRAFT_YEARS

        # Step 1: Ensure schema is set up
        logger.info("\n[1/7] Setting up Neo4j schema...")
        self.schema_manager.setup_schema()

        # Step 2: Load college teams
        logger.info("\n[2/7] Loading college teams and conferences...")
        self._load_teams_and_conferences(stats_years[-1])

        # Step 3: Load recruiting data (creates Prospect nodes)
        logger.info("\n[3/7] Loading recruiting data...")
        self._load_recruiting_data(recruiting_years)

        # Step 4: Load college stats
        logger.info("\n[4/7] Loading college statistics...")
        self._load_college_stats(stats_years)

        # Step 5: Load combine data
        if include_combine:
            logger.info("\n[5/7] Loading combine data...")
            self._load_combine_data()
        else:
            logger.info("\n[5/7] Skipping combine data...")

        # Step 6: Link prospects to NFL players via draft
        logger.info("\n[6/7] Linking prospects to NFL players...")
        self._link_draft_picks(draft_years)

        # Step 7: Load KTC devy values
        if include_devy:
            logger.info("\n[7/7] Loading KTC devy values...")
            self._load_devy_values()
        else:
            logger.info("\n[7/7] Skipping devy values...")

        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("ETL Pipeline Complete!")
        logger.info("=" * 60)
        logger.info(f"Prospects created/updated: {self.stats['prospects_created']}")
        logger.info(f"Teams created: {self.stats['teams_created']}")
        logger.info(f"Stats records created: {self.stats['stats_created']}")
        logger.info(f"Combine results loaded: {self.stats['combine_created']}")
        logger.info(f"Draft links established: {self.stats['draft_links']}")
        logger.info(f"Devy snapshots created: {self.stats['devy_snapshots']}")

        if self.stats['errors']:
            logger.warning(f"Errors encountered: {len(self.stats['errors'])}")
            for error in self.stats['errors'][:5]:
                logger.warning(f"  - {error}")

        return self.stats

    # =========================================================================
    # TEAM AND CONFERENCE LOADING
    # =========================================================================

    def _load_teams_and_conferences(self, year: int = 2024):
        """Load college teams with SP+ ratings and conference info."""

        # Get FBS teams
        teams_df = self.cfbd.get_fbs_teams(year)

        # Get team talent composites
        talent_df = self.cfbd.get_team_talent(year)

        # Get SP+ ratings
        sp_df = self.cfbd.get_sp_ratings(year)

        if teams_df.empty:
            logger.warning("No teams data retrieved")
            return

        with self.driver.session() as session:
            # Create conferences first
            conferences = teams_df['conference'].dropna().unique()
            for conf in conferences:
                tier = self.cfbd.CONFERENCE_TIERS.get(conf, 1.0)
                session.run("""
                    MERGE (c:Conference {name: $name})
                    SET c.conference_id = $conf_id,
                        c.tier_multiplier = $tier,
                        c.updated_at = datetime()
                """, {
                    'name': conf,
                    'conf_id': conf.lower().replace(' ', '_'),
                    'tier': tier
                })

            # Create team nodes
            for _, team in teams_df.iterrows():
                team_name = team.get('school', team.get('team'))
                if not team_name:
                    continue

                # Get talent score
                talent_row = talent_df[talent_df['school'] == team_name] if not talent_df.empty else pd.DataFrame()
                talent_score = talent_row['talent'].values[0] if not talent_row.empty else None

                # Get SP+ rating
                sp_row = sp_df[sp_df['team'] == team_name] if not sp_df.empty else pd.DataFrame()
                sp_rating = sp_row['rating'].values[0] if not sp_row.empty else None
                sp_offense = sp_row.get('offense', {}).get('rating') if not sp_row.empty else None

                session.run("""
                    MERGE (t:CollegeTeam {name: $name})
                    SET t.team_id = $team_id,
                        t.abbreviation = $abbr,
                        t.mascot = $mascot,
                        t.conference = $conference,
                        t.division = $division,
                        t.talent_composite = $talent,
                        t.sp_plus_rating = $sp_rating,
                        t.sp_offense_rating = $sp_offense,
                        t.updated_at = datetime()

                    WITH t
                    MATCH (c:Conference {name: $conference})
                    MERGE (t)-[:IN_CONFERENCE]->(c)
                """, {
                    'name': team_name,
                    'team_id': team_name.lower().replace(' ', '_').replace('&', 'and'),
                    'abbr': team.get('abbreviation'),
                    'mascot': team.get('mascot'),
                    'conference': team.get('conference'),
                    'division': team.get('division'),
                    'talent': float(talent_score) if talent_score else None,
                    'sp_rating': float(sp_rating) if sp_rating else None,
                    'sp_offense': float(sp_offense) if sp_offense else None
                })

                self.stats['teams_created'] += 1

        logger.info(f"Loaded {self.stats['teams_created']} college teams")

    # =========================================================================
    # RECRUITING DATA LOADING
    # =========================================================================

    def _load_recruiting_data(self, years: List[int]):
        """Load recruiting rankings for fantasy-relevant positions."""

        all_recruits = []

        for year in years:
            for position in self.cfbd.FANTASY_POSITIONS:
                try:
                    df = self.cfbd.get_recruiting_players(year, position=position)
                    if not df.empty:
                        all_recruits.append(df)
                        logger.info(f"  {year} {position}: {len(df)} recruits")
                except Exception as e:
                    logger.warning(f"  Failed to fetch {year} {position}: {e}")
                    self.stats['errors'].append(f"Recruiting {year} {position}: {e}")

        if not all_recruits:
            logger.warning("No recruiting data retrieved")
            return

        recruits_df = pd.concat(all_recruits, ignore_index=True)

        # Filter to 3+ star recruits
        if 'stars' in recruits_df.columns:
            recruits_df = recruits_df[recruits_df['stars'] >= 3]

        logger.info(f"Processing {len(recruits_df)} total recruits...")

        with self.driver.session() as session:
            for _, recruit in recruits_df.iterrows():
                try:
                    name = recruit.get('name', '')
                    if not name:
                        continue

                    # Generate prospect ID
                    college = recruit.get('committedTo', recruit.get('college', ''))
                    prospect_id = self._generate_prospect_id(name, college)

                    # Calculate recruiting class year
                    recruit_year = recruit.get('recruiting_year', recruit.get('year'))

                    session.run("""
                        MERGE (p:Prospect {name: $name})
                        ON CREATE SET p.prospect_id = $prospect_id
                        SET p.position = $position,
                            p.height = $height,
                            p.weight = $weight,
                            p.recruiting_class = $recruit_year,
                            p.stars = $stars,
                            p.recruiting_rating = $rating,
                            p.national_rank = $rank,
                            p.position_rank = $pos_rank,
                            p.state = $state,
                            p.city = $city,
                            p.college = $college,
                            p.updated_at = datetime()

                        WITH p
                        MATCH (t:CollegeTeam {name: $college})
                        MERGE (p)-[r:PLAYED_FOR]->(t)
                        SET r.start_year = $recruit_year
                    """, {
                        'name': name,
                        'prospect_id': prospect_id,
                        'position': recruit.get('position'),
                        'height': recruit.get('height'),
                        'weight': recruit.get('weight'),
                        'recruit_year': int(recruit_year) if recruit_year else None,
                        'stars': int(recruit.get('stars')) if recruit.get('stars') else None,
                        'rating': float(recruit.get('rating')) if recruit.get('rating') else None,
                        'rank': int(recruit.get('ranking')) if recruit.get('ranking') else None,
                        'pos_rank': int(recruit.get('positionRank')) if recruit.get('positionRank') else None,
                        'state': recruit.get('stateProvince'),
                        'city': recruit.get('city'),
                        'college': college
                    })

                    self.stats['prospects_created'] += 1

                except Exception as e:
                    self.stats['errors'].append(f"Recruit {recruit.get('name')}: {e}")

        logger.info(f"Created/updated {self.stats['prospects_created']} prospects from recruiting data")

    # =========================================================================
    # COLLEGE STATS LOADING
    # =========================================================================

    def _load_college_stats(self, years: List[int]):
        """Load college player statistics by season."""

        categories = ['passing', 'rushing', 'receiving']

        for year in years:
            logger.info(f"  Loading {year} stats...")

            # Get all stats for the year
            all_stats = self.cfbd.get_all_player_stats(year, categories=categories)

            if all_stats.empty:
                continue

            # Get player usage data for advanced metrics
            try:
                usage_df = self.cfbd.get_player_usage(year)
            except Exception:
                usage_df = pd.DataFrame()

            # Group stats by player
            player_stats = self._aggregate_player_stats(all_stats, year)

            with self.driver.session() as session:
                for player_name, stats in player_stats.items():
                    try:
                        # Generate stats ID
                        stats_id = f"{player_name.lower().replace(' ', '_')}_{year}"

                        # Get usage metrics if available
                        usage = {}
                        if not usage_df.empty and 'name' in usage_df.columns:
                            usage_row = usage_df[usage_df['name'] == player_name]
                            if not usage_row.empty:
                                usage = usage_row.iloc[0].to_dict()

                        # Create CollegeStats node
                        session.run("""
                            MERGE (s:CollegeStats {stats_id: $stats_id})
                            SET s.season = $season,
                                s.team = $team,
                                s.position = $position,
                                s.games = $games,
                                s.pass_yards = $pass_yards,
                                s.pass_tds = $pass_tds,
                                s.rush_yards = $rush_yards,
                                s.rush_tds = $rush_tds,
                                s.receptions = $receptions,
                                s.rec_yards = $rec_yards,
                                s.rec_tds = $rec_tds,
                                s.targets = $targets,
                                s.usage_overall = $usage,
                                s.usage_pass = $usage_pass,
                                s.usage_rush = $usage_rush,
                                s.ppa_overall = $ppa,
                                s.updated_at = datetime()

                            WITH s
                            MATCH (p:Prospect {name: $name})
                            MERGE (p)-[:HAS_COLLEGE_STATS]->(s)

                            WITH s
                            MATCH (t:CollegeTeam {name: $team})
                            MERGE (s)-[:FOR_TEAM]->(t)
                        """, {
                            'stats_id': stats_id,
                            'name': player_name,
                            'season': year,
                            'team': stats.get('team'),
                            'position': stats.get('position'),
                            'games': stats.get('games'),
                            'pass_yards': stats.get('YDS_passing'),
                            'pass_tds': stats.get('TD_passing'),
                            'rush_yards': stats.get('YDS_rushing'),
                            'rush_tds': stats.get('TD_rushing'),
                            'receptions': stats.get('REC_receiving'),
                            'rec_yards': stats.get('YDS_receiving'),
                            'rec_tds': stats.get('TD_receiving'),
                            'targets': stats.get('targets'),
                            'usage': usage.get('usage', {}).get('overall'),
                            'usage_pass': usage.get('usage', {}).get('pass'),
                            'usage_rush': usage.get('usage', {}).get('rush'),
                            'ppa': usage.get('ppa')
                        })

                        self.stats['stats_created'] += 1

                    except Exception as e:
                        self.stats['errors'].append(f"Stats {player_name} {year}: {e}")

        logger.info(f"Created {self.stats['stats_created']} college stats records")

    def _aggregate_player_stats(self, df: pd.DataFrame, year: int) -> Dict[str, Dict]:
        """Aggregate stats by player across categories."""

        player_stats = {}

        for _, row in df.iterrows():
            player = row.get('player', '')
            if not player:
                continue

            if player not in player_stats:
                player_stats[player] = {
                    'team': row.get('team'),
                    'position': row.get('position'),
                    'season': year,
                    'games': 1
                }

            # Add stat type with prefix
            stat_type = row.get('statType', '')
            category = row.get('category', '')
            stat_value = row.get('stat')

            if stat_type and stat_value is not None:
                key = f"{stat_type}_{category}"
                try:
                    player_stats[player][key] = float(stat_value)
                except (ValueError, TypeError):
                    pass

        return player_stats

    # =========================================================================
    # COMBINE DATA LOADING
    # =========================================================================

    def _load_combine_data(self):
        """Load NFL Combine data from nflverse."""

        try:
            # Import nflverse loader
            from .nflverse_loader import NFLverseLoader
            nfl_loader = NFLverseLoader()

            combine_df = nfl_loader.load_combine()

            if combine_df.empty:
                logger.warning("No combine data available")
                return

            logger.info(f"Processing {len(combine_df)} combine results...")

            with self.driver.session() as session:
                for _, row in combine_df.iterrows():
                    try:
                        player_name = row.get('player_name', row.get('display_name', ''))
                        if not player_name:
                            continue

                        # Generate combine ID
                        year = row.get('season', row.get('draft_year', 2024))
                        combine_id = f"{player_name.lower().replace(' ', '_')}_{year}"

                        # Calculate athletic scores
                        speed_score = self._calculate_speed_score(
                            row.get('wt', row.get('weight')),
                            row.get('forty', row.get('forty_yard'))
                        )

                        session.run("""
                            MERGE (c:CombineResult {combine_id: $combine_id})
                            SET c.year = $year,
                                c.position = $position,
                                c.height = $height,
                                c.weight = $weight,
                                c.forty_yard = $forty,
                                c.bench_press = $bench,
                                c.vertical_jump = $vertical,
                                c.broad_jump = $broad,
                                c.three_cone = $cone,
                                c.shuttle = $shuttle,
                                c.speed_score = $speed_score,
                                c.updated_at = datetime()

                            WITH c
                            MATCH (p:Prospect {name: $name})
                            MERGE (p)-[:HAS_COMBINE]->(c)
                            SET p.forty_yard = $forty,
                                p.vertical_jump = $vertical,
                                p.speed_score = $speed_score
                        """, {
                            'combine_id': combine_id,
                            'name': player_name,
                            'year': int(year) if year else None,
                            'position': row.get('pos', row.get('position')),
                            'height': row.get('ht', row.get('height')),
                            'weight': row.get('wt', row.get('weight')),
                            'forty': row.get('forty', row.get('forty_yard')),
                            'bench': row.get('bench', row.get('bench_press')),
                            'vertical': row.get('vertical', row.get('vertical_jump')),
                            'broad': row.get('broad_jump'),
                            'cone': row.get('three_cone'),
                            'shuttle': row.get('shuttle'),
                            'speed_score': speed_score
                        })

                        self.stats['combine_created'] += 1

                    except Exception as e:
                        self.stats['errors'].append(f"Combine {row.get('player_name')}: {e}")

            logger.info(f"Loaded {self.stats['combine_created']} combine results")

        except ImportError:
            logger.warning("NFLverse loader not available for combine data")
        except Exception as e:
            logger.error(f"Error loading combine data: {e}")
            self.stats['errors'].append(f"Combine loading: {e}")

    def _calculate_speed_score(self, weight, forty) -> Optional[float]:
        """Calculate Bill Kelley's Speed Score: (Weight * 200) / (Forty^4)"""
        try:
            if weight and forty and forty > 0:
                return (float(weight) * 200) / (float(forty) ** 4)
        except (ValueError, TypeError):
            pass
        return None

    # =========================================================================
    # DRAFT LINKING
    # =========================================================================

    def _link_draft_picks(self, years: List[int]):
        """Link prospects to NFL players via draft picks."""

        all_picks = []

        for year in years:
            try:
                picks = self.cfbd.get_draft_picks(year=year)
                if not picks.empty:
                    all_picks.append(picks)
                    logger.info(f"  {year}: {len(picks)} picks")
            except Exception as e:
                logger.warning(f"  Failed to fetch {year} draft picks: {e}")

        if not all_picks:
            logger.warning("No draft data retrieved")
            return

        draft_df = pd.concat(all_picks, ignore_index=True)

        # Filter to fantasy positions
        if 'position' in draft_df.columns:
            fantasy_positions = ['QB', 'RB', 'WR', 'TE', 'FB']
            draft_df = draft_df[draft_df['position'].isin(fantasy_positions)]

        with self.driver.session() as session:
            for _, pick in draft_df.iterrows():
                try:
                    name = pick.get('name', '')
                    if not name:
                        continue

                    draft_year = pick.get('year')
                    round_num = pick.get('round')
                    pick_num = pick.get('pick')
                    nfl_team = pick.get('nflTeam')
                    college = pick.get('collegeTeam')

                    # First ensure Prospect exists
                    session.run("""
                        MERGE (p:Prospect {name: $name})
                        SET p.draft_year = $draft_year,
                            p.draft_round = $round,
                            p.draft_pick = $pick,
                            p.nfl_team = $nfl_team,
                            p.was_drafted = true,
                            p.updated_at = datetime()
                    """, {
                        'name': name,
                        'draft_year': int(draft_year) if draft_year else None,
                        'round': int(round_num) if round_num else None,
                        'pick': int(pick_num) if pick_num else None,
                        'nfl_team': nfl_team
                    })

                    # Try to link to NFL Player node
                    result = session.run("""
                        MATCH (prospect:Prospect {name: $name})
                        MATCH (player:Player)
                        WHERE player.full_name = $name
                           OR player.display_name = $name
                           OR player.name = $name

                        MERGE (prospect)-[r:BECAME_NFL_PLAYER]->(player)
                        SET r.draft_year = $draft_year,
                            r.draft_round = $round,
                            r.draft_pick = $pick

                        WITH player, prospect
                        MERGE (player)-[:COLLEGE_PROFILE]->(prospect)

                        RETURN player.name as linked_player
                    """, {
                        'name': name,
                        'draft_year': int(draft_year) if draft_year else None,
                        'round': int(round_num) if round_num else None,
                        'pick': int(pick_num) if pick_num else None
                    })

                    if result.peek():
                        self.stats['draft_links'] += 1

                except Exception as e:
                    self.stats['errors'].append(f"Draft link {pick.get('name')}: {e}")

        logger.info(f"Established {self.stats['draft_links']} prospect-to-NFL links")

    # =========================================================================
    # DEVY VALUES LOADING
    # =========================================================================

    def _load_devy_values(self):
        """Load KTC devy values for prospects."""

        try:
            df = self.ktc_devy.fetch_devy_rankings(superflex=True)

            if df is None or df.empty:
                logger.warning("No devy values retrieved")
                return

            count = self.ktc_devy.load_devy_values_to_neo4j(df, superflex=True)
            self.stats['devy_snapshots'] = count

            # Link temporal snapshots
            self.ktc_devy.link_devy_snapshots_temporal()

            logger.info(f"Loaded {count} devy snapshots")

        except Exception as e:
            logger.error(f"Error loading devy values: {e}")
            self.stats['errors'].append(f"Devy loading: {e}")

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def _generate_prospect_id(self, name: str, college: str) -> str:
        """Generate unique prospect ID."""
        combined = f"{name.lower()}_{(college or 'unknown').lower()}"
        return hashlib.md5(combined.encode()).hexdigest()[:12]

    def get_etl_stats(self) -> Dict:
        """Return ETL statistics."""
        return self.stats

    def verify_data(self) -> Dict[str, int]:
        """Verify data loaded correctly with node counts."""

        with self.driver.session() as session:
            result = session.run("""
                MATCH (p:Prospect) WITH count(p) as prospects
                MATCH (t:CollegeTeam) WITH prospects, count(t) as teams
                MATCH (s:CollegeStats) WITH prospects, teams, count(s) as stats
                MATCH (c:CombineResult) WITH prospects, teams, stats, count(c) as combine
                MATCH (d:DevySnapshot) WITH prospects, teams, stats, combine, count(d) as devy
                MATCH (:Prospect)-[r:BECAME_NFL_PLAYER]->(:Player)
                WITH prospects, teams, stats, combine, devy, count(r) as nfl_links
                RETURN prospects, teams, stats, combine, devy, nfl_links
            """)

            record = result.single()
            return {
                'prospects': record['prospects'],
                'teams': record['teams'],
                'stats': record['stats'],
                'combine': record['combine'],
                'devy': record['devy'],
                'nfl_links': record['nfl_links']
            }


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    parser = argparse.ArgumentParser(description='College Football ETL Pipeline')
    parser.add_argument('--years', type=int, nargs='+', help='Recruiting years to load')
    parser.add_argument('--no-devy', action='store_true', help='Skip KTC devy loading')
    parser.add_argument('--no-combine', action='store_true', help='Skip combine data')
    parser.add_argument('--verify', action='store_true', help='Only verify existing data')

    args = parser.parse_args()

    etl = CollegeToNeo4jETL()

    try:
        if args.verify:
            print("\n=== Verifying College Data ===")
            counts = etl.verify_data()
            for node_type, count in counts.items():
                print(f"  {node_type}: {count}")
        else:
            print("\n=== Running College Football ETL ===")
            stats = etl.run_full_etl(
                recruiting_years=args.years,
                include_devy=not args.no_devy,
                include_combine=not args.no_combine
            )

            print("\n=== Verification ===")
            counts = etl.verify_data()
            for node_type, count in counts.items():
                print(f"  {node_type}: {count}")

    finally:
        etl.close()
