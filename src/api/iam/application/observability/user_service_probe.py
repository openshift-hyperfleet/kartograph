"""Protocol for user application service observability.

Defines the interface for domain probes that capture application-level
domain events for user service operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

import structlog

if TYPE_CHECKING:
    from shared_kernel.observability_context import ObservationContext


class UserServiceProbe(Protocol):
    """Domain probe for user application service operations."""

    def user_ensured(
        self,
        user_id: str,
        username: str,
        was_created: bool,
    ) -> None:
        """Record that a user was ensured to exist (found or created)."""
        ...

    def user_provision_failed(
        self,
        user_id: str,
        username: str,
        error: str,
    ) -> None:
        """Record that user provisioning failed."""
        ...

    def with_context(self, context: ObservationContext) -> UserServiceProbe:
        """Create a new probe with observation context bound."""
        ...


class DefaultUserServiceProbe:
    """Default implementation of UserServiceProbe using structlog."""

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

    def with_context(self, context: ObservationContext) -> DefaultUserServiceProbe:
        """Create a new probe with observation context bound."""
        return DefaultUserServiceProbe(logger=self._logger, context=context)

    def user_ensured(
        self,
        user_id: str,
        username: str,
        was_created: bool,
    ) -> None:
        """Record that a user was ensured to exist."""
        self._logger.info(
            "user_ensured",
            user_id=user_id,
            username=username,
            was_created=was_created,
            **self._get_context_kwargs(),
        )

    def user_provision_failed(
        self,
        user_id: str,
        username: str,
        error: str,
    ) -> None:
        """Record that user provisioning failed."""
        self._logger.error(
            "user_provision_failed",
            user_id=user_id,
            username=username,
            error=error,
            **self._get_context_kwargs(),
        )
