"""Observability probes for Workspace aggregate.

Domain probes for Workspace following Domain Oriented Observability pattern.
Probes emit structured logs with domain-specific context for workspace
member operations (add, remove, role change).

See: https://martinfowler.com/articles/domain-oriented-observability.html
"""

from __future__ import annotations

from typing import Protocol

import structlog


class WorkspaceProbe(Protocol):
    """Protocol for workspace aggregate observability probes.

    Defines the interface for domain probes that capture aggregate-level
    domain events for workspace member operations.
    """

    def member_added(
        self,
        workspace_id: str,
        member_id: str,
        member_type: str,
        role: str,
    ) -> None:
        """Probe emitted when a member is added to a workspace.

        Args:
            workspace_id: The workspace ID
            member_id: The user or group ID
            member_type: "user" or "group"
            role: The role assigned
        """
        ...

    def member_removed(
        self,
        workspace_id: str,
        member_id: str,
        member_type: str,
        role: str,
    ) -> None:
        """Probe emitted when a member is removed from a workspace.

        Args:
            workspace_id: The workspace ID
            member_id: The user or group ID
            member_type: "user" or "group"
            role: The role the member had
        """
        ...

    def member_role_changed(
        self,
        workspace_id: str,
        member_id: str,
        member_type: str,
        old_role: str,
        new_role: str,
    ) -> None:
        """Probe emitted when a member's role is changed.

        Args:
            workspace_id: The workspace ID
            member_id: The user or group ID
            member_type: "user" or "group"
            old_role: The previous role
            new_role: The new role
        """
        ...


class DefaultWorkspaceProbe:
    """Default implementation of WorkspaceProbe using structlog."""

    def __init__(
        self,
        logger: structlog.stdlib.BoundLogger | None = None,
    ) -> None:
        self._logger = logger or structlog.get_logger()

    def member_added(
        self,
        workspace_id: str,
        member_id: str,
        member_type: str,
        role: str,
    ) -> None:
        """Log member addition with structured context."""
        self._logger.info(
            "workspace_member_added",
            workspace_id=workspace_id,
            member_id=member_id,
            member_type=member_type,
            role=role,
        )

    def member_removed(
        self,
        workspace_id: str,
        member_id: str,
        member_type: str,
        role: str,
    ) -> None:
        """Log member removal with structured context."""
        self._logger.info(
            "workspace_member_removed",
            workspace_id=workspace_id,
            member_id=member_id,
            member_type=member_type,
            role=role,
        )

    def member_role_changed(
        self,
        workspace_id: str,
        member_id: str,
        member_type: str,
        old_role: str,
        new_role: str,
    ) -> None:
        """Log role change with structured context."""
        self._logger.info(
            "workspace_member_role_changed",
            workspace_id=workspace_id,
            member_id=member_id,
            member_type=member_type,
            old_role=old_role,
            new_role=new_role,
        )
