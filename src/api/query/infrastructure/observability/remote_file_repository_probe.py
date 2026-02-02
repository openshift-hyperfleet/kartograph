"""Domain probe for remote file repository operations.

Following Domain-Oriented Observability patterns, this probe captures
domain-significant events related to remote file fetching operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

import structlog

if TYPE_CHECKING:
    from shared_kernel.observability_context import ObservationContext


class RemoteFileRepositoryProbe(Protocol):
    """Domain probe for remote file repository operations.

    Records domain events during remote file fetching operations.
    """

    def file_fetch_requested(self, url: str) -> None:
        """Record that a file fetch was requested."""
        ...

    def invalid_url_format(self, url: str, reason: str) -> None:
        """Record that a URL failed validation."""
        ...

    def file_fetched(self, url: str, raw_url: str, content_length: int) -> None:
        """Record that a file was successfully fetched."""
        ...

    def file_fetch_failed(
        self, url: str, reason: str, status_code: int | None = None
    ) -> None:
        """Record that a file fetch failed."""
        ...

    def with_context(self, context: ObservationContext) -> RemoteFileRepositoryProbe:
        """Create a new probe with observation context bound."""
        ...


class DefaultRemoteFileRepositoryProbe:
    """Default implementation of RemoteFileRepositoryProbe using structlog."""

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

    def with_context(
        self, context: ObservationContext
    ) -> DefaultRemoteFileRepositoryProbe:
        """Create a new probe with observation context bound."""
        return DefaultRemoteFileRepositoryProbe(logger=self._logger, context=context)

    def file_fetch_requested(self, url: str) -> None:
        """Record that a file fetch was requested."""
        self._logger.info(
            "remote_file_fetch_requested",
            url=url,
            **self._get_context_kwargs(),
        )

    def invalid_url_format(self, url: str, reason: str) -> None:
        """Record that a URL failed validation."""
        self._logger.warning(
            "remote_file_invalid_url",
            url=url,
            reason=reason,
            **self._get_context_kwargs(),
        )

    def file_fetched(self, url: str, raw_url: str, content_length: int) -> None:
        """Record that a file was successfully fetched."""
        self._logger.info(
            "remote_file_fetched",
            url=url,
            raw_url=raw_url,
            content_length=content_length,
            **self._get_context_kwargs(),
        )

    def file_fetch_failed(
        self, url: str, reason: str, status_code: int | None = None
    ) -> None:
        """Record that a file fetch failed."""
        self._logger.error(
            "remote_file_fetch_failed",
            url=url,
            reason=reason,
            status_code=status_code,
            **self._get_context_kwargs(),
        )
