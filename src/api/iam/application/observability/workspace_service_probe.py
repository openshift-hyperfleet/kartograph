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
        user_id: str = "",
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

    def workspace_access_denied(
        self,
        workspace_id: str,
        user_id: str,
        permission: str,
    ) -> None:
        """Record workspace access denied."""
        ...

    def workspace_member_added(
        self,
        workspace_id: str,
        member_id: str,
        member_type: str,
        role: str,
        acting_user_id: str,
    ) -> None:
        """Record workspace member addition."""
        ...

    def workspace_member_removed(
        self,
        workspace_id: str,
        member_id: str,
        member_type: str,
        acting_user_id: str,
    ) -> None:
        """Record workspace member removal."""
        ...

    def workspace_member_role_changed(
        self,
        workspace_id: str,
        member_id: str,
        member_type: str,
        new_role: str,
        acting_user_id: str,
    ) -> None:
        """Record workspace member role change."""
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
        context_kwargs = self._get_context_kwargs(
            exclude={
                "workspace_id",
                "tenant_id",
                "name",
                "parent_workspace_id",
                "is_root",
                "creator_id",
            }
        )
        self._logger.info(
            "workspace_created",
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            name=name,
            parent_workspace_id=parent_workspace_id,
            is_root=is_root,
            creator_id=creator_id,
            **context_kwargs,
        )

    def workspace_creation_failed(
        self,
        tenant_id: str,
        name: str,
        error: str,
    ) -> None:
        """Record failed workspace creation."""
        context_kwargs = self._get_context_kwargs(
            exclude={"tenant_id", "name", "error"}
        )
        self._logger.error(
            "workspace_creation_failed",
            tenant_id=tenant_id,
            name=name,
            error=error,
            **context_kwargs,
        )

    def workspace_retrieved(
        self,
        workspace_id: str,
        tenant_id: str,
        name: str,
    ) -> None:
        """Record workspace retrieval."""
        context_kwargs = self._get_context_kwargs(
            exclude={"workspace_id", "tenant_id", "name"}
        )
        self._logger.debug(
            "workspace_retrieved",
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            name=name,
            **context_kwargs,
        )

    def workspace_not_found(
        self,
        workspace_id: str,
    ) -> None:
        """Record workspace not found."""
        context_kwargs = self._get_context_kwargs(exclude={"workspace_id"})
        self._logger.debug(
            "workspace_not_found",
            workspace_id=workspace_id,
            **context_kwargs,
        )

    def workspaces_listed(
        self,
        tenant_id: str,
        count: int,
        user_id: str = "",
    ) -> None:
        """Record workspaces listed."""
        context_kwargs = self._get_context_kwargs(
            exclude={"tenant_id", "count", "user_id"}
        )
        self._logger.debug(
            "workspaces_listed",
            tenant_id=tenant_id,
            count=count,
            user_id=user_id,
            **context_kwargs,
        )

    def workspace_deleted(
        self,
        workspace_id: str,
        tenant_id: str,
    ) -> None:
        """Record workspace deletion."""
        context_kwargs = self._get_context_kwargs(exclude={"workspace_id", "tenant_id"})
        self._logger.info(
            "workspace_deleted",
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            **context_kwargs,
        )

    def workspace_deletion_failed(
        self,
        workspace_id: str,
        error: str,
    ) -> None:
        """Record failed workspace deletion."""
        context_kwargs = self._get_context_kwargs(exclude={"workspace_id", "error"})
        self._logger.error(
            "workspace_deletion_failed",
            workspace_id=workspace_id,
            error=error,
            **context_kwargs,
        )

    def workspace_access_denied(
        self,
        workspace_id: str,
        user_id: str,
        permission: str,
    ) -> None:
        """Record workspace access denied."""
        context_kwargs = self._get_context_kwargs(
            exclude={"workspace_id", "user_id", "permission"}
        )
        self._logger.warning(
            "workspace_access_denied",
            workspace_id=workspace_id,
            user_id=user_id,
            permission=permission,
            **context_kwargs,
        )

    def workspace_member_added(
        self,
        workspace_id: str,
        member_id: str,
        member_type: str,
        role: str,
        acting_user_id: str,
    ) -> None:
        """Record workspace member addition."""
        context_kwargs = self._get_context_kwargs(
            exclude={
                "workspace_id",
                "member_id",
                "member_type",
                "role",
                "acting_user_id",
            }
        )
        self._logger.info(
            "workspace_member_added",
            workspace_id=workspace_id,
            member_id=member_id,
            member_type=member_type,
            role=role,
            acting_user_id=acting_user_id,
            **context_kwargs,
        )

    def workspace_member_removed(
        self,
        workspace_id: str,
        member_id: str,
        member_type: str,
        acting_user_id: str,
    ) -> None:
        """Record workspace member removal."""
        context_kwargs = self._get_context_kwargs(
            exclude={"workspace_id", "member_id", "member_type", "acting_user_id"}
        )
        self._logger.info(
            "workspace_member_removed",
            workspace_id=workspace_id,
            member_id=member_id,
            member_type=member_type,
            acting_user_id=acting_user_id,
            **context_kwargs,
        )

    def workspace_member_role_changed(
        self,
        workspace_id: str,
        member_id: str,
        member_type: str,
        new_role: str,
        acting_user_id: str,
    ) -> None:
        """Record workspace member role change."""
        context_kwargs = self._get_context_kwargs(
            exclude={
                "workspace_id",
                "member_id",
                "member_type",
                "new_role",
                "acting_user_id",
            }
        )
        self._logger.info(
            "workspace_member_role_changed",
            workspace_id=workspace_id,
            member_id=member_id,
            member_type=member_type,
            new_role=new_role,
            acting_user_id=acting_user_id,
            **context_kwargs,
        )
