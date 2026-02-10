"""Protocol for tenant application service observability.

Defines the interface for domain probes that capture application-level
domain events for tenant service operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

import structlog

if TYPE_CHECKING:
    from shared_kernel.observability_context import ObservationContext


class TenantServiceProbe(Protocol):
    """Domain probe for tenant application service operations."""

    def tenant_created(self, tenant_id: str, name: str) -> None:
        """Record that a tenant was created."""
        ...

    def tenant_retrieved(self, tenant_id: str) -> None:
        """Record that a tenant was retrieved."""
        ...

    def tenants_listed(self, count: int) -> None:
        """Record that tenants were listed."""
        ...

    def tenant_deleted(self, tenant_id: str) -> None:
        """Record that a tenant was deleted."""
        ...

    def tenant_not_found(self, tenant_id: str) -> None:
        """Record that a tenant was not found."""
        ...

    def duplicate_tenant_name(self, name: str) -> None:
        """Record that a duplicate tenant name was detected."""
        ...

    def tenant_member_added(
        self, tenant_id: str, user_id: str, role: str, added_by: str | None
    ) -> None:
        """Record that a member was added to a tenant."""
        ...

    def tenant_member_removed(
        self, tenant_id: str, user_id: str, removed_by: str
    ) -> None:
        """Record that a member was removed from a tenant."""
        ...

    def tenant_members_listed(self, tenant_id: str, member_count: int) -> None:
        """Record that tenant members were listed."""
        ...

    def tenant_cascade_deletion_started(
        self,
        tenant_id: str,
        workspaces_count: int,
        groups_count: int,
        api_keys_count: int,
    ) -> None:
        """Record that cascade deletion is starting for a tenant."""
        ...

    def with_context(self, context: ObservationContext) -> TenantServiceProbe:
        """Create a new probe with observation context bound."""
        ...


class DefaultTenantServiceProbe:
    """Default implementation of TenantServiceProbe using structlog."""

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

    def with_context(self, context: ObservationContext) -> DefaultTenantServiceProbe:
        """Create a new probe with observation context bound."""
        return DefaultTenantServiceProbe(logger=self._logger, context=context)

    def tenant_created(self, tenant_id: str, name: str) -> None:
        """Record that a tenant was created."""
        self._logger.info(
            "tenant_created",
            tenant_id=tenant_id,
            name=name,
            **self._get_context_kwargs(),
        )

    def tenant_retrieved(self, tenant_id: str) -> None:
        """Record that a tenant was retrieved."""
        self._logger.debug(
            "tenant_retrieved",
            tenant_id=tenant_id,
            **self._get_context_kwargs(),
        )

    def tenants_listed(self, count: int) -> None:
        """Record that tenants were listed."""
        self._logger.debug(
            "tenants_listed",
            count=count,
            **self._get_context_kwargs(),
        )

    def tenant_deleted(self, tenant_id: str) -> None:
        """Record that a tenant was deleted."""
        self._logger.info(
            "tenant_deleted",
            tenant_id=tenant_id,
            **self._get_context_kwargs(),
        )

    def tenant_not_found(self, tenant_id: str) -> None:
        """Record that a tenant was not found."""
        self._logger.debug(
            "tenant_not_found",
            tenant_id=tenant_id,
            **self._get_context_kwargs(),
        )

    def duplicate_tenant_name(self, name: str) -> None:
        """Record that a duplicate tenant name was detected."""
        self._logger.warning(
            "duplicate_tenant_name",
            name=name,
            **self._get_context_kwargs(),
        )

    def tenant_member_added(
        self, tenant_id: str, user_id: str, role: str, added_by: str | None
    ) -> None:
        """Record that a member was added to a tenant."""
        self._logger.info(
            "tenant_member_added",
            tenant_id=tenant_id,
            user_id=user_id,
            role=role,
            added_by=added_by,
            **self._get_context_kwargs(),
        )

    def tenant_member_removed(
        self, tenant_id: str, user_id: str, removed_by: str
    ) -> None:
        """Record that a member was removed from a tenant."""
        self._logger.info(
            "tenant_member_removed",
            tenant_id=tenant_id,
            user_id=user_id,
            removed_by=removed_by,
            **self._get_context_kwargs(),
        )

    def tenant_members_listed(self, tenant_id: str, member_count: int) -> None:
        """Record that tenant members were listed."""
        self._logger.debug(
            "tenant_members_listed",
            tenant_id=tenant_id,
            member_count=member_count,
            **self._get_context_kwargs(),
        )

    def tenant_cascade_deletion_started(
        self,
        tenant_id: str,
        workspaces_count: int,
        groups_count: int,
        api_keys_count: int,
    ) -> None:
        """Record that cascade deletion is starting for a tenant.

        This provides valuable operational insight into the scope of
        deletion operations, useful for debugging and monitoring.
        """
        self._logger.info(
            "tenant_cascade_deletion_started",
            tenant_id=tenant_id,
            workspaces_count=workspaces_count,
            groups_count=groups_count,
            api_keys_count=api_keys_count,
            **self._get_context_kwargs(),
        )
