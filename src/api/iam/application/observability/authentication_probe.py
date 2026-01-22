"""Protocol for authentication observability.

Defines the interface for domain probes that capture authentication events
for the get_current_user dependency.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

import structlog

if TYPE_CHECKING:
    from shared_kernel.observability_context import ObservationContext


class AuthenticationProbe(Protocol):
    """Domain probe for authentication operations."""

    def user_authenticated(
        self,
        user_id: str,
        username: str,
    ) -> None:
        """Record successful user authentication via JWT."""
        ...

    def authentication_failed(
        self,
        reason: str,
    ) -> None:
        """Record authentication failure."""
        ...

    def api_key_authentication_succeeded(
        self,
        api_key_id: str,
        user_id: str,
    ) -> None:
        """Record successful authentication via API key."""
        ...

    def api_key_authentication_failed(
        self,
        reason: str,
    ) -> None:
        """Record API key authentication failure.

        Args:
            reason: Failure reason (not_found, expired, revoked)
        """
        ...

    def with_context(self, context: ObservationContext) -> AuthenticationProbe:
        """Create a new probe with observation context bound."""
        ...


class DefaultAuthenticationProbe:
    """Default implementation of AuthenticationProbe using structlog."""

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

    def with_context(self, context: ObservationContext) -> DefaultAuthenticationProbe:
        """Create a new probe with observation context bound."""
        return DefaultAuthenticationProbe(logger=self._logger, context=context)

    def user_authenticated(
        self,
        user_id: str,
        username: str,
    ) -> None:
        """Record successful user authentication via JWT."""
        self._logger.info(
            "user_authenticated",
            user_id=user_id,
            username=username,
            **self._get_context_kwargs(),
        )

    def authentication_failed(
        self,
        reason: str,
    ) -> None:
        """Record authentication failure."""
        self._logger.warning(
            "authentication_failed",
            reason=reason,
            **self._get_context_kwargs(),
        )

    def api_key_authentication_succeeded(
        self,
        api_key_id: str,
        user_id: str,
    ) -> None:
        """Record successful authentication via API key."""
        self._logger.info(
            "api_key_authentication_succeeded",
            api_key_id=api_key_id,
            user_id=user_id,
            **self._get_context_kwargs(),
        )

    def api_key_authentication_failed(
        self,
        reason: str,
    ) -> None:
        """Record API key authentication failure.

        Args:
            reason: Failure reason (not_found, expired, revoked)
        """
        self._logger.warning(
            "api_key_authentication_failed",
            reason=reason,
            **self._get_context_kwargs(),
        )
