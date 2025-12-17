#!/usr/bin/env python3
"""
Dynasty Player Valuation Model
Generates independent valuations to compare against KTC crowdsourced values.
Author: Built for @danservfinn's Lucid Losers league
"""

import pandas as pd
import numpy as np
from datetime import datetime

# =============================================================================
# CONFIGURATION - Adjust these for your league settings
# =============================================================================

LEAGUE_SETTINGS = {
    'scoring': 'PPR',
    'superflex': True,
    'te_premium': 0.5,  # TE receives 0.5 extra PPR
    'roster_size': 28,
    'num_teams': 10
}

# Position scarcity multipliers for Superflex + TE Premium
SCARCITY_MULTIPLIER = {
    'QB': 1.8,   # Superflex makes QBs valuable
    'RB': 1.0,   # Baseline
    'WR': 1.0,   # Baseline
    'TE': 1.35   # TE premium boost
}

# Annual discount rate (future years are worth less)
DISCOUNT_RATE = 0.85

# =============================================================================
# AGING CURVES - Based on historical NFL data
# =============================================================================

def get_aging_factor(position: str, age: float) -> float:
    """
    Returns the aging curve factor for a player based on position and age.
    1.0 = peak performance, lower = declining
    """
    curves = {
        'QB': {
            (0, 28): 1.00,
            (28, 31): 0.95,
            (31, 34): 0.85,
            (34, 37): 0.70,
            (37, 50): 0.50
        },
        'RB': {
            (0, 24): 1.00,
            (24, 25): 0.90,
            (25, 26): 0.80,
            (26, 27): 0.65,
            (27, 28): 0.50,
            (28, 50): 0.35
        },
        'WR': {
            (0, 26): 1.00,
            (26, 28): 0.90,
            (28, 30): 0.75,
            (30, 32): 0.55,
            (32, 50): 0.35
        },
        'TE': {
            (0, 27): 1.00,
            (27, 30): 0.85,
            (30, 32): 0.65,
            (32, 50): 0.40
        }
    }
    
    if position not in curves:
        return 0.5
    
    for (low, high), factor in curves[position].items():
        if low <= age < high:
            return factor
    
    return 0.3  # Default for very old players


def get_career_endpoint(position: str) -> int:
    """Returns expected career endpoint age by position."""
    endpoints = {
        'QB': 38,
        'RB': 30,
        'WR': 33,
        'TE': 34
    }
    return endpoints.get(position, 32)


def get_years_remaining(position: str, age: float) -> int:
    """Calculate years of fantasy relevance remaining."""
    endpoint = get_career_endpoint(position)
    return max(1, int(endpoint - age))


# =============================================================================
# VALUATION CALCULATION
# =============================================================================

def calculate_independent_value(
    player_name: str,
    position: str,
    age: float,
    ktc_value: float,
    is_rookie: bool = False,
    injury_discount: float = 0.0,  # 0-1, higher = more injury prone
    situation_bonus: float = 0.0   # -0.2 to +0.2 for situation quality
) -> dict:
    """
    Calculate an independent valuation for a player.
    
    Returns a dict with:
    - your_value: Calculated value
    - ktc_value: Original KTC value
    - edge: Difference (positive = KTC overvalues)
    - reasoning: Why the value differs
    """
    
    # Start with KTC as baseline (since we don't have underlying production data)
    # In a full implementation, you'd use projected fantasy points
    baseline_value = ktc_value
    
    # Calculate years remaining
    years_remaining = get_years_remaining(position, age)
    
    # Apply aging curve adjustment
    current_age_factor = get_aging_factor(position, age)
    
    # Calculate present value of future production
    # This simulates discounting future years
    future_value_multiplier = 0
    for year in range(years_remaining):
        future_age = age + year
        year_factor = get_aging_factor(position, future_age)
        discounted_factor = year_factor * (DISCOUNT_RATE ** year)
        future_value_multiplier += discounted_factor
    
    # Normalize to roughly match KTC scale
    # A 23-year-old RB has ~7 years, a 28-year-old has ~2
    max_possible_years = get_career_endpoint(position) - 21  # Youngest plausible age
    normalized_multiplier = future_value_multiplier / max_possible_years
    
    # Apply rookie discount (KTC tends to overvalue rookies)
    rookie_factor = 0.85 if is_rookie else 1.0
    
    # Apply injury discount
    injury_factor = 1.0 - (injury_discount * 0.3)  # Max 30% discount for injury-prone
    
    # Apply situation adjustment
    situation_factor = 1.0 + situation_bonus
    
    # Apply position scarcity
    scarcity = SCARCITY_MULTIPLIER.get(position, 1.0)
    
    # Calculate final value
    # We're adjusting KTC based on our factors
    adjustment_factor = (
        normalized_multiplier * 
        rookie_factor * 
        injury_factor * 
        situation_factor *
        (scarcity / SCARCITY_MULTIPLIER.get(position, 1.0))  # Normalize out KTC's implicit scarcity
    )
    
    # The key insight: KTC doesn't properly discount aging
    # So we apply our aging curve to create divergence
    your_value = baseline_value * adjustment_factor * current_age_factor
    
    # Calculate edge
    edge = ktc_value - your_value
    edge_pct = (edge / ktc_value * 100) if ktc_value > 0 else 0
    
    # Generate reasoning
    reasons = []
    if age > get_career_endpoint(position) - 4:
        reasons.append(f"Aging concern: {position} at {age:.1f} years")
    if is_rookie:
        reasons.append("Rookie premium applied by KTC")
    if injury_discount > 0.1:
        reasons.append(f"Injury history discount: {injury_discount*100:.0f}%")
    if situation_bonus < -0.1:
        reasons.append("Poor situation (QB/scheme)")
    elif situation_bonus > 0.1:
        reasons.append("Great situation (QB/scheme)")
    
    return {
        'player_name': player_name,
        'position': position,
        'age': age,
        'years_remaining': years_remaining,
        'ktc_value': ktc_value,
        'your_value': round(your_value),
        'edge': round(edge),
        'edge_pct': round(edge_pct, 1),
        'signal': 'SELL' if edge_pct > 15 else ('BUY' if edge_pct < -15 else 'HOLD'),
        'reasoning': '; '.join(reasons) if reasons else 'Fair value'
    }


# =============================================================================
# MAIN ANALYSIS
# =============================================================================

def analyze_league(ktc_path: str) -> pd.DataFrame:
    """
    Analyze all players and generate independent valuations.
    """
    # Load KTC data
    ktc = pd.read_csv(ktc_path)
    ktc.columns = ['player_name', 'position_rank', 'position', 'team', 'value', 
                   'age', 'rookie', 'oneqb_rank', 'oneqb_value', 'rdraft_rank', 'rdraft_value']
    
    # Filter to actual players (not picks)
    players = ktc[ktc['position'].isin(['QB', 'RB', 'WR', 'TE'])].copy()
    players['age'] = pd.to_numeric(players['age'], errors='coerce')
    players['value'] = pd.to_numeric(players['value'], errors='coerce')
    players['is_rookie'] = players['rookie'] == 'Yes'
    
    # Calculate valuations for each player
    results = []
    for _, row in players.iterrows():
        if pd.isna(row['age']) or pd.isna(row['value']):
            continue
            
        result = calculate_independent_value(
            player_name=row['player_name'],
            position=row['position'],
            age=row['age'],
            ktc_value=row['value'],
            is_rookie=row['is_rookie']
        )
        results.append(result)
    
    df = pd.DataFrame(results)
    return df.sort_values('edge', ascending=False)


def print_opportunities(df: pd.DataFrame, roster_players: list = None):
    """Print buy/sell opportunities."""
    
    print("\n" + "=" * 90)
    print("🔴 TOP SELL OPPORTUNITIES (KTC Overvalues These Players)")
    print("=" * 90)
    sells = df[df['signal'] == 'SELL'].head(20)
    for _, row in sells.iterrows():
        owned = "📍 YOU OWN" if roster_players and row['player_name'] in roster_players else ""
        print(f"  {row['player_name']:<25} {row['position']:<3} Age {row['age']:.1f} | "
              f"KTC: {row['ktc_value']:>6,.0f} → Your: {row['your_value']:>6,.0f} | "
              f"Edge: +{row['edge_pct']:.0f}% {owned}")
        print(f"      └─ {row['reasoning']}")
    
    print("\n" + "=" * 90)
    print("🟢 TOP BUY OPPORTUNITIES (KTC Undervalues These Players)")
    print("=" * 90)
    buys = df[df['signal'] == 'BUY'].tail(20).iloc[::-1]
    for _, row in buys.iterrows():
        owned = "📍 YOU OWN" if roster_players and row['player_name'] in roster_players else ""
        print(f"  {row['player_name']:<25} {row['position']:<3} Age {row['age']:.1f} | "
              f"KTC: {row['ktc_value']:>6,.0f} → Your: {row['your_value']:>6,.0f} | "
              f"Edge: {row['edge_pct']:.0f}% {owned}")
        print(f"      └─ {row['reasoning']}")


if __name__ == "__main__":
    # Your roster
    your_roster = [
        "Jahmyr Gibbs", "Bijan Robinson", "Trey McBride", "Sam Darnold", "Nico Collins",
        "Drake London", "Jameson Williams", "Breece Hall", "C.J. Stroud", "Ashton Jeanty",
        "Travis Hunter", "Garrett Wilson", "Sam LaPorta", "Oronde Gadsden", "Jayden Reed",
        "Luther Burden", "Bryce Young", "Anthony Richardson", "Shedeur Sanders",
        "Zach Charbonnet", "Braelon Allen", "Dylan Sampson", "Matthew Golden"
    ]
    
    # Run analysis
    print("\n🏈 DYNASTY VALUATION MODEL - Lucid Losers League")
    print(f"📅 Analysis Date: {datetime.now().strftime('%Y-%m-%d')}")
    print("-" * 90)
    
    df = analyze_league('/mnt/project/ktc_lucid_losers.csv')
    print_opportunities(df, your_roster)
    
    # Save results
    output_path = '/mnt/user-data/outputs/valuation_analysis.csv'
    df.to_csv(output_path, index=False)
    print(f"\n✅ Full analysis saved to: {output_path}")
    
    # Summary stats
    print("\n" + "=" * 90)
    print("📊 SUMMARY STATISTICS")
    print("=" * 90)
    print(f"Total players analyzed: {len(df)}")
    print(f"SELL signals (KTC overvalues): {len(df[df['signal'] == 'SELL'])}")
    print(f"BUY signals (KTC undervalues): {len(df[df['signal'] == 'BUY'])}")
    print(f"HOLD (fair value): {len(df[df['signal'] == 'HOLD'])}")
