"""Domain probes for Management repository operations.

Following Domain-Oriented Observability patterns, these probes capture
domain-significant events related to knowledge graph, data source,
and sync run repository operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

import structlog

if TYPE_CHECKING:
    from shared_kernel.observability_context import ObservationContext


class KnowledgeGraphRepositoryProbe(Protocol):
    """Domain probe for knowledge graph repository operations."""

    def knowledge_graph_saved(self, knowledge_graph_id: str, tenant_id: str) -> None:
        """Record that a knowledge graph was successfully saved."""
        ...

    def knowledge_graph_retrieved(self, knowledge_graph_id: str) -> None:
        """Record that a knowledge graph was retrieved."""
        ...

    def knowledge_graph_not_found(self, knowledge_graph_id: str) -> None:
        """Record that a knowledge graph was not found."""
        ...

    def knowledge_graph_deleted(self, knowledge_graph_id: str) -> None:
        """Record that a knowledge graph was deleted."""
        ...

    def knowledge_graphs_listed(self, tenant_id: str, count: int) -> None:
        """Record that knowledge graphs were listed for a tenant."""
        ...

    def duplicate_knowledge_graph_name(self, name: str, tenant_id: str) -> None:
        """Record that a duplicate knowledge graph name was detected."""
        ...

    def with_context(
        self, context: ObservationContext
    ) -> KnowledgeGraphRepositoryProbe:
        """Create a new probe with observation context bound."""
        ...


class DefaultKnowledgeGraphRepositoryProbe:
    """Default implementation of KnowledgeGraphRepositoryProbe using structlog."""

    def __init__(
        self,
        logger: structlog.stdlib.BoundLogger | None = None,
        context: ObservationContext | None = None,
    ) -> None:
        self._logger = logger or structlog.get_logger()
        self._context = context

    def _get_context_kwargs(self) -> dict[str, Any]:
        if self._context is None:
            return {}
        return self._context.as_dict()

    def with_context(
        self, context: ObservationContext
    ) -> DefaultKnowledgeGraphRepositoryProbe:
        return DefaultKnowledgeGraphRepositoryProbe(
            logger=self._logger, context=context
        )

    def knowledge_graph_saved(self, knowledge_graph_id: str, tenant_id: str) -> None:
        self._logger.info(
            "knowledge_graph_saved",
            knowledge_graph_id=knowledge_graph_id,
            tenant_id=tenant_id,
            **self._get_context_kwargs(),
        )

    def knowledge_graph_retrieved(self, knowledge_graph_id: str) -> None:
        self._logger.debug(
            "knowledge_graph_retrieved",
            knowledge_graph_id=knowledge_graph_id,
            **self._get_context_kwargs(),
        )

    def knowledge_graph_not_found(self, knowledge_graph_id: str) -> None:
        self._logger.debug(
            "knowledge_graph_not_found",
            knowledge_graph_id=knowledge_graph_id,
            **self._get_context_kwargs(),
        )

    def knowledge_graph_deleted(self, knowledge_graph_id: str) -> None:
        self._logger.info(
            "knowledge_graph_deleted",
            knowledge_graph_id=knowledge_graph_id,
            **self._get_context_kwargs(),
        )

    def knowledge_graphs_listed(self, tenant_id: str, count: int) -> None:
        self._logger.debug(
            "knowledge_graphs_listed",
            tenant_id=tenant_id,
            count=count,
            **self._get_context_kwargs(),
        )

    def duplicate_knowledge_graph_name(self, name: str, tenant_id: str) -> None:
        self._logger.warning(
            "duplicate_knowledge_graph_name",
            name=name,
            tenant_id=tenant_id,
            **self._get_context_kwargs(),
        )


class DataSourceRepositoryProbe(Protocol):
    """Domain probe for data source repository operations."""

    def data_source_saved(self, data_source_id: str, knowledge_graph_id: str) -> None:
        """Record that a data source was successfully saved."""
        ...

    def data_source_retrieved(self, data_source_id: str) -> None:
        """Record that a data source was retrieved."""
        ...

    def data_source_not_found(self, data_source_id: str) -> None:
        """Record that a data source was not found."""
        ...

    def data_source_deleted(self, data_source_id: str) -> None:
        """Record that a data source was deleted."""
        ...

    def data_sources_listed(self, knowledge_graph_id: str, count: int) -> None:
        """Record that data sources were listed for a knowledge graph."""
        ...

    def duplicate_data_source_name(self, name: str, knowledge_graph_id: str) -> None:
        """Record that a duplicate data source name was detected."""
        ...

    def with_context(self, context: ObservationContext) -> DataSourceRepositoryProbe:
        """Create a new probe with observation context bound."""
        ...


class DefaultDataSourceRepositoryProbe:
    """Default implementation of DataSourceRepositoryProbe using structlog."""

    def __init__(
        self,
        logger: structlog.stdlib.BoundLogger | None = None,
        context: ObservationContext | None = None,
    ) -> None:
        self._logger = logger or structlog.get_logger()
        self._context = context

    def _get_context_kwargs(self) -> dict[str, Any]:
        if self._context is None:
            return {}
        return self._context.as_dict()

    def with_context(
        self, context: ObservationContext
    ) -> DefaultDataSourceRepositoryProbe:
        return DefaultDataSourceRepositoryProbe(logger=self._logger, context=context)

    def data_source_saved(self, data_source_id: str, knowledge_graph_id: str) -> None:
        self._logger.info(
            "data_source_saved",
            data_source_id=data_source_id,
            knowledge_graph_id=knowledge_graph_id,
            **self._get_context_kwargs(),
        )

    def data_source_retrieved(self, data_source_id: str) -> None:
        self._logger.debug(
            "data_source_retrieved",
            data_source_id=data_source_id,
            **self._get_context_kwargs(),
        )

    def data_source_not_found(self, data_source_id: str) -> None:
        self._logger.debug(
            "data_source_not_found",
            data_source_id=data_source_id,
            **self._get_context_kwargs(),
        )

    def data_source_deleted(self, data_source_id: str) -> None:
        self._logger.info(
            "data_source_deleted",
            data_source_id=data_source_id,
            **self._get_context_kwargs(),
        )

    def data_sources_listed(self, knowledge_graph_id: str, count: int) -> None:
        self._logger.debug(
            "data_sources_listed",
            knowledge_graph_id=knowledge_graph_id,
            count=count,
            **self._get_context_kwargs(),
        )

    def duplicate_data_source_name(self, name: str, knowledge_graph_id: str) -> None:
        self._logger.warning(
            "duplicate_data_source_name",
            name=name,
            knowledge_graph_id=knowledge_graph_id,
            **self._get_context_kwargs(),
        )


class SyncRunRepositoryProbe(Protocol):
    """Domain probe for sync run repository operations."""

    def sync_run_saved(self, sync_run_id: str, data_source_id: str) -> None:
        """Record that a sync run was successfully saved."""
        ...

    def sync_run_retrieved(self, sync_run_id: str) -> None:
        """Record that a sync run was retrieved."""
        ...

    def sync_run_not_found(self, sync_run_id: str) -> None:
        """Record that a sync run was not found."""
        ...

    def sync_runs_listed(self, data_source_id: str, count: int) -> None:
        """Record that sync runs were listed for a data source."""
        ...

    def with_context(self, context: ObservationContext) -> SyncRunRepositoryProbe:
        """Create a new probe with observation context bound."""
        ...


class DefaultSyncRunRepositoryProbe:
    """Default implementation of SyncRunRepositoryProbe using structlog."""

    def __init__(
        self,
        logger: structlog.stdlib.BoundLogger | None = None,
        context: ObservationContext | None = None,
    ) -> None:
        self._logger = logger or structlog.get_logger()
        self._context = context

    def _get_context_kwargs(self) -> dict[str, Any]:
        if self._context is None:
            return {}
        return self._context.as_dict()

    def with_context(
        self, context: ObservationContext
    ) -> DefaultSyncRunRepositoryProbe:
        return DefaultSyncRunRepositoryProbe(logger=self._logger, context=context)

    def sync_run_saved(self, sync_run_id: str, data_source_id: str) -> None:
        self._logger.info(
            "sync_run_saved",
            sync_run_id=sync_run_id,
            data_source_id=data_source_id,
            **self._get_context_kwargs(),
        )

    def sync_run_retrieved(self, sync_run_id: str) -> None:
        self._logger.debug(
            "sync_run_retrieved",
            sync_run_id=sync_run_id,
            **self._get_context_kwargs(),
        )

    def sync_run_not_found(self, sync_run_id: str) -> None:
        self._logger.debug(
            "sync_run_not_found",
            sync_run_id=sync_run_id,
            **self._get_context_kwargs(),
        )

    def sync_runs_listed(self, data_source_id: str, count: int) -> None:
        self._logger.debug(
            "sync_runs_listed",
            data_source_id=data_source_id,
            count=count,
            **self._get_context_kwargs(),
        )
