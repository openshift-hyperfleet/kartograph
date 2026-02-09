"""Protocol for workspace application service observability.

Defines the interface for domain probes that capture application-level
domain events for workspace service operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

import structlog

if TYPE_CHECKING:
    from shared_kernel.observability_context import ObservationContext


class WorkspaceServiceProbe(Protocol):
    """Domain probe for workspace application service operations.

    Records domain-significant events related to workspace operations.
    """

    def workspace_created(
        self,
        workspace_id: str,
        tenant_id: str,
        name: str,
        parent_workspace_id: str | None,
        is_root: bool,
        creator_id: str,
    ) -> None:
        """Record workspace creation."""
        ...

    def workspace_creation_failed(
        self,
        tenant_id: str,
        name: str,
        error: str,
    ) -> None:
        """Record failed workspace creation."""
        ...

    def workspace_retrieved(
        self,
        workspace_id: str,
        tenant_id: str,
        name: str,
    ) -> None:
        """Record workspace retrieval."""
        ...

    def workspace_not_found(
        self,
        workspace_id: str,
    ) -> None:
        """Record workspace not found."""
        ...

    def workspaces_listed(
        self,
        tenant_id: str,
        count: int,
    ) -> None:
        """Record workspaces listed."""
        ...

    def workspace_deleted(
        self,
        workspace_id: str,
        tenant_id: str,
    ) -> None:
        """Record workspace deletion."""
        ...

    def workspace_deletion_failed(
        self,
        workspace_id: str,
        error: str,
    ) -> None:
        """Record failed workspace deletion."""
        ...

    def with_context(self, context: ObservationContext) -> WorkspaceServiceProbe:
        """Return a new probe with additional context."""
        ...


class DefaultWorkspaceServiceProbe:
    """Default implementation of WorkspaceServiceProbe using structlog."""

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

    def with_context(self, context: ObservationContext) -> DefaultWorkspaceServiceProbe:
        """Create a new probe with observation context bound."""
        return DefaultWorkspaceServiceProbe(logger=self._logger, context=context)

    def workspace_created(
        self,
        workspace_id: str,
        tenant_id: str,
        name: str,
        parent_workspace_id: str | None,
        is_root: bool,
        creator_id: str,
    ) -> None:
        """Record workspace creation."""
        self._logger.info(
            "workspace_created",
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            name=name,
            parent_workspace_id=parent_workspace_id,
            is_root=is_root,
            creator_id=creator_id,
            **self._get_context_kwargs(),
        )

    def workspace_creation_failed(
        self,
        tenant_id: str,
        name: str,
        error: str,
    ) -> None:
        """Record failed workspace creation."""
        self._logger.error(
            "workspace_creation_failed",
            tenant_id=tenant_id,
            name=name,
            error=error,
            **self._get_context_kwargs(),
        )

    def workspace_retrieved(
        self,
        workspace_id: str,
        tenant_id: str,
        name: str,
    ) -> None:
        """Record workspace retrieval."""
        self._logger.debug(
            "workspace_retrieved",
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            name=name,
            **self._get_context_kwargs(),
        )

    def workspace_not_found(
        self,
        workspace_id: str,
    ) -> None:
        """Record workspace not found."""
        self._logger.debug(
            "workspace_not_found",
            workspace_id=workspace_id,
            **self._get_context_kwargs(),
        )

    def workspaces_listed(
        self,
        tenant_id: str,
        count: int,
    ) -> None:
        """Record workspaces listed."""
        self._logger.debug(
            "workspaces_listed",
            tenant_id=tenant_id,
            count=count,
            **self._get_context_kwargs(),
        )

    def workspace_deleted(
        self,
        workspace_id: str,
        tenant_id: str,
    ) -> None:
        """Record workspace deletion."""
        self._logger.info(
            "workspace_deleted",
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            **self._get_context_kwargs(),
        )

    def workspace_deletion_failed(
        self,
        workspace_id: str,
        error: str,
    ) -> None:
        """Record failed workspace deletion."""
        self._logger.error(
            "workspace_deletion_failed",
            workspace_id=workspace_id,
            error=error,
            **self._get_context_kwargs(),
        )
