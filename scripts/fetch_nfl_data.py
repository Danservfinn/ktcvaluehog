#!/usr/bin/env python3
"""
Fetch NFL data from nflverse for daily refresh.
Saves to data/ directory as CSV files.
"""

import os
from pathlib import Path
from datetime import datetime

import nflreadpy as nfl
import pandas as pd

# Configuration
DATA_DIR = Path(__file__).parent.parent / "data"
CURRENT_SEASON = 2024

def ensure_data_dir():
    """Ensure data directory exists."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "nfl").mkdir(exist_ok=True)

def fetch_weekly_stats():
    """Fetch weekly player statistics."""
    print("📊 Fetching weekly player stats...")
    try:
        stats = nfl.load_player_stats([CURRENT_SEASON], summary_level='week')
        df = stats.to_pandas()
        
        # Filter to skill positions
        df = df[df['position'].isin(['QB', 'RB', 'WR', 'TE'])]
        
        # Save to CSV
        output_path = DATA_DIR / "nfl" / "weekly_stats.csv"
        df.to_csv(output_path, index=False)
        print(f"   ✅ Saved {len(df)} records to {output_path}")
        return df
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None

def fetch_snap_counts():
    """Fetch snap count data."""
    print("📊 Fetching snap counts...")
    try:
        snaps = nfl.load_snap_counts([CURRENT_SEASON])
        df = snaps.to_pandas()
        
        output_path = DATA_DIR / "nfl" / "snap_counts.csv"
        df.to_csv(output_path, index=False)
        print(f"   ✅ Saved {len(df)} records to {output_path}")
        return df
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None

def fetch_nextgen_stats():
    """Fetch Next Gen Stats for all stat types."""
    print("📊 Fetching Next Gen Stats...")
    
    for stat_type in ['passing', 'rushing', 'receiving']:
        try:
            ngs = nfl.load_nextgen_stats([CURRENT_SEASON], stat_type=stat_type)
            df = ngs.to_pandas()
            
            output_path = DATA_DIR / "nfl" / f"ngs_{stat_type}.csv"
            df.to_csv(output_path, index=False)
            print(f"   ✅ NGS {stat_type}: {len(df)} records")
        except Exception as e:
            print(f"   ❌ NGS {stat_type} error: {e}")

def fetch_rosters():
    """Fetch current rosters."""
    print("📊 Fetching rosters...")
    try:
        rosters = nfl.load_rosters([CURRENT_SEASON])
        df = rosters.to_pandas()
        
        output_path = DATA_DIR / "nfl" / "rosters.csv"
        df.to_csv(output_path, index=False)
        print(f"   ✅ Saved {len(df)} records to {output_path}")
        return df
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None

def fetch_player_ids():
    """Fetch player ID mappings."""
    print("📊 Fetching player ID mappings...")
    try:
        players = nfl.load_players()
        df = players.to_pandas()
        
        # Filter to relevant columns
        id_cols = ['gsis_id', 'display_name', 'position', 'team_abbr', 
                   'sleeper_id', 'espn_id', 'yahoo_id', 'pfr_id', 'pff_id']
        available_cols = [c for c in id_cols if c in df.columns]
        df = df[available_cols]
        
        output_path = DATA_DIR / "nfl" / "player_ids.csv"
        df.to_csv(output_path, index=False)
        print(f"   ✅ Saved {len(df)} records to {output_path}")
        return df
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None

def calculate_dynasty_metrics():
    """Calculate aggregated dynasty metrics from weekly data."""
    print("📊 Calculating dynasty metrics...")
    
    try:
        # Load weekly stats
        weekly_path = DATA_DIR / "nfl" / "weekly_stats.csv"
        if not weekly_path.exists():
            print("   ⚠️ Weekly stats not found, skipping")
            return None
        
        weekly = pd.read_csv(weekly_path)
        
        # Aggregate by player
        agg_dict = {
            'targets': 'sum',
            'receptions': 'sum',
            'receiving_yards': 'sum',
            'receiving_tds': 'sum',
            'carries': 'sum',
            'rushing_yards': 'sum',
            'rushing_tds': 'sum',
            'fantasy_points_ppr': 'sum',
            'week': 'count'
        }
        
        # Only aggregate columns that exist
        agg_dict = {k: v for k, v in agg_dict.items() if k in weekly.columns}
        
        dynasty = weekly.groupby(['player_id', 'player_display_name', 'position']).agg(agg_dict).reset_index()
        dynasty.columns = ['player_id', 'name', 'position', 'targets', 'receptions', 
                          'rec_yards', 'rec_tds', 'carries', 'rush_yards', 'rush_tds',
                          'ppr_points', 'games']
        
        # Calculate per-game metrics
        dynasty['targets_per_game'] = (dynasty['targets'] / dynasty['games']).round(2)
        dynasty['ppg'] = (dynasty['ppr_points'] / dynasty['games']).round(2)
        dynasty['yards_per_target'] = (dynasty['rec_yards'] / dynasty['targets'].replace(0, 1)).round(2)
        dynasty['catch_rate'] = (dynasty['receptions'] / dynasty['targets'].replace(0, 1) * 100).round(1)
        
        # Sort by PPG
        dynasty = dynasty.sort_values('ppg', ascending=False)
        
        output_path = DATA_DIR / "nfl" / "dynasty_metrics.csv"
        dynasty.to_csv(output_path, index=False)
        print(f"   ✅ Saved {len(dynasty)} player metrics to {output_path}")
        return dynasty
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None

def save_metadata():
    """Save metadata about the data refresh."""
    metadata = {
        'last_updated': datetime.utcnow().isoformat(),
        'season': CURRENT_SEASON,
        'source': 'nflverse/nflreadpy'
    }
    
    import json
    with open(DATA_DIR / "nfl" / "metadata.json", 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"   ✅ Metadata saved")

def main():
    print("\n" + "=" * 60)
    print("🏈 NFL DATA REFRESH")
    print(f"   Season: {CURRENT_SEASON}")
    print(f"   Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60 + "\n")
    
    ensure_data_dir()
    
    # Fetch all data
    fetch_weekly_stats()
    fetch_snap_counts()
    fetch_nextgen_stats()
    fetch_rosters()
    fetch_player_ids()
    
    # Calculate derived metrics
    calculate_dynasty_metrics()
    
    # Save metadata
    save_metadata()
    
    print("\n" + "=" * 60)
    print("✅ NFL DATA REFRESH COMPLETE")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()
