"""
College Football Data Scheduler
================================
Automated updates for college football data pipeline.

Schedule:
- Weekly: CFBD data refresh (recruiting, stats, draft)
- Twice daily: KTC devy value updates
- Weekly: Feature engineering recalculation
- Weekly: Insight discovery cycle
"""

import os
import sys
import logging
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import schedule
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/college_scheduler.log')
    ]
)
logger = logging.getLogger(__name__)


class CollegeDataScheduler:
    """
    Scheduler for automated college football data updates.

    Jobs:
    - update_devy_values: Twice daily KTC devy scraping
    - update_cfbd_data: Weekly CFBD API refresh
    - recalculate_features: Weekly feature engineering
    - run_insight_discovery: Weekly insight discovery cycle
    """

    def __init__(self):
        """Initialize scheduler with Neo4j connection."""
        self.neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_user = os.getenv("NEO4J_USER")
        self.neo4j_password = os.getenv("NEO4J_PASSWORD")

        auth = None
        if self.neo4j_user and self.neo4j_password:
            auth = (self.neo4j_user, self.neo4j_password)

        self.driver = GraphDatabase.driver(self.neo4j_uri, auth=auth)

        # Track job execution
        self.job_history = []

    def close(self):
        """Clean up resources."""
        self.driver.close()

    def log_job_execution(self, job_name: str, success: bool, details: str = None):
        """Log job execution for monitoring."""
        entry = {
            'job': job_name,
            'timestamp': datetime.now().isoformat(),
            'success': success,
            'details': details
        }
        self.job_history.append(entry)

        # Keep last 100 entries
        if len(self.job_history) > 100:
            self.job_history = self.job_history[-100:]

    # =========================================================================
    # SCHEDULED JOBS
    # =========================================================================

    def update_devy_values(self):
        """
        Update KTC devy values from keeptradecut.com.

        Runs twice daily to capture market movements.
        """
        logger.info("="*50)
        logger.info("Starting KTC Devy Values Update")
        logger.info("="*50)

        try:
            from src.loaders.ktc_devy_loader import KTCDevyLoader

            loader = KTCDevyLoader(driver=self.driver)

            # Fetch and load superflex values
            df = loader.fetch_devy_rankings(superflex=True)

            if df is not None and not df.empty:
                count = loader.load_devy_values_to_neo4j(df, superflex=True)

                # Link temporal snapshots
                loader.link_devy_snapshots_temporal()

                logger.info(f"Updated {count} devy prospect values")
                self.log_job_execution('update_devy_values', True, f"{count} values updated")
            else:
                logger.warning("No devy data retrieved")
                self.log_job_execution('update_devy_values', False, "No data retrieved")

        except Exception as e:
            logger.error(f"Devy update failed: {e}")
            self.log_job_execution('update_devy_values', False, str(e))

    def update_cfbd_data(self):
        """
        Update CFBD data (recruiting, stats, draft picks).

        Runs weekly to capture new data from CollegeFootballData.com.
        """
        logger.info("="*50)
        logger.info("Starting CFBD Data Update")
        logger.info("="*50)

        try:
            from src.loaders.college_to_neo4j import CollegeToNeo4jETL

            etl = CollegeToNeo4jETL()

            # Run ETL with current year focus
            current_year = datetime.now().year

            stats = etl.run_full_etl(
                recruiting_years=[current_year - 1, current_year],
                stats_years=[current_year - 1],
                draft_years=[current_year],
                include_devy=False,  # Handled separately
                include_combine=True
            )

            etl.close()

            logger.info(f"CFBD Update Complete: {stats['prospects_created']} prospects updated")
            self.log_job_execution('update_cfbd_data', True, f"{stats['prospects_created']} prospects")

        except Exception as e:
            logger.error(f"CFBD update failed: {e}")
            self.log_job_execution('update_cfbd_data', False, str(e))

    def recalculate_features(self):
        """
        Recalculate prospect features (dominator, speed score, etc.).

        Runs weekly after CFBD update.
        """
        logger.info("="*50)
        logger.info("Starting Feature Recalculation")
        logger.info("="*50)

        try:
            from src.features.college_features import CollegeFeatureEngineer

            engineer = CollegeFeatureEngineer(driver=self.driver)
            engineer.update_prospect_features()

            logger.info("Feature recalculation complete")
            self.log_job_execution('recalculate_features', True, "All features updated")

        except Exception as e:
            logger.error(f"Feature recalculation failed: {e}")
            self.log_job_execution('recalculate_features', False, str(e))

    def run_insight_discovery(self):
        """
        Run insight discovery cycle.

        Runs weekly to discover new correlations and patterns.
        """
        logger.info("="*50)
        logger.info("Starting Insight Discovery")
        logger.info("="*50)

        try:
            from src.knowledge.insight_engine import InsightEngine

            engine = InsightEngine(self.driver)
            count = engine.run_discovery_cycle()

            logger.info(f"Discovered {count} new insights")
            self.log_job_execution('run_insight_discovery', True, f"{count} insights discovered")

        except Exception as e:
            logger.error(f"Insight discovery failed: {e}")
            self.log_job_execution('run_insight_discovery', False, str(e))

    def run_full_refresh(self):
        """Run all update jobs in sequence."""
        logger.info("="*60)
        logger.info("STARTING FULL COLLEGE DATA REFRESH")
        logger.info("="*60)

        self.update_cfbd_data()
        self.update_devy_values()
        self.recalculate_features()
        self.run_insight_discovery()

        logger.info("="*60)
        logger.info("FULL REFRESH COMPLETE")
        logger.info("="*60)

    # =========================================================================
    # SCHEDULER SETUP
    # =========================================================================

    def setup_schedule(self):
        """
        Configure the job schedule.

        Schedule:
        - Devy values: 6 AM and 6 PM daily
        - CFBD data: Tuesday 4 AM (after Monday night games)
        - Features: Tuesday 5 AM
        - Insights: Tuesday 6 AM
        """
        # KTC Devy values - twice daily
        schedule.every().day.at("06:00").do(self.update_devy_values)
        schedule.every().day.at("18:00").do(self.update_devy_values)

        # CFBD data - weekly Tuesday
        schedule.every().tuesday.at("04:00").do(self.update_cfbd_data)

        # Feature recalculation - weekly Tuesday after CFBD
        schedule.every().tuesday.at("05:00").do(self.recalculate_features)

        # Insight discovery - weekly Tuesday
        schedule.every().tuesday.at("06:00").do(self.run_insight_discovery)

        logger.info("Schedule configured:")
        logger.info("  - Devy values: 6:00 AM and 6:00 PM daily")
        logger.info("  - CFBD data: Tuesdays 4:00 AM")
        logger.info("  - Features: Tuesdays 5:00 AM")
        logger.info("  - Insights: Tuesdays 6:00 AM")

    def run_scheduler(self):
        """Run the scheduler loop."""
        self.setup_schedule()

        logger.info("Scheduler started. Press Ctrl+C to stop.")

        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")
        finally:
            self.close()

    def get_job_status(self) -> dict:
        """Get status of recent job executions."""
        return {
            'recent_jobs': self.job_history[-10:],
            'next_jobs': [
                {
                    'job': str(job),
                    'next_run': str(job.next_run)
                }
                for job in schedule.get_jobs()
            ]
        }


# =============================================================================
# CLI
# =============================================================================

def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='College Football Data Scheduler')
    parser.add_argument('--run-now', choices=['devy', 'cfbd', 'features', 'insights', 'all'],
                       help='Run a specific job immediately')
    parser.add_argument('--daemon', action='store_true',
                       help='Run as background scheduler daemon')

    args = parser.parse_args()

    # Ensure logs directory exists
    Path('logs').mkdir(exist_ok=True)

    scheduler = CollegeDataScheduler()

    try:
        if args.run_now:
            if args.run_now == 'devy':
                scheduler.update_devy_values()
            elif args.run_now == 'cfbd':
                scheduler.update_cfbd_data()
            elif args.run_now == 'features':
                scheduler.recalculate_features()
            elif args.run_now == 'insights':
                scheduler.run_insight_discovery()
            elif args.run_now == 'all':
                scheduler.run_full_refresh()
        elif args.daemon:
            scheduler.run_scheduler()
        else:
            print("Usage:")
            print("  --run-now [devy|cfbd|features|insights|all]  Run job immediately")
            print("  --daemon                                       Start scheduler daemon")
    finally:
        scheduler.close()


if __name__ == "__main__":
    main()
