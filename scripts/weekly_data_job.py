#!/usr/bin/env python3
"""
Weekly Data Consolidation Job
=============================
Runs all weekly data ingestion jobs in correct order.

Schedule: Tuesday 4:00 AM (during NFL season)
Duration: ~15-20 minutes

Components (in order):
1. Play-by-Play Aggregations (requires nfl_data_py)
2. Injury Reports (requires nfl_data_py)
3. Depth Charts (requires nfl_data_py)
4. KTC Trend Update (uses existing KTCSnapshot data)

Usage:
    python scripts/weekly_data_job.py              # Run all jobs
    python scripts/weekly_data_job.py --job pbp    # Run specific job
    python scripts/weekly_data_job.py --dry-run    # Show what would run
    python scripts/weekly_data_job.py --status     # Show last run status
"""

import sys
import argparse
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.data_jobs import JobRunner, is_nfl_season, check_import_lock
from scripts.data_jobs.job_runner import load_last_status

# Weekly job configuration
WEEKLY_JOBS = [
    {
        'name': 'pbp_features',
        'script': 'scripts/ingest_pbp_features.py',
        'args': ['--current-week'],
        'timeout': 600,  # 10 minutes
        'required': False,
        'description': 'Play-by-play aggregated features (EPA, red zone, etc.)',
    },
    {
        'name': 'injuries',
        'script': 'scripts/ingest_injuries.py',
        'args': ['--current-week'],
        'timeout': 180,  # 3 minutes
        'required': False,
        'description': 'Injury reports and designations',
    },
    {
        'name': 'depth_charts',
        'script': 'scripts/ingest_depth_charts.py',
        'args': ['--current-week'],
        'timeout': 180,  # 3 minutes
        'required': False,
        'description': 'Depth chart positions and roles',
    },
    {
        'name': 'ktc_trends',
        'script': 'scripts/process_ktc_timeseries.py',
        'args': [],
        'timeout': 120,  # 2 minutes
        'required': False,
        'description': 'KTC value trend calculations',
    },
]


def main():
    parser = argparse.ArgumentParser(
        description='Weekly Data Consolidation Job',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--job',
        choices=[j['name'] for j in WEEKLY_JOBS],
        help='Run only a specific job'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would run without executing'
    )
    parser.add_argument(
        '--status',
        action='store_true',
        help='Show status of last run'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Run even if not in NFL season or import locked'
    )

    args = parser.parse_args()

    # Show last status
    if args.status:
        status = load_last_status('weekly_data')
        if status:
            print(f"\nLast Run: {status.get('start_time', 'Unknown')}")
            print(f"Duration: {status.get('total_duration', 0)}s")
            print(f"Success: {status.get('success_count', 0)}/{len(status.get('jobs', {}))}")
            print(f"Failed: {status.get('failed_count', 0)}/{len(status.get('jobs', {}))}")
            print("\nJob Results:")
            for name, result in status.get('jobs', {}).items():
                print(f"  {name}: {result.get('status', 'unknown')} ({result.get('duration', 0)}s)")
        else:
            print("No previous run found")
        return 0

    # Check if we should run
    if not args.force:
        # Check import lock
        if check_import_lock():
            print("Import lock detected - Railway import may be in progress.")
            print("Use --force to run anyway.")
            return 1

        # Check if NFL season
        if not is_nfl_season():
            print("Not currently in NFL season (Sep-Feb).")
            print("Use --force to run anyway.")
            return 1

    # Determine which jobs to run
    if args.job:
        jobs = [j for j in WEEKLY_JOBS if j['name'] == args.job]
    else:
        jobs = WEEKLY_JOBS

    # Dry run
    if args.dry_run:
        print("\nWould run the following jobs:")
        print("-" * 50)
        for job in jobs:
            print(f"\n{job['name']}:")
            print(f"  Script: {job['script']}")
            print(f"  Args: {' '.join(job['args']) if job['args'] else '(none)'}")
            print(f"  Timeout: {job['timeout']}s")
            print(f"  Description: {job['description']}")
        return 0

    # Run jobs
    runner = JobRunner('weekly_data')
    result = runner.run_jobs(jobs)

    # Return exit code
    if result.get('status') == 'skipped':
        return 2
    elif result.get('failed_count', 0) > 0:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
