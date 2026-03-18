"""Protocol for data source application service observability.

Defines the interface for domain probes that capture application-level
domain events for data source service operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

import structlog

if TYPE_CHECKING:
    from shared_kernel.observability_context import ObservationContext


class DataSourceServiceProbe(Protocol):
    """Domain probe for data source application service operations.

    Records domain-significant events related to data source operations.
    """

    def data_source_created(
        self,
        ds_id: str,
        kg_id: str,
        tenant_id: str,
        name: str,
    ) -> None:
        """Record data source creation."""
        ...

    def data_source_creation_failed(
        self,
        kg_id: str,
        name: str,
        error: str,
    ) -> None:
        """Record failed data source creation."""
        ...

    def data_source_retrieved(
        self,
        ds_id: str,
    ) -> None:
        """Record data source retrieval."""
        ...

    def data_source_updated(
        self,
        ds_id: str,
        name: str,
    ) -> None:
        """Record data source update."""
        ...

    def data_source_deleted(
        self,
        ds_id: str,
    ) -> None:
        """Record data source deletion."""
        ...

    def data_source_deletion_failed(
        self,
        ds_id: str,
        error: str,
    ) -> None:
        """Record failed data source deletion."""
        ...

    def data_sources_listed(
        self,
        kg_id: str,
        count: int,
    ) -> None:
        """Record data sources listed."""
        ...

    def sync_requested(
        self,
        ds_id: str,
    ) -> None:
        """Record sync requested."""
        ...

    def permission_denied(
        self,
        user_id: str,
        resource_id: str,
        permission: str,
    ) -> None:
        """Record permission denied."""
        ...

    def with_context(self, context: ObservationContext) -> DataSourceServiceProbe:
        """Return a new probe with additional context."""
        ...


class DefaultDataSourceServiceProbe:
    """Default implementation of DataSourceServiceProbe using structlog."""

    def __init__(
        self,
        logger: structlog.stdlib.BoundLogger | None = None,
        context: ObservationContext | None = None,
    ):
        self._logger = logger or structlog.get_logger()
        self._context = context

    def _get_context_kwargs(self, exclude: set[str] | None = None) -> dict[str, Any]:
        """Get context as kwargs dict, excluding specified keys.

        Args:
            exclude: Set of keys to exclude from context (avoids parameter collision)

        Returns:
            Context dict with excluded keys filtered out
        """
        if self._context is None:
            return {}

        context_dict = self._context.as_dict()
        if exclude:
            return {k: v for k, v in context_dict.items() if k not in exclude}
        return context_dict

    def with_context(
        self, context: ObservationContext
    ) -> DefaultDataSourceServiceProbe:
        """Create a new probe with observation context bound."""
        return DefaultDataSourceServiceProbe(logger=self._logger, context=context)

    def data_source_created(
        self,
        ds_id: str,
        kg_id: str,
        tenant_id: str,
        name: str,
    ) -> None:
        """Record data source creation."""
        context_kwargs = self._get_context_kwargs(
            exclude={"ds_id", "kg_id", "tenant_id", "name"}
        )
        self._logger.info(
            "data_source_created",
            ds_id=ds_id,
            kg_id=kg_id,
            tenant_id=tenant_id,
            name=name,
            **context_kwargs,
        )

    def data_source_creation_failed(
        self,
        kg_id: str,
        name: str,
        error: str,
    ) -> None:
        """Record failed data source creation."""
        context_kwargs = self._get_context_kwargs(exclude={"kg_id", "name", "error"})
        self._logger.error(
            "data_source_creation_failed",
            kg_id=kg_id,
            name=name,
            error=error,
            **context_kwargs,
        )

    def data_source_retrieved(
        self,
        ds_id: str,
    ) -> None:
        """Record data source retrieval."""
        context_kwargs = self._get_context_kwargs(exclude={"ds_id"})
        self._logger.debug(
            "data_source_retrieved",
            ds_id=ds_id,
            **context_kwargs,
        )

    def data_source_updated(
        self,
        ds_id: str,
        name: str,
    ) -> None:
        """Record data source update."""
        context_kwargs = self._get_context_kwargs(exclude={"ds_id", "name"})
        self._logger.info(
            "data_source_updated",
            ds_id=ds_id,
            name=name,
            **context_kwargs,
        )

    def data_source_deleted(
        self,
        ds_id: str,
    ) -> None:
        """Record data source deletion."""
        context_kwargs = self._get_context_kwargs(exclude={"ds_id"})
        self._logger.info(
            "data_source_deleted",
            ds_id=ds_id,
            **context_kwargs,
        )

    def data_source_deletion_failed(
        self,
        ds_id: str,
        error: str,
    ) -> None:
        """Record failed data source deletion."""
        context_kwargs = self._get_context_kwargs(exclude={"ds_id", "error"})
        self._logger.error(
            "data_source_deletion_failed",
            ds_id=ds_id,
            error=error,
            **context_kwargs,
        )

    def data_sources_listed(
        self,
        kg_id: str,
        count: int,
    ) -> None:
        """Record data sources listed."""
        context_kwargs = self._get_context_kwargs(exclude={"kg_id", "count"})
        self._logger.debug(
            "data_sources_listed",
            kg_id=kg_id,
            count=count,
            **context_kwargs,
        )

    def sync_requested(
        self,
        ds_id: str,
    ) -> None:
        """Record sync requested."""
        context_kwargs = self._get_context_kwargs(exclude={"ds_id"})
        self._logger.info(
            "data_source_sync_requested",
            ds_id=ds_id,
            **context_kwargs,
        )

    def permission_denied(
        self,
        user_id: str,
        resource_id: str,
        permission: str,
    ) -> None:
        """Record permission denied."""
        context_kwargs = self._get_context_kwargs(
            exclude={"user_id", "resource_id", "permission"}
        )
        self._logger.warning(
            "data_source_permission_denied",
            user_id=user_id,
            resource_id=resource_id,
            permission=permission,
            **context_kwargs,
        )
