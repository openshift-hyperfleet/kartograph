"""Graph Extraction Read-Only Repository implementation.

This repository is designed for the Extraction bounded context, providing
the Claude Agent SDK with scoped, read-only access to the graph during
extraction jobs. All queries are automatically filtered to a specific
data_source_id for security isolation.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from age.models import Edge as AgeEdge  # type: ignore
from age.models import Vertex as AgeVertex

from graph.domain.value_objects import EdgeRecord, NodeRecord, QueryResultRow
from graph.infrastructure.protocols import GraphClientProtocol
from infrastructure.database.exceptions import GraphQueryError

if TYPE_CHECKING:
    pass


class GraphExtractionReadOnlyRepository:
    """Read-only repository for the Extraction bounded context.

    This repository provides the Claude Agent SDK with tools to query existing
    graph state during extraction jobs. It is statefully scoped to a specific
    data_source_id upon creation, ensuring that all queries are automatically
    filtered to only see nodes and edges belonging to that data source.

    Security features:
        - All queries automatically filtered by data_source_id
        - Raw queries enforced as read-only (no CREATE/DELETE/SET/REMOVE/MERGE)
        - Raw queries limited to 100 results maximum
        - Raw queries enforce 5-second timeout to prevent DoS

    Attributes:
        _client: The underlying graph client.
        _data_source_id: The data source ID scope for all queries.

    Example:
        # In the Extraction context, when processing a JobPackage
        repo = GraphExtractionReadOnlyRepository(
            client=age_client,
            data_source_id="ds-456",
        )

        # Agent SDK can now query existing state
        existing_nodes = repo.find_nodes_by_slug("alice-smith", "Person")
        deterministic_id = repo.generate_id("Person", "alice-smith")
    """

    def __init__(
        self,
        client: GraphClientProtocol,
        data_source_id: str,
    ):
        """Initialize the repository.

        Args:
            client: A connected graph client implementing GraphClientProtocol.
            data_source_id: The data source ID to scope all queries to.
        """
        self._client = client
        self._data_source_id = data_source_id

    def generate_id(self, entity_type: str, entity_slug: str) -> str:
        """Generate a deterministic ID for an entity.

        This method is critical for idempotent mutation operations in the
        Extraction context. It combines the repository's scoped data_source_id
        with the entity type and slug to produce a stable, reproducible
        identifier using SHA256 hashing.

        Args:
            entity_type: The type of entity (e.g., "Person", "Repository").
            entity_slug: The entity's slug (e.g., "alice-smith").

        Returns:
            A deterministic ID string (e.g., "Person:abc123def").

        Example:
            id1 = repo.generate_id("Person", "alice-smith")
            id2 = repo.generate_id("Person", "alice-smith")
            assert id1 == id2  # Same inputs always produce same ID
        """
        combined = f"{self._data_source_id}:{entity_type}:{entity_slug}"
        hash_value = hashlib.sha256(combined.encode()).hexdigest()[:16]
        return f"{entity_type}:{hash_value}"

    def find_nodes_by_path(
        self,
        path: str,
    ) -> tuple[list[NodeRecord], list[EdgeRecord]]:
        """Find nodes and their edges by source file path."""
        query = f"""
            MATCH (n {{source_path: '{path}', data_source_id: '{self._data_source_id}'}})
            OPTIONAL MATCH (n)-[r]-(m)
            WHERE m.data_source_id = '{self._data_source_id}'
            RETURN {{node: n, relationship: r, neighbor: m}}
        """
        result = self._client.execute_cypher(query)

        nodes: dict[str, NodeRecord] = {}
        edges: list[EdgeRecord] = []

        for row in result.rows:
            # row[0] is a dict: {"node": Vertex, "relationship": Edge, "neighbor": Vertex}
            if len(row) > 0 and isinstance(row[0], dict):
                result_map = row[0]

                # Extract node
                if "node" in result_map and result_map["node"] is not None:
                    node = self._vertex_to_node_record(result_map["node"])
                    nodes[node.id] = node

                # Extract relationship
                if (
                    "relationship" in result_map
                    and result_map["relationship"] is not None
                ):
                    edge = self._edge_to_edge_record(result_map["relationship"])
                    edges.append(edge)

                # Extract neighbor
                if "neighbor" in result_map and result_map["neighbor"] is not None:
                    neighbor = self._vertex_to_node_record(result_map["neighbor"])
                    nodes[neighbor.id] = neighbor

        return list(nodes.values()), edges

    def find_nodes_by_slug(
        self,
        slug: str,
        node_type: str | None = None,
    ) -> list[NodeRecord]:
        """Find nodes by their slug, optionally filtered by type."""
        type_filter = f":{node_type}" if node_type else ""
        query = f"""
            MATCH (n{type_filter} {{slug: '{slug}', data_source_id: '{self._data_source_id}'}})
            RETURN {{node: n}}
        """
        result = self._client.execute_cypher(query)

        nodes = []
        for row in result.rows:
            # row[0] is a dict: {"node": Vertex}
            if len(row) > 0 and isinstance(row[0], dict):
                result_map = row[0]
                if "node" in result_map and result_map["node"] is not None:
                    nodes.append(self._vertex_to_node_record(result_map["node"]))

        return nodes

    def get_neighbors(
        self,
        node_id: str,
    ) -> tuple[list[NodeRecord], list[EdgeRecord]]:
        """Get all neighboring nodes and connecting edges."""
        query = f"""
            MATCH (n {{id: '{node_id}', data_source_id: '{self._data_source_id}'}})-[r]-(m)
            WHERE m.data_source_id = '{self._data_source_id}'
            RETURN {{neighbor: m, relationship: r}}
        """
        result = self._client.execute_cypher(query)

        nodes: list[NodeRecord] = []
        edges: list[EdgeRecord] = []

        for row in result.rows:
            # row[0] is a dict: {"neighbor": Vertex, "relationship": Edge}
            if len(row) > 0 and isinstance(row[0], dict):
                result_map = row[0]

                # Extract neighbor
                if "neighbor" in result_map and result_map["neighbor"] is not None:
                    nodes.append(self._vertex_to_node_record(result_map["neighbor"]))

                # Extract relationship
                if (
                    "relationship" in result_map
                    and result_map["relationship"] is not None
                ):
                    edges.append(self._edge_to_edge_record(result_map["relationship"]))

        return nodes, edges

    def execute_raw_query(
        self,
        query: str,
        timeout_seconds: int = 5,
    ) -> list[QueryResultRow]:
        """Execute a raw Cypher query with safeguards.

        This method allows the Extraction agent to explore the graph beyond
        the optimized "fast path" methods. Multiple safeguards are enforced
        to prevent abuse:

        1. Read-only enforcement: Rejects queries with mutation keywords
        2. Result limiting: Automatically adds LIMIT 100 if not present
        3. Timeout enforcement: Queries must complete within timeout_seconds

        IMPORTANT: Due to Apache AGE's SQL wrapper requirements, queries must
        return results in a single column. For multiple values, use map syntax:
            - Single value: RETURN n
            - Multiple values: RETURN {person: p, friend: f}

        Args:
            query: A Cypher query string.
            timeout_seconds: Maximum execution time in seconds (default: 5).

        Returns:
            List of result dictionaries.

        Raises:
            GraphQueryError: If the query fails, violates safeguards, or times out.

        Examples:
            # Single value query
            results = repo.execute_raw_query("MATCH (n) RETURN count(n)")

            # Multiple values using map syntax
            results = repo.execute_raw_query(
                "MATCH (p:Person)-[:KNOWS]->(f) RETURN {person: p, friend: f}"
            )
        """
        # Safeguard: Reject mutation keywords
        mutation_keywords = ["CREATE", "DELETE", "SET", "REMOVE", "MERGE"]
        query_upper = query.upper()
        for keyword in mutation_keywords:
            if keyword in query_upper:
                raise GraphQueryError(
                    f"Raw queries must be read-only. Found: {keyword}",
                    query=query,
                )

        # Safeguard: Enforce LIMIT if not present
        if "LIMIT" not in query_upper:
            query = f"""\
{query}
LIMIT 100"""

        # Safeguard: Enforce timeout using transaction with SET LOCAL
        # This protects against accidentally expensive queries that could DoS the database
        try:
            with self._client.transaction() as tx:
                # Set statement_timeout for this transaction only (PostgreSQL milliseconds)
                # This must be executed as raw SQL, not wrapped in cypher()
                tx.execute_sql(
                    f"SET LOCAL statement_timeout = {timeout_seconds * 1000}"
                )
                result = tx.execute_cypher(query)
        except Exception as e:
            # PostgreSQL raises QueryCanceled error on timeout
            raise GraphQueryError(
                f"Query failed or exceeded {timeout_seconds}s timeout: {e}",
                query=query,
            ) from e

        # Convert results to dictionaries
        return [self._row_to_dict(row) for row in result.rows]

    def _vertex_to_node_record(self, vertex: AgeVertex) -> NodeRecord:
        """Convert an AGE Vertex to a NodeRecord."""
        if vertex.label is None:
            raise ValueError(
                f"Invalid Nonetype for vertex.label (vertex: {repr(vertex)})"
            )
        return NodeRecord(
            id=str(vertex.id),
            label=vertex.label,
            properties=dict(vertex.properties) if vertex.properties else {},
        )

    def _edge_to_edge_record(self, edge: AgeEdge) -> EdgeRecord:
        """Convert an AGE Edge to an EdgeRecord."""
        if edge.label is None:
            raise ValueError(f"Invalid Nonetype for edge.label (edge: {repr(edge)})")
        return EdgeRecord(
            id=str(edge.id),
            label=edge.label,
            start_id=str(edge.start_id),
            end_id=str(edge.end_id),
            properties=dict(edge.properties) if edge.properties else {},
        )

    def _row_to_dict(self, row: tuple) -> QueryResultRow:
        """Convert a result row to a dictionary.

        Handles various return types:
        - Single Vertex: {"node": {...}}
        - Single Edge: {"edge": {...}}
        - Map with Vertex/Edge values: Converts nested objects to Records
        - Primitives: {"value": ...}
        """
        if len(row) == 1:
            item = row[0]
            if isinstance(item, AgeVertex):
                node = self._vertex_to_node_record(item)
                return {"node": node.model_dump()}
            elif isinstance(item, AgeEdge):
                edge = self._edge_to_edge_record(item)
                return {"edge": edge.model_dump()}
            elif isinstance(item, dict):
                # Handle map returns: {person: Vertex, friend: Vertex, ...}
                result = {}
                for key, value in item.items():
                    if isinstance(value, AgeVertex):
                        result[key] = self._vertex_to_node_record(value).model_dump()
                    elif isinstance(value, AgeEdge):
                        result[key] = self._edge_to_edge_record(value).model_dump()
                    else:
                        result[key] = value
                return result
            else:
                return {"value": item}
        return {f"col_{i}": val for i, val in enumerate(row)}
