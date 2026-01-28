"""Protocol for API key application service observability.

Defines the interface for domain probes that capture application-level
domain events for API key service operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

import structlog

if TYPE_CHECKING:
    from shared_kernel.observability_context import ObservationContext


class APIKeyServiceProbe(Protocol):
    """Domain probe for API key application service operations."""

    def api_key_created(
        self,
        api_key_id: str,
        user_id: str,
        name: str,
    ) -> None:
        """Record that an API key was created."""
        ...

    def api_key_creation_failed(
        self,
        user_id: str,
        error: str,
    ) -> None:
        """Record that API key creation failed."""
        ...

    def api_key_revoked(
        self,
        api_key_id: str,
        user_id: str,
    ) -> None:
        """Record that an API key was revoked."""
        ...

    def api_key_revocation_failed(
        self,
        api_key_id: str,
        error: str,
    ) -> None:
        """Record that API key revocation failed."""
        ...

    def api_key_list_retrieved(
        self,
        user_id: str,
        count: int,
    ) -> None:
        """Record that API keys were listed for a user."""
        ...

    def api_key_list_retrieval_failed(self, user_id: str, reason: str) -> None:
        """Record that API key list operation failed."""

    def with_context(self, context: ObservationContext) -> APIKeyServiceProbe:
        """Create a new probe with observation context bound."""
        ...


class DefaultAPIKeyServiceProbe:
    """Default implementation of APIKeyServiceProbe using structlog."""

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

    def with_context(self, context: ObservationContext) -> DefaultAPIKeyServiceProbe:
        """Create a new probe with observation context bound."""
        return DefaultAPIKeyServiceProbe(logger=self._logger, context=context)

    def api_key_created(
        self,
        api_key_id: str,
        user_id: str,
        name: str,
    ) -> None:
        """Record that an API key was created."""
        self._logger.info(
            "api_key_created",
            api_key_id=api_key_id,
            user_id=user_id,
            name=name,
            **self._get_context_kwargs(),
        )

    def api_key_creation_failed(
        self,
        user_id: str,
        error: str,
    ) -> None:
        """Record that API key creation failed."""
        self._logger.error(
            "api_key_creation_failed",
            user_id=user_id,
            error=error,
            **self._get_context_kwargs(),
        )

    def api_key_revoked(
        self,
        api_key_id: str,
        user_id: str,
    ) -> None:
        """Record that an API key was revoked."""
        self._logger.info(
            "api_key_revoked",
            api_key_id=api_key_id,
            user_id=user_id,
            **self._get_context_kwargs(),
        )

    def api_key_revocation_failed(
        self,
        api_key_id: str,
        error: str,
    ) -> None:
        """Record that API key revocation failed."""
        self._logger.error(
            "api_key_revocation_failed",
            api_key_id=api_key_id,
            error=error,
            **self._get_context_kwargs(),
        )

    def api_key_list_retrieved(
        self,
        user_id: str,
        count: int,
    ) -> None:
        """Record that API keys were listed for a user."""
        self._logger.info(
            "api_key_list_retrieved",
            user_id=user_id,
            count=count,
            **self._get_context_kwargs(),
        )

    def api_key_list_retrieval_failed(
        self,
        user_id: str,
        reason: str,
    ) -> None:
        """Record that API key list operation failed."""
        self._logger.warning(
            "api_key_list_retrieval_failed",
            user_id=user_id,
            reason=reason,
            **self._get_context_kwargs(),
        )
