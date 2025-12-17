"""Player ID resolver for cross-platform mapping.

Maps player IDs between:
- GSIS (NFL official)
- Sleeper
- ESPN
- Yahoo
- PFR (Pro Football Reference)
- PFF (Pro Football Focus)
- Rotowire
- Sportradar
- Fantasy Data
- MFL (MyFantasyLeague)
"""

from typing import Optional, Dict, List
import pandas as pd
from functools import lru_cache


class IDResolver:
    """Resolve player IDs across fantasy football platforms."""

    def __init__(self, playerids_df: pd.DataFrame = None):
        """Initialize with player ID mapping DataFrame.

        Args:
            playerids_df: DataFrame from NFLverseLoader.load_ff_playerids()
                         If not provided, will load lazily on first use.
        """
        self._raw_df = playerids_df
        self._gsis_index = None
        self._sleeper_index = None
        self._name_index = None

    @property
    def mapping(self) -> pd.DataFrame:
        """Lazy load player ID mapping."""
        if self._raw_df is None:
            from .nflverse_loader import NFLverseLoader
            loader = NFLverseLoader()
            self._raw_df = loader.load_ff_playerids()
        return self._raw_df

    @property
    def gsis_index(self) -> pd.DataFrame:
        """Index by GSIS ID for fast lookups."""
        if self._gsis_index is None:
            df = self.mapping[self.mapping['gsis_id'].notna()].copy()
            self._gsis_index = df.set_index('gsis_id')
        return self._gsis_index

    @property
    def sleeper_index(self) -> pd.DataFrame:
        """Index by Sleeper ID for fast lookups."""
        if self._sleeper_index is None:
            df = self.mapping[self.mapping['sleeper_id'].notna()].copy()
            # Convert sleeper_id to string for consistent lookups
            df['sleeper_id'] = df['sleeper_id'].astype(str)
            self._sleeper_index = df.set_index('sleeper_id')
        return self._sleeper_index

    @property
    def name_index(self) -> pd.DataFrame:
        """Index by name for fuzzy lookups."""
        if self._name_index is None:
            df = self.mapping.copy()
            # Create normalized name for matching
            df['name_normalized'] = df['name'].str.lower().str.replace(r'[^a-z\s]', '', regex=True)
            self._name_index = df
        return self._name_index

    # =========================================================================
    # Single ID Conversions
    # =========================================================================

    def gsis_to_sleeper(self, gsis_id: str) -> Optional[str]:
        """Convert GSIS ID to Sleeper ID."""
        try:
            result = self.gsis_index.loc[gsis_id, 'sleeper_id']
            return str(result) if pd.notna(result) else None
        except KeyError:
            return None

    def sleeper_to_gsis(self, sleeper_id: str) -> Optional[str]:
        """Convert Sleeper ID to GSIS ID."""
        try:
            sleeper_id = str(sleeper_id)
            result = self.sleeper_index.loc[sleeper_id, 'gsis_id']
            return str(result) if pd.notna(result) else None
        except KeyError:
            return None

    def gsis_to_espn(self, gsis_id: str) -> Optional[str]:
        """Convert GSIS ID to ESPN ID."""
        try:
            result = self.gsis_index.loc[gsis_id, 'espn_id']
            return str(int(result)) if pd.notna(result) else None
        except (KeyError, ValueError):
            return None

    def gsis_to_pfr(self, gsis_id: str) -> Optional[str]:
        """Convert GSIS ID to PFR ID."""
        try:
            result = self.gsis_index.loc[gsis_id, 'pfr_id']
            return str(result) if pd.notna(result) else None
        except KeyError:
            return None

    def gsis_to_yahoo(self, gsis_id: str) -> Optional[str]:
        """Convert GSIS ID to Yahoo ID."""
        try:
            result = self.gsis_index.loc[gsis_id, 'yahoo_id']
            return str(int(result)) if pd.notna(result) else None
        except (KeyError, ValueError):
            return None

    # =========================================================================
    # Get All IDs for a Player
    # =========================================================================

    def get_all_ids(self, gsis_id: str) -> Dict[str, Optional[str]]:
        """Get all platform IDs for a player by GSIS ID.

        Args:
            gsis_id: NFL GSIS player ID

        Returns:
            Dict with all available platform IDs
        """
        try:
            row = self.gsis_index.loc[gsis_id]
            return {
                'gsis_id': gsis_id,
                'sleeper_id': str(row.get('sleeper_id')) if pd.notna(row.get('sleeper_id')) else None,
                'espn_id': str(int(row.get('espn_id'))) if pd.notna(row.get('espn_id')) else None,
                'yahoo_id': str(int(row.get('yahoo_id'))) if pd.notna(row.get('yahoo_id')) else None,
                'pfr_id': str(row.get('pfr_id')) if pd.notna(row.get('pfr_id')) else None,
                'pff_id': str(int(row.get('pff_id'))) if pd.notna(row.get('pff_id')) else None,
                'rotowire_id': str(int(row.get('rotowire_id'))) if pd.notna(row.get('rotowire_id')) else None,
                'sportradar_id': str(row.get('sportradar_id')) if pd.notna(row.get('sportradar_id')) else None,
                'fantasy_data_id': str(int(row.get('fantasy_data_id'))) if pd.notna(row.get('fantasy_data_id')) else None,
                'mfl_id': str(row.get('mfl_id')) if pd.notna(row.get('mfl_id')) else None,
                'name': row.get('name'),
                'position': row.get('position'),
                'team': row.get('team')
            }
        except KeyError:
            return {'gsis_id': gsis_id, 'error': 'Player not found'}

    def get_player_by_sleeper(self, sleeper_id: str) -> Dict[str, Optional[str]]:
        """Get player info and all IDs by Sleeper ID."""
        gsis_id = self.sleeper_to_gsis(sleeper_id)
        if gsis_id:
            return self.get_all_ids(gsis_id)
        return {'sleeper_id': sleeper_id, 'error': 'Player not found'}

    # =========================================================================
    # Batch Conversions
    # =========================================================================

    def batch_gsis_to_sleeper(self, gsis_ids: List[str]) -> Dict[str, Optional[str]]:
        """Convert multiple GSIS IDs to Sleeper IDs.

        Args:
            gsis_ids: List of GSIS IDs

        Returns:
            Dict mapping GSIS ID to Sleeper ID
        """
        return {gsis_id: self.gsis_to_sleeper(gsis_id) for gsis_id in gsis_ids}

    def batch_sleeper_to_gsis(self, sleeper_ids: List[str]) -> Dict[str, Optional[str]]:
        """Convert multiple Sleeper IDs to GSIS IDs.

        Args:
            sleeper_ids: List of Sleeper IDs

        Returns:
            Dict mapping Sleeper ID to GSIS ID
        """
        return {str(sid): self.sleeper_to_gsis(str(sid)) for sid in sleeper_ids}

    # =========================================================================
    # Name-Based Lookup
    # =========================================================================

    def find_by_name(self, name: str, position: str = None) -> List[Dict]:
        """Find players by name (fuzzy matching).

        Args:
            name: Player name to search for
            position: Optional position filter

        Returns:
            List of matching players with all IDs
        """
        name_norm = name.lower().replace('.', '').replace("'", "")

        df = self.name_index

        # Filter by position if provided
        if position:
            df = df[df['position'] == position]

        # Exact match first
        exact_matches = df[df['name_normalized'] == name_norm]
        if not exact_matches.empty:
            return [self.get_all_ids(row['gsis_id']) for _, row in exact_matches.iterrows() if pd.notna(row.get('gsis_id'))]

        # Partial match
        partial_matches = df[df['name_normalized'].str.contains(name_norm, na=False)]
        if not partial_matches.empty:
            return [self.get_all_ids(row['gsis_id']) for _, row in partial_matches.head(10).iterrows() if pd.notna(row.get('gsis_id'))]

        return []

    # =========================================================================
    # DataFrame Operations
    # =========================================================================

    def add_sleeper_ids(self, df: pd.DataFrame, gsis_col: str = 'gsis_id') -> pd.DataFrame:
        """Add Sleeper IDs to a DataFrame with GSIS IDs.

        Args:
            df: DataFrame with GSIS IDs
            gsis_col: Name of column containing GSIS IDs

        Returns:
            DataFrame with added 'sleeper_id' column
        """
        df = df.copy()
        df['sleeper_id'] = df[gsis_col].apply(self.gsis_to_sleeper)
        return df

    def add_gsis_ids(self, df: pd.DataFrame, sleeper_col: str = 'sleeper_id') -> pd.DataFrame:
        """Add GSIS IDs to a DataFrame with Sleeper IDs.

        Args:
            df: DataFrame with Sleeper IDs
            sleeper_col: Name of column containing Sleeper IDs

        Returns:
            DataFrame with added 'gsis_id' column
        """
        df = df.copy()
        df['gsis_id'] = df[sleeper_col].astype(str).apply(self.sleeper_to_gsis)
        return df

    def merge_with_ids(self, df: pd.DataFrame, on_col: str,
                       id_type: str = 'gsis_id') -> pd.DataFrame:
        """Merge DataFrame with full player ID mapping.

        Args:
            df: DataFrame to merge
            on_col: Column name in df to join on
            id_type: Type of ID in on_col ('gsis_id', 'sleeper_id', etc.)

        Returns:
            DataFrame merged with player ID columns
        """
        id_cols = ['gsis_id', 'sleeper_id', 'espn_id', 'yahoo_id', 'pfr_id', 'name', 'position']
        available_cols = [c for c in id_cols if c in self.mapping.columns]

        return df.merge(
            self.mapping[available_cols],
            left_on=on_col,
            right_on=id_type,
            how='left'
        )

    # =========================================================================
    # Statistics
    # =========================================================================

    def get_coverage_stats(self) -> Dict[str, int]:
        """Get statistics on ID coverage.

        Returns:
            Dict with count of players having each ID type
        """
        id_columns = ['gsis_id', 'sleeper_id', 'espn_id', 'yahoo_id', 'pfr_id',
                      'pff_id', 'rotowire_id', 'sportradar_id', 'fantasy_data_id', 'mfl_id']

        stats = {'total_players': len(self.mapping)}

        for col in id_columns:
            if col in self.mapping.columns:
                stats[f'has_{col}'] = self.mapping[col].notna().sum()

        # Calculate overlap
        has_both_gsis_sleeper = (
            self.mapping['gsis_id'].notna() &
            self.mapping['sleeper_id'].notna()
        ).sum()
        stats['has_gsis_and_sleeper'] = has_both_gsis_sleeper

        return stats


class UnifiedIDResolver:
    """
    Enhanced ID resolver with Neo4j integration and KTC name matching.

    Combines NFLverse ID mapping with Neo4j player database and KTC data
    for comprehensive cross-platform player identification.
    """

    def __init__(self, driver=None):
        """
        Initialize resolver with optional Neo4j driver.

        Args:
            driver: Neo4j driver for database lookups
        """
        self.driver = driver
        self._base_resolver = None
        self._ktc_names = None
        self._neo4j_index = None

    @property
    def base_resolver(self) -> IDResolver:
        """Lazy load base ID resolver."""
        if self._base_resolver is None:
            self._base_resolver = IDResolver()
        return self._base_resolver

    def _build_neo4j_index(self):
        """Build name index from Neo4j database."""
        if self.driver is None or self._neo4j_index is not None:
            return

        with self.driver.session() as session:
            result = session.run("""
                MATCH (p:Player)
                WHERE p.position IN ['QB', 'RB', 'WR', 'TE']
                RETURN p.gsis_id as gsis_id,
                       p.name as name,
                       p.position as position,
                       p.current_team as team,
                       p.ktc_value as ktc_value,
                       p.sleeper_id as sleeper_id
            """)
            self._neo4j_index = pd.DataFrame([dict(r) for r in result])

            if not self._neo4j_index.empty:
                self._neo4j_index['name_normalized'] = (
                    self._neo4j_index['name']
                    .str.lower()
                    .str.replace(r'[^a-z\s]', '', regex=True)
                    .str.strip()
                )

    def resolve_player(self, identifier: str, id_type: str = 'auto') -> Dict:
        """
        Resolve player from any identifier type.

        Args:
            identifier: Player ID or name
            id_type: 'gsis', 'sleeper', 'name', or 'auto' (detect automatically)

        Returns:
            Dict with all player IDs and info
        """
        if id_type == 'auto':
            id_type = self._detect_id_type(identifier)

        if id_type == 'gsis':
            return self.base_resolver.get_all_ids(identifier)
        elif id_type == 'sleeper':
            return self.base_resolver.get_player_by_sleeper(identifier)
        elif id_type == 'name':
            matches = self.find_player_by_name(identifier)
            return matches[0] if matches else {'name': identifier, 'error': 'Not found'}
        else:
            # Try each type
            result = self.base_resolver.get_all_ids(identifier)
            if 'error' not in result:
                return result

            result = self.base_resolver.get_player_by_sleeper(identifier)
            if 'error' not in result:
                return result

            matches = self.find_player_by_name(identifier)
            return matches[0] if matches else {'identifier': identifier, 'error': 'Not found'}

    def _detect_id_type(self, identifier: str) -> str:
        """Detect the type of identifier."""
        if not identifier:
            return 'name'

        # GSIS IDs are formatted like "00-0033873"
        if identifier.startswith('00-'):
            return 'gsis'

        # Sleeper IDs are numeric strings
        if identifier.isdigit() and len(identifier) >= 4:
            return 'sleeper'

        # Otherwise assume it's a name
        return 'name'

    def find_player_by_name(self, name: str, position: str = None) -> List[Dict]:
        """
        Find player by name using multiple data sources.

        Searches NFLverse IDs, Neo4j database, and applies fuzzy matching.
        """
        results = []

        # Try base resolver first
        base_results = self.base_resolver.find_by_name(name, position)
        results.extend(base_results)

        # If we have Neo4j, also search there
        if self.driver:
            self._build_neo4j_index()

            if self._neo4j_index is not None and not self._neo4j_index.empty:
                name_norm = name.lower().replace('.', '').replace("'", "").strip()

                # Search Neo4j index
                df = self._neo4j_index
                if position:
                    df = df[df['position'] == position]

                # Exact match
                exact = df[df['name_normalized'] == name_norm]
                for _, row in exact.iterrows():
                    neo4j_result = {
                        'gsis_id': row.get('gsis_id'),
                        'name': row.get('name'),
                        'position': row.get('position'),
                        'team': row.get('team'),
                        'ktc_value': row.get('ktc_value'),
                        'sleeper_id': row.get('sleeper_id'),
                        'source': 'neo4j'
                    }
                    if neo4j_result not in results:
                        results.append(neo4j_result)

                # Fuzzy match
                partial = df[df['name_normalized'].str.contains(name_norm, na=False)]
                for _, row in partial.head(5).iterrows():
                    neo4j_result = {
                        'gsis_id': row.get('gsis_id'),
                        'name': row.get('name'),
                        'position': row.get('position'),
                        'team': row.get('team'),
                        'ktc_value': row.get('ktc_value'),
                        'sleeper_id': row.get('sleeper_id'),
                        'source': 'neo4j'
                    }
                    if neo4j_result not in results:
                        results.append(neo4j_result)

        # Deduplicate by gsis_id
        seen = set()
        unique_results = []
        for r in results:
            gsis = r.get('gsis_id')
            if gsis and gsis not in seen:
                seen.add(gsis)
                unique_results.append(r)
            elif not gsis:
                unique_results.append(r)

        return unique_results[:10]

    def sync_ids_to_neo4j(self) -> int:
        """
        Sync player IDs from NFLverse to Neo4j database.

        Updates Player nodes with sleeper_id, espn_id, etc.
        """
        if self.driver is None:
            raise ValueError("Neo4j driver required for sync")

        mapping = self.base_resolver.mapping
        count = 0

        with self.driver.session() as session:
            for _, row in mapping.iterrows():
                gsis_id = row.get('gsis_id')
                if pd.isna(gsis_id):
                    continue

                params = {
                    'gsis_id': gsis_id,
                    'sleeper_id': str(row.get('sleeper_id')) if pd.notna(row.get('sleeper_id')) else None,
                    'espn_id': str(int(row.get('espn_id'))) if pd.notna(row.get('espn_id')) else None,
                    'yahoo_id': str(int(row.get('yahoo_id'))) if pd.notna(row.get('yahoo_id')) else None,
                    'pfr_id': str(row.get('pfr_id')) if pd.notna(row.get('pfr_id')) else None,
                }

                result = session.run("""
                    MATCH (p:Player {gsis_id: $gsis_id})
                    SET p.sleeper_id = $sleeper_id,
                        p.espn_id = $espn_id,
                        p.yahoo_id = $yahoo_id,
                        p.pfr_id = $pfr_id
                    RETURN p.name as name
                """, params)

                if result.single():
                    count += 1

        return count

    def match_ktc_to_neo4j(self, ktc_players: List[Dict]) -> Dict[str, str]:
        """
        Match KTC player names to Neo4j GSIS IDs.

        Args:
            ktc_players: List of KTC player dicts with 'name' and 'position'

        Returns:
            Dict mapping KTC names to GSIS IDs
        """
        matches = {}

        for player in ktc_players:
            name = player.get('name', '')
            position = player.get('position')

            results = self.find_player_by_name(name, position)
            if results:
                matches[name] = results[0].get('gsis_id')
            else:
                matches[name] = None

        return matches
