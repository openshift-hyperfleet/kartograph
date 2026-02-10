"""Domain probe for tenant context resolution.

Following Domain-Oriented Observability patterns, this probe captures
domain-significant events related to tenant context resolution from
the X-Tenant-ID request header.

See: https://martinfowler.com/articles/domain-oriented-observability.html
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

import structlog

if TYPE_CHECKING:
    from shared_kernel.observability_context import ObservationContext


class TenantContextProbe(Protocol):
    """Domain probe for tenant context resolution operations."""

    def tenant_resolved_from_header(
        self,
        tenant_id: str,
        user_id: str,
    ) -> None:
        """Record that tenant context was resolved from X-Tenant-ID header."""
        ...

    def tenant_resolved_from_default(
        self,
        tenant_id: str,
        user_id: str,
    ) -> None:
        """Record that tenant context was auto-selected from the default tenant."""
        ...

    def tenant_header_missing(
        self,
        user_id: str,
    ) -> None:
        """Record that the X-Tenant-ID header was missing in multi-tenant mode."""
        ...

    def invalid_tenant_id_format(
        self,
        raw_value: str,
        user_id: str,
    ) -> None:
        """Record that the X-Tenant-ID header contained an invalid ULID."""
        ...

    def tenant_access_denied(
        self,
        tenant_id: str,
        user_id: str,
    ) -> None:
        """Record that user was denied access to the requested tenant."""
        ...

    def tenant_authz_check_failed(
        self,
        tenant_id: str,
        user_id: str,
        error: Exception,
    ) -> None:
        """Record that the authorization check for tenant access failed."""
        ...

    def default_tenant_not_found(self) -> None:
        """Record that the default tenant was not found in single-tenant mode."""
        ...

    def with_context(self, context: ObservationContext) -> TenantContextProbe:
        """Create a new probe with observation context bound."""
        ...


class DefaultTenantContextProbe:
    """Default implementation of TenantContextProbe using structlog."""

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

    def with_context(self, context: ObservationContext) -> DefaultTenantContextProbe:
        """Create a new probe with observation context bound."""
        return DefaultTenantContextProbe(logger=self._logger, context=context)

    def tenant_resolved_from_header(
        self,
        tenant_id: str,
        user_id: str,
    ) -> None:
        """Record that tenant context was resolved from X-Tenant-ID header."""
        self._logger.debug(
            "tenant_context_resolved_from_header",
            tenant_id=tenant_id,
            user_id=user_id,
            **self._get_context_kwargs(),
        )

    def tenant_resolved_from_default(
        self,
        tenant_id: str,
        user_id: str,
    ) -> None:
        """Record that tenant context was auto-selected from the default tenant."""
        self._logger.debug(
            "tenant_context_resolved_from_default",
            tenant_id=tenant_id,
            user_id=user_id,
            **self._get_context_kwargs(),
        )

    def tenant_header_missing(
        self,
        user_id: str,
    ) -> None:
        """Record that the X-Tenant-ID header was missing in multi-tenant mode."""
        self._logger.warning(
            "tenant_context_header_missing",
            user_id=user_id,
            message="X-Tenant-ID header is required in multi-tenant mode",
            **self._get_context_kwargs(),
        )

    def invalid_tenant_id_format(
        self,
        raw_value: str,
        user_id: str,
    ) -> None:
        """Record that the X-Tenant-ID header contained an invalid ULID."""
        self._logger.warning(
            "tenant_context_invalid_format",
            raw_value=raw_value,
            user_id=user_id,
            **self._get_context_kwargs(),
        )

    def tenant_access_denied(
        self,
        tenant_id: str,
        user_id: str,
    ) -> None:
        """Record that user was denied access to the requested tenant."""
        self._logger.warning(
            "tenant_context_access_denied",
            tenant_id=tenant_id,
            user_id=user_id,
            **self._get_context_kwargs(),
        )

    def tenant_authz_check_failed(
        self,
        tenant_id: str,
        user_id: str,
        error: Exception,
    ) -> None:
        """Record that the authorization check for tenant access failed."""
        self._logger.error(
            "tenant_context_authz_check_failed",
            tenant_id=tenant_id,
            user_id=user_id,
            error=str(error),
            error_type=type(error).__name__,
            **self._get_context_kwargs(),
        )

    def default_tenant_not_found(self) -> None:
        """Record that the default tenant was not found in single-tenant mode."""
        self._logger.error(
            "tenant_context_default_tenant_not_found",
            message="Default tenant not found. Ensure app startup completed successfully.",
            **self._get_context_kwargs(),
        )
