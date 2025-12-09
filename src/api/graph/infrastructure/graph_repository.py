"""GraphReadOnlyRepository implementation.

Implements the IGraphReadOnlyRepository interface using AgeGraphClient
for the underlying graph operations.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from age.models import Edge as AgeEdge
from age.models import Vertex as AgeVertex

from graph.domain.value_objects import EdgeRecord, NodeRecord, QueryResultRow
from graph.infrastructure.protocols import GraphClientProtocol
from infrastructure.database.exceptions import GraphQueryError

if TYPE_CHECKING:
    pass


class GraphReadOnlyRepository:
    """Read-only repository implementation for graph queries.

    This implementation wraps a GraphClientProtocol-compatible client
    and provides domain-level abstractions. It is scoped to a specific
    data_source_id for security isolation.

    Attributes:
        _client: The underlying graph client.
        _data_source_id: The data source scope for all queries.
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

        Combines data_source_id + entity_type + entity_slug using SHA256
        to produce a stable, reproducible identifier.
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
            RETURN n, r, m
        """
        result = self._client.execute_cypher(query)

        nodes: dict[str, NodeRecord] = {}
        edges: list[EdgeRecord] = []

        for row in result.rows:
            if len(row) >= 1 and row[0] is not None:
                node = self._vertex_to_node_record(row[0])
                nodes[node.id] = node
            if len(row) >= 2 and row[1] is not None:
                edge = self._edge_to_edge_record(row[1])
                edges.append(edge)
            if len(row) >= 3 and row[2] is not None:
                neighbor = self._vertex_to_node_record(row[2])
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
            RETURN n
        """
        result = self._client.execute_cypher(query)

        return [
            self._vertex_to_node_record(row[0])
            for row in result.rows
            if row[0] is not None
        ]

    def get_neighbors(
        self,
        node_id: str,
    ) -> tuple[list[NodeRecord], list[EdgeRecord]]:
        """Get all neighboring nodes and connecting edges."""
        query = f"""
            MATCH (n {{id: '{node_id}', data_source_id: '{self._data_source_id}'}})-[r]-(m)
            WHERE m.data_source_id = '{self._data_source_id}'
            RETURN m, r
        """
        result = self._client.execute_cypher(query)

        nodes: list[NodeRecord] = []
        edges: list[EdgeRecord] = []

        for row in result.rows:
            if row[0] is not None:
                nodes.append(self._vertex_to_node_record(row[0]))
            if len(row) > 1 and row[1] is not None:
                edges.append(self._edge_to_edge_record(row[1]))

        return nodes, edges

    def execute_raw_query(
        self,
        query: str,
    ) -> list[QueryResultRow]:
        """Execute a raw Cypher query with safeguards.

        Enforces read-only by rejecting mutation keywords and
        limits results to 100 rows.
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

        # Enforce LIMIT if not present
        if "LIMIT" not in query_upper:
            query = f"{query} LIMIT 100"

        result = self._client.execute_cypher(query)

        # Convert results to dictionaries
        return [self._row_to_dict(row) for row in result.rows]

    def _vertex_to_node_record(self, vertex: AgeVertex) -> NodeRecord:
        """Convert an AGE Vertex to a NodeRecord."""
        return NodeRecord(
            id=str(vertex.id),
            label=vertex.label,
            properties=dict(vertex.properties) if vertex.properties else {},
        )

    def _edge_to_edge_record(self, edge: AgeEdge) -> EdgeRecord:
        """Convert an AGE Edge to an EdgeRecord."""
        return EdgeRecord(
            id=str(edge.id),
            label=edge.label,
            start_id=str(edge.start_id),
            end_id=str(edge.end_id),
            properties=dict(edge.properties) if edge.properties else {},
        )

    def _row_to_dict(self, row: tuple) -> QueryResultRow:
        """Convert a result row to a dictionary."""
        if len(row) == 1:
            item = row[0]
            if isinstance(item, AgeVertex):
                node = self._vertex_to_node_record(item)
                return {"node": node.model_dump()}
            elif isinstance(item, AgeEdge):
                edge = self._edge_to_edge_record(item)
                return {"edge": edge.model_dump()}
            else:
                return {"value": item}
        return {f"col_{i}": val for i, val in enumerate(row)}
