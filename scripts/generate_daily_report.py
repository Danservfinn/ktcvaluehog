#!/usr/bin/env python3
"""
Generate daily dynasty analysis report.
Combines NFL stats, KTC values, and Sleeper data to identify opportunities.
"""

import os
import json
from pathlib import Path
from datetime import datetime

import pandas as pd

# Configuration
DATA_DIR = Path(__file__).parent.parent / "data"
REPORTS_DIR = DATA_DIR / "reports"

def ensure_dirs():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

def load_data():
    """Load all available data files."""
    data = {}
    
    # NFL Data
    try:
        data['dynasty_metrics'] = pd.read_csv(DATA_DIR / "nfl" / "dynasty_metrics.csv")
        print(f"   ✅ Dynasty metrics: {len(data['dynasty_metrics'])} players")
    except:
        print("   ⚠️ Dynasty metrics not found")
    
    try:
        data['weekly_stats'] = pd.read_csv(DATA_DIR / "nfl" / "weekly_stats.csv")
        print(f"   ✅ Weekly stats: {len(data['weekly_stats'])} records")
    except:
        print("   ⚠️ Weekly stats not found")
    
    try:
        data['ngs_receiving'] = pd.read_csv(DATA_DIR / "nfl" / "ngs_receiving.csv")
        print(f"   ✅ NGS receiving: {len(data['ngs_receiving'])} records")
    except:
        print("   ⚠️ NGS receiving not found")
    
    # KTC Data
    try:
        data['ktc'] = pd.read_csv(DATA_DIR / "ktc_values.csv")
        print(f"   ✅ KTC values: {len(data['ktc'])} players")
    except:
        print("   ⚠️ KTC values not found")
    
    # Sleeper Data
    try:
        data['roster_details'] = pd.read_csv(DATA_DIR / "sleeper" / "roster_details.csv")
        print(f"   ✅ Roster details: {len(data['roster_details'])} entries")
    except:
        print("   ⚠️ Roster details not found")
    
    try:
        data['rosters_summary'] = pd.read_csv(DATA_DIR / "sleeper" / "rosters_summary.csv")
        print(f"   ✅ Roster summary: {len(data['rosters_summary'])} teams")
    except:
        print("   ⚠️ Roster summary not found")
    
    return data

def identify_buy_candidates(data: dict) -> pd.DataFrame:
    """
    Identify players who are undervalued based on production.
    High targets/PPG but lower KTC value.
    """
    if 'dynasty_metrics' not in data or 'ktc' not in data:
        return pd.DataFrame()
    
    metrics = data['dynasty_metrics'].copy()
    ktc = data['ktc'].copy()
    
    # Merge on name (fuzzy matching would be better in production)
    merged = metrics.merge(ktc, on='name', how='inner', suffixes=('', '_ktc'))
    
    if len(merged) == 0:
        return pd.DataFrame()
    
    # Calculate value score (production / KTC value)
    merged['value_score'] = (merged['ppg'] * 100) / merged['ktc_value'].replace(0, 1)
    
    # Filter to players with decent sample size and meaningful KTC value
    buys = merged[
        (merged['games'] >= 5) & 
        (merged['ktc_value'] > 1000) &
        (merged['position'].isin(['WR', 'RB', 'TE']))
    ].copy()
    
    # Sort by value score (higher = more undervalued)
    buys = buys.sort_values('value_score', ascending=False)
    
    return buys[['name', 'position', 'team', 'games', 'ppg', 'targets_per_game', 
                 'ktc_value', 'value_score']].head(20)

def identify_sell_candidates(data: dict) -> pd.DataFrame:
    """
    Identify players who are overvalued based on production.
    Lower targets/PPG but higher KTC value.
    """
    if 'dynasty_metrics' not in data or 'ktc' not in data:
        return pd.DataFrame()
    
    metrics = data['dynasty_metrics'].copy()
    ktc = data['ktc'].copy()
    
    merged = metrics.merge(ktc, on='name', how='inner', suffixes=('', '_ktc'))
    
    if len(merged) == 0:
        return pd.DataFrame()
    
    # Calculate value score
    merged['value_score'] = (merged['ppg'] * 100) / merged['ktc_value'].replace(0, 1)
    
    # Filter to high-value players with declining production
    sells = merged[
        (merged['games'] >= 5) & 
        (merged['ktc_value'] > 3000) &
        (merged['position'].isin(['WR', 'RB', 'TE']))
    ].copy()
    
    # Sort by value score (lower = more overvalued)
    sells = sells.sort_values('value_score', ascending=True)
    
    return sells[['name', 'position', 'team', 'games', 'ppg', 'targets_per_game',
                  'ktc_value', 'value_score']].head(20)

def identify_rising_players(data: dict) -> pd.DataFrame:
    """
    Identify players with increasing target share / snap share.
    """
    if 'weekly_stats' not in data:
        return pd.DataFrame()
    
    weekly = data['weekly_stats'].copy()
    
    # Get recent vs early season
    max_week = weekly['week'].max()
    recent_weeks = weekly[weekly['week'] > max_week - 4]
    early_weeks = weekly[weekly['week'] <= 4]
    
    # Aggregate
    recent_agg = recent_weeks.groupby(['player_display_name', 'position']).agg({
        'targets': 'mean',
        'fantasy_points_ppr': 'mean'
    }).reset_index()
    recent_agg.columns = ['name', 'position', 'recent_tpg', 'recent_ppg']
    
    early_agg = early_weeks.groupby(['player_display_name', 'position']).agg({
        'targets': 'mean',
        'fantasy_points_ppr': 'mean'
    }).reset_index()
    early_agg.columns = ['name', 'position', 'early_tpg', 'early_ppg']
    
    # Merge
    merged = recent_agg.merge(early_agg, on=['name', 'position'], how='inner')
    
    # Calculate change
    merged['tpg_change'] = merged['recent_tpg'] - merged['early_tpg']
    merged['ppg_change'] = merged['recent_ppg'] - merged['early_ppg']
    
    # Filter to risers
    risers = merged[
        (merged['tpg_change'] > 1) &
        (merged['position'].isin(['WR', 'RB', 'TE']))
    ].sort_values('tpg_change', ascending=False)
    
    return risers.head(15)

def generate_standings_report(data: dict) -> str:
    """Generate league standings markdown."""
    if 'rosters_summary' not in data:
        return "No standings data available."
    
    standings = data['rosters_summary'].sort_values('total_fpts', ascending=False)
    
    report = "## League Standings\n\n"
    report += "| Rank | Team | Record | Points For |\n"
    report += "|------|------|--------|------------|\n"
    
    for i, row in standings.iterrows():
        rank = standings.index.get_loc(i) + 1
        report += f"| {rank} | Team {row['roster_id']} | {row['record']} | {row['total_fpts']:.1f} |\n"
    
    return report

def generate_markdown_report(data: dict) -> str:
    """Generate full markdown report."""
    report = f"""# Dynasty Edge Daily Report
**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}

---

"""
    
    # Buy Candidates
    report += "## 🟢 BUY Candidates (Undervalued)\n\n"
    buys = identify_buy_candidates(data)
    if len(buys) > 0:
        report += "| Player | Pos | Team | Games | PPG | TPG | KTC | Value Score |\n"
        report += "|--------|-----|------|-------|-----|-----|-----|-------------|\n"
        for _, row in buys.head(10).iterrows():
            report += f"| {row['name']} | {row['position']} | {row.get('team', 'FA')} | "
            report += f"{int(row['games'])} | {row['ppg']:.1f} | {row['targets_per_game']:.1f} | "
            report += f"{int(row['ktc_value'])} | {row['value_score']:.2f} |\n"
    else:
        report += "No buy candidates identified.\n"
    
    report += "\n---\n\n"
    
    # Sell Candidates
    report += "## 🔴 SELL Candidates (Overvalued)\n\n"
    sells = identify_sell_candidates(data)
    if len(sells) > 0:
        report += "| Player | Pos | Team | Games | PPG | TPG | KTC | Value Score |\n"
        report += "|--------|-----|------|-------|-----|-----|-----|-------------|\n"
        for _, row in sells.head(10).iterrows():
            report += f"| {row['name']} | {row['position']} | {row.get('team', 'FA')} | "
            report += f"{int(row['games'])} | {row['ppg']:.1f} | {row['targets_per_game']:.1f} | "
            report += f"{int(row['ktc_value'])} | {row['value_score']:.2f} |\n"
    else:
        report += "No sell candidates identified.\n"
    
    report += "\n---\n\n"
    
    # Rising Players
    report += "## 📈 Rising Players (Increasing Volume)\n\n"
    risers = identify_rising_players(data)
    if len(risers) > 0:
        report += "| Player | Pos | Early TPG | Recent TPG | Change |\n"
        report += "|--------|-----|-----------|------------|--------|\n"
        for _, row in risers.head(10).iterrows():
            report += f"| {row['name']} | {row['position']} | {row['early_tpg']:.1f} | "
            report += f"{row['recent_tpg']:.1f} | +{row['tpg_change']:.1f} |\n"
    else:
        report += "No rising players identified.\n"
    
    report += "\n---\n\n"
    
    # Standings
    report += generate_standings_report(data)
    
    return report

def main():
    print("\n" + "=" * 60)
    print("📊 DAILY REPORT GENERATION")
    print(f"   Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60 + "\n")
    
    ensure_dirs()
    
    print("📥 Loading data...")
    data = load_data()
    
    print("\n📝 Generating report...")
    report = generate_markdown_report(data)
    
    # Save report
    report_path = REPORTS_DIR / f"daily_report_{datetime.utcnow().strftime('%Y%m%d')}.md"
    with open(report_path, 'w') as f:
        f.write(report)
    print(f"   ✅ Saved to {report_path}")
    
    # Also save as latest
    with open(REPORTS_DIR / "latest_report.md", 'w') as f:
        f.write(report)
    print(f"   ✅ Saved to latest_report.md")
    
    print("\n" + "=" * 60)
    print("✅ REPORT GENERATION COMPLETE")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()
