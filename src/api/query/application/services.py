"""Application services for the Querying bounded context."""

from __future__ import annotations

import time

from query.application.observability import (
    DefaultQueryServiceProbe,
    QueryServiceProbe,
)
from query.domain.value_objects import (
    CypherQueryResult,
    QueryError,
    QueryExecutionError,
    QueryForbiddenError,
    QueryTimeoutError,
)
from query.ports.repositories import IQueryGraphRepository


class MCPQueryService:
    """Application service for MCP query operations.

    Orchestrates Cypher query execution with observability
    and error handling for MCP tool consumers.
    """

    def __init__(
        self,
        repository: IQueryGraphRepository,
        probe: QueryServiceProbe | None = None,
        default_timeout_seconds: int = 30,
        default_max_rows: int = 1000,
    ):
        """Initialize the service.

        Args:
            repository: The graph repository for query execution.
            probe: Optional domain probe for observability.
            default_timeout_seconds: Default query timeout.
            default_max_rows: Default maximum result rows.
        """
        self._repository = repository
        self._probe = probe or DefaultQueryServiceProbe()
        self._default_timeout = default_timeout_seconds
        self._default_max_rows = default_max_rows

    def execute_cypher_query(
        self,
        query: str,
        timeout_seconds: int | None = None,
        max_rows: int | None = None,
    ) -> CypherQueryResult | QueryError:
        """Execute a Cypher query and return structured results.

        Args:
            query: The Cypher query to execute.
            timeout_seconds: Query timeout (uses default if not provided).
            max_rows: Maximum rows (uses default if not provided).

        Returns:
            CypherQueryResult on success, QueryError on failure.
        """
        timeout = timeout_seconds or self._default_timeout
        limit = max_rows or self._default_max_rows

        self._probe.cypher_query_received(query=query, query_length=len(query))

        start_time = time.perf_counter()

        try:
            rows = self._repository.execute_cypher(
                query=query,
                timeout_seconds=timeout,
                max_rows=limit,
            )

            elapsed_ms = (time.perf_counter() - start_time) * 1000
            truncated = len(rows) >= limit

            self._probe.cypher_query_executed(
                query=query,
                row_count=len(rows),
                execution_time_ms=elapsed_ms,
                truncated=truncated,
            )

            return CypherQueryResult(
                rows=rows,
                row_count=len(rows),
                truncated=truncated,
                execution_time_ms=elapsed_ms,
            )

        except QueryForbiddenError as e:
            error_msg = str(e)
            self._probe.cypher_query_rejected(query=query, reason=error_msg)
            return QueryError(
                error_type="forbidden",
                message=error_msg,
                query=query,
            )
        except QueryTimeoutError as e:
            error_msg = str(e)
            self._probe.cypher_query_failed(query=query, error=error_msg)
            return QueryError(
                error_type="timeout",
                message=error_msg,
                query=query,
            )
        except QueryExecutionError as e:
            error_msg = str(e)
            self._probe.cypher_query_failed(query=query, error=error_msg)
            return QueryError(
                error_type="execution_error",
                message=error_msg,
                query=query,
            )
        except Exception as e:
            # Catch-all for unexpected errors
            error_msg = str(e)
            self._probe.cypher_query_failed(query=query, error=error_msg)
            return QueryError(
                error_type="unknown_error",
                message=error_msg,
                query=query,
            )
