"""Domain probes for secret store operations.

Following Domain-Oriented Observability patterns, these probes capture
domain-significant events related to credential storage operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

import structlog

if TYPE_CHECKING:
    from shared_kernel.observability_context import ObservationContext


class SecretStoreProbe(Protocol):
    """Domain probe for secret store operations."""

    def credential_stored(self, path: str, tenant_id: str) -> None:
        """Record that credentials were successfully stored."""
        ...

    def credential_retrieved(self, path: str, tenant_id: str) -> None:
        """Record that credentials were successfully retrieved."""
        ...

    def credential_not_found(self, path: str, tenant_id: str) -> None:
        """Record that credentials were not found."""
        ...

    def credential_deleted(self, path: str, tenant_id: str) -> None:
        """Record that credentials were successfully deleted."""
        ...

    def with_context(self, context: ObservationContext) -> SecretStoreProbe:
        """Create a new probe with observation context bound."""
        ...


class DefaultSecretStoreProbe:
    """Default implementation of SecretStoreProbe using structlog."""

    def __init__(
        self,
        logger: structlog.stdlib.BoundLogger | None = None,
        context: ObservationContext | None = None,
    ) -> None:
        self._logger = logger or structlog.get_logger()
        self._context = context

    def _get_context_kwargs(self) -> dict[str, Any]:
        if self._context is None:
            return {}
        return self._context.as_dict()

    def with_context(self, context: ObservationContext) -> DefaultSecretStoreProbe:
        return DefaultSecretStoreProbe(logger=self._logger, context=context)

    def credential_stored(self, path: str, tenant_id: str) -> None:
        self._logger.info(
            "credential_stored",
            path=path,
            tenant_id=tenant_id,
            **self._get_context_kwargs(),
        )

    def credential_retrieved(self, path: str, tenant_id: str) -> None:
        self._logger.debug(
            "credential_retrieved",
            path=path,
            tenant_id=tenant_id,
            **self._get_context_kwargs(),
        )

    def credential_not_found(self, path: str, tenant_id: str) -> None:
        self._logger.debug(
            "credential_not_found",
            path=path,
            tenant_id=tenant_id,
            **self._get_context_kwargs(),
        )

    def credential_deleted(self, path: str, tenant_id: str) -> None:
        self._logger.info(
            "credential_deleted",
            path=path,
            tenant_id=tenant_id,
            **self._get_context_kwargs(),
        )
