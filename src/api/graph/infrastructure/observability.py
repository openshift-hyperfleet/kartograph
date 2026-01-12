"""Domain probes for Graph bounded context observability.

These probes capture domain-significant events related to graph operations,
following the Domain Oriented Observability pattern.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

import structlog

if TYPE_CHECKING:
    from shared_kernel.observability_context import ObservationContext


class GraphClientProbe(Protocol):
    """Domain probe for graph client observability.

    This probe captures domain-significant events related to graph
    database operations without exposing logging implementation details.
    """

    def connected_to_graph(self, graph_name: str) -> None:
        """Record successful connection to a graph."""
        ...

    def graph_created(self, graph_name: str) -> None:
        """Record that a new graph was created."""
        ...

    def connection_verification_failed(self, error: Exception) -> None:
        """Record that connection verification failed."""
        ...

    def query_failed(self, query: str, error: Exception) -> None:
        """Record that a Cypher query execution failed."""
        ...

    def query_executed(self, query: str, row_count: int) -> None:
        """Record successful Cypher query execution."""
        ...

    def transaction_started(self) -> None:
        """Record that a transaction was started."""
        ...

    def transaction_committed(self) -> None:
        """Record that a transaction was committed."""
        ...

    def transaction_rolled_back(self) -> None:
        """Record that a transaction was rolled back."""
        ...

    def with_context(self, context: ObservationContext) -> GraphClientProbe:
        """Create a new probe with observation context bound."""
        ...


class DefaultGraphClientProbe:
    """Default implementation of GraphClientProbe using structlog.

    Supports observation context for including request-scoped metadata
    with all log events.
    """

    def __init__(
        self,
        logger: structlog.stdlib.BoundLogger | None = None,
        context: ObservationContext | None = None,
    ):
        self._logger = logger or structlog.get_logger()
        self._context = context

    def _get_context_kwargs(self) -> dict[str, Any]:
        """Get context metadata as kwargs for logging."""
        if self._context is None:
            return {}
        return self._context.as_dict()

    def with_context(self, context: ObservationContext) -> DefaultGraphClientProbe:
        """Create a new probe with observation context bound."""
        return DefaultGraphClientProbe(logger=self._logger, context=context)

    def connected_to_graph(self, graph_name: str) -> None:
        """Record successful connection to a graph."""
        self._logger.info(
            "graph_connected",
            graph_name=graph_name,
            **self._get_context_kwargs(),
        )

    def graph_created(self, graph_name: str) -> None:
        """Record that a new graph was created."""
        self._logger.info(
            "graph_created",
            graph_name=graph_name,
            **self._get_context_kwargs(),
        )

    def connection_verification_failed(self, error: Exception) -> None:
        """Record that connection verification failed."""
        self._logger.warning(
            "graph_connection_verification_failed",
            error=str(error),
            **self._get_context_kwargs(),
        )

    def query_failed(self, query: str, error: Exception) -> None:
        """Record that a Cypher query execution failed."""
        self._logger.error(
            "graph_query_failed",
            query=query,
            error=str(error),
            **self._get_context_kwargs(),
        )

    def query_executed(self, query: str, row_count: int) -> None:
        """Record successful Cypher query execution."""
        self._logger.debug(
            "graph_query_executed",
            query=query,
            row_count=row_count,
            **self._get_context_kwargs(),
        )

    def transaction_started(self) -> None:
        """Record that a transaction was started."""
        self._logger.info(
            "graph_transaction_started",
            **self._get_context_kwargs(),
        )

    def transaction_committed(self) -> None:
        """Record that a transaction was committed."""
        self._logger.info(
            "graph_transaction_committed",
            **self._get_context_kwargs(),
        )

    def transaction_rolled_back(self) -> None:
        """Record that a transaction was rolled back."""
        self._logger.warning(
            "graph_transaction_rolled_back",
            **self._get_context_kwargs(),
        )


# Re-export MutationProbe protocol from ports for backwards compatibility


class DefaultMutationProbe:
    """Default implementation of MutationProbe using structlog."""

    def __init__(
        self,
        logger: structlog.stdlib.BoundLogger | None = None,
        context: ObservationContext | None = None,
    ):
        self._logger = logger or structlog.get_logger()
        self._context = context

    def _get_context_kwargs(self) -> dict[str, Any]:
        """Get context metadata as kwargs for logging."""
        if self._context is None:
            return {}
        return self._context.as_dict()

    def with_context(self, context: ObservationContext) -> DefaultMutationProbe:
        """Create a new probe with observation context bound."""
        return DefaultMutationProbe(logger=self._logger, context=context)

    def mutation_applied(
        self,
        operation: str,
        entity_type: str,
        entity_id: str | None,
    ) -> None:
        """Record that a mutation was successfully applied."""
        self._logger.info(
            "mutation_applied",
            operation=operation,
            entity_type=entity_type,
            entity_id=entity_id,
            **self._get_context_kwargs(),
        )

    def batch_applied(
        self,
        operation: str,
        entity_type: str,
        label: str | None,
        count: int,
        duration_ms: float,
    ) -> None:
        """Record that a batch of mutations was successfully applied."""
        self._logger.info(
            "mutation_batch_applied",
            operation=operation,
            entity_type=entity_type,
            label=label,
            count=count,
            duration_ms=round(duration_ms, 2),
            **self._get_context_kwargs(),
        )

    def apply_batch_completed(
        self,
        total_operations: int,
        total_batches: int,
        duration_ms: float,
        success: bool,
    ) -> None:
        """Record completion of the entire apply_batch operation."""
        self._logger.info(
            "mutation_apply_batch_completed",
            total_operations=total_operations,
            total_batches=total_batches,
            duration_ms=round(duration_ms, 2),
            success=success,
            **self._get_context_kwargs(),
        )

    def duplicate_ids_detected(
        self,
        duplicate_ids: list[str],
        entity_type: str,
    ) -> None:
        """Record that duplicate IDs were detected in a batch."""
        self._logger.warning(
            "mutation_duplicate_ids_detected",
            duplicate_ids=duplicate_ids,
            entity_type=entity_type,
            count=len(duplicate_ids),
            **self._get_context_kwargs(),
        )
