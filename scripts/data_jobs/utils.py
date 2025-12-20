"""
Data Jobs Utilities
===================
Common utilities shared across all data ingestion jobs.
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Tuple

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv()

# Import lock file location
IMPORT_LOCK_FILE = PROJECT_ROOT / "data" / ".import_lock"


def get_neo4j_client():
    """
    Get a Neo4j client instance using environment variables.

    Returns:
        Neo4jClient instance from src.database
    """
    from src.database.neo4j_client import Neo4jClient
    return Neo4jClient()


def check_import_lock() -> bool:
    """
    Check if Railway import is in progress.

    Returns:
        True if import is locked (should skip jobs)
    """
    return IMPORT_LOCK_FILE.exists()


def create_import_lock(reason: str = "Manual lock"):
    """
    Create an import lock to prevent data jobs from running.

    Args:
        reason: Description of why the lock was created
    """
    IMPORT_LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(IMPORT_LOCK_FILE, 'w') as f:
        f.write(f"Created: {datetime.now().isoformat()}\n")
        f.write(f"Reason: {reason}\n")


def release_import_lock():
    """Remove the import lock."""
    if IMPORT_LOCK_FILE.exists():
        IMPORT_LOCK_FILE.unlink()


def get_current_nfl_week() -> Tuple[int, int]:
    """
    Calculate the current NFL season and week.

    The NFL season typically runs from early September to early February.
    Regular season is weeks 1-18, playoffs are weeks 19-22.

    Returns:
        Tuple of (season_year, week_number)
    """
    now = datetime.now()
    year = now.year
    month = now.month

    # NFL season starts in September
    # If we're in Jan/Feb, we're still in the previous year's season
    if month <= 2:
        season = year - 1
    else:
        season = year

    # Estimate week based on date
    # Season typically starts first Thursday after Labor Day (first Monday in Sep)
    # For simplicity, assume Week 1 starts around Sep 7

    if month < 9 or (month == 9 and now.day < 7):
        # Preseason or before season starts
        return (season, 0)

    # Calculate weeks since season start
    season_start = datetime(season, 9, 7)  # Approximate
    days_since_start = (now - season_start).days
    week = min(max(1, days_since_start // 7 + 1), 22)  # Cap at week 22 (Super Bowl)

    return (season, week)


def is_nfl_season() -> bool:
    """
    Check if we're currently in the NFL season.

    Returns:
        True if we're in regular season or playoffs (Sep-Feb)
    """
    month = datetime.now().month
    return month >= 9 or month <= 2


def get_recent_seasons(count: int = 5) -> list:
    """
    Get a list of recent NFL seasons.

    Args:
        count: Number of seasons to return

    Returns:
        List of season years, most recent first
    """
    current_season = get_current_nfl_week()[0]
    return list(range(current_season, current_season - count, -1))


def format_duration(seconds: int) -> str:
    """Format duration in human-readable format."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"


def get_env_with_default(key: str, default: str) -> str:
    """Get environment variable with fallback default."""
    return os.getenv(key, default)


# NFL team abbreviations (modern)
NFL_TEAMS = [
    'ARI', 'ATL', 'BAL', 'BUF', 'CAR', 'CHI', 'CIN', 'CLE',
    'DAL', 'DEN', 'DET', 'GB', 'HOU', 'IND', 'JAX', 'KC',
    'LAC', 'LAR', 'LV', 'MIA', 'MIN', 'NE', 'NO', 'NYG',
    'NYJ', 'PHI', 'PIT', 'SEA', 'SF', 'TB', 'TEN', 'WAS'
]

# Position groups
FANTASY_POSITIONS = ['QB', 'RB', 'WR', 'TE']
ALL_POSITIONS = ['QB', 'RB', 'WR', 'TE', 'K', 'DEF']

# Team abbreviation normalization
TEAM_ABBR_NORMALIZE = {
    'OAK': 'LV',
    'SD': 'LAC',
    'STL': 'LAR',
    'SL': 'LAR',
    'WSH': 'WAS',
    'JAC': 'JAX',
}


def normalize_team_abbr(abbr: str) -> str:
    """Normalize team abbreviation to current standard."""
    if not abbr:
        return ''
    abbr = abbr.upper().strip()
    return TEAM_ABBR_NORMALIZE.get(abbr, abbr)


def normalize_position(pos: str) -> Optional[str]:
    """Normalize position to standard fantasy positions."""
    if not pos:
        return None

    pos = pos.upper().strip()

    # Handle special cases
    if pos in ['HB', 'FB']:
        return 'RB'
    elif pos in ['WR/TE', 'TE/WR']:
        return 'WR'
    elif pos in FANTASY_POSITIONS:
        return pos

    return pos  # Return as-is for non-fantasy positions
