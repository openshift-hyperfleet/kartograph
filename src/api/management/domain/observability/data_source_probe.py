"""Observability probes for DataSource aggregate.

Domain probes for DataSource following Domain Oriented Observability pattern.
Probes emit structured logs with domain-specific context for data source
lifecycle operations (create, update, delete, sync).

See: https://martinfowler.com/articles/domain-oriented-observability.html
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import structlog


@runtime_checkable
class DataSourceProbe(Protocol):
    """Protocol for data source aggregate observability probes.

    Defines the interface for domain probes that capture aggregate-level
    domain events for data source lifecycle operations.
    """

    def created(
        self,
        data_source_id: str,
        knowledge_graph_id: str,
        tenant_id: str,
        name: str,
        adapter_type: str,
    ) -> None:
        """Probe emitted when a data source is created.

        Args:
            data_source_id: The data source ID
            knowledge_graph_id: The parent knowledge graph ID
            tenant_id: The owning tenant ID
            name: The name of the data source
            adapter_type: The adapter type (e.g., "github")
        """
        ...

    def updated(
        self,
        data_source_id: str,
        knowledge_graph_id: str,
        tenant_id: str,
        name: str,
    ) -> None:
        """Probe emitted when a data source is updated.

        Args:
            data_source_id: The data source ID
            knowledge_graph_id: The parent knowledge graph ID
            tenant_id: The owning tenant ID
            name: The current name of the data source
        """
        ...

    def deleted(
        self,
        data_source_id: str,
        knowledge_graph_id: str,
        tenant_id: str,
    ) -> None:
        """Probe emitted when a data source is deleted.

        Args:
            data_source_id: The data source ID
            knowledge_graph_id: The parent knowledge graph ID
            tenant_id: The owning tenant ID
        """
        ...

    def sync_completed(
        self,
        data_source_id: str,
        knowledge_graph_id: str,
        tenant_id: str,
    ) -> None:
        """Probe emitted when a data source sync completes.

        Args:
            data_source_id: The data source ID
            knowledge_graph_id: The parent knowledge graph ID
            tenant_id: The owning tenant ID
        """
        ...


class DefaultDataSourceProbe:
    """Default implementation of DataSourceProbe using structlog."""

    def __init__(
        self,
        logger: structlog.stdlib.BoundLogger | None = None,
    ) -> None:
        self._logger = logger or structlog.get_logger()

    def created(
        self,
        data_source_id: str,
        knowledge_graph_id: str,
        tenant_id: str,
        name: str,
        adapter_type: str,
    ) -> None:
        """Log data source creation with structured context."""
        self._logger.info(
            "data_source_created",
            data_source_id=data_source_id,
            knowledge_graph_id=knowledge_graph_id,
            tenant_id=tenant_id,
            name=name,
            adapter_type=adapter_type,
        )

    def updated(
        self,
        data_source_id: str,
        knowledge_graph_id: str,
        tenant_id: str,
        name: str,
    ) -> None:
        """Log data source update with structured context."""
        self._logger.info(
            "data_source_updated",
            data_source_id=data_source_id,
            knowledge_graph_id=knowledge_graph_id,
            tenant_id=tenant_id,
            name=name,
        )

    def deleted(
        self,
        data_source_id: str,
        knowledge_graph_id: str,
        tenant_id: str,
    ) -> None:
        """Log data source deletion with structured context."""
        self._logger.info(
            "data_source_deleted",
            data_source_id=data_source_id,
            knowledge_graph_id=knowledge_graph_id,
            tenant_id=tenant_id,
        )

    def sync_completed(
        self,
        data_source_id: str,
        knowledge_graph_id: str,
        tenant_id: str,
    ) -> None:
        """Log data source sync completion with structured context."""
        self._logger.info(
            "data_source_sync_completed",
            data_source_id=data_source_id,
            knowledge_graph_id=knowledge_graph_id,
            tenant_id=tenant_id,
        )
