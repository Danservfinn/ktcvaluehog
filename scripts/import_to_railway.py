#!/usr/bin/env python3
"""
Import Neo4j data to Railway production via HTTP Transaction API.
Uses MERGE statements (idempotent) - safe to re-run for resume.
"""

import os
import re
import glob
import time
import requests
from pathlib import Path

# Railway Neo4j HTTP endpoint
NEO4J_URL = "https://sparkling-commitment-production.up.railway.app/db/neo4j/tx/commit"
NEO4J_AUTH = ("neo4j", "dynastyedge2025")

EXPORT_DIR = Path(__file__).parent.parent / "deploy" / "exports"
BATCH_SIZE = 50  # Statements per HTTP request


def get_node_count():
    """Get current node count in production."""
    resp = requests.post(
        NEO4J_URL,
        json={"statements": [{"statement": "MATCH (n) RETURN count(n) as c"}]},
        auth=NEO4J_AUTH,
        headers={"Content-Type": "application/json"},
    )
    if resp.ok:
        data = resp.json()
        if data.get("results") and data["results"][0].get("data"):
            return data["results"][0]["data"][0]["row"][0]
    return 0


def import_cypher_file(filepath: Path, skip_existing: bool = True):
    """Import a single Cypher file via HTTP API."""
    print(f"\n📄 Importing {filepath.name}...")

    with open(filepath, "r") as f:
        content = f.read()

    # Split into individual statements
    statements = []
    for line in content.split("\n"):
        line = line.strip()
        if line and not line.startswith("//"):
            # Remove trailing semicolon
            if line.endswith(";"):
                line = line[:-1]
            if line:
                statements.append(line)

    if not statements:
        print(f"  ⚠️  No statements found")
        return 0

    print(f"  📊 {len(statements)} statements")

    imported = 0
    errors = 0
    start = time.time()

    # Process in batches
    for i in range(0, len(statements), BATCH_SIZE):
        batch = statements[i:i + BATCH_SIZE]
        payload = {"statements": [{"statement": s} for s in batch]}

        try:
            resp = requests.post(
                NEO4J_URL,
                json=payload,
                auth=NEO4J_AUTH,
                headers={"Content-Type": "application/json"},
                timeout=60,
            )

            if resp.ok:
                data = resp.json()
                batch_errors = len(data.get("errors", []))
                errors += batch_errors
                imported += len(batch) - batch_errors
            else:
                errors += len(batch)

        except requests.RequestException as e:
            print(f"  ❌ Request error: {e}")
            errors += len(batch)
            time.sleep(2)  # Back off on error

        # Progress update every 500 statements
        if (i + BATCH_SIZE) % 500 == 0 or i + BATCH_SIZE >= len(statements):
            elapsed = time.time() - start
            rate = imported / elapsed if elapsed > 0 else 0
            pct = min(100, (i + BATCH_SIZE) / len(statements) * 100)
            print(f"  📈 {pct:.1f}% ({imported:,} imported, {errors} errors, {rate:.0f}/sec)")

    elapsed = time.time() - start
    print(f"  ✅ Done in {elapsed:.1f}s ({imported:,} imported, {errors} errors)")
    return imported


def main():
    print("=" * 60)
    print("🚀 Dynasty Edge - Railway Neo4j Import")
    print("=" * 60)

    # Check current state
    current = get_node_count()
    print(f"\n📊 Current production nodes: {current:,}")

    # Get all export files in order
    files = sorted(glob.glob(str(EXPORT_DIR / "*.cypher")))

    # Import order: schema first, then nodes, then relationships
    schema_files = [f for f in files if "schema" in f]
    node_files = [f for f in files if "nodes_" in f]
    rel_files = [f for f in files if "relationship" in f]

    all_files = schema_files + node_files + rel_files

    print(f"\n📁 Found {len(all_files)} export files")

    total_imported = 0

    for filepath in all_files:
        try:
            imported = import_cypher_file(Path(filepath))
            total_imported += imported
        except Exception as e:
            print(f"  ❌ Error: {e}")

    # Final count
    final = get_node_count()
    print("\n" + "=" * 60)
    print(f"✅ Import complete!")
    print(f"   Nodes before: {current:,}")
    print(f"   Nodes after:  {final:,}")
    print(f"   Added:        {final - current:,}")
    print("=" * 60)


if __name__ == "__main__":
    main()
