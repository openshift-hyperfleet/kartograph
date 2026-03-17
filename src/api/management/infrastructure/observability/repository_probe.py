"""Domain probes for Management repository operations.

Following Domain-Oriented Observability patterns, these probes capture
domain-significant events related to knowledge graph and data source
repository operations.
"""

from __future__ import annotations

from typing import Protocol

import structlog


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


class DefaultKnowledgeGraphRepositoryProbe:
    """Default implementation of KnowledgeGraphRepositoryProbe using structlog."""

    def __init__(
        self,
        logger: structlog.stdlib.BoundLogger | None = None,
    ) -> None:
        self._logger = logger or structlog.get_logger()

    def knowledge_graph_saved(self, knowledge_graph_id: str, tenant_id: str) -> None:
        self._logger.info(
            "knowledge_graph_saved",
            knowledge_graph_id=knowledge_graph_id,
            tenant_id=tenant_id,
        )

    def knowledge_graph_retrieved(self, knowledge_graph_id: str) -> None:
        self._logger.debug(
            "knowledge_graph_retrieved",
            knowledge_graph_id=knowledge_graph_id,
        )

    def knowledge_graph_not_found(self, knowledge_graph_id: str) -> None:
        self._logger.debug(
            "knowledge_graph_not_found",
            knowledge_graph_id=knowledge_graph_id,
        )

    def knowledge_graph_deleted(self, knowledge_graph_id: str) -> None:
        self._logger.info(
            "knowledge_graph_deleted",
            knowledge_graph_id=knowledge_graph_id,
        )

    def knowledge_graphs_listed(self, tenant_id: str, count: int) -> None:
        self._logger.debug(
            "knowledge_graphs_listed",
            tenant_id=tenant_id,
            count=count,
        )

    def duplicate_knowledge_graph_name(self, name: str, tenant_id: str) -> None:
        self._logger.warning(
            "duplicate_knowledge_graph_name",
            name=name,
            tenant_id=tenant_id,
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


class DefaultDataSourceRepositoryProbe:
    """Default implementation of DataSourceRepositoryProbe using structlog."""

    def __init__(
        self,
        logger: structlog.stdlib.BoundLogger | None = None,
    ) -> None:
        self._logger = logger or structlog.get_logger()

    def data_source_saved(self, data_source_id: str, knowledge_graph_id: str) -> None:
        self._logger.info(
            "data_source_saved",
            data_source_id=data_source_id,
            knowledge_graph_id=knowledge_graph_id,
        )

    def data_source_retrieved(self, data_source_id: str) -> None:
        self._logger.debug(
            "data_source_retrieved",
            data_source_id=data_source_id,
        )

    def data_source_not_found(self, data_source_id: str) -> None:
        self._logger.debug(
            "data_source_not_found",
            data_source_id=data_source_id,
        )

    def data_source_deleted(self, data_source_id: str) -> None:
        self._logger.info(
            "data_source_deleted",
            data_source_id=data_source_id,
        )

    def data_sources_listed(self, knowledge_graph_id: str, count: int) -> None:
        self._logger.debug(
            "data_sources_listed",
            knowledge_graph_id=knowledge_graph_id,
            count=count,
        )

    def duplicate_data_source_name(self, name: str, knowledge_graph_id: str) -> None:
        self._logger.warning(
            "duplicate_data_source_name",
            name=name,
            knowledge_graph_id=knowledge_graph_id,
        )
