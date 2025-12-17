#!/usr/bin/env python3
"""
Dynasty Edge - Neo4j Initial Setup Script
Loads your existing CSV data into Neo4j graph database.

Prerequisites:
1. Install Neo4j Desktop: https://neo4j.com/download/
2. Create a new database and start it
3. pip install neo4j pandas python-dotenv

Usage:
    python setup_neo4j.py
"""

import os
import pandas as pd
from neo4j import GraphDatabase
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# Configuration - Update these or use .env file
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

# Path to your CSV files
DATA_PATH = os.getenv("DATA_PATH", "./data")


class DynastyGraphLoader:
    """Loads dynasty fantasy football data into Neo4j."""
    
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        print(f"✅ Connected to Neo4j at {uri}")
    
    def close(self):
        self.driver.close()
    
    def clear_database(self):
        """Clear all nodes and relationships (use with caution!)."""
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            print("🗑️  Cleared existing data")
    
    def create_constraints(self):
        """Create uniqueness constraints for node types."""
        constraints = [
            "CREATE CONSTRAINT player_id IF NOT EXISTS FOR (p:Player) REQUIRE p.player_id IS UNIQUE",
            "CREATE CONSTRAINT player_name IF NOT EXISTS FOR (p:Player) REQUIRE p.name IS UNIQUE",
            "CREATE CONSTRAINT team_id IF NOT EXISTS FOR (t:Team) REQUIRE t.team_id IS UNIQUE",
            "CREATE CONSTRAINT fantasy_team IF NOT EXISTS FOR (f:FantasyTeam) REQUIRE f.roster_id IS UNIQUE",
            "CREATE CONSTRAINT pick_id IF NOT EXISTS FOR (d:DraftPick) REQUIRE d.pick_id IS UNIQUE",
        ]
        with self.driver.session() as session:
            for constraint in constraints:
                try:
                    session.run(constraint)
                except Exception as e:
                    pass  # Constraint may already exist
        print("✅ Created database constraints")
    
    def load_ktc_players(self, ktc_path: str):
        """Load players from KTC CSV with their valuations."""
        df = pd.read_csv(ktc_path)
        df.columns = ['player_name', 'position_rank', 'position', 'team', 'value', 
                      'age', 'rookie', 'oneqb_rank', 'oneqb_value', 'rdraft_rank', 'rdraft_value']
        
        # Filter to actual players (not draft picks)
        players = df[df['position'].isin(['QB', 'RB', 'WR', 'TE'])].copy()
        
        with self.driver.session() as session:
            count = 0
            for _, row in players.iterrows():
                if pd.isna(row['player_name']):
                    continue
                
                # Generate a player_id from name (you'd use Sleeper IDs in production)
                player_id = row['player_name'].lower().replace(' ', '_').replace('.', '').replace("'", "")
                
                session.run("""
                    MERGE (p:Player {name: $name})
                    SET p.player_id = $player_id,
                        p.position = $position,
                        p.position_rank = $position_rank,
                        p.team = $team,
                        p.ktc_value = $ktc_value,
                        p.age = $age,
                        p.rookie = $rookie,
                        p.ktc_updated = datetime(),
                        p.oneqb_value = $oneqb_value
                """, {
                    'name': row['player_name'],
                    'player_id': player_id,
                    'position': row['position'],
                    'position_rank': row['position_rank'],
                    'team': row['team'] if pd.notna(row['team']) else 'FA',
                    'ktc_value': int(row['value']) if pd.notna(row['value']) else 0,
                    'age': float(row['age']) if pd.notna(row['age']) else None,
                    'rookie': row['rookie'] == 'Yes',
                    'oneqb_value': int(row['oneqb_value']) if pd.notna(row['oneqb_value']) else 0
                })
                count += 1
            
            print(f"✅ Loaded {count} players from KTC data")
    
    def load_draft_picks(self, ktc_path: str):
        """Load draft pick valuations as DraftPick nodes."""
        df = pd.read_csv(ktc_path)
        df.columns = ['player_name', 'position_rank', 'position', 'team', 'value', 
                      'age', 'rookie', 'oneqb_rank', 'oneqb_value', 'rdraft_rank', 'rdraft_value']
        
        # Filter to picks only (position = PI)
        picks = df[df['position'] == 'PI'].copy()
        
        with self.driver.session() as session:
            count = 0
            for _, row in picks.iterrows():
                pick_name = str(row['player_name'])
                
                # Parse pick info from name (e.g., "2026 Early 1st")
                parts = pick_name.split()
                if len(parts) >= 3:
                    year = int(parts[0])
                    slot = parts[1]  # Early, Mid, Late
                    round_num = int(parts[2].replace('st', '').replace('nd', '').replace('rd', '').replace('th', ''))
                    
                    pick_id = f"{year}_{slot}_{round_num}"
                    
                    session.run("""
                        MERGE (d:DraftPick {pick_id: $pick_id})
                        SET d.name = $name,
                            d.season = $season,
                            d.round = $round,
                            d.projected_slot = $slot,
                            d.ktc_value = $ktc_value,
                            d.ktc_updated = datetime()
                    """, {
                        'pick_id': pick_id,
                        'name': pick_name,
                        'season': year,
                        'round': round_num,
                        'slot': slot,
                        'ktc_value': int(row['value']) if pd.notna(row['value']) else 0
                    })
                    count += 1
            
            print(f"✅ Loaded {count} draft picks")
    
    def load_nfl_teams(self):
        """Create NFL team nodes with basic info."""
        teams = [
            ('ARI', 'Arizona Cardinals', 'NFC', 'West'),
            ('ATL', 'Atlanta Falcons', 'NFC', 'South'),
            ('BAL', 'Baltimore Ravens', 'AFC', 'North'),
            ('BUF', 'Buffalo Bills', 'AFC', 'East'),
            ('CAR', 'Carolina Panthers', 'NFC', 'South'),
            ('CHI', 'Chicago Bears', 'NFC', 'North'),
            ('CIN', 'Cincinnati Bengals', 'AFC', 'North'),
            ('CLE', 'Cleveland Browns', 'AFC', 'North'),
            ('DAL', 'Dallas Cowboys', 'NFC', 'East'),
            ('DEN', 'Denver Broncos', 'AFC', 'West'),
            ('DET', 'Detroit Lions', 'NFC', 'North'),
            ('GBP', 'Green Bay Packers', 'NFC', 'North'),
            ('HOU', 'Houston Texans', 'AFC', 'South'),
            ('IND', 'Indianapolis Colts', 'AFC', 'South'),
            ('JAC', 'Jacksonville Jaguars', 'AFC', 'South'),
            ('KCC', 'Kansas City Chiefs', 'AFC', 'West'),
            ('LAC', 'Los Angeles Chargers', 'AFC', 'West'),
            ('LAR', 'Los Angeles Rams', 'NFC', 'West'),
            ('LVR', 'Las Vegas Raiders', 'AFC', 'West'),
            ('MIA', 'Miami Dolphins', 'AFC', 'East'),
            ('MIN', 'Minnesota Vikings', 'NFC', 'North'),
            ('NEP', 'New England Patriots', 'AFC', 'East'),
            ('NOS', 'New Orleans Saints', 'NFC', 'South'),
            ('NYG', 'New York Giants', 'NFC', 'East'),
            ('NYJ', 'New York Jets', 'AFC', 'East'),
            ('PHI', 'Philadelphia Eagles', 'NFC', 'East'),
            ('PIT', 'Pittsburgh Steelers', 'AFC', 'North'),
            ('SEA', 'Seattle Seahawks', 'NFC', 'West'),
            ('SFO', 'San Francisco 49ers', 'NFC', 'West'),
            ('TBB', 'Tampa Bay Buccaneers', 'NFC', 'South'),
            ('TEN', 'Tennessee Titans', 'AFC', 'South'),
            ('WAS', 'Washington Commanders', 'NFC', 'East'),
        ]
        
        with self.driver.session() as session:
            for team_id, name, conference, division in teams:
                session.run("""
                    MERGE (t:Team {team_id: $team_id})
                    SET t.name = $name,
                        t.conference = $conference,
                        t.division = $division
                """, {
                    'team_id': team_id,
                    'name': name,
                    'conference': conference,
                    'division': division
                })
            
            print(f"✅ Loaded {len(teams)} NFL teams")
    
    def create_plays_for_relationships(self):
        """Create PLAYS_FOR relationships between players and teams."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (p:Player), (t:Team)
                WHERE p.team = t.team_id
                MERGE (p)-[r:PLAYS_FOR]->(t)
                RETURN count(r) as count
            """)
            count = result.single()['count']
            print(f"✅ Created {count} PLAYS_FOR relationships")
    
    def create_targets_from_relationships(self):
        """Create TARGETS_FROM relationships (WR/TE -> QB on same team)."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (receiver:Player)-[:PLAYS_FOR]->(t:Team)<-[:PLAYS_FOR]-(qb:Player)
                WHERE receiver.position IN ['WR', 'TE']
                  AND qb.position = 'QB'
                  AND qb.ktc_value > 2000  // Only established QBs
                MERGE (receiver)-[r:TARGETS_FROM]->(qb)
                SET r.team = t.team_id,
                    r.created = datetime()
                RETURN count(r) as count
            """)
            count = result.single()['count']
            print(f"✅ Created {count} TARGETS_FROM relationships")
    
    def create_competes_with_relationships(self):
        """Create COMPETES_WITH relationships for same-position players on same team."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (p1:Player)-[:PLAYS_FOR]->(t:Team)<-[:PLAYS_FOR]-(p2:Player)
                WHERE p1.position = p2.position
                  AND p1.name < p2.name  // Avoid duplicates
                  AND p1.ktc_value > 1000
                  AND p2.ktc_value > 1000
                MERGE (p1)-[r:COMPETES_WITH]->(p2)
                SET r.team = t.team_id
                RETURN count(r) as count
            """)
            count = result.single()['count']
            print(f"✅ Created {count} COMPETES_WITH relationships")
    
    def load_fantasy_teams(self, rosters_path: str):
        """Load fantasy league teams and ROSTERED_BY relationships."""
        df = pd.read_csv(rosters_path)
        
        with self.driver.session() as session:
            for _, row in df.iterrows():
                # Create FantasyTeam node
                session.run("""
                    MERGE (f:FantasyTeam {roster_id: $roster_id})
                    SET f.owner = $owner,
                        f.team_name = $team_name,
                        f.wins = $wins,
                        f.losses = $losses,
                        f.fpts = $fpts,
                        f.fpts_against = $fpts_against
                """, {
                    'roster_id': row['roster_id'],
                    'owner': row['display_name'],
                    'team_name': row['team_name'] if pd.notna(row['team_name']) else row['display_name'],
                    'wins': row['wins'],
                    'losses': row['losses'],
                    'fpts': row['fpts'],
                    'fpts_against': row['fpts_against']
                })
                
                # Parse player list and create ROSTERED_BY relationships
                if pd.notna(row['players']):
                    players = [p.strip() for p in str(row['players']).split(',')]
                    for player_name in players:
                        session.run("""
                            MATCH (p:Player {name: $player_name})
                            MATCH (f:FantasyTeam {roster_id: $roster_id})
                            MERGE (p)-[:ROSTERED_BY]->(f)
                        """, {
                            'player_name': player_name,
                            'roster_id': row['roster_id']
                        })
            
            print(f"✅ Loaded {len(df)} fantasy teams with roster relationships")
    
    def load_traded_picks(self, traded_picks_path: str):
        """Load traded picks and ownership relationships."""
        df = pd.read_csv(traded_picks_path)
        
        with self.driver.session() as session:
            for _, row in df.iterrows():
                pick_id = f"{row['season']}_r{row['round']}_{row['original_owner']}"
                
                # Create or match the pick
                session.run("""
                    MERGE (d:DraftPick {pick_id: $pick_id})
                    SET d.season = $season,
                        d.round = $round,
                        d.original_owner = $original_owner
                    
                    WITH d
                    MATCH (current:FantasyTeam)
                    WHERE current.owner = $current_owner
                    MERGE (current)-[:OWNS]->(d)
                    
                    WITH d
                    MATCH (original:FantasyTeam)
                    WHERE original.owner = $original_owner
                    MERGE (d)-[:ORIGINALLY_OWNED_BY]->(original)
                """, {
                    'pick_id': pick_id,
                    'season': row['season'],
                    'round': row['round'],
                    'original_owner': row['original_owner'],
                    'current_owner': row['current_owner']
                })
            
            print(f"✅ Loaded {len(df)} traded picks")
    
    def calculate_edge_values(self):
        """Calculate edge values for all players based on graph relationships."""
        with self.driver.session() as session:
            # Calculate edge values using graph features
            session.run("""
                MATCH (p:Player)
                WHERE p.ktc_value > 0 AND p.age IS NOT NULL
                
                // Calculate years remaining
                WITH p, 
                     CASE p.position
                         WHEN 'QB' THEN 38 - p.age
                         WHEN 'RB' THEN 30 - p.age
                         WHEN 'WR' THEN 33 - p.age
                         WHEN 'TE' THEN 34 - p.age
                         ELSE 32 - p.age
                     END as years_remaining
                
                // Calculate age factor
                WITH p, years_remaining,
                     CASE 
                         WHEN p.position = 'RB' AND p.age >= 27 THEN 0.7
                         WHEN p.position = 'RB' AND p.age >= 26 THEN 0.85
                         WHEN p.position = 'WR' AND p.age >= 30 THEN 0.75
                         WHEN p.position = 'QB' AND p.age >= 34 THEN 0.8
                         ELSE 1.0
                     END as age_factor
                
                // Check for young QB (WR/TE boost)
                OPTIONAL MATCH (p)-[:TARGETS_FROM]->(qb:Player)
                WITH p, years_remaining, age_factor,
                     CASE 
                         WHEN qb IS NOT NULL AND qb.age < 26 THEN 1.08
                         WHEN qb IS NOT NULL AND qb.age > 32 THEN 0.92
                         ELSE 1.0
                     END as qb_factor
                
                // Calculate edge value
                SET p.years_remaining = CASE WHEN years_remaining > 0 THEN years_remaining ELSE 1 END,
                    p.edge_value = toInteger(p.ktc_value * age_factor * qb_factor),
                    p.edge_score = ((p.ktc_value - (p.ktc_value * age_factor * qb_factor)) / p.ktc_value) * 100,
                    p.edge_signal = CASE 
                        WHEN ((p.ktc_value - (p.ktc_value * age_factor * qb_factor)) / p.ktc_value) * 100 > 15 THEN 'SELL'
                        WHEN ((p.ktc_value - (p.ktc_value * age_factor * qb_factor)) / p.ktc_value) * 100 < -15 THEN 'BUY'
                        ELSE 'HOLD'
                    END,
                    p.edge_calculated = datetime()
            """)
            
            # Count signals
            result = session.run("""
                MATCH (p:Player)
                WHERE p.edge_signal IS NOT NULL
                RETURN p.edge_signal as signal, count(*) as count
            """)
            
            print("\n📊 Edge Value Calculation Complete:")
            for record in result:
                print(f"   {record['signal']}: {record['count']} players")


def main():
    """Main execution flow."""
    print("\n" + "=" * 60)
    print("🏈 DYNASTY EDGE - Neo4j Setup")
    print("=" * 60 + "\n")
    
    # Initialize loader
    loader = DynastyGraphLoader(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    
    try:
        # Optional: Clear existing data
        response = input("Clear existing data? (y/N): ")
        if response.lower() == 'y':
            loader.clear_database()
        
        # Create constraints
        loader.create_constraints()
        
        # Load base data
        ktc_path = os.path.join(DATA_PATH, "ktc_lucid_losers.csv")
        rosters_path = os.path.join(DATA_PATH, "rosters_standings.csv")
        traded_picks_path = os.path.join(DATA_PATH, "traded_picks.csv")
        
        loader.load_nfl_teams()
        loader.load_ktc_players(ktc_path)
        loader.load_draft_picks(ktc_path)
        
        # Create relationships
        loader.create_plays_for_relationships()
        loader.create_targets_from_relationships()
        loader.create_competes_with_relationships()
        
        # Load fantasy league data
        loader.load_fantasy_teams(rosters_path)
        loader.load_traded_picks(traded_picks_path)
        
        # Calculate edge values
        loader.calculate_edge_values()
        
        print("\n" + "=" * 60)
        print("✅ Setup Complete!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Open Neo4j Browser at http://localhost:7474")
        print("2. Try these queries:")
        print("   MATCH (p:Player) RETURN p LIMIT 25")
        print("   MATCH (p)-[r:TARGETS_FROM]->(qb) RETURN p.name, qb.name LIMIT 10")
        print("   MATCH (p:Player) WHERE p.edge_signal = 'BUY' RETURN p.name, p.edge_score ORDER BY p.edge_score LIMIT 10")
        
    finally:
        loader.close()


if __name__ == "__main__":
    main()
