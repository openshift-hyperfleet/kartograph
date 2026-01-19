"""Domain probe for IAM repository operations.

Following Domain-Oriented Observability patterns, this probe captures
domain-significant events related to group, user, and tenant repository operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

import structlog

if TYPE_CHECKING:
    from shared_kernel.observability_context import ObservationContext


class UserRepositoryProbe(Protocol):
    """Domain probe for user repository operations.

    Records domain events during user persistence operations.
    """

    def user_saved(self, user_id: str, username: str) -> None:
        """Record that a user was successfully saved."""
        ...

    def user_retrieved(self, user_id: str) -> None:
        """Record that a user was retrieved."""
        ...

    def user_not_found(self, user_id: str) -> None:
        """Record that a user was not found."""
        ...

    def username_not_found(self, username: str) -> None:
        """Record that a username was not found."""
        ...

    def with_context(self, context: ObservationContext) -> UserRepositoryProbe:
        """Create a new probe with observation context bound."""
        ...


class GroupRepositoryProbe(Protocol):
    """Domain probe for group repository operations.

    Records domain events during group persistence operations, including
    both PostgreSQL (metadata) and SpiceDB (membership) operations.
    """

    def group_saved(self, group_id: str, tenant_id: str) -> None:
        """Record that a group was successfully saved."""
        ...

    def group_retrieved(self, group_id: str, member_count: int) -> None:
        """Record that a group was retrieved with members hydrated."""
        ...

    def group_not_found(self, group_id: str) -> None:
        """Record that a group was not found."""
        ...

    def group_deleted(self, group_id: str) -> None:
        """Record that a group was deleted."""
        ...

    def duplicate_group_name(self, name: str, tenant_id: str) -> None:
        """Record that a duplicate group name was detected."""
        ...

    def membership_hydration_failed(self, group_id: str, error: str) -> None:
        """Record that hydrating members from SpiceDB failed."""
        ...

    def with_context(self, context: ObservationContext) -> GroupRepositoryProbe:
        """Create a new probe with observation context bound."""
        ...


class DefaultGroupRepositoryProbe:
    """Default implementation of GroupRepositoryProbe using structlog."""

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

    def with_context(self, context: ObservationContext) -> DefaultGroupRepositoryProbe:
        """Create a new probe with observation context bound."""
        return DefaultGroupRepositoryProbe(logger=self._logger, context=context)

    def group_saved(self, group_id: str, tenant_id: str) -> None:
        """Record that a group was successfully saved."""
        self._logger.info(
            "group_saved",
            group_id=group_id,
            tenant_id=tenant_id,
            **self._get_context_kwargs(),
        )

    def group_retrieved(self, group_id: str, member_count: int) -> None:
        """Record that a group was retrieved with members hydrated."""
        self._logger.debug(
            "group_retrieved",
            group_id=group_id,
            member_count=member_count,
            **self._get_context_kwargs(),
        )

    def group_not_found(self, group_id: str) -> None:
        """Record that a group was not found."""
        self._logger.debug(
            "group_not_found",
            group_id=group_id,
            **self._get_context_kwargs(),
        )

    def group_deleted(self, group_id: str) -> None:
        """Record that a group was deleted."""
        self._logger.info(
            "group_deleted",
            group_id=group_id,
            **self._get_context_kwargs(),
        )

    def duplicate_group_name(self, name: str, tenant_id: str) -> None:
        """Record that a duplicate group name was detected."""
        self._logger.warning(
            "duplicate_group_name",
            name=name,
            tenant_id=tenant_id,
            **self._get_context_kwargs(),
        )

    def membership_hydration_failed(self, group_id: str, error: str) -> None:
        """Record that hydrating members from SpiceDB failed."""
        self._logger.error(
            "membership_hydration_failed",
            group_id=group_id,
            error=error,
            **self._get_context_kwargs(),
        )


class DefaultUserRepositoryProbe:
    """Default implementation of UserRepositoryProbe using structlog."""

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

    def with_context(self, context: ObservationContext) -> DefaultUserRepositoryProbe:
        """Create a new probe with observation context bound."""
        return DefaultUserRepositoryProbe(logger=self._logger, context=context)

    def user_saved(self, user_id: str, username: str) -> None:
        """Record that a user was successfully saved."""
        self._logger.info(
            "user_saved",
            user_id=user_id,
            username=username,
            **self._get_context_kwargs(),
        )

    def user_retrieved(self, user_id: str) -> None:
        """Record that a user was retrieved."""
        self._logger.debug(
            "user_retrieved",
            user_id=user_id,
            **self._get_context_kwargs(),
        )

    def user_not_found(self, user_id: str) -> None:
        """Record that a user was not found."""
        self._logger.debug(
            "user_not_found",
            user_id=user_id,
            **self._get_context_kwargs(),
        )

    def username_not_found(self, username: str) -> None:
        """Record that a username was not found."""
        self._logger.debug(
            "username_not_found",
            username=username,
            **self._get_context_kwargs(),
        )


class TenantRepositoryProbe(Protocol):
    """Domain probe for tenant repository operations.

    Records domain events during tenant persistence operations.
    """

    def tenant_saved(self, tenant_id: str) -> None:
        """Record that a tenant was successfully saved."""
        ...

    def tenant_retrieved(self, tenant_id: str) -> None:
        """Record that a tenant was retrieved."""
        ...

    def tenant_deleted(self, tenant_id: str) -> None:
        """Record that a tenant was deleted."""
        ...

    def tenants_listed(self, count: int) -> None:
        """Record that tenants were listed."""
        ...

    def duplicate_tenant_name(self, name: str) -> None:
        """Record that a duplicate tenant name was detected."""
        ...

    def with_context(self, context: ObservationContext) -> TenantRepositoryProbe:
        """Create a new probe with observation context bound."""
        ...


class DefaultTenantRepositoryProbe:
    """Default implementation of TenantRepositoryProbe using structlog."""

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

    def with_context(self, context: ObservationContext) -> DefaultTenantRepositoryProbe:
        """Create a new probe with observation context bound."""
        return DefaultTenantRepositoryProbe(logger=self._logger, context=context)

    def tenant_saved(self, tenant_id: str) -> None:
        """Record that a tenant was successfully saved."""
        self._logger.info(
            "tenant_saved",
            tenant_id=tenant_id,
            **self._get_context_kwargs(),
        )

    def tenant_retrieved(self, tenant_id: str) -> None:
        """Record that a tenant was retrieved."""
        self._logger.debug(
            "tenant_retrieved",
            tenant_id=tenant_id,
            **self._get_context_kwargs(),
        )

    def tenant_deleted(self, tenant_id: str) -> None:
        """Record that a tenant was deleted."""
        self._logger.info(
            "tenant_deleted",
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

    def duplicate_tenant_name(self, name: str) -> None:
        """Record that a duplicate tenant name was detected."""
        self._logger.warning(
            "duplicate_tenant_name",
            name=name,
            **self._get_context_kwargs(),
        )
