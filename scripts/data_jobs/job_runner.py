"""
Job Runner
==========
Unified job execution with logging, error handling, and status reporting.

Used to run multiple ingestion jobs in sequence with proper error handling
and consolidated reporting.
"""

import os
import sys
import json
import logging
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from .utils import check_import_lock, format_duration

# Configure logging
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


class JobRunner:
    """
    Orchestrates multiple data ingestion jobs.

    Features:
    - Sequential job execution with dependency handling
    - Consolidated logging and status reporting
    - Import lock checking
    - Timeout handling
    - Status persistence for monitoring
    """

    def __init__(self, name: str = "job_runner"):
        """
        Initialize the job runner.

        Args:
            name: Identifier for this runner instance
        """
        self.name = name
        self.logger = self._setup_logging()
        self.results: Dict[str, Dict] = {}
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None

    def _setup_logging(self) -> logging.Logger:
        """Configure logging."""
        logger = logging.getLogger(self.name)
        logger.setLevel(logging.INFO)
        logger.handlers = []

        # Console handler
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        logger.addHandler(console)

        # File handler
        file_handler = logging.FileHandler(LOG_DIR / f"{self.name}.log")
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        logger.addHandler(file_handler)

        return logger

    def run_job(
        self,
        script: str,
        args: List[str] = None,
        timeout: int = 600,
        required: bool = False
    ) -> Dict[str, Any]:
        """
        Run a single job script.

        Args:
            script: Path to the Python script (relative to project root)
            args: Command-line arguments for the script
            timeout: Maximum execution time in seconds
            required: If True, stop pipeline on failure

        Returns:
            Dictionary with job result
        """
        script_path = PROJECT_ROOT / script
        args = args or []

        job_name = Path(script).stem
        self.logger.info(f"Running job: {job_name}")

        start = datetime.now()
        result = {
            'job': job_name,
            'script': script,
            'status': 'unknown',
            'start_time': start.isoformat(),
            'duration': 0,
        }

        try:
            process = subprocess.run(
                [sys.executable, str(script_path)] + args,
                cwd=str(PROJECT_ROOT),
                timeout=timeout,
                capture_output=True,
                text=True
            )

            duration = (datetime.now() - start).seconds
            result['duration'] = duration
            result['return_code'] = process.returncode

            if process.returncode == 0:
                result['status'] = 'success'
                self.logger.info(
                    f"  {job_name} completed successfully in {format_duration(duration)}"
                )
            else:
                result['status'] = 'failed'
                result['stderr'] = process.stderr[-1000:] if process.stderr else ''
                self.logger.error(f"  {job_name} failed with code {process.returncode}")
                if result['stderr']:
                    self.logger.error(f"  Error: {result['stderr'][:200]}")

        except subprocess.TimeoutExpired:
            result['status'] = 'timeout'
            result['duration'] = timeout
            self.logger.error(f"  {job_name} timed out after {timeout}s")

        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
            self.logger.error(f"  {job_name} error: {e}")

        self.results[job_name] = result
        return result

    def run_jobs(
        self,
        jobs: List[Dict[str, Any]],
        stop_on_failure: bool = False
    ) -> Dict[str, Any]:
        """
        Run multiple jobs in sequence.

        Args:
            jobs: List of job configurations:
                {
                    'name': str,
                    'script': str,
                    'args': list (optional),
                    'timeout': int (optional, default 600),
                    'required': bool (optional, default False)
                }
            stop_on_failure: If True, stop on first failure

        Returns:
            Dictionary with consolidated results
        """
        self.start_time = datetime.now()
        self.logger.info("=" * 60)
        self.logger.info(f"JOB RUNNER STARTED: {self.name}")
        self.logger.info(f"Time: {self.start_time.isoformat()}")
        self.logger.info(f"Jobs: {len(jobs)}")
        self.logger.info("=" * 60)

        # Check import lock
        if check_import_lock():
            self.logger.warning("Import lock detected - skipping all jobs")
            return {
                'status': 'skipped',
                'reason': 'import_lock',
                'jobs': {}
            }

        # Run each job
        for job_config in jobs:
            name = job_config.get('name', job_config['script'])
            script = job_config['script']
            args = job_config.get('args', [])
            timeout = job_config.get('timeout', 600)
            required = job_config.get('required', False)

            result = self.run_job(script, args, timeout, required)

            # Check if we should stop
            if result['status'] not in ['success', 'skipped']:
                if stop_on_failure or required:
                    self.logger.error(f"Required job {name} failed - stopping pipeline")
                    break

        self.end_time = datetime.now()
        total_duration = (self.end_time - self.start_time).seconds

        # Calculate summary
        success_count = sum(1 for r in self.results.values() if r['status'] == 'success')
        failed_count = sum(1 for r in self.results.values() if r['status'] in ['failed', 'error', 'timeout'])

        # Log summary
        self.logger.info("=" * 60)
        self.logger.info("JOB RUNNER COMPLETED")
        self.logger.info(f"Total duration: {format_duration(total_duration)}")
        self.logger.info(f"Success: {success_count}/{len(self.results)}")
        self.logger.info(f"Failed: {failed_count}/{len(self.results)}")
        self.logger.info("=" * 60)

        # Save status to file
        status = {
            'runner': self.name,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'total_duration': total_duration,
            'success_count': success_count,
            'failed_count': failed_count,
            'jobs': self.results
        }

        status_file = LOG_DIR / f"{self.name}_status.json"
        with open(status_file, 'w') as f:
            json.dump(status, f, indent=2)

        return status

    def get_status(self) -> Dict[str, Any]:
        """Get current runner status."""
        return {
            'runner': self.name,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'jobs': self.results
        }


def load_last_status(runner_name: str) -> Optional[Dict]:
    """Load the last run status for a job runner."""
    status_file = LOG_DIR / f"{runner_name}_status.json"
    if status_file.exists():
        with open(status_file, 'r') as f:
            return json.load(f)
    return None
