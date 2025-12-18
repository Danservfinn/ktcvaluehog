"""
Neo4j Database Export Script
============================
Exports the Neo4j database to Cypher statements for migration to Railway.

Usage:
    python scripts/export_neo4j.py                    # Full export
    python scripts/export_neo4j.py --nodes-only       # Export nodes only
    python scripts/export_neo4j.py --sample 1000      # Export sample for testing
    python scripts/export_neo4j.py --label Player     # Export specific label

Output:
    deploy/exports/
    ├── schema.cypher          # Constraints and indexes
    ├── nodes_*.cypher         # Node creation statements (chunked)
    ├── relationships.cypher   # Relationship creation statements
    └── export_manifest.json   # Export metadata
"""

import os
import sys
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.neo4j_client import Neo4jClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

EXPORT_DIR = Path(__file__).parent.parent / "deploy" / "exports"


class Neo4jExporter:
    """Export Neo4j database to Cypher statements."""

    def __init__(self):
        self.client = Neo4jClient()
        self.stats = {
            'nodes_exported': 0,
            'relationships_exported': 0,
            'labels': [],
            'rel_types': [],
        }

    def export_schema(self) -> str:
        """Export indexes and constraints as Cypher."""
        logger.info("Exporting schema...")
        statements = []

        # Get constraints
        try:
            result = self.client.run_query("SHOW CONSTRAINTS")
            for r in result:
                name = r.get('name', '')
                constraint_type = r.get('type', '')
                entity_type = r.get('entityType', '')
                labels = r.get('labelsOrTypes', [])
                properties = r.get('properties', [])

                if constraint_type == 'UNIQUENESS' and labels and properties:
                    label = labels[0]
                    prop = properties[0]
                    statements.append(
                        f"CREATE CONSTRAINT {name} IF NOT EXISTS FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE;"
                    )
        except Exception as e:
            logger.warning(f"Could not export constraints: {e}")

        # Get indexes
        try:
            result = self.client.run_query("SHOW INDEXES")
            for r in result:
                name = r.get('name', '')
                index_type = r.get('type', '')
                entity_type = r.get('entityType', '')
                labels = r.get('labelsOrTypes', [])
                properties = r.get('properties', [])

                # Skip constraints (they create their own indexes)
                if r.get('owningConstraint'):
                    continue

                if index_type == 'RANGE' and labels and properties:
                    label = labels[0]
                    props = ', '.join([f"n.{p}" for p in properties])
                    statements.append(
                        f"CREATE INDEX {name} IF NOT EXISTS FOR (n:{label}) ON ({props});"
                    )
        except Exception as e:
            logger.warning(f"Could not export indexes: {e}")

        return '\n'.join(statements)

    def get_labels(self) -> List[str]:
        """Get all node labels in the database."""
        result = self.client.run_query("CALL db.labels() YIELD label RETURN label ORDER BY label")
        return [r['label'] for r in result]

    def get_relationship_types(self) -> List[str]:
        """Get all relationship types in the database."""
        result = self.client.run_query("CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType")
        return [r['relationshipType'] for r in result]

    def export_nodes_by_label(self, label: str, limit: Optional[int] = None) -> List[str]:
        """Export nodes of a specific label as Cypher CREATE statements."""
        statements = []

        query = f"MATCH (n:{label}) RETURN n, id(n) as node_id"
        if limit:
            query += f" LIMIT {limit}"

        result = self.client.run_query(query)

        for r in result:
            node = r['n']
            node_id = r['node_id']

            # Build property string
            props = self._format_properties(dict(node))

            # Use MERGE with a unique identifier if available, else CREATE
            if 'game_id' in node:
                statements.append(f"MERGE (n:{label} {{game_id: '{node['game_id']}'}})\nSET n = {props};")
            elif 'sleeper_id' in node:
                statements.append(f"MERGE (n:{label} {{sleeper_id: '{node['sleeper_id']}'}})\nSET n = {props};")
            elif 'id' in node:
                statements.append(f"MERGE (n:{label} {{id: '{node['id']}'}})\nSET n = {props};")
            else:
                # Fallback: use internal ID as temp_id for relationship matching
                props_with_id = dict(node)
                props_with_id['_export_id'] = node_id
                statements.append(f"CREATE (n:{label} {self._format_properties(props_with_id)});")

            self.stats['nodes_exported'] += 1

        return statements

    def export_relationships(self, rel_type: str, limit: Optional[int] = None) -> List[str]:
        """Export relationships of a specific type."""
        statements = []

        query = f"""
        MATCH (a)-[r:{rel_type}]->(b)
        RETURN labels(a) as a_labels, id(a) as a_id, properties(a) as a_props,
               type(r) as rel_type, properties(r) as r_props,
               labels(b) as b_labels, id(b) as b_id, properties(b) as b_props
        """
        if limit:
            query += f" LIMIT {limit}"

        result = self.client.run_query(query)

        for r in result:
            # Build MATCH clauses to find the nodes
            a_match = self._build_node_match('a', r['a_labels'], r['a_props'])
            b_match = self._build_node_match('b', r['b_labels'], r['b_props'])

            if a_match and b_match:
                rel_props = self._format_properties(r['r_props']) if r['r_props'] else ''
                rel_clause = f"[r:{rel_type}]" if not rel_props else f"[r:{rel_type} {rel_props}]"

                statements.append(f"MATCH {a_match}\nMATCH {b_match}\nMERGE (a)-{rel_clause}->(b);")
                self.stats['relationships_exported'] += 1

        return statements

    def _build_node_match(self, var: str, labels: List[str], props: Dict) -> Optional[str]:
        """Build a MATCH clause for a node based on its identifying properties."""
        if not labels:
            return None

        label = labels[0]  # Use first label

        # Try to find a unique identifier
        id_props = ['game_id', 'sleeper_id', 'gsis_id', 'id', 'player_id', 'team_abbr', 'name']

        for id_prop in id_props:
            if id_prop in props and props[id_prop]:
                val = props[id_prop]
                if isinstance(val, str):
                    return f"({var}:{label} {{{id_prop}: '{val}'}})"
                else:
                    return f"({var}:{label} {{{id_prop}: {val}}})"

        # Fallback: use _export_id if we created it
        if '_export_id' in props:
            return f"({var}:{label} {{_export_id: {props['_export_id']}}})"

        return None

    def _format_properties(self, props: Dict) -> str:
        """Format properties as a Cypher map."""
        if not props:
            return '{}'

        formatted = []
        for key, value in props.items():
            if value is None:
                continue
            elif isinstance(value, bool):
                formatted.append(f"{key}: {str(value).lower()}")
            elif isinstance(value, (int, float)):
                formatted.append(f"{key}: {value}")
            elif isinstance(value, str):
                # Escape quotes and newlines
                escaped = value.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n')
                formatted.append(f"{key}: '{escaped}'")
            elif isinstance(value, list):
                # Handle arrays
                if all(isinstance(v, str) for v in value):
                    arr = ', '.join([f"'{v}'" for v in value])
                    formatted.append(f"{key}: [{arr}]")
                else:
                    arr = ', '.join([str(v) for v in value])
                    formatted.append(f"{key}: [{arr}]")

        return '{' + ', '.join(formatted) + '}'

    def run_full_export(self, sample_size: Optional[int] = None, labels_filter: Optional[List[str]] = None):
        """Run complete database export."""
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)

        start_time = datetime.now()
        logger.info("=" * 60)
        logger.info("NEO4J DATABASE EXPORT")
        logger.info("=" * 60)

        # Export schema
        logger.info("Exporting schema...")
        schema = self.export_schema()
        with open(EXPORT_DIR / "schema.cypher", 'w') as f:
            f.write("// Schema: Constraints and Indexes\n")
            f.write("// Run this first before importing nodes\n\n")
            f.write(schema)
        logger.info(f"Schema exported to schema.cypher")

        # Get labels to export
        all_labels = self.get_labels()
        labels_to_export = labels_filter if labels_filter else all_labels
        self.stats['labels'] = labels_to_export

        logger.info(f"Exporting {len(labels_to_export)} node labels...")

        # Export nodes by label (chunked to avoid memory issues)
        node_file_count = 0
        chunk_size = 10000

        for label in labels_to_export:
            logger.info(f"  Exporting {label}...")

            # Get count for this label
            count_result = self.client.run_query(f"MATCH (n:{label}) RETURN count(n) as cnt")
            total_count = count_result[0]['cnt'] if count_result else 0

            if sample_size:
                total_count = min(total_count, sample_size)

            # Export in chunks
            offset = 0
            label_statements = []

            while offset < total_count:
                query = f"MATCH (n:{label}) RETURN n, id(n) as node_id SKIP {offset} LIMIT {chunk_size}"
                result = self.client.run_query(query)

                for r in result:
                    node = r['n']
                    node_id = r['node_id']
                    props = self._format_properties(dict(node))

                    # Use identifying property for MERGE
                    id_props = ['game_id', 'sleeper_id', 'gsis_id', 'id', 'player_id', 'team_abbr']
                    merged = False

                    for id_prop in id_props:
                        if id_prop in node and node[id_prop]:
                            val = node[id_prop]
                            if isinstance(val, str):
                                label_statements.append(f"MERGE (n:{label} {{{id_prop}: '{val}'}})\nSET n += {props};")
                            else:
                                label_statements.append(f"MERGE (n:{label} {{{id_prop}: {val}}})\nSET n += {props};")
                            merged = True
                            break

                    if not merged:
                        # Add temp ID for relationship matching
                        props_dict = dict(node)
                        props_dict['_temp_id'] = node_id
                        label_statements.append(f"CREATE (n:{label} {self._format_properties(props_dict)});")

                    self.stats['nodes_exported'] += 1

                offset += chunk_size

                if sample_size and self.stats['nodes_exported'] >= sample_size:
                    break

            # Write label file
            if label_statements:
                node_file_count += 1
                filename = f"nodes_{node_file_count:03d}_{label.lower()}.cypher"
                with open(EXPORT_DIR / filename, 'w') as f:
                    f.write(f"// Nodes: {label} ({len(label_statements)} nodes)\n\n")
                    f.write('\n'.join(label_statements))
                logger.info(f"    → {filename} ({len(label_statements)} nodes)")

        # Export relationships
        logger.info("Exporting relationships...")
        rel_types = self.get_relationship_types()
        self.stats['rel_types'] = rel_types

        all_rel_statements = []
        for rel_type in rel_types:
            logger.info(f"  Exporting {rel_type}...")
            statements = self.export_relationships(rel_type, sample_size)
            all_rel_statements.extend(statements)
            logger.info(f"    → {len(statements)} relationships")

        with open(EXPORT_DIR / "relationships.cypher", 'w') as f:
            f.write(f"// Relationships ({len(all_rel_statements)} total)\n")
            f.write("// Run this after all nodes are imported\n\n")
            f.write('\n'.join(all_rel_statements))

        # Write manifest
        duration = datetime.now() - start_time
        manifest = {
            'export_timestamp': datetime.now().isoformat(),
            'duration_seconds': duration.total_seconds(),
            'nodes_exported': self.stats['nodes_exported'],
            'relationships_exported': self.stats['relationships_exported'],
            'labels': self.stats['labels'],
            'relationship_types': self.stats['rel_types'],
            'files': list(EXPORT_DIR.glob('*.cypher')),
            'sample_size': sample_size,
        }
        manifest['files'] = [f.name for f in EXPORT_DIR.glob('*.cypher')]

        with open(EXPORT_DIR / "export_manifest.json", 'w') as f:
            json.dump(manifest, f, indent=2)

        logger.info("=" * 60)
        logger.info("EXPORT COMPLETE")
        logger.info(f"Duration: {duration}")
        logger.info(f"Nodes exported: {self.stats['nodes_exported']:,}")
        logger.info(f"Relationships exported: {self.stats['relationships_exported']:,}")
        logger.info(f"Output directory: {EXPORT_DIR}")
        logger.info("=" * 60)

        return self.stats

    def close(self):
        """Close database connection."""
        if self.client:
            self.client.close()


def main():
    parser = argparse.ArgumentParser(description='Export Neo4j database to Cypher')
    parser.add_argument('--nodes-only', action='store_true', help='Export nodes only (skip relationships)')
    parser.add_argument('--sample', type=int, help='Export only N nodes per label (for testing)')
    parser.add_argument('--label', type=str, nargs='+', help='Export specific labels only')

    args = parser.parse_args()

    exporter = Neo4jExporter()

    try:
        exporter.run_full_export(
            sample_size=args.sample,
            labels_filter=args.label
        )
    finally:
        exporter.close()


if __name__ == "__main__":
    main()
