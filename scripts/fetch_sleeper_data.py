#!/usr/bin/env python3
"""
Fetch Sleeper fantasy football league data.
Uses the Sleeper API to get rosters, standings, and transactions.
"""

import os
import json
from pathlib import Path
from datetime import datetime
from typing import Optional

import requests
import pandas as pd

# Configuration
DATA_DIR = Path(__file__).parent.parent / "data"
SLEEPER_API = "https://api.sleeper.app/v1"
LEAGUE_ID = os.environ.get("SLEEPER_LEAGUE_ID", "1180199027998867456")  # Lucid Losers

def ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "sleeper").mkdir(exist_ok=True)

def fetch_json(endpoint: str) -> Optional[dict]:
    """Fetch JSON from Sleeper API."""
    url = f"{SLEEPER_API}/{endpoint}"
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"   ❌ Error fetching {endpoint}: {e}")
        return None

def fetch_league_info():
    """Fetch basic league information."""
    print("📊 Fetching league info...")
    data = fetch_json(f"league/{LEAGUE_ID}")
    
    if data:
        # Save raw JSON
        with open(DATA_DIR / "sleeper" / "league_info.json", 'w') as f:
            json.dump(data, f, indent=2)
        
        # Create summary
        info = {
            'league_id': data.get('league_id'),
            'name': data.get('name'),
            'season': data.get('season'),
            'total_rosters': data.get('total_rosters'),
            'status': data.get('status'),
            'scoring': data.get('scoring_settings', {}).get('rec', 0),
            'best_ball': data.get('settings', {}).get('best_ball', 0)
        }
        print(f"   ✅ League: {info['name']} ({info['season']})")
        return info
    return None

def fetch_users():
    """Fetch league users/managers."""
    print("📊 Fetching users...")
    data = fetch_json(f"league/{LEAGUE_ID}/users")
    
    if data:
        users = []
        for user in data:
            users.append({
                'user_id': user.get('user_id'),
                'display_name': user.get('display_name'),
                'team_name': user.get('metadata', {}).get('team_name', user.get('display_name')),
                'avatar': user.get('avatar')
            })
        
        df = pd.DataFrame(users)
        df.to_csv(DATA_DIR / "sleeper" / "users.csv", index=False)
        print(f"   ✅ {len(users)} users")
        return df
    return None

def fetch_rosters():
    """Fetch all team rosters."""
    print("📊 Fetching rosters...")
    data = fetch_json(f"league/{LEAGUE_ID}/rosters")
    
    if data:
        rosters = []
        for roster in data:
            roster_info = {
                'roster_id': roster.get('roster_id'),
                'owner_id': roster.get('owner_id'),
                'players': roster.get('players', []),
                'starters': roster.get('starters', []),
                'wins': roster.get('settings', {}).get('wins', 0),
                'losses': roster.get('settings', {}).get('losses', 0),
                'ties': roster.get('settings', {}).get('ties', 0),
                'fpts': roster.get('settings', {}).get('fpts', 0),
                'fpts_decimal': roster.get('settings', {}).get('fpts_decimal', 0),
                'fpts_against': roster.get('settings', {}).get('fpts_against', 0)
            }
            rosters.append(roster_info)
        
        # Save raw JSON
        with open(DATA_DIR / "sleeper" / "rosters.json", 'w') as f:
            json.dump(data, f, indent=2)
        
        # Create summary CSV
        df = pd.DataFrame(rosters)
        df['total_fpts'] = df['fpts'] + df['fpts_decimal'] / 100
        df['record'] = df['wins'].astype(str) + '-' + df['losses'].astype(str)
        df.to_csv(DATA_DIR / "sleeper" / "rosters_summary.csv", index=False)
        
        print(f"   ✅ {len(rosters)} rosters")
        return rosters
    return None

def fetch_players():
    """Fetch all NFL players from Sleeper."""
    print("📊 Fetching player database...")
    data = fetch_json("players/nfl")
    
    if data:
        players = []
        for player_id, player in data.items():
            if player.get('position') in ['QB', 'RB', 'WR', 'TE', 'K', 'DEF']:
                players.append({
                    'sleeper_id': player_id,
                    'name': player.get('full_name', f"{player.get('first_name', '')} {player.get('last_name', '')}"),
                    'position': player.get('position'),
                    'team': player.get('team'),
                    'age': player.get('age'),
                    'years_exp': player.get('years_exp'),
                    'status': player.get('status'),
                    'injury_status': player.get('injury_status'),
                    'number': player.get('number')
                })
        
        df = pd.DataFrame(players)
        df.to_csv(DATA_DIR / "sleeper" / "players.csv", index=False)
        print(f"   ✅ {len(players)} players")
        return df
    return None

def fetch_matchups(week: int = None):
    """Fetch matchups for current or specified week."""
    # Get current week from league info
    league_info = fetch_json(f"league/{LEAGUE_ID}")
    if not league_info:
        return None
    
    current_week = week or league_info.get('settings', {}).get('leg', 1)
    
    print(f"📊 Fetching matchups (week {current_week})...")
    data = fetch_json(f"league/{LEAGUE_ID}/matchups/{current_week}")
    
    if data:
        with open(DATA_DIR / "sleeper" / f"matchups_week{current_week}.json", 'w') as f:
            json.dump(data, f, indent=2)
        print(f"   ✅ Week {current_week} matchups")
        return data
    return None

def fetch_transactions(week: int = None):
    """Fetch recent transactions."""
    league_info = fetch_json(f"league/{LEAGUE_ID}")
    if not league_info:
        return None
    
    current_week = week or league_info.get('settings', {}).get('leg', 1)
    
    print(f"📊 Fetching transactions...")
    data = fetch_json(f"league/{LEAGUE_ID}/transactions/{current_week}")
    
    if data:
        with open(DATA_DIR / "sleeper" / "transactions.json", 'w') as f:
            json.dump(data, f, indent=2)
        print(f"   ✅ {len(data)} transactions")
        return data
    return None

def fetch_traded_picks():
    """Fetch traded draft picks."""
    print("📊 Fetching traded picks...")
    data = fetch_json(f"league/{LEAGUE_ID}/traded_picks")
    
    if data:
        picks = []
        for pick in data:
            picks.append({
                'season': pick.get('season'),
                'round': pick.get('round'),
                'roster_id': pick.get('roster_id'),
                'previous_owner_id': pick.get('previous_owner_id'),
                'owner_id': pick.get('owner_id')
            })
        
        df = pd.DataFrame(picks)
        df.to_csv(DATA_DIR / "sleeper" / "traded_picks.csv", index=False)
        print(f"   ✅ {len(picks)} traded picks")
        return df
    return None

def create_roster_with_players():
    """Create detailed roster report with player names."""
    print("📊 Creating detailed roster report...")
    
    # Load data
    try:
        with open(DATA_DIR / "sleeper" / "rosters.json", 'r') as f:
            rosters_data = json.load(f)
        
        users_df = pd.read_csv(DATA_DIR / "sleeper" / "users.csv")
        players_df = pd.read_csv(DATA_DIR / "sleeper" / "players.csv")
    except FileNotFoundError as e:
        print(f"   ❌ Missing data: {e}")
        return None
    
    # Create player lookup
    player_lookup = dict(zip(players_df['sleeper_id'].astype(str), 
                            players_df[['name', 'position', 'team']].to_dict('records')))
    
    # Create user lookup
    user_lookup = dict(zip(users_df['user_id'], users_df['display_name']))
    
    # Build detailed roster data
    roster_details = []
    for roster in rosters_data:
        owner_name = user_lookup.get(roster.get('owner_id'), 'Unknown')
        roster_id = roster.get('roster_id')
        
        for player_id in roster.get('players', []):
            player_info = player_lookup.get(str(player_id), {})
            is_starter = player_id in roster.get('starters', [])
            
            roster_details.append({
                'roster_id': roster_id,
                'owner': owner_name,
                'sleeper_id': player_id,
                'name': player_info.get('name', 'Unknown'),
                'position': player_info.get('position', 'Unknown'),
                'team': player_info.get('team', 'FA'),
                'is_starter': is_starter
            })
    
    df = pd.DataFrame(roster_details)
    df.to_csv(DATA_DIR / "sleeper" / "roster_details.csv", index=False)
    print(f"   ✅ Created detailed roster with {len(df)} player entries")
    return df

def save_metadata():
    """Save refresh metadata."""
    metadata = {
        'last_updated': datetime.utcnow().isoformat(),
        'league_id': LEAGUE_ID,
        'source': 'api.sleeper.app'
    }
    
    with open(DATA_DIR / "sleeper" / "metadata.json", 'w') as f:
        json.dump(metadata, f, indent=2)

def main():
    print("\n" + "=" * 60)
    print("😴 SLEEPER DATA REFRESH")
    print(f"   League ID: {LEAGUE_ID}")
    print(f"   Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60 + "\n")
    
    ensure_data_dir()
    
    # Fetch all data
    fetch_league_info()
    fetch_users()
    fetch_rosters()
    fetch_players()
    fetch_matchups()
    fetch_transactions()
    fetch_traded_picks()
    
    # Create derived reports
    create_roster_with_players()
    
    # Save metadata
    save_metadata()
    
    print("\n" + "=" * 60)
    print("✅ SLEEPER DATA REFRESH COMPLETE")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()
