"""Query repository implementation for the Querying bounded context.

This repository provides UNSCOPED read-only access to the graph
for MCP clients, in contrast to the scoped GraphExtractionReadOnlyRepository.
"""

from __future__ import annotations


from age.models import Edge as AgeEdge  # type: ignore
from age.models import Vertex as AgeVertex

from graph.ports.protocols import GraphClientProtocol
from query.domain.value_objects import (
    EdgeDict,
    NodeDict,
    QueryExecutionError,
    QueryForbiddenError,
    QueryResultRow,
    QueryTimeoutError,
)
from query.ports.repositories import IQueryGraphRepository


class QueryGraphRepository(IQueryGraphRepository):
    """Read-only repository for MCP query execution.

    Provides unscoped access to the entire graph with security safeguards:
    - Read-only enforcement (rejects mutation keywords)
    - Result limiting (auto-adds LIMIT if not present)
    - Timeout enforcement (via PostgreSQL statement_timeout)

    Unlike GraphExtractionReadOnlyRepository, this does NOT scope
    queries to a specific data_source_id.
    """

    # Mutation keywords to reject
    MUTATION_KEYWORDS = frozenset(
        ["CREATE", "DELETE", "SET", "REMOVE", "MERGE", "EXPLAIN", "LOAD"]
    )

    def __init__(self, client: GraphClientProtocol):
        """Initialize the repository.

        Args:
            client: A connected graph client.
        """
        self._client = client

    def execute_cypher(
        self,
        query: str,
        timeout_seconds: int = 30,
        max_rows: int = 1000,
    ) -> list[QueryResultRow]:
        """Execute a Cypher query with safeguards.

        Safeguards:
        1. Read-only enforcement: Rejects queries with mutation keywords
        2. Result limiting: Adds LIMIT if not present
        3. Timeout: Uses PostgreSQL statement_timeout

        Args:
            query: Cypher query string.
            timeout_seconds: Query timeout in seconds.
            max_rows: Maximum rows to return.

        Returns:
            List of result dictionaries.

        Raises:
            QueryExecutionError: On query failure or security violation.
        """
        # Safeguard 1: Reject mutation keywords
        self._validate_read_only(query)

        # Safeguard 2: Ensure LIMIT is present
        query = self._ensure_limit(query, max_rows)

        # Safeguard 3: Execute with timeout
        try:
            with self._client.transaction() as tx:
                # Set statement_timeout for this transaction
                tx.execute_sql(
                    f"SET LOCAL statement_timeout = {timeout_seconds * 1000}"
                )
                result = tx.execute_cypher(query)
        except Exception as e:
            error_msg = str(e).lower()
            # Check if it's a timeout error (PostgreSQL raises specific error)
            if "timeout" in error_msg or "canceling statement" in error_msg:
                raise QueryTimeoutError(
                    f"Query exceeded {timeout_seconds}s timeout",
                    query=query,
                ) from e
            # Otherwise it's a general execution error
            raise QueryExecutionError(
                f"Query execution failed: {e}",
                query=query,
            ) from e

        # Convert results to dictionaries
        return [self._row_to_dict(row) for row in result.rows]

    def _validate_read_only(self, query: str) -> None:
        """Validate that query contains no mutation keywords.

        Raises:
            QueryForbiddenError: If mutation keyword found.
        """
        query_upper = query.upper()
        for keyword in self.MUTATION_KEYWORDS:
            if keyword in query_upper:
                raise QueryForbiddenError(
                    f"Query must be read-only. Found forbidden keyword: {keyword}",
                    query=query,
                )

    def _ensure_limit(self, query: str, max_rows: int) -> str:
        """Add LIMIT clause if not present."""
        if "LIMIT" not in query.upper():
            return f"{query}\nLIMIT {max_rows}"
        return query

    def _row_to_dict(self, row: tuple) -> QueryResultRow:
        """Convert a result row to a dictionary."""
        if len(row) == 1:
            item = row[0]
            if isinstance(item, AgeVertex):
                return {"node": self._vertex_to_dict(item)}
            elif isinstance(item, AgeEdge):
                return {"edge": self._edge_to_dict(item)}
            elif isinstance(item, dict):
                # Handle map returns - explicitly type the result dict
                result: QueryResultRow = {}
                for key, value in item.items():
                    if isinstance(value, AgeVertex):
                        result[key] = self._vertex_to_dict(value)
                    elif isinstance(value, AgeEdge):
                        result[key] = self._edge_to_dict(value)
                    else:
                        result[key] = value
                return result
            else:
                return {"value": item}
        return {f"col_{i}": val for i, val in enumerate(row)}

    def _vertex_to_dict(self, vertex: AgeVertex) -> NodeDict:
        """Convert vertex to NodeDict."""
        if vertex.label is None:
            raise ValueError(
                f"Invalid None value for vertex.label (vertex: {repr(vertex)})"
            )
        return NodeDict(
            id=str(vertex.id),
            label=vertex.label,
            properties=dict(vertex.properties) if vertex.properties else {},
        )

    def _edge_to_dict(self, edge: AgeEdge) -> EdgeDict:
        """Convert edge to EdgeDict."""
        if edge.label is None:
            raise ValueError(f"Invalid None value for edge.label (edge: {repr(edge)})")
        return EdgeDict(
            id=str(edge.id),
            label=edge.label,
            start_id=str(edge.start_id),
            end_id=str(edge.end_id),
            properties=dict(edge.properties) if edge.properties else {},
        )
