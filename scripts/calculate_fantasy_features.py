"""
Calculate advanced fantasy production features for ML model training.
Adds career totals, trends, consistency metrics, and peak production.
"""

import pandas as pd
import numpy as np
from neo4j import GraphDatabase
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')


def get_driver():
    """Get Neo4j driver."""
    return GraphDatabase.driver("bolt://localhost:7687", auth=None)


def calculate_career_totals(driver):
    """
    Calculate career fantasy totals in all 3 scoring formats.
    Updates Player nodes with:
    - career_fpts_std (Standard)
    - career_fpts_half (0.5 PPR)
    - career_fpts_ppr (1 PPR)
    - career_ppg_std, career_ppg_half, career_ppg_ppr
    """
    print("\n" + "=" * 60)
    print("1. CALCULATING CAREER FANTASY TOTALS (ALL FORMATS)")
    print("=" * 60)

    with driver.session() as session:
        # Calculate career totals from SeasonStats
        result = session.run("""
            MATCH (p:Player)-[:HAS_SEASON_STATS]->(s:SeasonStats)
            WHERE p.position IN ['QB', 'RB', 'WR', 'TE']
            WITH p,
                 sum(s.games_played) as total_games,
                 sum(s.fantasy_points) as total_std,
                 sum(s.fantasy_points_ppr) as total_ppr,
                 sum(s.receptions) as total_rec,
                 count(s) as seasons
            WHERE total_games > 0
            WITH p, total_games, total_std, total_ppr, total_rec, seasons,
                 total_std + (total_rec * 0.5) as total_half
            SET p.career_fpts_std = total_std,
                p.career_fpts_half = total_half,
                p.career_fpts_ppr = total_ppr,
                p.career_ppg_std = total_std / total_games,
                p.career_ppg_half = total_half / total_games,
                p.career_ppg_ppr = total_ppr / total_games,
                p.career_games = total_games,
                p.career_receptions = total_rec,
                p.seasons_played = seasons
            RETURN count(p) as updated
        """)
        count = result.single()['updated']
        print(f"   ✅ Updated {count} players with career totals")

        # Sample output
        result = session.run("""
            MATCH (p:Player)
            WHERE p.position = 'WR' AND p.career_fpts_ppr > 500
            RETURN p.name, p.career_games,
                   p.career_fpts_std, p.career_fpts_half, p.career_fpts_ppr,
                   p.career_ppg_std, p.career_ppg_half, p.career_ppg_ppr
            ORDER BY p.career_fpts_ppr DESC
            LIMIT 5
        """)

        print("\n   Sample Career Totals (Top 5 WRs):")
        print("   " + "-" * 70)
        for r in result:
            print(f"   {r['p.name'][:20]:<20} Games: {r['p.career_games']:>3} | "
                  f"Std: {r['p.career_ppg_std']:.1f} | "
                  f"Half: {r['p.career_ppg_half']:.1f} | "
                  f"PPR: {r['p.career_ppg_ppr']:.1f}")


def calculate_ppg_trends(driver):
    """
    Calculate multi-season PPG trends.
    Updates Player nodes with:
    - ppg_trend_slope (positive = improving, negative = declining)
    - ppg_trend_3yr (recent 3-year trend)
    - ppg_trajectory (categorical: rising/stable/declining)
    """
    print("\n" + "=" * 60)
    print("2. CALCULATING MULTI-SEASON PPG TRENDS")
    print("=" * 60)

    with driver.session() as session:
        # Get all players with season stats
        result = session.run("""
            MATCH (p:Player)-[:HAS_SEASON_STATS]->(s:SeasonStats)
            WHERE p.position IN ['QB', 'RB', 'WR', 'TE']
              AND s.games_played >= 5
            WITH p, s
            ORDER BY s.season ASC
            WITH p, collect({
                season: s.season,
                ppg: CASE WHEN s.games_played > 0
                     THEN (s.fantasy_points + s.receptions * 0.5) / s.games_played
                     ELSE 0 END,
                games: s.games_played
            }) as seasons
            WHERE size(seasons) >= 2
            RETURN p.gsis_id as gsis_id, seasons
        """)

        updates = []
        for record in result:
            gsis_id = record['gsis_id']
            seasons = record['seasons']

            if len(seasons) < 2:
                continue

            # Calculate trend using linear regression
            x = np.array([i for i in range(len(seasons))])
            y = np.array([s['ppg'] for s in seasons])

            # Simple linear regression
            if len(x) >= 2 and np.std(y) > 0:
                slope = np.polyfit(x, y, 1)[0]
            else:
                slope = 0

            # 3-year trend (last 3 seasons)
            recent = seasons[-3:] if len(seasons) >= 3 else seasons
            recent_ppg = [s['ppg'] for s in recent]

            if len(recent_ppg) >= 2:
                trend_3yr = recent_ppg[-1] - recent_ppg[0]
            else:
                trend_3yr = 0

            # Trajectory classification
            if slope > 1.0:
                trajectory = "RISING"
            elif slope < -1.0:
                trajectory = "DECLINING"
            else:
                trajectory = "STABLE"

            updates.append({
                'gsis_id': gsis_id,
                'slope': float(slope),
                'trend_3yr': float(trend_3yr),
                'trajectory': trajectory
            })

        # Batch update
        session.run("""
            UNWIND $updates as u
            MATCH (p:Player {gsis_id: u.gsis_id})
            SET p.ppg_trend_slope = u.slope,
                p.ppg_trend_3yr = u.trend_3yr,
                p.ppg_trajectory = u.trajectory
        """, {'updates': updates})

        print(f"   ✅ Updated {len(updates)} players with PPG trends")

        # Distribution
        result = session.run("""
            MATCH (p:Player)
            WHERE p.ppg_trajectory IS NOT NULL
            RETURN p.ppg_trajectory as trajectory, count(*) as count
            ORDER BY count DESC
        """)

        print("\n   Trajectory Distribution:")
        for r in result:
            print(f"   {r['trajectory']}: {r['count']}")


def calculate_consistency_metrics(driver):
    """
    Calculate production consistency metrics.
    Updates Player nodes with:
    - ppg_stddev (standard deviation of weekly points)
    - ppg_cv (coefficient of variation - stddev/mean)
    - boom_rate (% of games with 20+ points)
    - bust_rate (% of games with <5 points)
    - floor_ppg (10th percentile weekly score)
    - ceiling_ppg (90th percentile weekly score)
    """
    print("\n" + "=" * 60)
    print("3. CALCULATING PRODUCTION CONSISTENCY METRICS")
    print("=" * 60)

    with driver.session() as session:
        # Get weekly stats for each player
        result = session.run("""
            MATCH (p:Player)-[:HAS_WEEKLY_STATS]->(w:WeeklyStats)
            WHERE p.position IN ['QB', 'RB', 'WR', 'TE']
              AND w.season >= 2022  // Focus on recent seasons
            WITH p, collect(w.fantasy_points + coalesce(w.receptions, 0) * 0.5) as weekly_pts
            WHERE size(weekly_pts) >= 10
            RETURN p.gsis_id as gsis_id, weekly_pts
        """)

        updates = []
        for record in result:
            gsis_id = record['gsis_id']
            pts = np.array([p for p in record['weekly_pts'] if p is not None and p >= 0])

            if len(pts) < 10:
                continue

            mean_pts = np.mean(pts)
            std_pts = np.std(pts)

            # Coefficient of variation (lower = more consistent)
            cv = (std_pts / mean_pts * 100) if mean_pts > 0 else 0

            # Boom/Bust rates (using half PPR thresholds)
            boom_threshold = 20  # Great week
            bust_threshold = 5   # Bad week

            boom_rate = np.sum(pts >= boom_threshold) / len(pts) * 100
            bust_rate = np.sum(pts < bust_threshold) / len(pts) * 100

            # Floor/Ceiling (10th/90th percentile)
            floor_ppg = np.percentile(pts, 10)
            ceiling_ppg = np.percentile(pts, 90)

            updates.append({
                'gsis_id': gsis_id,
                'stddev': float(std_pts),
                'cv': float(cv),
                'boom_rate': float(boom_rate),
                'bust_rate': float(bust_rate),
                'floor': float(floor_ppg),
                'ceiling': float(ceiling_ppg)
            })

        # Batch update
        session.run("""
            UNWIND $updates as u
            MATCH (p:Player {gsis_id: u.gsis_id})
            SET p.ppg_stddev = u.stddev,
                p.ppg_cv = u.cv,
                p.boom_rate = u.boom_rate,
                p.bust_rate = u.bust_rate,
                p.floor_ppg = u.floor,
                p.ceiling_ppg = u.ceiling
        """, {'updates': updates})

        print(f"   ✅ Updated {len(updates)} players with consistency metrics")

        # Sample high-floor players
        result = session.run("""
            MATCH (p:Player)
            WHERE p.floor_ppg IS NOT NULL AND p.ktc_value > 3000
            RETURN p.name, p.position, p.floor_ppg, p.ceiling_ppg,
                   p.boom_rate, p.bust_rate, p.ppg_cv
            ORDER BY p.floor_ppg DESC
            LIMIT 5
        """)

        print("\n   Highest Floor Players:")
        print("   " + "-" * 70)
        for r in result:
            print(f"   {r['p.name'][:18]:<18} ({r['p.position']}) | "
                  f"Floor: {r['p.floor_ppg']:.1f} | Ceil: {r['p.ceiling_ppg']:.1f} | "
                  f"Boom: {r['p.boom_rate']:.0f}% | Bust: {r['p.bust_rate']:.0f}%")


def calculate_peak_production(driver):
    """
    Calculate peak season production stats.
    Updates Player nodes with:
    - peak_ppg (best season PPG - half PPR)
    - peak_season (year of best season)
    - peak_fpts (total points in best season)
    - years_from_peak_season (how long ago was peak)
    - peak_vs_current (peak PPG / current PPG ratio)
    """
    print("\n" + "=" * 60)
    print("4. CALCULATING PEAK SEASON PRODUCTION")
    print("=" * 60)

    current_year = 2024  # Most recent complete season

    with driver.session() as session:
        # Find peak season for each player
        result = session.run("""
            MATCH (p:Player)-[:HAS_SEASON_STATS]->(s:SeasonStats)
            WHERE p.position IN ['QB', 'RB', 'WR', 'TE']
              AND s.games_played >= 8
            WITH p, s,
                 (s.fantasy_points + coalesce(s.receptions, 0) * 0.5) / s.games_played as ppg
            ORDER BY ppg DESC
            WITH p, collect({season: s.season, ppg: ppg, fpts: s.fantasy_points + coalesce(s.receptions, 0) * 0.5})[0] as peak
            RETURN p.gsis_id as gsis_id, peak.season as peak_season,
                   peak.ppg as peak_ppg, peak.fpts as peak_fpts
        """)

        updates = []
        for record in result:
            gsis_id = record['gsis_id']
            peak_season = record['peak_season']
            peak_ppg = record['peak_ppg']
            peak_fpts = record['peak_fpts']

            years_from_peak = current_year - peak_season if peak_season else 0

            updates.append({
                'gsis_id': gsis_id,
                'peak_season': int(peak_season) if peak_season else None,
                'peak_ppg': float(peak_ppg) if peak_ppg else 0,
                'peak_fpts': float(peak_fpts) if peak_fpts else 0,
                'years_from_peak': int(years_from_peak)
            })

        # Batch update
        session.run("""
            UNWIND $updates as u
            MATCH (p:Player {gsis_id: u.gsis_id})
            SET p.peak_season = u.peak_season,
                p.peak_ppg = u.peak_ppg,
                p.peak_fpts = u.peak_fpts,
                p.years_from_peak_season = u.years_from_peak
        """, {'updates': updates})

        print(f"   ✅ Updated {len(updates)} players with peak production stats")

        # Calculate peak vs current ratio
        session.run("""
            MATCH (p:Player)
            WHERE p.peak_ppg IS NOT NULL AND p.peak_ppg > 0
              AND p.career_ppg_half IS NOT NULL AND p.career_ppg_half > 0
            SET p.peak_vs_career = p.peak_ppg / p.career_ppg_half
        """)

        # Sample players past their peak
        result = session.run("""
            MATCH (p:Player)
            WHERE p.peak_season IS NOT NULL
              AND p.ktc_value > 3000
              AND p.years_from_peak_season > 0
            RETURN p.name, p.position, p.age, p.peak_season,
                   p.peak_ppg, p.years_from_peak_season, p.ktc_value
            ORDER BY p.peak_ppg DESC
            LIMIT 5
        """)

        print("\n   Players With Elite Peak Seasons:")
        print("   " + "-" * 70)
        for r in result:
            print(f"   {r['p.name'][:18]:<18} ({r['p.position']}) Age {r['p.age']:.0f} | "
                  f"Peak: {r['p.peak_ppg']:.1f} PPG in {r['p.peak_season']} | "
                  f"{r['p.years_from_peak_season']}yr ago")


def verify_features(driver):
    """Verify all new features were calculated correctly."""
    print("\n" + "=" * 60)
    print("5. FEATURE VERIFICATION")
    print("=" * 60)

    with driver.session() as session:
        # Count features
        result = session.run("""
            MATCH (p:Player)
            WHERE p.position IN ['QB', 'RB', 'WR', 'TE'] AND p.ktc_value > 1000
            RETURN
                count(p.career_fpts_std) as career_std,
                count(p.career_fpts_half) as career_half,
                count(p.career_fpts_ppr) as career_ppr,
                count(p.ppg_trend_slope) as trends,
                count(p.ppg_stddev) as consistency,
                count(p.peak_ppg) as peak,
                count(p) as total
        """)
        r = result.single()

        print(f"\n   Feature Coverage (players with KTC > 1000):")
        print(f"   " + "-" * 50)
        print(f"   Career Totals (Std):    {r['career_std']:>5} / {r['total']}")
        print(f"   Career Totals (Half):   {r['career_half']:>5} / {r['total']}")
        print(f"   Career Totals (PPR):    {r['career_ppr']:>5} / {r['total']}")
        print(f"   PPG Trends:             {r['trends']:>5} / {r['total']}")
        print(f"   Consistency Metrics:    {r['consistency']:>5} / {r['total']}")
        print(f"   Peak Production:        {r['peak']:>5} / {r['total']}")

        # List all new features
        print("\n   New Features Added:")
        features = [
            'career_fpts_std', 'career_fpts_half', 'career_fpts_ppr',
            'career_ppg_std', 'career_ppg_half', 'career_ppg_ppr',
            'ppg_trend_slope', 'ppg_trend_3yr', 'ppg_trajectory',
            'ppg_stddev', 'ppg_cv', 'boom_rate', 'bust_rate', 'floor_ppg', 'ceiling_ppg',
            'peak_season', 'peak_ppg', 'peak_fpts', 'years_from_peak_season', 'peak_vs_career'
        ]
        for i, f in enumerate(features, 1):
            print(f"   {i:>2}. {f}")


def main():
    """Main entry point."""
    print("=" * 60)
    print("FANTASY PRODUCTION FEATURE ENGINEERING")
    print(f"Started: {datetime.now()}")
    print("=" * 60)

    driver = get_driver()

    try:
        # Calculate all features
        calculate_career_totals(driver)
        calculate_ppg_trends(driver)
        calculate_consistency_metrics(driver)
        calculate_peak_production(driver)
        verify_features(driver)

        print("\n" + "=" * 60)
        print("FEATURE ENGINEERING COMPLETE")
        print("=" * 60)
        print("\n✅ Ready to retrain ML model with new features!")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        driver.close()


if __name__ == "__main__":
    main()
