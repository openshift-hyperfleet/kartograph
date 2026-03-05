"""Observability probes for KnowledgeGraph aggregate.

Domain probes for KnowledgeGraph following Domain Oriented Observability pattern.
Probes emit structured logs with domain-specific context for knowledge graph
lifecycle operations (create, update, delete).

See: https://martinfowler.com/articles/domain-oriented-observability.html
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import structlog


@runtime_checkable
class KnowledgeGraphProbe(Protocol):
    """Protocol for knowledge graph aggregate observability probes.

    Defines the interface for domain probes that capture aggregate-level
    domain events for knowledge graph lifecycle operations.
    """

    def created(
        self,
        knowledge_graph_id: str,
        tenant_id: str,
        workspace_id: str,
        name: str,
    ) -> None:
        """Probe emitted when a knowledge graph is created.

        Args:
            knowledge_graph_id: The knowledge graph ID
            tenant_id: The owning tenant ID
            workspace_id: The containing workspace ID
            name: The name of the knowledge graph
        """
        ...

    def updated(
        self,
        knowledge_graph_id: str,
        tenant_id: str,
        name: str,
    ) -> None:
        """Probe emitted when a knowledge graph is updated.

        Args:
            knowledge_graph_id: The knowledge graph ID
            tenant_id: The owning tenant ID
            name: The updated name
        """
        ...

    def deleted(
        self,
        knowledge_graph_id: str,
        tenant_id: str,
        workspace_id: str,
    ) -> None:
        """Probe emitted when a knowledge graph is deleted.

        Args:
            knowledge_graph_id: The knowledge graph ID
            tenant_id: The owning tenant ID
            workspace_id: The containing workspace ID
        """
        ...


class DefaultKnowledgeGraphProbe:
    """Default implementation of KnowledgeGraphProbe using structlog."""

    def __init__(
        self,
        logger: structlog.stdlib.BoundLogger | None = None,
    ) -> None:
        self._logger = logger or structlog.get_logger()

    def created(
        self,
        knowledge_graph_id: str,
        tenant_id: str,
        workspace_id: str,
        name: str,
    ) -> None:
        """Log knowledge graph creation with structured context."""
        self._logger.info(
            "knowledge_graph_created",
            knowledge_graph_id=knowledge_graph_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            name=name,
        )

    def updated(
        self,
        knowledge_graph_id: str,
        tenant_id: str,
        name: str,
    ) -> None:
        """Log knowledge graph update with structured context."""
        self._logger.info(
            "knowledge_graph_updated",
            knowledge_graph_id=knowledge_graph_id,
            tenant_id=tenant_id,
            name=name,
        )

    def deleted(
        self,
        knowledge_graph_id: str,
        tenant_id: str,
        workspace_id: str,
    ) -> None:
        """Log knowledge graph deletion with structured context."""
        self._logger.info(
            "knowledge_graph_deleted",
            knowledge_graph_id=knowledge_graph_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
        )
