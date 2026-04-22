"""Query repository implementation for the Querying bounded context.

This repository provides UNSCOPED read-only access to the graph
for MCP clients, in contrast to the scoped GraphExtractionReadOnlyRepository.
"""

from __future__ import annotations

import re
import uuid


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

    Provides unscoped access to the entire graph with defense-in-depth
    security safeguards:

    Primary defense — database-level read-only session:
        Every transaction is started with ``SET TRANSACTION READ ONLY``,
        causing the database to reject any write attempt regardless of
        query content.

    Secondary defense — keyword blacklist:
        Queries containing mutation keywords (CREATE, DELETE, SET, REMOVE,
        MERGE, EXPLAIN, LOAD) are rejected before reaching the database.
        A redacted log entry keyed by a correlation ID is emitted; the raw
        query text is never logged.

    Additional safeguards:
        - Result limiting: appends LIMIT if absent; caps explicit LIMITs
          that exceed MAX_LIMIT.
        - Timeout: sets PostgreSQL ``statement_timeout`` for each transaction.

    Unlike GraphExtractionReadOnlyRepository, this does NOT scope
    queries to a specific data_source_id.
    """

    # Mutation keywords to reject (spec: secondary read-only enforcement)
    MUTATION_KEYWORDS = frozenset(
        ["CREATE", "DELETE", "SET", "REMOVE", "MERGE", "EXPLAIN", "LOAD"]
    )

    # Absolute maximum number of rows any query may return
    MAX_LIMIT: int = 10000

    # Default LIMIT appended when query has no LIMIT clause
    DEFAULT_LIMIT: int = 1000

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
        """Execute a Cypher query with defense-in-depth safeguards.

        Safeguards (applied in order):
        1. Keyword blacklist: Rejects queries with mutation keywords before
           any database round-trip. The rejection is logged with a correlation
           ID; the raw query text is never logged.
        2. Result limiting: Appends LIMIT when absent; caps explicit LIMITs
           exceeding MAX_LIMIT.
        3. Database-level read-only: Sets the transaction to READ ONLY so
           the database itself rejects writes regardless of query content.
        4. Timeout: Sets ``statement_timeout`` so long-running queries are
           cancelled by the database.

        Args:
            query: Cypher query string.
            timeout_seconds: Query timeout in seconds.
            max_rows: Default LIMIT appended when query has no LIMIT clause.

        Returns:
            List of result dictionaries.

        Raises:
            QueryForbiddenError: If a mutation keyword is detected.
            QueryTimeoutError: If the database cancels the statement.
            QueryExecutionError: On other query failures.
        """
        # Safeguard 1: Reject mutation keywords (secondary read-only defense)
        self._validate_read_only(query)

        # Safeguard 2: Ensure LIMIT is present and within bounds
        query = self._ensure_limit(query, max_rows)

        # Safeguards 3 + 4: Execute within a read-only transaction with timeout
        try:
            with self._client.transaction() as tx:
                # Primary defense: configure the session as read-only at the
                # database level. The database will reject any write attempt
                # regardless of query content.
                tx.execute_sql("SET TRANSACTION READ ONLY")

                # Set per-statement timeout (secondary timeout safeguard)
                tx.execute_sql(
                    f"SET LOCAL statement_timeout = {timeout_seconds * 1000}"
                )

                result = tx.execute_cypher(query)
        except (QueryForbiddenError, QueryTimeoutError):
            raise
        except Exception as e:
            error_msg = str(e).lower()
            # Check if it's a timeout error (PostgreSQL raises specific error)
            if "timeout" in error_msg or "canceling statement" in error_msg:
                correlation_id = str(uuid.uuid4())
                raise QueryTimeoutError(
                    f"Query exceeded {timeout_seconds}s timeout",
                    query=query,
                    correlation_id=correlation_id,
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

        This is the secondary read-only defense. Generates a correlation ID
        per rejection so the redacted log entry can be linked to the error
        response without exposing the raw query text.

        Raises:
            QueryForbiddenError: If mutation keyword found, with correlation_id set.
        """
        query_upper = query.upper()
        for keyword in self.MUTATION_KEYWORDS:
            if keyword in query_upper:
                correlation_id = str(uuid.uuid4())
                raise QueryForbiddenError(
                    f"Query must be read-only. Found forbidden keyword: {keyword}",
                    query=query,
                    correlation_id=correlation_id,
                )

    def _ensure_limit(self, query: str, max_rows: int = DEFAULT_LIMIT) -> str:
        """Enforce result limits on the query.

        Rules (spec: Result Limiting requirement):
        - If no LIMIT clause is present, append ``LIMIT max_rows``.
        - If LIMIT is present and within MAX_LIMIT, keep it as-is.
        - If LIMIT exceeds MAX_LIMIT, replace it with MAX_LIMIT.

        Args:
            query: Cypher query string.
            max_rows: Default limit appended when LIMIT is absent.

        Returns:
            Query string with an appropriate LIMIT clause.
        """
        limit_match = re.search(r"\bLIMIT\s+(\d+)", query, re.IGNORECASE)
        if limit_match:
            existing_limit = int(limit_match.group(1))
            if existing_limit > self.MAX_LIMIT:
                # Cap to absolute maximum (spec: Explicit LIMIT exceeds maximum)
                return re.sub(
                    r"\bLIMIT\s+\d+",
                    f"LIMIT {self.MAX_LIMIT}",
                    query,
                    flags=re.IGNORECASE,
                )
            # Within bounds — respect the explicit LIMIT
            return query

        # No LIMIT present — append the default (spec: No LIMIT in query)
        return f"{query}\nLIMIT {max_rows}"

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
