"""Domain probe for authorization operations.

Following Domain-Oriented Observability patterns, this probe captures
domain-significant events related to authorization checks and relationship writes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

import structlog

if TYPE_CHECKING:
    from shared_kernel.observability_context import ObservationContext


class AuthorizationProbe(Protocol):
    """Domain probe for authorization operations."""

    def relationship_written(
        self,
        resource: str,
        relation: str,
        subject: str,
    ) -> None:
        """Record that a relationship was written to the authorization system."""
        ...

    def relationship_write_failed(
        self,
        resource: str,
        relation: str,
        subject: str,
        error: Exception,
    ) -> None:
        """Record that writing a relationship failed."""
        ...

    def permission_checked(
        self,
        resource: str,
        permission: str,
        subject: str,
        granted: bool,
    ) -> None:
        """Record that a permission was checked."""
        ...

    def permission_check_failed(
        self,
        resource: str,
        permission: str,
        subject: str,
        error: Exception,
    ) -> None:
        """Record that checking a permission failed."""
        ...

    def bulk_check_completed(
        self,
        total_requests: int,
        permitted_count: int,
    ) -> None:
        """Record that a bulk permission check completed."""
        ...

    def relationship_deleted(
        self,
        resource: str,
        relation: str,
        subject: str,
    ) -> None:
        """Record that a relationship was deleted."""
        ...

    def relationship_delete_failed(
        self,
        resource: str,
        relation: str,
        subject: str,
        error: Exception,
    ) -> None:
        """Record that deleting a relationship failed."""
        ...

    def connection_failed(
        self,
        endpoint: str,
        error: Exception,
    ) -> None:
        """Record that connection to authorization system failed."""
        ...

    def with_context(self, context: ObservationContext) -> AuthorizationProbe:
        """Create a new probe with observation context bound."""
        ...


class DefaultAuthorizationProbe:
    """Default implementation of AuthorizationProbe using structlog."""

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

    def with_context(self, context: ObservationContext) -> DefaultAuthorizationProbe:
        """Create a new probe with observation context bound."""
        return DefaultAuthorizationProbe(logger=self._logger, context=context)

    def relationship_written(
        self,
        resource: str,
        relation: str,
        subject: str,
    ) -> None:
        """Record that a relationship was written."""
        self._logger.info(
            "authorization_relationship_written",
            resource=resource,
            relation=relation,
            subject=subject,
            **self._get_context_kwargs(),
        )

    def relationship_write_failed(
        self,
        resource: str,
        relation: str,
        subject: str,
        error: Exception,
    ) -> None:
        """Record that writing a relationship failed."""
        self._logger.error(
            "authorization_relationship_write_failed",
            resource=resource,
            relation=relation,
            subject=subject,
            error=str(error),
            error_type=type(error).__name__,
            **self._get_context_kwargs(),
        )

    def permission_checked(
        self,
        resource: str,
        permission: str,
        subject: str,
        granted: bool,
    ) -> None:
        """Record that a permission was checked."""
        self._logger.debug(
            "authorization_permission_checked",
            resource=resource,
            permission=permission,
            subject=subject,
            granted=granted,
            **self._get_context_kwargs(),
        )

    def permission_check_failed(
        self,
        resource: str,
        permission: str,
        subject: str,
        error: Exception,
    ) -> None:
        """Record that checking a permission failed."""
        self._logger.error(
            "authorization_permission_check_failed",
            resource=resource,
            permission=permission,
            subject=subject,
            error=str(error),
            error_type=type(error).__name__,
            **self._get_context_kwargs(),
        )

    def bulk_check_completed(
        self,
        total_requests: int,
        permitted_count: int,
    ) -> None:
        """Record that a bulk permission check completed."""
        self._logger.info(
            "authorization_bulk_check_completed",
            total_requests=total_requests,
            permitted_count=permitted_count,
            **self._get_context_kwargs(),
        )

    def relationship_deleted(
        self,
        resource: str,
        relation: str,
        subject: str,
    ) -> None:
        """Record that a relationship was deleted."""
        self._logger.info(
            "authorization_relationship_deleted",
            resource=resource,
            relation=relation,
            subject=subject,
            **self._get_context_kwargs(),
        )

    def relationship_delete_failed(
        self,
        resource: str,
        relation: str,
        subject: str,
        error: Exception,
    ) -> None:
        """Record that deleting a relationship failed."""
        self._logger.error(
            "authorization_relationship_delete_failed",
            resource=resource,
            relation=relation,
            subject=subject,
            error=str(error),
            error_type=type(error).__name__,
            **self._get_context_kwargs(),
        )

    def connection_failed(
        self,
        endpoint: str,
        error: Exception,
    ) -> None:
        """Record that connection to authorization system failed."""
        self._logger.error(
            "authorization_connection_failed",
            endpoint=endpoint,
            error=str(error),
            error_type=type(error).__name__,
            **self._get_context_kwargs(),
        )
