#!/usr/bin/env python3
"""
Fetch KeepTradeCut dynasty player values.
Scrapes KTC website and saves to CSV.
"""

import os
import json
import time
from pathlib import Path
from datetime import datetime

import requests
import pandas as pd

# Configuration
DATA_DIR = Path(__file__).parent.parent / "data"
KTC_URL = "https://keeptradecut.com/dynasty-rankings"

def ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

def fetch_ktc_values():
    """
    Fetch KTC values from their website.
    KTC loads data via JavaScript, so we need to find the data endpoint.
    """
    print("📊 Fetching KTC values...")
    
    # KTC API endpoint (discovered via browser dev tools)
    api_url = "https://keeptradecut.com/api/v1/rankings"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Referer': 'https://keeptradecut.com/dynasty-rankings'
    }
    
    try:
        # Try Superflex rankings first
        params = {
            'format': 'json',
            'sf': '1',  # Superflex
            'tep': '0.5'  # 0.5 TE Premium
        }
        
        response = requests.get(api_url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            if isinstance(data, list):
                df = pd.DataFrame(data)
                print(f"   ✅ Retrieved {len(df)} players from KTC API")
                return df
        
        print(f"   ⚠️ API returned status {response.status_code}, trying scrape method...")
        
    except Exception as e:
        print(f"   ⚠️ API method failed: {e}, trying scrape method...")
    
    # Fallback: Try to get embedded JSON from page
    try:
        response = requests.get(KTC_URL, headers=headers, timeout=30)
        
        if response.status_code == 200:
            # Look for embedded data in script tags
            import re
            
            # Try to find JSON data in the page
            json_pattern = r'window\.__INITIAL_STATE__\s*=\s*({.*?});'
            match = re.search(json_pattern, response.text, re.DOTALL)
            
            if match:
                data = json.loads(match.group(1))
                if 'rankings' in data:
                    df = pd.DataFrame(data['rankings'])
                    print(f"   ✅ Extracted {len(df)} players from embedded data")
                    return df
        
        print(f"   ❌ Could not extract KTC data")
        return None
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None

def process_ktc_data(df: pd.DataFrame) -> pd.DataFrame:
    """Process raw KTC data into clean format."""
    if df is None or len(df) == 0:
        return None
    
    # Standardize column names
    column_mapping = {
        'playerName': 'name',
        'player_name': 'name',
        'firstName': 'first_name',
        'lastName': 'last_name',
        'position': 'position',
        'team': 'team',
        'value': 'ktc_value',
        'superflexValue': 'sf_value',
        'oneQBValue': 'oneqb_value',
        'age': 'age',
        'rookie': 'is_rookie',
        'sleeperId': 'sleeper_id'
    }
    
    # Rename columns that exist
    df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})
    
    # If name is split, combine
    if 'first_name' in df.columns and 'last_name' in df.columns and 'name' not in df.columns:
        df['name'] = df['first_name'] + ' ' + df['last_name']
    
    # Select key columns
    key_cols = ['name', 'position', 'team', 'ktc_value', 'sf_value', 'oneqb_value', 
                'age', 'is_rookie', 'sleeper_id']
    available_cols = [c for c in key_cols if c in df.columns]
    
    return df[available_cols]

def save_ktc_data(df: pd.DataFrame):
    """Save KTC data to CSV."""
    if df is None or len(df) == 0:
        print("   ⚠️ No data to save")
        return
    
    output_path = DATA_DIR / "ktc_values.csv"
    df.to_csv(output_path, index=False)
    print(f"   ✅ Saved {len(df)} players to {output_path}")
    
    # Also save metadata
    metadata = {
        'last_updated': datetime.utcnow().isoformat(),
        'player_count': len(df),
        'source': 'keeptradecut.com'
    }
    
    with open(DATA_DIR / "ktc_metadata.json", 'w') as f:
        json.dump(metadata, f, indent=2)

def main():
    print("\n" + "=" * 60)
    print("💰 KTC DATA REFRESH")
    print(f"   Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60 + "\n")
    
    ensure_data_dir()
    
    # Fetch and process
    raw_df = fetch_ktc_values()
    processed_df = process_ktc_data(raw_df)
    save_ktc_data(processed_df)
    
    print("\n" + "=" * 60)
    print("✅ KTC DATA REFRESH COMPLETE")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()
