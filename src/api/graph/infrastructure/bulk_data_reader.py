"""Bulk graph data reader for visualization endpoints.

Fetches all nodes and edges from an AGE graph using direct SQL queries
on label tables. This bypasses the Cypher layer for maximum performance
with large graphs.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from infrastructure.database.connection_pool import ConnectionPool

logger = logging.getLogger(__name__)


def fetch_bulk_graph_data(pool: ConnectionPool, graph_name: str) -> dict[str, Any]:
    """Fetch all nodes and edges from the graph using direct SQL.

    Uses direct SQL queries on AGE label tables instead of Cypher for
    maximum performance with large graphs. Cypher MATCH scans everything
    through the AGE layer which is slow for large datasets.

    Args:
        pool: AGE connection pool.
        graph_name: The AGE graph name (e.g. ``tenant_{tenant_id}``).

    Returns:
        Dict with ``nodes`` and ``edges`` lists in Cosmograph-compatible format.
    """
    logger.info(f"Fetching graph data for graph: {graph_name}")

    conn = pool.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT name, kind FROM ag_catalog.ag_label
                WHERE graph = (SELECT graphid FROM ag_catalog.ag_graph WHERE name = %s)
                AND name NOT LIKE '_ag_label%%'
                """,
                (graph_name,),
            )
            labels = [(row[0], row[1]) for row in cur.fetchall()]

            vertex_labels = [name for name, kind in labels if kind == "v"]
            edge_labels = [name for name, kind in labels if kind == "e"]

            logger.info(
                f"Found {len(vertex_labels)} vertex labels, {len(edge_labels)} edge labels"
            )

            nodes: list[dict[str, Any]] = []
            if vertex_labels:
                union_parts = []
                for label in vertex_labels:
                    union_parts.append(f'''
                        SELECT
                            id::text AS age_id,
                            '{label}' AS label,
                            ag_catalog.agtype_out(properties) AS props
                        FROM "{graph_name}"."{label}"
                    ''')

                cur.execute(" UNION ALL ".join(union_parts))

                for row in cur.fetchall():
                    age_id, label, props_str = row
                    try:
                        props = json.loads(props_str) if props_str else {}
                        domain_id = props.get("id", "")
                        props_copy = {k: v for k, v in props.items() if k != "id"}
                        nodes.append(
                            {
                                "id": age_id,
                                "domainId": domain_id,
                                "label": props.get("name")
                                or props.get("slug")
                                or domain_id
                                or label,
                                "type": label,
                                **props_copy,
                            }
                        )
                    except json.JSONDecodeError:
                        continue

            logger.info(f"Fetched {len(nodes)} nodes")

            edges: list[dict[str, Any]] = []
            if edge_labels:
                union_parts = []
                for label in edge_labels:
                    union_parts.append(f'''
                        SELECT
                            id::text AS age_id,
                            start_id::text AS source,
                            end_id::text AS target,
                            '{label}' AS label,
                            ag_catalog.agtype_out(properties) AS props
                        FROM "{graph_name}"."{label}"
                    ''')

                cur.execute(" UNION ALL ".join(union_parts))

                for row in cur.fetchall():
                    age_id, source, target, label, props_str = row
                    try:
                        props = json.loads(props_str) if props_str else {}
                        domain_id = props.get("id", "")
                        props_copy = {k: v for k, v in props.items() if k != "id"}
                        edges.append(
                            {
                                "id": age_id,
                                "domainId": domain_id,
                                "source": source,
                                "target": target,
                                "type": label,
                                **props_copy,
                            }
                        )
                    except json.JSONDecodeError:
                        continue

            logger.info(f"Fetched {len(edges)} edges")

        return {"nodes": nodes, "edges": edges}
    except Exception as e:
        logger.exception(f"Error fetching graph data: {e}")
        raise
    finally:
        pool.return_connection(conn)
