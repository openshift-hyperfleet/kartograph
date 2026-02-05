"""Domain probe for JWT validation operations.

Following Domain-Oriented Observability patterns, this probe captures
domain-significant events related to JWT token validation.

See: https://martinfowler.com/articles/domain-oriented-observability.html
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

import structlog

if TYPE_CHECKING:
    from shared_kernel.observability_context import ObservationContext


class JWTValidatorProbe(Protocol):
    """Domain probe for JWT validation operations."""

    def token_validated(self, user_id: str) -> None:
        """Record that a token was successfully validated."""
        ...

    def token_validation_failed(self, reason: str) -> None:
        """Record that token validation failed."""
        ...

    def jwks_fetched(self, key_count: int) -> None:
        """Record that JWKS was fetched from the issuer."""
        ...

    def jwks_cache_hit(self) -> None:
        """Record that JWKS was served from cache."""
        ...

    def jwks_fetch_failed(self, error: str) -> None:
        """Record that JWKS fetch failed."""
        ...

    def with_context(self, context: ObservationContext) -> JWTValidatorProbe:
        """Create a new probe with observation context bound."""
        ...


class DefaultJWTValidatorProbe:
    """Default implementation of JWTValidatorProbe using structlog."""

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

    def with_context(self, context: ObservationContext) -> DefaultJWTValidatorProbe:
        """Create a new probe with observation context bound."""
        return DefaultJWTValidatorProbe(logger=self._logger, context=context)

    def token_validated(self, user_id: str) -> None:
        """Record that a token was successfully validated."""
        self._logger.info(
            "jwt_token_validated",
            user_id=user_id,
            **self._get_context_kwargs(),
        )

    def token_validation_failed(self, reason: str) -> None:
        """Record that token validation failed."""
        self._logger.warning(
            "jwt_token_validation_failed",
            reason=reason,
            **self._get_context_kwargs(),
        )

    def jwks_fetched(self, key_count: int) -> None:
        """Record that JWKS was fetched from the issuer."""
        self._logger.info(
            "jwt_jwks_fetched",
            key_count=key_count,
            **self._get_context_kwargs(),
        )

    def jwks_cache_hit(self) -> None:
        """Record that JWKS was served from cache."""
        self._logger.debug(
            "jwt_jwks_cache_hit",
            **self._get_context_kwargs(),
        )

    def jwks_fetch_failed(self, error: str) -> None:
        """Record that JWKS fetch failed."""
        self._logger.error(
            "jwt_jwks_fetch_failed",
            error=error,
            **self._get_context_kwargs(),
        )
