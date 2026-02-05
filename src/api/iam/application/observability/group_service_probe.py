"""Protocol for group application service observability.

Defines the interface for domain probes that capture application-level
domain events for group service operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

import structlog

if TYPE_CHECKING:
    from shared_kernel.observability_context import ObservationContext


class GroupServiceProbe(Protocol):
    """Domain probe for group application service operations."""

    def group_created(
        self,
        group_id: str,
        name: str,
        tenant_id: str,
        creator_id: str,
    ) -> None:
        """Record that a group was created."""
        ...

    def group_creation_failed(
        self,
        name: str,
        tenant_id: str,
        error: str,
    ) -> None:
        """Record that group creation failed."""
        ...

    def with_context(self, context: ObservationContext) -> GroupServiceProbe:
        """Create a new probe with observation context bound."""
        ...


class DefaultGroupServiceProbe:
    """Default implementation of GroupServiceProbe using structlog."""

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

    def with_context(self, context: ObservationContext) -> DefaultGroupServiceProbe:
        """Create a new probe with observation context bound."""
        return DefaultGroupServiceProbe(logger=self._logger, context=context)

    def group_created(
        self,
        group_id: str,
        name: str,
        tenant_id: str,
        creator_id: str,
    ) -> None:
        """Record that a group was created."""
        self._logger.info(
            "group_created",
            group_id=group_id,
            name=name,
            tenant_id=tenant_id,
            creator_id=creator_id,
            **self._get_context_kwargs(),
        )

    def group_creation_failed(
        self,
        name: str,
        tenant_id: str,
        error: str,
    ) -> None:
        """Record that group creation failed."""
        self._logger.error(
            "group_creation_failed",
            name=name,
            tenant_id=tenant_id,
            error=error,
            **self._get_context_kwargs(),
        )
