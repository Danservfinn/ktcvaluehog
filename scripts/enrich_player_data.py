#!/usr/bin/env python3
"""
Comprehensive Player Data Enrichment Script
Loads all NFLverse stats and KTC values into Neo4j Player nodes.
"""

import logging
import pandas as pd
from pathlib import Path
from neo4j import GraphDatabase

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.loaders.nflverse_loader import NFLverseLoader
from src.config import NEO4J_URI


class PlayerDataEnricher:
    """Enrich Neo4j Player nodes with comprehensive stats."""

    def __init__(self, driver):
        self.driver = driver
        self.loader = NFLverseLoader()

    def load_ktc_from_file(self) -> int:
        """Load KTC values from existing CSV file."""
        ktc_file = Path(__file__).parent.parent / "data" / "ktc_values.csv"

        if not ktc_file.exists():
            logger.warning(f"KTC file not found: {ktc_file}")
            return 0

        df = pd.read_csv(ktc_file)
        logger.info(f"Loaded {len(df)} players from KTC file")

        count = 0
        with self.driver.session() as session:
            for _, row in df.iterrows():
                name = row.get('name')
                sf_value = row.get('sf_value', 0)
                oneqb_value = row.get('oneqb_value', 0)
                age = row.get('age')
                position = row.get('position')

                result = session.run("""
                    MATCH (p:Player)
                    WHERE toLower(p.name) = toLower($name)
                       OR p.name CONTAINS $name
                    SET p.ktc_value = $sf_value,
                        p.ktc_1qb_value = $oneqb_value,
                        p.ktc_updated = datetime()
                    RETURN count(p) as updated
                """, {
                    'name': name,
                    'sf_value': int(sf_value) if pd.notna(sf_value) else 0,
                    'oneqb_value': int(oneqb_value) if pd.notna(oneqb_value) else 0
                })

                record = result.single()
                if record and record['updated'] > 0:
                    count += 1

        logger.info(f"Updated KTC values for {count} players")
        return count

    def load_player_stats(self, seasons: list = None) -> int:
        """Load comprehensive player stats into Neo4j."""
        seasons = seasons or [2023, 2024, 2025]

        logger.info(f"Loading player stats for seasons: {seasons}")

        # Load weekly stats
        try:
            stats_df = self.loader.load_player_stats(seasons, summary_level='week')
            logger.info(f"Loaded {len(stats_df)} weekly stat records")
        except Exception as e:
            logger.error(f"Failed to load player stats: {e}")
            return 0

        # Aggregate to season level
        agg_cols = {}
        numeric_cols = stats_df.select_dtypes(include=['number']).columns

        # Stats to sum
        sum_cols = [
            'completions', 'attempts', 'passing_yards', 'passing_tds', 'interceptions',
            'sacks', 'sack_yards', 'sack_fumbles', 'sack_fumbles_lost',
            'passing_air_yards', 'passing_yards_after_catch', 'passing_first_downs',
            'passing_2pt_conversions', 'carries', 'rushing_yards', 'rushing_tds',
            'rushing_fumbles', 'rushing_fumbles_lost', 'rushing_first_downs',
            'rushing_2pt_conversions', 'targets', 'receptions', 'receiving_yards',
            'receiving_tds', 'receiving_fumbles', 'receiving_fumbles_lost',
            'receiving_air_yards', 'receiving_yards_after_catch', 'receiving_first_downs',
            'receiving_2pt_conversions', 'special_teams_tds', 'fantasy_points',
            'fantasy_points_ppr'
        ]

        # Stats to average
        avg_cols = ['passing_epa', 'rushing_epa', 'receiving_epa']

        for col in sum_cols:
            if col in stats_df.columns:
                agg_cols[col] = 'sum'

        for col in avg_cols:
            if col in stats_df.columns:
                agg_cols[col] = 'mean'

        # Group by player and season
        if 'player_id' in stats_df.columns:
            id_col = 'player_id'
        elif 'gsis_id' in stats_df.columns:
            id_col = 'gsis_id'
        else:
            logger.error("No player ID column found")
            return 0

        grouped = stats_df.groupby([id_col, 'season']).agg(agg_cols).reset_index()
        logger.info(f"Aggregated to {len(grouped)} player-seasons")

        # Load into Neo4j
        count = 0
        with self.driver.session() as session:
            for _, row in grouped.iterrows():
                player_id = row[id_col]
                season = row['season']

                # Build SET clause dynamically
                set_parts = []
                params = {'player_id': player_id, 'season': int(season)}

                for col in agg_cols.keys():
                    if col in row and pd.notna(row[col]):
                        prop_name = col
                        set_parts.append(f"p.{prop_name} = ${prop_name}")
                        params[prop_name] = float(row[col])

                if not set_parts:
                    continue

                set_clause = ", ".join(set_parts)

                query = f"""
                    MATCH (p:Player)
                    WHERE p.gsis_id = $player_id OR p.player_id = $player_id
                    SET {set_clause},
                        p.stats_season = $season,
                        p.stats_updated = datetime()
                    RETURN count(p) as updated
                """

                try:
                    result = session.run(query, params)
                    record = result.single()
                    if record and record['updated'] > 0:
                        count += 1
                except Exception as e:
                    logger.debug(f"Error updating {player_id}: {e}")
                    continue

        logger.info(f"Updated stats for {count} players")
        return count

    def load_snap_counts(self, seasons: list = None) -> int:
        """Load snap count data."""
        seasons = seasons or [2023, 2024, 2025]

        logger.info("Loading snap counts...")

        try:
            snaps_df = self.loader.load_snap_counts(seasons)
            logger.info(f"Loaded {len(snaps_df)} snap count records")
        except Exception as e:
            logger.error(f"Failed to load snap counts: {e}")
            return 0

        # Aggregate to season level
        if 'pfr_player_id' in snaps_df.columns:
            id_col = 'pfr_player_id'
        elif 'player' in snaps_df.columns:
            id_col = 'player'
        else:
            logger.warning("No suitable ID column for snap counts")
            return 0

        agg_cols = {}
        for col in ['offense_snaps', 'offense_pct', 'defense_snaps', 'st_snaps']:
            if col in snaps_df.columns:
                agg_cols[col] = 'sum' if 'snaps' in col else 'mean'

        if not agg_cols:
            return 0

        grouped = snaps_df.groupby([id_col, 'season']).agg(agg_cols).reset_index()

        count = 0
        with self.driver.session() as session:
            for _, row in grouped.iterrows():
                player_name = row[id_col]

                params = {'name': player_name}
                set_parts = []

                if 'offense_snaps' in row and pd.notna(row['offense_snaps']):
                    set_parts.append("p.offense_snaps = $snaps")
                    params['snaps'] = int(row['offense_snaps'])

                if 'offense_pct' in row and pd.notna(row['offense_pct']):
                    set_parts.append("p.snap_pct = $snap_pct")
                    params['snap_pct'] = float(row['offense_pct'])

                if not set_parts:
                    continue

                query = f"""
                    MATCH (p:Player)
                    WHERE toLower(p.name) CONTAINS toLower($name)
                       OR p.pfr_id = $name
                    SET {", ".join(set_parts)}
                    RETURN count(p) as updated
                """

                try:
                    result = session.run(query, params)
                    record = result.single()
                    if record and record['updated'] > 0:
                        count += 1
                except:
                    continue

        logger.info(f"Updated snap counts for {count} players")
        return count

    def load_advanced_stats(self, seasons: list = None) -> int:
        """Load NextGen and PFR advanced stats."""
        seasons = seasons or [2023, 2024, 2025]

        total_updated = 0

        # NextGen receiving stats
        logger.info("Loading NextGen receiving stats...")
        try:
            ngs_rec = self.loader.load_nextgen_stats(seasons, 'receiving')
            logger.info(f"Loaded {len(ngs_rec)} NextGen receiving records")

            # Key receiving metrics
            count = 0
            with self.driver.session() as session:
                for _, row in ngs_rec.iterrows():
                    name = row.get('player_display_name', row.get('player_name', ''))
                    if not name:
                        continue

                    params = {'name': name}
                    set_parts = []

                    # Separation, cushion, YAC metrics
                    if 'avg_separation' in row and pd.notna(row['avg_separation']):
                        set_parts.append("p.ngs_separation = $sep")
                        params['sep'] = float(row['avg_separation'])

                    if 'avg_cushion' in row and pd.notna(row['avg_cushion']):
                        set_parts.append("p.ngs_cushion = $cushion")
                        params['cushion'] = float(row['avg_cushion'])

                    if 'avg_yac' in row and pd.notna(row['avg_yac']):
                        set_parts.append("p.ngs_yac = $yac")
                        params['yac'] = float(row['avg_yac'])

                    if 'avg_intended_air_yards' in row and pd.notna(row['avg_intended_air_yards']):
                        set_parts.append("p.ngs_air_yards = $ay")
                        params['ay'] = float(row['avg_intended_air_yards'])

                    if not set_parts:
                        continue

                    query = f"""
                        MATCH (p:Player)
                        WHERE toLower(p.name) = toLower($name)
                        SET {", ".join(set_parts)}
                        RETURN count(p) as updated
                    """

                    try:
                        result = session.run(query, params)
                        record = result.single()
                        if record and record['updated'] > 0:
                            count += 1
                    except:
                        continue

            logger.info(f"Updated NextGen receiving for {count} players")
            total_updated += count

        except Exception as e:
            logger.warning(f"Failed to load NextGen receiving: {e}")

        # NextGen rushing stats
        logger.info("Loading NextGen rushing stats...")
        try:
            ngs_rush = self.loader.load_nextgen_stats(seasons, 'rushing')
            logger.info(f"Loaded {len(ngs_rush)} NextGen rushing records")

            count = 0
            with self.driver.session() as session:
                for _, row in ngs_rush.iterrows():
                    name = row.get('player_display_name', row.get('player_name', ''))
                    if not name:
                        continue

                    params = {'name': name}
                    set_parts = []

                    if 'efficiency' in row and pd.notna(row['efficiency']):
                        set_parts.append("p.ngs_rush_efficiency = $eff")
                        params['eff'] = float(row['efficiency'])

                    if 'avg_time_to_los' in row and pd.notna(row['avg_time_to_los']):
                        set_parts.append("p.ngs_time_to_los = $ttlos")
                        params['ttlos'] = float(row['avg_time_to_los'])

                    if 'rush_yards_over_expected_per_att' in row and pd.notna(row['rush_yards_over_expected_per_att']):
                        set_parts.append("p.ngs_ryoe = $ryoe")
                        params['ryoe'] = float(row['rush_yards_over_expected_per_att'])

                    if not set_parts:
                        continue

                    query = f"""
                        MATCH (p:Player)
                        WHERE toLower(p.name) = toLower($name)
                        SET {", ".join(set_parts)}
                        RETURN count(p) as updated
                    """

                    try:
                        result = session.run(query, params)
                        record = result.single()
                        if record and record['updated'] > 0:
                            count += 1
                    except:
                        continue

            logger.info(f"Updated NextGen rushing for {count} players")
            total_updated += count

        except Exception as e:
            logger.warning(f"Failed to load NextGen rushing: {e}")

        # PFR receiving stats
        logger.info("Loading PFR receiving stats...")
        try:
            pfr_rec = self.loader.load_pfr_advstats(seasons, 'rec', 'season')
            logger.info(f"Loaded {len(pfr_rec)} PFR receiving records")

            count = 0
            with self.driver.session() as session:
                for _, row in pfr_rec.iterrows():
                    name = row.get('player_display_name', row.get('player', ''))
                    if not name:
                        continue

                    params = {'name': name}
                    set_parts = []

                    if 'avg_yac' in row and pd.notna(row['avg_yac']):
                        set_parts.append("p.pfr_yac = $yac")
                        params['yac'] = float(row['avg_yac'])

                    if 'adot' in row and pd.notna(row['adot']):
                        set_parts.append("p.pfr_adot = $adot")
                        params['adot'] = float(row['adot'])

                    if 'rec_br_tkl' in row and pd.notna(row['rec_br_tkl']):
                        set_parts.append("p.pfr_broken_tackles = $bt")
                        params['bt'] = int(row['rec_br_tkl'])

                    if 'drop_rate' in row and pd.notna(row['drop_rate']):
                        set_parts.append("p.pfr_drop_rate = $dr")
                        params['dr'] = float(row['drop_rate'])

                    if 'rec_tgt_share' in row and pd.notna(row['rec_tgt_share']):
                        set_parts.append("p.target_share = $ts")
                        params['ts'] = float(row['rec_tgt_share'])

                    if not set_parts:
                        continue

                    query = f"""
                        MATCH (p:Player)
                        WHERE toLower(p.name) = toLower($name)
                        SET {", ".join(set_parts)}
                        RETURN count(p) as updated
                    """

                    try:
                        result = session.run(query, params)
                        record = result.single()
                        if record and record['updated'] > 0:
                            count += 1
                    except:
                        continue

            logger.info(f"Updated PFR receiving for {count} players")
            total_updated += count

        except Exception as e:
            logger.warning(f"Failed to load PFR receiving: {e}")

        return total_updated

    def calculate_derived_features(self) -> int:
        """Calculate derived features from loaded stats."""
        logger.info("Calculating derived features...")

        with self.driver.session() as session:
            # Fantasy points per game
            result = session.run("""
                MATCH (p:Player)
                WHERE p.fantasy_points_ppr IS NOT NULL AND p.fantasy_points_ppr > 0
                WITH p,
                     CASE WHEN p.games_played > 0 THEN p.games_played ELSE 17 END as games
                SET p.fpts_per_game = p.fantasy_points_ppr / games
                RETURN count(p) as updated
            """)
            fpts_count = result.single()['updated']
            logger.info(f"Calculated fpts_per_game for {fpts_count} players")

            # Target share (if not already set)
            result = session.run("""
                MATCH (p:Player)
                WHERE p.targets IS NOT NULL AND p.targets > 0
                  AND p.target_share IS NULL
                  AND p.current_team IS NOT NULL
                WITH p
                MATCH (t:Player)
                WHERE t.current_team = p.current_team AND t.targets IS NOT NULL
                WITH p, sum(t.targets) as team_targets
                WHERE team_targets > 0
                SET p.target_share = toFloat(p.targets) / team_targets
                RETURN count(p) as updated
            """)
            ts_count = result.single()['updated']
            logger.info(f"Calculated target_share for {ts_count} players")

            # Yards per target
            result = session.run("""
                MATCH (p:Player)
                WHERE p.receiving_yards IS NOT NULL AND p.targets > 0
                SET p.yards_per_target = toFloat(p.receiving_yards) / p.targets
                RETURN count(p) as updated
            """)
            ypt_count = result.single()['updated']
            logger.info(f"Calculated yards_per_target for {ypt_count} players")

            # TD rate
            result = session.run("""
                MATCH (p:Player)
                WHERE p.receiving_tds IS NOT NULL AND p.targets > 0
                SET p.td_rate = toFloat(p.receiving_tds) / p.targets
                RETURN count(p) as updated
            """)
            td_count = result.single()['updated']
            logger.info(f"Calculated td_rate for {td_count} players")

            # Yards per carry for RBs
            result = session.run("""
                MATCH (p:Player)
                WHERE p.rushing_yards IS NOT NULL AND p.carries > 0
                SET p.yards_per_carry = toFloat(p.rushing_yards) / p.carries
                RETURN count(p) as updated
            """)
            ypc_count = result.single()['updated']
            logger.info(f"Calculated yards_per_carry for {ypc_count} players")

        return fpts_count + ts_count + ypt_count + td_count + ypc_count

    def run_full_enrichment(self, seasons: list = None) -> dict:
        """Run full data enrichment pipeline."""
        seasons = seasons or [2023, 2024, 2025]

        results = {}

        logger.info("=" * 60)
        logger.info("PLAYER DATA ENRICHMENT")
        logger.info("=" * 60)

        # 1. Load KTC values
        logger.info("\n--- Loading KTC Values ---")
        results['ktc'] = self.load_ktc_from_file()

        # 2. Load player stats
        logger.info("\n--- Loading Player Stats ---")
        results['stats'] = self.load_player_stats(seasons)

        # 3. Load snap counts
        logger.info("\n--- Loading Snap Counts ---")
        results['snaps'] = self.load_snap_counts(seasons)

        # 4. Load advanced stats
        logger.info("\n--- Loading Advanced Stats ---")
        results['advanced'] = self.load_advanced_stats(seasons)

        # 5. Calculate derived features
        logger.info("\n--- Calculating Derived Features ---")
        results['derived'] = self.calculate_derived_features()

        logger.info("\n" + "=" * 60)
        logger.info("ENRICHMENT COMPLETE")
        logger.info(f"Results: {results}")
        logger.info("=" * 60)

        return results


def main():
    """Run data enrichment."""
    driver = GraphDatabase.driver(NEO4J_URI, auth=None)

    enricher = PlayerDataEnricher(driver)
    results = enricher.run_full_enrichment(seasons=[2023, 2024, 2025])

    driver.close()

    print("\nEnrichment Summary:")
    for key, value in results.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
