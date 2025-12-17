#!/usr/bin/env python3
"""
Dynasty Edge - Integration Demo

This script demonstrates the AI Data Science Team integration capabilities
without requiring a full Neo4j setup. Uses sample data to show the workflow.

Run with: python demo_integration.py
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# Check for AI Data Science Team
try:
    from ai_data_science_team.agents import FeatureEngineeringAgent
    from ai_data_science_team.ds_agents import EDAToolsAgent
    from langchain_openai import ChatOpenAI
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    print("⚠️  ai-data-science-team not installed")
    print("   Install with: pip install ai-data-science-team langchain-openai")


def create_sample_data() -> pd.DataFrame:
    """Create realistic sample dynasty football data."""
    
    np.random.seed(42)
    
    # Sample players with realistic values
    players = [
        # WRs
        {'name': 'Ja\'Marr Chase', 'position': 'WR', 'age': 24.3, 'team': 'CIN', 'ktc': 9500, 'qb_age': 27.5},
        {'name': 'CeeDee Lamb', 'position': 'WR', 'age': 25.4, 'team': 'DAL', 'ktc': 8800, 'qb_age': 31.2},
        {'name': 'Amon-Ra St. Brown', 'position': 'WR', 'age': 24.9, 'team': 'DET', 'ktc': 8200, 'qb_age': 31.1},
        {'name': 'Drake London', 'position': 'WR', 'age': 23.2, 'team': 'ATL', 'ktc': 7062, 'qb_age': 24.5},
        {'name': 'Malik Nabers', 'position': 'WR', 'age': 21.4, 'team': 'NYG', 'ktc': 7801, 'qb_age': 22.6},
        {'name': 'Marvin Harrison Jr', 'position': 'WR', 'age': 22.1, 'team': 'ARI', 'ktc': 7500, 'qb_age': 25.1},
        {'name': 'Davante Adams', 'position': 'WR', 'age': 32.0, 'team': 'NYJ', 'ktc': 4200, 'qb_age': 26.8},
        {'name': 'Stefon Diggs', 'position': 'WR', 'age': 31.5, 'team': 'HOU', 'ktc': 3800, 'qb_age': 23.2},
        # RBs
        {'name': 'Jahmyr Gibbs', 'position': 'RB', 'age': 22.7, 'team': 'DET', 'ktc': 9808, 'qb_age': 31.1},
        {'name': 'Bijan Robinson', 'position': 'RB', 'age': 22.4, 'team': 'ATL', 'ktc': 9100, 'qb_age': 24.5},
        {'name': 'Breece Hall', 'position': 'RB', 'age': 23.5, 'team': 'NYJ', 'ktc': 7200, 'qb_age': 26.8},
        {'name': 'Jonathan Taylor', 'position': 'RB', 'age': 25.9, 'team': 'IND', 'ktc': 6500, 'qb_age': 26.2},
        {'name': 'Saquon Barkley', 'position': 'RB', 'age': 27.8, 'team': 'PHI', 'ktc': 5800, 'qb_age': 27.4},
        {'name': 'Derrick Henry', 'position': 'RB', 'age': 30.9, 'team': 'BAL', 'ktc': 3500, 'qb_age': 28.3},
    ]
    
    # Create multiple snapshots per player (simulating temporal data)
    snapshots = []
    for player in players:
        base_ktc = player['ktc']
        base_tpg = np.random.uniform(4, 10) if player['position'] == 'WR' else np.random.uniform(2, 6)
        base_ppg = np.random.uniform(10, 20)
        
        for i in range(10):  # 10 snapshots over 30 days
            days_ago = 30 - (i * 3)
            
            # Simulate realistic changes
            ktc_noise = np.random.normal(0, 100)
            tpg_change = np.random.normal(0, 0.3)
            ppg_change = np.random.normal(0, 1)
            
            # Younger players tend to gain value
            age_effect = -20 if player['age'] < 25 else 10 if player['age'] > 28 else 0
            
            # Higher targets correlate with KTC gains
            tpg_effect = tpg_change * 150  # Strong correlation
            
            ktc_value = int(base_ktc + ktc_noise + age_effect * i + tpg_effect)
            tpg = round(base_tpg + tpg_change * i, 2)
            ppg = round(base_ppg + ppg_change, 1)
            
            snapshot = {
                'player_name': player['name'],
                'position': player['position'],
                'age': player['age'],
                'team': player['team'],
                'qb_age': player['qb_age'],
                'snapshot_date': (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d'),
                'ktc_value': ktc_value,
                'targets_per_game': max(1, tpg),
                'target_share': round(np.random.uniform(0.15, 0.30), 3),
                'snap_share': round(np.random.uniform(0.70, 0.95), 3),
                'ppg': max(5, ppg),
                'games_played': 10 + i
            }
            snapshots.append(snapshot)
    
    df = pd.DataFrame(snapshots)
    
    # Calculate deltas
    df = df.sort_values(['player_name', 'snapshot_date'])
    df['ktc_delta'] = df.groupby('player_name')['ktc_value'].diff()
    df['tpg_delta'] = df.groupby('player_name')['targets_per_game'].diff()
    
    return df


def demo_manual_analysis(df: pd.DataFrame):
    """Demonstrate manual correlation analysis without AI agents."""
    from scipy import stats
    
    print("\n" + "=" * 70)
    print("📊 MANUAL CORRELATION ANALYSIS (No AI Required)")
    print("=" * 70)
    
    # Filter to rows with valid deltas
    analysis_df = df[df['ktc_delta'].notna()].copy()
    
    print(f"\n📈 Analyzing {len(analysis_df)} snapshots across {df['player_name'].nunique()} players")
    
    # Calculate correlations
    numeric_cols = ['targets_per_game', 'target_share', 'snap_share', 'ppg', 'age', 'qb_age', 'tpg_delta']
    
    correlations = []
    for col in numeric_cols:
        if col in analysis_df.columns:
            valid = analysis_df[[col, 'ktc_delta']].dropna()
            if len(valid) >= 10:
                r, p = stats.pearsonr(valid[col], valid['ktc_delta'])
                correlations.append({
                    'metric': col,
                    'correlation': round(r, 3),
                    'p_value': round(p, 4),
                    'significant': p < 0.05
                })
    
    # Sort by absolute correlation
    correlations.sort(key=lambda x: abs(x['correlation']), reverse=True)
    
    print("\n🔍 Correlations with KTC Changes:")
    print("-" * 50)
    for corr in correlations:
        sig = "✓" if corr['significant'] else " "
        print(f"  {sig} {corr['metric']:20s} r={corr['correlation']:+.3f}  (p={corr['p_value']:.4f})")
    
    print("\n💡 Key Insights:")
    top_corr = correlations[0] if correlations else None
    if top_corr:
        print(f"  • Strongest predictor: {top_corr['metric']} (r={top_corr['correlation']:.3f})")
        print(f"  • Suggested weight adjustment: w_{top_corr['metric']} = {1.0 + abs(top_corr['correlation']) * 0.5:.2f}")


def demo_ai_analysis(df: pd.DataFrame):
    """Demonstrate AI-powered analysis using ai-data-science-team."""
    
    if not AI_AVAILABLE:
        print("\n⚠️  Skipping AI analysis (ai-data-science-team not installed)")
        return
    
    if not os.getenv('OPENAI_API_KEY'):
        print("\n⚠️  Skipping AI analysis (OPENAI_API_KEY not set)")
        return
    
    print("\n" + "=" * 70)
    print("🤖 AI-POWERED ANALYSIS (using ai-data-science-team)")
    print("=" * 70)
    
    llm = ChatOpenAI(model="gpt-4o", api_key=os.getenv('OPENAI_API_KEY'))
    
    # Prepare data
    analysis_df = df[df['ktc_delta'].notna()].copy()
    
    # --- Feature Engineering ---
    print("\n📍 Step 1: Feature Engineering Agent")
    print("-" * 50)
    
    try:
        fe_agent = FeatureEngineeringAgent(model=llm, log=False)
        fe_agent.invoke_agent(
            data_raw=analysis_df,
            user_instructions="""
            Create dynasty fantasy football features to predict ktc_delta:
            
            1. years_remaining: Career endpoint minus age
               - WR: 33 - age
               - RB: 30 - age
            
            2. value_per_year: ktc_value / years_remaining
            
            3. qb_youth_score: 1 if qb_age < 26, 0.5 if 26-30, 0 if > 30
            
            4. age_bucket: categorical (young: <24, prime: 24-27, aging: 27-30, old: >30)
            
            Keep all original columns. Handle any missing values with median imputation.
            """,
            target_variable="ktc_delta",
            max_retries=2
        )
        
        engineered_df = fe_agent.get_data_engineered()
        new_features = [c for c in engineered_df.columns if c not in analysis_df.columns]
        print(f"  ✅ Created {len(new_features)} new features: {new_features}")
        
        # Show generated code
        print("\n  📝 Generated Code Preview:")
        code = fe_agent.get_data_engineer_function()
        if code:
            # Show first 500 chars
            preview = code[:500] + "..." if len(code) > 500 else code
            for line in preview.split('\n')[:15]:
                print(f"     {line}")
        
    except Exception as e:
        print(f"  ❌ Feature engineering failed: {e}")
        engineered_df = analysis_df
    
    # --- EDA Analysis ---
    print("\n📍 Step 2: EDA Tools Agent")
    print("-" * 50)
    
    try:
        eda_agent = EDAToolsAgent(model=llm, log=False)
        eda_agent.invoke_agent(
            data_raw=engineered_df,
            user_instructions="""
            Analyze what drives ktc_delta (KTC value changes):
            
            1. Calculate correlations between all numeric features and ktc_delta
            2. Identify the top 5 predictors
            3. Check for multicollinearity
            4. Provide actionable insights for dynasty fantasy football
            
            Focus on which metrics I should weight more heavily in my valuation model.
            """
        )
        
        print("  ✅ EDA analysis complete")
        
        # Get workflow summary if available
        if hasattr(eda_agent, 'get_workflow_summary'):
            summary = eda_agent.get_workflow_summary()
            if summary:
                print(f"\n  📊 Analysis Summary:\n{summary[:1000]}...")
        
    except Exception as e:
        print(f"  ❌ EDA analysis failed: {e}")
    
    print("\n✅ AI Analysis Complete!")


def demo_weight_suggestion(correlations: list):
    """Demonstrate weight adjustment suggestions based on correlations."""
    
    print("\n" + "=" * 70)
    print("⚖️  WEIGHT ADJUSTMENT SUGGESTIONS")
    print("=" * 70)
    
    print("\nBased on discovered correlations, here are suggested weight changes:")
    print("-" * 60)
    print(f"{'Metric':<25} {'Correlation':>12} {'Current':>10} {'Suggested':>10}")
    print("-" * 60)
    
    for corr in correlations[:5]:
        r = corr['correlation']
        current = 1.0
        
        # Suggest weight based on correlation strength
        if abs(r) >= 0.5:
            suggested = 1.0 + abs(r) * 0.6
        elif abs(r) >= 0.3:
            suggested = 1.0 + abs(r) * 0.4
        else:
            suggested = 1.0
        
        print(f"w_{corr['metric']:<23} {r:>+10.3f} {current:>10.2f} {suggested:>10.2f}")
    
    print("-" * 60)
    print("\n💡 To apply: Use the agent command:")
    print('   "Apply weight change for w_targets_per_game to 1.3 because of strong correlation"')


def main():
    """Run the integration demo."""
    
    print("\n" + "=" * 70)
    print("🏈 DYNASTY EDGE - AI Data Science Team Integration Demo")
    print("=" * 70)
    
    # Create sample data
    print("\n📊 Creating sample dynasty football data...")
    df = create_sample_data()
    print(f"   Created {len(df)} snapshots for {df['player_name'].nunique()} players")
    print(f"   Date range: {df['snapshot_date'].min()} to {df['snapshot_date'].max()}")
    
    # Show sample
    print("\n📋 Sample Data:")
    print(df[['player_name', 'position', 'age', 'ktc_value', 'targets_per_game', 'ktc_delta']].head(10).to_string(index=False))
    
    # Manual analysis (always runs)
    demo_manual_analysis(df)
    
    # AI analysis (if available)
    demo_ai_analysis(df)
    
    # Weight suggestions
    from scipy import stats
    correlations = []
    for col in ['targets_per_game', 'target_share', 'snap_share', 'ppg', 'age']:
        valid = df[[col, 'ktc_delta']].dropna()
        if len(valid) >= 10:
            r, p = stats.pearsonr(valid[col], valid['ktc_delta'])
            correlations.append({'metric': col, 'correlation': r})
    correlations.sort(key=lambda x: abs(x['correlation']), reverse=True)
    demo_weight_suggestion(correlations)
    
    print("\n" + "=" * 70)
    print("✅ DEMO COMPLETE")
    print("=" * 70)
    print("\nNext steps:")
    print("  1. Set up Neo4j and run setup_neo4j.py")
    print("  2. Configure your API keys in .env")
    print("  3. Run dynasty_agent_enhanced.py for full functionality")
    print("  4. Start collecting temporal data with temporal_pipeline.py")


if __name__ == "__main__":
    main()
