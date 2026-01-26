"""Domain probe for API key repository operations.

Following Domain-Oriented Observability patterns, this probe captures
domain-significant events related to API key repository operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

import structlog

if TYPE_CHECKING:
    from shared_kernel.observability_context import ObservationContext


class APIKeyRepositoryProbe(Protocol):
    """Domain probe for API key repository operations.

    Records domain events during API key persistence operations.
    """

    def api_key_saved(self, api_key_id: str, user_id: str) -> None:
        """Record that an API key was successfully saved."""
        ...

    def api_key_retrieved(self, api_key_id: str) -> None:
        """Record that an API key was retrieved."""
        ...

    def api_key_not_found(self, api_key_id: str) -> None:
        """Record that an API key was not found by ID."""
        ...

    def api_key_verification_failed(self) -> None:
        """Record that API key secret verification failed.

        This covers both cases: no key found with matching prefix,
        or hash verification failed for all candidates.

        Note: We don't log the secret for security reasons.
        """
        ...

    def api_key_prefix_collision(self, prefix: str, count: int) -> None:
        """Record that multiple API keys share the same prefix.

        Args:
            prefix: The colliding prefix (first 6 chars logged for diagnostics)
            count: Number of keys sharing this prefix
        """
        ...

    def api_key_deleted(self, api_key_id: str) -> None:
        """Record that an API key was deleted."""
        ...

    def api_key_list_retrieved(self, user_id: str, count: int) -> None:
        """Record that API keys were listed for a user."""
        ...

    def duplicate_api_key_name(self, name: str, user_id: str, tenant_id: str) -> None:
        """Record that a duplicate API key name was detected."""
        ...

    def with_context(self, context: ObservationContext) -> APIKeyRepositoryProbe:
        """Create a new probe with observation context bound."""
        ...


class DefaultAPIKeyRepositoryProbe:
    """Default implementation of APIKeyRepositoryProbe using structlog."""

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

    def with_context(self, context: ObservationContext) -> DefaultAPIKeyRepositoryProbe:
        """Create a new probe with observation context bound."""
        return DefaultAPIKeyRepositoryProbe(logger=self._logger, context=context)

    def api_key_saved(self, api_key_id: str, user_id: str) -> None:
        """Record that an API key was successfully saved."""
        self._logger.info(
            "api_key_saved",
            api_key_id=api_key_id,
            user_id=user_id,
            **self._get_context_kwargs(),
        )

    def api_key_retrieved(self, api_key_id: str) -> None:
        """Record that an API key was retrieved."""
        self._logger.debug(
            "api_key_retrieved",
            api_key_id=api_key_id,
            **self._get_context_kwargs(),
        )

    def api_key_not_found(self, api_key_id: str) -> None:
        """Record that an API key was not found by ID."""
        self._logger.debug(
            "api_key_not_found",
            api_key_id=api_key_id,
            **self._get_context_kwargs(),
        )

    def api_key_verification_failed(self) -> None:
        """Record that API key secret verification failed.

        This covers both cases: no key found with matching prefix,
        or hash verification failed for all candidates.

        Note: We don't log the secret for security reasons.
        """
        self._logger.debug(
            "api_key_verification_failed",
            **self._get_context_kwargs(),
        )

    def api_key_prefix_collision(self, prefix: str, count: int) -> None:
        """Record that multiple API keys share the same prefix.

        Args:
            prefix: The colliding prefix (first 6 chars logged for diagnostics)
            count: Number of keys sharing this prefix
        """
        self._logger.error(
            "api_key_prefix_collision",
            prefix_sample=prefix[:6] + "...",  # Only log first 6 chars
            collision_count=count,
            **self._get_context_kwargs(),
        )

    def api_key_deleted(self, api_key_id: str) -> None:
        """Record that an API key was deleted."""
        self._logger.info(
            "api_key_deleted",
            api_key_id=api_key_id,
            **self._get_context_kwargs(),
        )

    def api_key_list_retrieved(self, user_id: str, count: int) -> None:
        """Record that API keys were listed for a user."""
        self._logger.debug(
            "api_key_list_retrieved",
            user_id=user_id,
            count=count,
            **self._get_context_kwargs(),
        )

    def duplicate_api_key_name(self, name: str, user_id: str, tenant_id: str) -> None:
        """Record that a duplicate API key name was detected."""
        self._logger.warning(
            "duplicate_api_key_name",
            name=name,
            user_id=user_id,
            tenant_id=tenant_id,
            **self._get_context_kwargs(),
        )
