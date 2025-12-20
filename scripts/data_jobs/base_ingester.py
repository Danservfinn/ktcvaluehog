"""
Base Ingester Class
===================
Abstract base class providing common patterns for all data ingesters.

All data ingestion scripts should inherit from this class to ensure
consistent logging, error handling, and Neo4j interaction patterns.
"""

import os
import sys
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List

import pandas as pd
from dotenv import load_dotenv

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv()


class BaseIngester(ABC):
    """
    Abstract base class for all data ingesters.

    Provides:
    - Neo4j connection management
    - Logging configuration
    - Import lock checking (to avoid conflicts with Railway import)
    - Statistics tracking
    - Batch processing utilities
    """

    def __init__(
        self,
        name: str,
        use_railway: bool = True,
        batch_size: int = 500,
        log_to_file: bool = True
    ):
        """
        Initialize the ingester.

        Args:
            name: Identifier for this ingester (used in logs)
            use_railway: If True, connect to Railway; else local Neo4j
            batch_size: Default batch size for Neo4j operations
            log_to_file: If True, also log to file in logs/ directory
        """
        self.name = name
        self.use_railway = use_railway
        self.batch_size = batch_size
        self.project_root = PROJECT_ROOT
        self.data_dir = PROJECT_ROOT / "data"
        self.log_dir = PROJECT_ROOT / "logs"

        # Ensure directories exist
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Setup logging
        self.logger = self._setup_logging(log_to_file)

        # Statistics
        self.stats = {
            'records_downloaded': 0,
            'records_processed': 0,
            'nodes_created': 0,
            'nodes_updated': 0,
            'relationships_created': 0,
            'errors': 0,
            'start_time': None,
            'end_time': None,
        }

        # Neo4j driver (lazy initialization)
        self._driver = None

    def _setup_logging(self, log_to_file: bool) -> logging.Logger:
        """Configure logging for this ingester."""
        logger = logging.getLogger(self.name)
        logger.setLevel(logging.INFO)

        # Clear existing handlers
        logger.handlers = []

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_format)
        logger.addHandler(console_handler)

        # File handler
        if log_to_file:
            log_file = self.log_dir / f"{self.name}.log"
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(console_format)
            logger.addHandler(file_handler)

        return logger

    @property
    def driver(self):
        """Lazy-load Neo4j driver."""
        if self._driver is None:
            from neo4j import GraphDatabase

            uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
            user = os.getenv("NEO4J_USER", "neo4j")
            password = os.getenv("NEO4J_PASSWORD", "password")

            self._driver = GraphDatabase.driver(uri, auth=(user, password))
            self.logger.info(f"Connected to Neo4j at {uri}")

        return self._driver

    def close(self):
        """Close Neo4j connection."""
        if self._driver:
            self._driver.close()
            self._driver = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # =========================================================================
    # Abstract methods (must be implemented by subclasses)
    # =========================================================================

    @abstractmethod
    def download_data(self, **kwargs) -> pd.DataFrame:
        """
        Download data from the source.

        Returns:
            DataFrame with raw data
        """
        pass

    @abstractmethod
    def process_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Process and clean the downloaded data.

        Args:
            df: Raw data from download_data()

        Returns:
            Processed DataFrame ready for Neo4j
        """
        pass

    @abstractmethod
    def create_schema(self):
        """
        Create Neo4j indexes and constraints for this data type.
        Should be idempotent (safe to run multiple times).
        """
        pass

    @abstractmethod
    def create_nodes(self, df: pd.DataFrame) -> int:
        """
        Create or update Neo4j nodes from processed data.

        Args:
            df: Processed data from process_data()

        Returns:
            Number of nodes created/updated
        """
        pass

    # =========================================================================
    # Common utilities
    # =========================================================================

    def check_import_lock(self) -> bool:
        """
        Check if a Railway import is in progress.

        Returns:
            True if import is locked (should skip this job)
        """
        lock_file = self.data_dir / ".import_lock"
        if lock_file.exists():
            self.logger.warning(
                "Import lock detected - Railway import may be in progress. "
                "Skipping this job to avoid conflicts."
            )
            return True
        return False

    def batch_merge(
        self,
        query: str,
        records: List[Dict],
        batch_size: Optional[int] = None
    ) -> int:
        """
        Execute a MERGE query in batches.

        Args:
            query: Cypher query with $batch parameter (UNWIND $batch AS record ...)
            records: List of record dicts
            batch_size: Override default batch size

        Returns:
            Total records processed
        """
        batch_size = batch_size or self.batch_size
        total = 0

        with self.driver.session() as session:
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                try:
                    session.run(query, {'batch': batch})
                    total += len(batch)
                except Exception as e:
                    self.logger.error(f"Batch merge error at offset {i}: {e}")
                    self.stats['errors'] += 1

        return total

    def run_query(self, query: str, params: Optional[Dict] = None) -> List[Dict]:
        """Execute a read query and return results."""
        with self.driver.session() as session:
            result = session.run(query, params or {})
            return [dict(record) for record in result]

    def run_write(self, query: str, params: Optional[Dict] = None):
        """Execute a write query."""
        with self.driver.session() as session:
            session.run(query, params or {})

    # =========================================================================
    # Main execution
    # =========================================================================

    def run(self, skip_lock_check: bool = False, **kwargs) -> Dict[str, Any]:
        """
        Execute the full ETL pipeline.

        Args:
            skip_lock_check: If True, ignore import lock
            **kwargs: Passed to download_data()

        Returns:
            Dictionary with job results and statistics
        """
        self.stats['start_time'] = datetime.now()
        self.logger.info("=" * 60)
        self.logger.info(f"{self.name.upper()} INGESTION JOB STARTED")
        self.logger.info(f"Time: {self.stats['start_time'].isoformat()}")
        self.logger.info("=" * 60)

        # Check for import lock
        if not skip_lock_check and self.check_import_lock():
            return {
                'status': 'skipped',
                'reason': 'import_lock',
                'stats': self.stats
            }

        try:
            # Step 1: Download
            self.logger.info("Step 1/4: Downloading data...")
            df = self.download_data(**kwargs)

            if df is None or df.empty:
                self.logger.warning("No data downloaded")
                return {
                    'status': 'no_data',
                    'stats': self.stats
                }

            self.stats['records_downloaded'] = len(df)
            self.logger.info(f"  Downloaded {len(df):,} records")

            # Step 2: Process
            self.logger.info("Step 2/4: Processing data...")
            df = self.process_data(df)
            self.stats['records_processed'] = len(df)
            self.logger.info(f"  Processed {len(df):,} records")

            # Step 3: Schema
            self.logger.info("Step 3/4: Ensuring schema exists...")
            self.create_schema()

            # Step 4: Create nodes
            self.logger.info("Step 4/4: Creating/updating nodes...")
            count = self.create_nodes(df)
            self.stats['nodes_created'] = count
            self.logger.info(f"  Created/updated {count:,} nodes")

            self.stats['end_time'] = datetime.now()
            duration = (self.stats['end_time'] - self.stats['start_time']).seconds

            self.logger.info("=" * 60)
            self.logger.info(f"{self.name.upper()} INGESTION COMPLETED")
            self.logger.info(f"Duration: {duration}s")
            self.logger.info(f"Records: {self.stats['records_processed']:,}")
            self.logger.info(f"Errors: {self.stats['errors']}")
            self.logger.info("=" * 60)

            return {
                'status': 'success',
                'duration_seconds': duration,
                'stats': self.stats
            }

        except Exception as e:
            self.logger.error(f"Job failed: {e}", exc_info=True)
            self.stats['errors'] += 1
            self.stats['end_time'] = datetime.now()

            return {
                'status': 'failed',
                'error': str(e),
                'stats': self.stats
            }

        finally:
            self.close()

    # =========================================================================
    # Data validation helpers
    # =========================================================================

    @staticmethod
    def safe_int(val) -> Optional[int]:
        """Safely convert to int."""
        if pd.isna(val) or val is None or val == '':
            return None
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def safe_float(val) -> Optional[float]:
        """Safely convert to float."""
        if pd.isna(val) or val is None or val == '':
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def safe_str(val) -> Optional[str]:
        """Safely convert to string."""
        if pd.isna(val) or val is None:
            return None
        return str(val).strip() or None
