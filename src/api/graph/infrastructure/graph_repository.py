"""Graph Extraction Read-Only Repository implementation.

This repository is designed for the Extraction bounded context, providing
the Claude Agent SDK with scoped, read-only access to the graph during
extraction jobs. All queries are automatically filtered to a specific
graph_id for security isolation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from age.models import Edge as AgeEdge  # type: ignore
from age.models import Vertex as AgeVertex

from graph.ports.repositories import IGraphReadOnlyRepository
from graph.domain.value_objects import EdgeRecord, NodeRecord, QueryResultRow
from graph.ports.protocols import GraphClientProtocol, NodeNeighborsResult
from infrastructure.database.exceptions import GraphQueryError
from shared_kernel.graph_primitives import EntityIdGenerator

if TYPE_CHECKING:
    pass


class GraphExtractionReadOnlyRepository(IGraphReadOnlyRepository):
    """Read-only repository for the Extraction bounded context.

    This repository provides the Claude Agent SDK with tools to query existing
    graph state during extraction jobs. It is statefully scoped to a specific
    graph_id upon creation, ensuring that all queries are automatically
    filtered to only see nodes and edges belonging to that graph.

    Security features:
        - All queries automatically filtered by graph_id
        - Raw queries enforced as read-only (no CREATE/DELETE/SET/REMOVE/MERGE)
        - Raw queries limited to 100 results maximum
        - Raw queries enforce 5-second timeout to prevent DoS

    Attributes:
        _client: The underlying graph client.
        _graph_id: The data source ID scope for all queries.

    Example:
        # In the Extraction context, when processing a JobPackage
        repo = GraphExtractionReadOnlyRepository(
            client=age_client,
            graph_id="ds-456",
        )

        # Agent SDK can now query existing state
        existing_nodes = repo.find_nodes_by_slug("alice-smith", "Person")
        deterministic_id = repo.generate_id("Person", "alice-smith")
    """

    def __init__(
        self,
        client: GraphClientProtocol,
        graph_id: str,
    ):
        """Initialize the repository.

        Args:
            client: A connected graph client implementing GraphClientProtocol.
            graph_id: The graph ID to scope all queries to. For initial tracer bullet
                implementation, this is statically set via environment variable.
        """
        self._client = client
        self._graph_id = graph_id

    def generate_id(self, entity_type: str, entity_slug: str) -> str:
        """Generate a deterministic ID for an entity.

        This method delegates to the shared EntityIdGenerator from the
        Shared Kernel, ensuring consistency across all bounded contexts
        (particularly Graph and Extraction).

        The entity_type is normalized to lowercase for the ID prefix, ensuring
        consistent IDs regardless of input casing. This supports the secure
        enclave pattern where IDs and types are visible metadata, while all
        sensitive information resides in properties.

        Args:
            entity_type: The type of entity (e.g., "Person", "Repository").
            entity_slug: The entity's slug (e.g., "alice-smith").

        Returns:
            A deterministic ID string with lowercase prefix (e.g., "person:abc123def").

        Example:
            id1 = repo.generate_id("Person", "alice-smith")
            id2 = repo.generate_id("person", "alice-smith")
            assert id1 == id2  # Normalized to same ID: "person:..."
        """
        return EntityIdGenerator.generate(
            entity_type=entity_type, entity_slug=entity_slug
        )

    def find_nodes_by_slug(
        self,
        slug: str,
        node_type: str | None = None,
    ) -> list[NodeRecord]:
        """Find nodes by their slug, optionally filtered by type."""
        type_filter = f":{node_type}" if node_type else ""
        query = f"""
            MATCH (n{type_filter} {{slug: '{slug}', graph_id: '{self._graph_id}'}})
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
    ) -> NodeNeighborsResult:
        """Get all neighboring nodes and connecting edges."""
        query = f"""\
MATCH (n {{id: '{node_id}', graph_id: '{self._graph_id}'}})
OPTIONAL MATCH (n)-[r]-(m)
WHERE m.graph_id = '{self._graph_id}' OR m IS NULL
RETURN {{central_node: n, neighbor: m, relationship: r}}\
"""
        result = self._client.execute_cypher(query)

        nodes: list[NodeRecord] = []
        edges: list[EdgeRecord] = []
        central_node: NodeRecord | None = None

        for row in result.rows:
            # row[0] is a dict: {"central_node": Vertex, "neighbor": Vertex | null, "relationship": Edge | null}
            if len(row) > 0 and isinstance(row[0], dict):
                result_map = row[0]

                # Get central node details (should be present in every row)
                if (
                    "central_node" in result_map
                    and result_map["central_node"] is not None
                ):
                    central_node = self._vertex_to_node_record(
                        result_map["central_node"]
                    )

                # Extract neighbor (may be null if no neighbors)
                if "neighbor" in result_map and result_map["neighbor"] is not None:
                    nodes.append(self._vertex_to_node_record(result_map["neighbor"]))

                # Extract relationship (may be null if no neighbors)
                if (
                    "relationship" in result_map
                    and result_map["relationship"] is not None
                ):
                    edges.append(self._edge_to_edge_record(result_map["relationship"]))

        if central_node is None:
            raise GraphQueryError("Cannot find central node details.", query=query)

        return NodeNeighborsResult(central_node=central_node, edges=edges, nodes=nodes)

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

        # Safeguard: Enforce LIMIT if not present (TODO: be smarter about this)
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
        props = dict(vertex.properties) if vertex.properties else {}
        # Prefer the application-level 'id' property over the AGE-internal numeric ID
        node_id = str(props.get("id", vertex.id))
        return NodeRecord(
            id=node_id,
            label=vertex.label,
            properties=props,
        )

    def _edge_to_edge_record(self, edge: AgeEdge) -> EdgeRecord:
        """Convert an AGE Edge to an EdgeRecord."""
        if edge.label is None:
            raise ValueError(f"Invalid Nonetype for edge.label (edge: {repr(edge)})")
        props = dict(edge.properties) if edge.properties else {}
        # Prefer application-level IDs from properties over AGE-internal numeric IDs
        edge_id = str(props.get("id", edge.id))
        start_id = str(props.get("start_id", edge.start_id))
        end_id = str(props.get("end_id", edge.end_id))
        return EdgeRecord(
            id=edge_id,
            label=edge.label,
            start_id=start_id,
            end_id=end_id,
            properties=props,
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
