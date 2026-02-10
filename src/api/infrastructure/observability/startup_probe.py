"""Domain probe for application startup and lifecycle events.

Following Domain-Oriented Observability patterns, this probe captures
domain-significant events during application initialization and shutdown.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

import structlog

if TYPE_CHECKING:
    from shared_kernel.observability_context import ObservationContext


class StartupProbe(Protocol):
    """Domain probe for application startup operations."""

    def default_tenant_bootstrapped(self, tenant_id: str, name: str) -> None:
        """Record that the default tenant was bootstrapped at startup."""
        ...

    def default_tenant_already_exists(self, tenant_id: str, name: str) -> None:
        """Record that the default tenant already existed."""
        ...

    def default_workspace_bootstrapped(
        self, workspace_id: str, tenant_id: str, name: str
    ) -> None:
        """Record that the default root workspace was bootstrapped at startup."""
        ...

    def default_workspace_already_exists(
        self, workspace_id: str, tenant_id: str, name: str
    ) -> None:
        """Record that the default root workspace already existed."""
        ...

    def with_context(self, context: ObservationContext) -> StartupProbe:
        """Create a new probe with observation context bound."""
        ...


class DefaultStartupProbe:
    """Default implementation of StartupProbe using structlog."""

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

    def with_context(self, context: ObservationContext) -> DefaultStartupProbe:
        """Create a new probe with observation context bound."""
        return DefaultStartupProbe(logger=self._logger, context=context)

    def default_tenant_bootstrapped(self, tenant_id: str, name: str) -> None:
        """Record that the default tenant was bootstrapped at startup."""
        self._logger.info(
            "default_tenant_bootstrapped",
            tenant_id=tenant_id,
            name=name,
            **self._get_context_kwargs(),
        )

    def default_tenant_already_exists(self, tenant_id: str, name: str) -> None:
        """Record that the default tenant already existed."""
        self._logger.info(
            "default_tenant_already_exists",
            tenant_id=tenant_id,
            name=name,
            **self._get_context_kwargs(),
        )

    def default_workspace_bootstrapped(
        self, workspace_id: str, tenant_id: str, name: str
    ) -> None:
        """Record that the default root workspace was bootstrapped at startup."""
        self._logger.info(
            "default_workspace_bootstrapped",
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            name=name,
            **self._get_context_kwargs(),
        )

    def default_workspace_already_exists(
        self, workspace_id: str, tenant_id: str, name: str
    ) -> None:
        """Record that the default root workspace already existed."""
        self._logger.info(
            "default_workspace_already_exists",
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            name=name,
            **self._get_context_kwargs(),
        )
