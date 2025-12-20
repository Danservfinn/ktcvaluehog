#!/usr/bin/env python3
"""
Archive KTC Snapshot for ML Training

Saves daily KTC values to historical directory for future time-series ML training.
Extracts key fields and adds timestamp for temporal analysis.
"""

import os
import json
import pandas as pd
from datetime import datetime
from pathlib import Path

# Paths
DATA_DIR = Path(__file__).parent.parent / "data"
HISTORICAL_DIR = DATA_DIR / "historical" / "ktc_snapshots"
KTC_LIVE = DATA_DIR / "ktc_live.json"
KTC_SCRAPED = DATA_DIR / "ktc_scraped.csv"


def extract_superflex_value(sf_values: str) -> int:
    """Extract superflex value from JSON string."""
    try:
        if isinstance(sf_values, str):
            data = eval(sf_values)  # KTC data uses Python dict format
            return data.get('value', 0)
        return 0
    except:
        return 0


def extract_trend(sf_values: str) -> int:
    """Extract 7-day trend from JSON string."""
    try:
        if isinstance(sf_values, str):
            data = eval(sf_values)
            return data.get('overall7DayTrend', 0)
        return 0
    except:
        return 0


def archive_from_json():
    """Archive from ktc_live.json if available."""
    if not KTC_LIVE.exists():
        return None

    with open(KTC_LIVE, 'r') as f:
        data = json.load(f)

    players = []
    for player in data:
        sf_data = player.get('superflexValues', {})
        players.append({
            'player_id': player.get('playerID'),
            'name': player.get('playerName'),
            'position': player.get('position'),
            'team': player.get('team'),
            'age': player.get('age'),
            'sf_value': sf_data.get('value', 0),
            'sf_rank': sf_data.get('rank', 0),
            'trend_7d': sf_data.get('overall7DayTrend', 0),
            'positional_rank': sf_data.get('positionalRank', 0),
        })

    return pd.DataFrame(players)


def archive_from_csv():
    """Archive from ktc_scraped.csv as fallback."""
    if not KTC_SCRAPED.exists():
        return None

    df = pd.read_csv(KTC_SCRAPED)

    # Extract values from nested JSON strings
    df['sf_value'] = df['superflexValues'].apply(extract_superflex_value)
    df['trend_7d'] = df['superflexValues'].apply(extract_trend)

    return df[['playerID', 'playerName', 'position', 'team', 'age', 'sf_value']].rename(columns={
        'playerID': 'player_id',
        'playerName': 'name'
    })


def main():
    # Create historical directory
    HISTORICAL_DIR.mkdir(parents=True, exist_ok=True)

    # Get current date and time period (AM/PM for twice daily)
    now = datetime.now()
    today = now.strftime('%Y%m%d')
    period = 'AM' if now.hour < 12 else 'PM'
    snapshot_file = HISTORICAL_DIR / f"ktc_{today}_{period}.csv"

    # Skip if already archived for this period
    if snapshot_file.exists():
        print(f"Snapshot already exists for {today} {period}, skipping")
        return

    # Try JSON first, then CSV
    df = archive_from_json()
    if df is None or df.empty:
        df = archive_from_csv()

    if df is None or df.empty:
        print("No KTC data found to archive")
        return

    # Add snapshot metadata
    df['snapshot_date'] = today
    df['snapshot_period'] = period
    df['snapshot_ts'] = now.isoformat()

    # Save snapshot
    df.to_csv(snapshot_file, index=False)
    print(f"Archived {len(df)} players to {snapshot_file}")

    # Also update the consolidated historical file
    consolidated = HISTORICAL_DIR / "ktc_all_snapshots.csv"
    if consolidated.exists():
        existing = pd.read_csv(consolidated)
        combined = pd.concat([existing, df], ignore_index=True)
        # Dedupe by player_id + snapshot_date + period for twice-daily
        combined = combined.drop_duplicates(
            subset=['player_id', 'snapshot_date', 'snapshot_period'],
            keep='last'
        )
    else:
        combined = df

    combined.to_csv(consolidated, index=False)
    print(f"Consolidated file now has {len(combined)} total records")

    # Print stats
    snapshot_files = [f for f in HISTORICAL_DIR.glob("ktc_*.csv") if 'all_snapshots' not in f.name]
    snapshot_count = len(snapshot_files)
    print(f"Total snapshots collected: {snapshot_count} (twice-daily enabled)")
    if snapshot_count >= 60:  # 30 days x 2 snapshots
        print("You have enough data for time-series ML training!")


if __name__ == "__main__":
    main()
