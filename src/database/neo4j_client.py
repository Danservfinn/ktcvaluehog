"""Neo4j client for Dynasty Edge."""

from neo4j import GraphDatabase
from typing import List, Dict, Any, Optional
import pandas as pd

from ..config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD


class Neo4jClient:
    """Connection manager for Neo4j database."""

    def __init__(self, uri: str = None, user: str = None, password: str = None):
        self.uri = uri or NEO4J_URI
        self.user = user or NEO4J_USER
        self.password = password or NEO4J_PASSWORD
        self._driver = None

    @property
    def driver(self):
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password)
            )
        return self._driver

    def close(self):
        if self._driver:
            self._driver.close()
            self._driver = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def run_query(self, query: str, parameters: dict = None) -> List[Dict]:
        """Execute a Cypher query and return results as list of dicts."""
        with self.driver.session() as session:
            result = session.run(query, parameters or {})
            return [dict(record) for record in result]

    def run_write(self, query: str, parameters: dict = None) -> Any:
        """Execute a write query (MERGE, CREATE, SET, DELETE)."""
        with self.driver.session() as session:
            result = session.run(query, parameters or {})
            return result.consume()

    def run_batch(self, query: str, batch_data: List[Dict], batch_size: int = 1000) -> int:
        """Execute a query in batches for large data loads."""
        total_processed = 0

        with self.driver.session() as session:
            for i in range(0, len(batch_data), batch_size):
                batch = batch_data[i:i + batch_size]
                session.run(query, {'batch': batch})
                total_processed += len(batch)

        return total_processed

    def to_dataframe(self, query: str, parameters: dict = None) -> pd.DataFrame:
        """Execute query and return results as DataFrame."""
        results = self.run_query(query, parameters)
        return pd.DataFrame(results)

    def verify_connection(self) -> bool:
        """Verify database connection is working."""
        try:
            self.run_query("RETURN 1 as test")
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    def get_node_count(self, label: str = None) -> int:
        """Get count of nodes with optional label filter."""
        if label:
            query = f"MATCH (n:{label}) RETURN count(n) as count"
        else:
            query = "MATCH (n) RETURN count(n) as count"
        result = self.run_query(query)
        return result[0]['count'] if result else 0

    def get_relationship_count(self, rel_type: str = None) -> int:
        """Get count of relationships with optional type filter."""
        if rel_type:
            query = f"MATCH ()-[r:{rel_type}]->() RETURN count(r) as count"
        else:
            query = "MATCH ()-[r]->() RETURN count(r) as count"
        result = self.run_query(query)
        return result[0]['count'] if result else 0

    def get_db_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        # Get node labels and counts
        labels_query = """
            CALL db.labels() YIELD label
            CALL {
                WITH label
                MATCH (n) WHERE label IN labels(n)
                RETURN count(n) as count
            }
            RETURN label, count
            ORDER BY count DESC
        """

        # Get relationship types and counts
        rels_query = """
            CALL db.relationshipTypes() YIELD relationshipType
            CALL {
                WITH relationshipType
                MATCH ()-[r]->()
                WHERE type(r) = relationshipType
                RETURN count(r) as count
            }
            RETURN relationshipType, count
            ORDER BY count DESC
        """

        try:
            labels = self.run_query(labels_query)
            rels = self.run_query(rels_query)

            return {
                'nodes': {r['label']: r['count'] for r in labels},
                'relationships': {r['relationshipType']: r['count'] for r in rels},
                'total_nodes': sum(r['count'] for r in labels),
                'total_relationships': sum(r['count'] for r in rels)
            }
        except Exception as e:
            return {'error': str(e)}
