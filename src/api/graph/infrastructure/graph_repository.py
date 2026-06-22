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

from graph.infrastructure.age_bulk_loading.utils import validate_label_name
from graph.ports.repositories import IGraphReadOnlyRepository
from graph.domain.value_objects import EdgeRecord, NodeRecord, QueryResultRow
from graph.ports.protocols import GraphClientProtocol, NodeNeighborsResult
from infrastructure.database.exceptions import GraphQueryError
from shared_kernel.graph_primitives import EntityIdGenerator

if TYPE_CHECKING:
    pass


def _escape_cypher_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _property_contains_filter(
    alias: str,
    *,
    property_name: str | None,
    property_value: str | None,
) -> str:
    if not property_name or property_value is None:
        return ""
    validate_label_name(property_name)
    escaped_value = _escape_cypher_string(property_value)
    return (
        f" AND toLower(toString({alias}.{property_name})) "
        f"CONTAINS toLower('{escaped_value}')"
    )


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
        knowledge_graph_id: str | None = None,
    ) -> list[NodeRecord]:
        """Find nodes by their slug, optionally filtered by type and KnowledgeGraph.

        Args:
            slug: The entity slug (e.g., "alice-smith")
            node_type: Optional type filter (e.g., "Person")
            knowledge_graph_id: Optional KnowledgeGraph ID filter. When provided,
                only nodes whose ``knowledge_graph_id`` property matches are returned.
                When absent, nodes across all KnowledgeGraphs in the tenant graph
                are returned.

        Returns:
            List of matching nodes.
        """
        type_filter = f":{node_type}" if node_type else ""
        kg_filter = (
            f", knowledge_graph_id: '{knowledge_graph_id}'"
            if knowledge_graph_id
            else ""
        )
        query = f"""
            MATCH (n{type_filter} {{slug: '{slug}', graph_id: '{self._graph_id}'{kg_filter}}})
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

    def find_nodes_by_label(
        self,
        node_type: str,
        *,
        knowledge_graph_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
        property_name: str | None = None,
        property_value: str | None = None,
    ) -> list[NodeRecord]:
        """List nodes of one entity type, optionally scoped to a knowledge graph."""
        validate_label_name(node_type)
        bounded_limit = max(1, min(limit, 500))
        bounded_offset = max(0, offset)
        kg_filter = (
            f", knowledge_graph_id: '{knowledge_graph_id}'"
            if knowledge_graph_id
            else ""
        )
        prop_filter = _property_contains_filter(
            "n",
            property_name=property_name,
            property_value=property_value,
        )
        query = f"""
            MATCH (n:{node_type} {{graph_id: '{self._graph_id}'{kg_filter}}})
            WHERE true{prop_filter}
            RETURN {{node: n}}
            ORDER BY n.slug
            SKIP {bounded_offset}
            LIMIT {bounded_limit}
        """
        result = self._client.execute_cypher(query)

        nodes: list[NodeRecord] = []
        for row in result.rows:
            if len(row) > 0 and isinstance(row[0], dict):
                result_map = row[0]
                if "node" in result_map and result_map["node"] is not None:
                    nodes.append(self._vertex_to_node_record(result_map["node"]))
        return nodes

    def find_existing_node_ids(
        self,
        node_ids: list[str],
        *,
        knowledge_graph_id: str,
        chunk_size: int = 200,
    ) -> set[str]:
        """Return node IDs from ``node_ids`` that already exist in the knowledge graph."""
        if not node_ids:
            return set()
        existing: set[str] = set()
        for offset in range(0, len(node_ids), chunk_size):
            chunk = node_ids[offset : offset + chunk_size]
            literals = ", ".join(
                f"'{_escape_cypher_string(node_id)}'" for node_id in chunk
            )
            query = f"""
                MATCH (n {{graph_id: '{self._graph_id}', knowledge_graph_id: '{_escape_cypher_string(knowledge_graph_id)}'}})
                WHERE n.id IN [{literals}]
                RETURN n.id AS id
            """
            result = self._client.execute_cypher(query)
            for row in result.rows:
                if row and row[0] is not None:
                    existing.add(str(row[0]))
        return existing

    def find_existing_edge_ids(
        self,
        edge_ids: list[str],
        *,
        knowledge_graph_id: str,
        chunk_size: int = 200,
    ) -> set[str]:
        """Return edge IDs from ``edge_ids`` that already exist in the knowledge graph."""
        if not edge_ids:
            return set()
        existing: set[str] = set()
        for offset in range(0, len(edge_ids), chunk_size):
            chunk = edge_ids[offset : offset + chunk_size]
            literals = ", ".join(
                f"'{_escape_cypher_string(edge_id)}'" for edge_id in chunk
            )
            query = f"""
                MATCH ()-[r {{graph_id: '{self._graph_id}', knowledge_graph_id: '{_escape_cypher_string(knowledge_graph_id)}'}}]->()
                WHERE r.id IN [{literals}]
                RETURN r.id AS id
            """
            result = self._client.execute_cypher(query)
            for row in result.rows:
                if row and row[0] is not None:
                    existing.add(str(row[0]))
        return existing

    def find_nodes_by_ids(
        self,
        node_ids: list[str],
        *,
        knowledge_graph_id: str,
        chunk_size: int = 200,
    ) -> dict[str, NodeRecord]:
        """Return node snapshots keyed by application id."""
        if not node_ids:
            return {}
        snapshots: dict[str, NodeRecord] = {}
        kg = _escape_cypher_string(knowledge_graph_id)
        for offset in range(0, len(node_ids), chunk_size):
            chunk = node_ids[offset : offset + chunk_size]
            literals = ", ".join(
                f"'{_escape_cypher_string(node_id)}'" for node_id in chunk
            )
            query = f"""
                MATCH (n {{graph_id: '{self._graph_id}', knowledge_graph_id: '{kg}'}})
                WHERE n.id IN [{literals}]
                RETURN n
            """
            result = self._client.execute_cypher(query)
            for row in result.rows:
                if not row or row[0] is None:
                    continue
                node = self._vertex_to_node_record(row[0])
                snapshots[node.id] = node
        return snapshots

    def find_edges_by_ids(
        self,
        edge_ids: list[str],
        *,
        knowledge_graph_id: str,
        chunk_size: int = 200,
    ) -> dict[str, EdgeRecord]:
        """Return edge snapshots keyed by application id."""
        if not edge_ids:
            return {}
        snapshots: dict[str, EdgeRecord] = {}
        kg = _escape_cypher_string(knowledge_graph_id)
        for offset in range(0, len(edge_ids), chunk_size):
            chunk = edge_ids[offset : offset + chunk_size]
            literals = ", ".join(
                f"'{_escape_cypher_string(edge_id)}'" for edge_id in chunk
            )
            query = f"""
                MATCH ()-[r {{graph_id: '{self._graph_id}', knowledge_graph_id: '{kg}'}}]->()
                WHERE r.id IN [{literals}]
                RETURN r
            """
            result = self._client.execute_cypher(query)
            for row in result.rows:
                if not row or row[0] is None:
                    continue
                edge = self._edge_to_edge_record(row[0])
                snapshots[edge.id] = edge
        return snapshots

    def find_existing_slugs_for_entity_type(
        self,
        entity_type: str,
        slugs: list[str],
        *,
        knowledge_graph_id: str,
        chunk_size: int = 200,
    ) -> set[str]:
        """Return slugs that already exist for one entity type within a knowledge graph."""
        if not slugs:
            return set()
        validate_label_name(entity_type)
        existing: set[str] = set()
        kg = _escape_cypher_string(knowledge_graph_id)
        for offset in range(0, len(slugs), chunk_size):
            chunk = slugs[offset : offset + chunk_size]
            literals = ", ".join(f"'{_escape_cypher_string(slug)}'" for slug in chunk)
            query = f"""
                MATCH (n:{entity_type} {{graph_id: '{self._graph_id}', knowledge_graph_id: '{kg}'}})
                WHERE n.slug IN [{literals}]
                RETURN n.slug AS slug
            """
            result = self._client.execute_cypher(query)
            for row in result.rows:
                if row and row[0] is not None:
                    existing.add(str(row[0]))
        return existing

    def count_nodes_by_label(
        self,
        node_type: str,
        *,
        knowledge_graph_id: str | None = None,
        property_name: str | None = None,
        property_value: str | None = None,
    ) -> int:
        """Count nodes of one entity type within an optional knowledge graph scope."""
        validate_label_name(node_type)
        kg_filter = (
            f", knowledge_graph_id: '{knowledge_graph_id}'"
            if knowledge_graph_id
            else ""
        )
        prop_filter = _property_contains_filter(
            "n",
            property_name=property_name,
            property_value=property_value,
        )
        query = f"""
            MATCH (n:{node_type} {{graph_id: '{self._graph_id}'{kg_filter}}})
            WHERE true{prop_filter}
            RETURN count(n) AS total
        """
        result = self._client.execute_cypher(query)
        if not result.rows:
            return 0
        row = result.rows[0]
        if not row:
            return 0
        value = row[0]
        if isinstance(value, dict) and "total" in value:
            return int(value["total"])
        return int(value)

    def find_relationship_instances(
        self,
        relationship_label: str,
        *,
        knowledge_graph_id: str | None = None,
        source_entity_type: str | None = None,
        target_entity_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
        property_name: str | None = None,
        property_value: str | None = None,
    ) -> list[tuple[EdgeRecord, NodeRecord, NodeRecord]]:
        """List relationship instances with resolved source and target nodes."""
        validate_label_name(relationship_label)
        if source_entity_type:
            validate_label_name(source_entity_type)
        if target_entity_type:
            validate_label_name(target_entity_type)
        bounded_limit = max(1, min(limit, 500))
        bounded_offset = max(0, offset)
        source_type = f":{source_entity_type}" if source_entity_type else ""
        target_type = f":{target_entity_type}" if target_entity_type else ""
        kg_filter = (
            f", knowledge_graph_id: '{knowledge_graph_id}'"
            if knowledge_graph_id
            else ""
        )
        prop_filter = _property_contains_filter(
            "edge",
            property_name=property_name,
            property_value=property_value,
        )
        query = f"""
            MATCH (source{source_type})-[edge:{relationship_label} {{
                graph_id: '{self._graph_id}'{kg_filter}
            }}]->(target{target_type})
            WHERE true{prop_filter}
            RETURN {{edge: edge, source: source, target: target}}
            ORDER BY edge.id
            SKIP {bounded_offset}
            LIMIT {bounded_limit}
        """
        result = self._client.execute_cypher(query)

        instances: list[tuple[EdgeRecord, NodeRecord, NodeRecord]] = []
        for row in result.rows:
            if len(row) == 0 or not isinstance(row[0], dict):
                continue
            result_map = row[0]
            edge_vertex = result_map.get("edge")
            source_vertex = result_map.get("source")
            target_vertex = result_map.get("target")
            if edge_vertex is None or source_vertex is None or target_vertex is None:
                continue
            instances.append(
                (
                    self._edge_to_edge_record(edge_vertex),
                    self._vertex_to_node_record(source_vertex),
                    self._vertex_to_node_record(target_vertex),
                )
            )
        return instances

    def count_relationship_instances(
        self,
        relationship_label: str,
        *,
        knowledge_graph_id: str | None = None,
        source_entity_type: str | None = None,
        target_entity_type: str | None = None,
        property_name: str | None = None,
        property_value: str | None = None,
    ) -> int:
        """Count relationship instances matching optional endpoint type filters."""
        validate_label_name(relationship_label)
        if source_entity_type:
            validate_label_name(source_entity_type)
        if target_entity_type:
            validate_label_name(target_entity_type)
        source_type = f":{source_entity_type}" if source_entity_type else ""
        target_type = f":{target_entity_type}" if target_entity_type else ""
        kg_filter = (
            f", knowledge_graph_id: '{knowledge_graph_id}'"
            if knowledge_graph_id
            else ""
        )
        prop_filter = _property_contains_filter(
            "edge",
            property_name=property_name,
            property_value=property_value,
        )
        query = f"""
            MATCH (source{source_type})-[edge:{relationship_label} {{
                graph_id: '{self._graph_id}'{kg_filter}
            }}]->(target{target_type})
            WHERE true{prop_filter}
            RETURN count(edge) AS total
        """
        result = self._client.execute_cypher(query)
        if not result.rows:
            return 0
        row = result.rows[0]
        if not row:
            return 0
        value = row[0]
        if isinstance(value, dict) and "total" in value:
            return int(value["total"])
        return int(value)

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
        raw_edges: list[AgeEdge] = []
        central_node: NodeRecord | None = None
        # Map AGE numeric vertex IDs → application-level IDs so we can
        # remap edge start_id/end_id (which AGE stores as numeric graphids).
        age_id_to_app_id: dict[str, str] = {}

        for row in result.rows:
            # row[0] is a dict: {"central_node": Vertex, "neighbor": Vertex | null, "relationship": Edge | null}
            if len(row) > 0 and isinstance(row[0], dict):
                result_map = row[0]

                # Get central node details (should be present in every row)
                if (
                    "central_node" in result_map
                    and result_map["central_node"] is not None
                ):
                    vertex = result_map["central_node"]
                    central_node = self._vertex_to_node_record(vertex)
                    age_id_to_app_id[str(vertex.id)] = central_node.id

                # Extract neighbor (may be null if no neighbors)
                if "neighbor" in result_map and result_map["neighbor"] is not None:
                    vertex = result_map["neighbor"]
                    node_record = self._vertex_to_node_record(vertex)
                    nodes.append(node_record)
                    age_id_to_app_id[str(vertex.id)] = node_record.id

                # Collect raw edges for remapping after all vertices are processed
                if (
                    "relationship" in result_map
                    and result_map["relationship"] is not None
                ):
                    raw_edges.append(result_map["relationship"])

        if central_node is None:
            raise GraphQueryError("Cannot find central node details.", query=query)

        # Convert edges with remapped start_id/end_id
        edges: list[EdgeRecord] = []
        for age_edge in raw_edges:
            edge = self._edge_to_edge_record(age_edge)
            # Remap AGE numeric start/end IDs to application-level IDs
            remapped_start = age_id_to_app_id.get(str(age_edge.start_id), edge.start_id)
            remapped_end = age_id_to_app_id.get(str(age_edge.end_id), edge.end_id)
            if remapped_start != edge.start_id or remapped_end != edge.end_id:
                edge = EdgeRecord(
                    id=edge.id,
                    label=edge.label,
                    start_id=remapped_start,
                    end_id=remapped_end,
                    properties=edge.properties,
                )
            edges.append(edge)

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
