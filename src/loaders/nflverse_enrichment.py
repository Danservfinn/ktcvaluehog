"""
NFLverse Data Enrichment Module

Loads comprehensive data from nflverse to enrich player profiles:
- Athletic Profile (Combine)
- Draft Capital
- Contract Value
- Injury History
- Snap Counts
- Advanced Stats (NextGen, QBR)

These features are designed to predict dynasty value changes.
"""

import ssl
import certifi
import os

# Fix SSL certificate issues for nfl_data_py
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
ssl._create_default_https_context = ssl._create_unverified_context

import nfl_data_py as nfl
import pandas as pd
import numpy as np
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from neo4j import GraphDatabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NFLverseEnrichment:
    """
    Comprehensive data enrichment from NFLverse sources.

    Features loaded:
    1. Combine: Athletic measurements (40 time, vertical, etc.)
    2. Draft: Draft capital, career value
    3. Contracts: Salary, guaranteed money, cap %
    4. Injuries: Injury frequency, games missed
    5. Snap Counts: Playing time, trend
    6. NextGen Stats: Separation, YAC, RYOE
    7. QBR: QB performance ratings
    """

    def __init__(self, neo4j_uri: str = "bolt://localhost:7687",
                 neo4j_auth: tuple = ("neo4j", "dynasty123")):
        self.driver = GraphDatabase.driver(neo4j_uri, auth=neo4j_auth)
        self.cache_dir = Path(__file__).parent.parent.parent / "data" / "nflverse"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def close(self):
        self.driver.close()

    # =========================================================================
    # DATA LOADERS
    # =========================================================================

    def load_combine_data(self, years: List[int] = None) -> pd.DataFrame:
        """Load NFL Combine athletic measurements."""
        years = years or list(range(2015, 2025))
        logger.info(f"Loading combine data for {years}...")

        try:
            combine = nfl.import_combine_data(years)
            logger.info(f"Loaded {len(combine)} combine records")
            return combine
        except Exception as e:
            logger.error(f"Failed to load combine data: {e}")
            return pd.DataFrame()

    def load_draft_data(self, years: List[int] = None) -> pd.DataFrame:
        """Load draft pick data with career value."""
        years = years or list(range(2015, 2025))
        logger.info(f"Loading draft data for {years}...")

        try:
            draft = nfl.import_draft_picks(years)
            logger.info(f"Loaded {len(draft)} draft records")
            return draft
        except Exception as e:
            logger.error(f"Failed to load draft data: {e}")
            return pd.DataFrame()

    def load_contracts(self) -> pd.DataFrame:
        """Load historical contract data."""
        logger.info("Loading contract data...")

        try:
            contracts = nfl.import_contracts()
            # Filter to active/recent contracts
            contracts = contracts[contracts['is_active'] == True].copy()
            logger.info(f"Loaded {len(contracts)} active contracts")
            return contracts
        except Exception as e:
            logger.error(f"Failed to load contracts: {e}")
            return pd.DataFrame()

    def load_injuries(self, years: List[int] = None) -> pd.DataFrame:
        """Load injury report data."""
        years = years or [2022, 2023, 2024]
        logger.info(f"Loading injury data for {years}...")

        try:
            injuries = nfl.import_injuries(years)
            logger.info(f"Loaded {len(injuries)} injury records")
            return injuries
        except Exception as e:
            logger.error(f"Failed to load injuries: {e}")
            return pd.DataFrame()

    def load_snap_counts(self, years: List[int] = None) -> pd.DataFrame:
        """Load snap count data."""
        years = years or [2023, 2024]
        logger.info(f"Loading snap counts for {years}...")

        try:
            snaps = nfl.import_snap_counts(years)
            logger.info(f"Loaded {len(snaps)} snap records")
            return snaps
        except Exception as e:
            logger.error(f"Failed to load snap counts: {e}")
            return pd.DataFrame()

    def load_nextgen_receiving(self, years: List[int] = None) -> pd.DataFrame:
        """Load NextGen receiving stats."""
        years = years or [2023, 2024]
        logger.info(f"Loading NextGen receiving for {years}...")

        try:
            ngs = nfl.import_ngs_data('receiving', years)
            logger.info(f"Loaded {len(ngs)} NextGen receiving records")
            return ngs
        except Exception as e:
            logger.error(f"Failed to load NextGen receiving: {e}")
            return pd.DataFrame()

    def load_nextgen_rushing(self, years: List[int] = None) -> pd.DataFrame:
        """Load NextGen rushing stats."""
        years = years or [2023, 2024]
        logger.info(f"Loading NextGen rushing for {years}...")

        try:
            ngs = nfl.import_ngs_data('rushing', years)
            logger.info(f"Loaded {len(ngs)} NextGen rushing records")
            return ngs
        except Exception as e:
            logger.error(f"Failed to load NextGen rushing: {e}")
            return pd.DataFrame()

    def load_qbr(self, years: List[int] = None) -> pd.DataFrame:
        """Load ESPN QBR data."""
        years = years or [2023, 2024]
        logger.info(f"Loading QBR for {years}...")

        try:
            qbr = nfl.import_qbr(years)
            logger.info(f"Loaded {len(qbr)} QBR records")
            return qbr
        except Exception as e:
            logger.error(f"Failed to load QBR: {e}")
            return pd.DataFrame()

    def load_rosters(self, years: List[int] = None) -> pd.DataFrame:
        """Load roster data for player IDs."""
        years = years or [2024]
        logger.info(f"Loading rosters for {years}...")

        try:
            rosters = nfl.import_seasonal_rosters(years)
            logger.info(f"Loaded {len(rosters)} roster entries")
            return rosters
        except Exception as e:
            logger.error(f"Failed to load rosters: {e}")
            return pd.DataFrame()

    # =========================================================================
    # FEATURE ENGINEERING
    # =========================================================================

    def calculate_athletic_score(self, combine: pd.DataFrame) -> pd.DataFrame:
        """Calculate composite athletic score from combine metrics."""
        if combine.empty:
            return pd.DataFrame()

        df = combine.copy()

        # Normalize metrics (lower is better for 40, cone, shuttle)
        # Higher is better for vertical, broad_jump, bench

        # Z-score normalization by position
        metrics = {
            'forty': -1,      # Lower is better
            'vertical': 1,    # Higher is better
            'broad_jump': 1,
            'bench': 1,
            'cone': -1,       # Lower is better
            'shuttle': -1     # Lower is better
        }

        for metric, direction in metrics.items():
            if metric in df.columns:
                # Group by position for position-relative scoring
                df[f'{metric}_zscore'] = df.groupby('pos')[metric].transform(
                    lambda x: (x - x.mean()) / x.std() * direction if x.std() > 0 else 0
                )

        # Composite athletic score
        zscore_cols = [f'{m}_zscore' for m in metrics.keys() if f'{m}_zscore' in df.columns]
        df['athletic_score'] = df[zscore_cols].mean(axis=1, skipna=True)

        # Percentile rank
        df['athletic_percentile'] = df.groupby('pos')['athletic_score'].rank(pct=True) * 100

        return df[['player_name', 'pos', 'draft_year', 'draft_round', 'draft_ovr',
                   'ht', 'wt', 'forty', 'vertical', 'broad_jump', 'bench', 'cone', 'shuttle',
                   'athletic_score', 'athletic_percentile']].copy()

    def calculate_draft_capital(self, draft: pd.DataFrame) -> pd.DataFrame:
        """Calculate draft capital value."""
        if draft.empty:
            return pd.DataFrame()

        df = draft.copy()

        # Draft value curve (pick 1 = 1000, pick 32 = 500, pick 256 = 10)
        df['draft_value'] = 1000 * np.exp(-0.02 * (df['pick'] - 1))

        # Round-based capital (1st = 10, 7th = 1)
        df['round_capital'] = 11 - df['round']

        # Age at draft (younger = better)
        df['draft_age_factor'] = np.where(df['age'] < 22, 1.2,
                                 np.where(df['age'] < 23, 1.1,
                                 np.where(df['age'] < 24, 1.0,
                                 np.where(df['age'] < 25, 0.9, 0.8))))

        # Career value (from PFR)
        df['career_value'] = df['car_av'].fillna(0)

        return df

    def calculate_injury_risk(self, injuries: pd.DataFrame) -> pd.DataFrame:
        """Calculate injury risk metrics."""
        if injuries.empty:
            return pd.DataFrame()

        def get_most_common_injury(x):
            """Safely get most common injury type."""
            vc = x.dropna().value_counts()
            return vc.index[0] if len(vc) > 0 else None

        # Count injuries by player and season
        injury_counts = injuries.groupby(['gsis_id', 'season']).agg({
            'report_status': 'count',
            'report_primary_injury': get_most_common_injury
        }).reset_index()

        injury_counts.columns = ['gsis_id', 'season', 'injury_reports', 'primary_injury_type']

        # Aggregate across seasons
        player_injuries = injury_counts.groupby('gsis_id').agg({
            'injury_reports': 'sum',
            'season': 'count'
        }).reset_index()

        player_injuries.columns = ['gsis_id', 'total_injury_reports', 'seasons_tracked']
        player_injuries['injuries_per_season'] = (
            player_injuries['total_injury_reports'] / player_injuries['seasons_tracked']
        )

        # Injury risk score (higher = more risky)
        player_injuries['injury_risk_score'] = player_injuries['injuries_per_season'].clip(0, 20) / 20 * 100

        return player_injuries

    def calculate_snap_share(self, snaps: pd.DataFrame) -> pd.DataFrame:
        """Calculate snap share metrics."""
        if snaps.empty:
            return pd.DataFrame()

        # Aggregate by player and season
        player_snaps = snaps.groupby(['pfr_player_id', 'player', 'position', 'season']).agg({
            'offense_snaps': 'sum',
            'offense_pct': 'mean',
            'week': 'count'  # Games played
        }).reset_index()

        player_snaps.columns = ['pfr_player_id', 'player_name', 'position', 'season',
                                'total_offense_snaps', 'avg_snap_pct', 'games_played']

        # Calculate snap share trend using vectorized approach
        first_half = snaps[snaps['week'] <= 9].groupby(['pfr_player_id', 'season'])['offense_pct'].mean()
        second_half = snaps[snaps['week'] > 9].groupby(['pfr_player_id', 'season'])['offense_pct'].mean()

        snap_trends = (second_half - first_half).fillna(0).reset_index()
        snap_trends.columns = ['pfr_player_id', 'season', 'snap_trend']

        # Merge trends back to player_snaps
        player_snaps = player_snaps.merge(snap_trends, on=['pfr_player_id', 'season'], how='left')
        player_snaps['snap_trend'] = player_snaps['snap_trend'].fillna(0)

        return player_snaps

    def calculate_contract_value(self, contracts: pd.DataFrame) -> pd.DataFrame:
        """Calculate contract-based features."""
        if contracts.empty:
            return pd.DataFrame()

        df = contracts.copy()

        # Keep most recent contract per player
        df = df.sort_values('year_signed', ascending=False)
        df = df.drop_duplicates(subset=['gsis_id'], keep='first')

        # Contract quality metrics
        df['guaranteed_pct'] = np.where(df['value'] > 0, df['guaranteed'] / df['value'], 0)

        # Position-relative APY
        df['apy_percentile'] = df.groupby('position')['apy'].rank(pct=True) * 100

        return df[['gsis_id', 'player', 'position', 'team', 'year_signed', 'years',
                   'value', 'apy', 'guaranteed', 'guaranteed_pct', 'apy_cap_pct', 'apy_percentile']]

    # =========================================================================
    # NEO4J UPDATES
    # =========================================================================

    def update_athletic_profiles(self, combine: pd.DataFrame) -> int:
        """Update Player nodes with athletic profile data."""
        if combine.empty:
            return 0

        athletic = self.calculate_athletic_score(combine)
        updated = 0

        with self.driver.session() as session:
            for _, row in athletic.iterrows():
                try:
                    result = session.run("""
                        MATCH (p:Player)
                        WHERE toLower(p.name) = toLower($name)
                        SET p.combine_forty = $forty,
                            p.combine_vertical = $vertical,
                            p.combine_broad_jump = $broad_jump,
                            p.combine_bench = $bench,
                            p.combine_cone = $cone,
                            p.combine_shuttle = $shuttle,
                            p.athletic_score = $athletic_score,
                            p.athletic_percentile = $athletic_percentile,
                            p.combine_height = $height,
                            p.combine_weight = $weight
                        RETURN count(p) as updated
                    """, {
                        'name': row['player_name'],
                        'forty': row.get('forty'),
                        'vertical': row.get('vertical'),
                        'broad_jump': row.get('broad_jump'),
                        'bench': row.get('bench'),
                        'cone': row.get('cone'),
                        'shuttle': row.get('shuttle'),
                        'athletic_score': row.get('athletic_score'),
                        'athletic_percentile': row.get('athletic_percentile'),
                        'height': row.get('ht'),
                        'weight': row.get('wt')
                    })
                    updated += result.single()['updated']
                except Exception as e:
                    logger.debug(f"Error updating {row['player_name']}: {e}")

        logger.info(f"Updated athletic profiles for {updated} players")
        return updated

    def update_draft_capital(self, draft: pd.DataFrame) -> int:
        """Update Player nodes with draft capital data."""
        if draft.empty:
            return 0

        draft_data = self.calculate_draft_capital(draft)
        updated = 0

        with self.driver.session() as session:
            for _, row in draft_data.iterrows():
                try:
                    result = session.run("""
                        MATCH (p:Player)
                        WHERE p.gsis_id = $gsis_id OR toLower(p.name) = toLower($name)
                        SET p.draft_round = $round,
                            p.draft_pick = $pick,
                            p.draft_year = $season,
                            p.draft_value = $draft_value,
                            p.round_capital = $round_capital,
                            p.draft_age = $age,
                            p.career_av = $career_value
                        RETURN count(p) as updated
                    """, {
                        'gsis_id': row.get('gsis_id'),
                        'name': row.get('pfr_player_name'),
                        'round': row.get('round'),
                        'pick': row.get('pick'),
                        'season': row.get('season'),
                        'draft_value': row.get('draft_value'),
                        'round_capital': row.get('round_capital'),
                        'age': row.get('age'),
                        'career_value': row.get('career_value')
                    })
                    updated += result.single()['updated']
                except Exception as e:
                    logger.debug(f"Error updating draft: {e}")

        logger.info(f"Updated draft capital for {updated} players")
        return updated

    def update_contract_data(self, contracts: pd.DataFrame) -> int:
        """Update Player nodes with contract data."""
        if contracts.empty:
            return 0

        contract_data = self.calculate_contract_value(contracts)
        updated = 0

        with self.driver.session() as session:
            for _, row in contract_data.iterrows():
                try:
                    result = session.run("""
                        MATCH (p:Player)
                        WHERE p.gsis_id = $gsis_id OR toLower(p.name) = toLower($name)
                        SET p.contract_apy = $apy,
                            p.contract_value = $value,
                            p.contract_guaranteed = $guaranteed,
                            p.contract_guaranteed_pct = $guaranteed_pct,
                            p.contract_cap_pct = $cap_pct,
                            p.contract_years = $years,
                            p.apy_percentile = $apy_percentile
                        RETURN count(p) as updated
                    """, {
                        'gsis_id': row.get('gsis_id'),
                        'name': row.get('player'),
                        'apy': row.get('apy'),
                        'value': row.get('value'),
                        'guaranteed': row.get('guaranteed'),
                        'guaranteed_pct': row.get('guaranteed_pct'),
                        'cap_pct': row.get('apy_cap_pct'),
                        'years': row.get('years'),
                        'apy_percentile': row.get('apy_percentile')
                    })
                    updated += result.single()['updated']
                except Exception as e:
                    logger.debug(f"Error updating contract: {e}")

        logger.info(f"Updated contracts for {updated} players")
        return updated

    def update_injury_risk(self, injuries: pd.DataFrame) -> int:
        """Update Player nodes with injury risk data."""
        if injuries.empty:
            return 0

        injury_data = self.calculate_injury_risk(injuries)
        updated = 0

        with self.driver.session() as session:
            for _, row in injury_data.iterrows():
                try:
                    result = session.run("""
                        MATCH (p:Player)
                        WHERE p.gsis_id = $gsis_id
                        SET p.injury_reports = $injury_reports,
                            p.injuries_per_season = $injuries_per_season,
                            p.injury_risk_score = $injury_risk_score
                        RETURN count(p) as updated
                    """, {
                        'gsis_id': row['gsis_id'],
                        'injury_reports': row['total_injury_reports'],
                        'injuries_per_season': row['injuries_per_season'],
                        'injury_risk_score': row['injury_risk_score']
                    })
                    updated += result.single()['updated']
                except Exception as e:
                    logger.debug(f"Error updating injury: {e}")

        logger.info(f"Updated injury data for {updated} players")
        return updated

    def update_snap_data(self, snaps: pd.DataFrame) -> int:
        """Update Player nodes with snap share data."""
        if snaps.empty:
            return 0

        snap_data = self.calculate_snap_share(snaps)
        # Get most recent season
        snap_data = snap_data.sort_values('season', ascending=False)
        snap_data = snap_data.drop_duplicates(subset=['pfr_player_id'], keep='first')

        updated = 0

        with self.driver.session() as session:
            for _, row in snap_data.iterrows():
                try:
                    result = session.run("""
                        MATCH (p:Player)
                        WHERE toLower(p.name) = toLower($name)
                        SET p.total_snaps = $total_snaps,
                            p.avg_snap_pct = $snap_pct,
                            p.games_played = $games,
                            p.snap_trend = $snap_trend
                        RETURN count(p) as updated
                    """, {
                        'name': row['player_name'],
                        'total_snaps': row['total_offense_snaps'],
                        'snap_pct': row['avg_snap_pct'],
                        'games': row['games_played'],
                        'snap_trend': row.get('snap_trend', 0)
                    })
                    updated += result.single()['updated']
                except Exception as e:
                    logger.debug(f"Error updating snaps: {e}")

        logger.info(f"Updated snap data for {updated} players")
        return updated

    def update_qbr_data(self, qbr: pd.DataFrame) -> int:
        """Update QB nodes with QBR data."""
        if qbr.empty:
            return 0

        # Aggregate to season level
        qbr_season = qbr.groupby(['name_display', 'season']).agg({
            'qbr_total': 'mean',
            'pts_added': 'sum',
            'epa_total': 'sum',
            'qb_plays': 'sum'
        }).reset_index()

        # Get most recent
        qbr_season = qbr_season.sort_values('season', ascending=False)
        qbr_season = qbr_season.drop_duplicates(subset=['name_display'], keep='first')

        updated = 0

        with self.driver.session() as session:
            for _, row in qbr_season.iterrows():
                try:
                    result = session.run("""
                        MATCH (p:Player)
                        WHERE toLower(p.name) = toLower($name) AND p.position = 'QB'
                        SET p.qbr = $qbr,
                            p.qbr_pts_added = $pts_added,
                            p.qbr_epa = $epa,
                            p.qbr_plays = $plays
                        RETURN count(p) as updated
                    """, {
                        'name': row['name_display'],
                        'qbr': row['qbr_total'],
                        'pts_added': row['pts_added'],
                        'epa': row['epa_total'],
                        'plays': row['qb_plays']
                    })
                    updated += result.single()['updated']
                except Exception as e:
                    logger.debug(f"Error updating QBR: {e}")

        logger.info(f"Updated QBR for {updated} QBs")
        return updated

    # =========================================================================
    # MAIN ENRICHMENT PIPELINE
    # =========================================================================

    def run_full_enrichment(self) -> Dict[str, int]:
        """Run complete enrichment pipeline."""
        logger.info("="*60)
        logger.info("STARTING FULL NFLVERSE ENRICHMENT")
        logger.info("="*60)

        results = {}

        # 1. Athletic Profiles (Combine)
        logger.info("\n[1/6] Loading Combine Data...")
        combine = self.load_combine_data()
        results['combine'] = self.update_athletic_profiles(combine)

        # 2. Draft Capital
        logger.info("\n[2/6] Loading Draft Data...")
        draft = self.load_draft_data()
        results['draft'] = self.update_draft_capital(draft)

        # 3. Contracts
        logger.info("\n[3/6] Loading Contract Data...")
        contracts = self.load_contracts()
        results['contracts'] = self.update_contract_data(contracts)

        # 4. Injuries
        logger.info("\n[4/6] Loading Injury Data...")
        injuries = self.load_injuries()
        results['injuries'] = self.update_injury_risk(injuries)

        # 5. Snap Counts
        logger.info("\n[5/6] Loading Snap Data...")
        snaps = self.load_snap_counts()
        results['snaps'] = self.update_snap_data(snaps)

        # 6. QBR
        logger.info("\n[6/6] Loading QBR Data...")
        qbr = self.load_qbr()
        results['qbr'] = self.update_qbr_data(qbr)

        logger.info("\n" + "="*60)
        logger.info("ENRICHMENT COMPLETE")
        logger.info("="*60)
        logger.info(f"Results: {results}")

        return results


if __name__ == "__main__":
    enricher = NFLverseEnrichment()
    try:
        results = enricher.run_full_enrichment()
        print("\nEnrichment Summary:")
        for source, count in results.items():
            print(f"  {source}: {count} players updated")
    finally:
        enricher.close()
