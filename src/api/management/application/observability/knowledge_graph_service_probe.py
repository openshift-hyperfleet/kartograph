"""Protocol for knowledge graph application service observability.

Defines the interface for domain probes that capture application-level
domain events for knowledge graph service operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

import structlog

if TYPE_CHECKING:
    from shared_kernel.observability_context import ObservationContext


class KnowledgeGraphServiceProbe(Protocol):
    """Domain probe for knowledge graph application service operations.

    Records domain-significant events related to knowledge graph operations.
    """

    def knowledge_graph_created(
        self,
        kg_id: str,
        tenant_id: str,
        workspace_id: str,
        name: str,
    ) -> None:
        """Record knowledge graph creation."""
        ...

    def knowledge_graph_creation_failed(
        self,
        tenant_id: str,
        name: str,
        error: str,
    ) -> None:
        """Record failed knowledge graph creation."""
        ...

    def knowledge_graph_retrieved(
        self,
        kg_id: str,
    ) -> None:
        """Record knowledge graph retrieval."""
        ...

    def knowledge_graph_updated(
        self,
        kg_id: str,
        name: str,
    ) -> None:
        """Record knowledge graph update."""
        ...

    def knowledge_graph_deleted(
        self,
        kg_id: str,
    ) -> None:
        """Record knowledge graph deletion."""
        ...

    def knowledge_graph_deletion_failed(
        self,
        kg_id: str,
        error: str,
    ) -> None:
        """Record failed knowledge graph deletion."""
        ...

    def knowledge_graphs_listed(
        self,
        workspace_id: str,
        count: int,
    ) -> None:
        """Record knowledge graphs listed."""
        ...

    def permission_denied(
        self,
        user_id: str,
        resource_id: str,
        permission: str,
    ) -> None:
        """Record permission denied."""
        ...

    def with_context(self, context: ObservationContext) -> KnowledgeGraphServiceProbe:
        """Return a new probe with additional context."""
        ...


class DefaultKnowledgeGraphServiceProbe:
    """Default implementation of KnowledgeGraphServiceProbe using structlog."""

    def __init__(
        self,
        logger: structlog.stdlib.BoundLogger | None = None,
        context: ObservationContext | None = None,
    ):
        self._logger = logger or structlog.get_logger()
        self._context = context

    def _get_context_kwargs(self, exclude: set[str] | None = None) -> dict[str, Any]:
        """Get context as kwargs dict, excluding specified keys.

        Args:
            exclude: Set of keys to exclude from context (avoids parameter collision)

        Returns:
            Context dict with excluded keys filtered out
        """
        if self._context is None:
            return {}

        context_dict = self._context.as_dict()
        if exclude:
            return {k: v for k, v in context_dict.items() if k not in exclude}
        return context_dict

    def with_context(
        self, context: ObservationContext
    ) -> DefaultKnowledgeGraphServiceProbe:
        """Create a new probe with observation context bound."""
        return DefaultKnowledgeGraphServiceProbe(logger=self._logger, context=context)

    def knowledge_graph_created(
        self,
        kg_id: str,
        tenant_id: str,
        workspace_id: str,
        name: str,
    ) -> None:
        """Record knowledge graph creation."""
        context_kwargs = self._get_context_kwargs(
            exclude={"kg_id", "tenant_id", "workspace_id", "name"}
        )
        self._logger.info(
            "knowledge_graph_created",
            kg_id=kg_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            name=name,
            **context_kwargs,
        )

    def knowledge_graph_creation_failed(
        self,
        tenant_id: str,
        name: str,
        error: str,
    ) -> None:
        """Record failed knowledge graph creation."""
        context_kwargs = self._get_context_kwargs(
            exclude={"tenant_id", "name", "error"}
        )
        self._logger.error(
            "knowledge_graph_creation_failed",
            tenant_id=tenant_id,
            name=name,
            error=error,
            **context_kwargs,
        )

    def knowledge_graph_retrieved(
        self,
        kg_id: str,
    ) -> None:
        """Record knowledge graph retrieval."""
        context_kwargs = self._get_context_kwargs(exclude={"kg_id"})
        self._logger.debug(
            "knowledge_graph_retrieved",
            kg_id=kg_id,
            **context_kwargs,
        )

    def knowledge_graph_updated(
        self,
        kg_id: str,
        name: str,
    ) -> None:
        """Record knowledge graph update."""
        context_kwargs = self._get_context_kwargs(exclude={"kg_id", "name"})
        self._logger.info(
            "knowledge_graph_updated",
            kg_id=kg_id,
            name=name,
            **context_kwargs,
        )

    def knowledge_graph_deleted(
        self,
        kg_id: str,
    ) -> None:
        """Record knowledge graph deletion."""
        context_kwargs = self._get_context_kwargs(exclude={"kg_id"})
        self._logger.info(
            "knowledge_graph_deleted",
            kg_id=kg_id,
            **context_kwargs,
        )

    def knowledge_graph_deletion_failed(
        self,
        kg_id: str,
        error: str,
    ) -> None:
        """Record failed knowledge graph deletion."""
        context_kwargs = self._get_context_kwargs(exclude={"kg_id", "error"})
        self._logger.error(
            "knowledge_graph_deletion_failed",
            kg_id=kg_id,
            error=error,
            **context_kwargs,
        )

    def knowledge_graphs_listed(
        self,
        workspace_id: str,
        count: int,
    ) -> None:
        """Record knowledge graphs listed."""
        context_kwargs = self._get_context_kwargs(exclude={"workspace_id", "count"})
        self._logger.debug(
            "knowledge_graphs_listed",
            workspace_id=workspace_id,
            count=count,
            **context_kwargs,
        )

    def permission_denied(
        self,
        user_id: str,
        resource_id: str,
        permission: str,
    ) -> None:
        """Record permission denied."""
        context_kwargs = self._get_context_kwargs(
            exclude={"user_id", "resource_id", "permission"}
        )
        self._logger.warning(
            "knowledge_graph_permission_denied",
            user_id=user_id,
            resource_id=resource_id,
            permission=permission,
            **context_kwargs,
        )
