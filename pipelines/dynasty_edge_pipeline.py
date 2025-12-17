"""
Dynasty Edge Pipeline Orchestrator
Master pipeline that orchestrates all components of the Dynasty Edge system.

This combines:
- NFLverse data loading
- KTC value scraping
- Neo4j graph database operations
- Feature engineering
- H2O ML training
- Novel valuation framework
- Dynasty Edge Score calculation
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
import pandas as pd

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)


class DynastyEdgePipeline:
    """Master pipeline for Dynasty Edge system."""

    def __init__(self, neo4j_uri: str = "bolt://localhost:7687",
                 neo4j_auth: tuple = None,
                 data_dir: Path = None,
                 models_dir: Path = None):
        """Initialize pipeline with configuration."""
        self.neo4j_uri = neo4j_uri
        self.neo4j_auth = neo4j_auth
        self.data_dir = Path(data_dir or PROJECT_ROOT / "data")
        self.models_dir = Path(models_dir or self.data_dir / "models")
        self.features_dir = self.data_dir / "features"

        # Create directories
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.features_dir.mkdir(parents=True, exist_ok=True)

        # Components (lazy loaded)
        self._driver = None
        self._schema_manager = None
        self._nflverse_loader = None
        self._ktc_loader = None
        self._relationship_builder = None
        self._feature_extractor = None
        self._novel_framework = None
        self._ml_trainer = None
        self._predictor = None

    @property
    def driver(self):
        """Lazy load Neo4j driver."""
        if self._driver is None:
            from neo4j import GraphDatabase
            self._driver = GraphDatabase.driver(self.neo4j_uri, auth=self.neo4j_auth)
        return self._driver

    def close(self):
        """Close connections."""
        if self._driver:
            self._driver.close()

    # ==========================================================================
    # Phase 1: Data Foundation
    # ==========================================================================

    def setup_schema(self, drop_existing: bool = False):
        """Initialize Neo4j schema with constraints and indexes."""
        logger.info("Setting up Neo4j schema...")

        from src.database.unified_schema import UnifiedSchemaManager

        self._schema_manager = UnifiedSchemaManager(self.driver)

        if drop_existing:
            logger.warning("Dropping existing schema...")
            self._schema_manager.drop_schema()

        self._schema_manager.create_schema()
        stats = self._schema_manager.get_schema_stats()
        logger.info(f"Schema stats: {stats}")
        return stats

    def load_nflverse_data(self, seasons: list = None) -> Dict[str, int]:
        """Load NFLverse data into Neo4j."""
        logger.info("Loading NFLverse data...")

        if seasons is None:
            seasons = [2024, 2025]

        from src.loaders.nflverse_loader import NFLverseLoader

        self._nflverse_loader = NFLverseLoader(cache_dir=self.data_dir / "raw" / "nflverse")

        results = {}

        try:
            # Load players
            logger.info("Loading players...")
            players_df = self._nflverse_loader.load_players()
            results['players'] = len(players_df)
            logger.info(f"Loaded {len(players_df)} players")

            # Load teams
            logger.info("Loading teams...")
            teams_df = self._nflverse_loader.load_teams()
            results['teams'] = len(teams_df)

            # Load to Neo4j
            self._load_players_to_neo4j(players_df)
            self._load_teams_to_neo4j(teams_df)

            # Load player stats
            logger.info(f"Loading player stats for seasons {seasons}...")
            stats_df = self._nflverse_loader.load_player_stats(seasons)
            results['player_stats'] = len(stats_df)
            self._load_stats_to_neo4j(stats_df)

        except Exception as e:
            logger.error(f"Error loading NFLverse data: {e}")
            raise

        return results

    def load_ktc_values(self, superflex: bool = True) -> int:
        """Load KTC values from keeptradecut.com."""
        logger.info("Loading KTC values...")

        from src.loaders.ktc_loader import KTCLoader

        self._ktc_loader = KTCLoader(driver=self.driver)
        count = self._ktc_loader.load_ktc_values(superflex=superflex)
        logger.info(f"Loaded KTC values for {count} players")
        return count

    def _load_players_to_neo4j(self, players_df: pd.DataFrame):
        """Load player data to Neo4j."""
        with self.driver.session() as session:
            batch_size = 500
            total = 0

            for i in range(0, len(players_df), batch_size):
                batch = players_df.iloc[i:i+batch_size]
                records = batch.to_dict('records')

                session.run("""
                    UNWIND $players as p
                    MERGE (player:Player {gsis_id: p.gsis_id})
                    SET player.name = COALESCE(p.display_name, p.first_name + ' ' + p.last_name),
                        player.display_name = p.display_name,
                        player.position = p.position,
                        player.current_team = p.team_abbr,
                        player.height = p.height,
                        player.weight = p.weight,
                        player.college = p.college,
                        player.years_exp = p.years_exp,
                        player.updated_at = datetime()
                """, {'players': records})
                total += len(batch)

            logger.info(f"Loaded {total} players to Neo4j")

    def _load_teams_to_neo4j(self, teams_df: pd.DataFrame):
        """Load team data to Neo4j."""
        with self.driver.session() as session:
            records = teams_df.to_dict('records')
            session.run("""
                UNWIND $teams as t
                MERGE (team:Team {team_abbr: t.team_abbr})
                SET team.team_name = t.team_name,
                    team.conference = t.team_conf,
                    team.division = t.team_division,
                    team.updated_at = datetime()
            """, {'teams': records})
            logger.info(f"Loaded {len(records)} teams to Neo4j")

    def _load_stats_to_neo4j(self, stats_df: pd.DataFrame):
        """Load player stats to Neo4j."""
        # Define columns to aggregate with fallback handling
        agg_cols = {}
        for col in ['completions', 'attempts', 'passing_yards', 'passing_tds',
                    'interceptions', 'carries', 'rushing_yards', 'rushing_tds',
                    'targets', 'receptions', 'receiving_yards', 'receiving_tds',
                    'fantasy_points_ppr']:
            if col in stats_df.columns:
                agg_cols[col] = 'sum'

        # Check for alternative column names
        column_aliases = {
            'interceptions': ['interceptions', 'passing_int', 'int', 'pass_int'],
            'attempts': ['attempts', 'passing_attempts', 'pass_att'],
        }

        for target_col, aliases in column_aliases.items():
            if target_col not in stats_df.columns:
                for alias in aliases:
                    if alias in stats_df.columns and alias != target_col:
                        stats_df[target_col] = stats_df[alias]
                        agg_cols[target_col] = 'sum'
                        break

        if not agg_cols or 'player_id' not in stats_df.columns:
            logger.warning("Stats DataFrame missing required columns")
            return

        # Aggregate to season level
        season_stats = stats_df.groupby(['player_id', 'season']).agg(agg_cols).reset_index()

        def safe_int(val):
            """Safely convert to int, handling NaN."""
            return int(val) if pd.notna(val) else 0

        def safe_float(val):
            """Safely convert to float, handling NaN."""
            return float(val) if pd.notna(val) else 0.0

        with self.driver.session() as session:
            for _, row in season_stats.iterrows():
                if pd.isna(row['player_id']):
                    continue

                # Build params dict with only available columns
                params = {'gsis_id': row['player_id']}

                # Map columns to Neo4j properties
                col_mapping = {
                    'completions': ('completions', safe_int),
                    'attempts': ('pass_attempts', safe_int),
                    'passing_yards': ('passing_yards', safe_int),
                    'passing_tds': ('passing_tds', safe_int),
                    'interceptions': ('interceptions', safe_int),
                    'carries': ('carries', safe_int),
                    'rushing_yards': ('rushing_yards', safe_int),
                    'rushing_tds': ('rushing_tds', safe_int),
                    'targets': ('targets', safe_int),
                    'receptions': ('receptions', safe_int),
                    'receiving_yards': ('receiving_yards', safe_int),
                    'receiving_tds': ('receiving_tds', safe_int),
                    'fantasy_points_ppr': ('fantasy_points_season', safe_float),
                }

                set_clauses = []
                for col, (prop, converter) in col_mapping.items():
                    if col in row.index:
                        params[prop] = converter(row[col])
                        set_clauses.append(f"p.{prop} = ${prop}")

                if set_clauses:
                    query = f"""
                        MATCH (p:Player {{gsis_id: $gsis_id}})
                        SET {', '.join(set_clauses)}
                    """
                    session.run(query, params)

        logger.info(f"Loaded stats for {len(season_stats)} player-seasons")

    # ==========================================================================
    # Phase 2: Graph Relationships
    # ==========================================================================

    def build_relationships(self, season: int = 2025) -> Dict[str, int]:
        """Build all graph relationships."""
        logger.info("Building graph relationships...")

        from src.database.relationship_builder import MasterRelationshipBuilder

        self._relationship_builder = MasterRelationshipBuilder(self.driver)
        results = self._relationship_builder.build_all(season=season)

        return results

    # ==========================================================================
    # Phase 3: Feature Engineering
    # ==========================================================================

    def extract_graph_features(self, season: int = 2025) -> pd.DataFrame:
        """Extract ML features from graph."""
        logger.info("Extracting graph features...")

        from src.features.graph_features import extract_graph_features, combine_graph_features
        from src.database.neo4j_client import Neo4jClient

        client = Neo4jClient(self.neo4j_uri, self.neo4j_auth)
        try:
            features = extract_graph_features(client, season)
            combined = combine_graph_features(features)

            # Save to feature store
            if not combined.empty:
                combined.to_parquet(self.features_dir / "graph_features.parquet")
                logger.info(f"Saved graph features for {len(combined)} players")

            return combined
        finally:
            client.close()

    def build_training_dataset(self) -> pd.DataFrame:
        """Build ML-ready training dataset."""
        logger.info("Building training dataset...")

        from src.features.feature_store import FeatureStore

        store = FeatureStore(self.features_dir)

        # Load player data from Neo4j
        with self.driver.session() as session:
            result = session.run("""
                MATCH (p:Player)
                WHERE p.position IN ['QB', 'RB', 'WR', 'TE']
                  AND p.ktc_value > 500
                RETURN p.gsis_id as gsis_id,
                       p.name as name,
                       p.position as position,
                       p.age as age,
                       p.years_exp as years_exp,
                       p.ktc_value as ktc_value,
                       p.fantasy_points_season as fantasy_points,
                       p.targets as targets,
                       p.receptions as receptions,
                       p.carries as carries,
                       p.passing_yards as passing_yards,
                       p.rushing_yards as rushing_yards,
                       p.receiving_yards as receiving_yards
            """)
            data = [dict(r) for r in result]

        df = pd.DataFrame(data)

        # Load and join graph features
        graph_features_path = self.features_dir / "graph_features.parquet"
        if graph_features_path.exists():
            graph_features = pd.read_parquet(graph_features_path)
            df = df.merge(graph_features, on='gsis_id', how='left', suffixes=('', '_graph'))

        # Save training dataset
        df.to_parquet(self.features_dir / "training_data.parquet")
        logger.info(f"Built training dataset with {len(df)} players, {len(df.columns)} features")

        return df

    # ==========================================================================
    # Phase 4: ML Training
    # ==========================================================================

    def train_model(self, max_runtime_secs: int = 3600, max_models: int = 50) -> Dict[str, Any]:
        """Train H2O AutoML model for KTC prediction."""
        logger.info("Training ML model...")

        from src.ml.train import DynastyMLTrainer

        self._ml_trainer = DynastyMLTrainer(models_dir=self.models_dir)

        # Load training data
        training_path = self.features_dir / "training_data.parquet"
        if not training_path.exists():
            logger.warning("Training data not found, building...")
            df = self.build_training_dataset()
        else:
            df = pd.read_parquet(training_path)

        if len(df) < 100:
            logger.warning(f"Only {len(df)} samples, may not train well")

        # Train model
        model, leaderboard, importance = self._ml_trainer.train(
            df,
            target='ktc_value',
            max_runtime_secs=max_runtime_secs,
            max_models=max_models
        )

        return {
            'model': model,
            'leaderboard': leaderboard,
            'importance': importance
        }

    # ==========================================================================
    # Phase 5: Predictions and Signals
    # ==========================================================================

    def generate_predictions(self) -> pd.DataFrame:
        """Generate predictions and trading signals."""
        logger.info("Generating predictions...")

        from src.ml.predict import DynastyPredictor, SignalReporter

        self._predictor = DynastyPredictor(models_dir=self.models_dir)

        # Load data
        with self.driver.session() as session:
            result = session.run("""
                MATCH (p:Player)
                WHERE p.position IN ['QB', 'RB', 'WR', 'TE']
                  AND p.ktc_value > 500
                RETURN p.gsis_id as gsis_id,
                       p.name as name,
                       p.position as position,
                       p.age as age,
                       p.years_exp as years_exp,
                       p.ktc_value as ktc_value,
                       p.fantasy_points_season as fantasy_points,
                       p.targets as targets,
                       p.receptions as receptions,
                       p.carries as carries
            """)
            data = [dict(r) for r in result]

        df = pd.DataFrame(data)

        # Generate predictions
        try:
            df = self._predictor.predict_and_signal(df)
            SignalReporter.print_report(df)

            # Update Neo4j with predictions
            from src.ml.predict import update_neo4j_with_predictions
            update_neo4j_with_predictions(self.driver, df)

            return df
        except FileNotFoundError:
            logger.warning("No trained model found, skipping predictions")
            return df

    # ==========================================================================
    # Phase 6: Novel Valuation Framework
    # ==========================================================================

    def run_novel_framework(self, season: int = 2025) -> Dict[str, pd.DataFrame]:
        """Run the Novel Valuation Framework."""
        logger.info("Running Novel Valuation Framework...")

        from src.features.novel_valuation import NovelValuationFramework

        self._novel_framework = NovelValuationFramework(self.driver)

        # Initialize framework
        self._novel_framework.initialize_framework(season)

        # Run full analysis
        results = self._novel_framework.run_full_analysis(season)

        # Print summary
        if 'dynasty_edge' in results and not results['dynasty_edge'].empty:
            print("\n" + "=" * 70)
            print("  DYNASTY EDGE TOP OPPORTUNITIES")
            print("=" * 70)

            top_buys = results['dynasty_edge'][
                results['dynasty_edge']['edge_signal'].isin(['BUY', 'STRONG_BUY'])
            ].head(10)

            print("\nTOP BUY SIGNALS:")
            for _, row in top_buys.iterrows():
                print(f"  {row['player']:<25} {row['position']:<4} "
                      f"KTC: {row['base_ktc']:>6,} → Edge: {row['dynasty_edge_score']:>6,} "
                      f"({row['edge_pct']:+.1f}%)")

            top_sells = results['dynasty_edge'][
                results['dynasty_edge']['edge_signal'].isin(['SELL', 'STRONG_SELL'])
            ].head(10)

            print("\nTOP SELL SIGNALS:")
            for _, row in top_sells.iterrows():
                print(f"  {row['player']:<25} {row['position']:<4} "
                      f"KTC: {row['base_ktc']:>6,} → Edge: {row['dynasty_edge_score']:>6,} "
                      f"({row['edge_pct']:+.1f}%)")

        return results

    # ==========================================================================
    # Master Pipeline
    # ==========================================================================

    def run_full_pipeline(self, seasons: list = None, train_model: bool = True,
                          max_runtime_secs: int = 3600) -> Dict[str, Any]:
        """Run the complete Dynasty Edge pipeline."""
        logger.info("=" * 70)
        logger.info("DYNASTY EDGE PIPELINE - FULL RUN")
        logger.info("=" * 70)

        results = {}
        start_time = datetime.now()

        try:
            # Phase 1: Data Foundation
            logger.info("\n--- PHASE 1: DATA FOUNDATION ---")
            results['schema'] = self.setup_schema()
            results['nflverse'] = self.load_nflverse_data(seasons)
            results['ktc'] = self.load_ktc_values()

            # Phase 2: Graph Relationships
            logger.info("\n--- PHASE 2: GRAPH RELATIONSHIPS ---")
            results['relationships'] = self.build_relationships()

            # Phase 3: Feature Engineering
            logger.info("\n--- PHASE 3: FEATURE ENGINEERING ---")
            results['features'] = self.extract_graph_features()
            results['training_data'] = self.build_training_dataset()

            # Phase 4: ML Training (optional)
            if train_model:
                logger.info("\n--- PHASE 4: ML TRAINING ---")
                results['ml'] = self.train_model(max_runtime_secs=max_runtime_secs)

            # Phase 5: Predictions
            logger.info("\n--- PHASE 5: PREDICTIONS ---")
            results['predictions'] = self.generate_predictions()

            # Phase 6: Novel Valuation Framework
            logger.info("\n--- PHASE 6: NOVEL VALUATION ---")
            results['novel'] = self.run_novel_framework()

            elapsed = datetime.now() - start_time
            logger.info("\n" + "=" * 70)
            logger.info(f"PIPELINE COMPLETE - Elapsed: {elapsed}")
            logger.info("=" * 70)

        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            raise
        finally:
            self.close()

        return results


def run_daily_refresh():
    """Daily refresh pipeline - updates KTC and recalculates signals.

    Now includes temporal tracking for value change analysis.
    """
    logging.basicConfig(level=logging.INFO)
    logger.info("Running daily refresh...")

    pipeline = DynastyEdgePipeline()

    try:
        # Update KTC values
        pipeline.load_ktc_values()

        # Update relationships
        pipeline.build_relationships()

        # Regenerate predictions with existing model
        pipeline.generate_predictions()

        # Update Dynasty Edge scores
        from src.features.novel_valuation import DynastyEdgeCalculator
        calc = DynastyEdgeCalculator(pipeline.driver)
        calc.update_player_edge_scores()

        # Create temporal snapshots for tracking
        logger.info("Creating temporal snapshots...")
        from src.features.temporal_tracking import run_daily_tracking

        # Get current player data for snapshots
        with pipeline.driver.session() as session:
            result = session.run("""
                MATCH (p:Player)
                WHERE p.position IN ['QB', 'RB', 'WR', 'TE'] AND p.ktc_value > 500
                RETURN p.gsis_id as gsis_id,
                       p.name as name,
                       p.ktc_value as ktc_value,
                       p.targets as targets,
                       COALESCE(p.targets / 17.0, 0) as targets_per_game,
                       p.receptions as receptions,
                       COALESCE(p.fantasy_points_season / 17.0, 0) as fantasy_ppg,
                       0.5 as snap_share,
                       0.2 as target_share
            """)
            players_df = pd.DataFrame([dict(r) for r in result])

        if not players_df.empty:
            tracking_results = run_daily_tracking(pipeline.driver, players_df)
            logger.info(f"Temporal tracking: {tracking_results}")

        logger.info("Daily refresh complete")

    finally:
        pipeline.close()


def run_weekly_retrain():
    """Weekly retrain pipeline - retrains ML model.

    Now includes correlation discovery from temporal data.
    """
    logging.basicConfig(level=logging.INFO)
    logger.info("Running weekly retrain...")

    pipeline = DynastyEdgePipeline()

    try:
        # Rebuild training data
        pipeline.extract_graph_features()
        pipeline.build_training_dataset()

        # Retrain model
        pipeline.train_model(max_runtime_secs=3600)

        # Generate new predictions
        pipeline.generate_predictions()

        # Run full novel framework
        pipeline.run_novel_framework()

        # Discover correlations from temporal data
        logger.info("Discovering correlations from temporal data...")
        from src.features.temporal_tracking import CorrelationDiscovery, ModelConfigManager

        discovery = CorrelationDiscovery(pipeline.driver)
        correlations = discovery.discover_and_save(lookback_days=60)
        logger.info(f"Discovered {len(correlations)} correlations")

        # Suggest new model weights based on correlations
        config_mgr = ModelConfigManager(pipeline.driver)
        suggested_weights = config_mgr.suggest_weights_from_correlations()

        if suggested_weights:
            # Create new config (not activated by default)
            config_id = config_mgr.create_config(suggested_weights, created_by='weekly_retrain')
            logger.info(f"Created suggested config: {config_id}")

        logger.info("Weekly retrain complete")

    finally:
        pipeline.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Dynasty Edge Pipeline")
    parser.add_argument("--mode", choices=["full", "daily", "weekly"],
                        default="full", help="Pipeline mode")
    parser.add_argument("--seasons", nargs="+", type=int,
                        default=[2024, 2025], help="Seasons to load")
    parser.add_argument("--no-train", action="store_true",
                        help="Skip ML training")
    parser.add_argument("--runtime", type=int, default=3600,
                        help="Max ML training runtime in seconds")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    if args.mode == "full":
        pipeline = DynastyEdgePipeline()
        pipeline.run_full_pipeline(
            seasons=args.seasons,
            train_model=not args.no_train,
            max_runtime_secs=args.runtime
        )
    elif args.mode == "daily":
        run_daily_refresh()
    elif args.mode == "weekly":
        run_weekly_retrain()
