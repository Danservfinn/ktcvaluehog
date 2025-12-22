"""Neo4j HTTP Transaction API client for Railway deployment."""

import httpx
from typing import Any
from functools import lru_cache

from .config import get_settings


class Neo4jHTTPClient:
    """HTTP client for Neo4j Transaction API (Railway deployment)."""

    def __init__(self):
        settings = get_settings()
        self.url = settings.neo4j_url
        self.auth = (settings.neo4j_user, settings.neo4j_password)
        self.headers = {"Content-Type": "application/json"}

    async def execute(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict]:
        """Execute a Cypher query and return results."""
        statement = {"statement": query}
        if parameters:
            statement["parameters"] = parameters

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.url,
                json={"statements": [statement]},
                auth=self.auth,
                headers=self.headers,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

            # Check for Neo4j errors
            if data.get("errors"):
                error = data["errors"][0]
                raise Exception(f"Neo4j error: {error.get('message', 'Unknown error')}")

            # Parse results into list of dicts
            results = []
            if data.get("results") and data["results"][0].get("data"):
                columns = data["results"][0]["columns"]
                for row_data in data["results"][0]["data"]:
                    row = row_data["row"]
                    results.append(dict(zip(columns, row)))

            return results

    async def execute_many(self, queries: list[tuple[str, dict | None]]) -> list[list[dict]]:
        """Execute multiple queries in a single transaction."""
        statements = []
        for query, params in queries:
            statement = {"statement": query}
            if params:
                statement["parameters"] = params
            statements.append(statement)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.url,
                json={"statements": statements},
                auth=self.auth,
                headers=self.headers,
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()

            if data.get("errors"):
                error = data["errors"][0]
                raise Exception(f"Neo4j error: {error.get('message', 'Unknown error')}")

            all_results = []
            for result in data.get("results", []):
                results = []
                if result.get("data"):
                    columns = result["columns"]
                    for row_data in result["data"]:
                        row = row_data["row"]
                        results.append(dict(zip(columns, row)))
                all_results.append(results)

            return all_results


# Singleton instance
_db_client: Neo4jHTTPClient | None = None


def get_db() -> Neo4jHTTPClient:
    """Get the database client singleton."""
    global _db_client
    if _db_client is None:
        _db_client = Neo4jHTTPClient()
    return _db_client


# Cache for data freshness timestamp (refreshed every 5 minutes)
_data_freshness_cache: dict[str, str | None] = {"timestamp": None, "fetched_at": None}


async def get_data_freshness() -> str | None:
    """Get the latest KTC data update timestamp (cached)."""
    import time

    # Return cached value if less than 5 minutes old
    if _data_freshness_cache["fetched_at"]:
        age = time.time() - float(_data_freshness_cache["fetched_at"])
        if age < 300:  # 5 minutes
            return _data_freshness_cache["timestamp"]

    try:
        db = get_db()
        result = await db.execute("""
            MATCH (k:KTCSnapshot)
            RETURN max(k.date) as latest_date
        """)
        if result and result[0].get("latest_date"):
            # Convert date to ISO timestamp
            date_str = result[0]["latest_date"]
            timestamp = f"{date_str}T12:00:00Z"  # Noon UTC as approximate
            _data_freshness_cache["timestamp"] = timestamp
            _data_freshness_cache["fetched_at"] = str(time.time())
            return timestamp
    except Exception:
        pass

    return None
