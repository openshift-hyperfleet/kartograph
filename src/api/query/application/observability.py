"""Domain probes for Querying application layer.

Following Domain Oriented Observability pattern.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

import structlog

if TYPE_CHECKING:
    from shared_kernel.observability_context import ObservationContext


class QueryServiceProbe(Protocol):
    """Domain probe for query service operations."""

    def cypher_query_received(
        self,
        query: str,
        query_length: int,
    ) -> None:
        """Record that a Cypher query was received."""
        ...

    def cypher_query_executed(
        self,
        query: str,
        row_count: int,
        execution_time_ms: float,
        truncated: bool,
    ) -> None:
        """Record successful query execution."""
        ...

    def cypher_query_rejected(
        self,
        query: str,
        reason: str,
    ) -> None:
        """Record that a query was rejected (security violation)."""
        ...

    def cypher_query_failed(
        self,
        query: str,
        error: str,
    ) -> None:
        """Record that a query failed during execution."""
        ...

    def with_context(self, context: ObservationContext) -> QueryServiceProbe:
        """Create a new probe with observation context bound."""
        ...


class DefaultQueryServiceProbe:
    """Default implementation using structlog."""

    def __init__(
        self,
        logger: structlog.stdlib.BoundLogger | None = None,
        context: ObservationContext | None = None,
    ):
        self._logger = logger or structlog.get_logger()
        self._context = context

    def _get_context_kwargs(self) -> dict[str, Any]:
        if self._context is None:
            return {}
        return self._context.as_dict()

    def with_context(self, context: ObservationContext) -> DefaultQueryServiceProbe:
        return DefaultQueryServiceProbe(logger=self._logger, context=context)

    def cypher_query_received(self, query: str, query_length: int) -> None:
        self._logger.info(
            "mcp_cypher_query_received",
            query_length=query_length,
            **self._get_context_kwargs(),
        )

    def cypher_query_executed(
        self, query: str, row_count: int, execution_time_ms: float, truncated: bool
    ) -> None:
        self._logger.info(
            "mcp_cypher_query_executed",
            row_count=row_count,
            execution_time_ms=execution_time_ms,
            truncated=truncated,
            **self._get_context_kwargs(),
        )

    def cypher_query_rejected(self, query: str, reason: str) -> None:
        self._logger.warning(
            "mcp_cypher_query_rejected",
            reason=reason,
            **self._get_context_kwargs(),
        )

    def cypher_query_failed(self, query: str, error: str) -> None:
        self._logger.error(
            "mcp_cypher_query_failed",
            error=error,
            **self._get_context_kwargs(),
        )


class SchemaResourceProbe(Protocol):
    """Domain probe for schema resource access via MCP."""

    def schema_resource_accessed(
        self,
        resource_uri: str,
        label: str | None = None,
    ) -> None:
        """Record that a schema resource was accessed."""
        ...

    def schema_resource_returned(
        self,
        resource_uri: str,
        result_count: int | None = None,
        found: bool = True,
    ) -> None:
        """Record successful schema resource retrieval."""
        ...

    def schema_type_not_found(
        self,
        resource_uri: str,
        label: str,
    ) -> None:
        """Record that a requested type label was not found."""
        ...

    def with_context(self, context: ObservationContext) -> SchemaResourceProbe:
        """Create a new probe with observation context bound."""
        ...


class DefaultSchemaResourceProbe:
    """Default implementation using structlog."""

    def __init__(
        self,
        logger: structlog.stdlib.BoundLogger | None = None,
        context: ObservationContext | None = None,
    ):
        self._logger = logger or structlog.get_logger()
        self._context = context

    def _get_context_kwargs(self) -> dict[str, Any]:
        if self._context is None:
            return {}
        return self._context.as_dict()

    def with_context(self, context: ObservationContext) -> DefaultSchemaResourceProbe:
        return DefaultSchemaResourceProbe(logger=self._logger, context=context)

    def schema_resource_accessed(
        self, resource_uri: str, label: str | None = None
    ) -> None:
        self._logger.info(
            "mcp_schema_resource_accessed",
            resource_uri=resource_uri,
            label=label,
            **self._get_context_kwargs(),
        )

    def schema_resource_returned(
        self, resource_uri: str, result_count: int | None = None, found: bool = True
    ) -> None:
        self._logger.info(
            "mcp_schema_resource_returned",
            resource_uri=resource_uri,
            result_count=result_count,
            found=found,
            **self._get_context_kwargs(),
        )

    def schema_type_not_found(self, resource_uri: str, label: str) -> None:
        self._logger.warning(
            "mcp_schema_type_not_found",
            resource_uri=resource_uri,
            label=label,
            **self._get_context_kwargs(),
        )
