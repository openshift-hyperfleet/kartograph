"""Domain probe for integration test cleanup operations.

Following Domain-Oriented Observability pattern - records domain-significant
events during test data cleanup rather than using raw logger calls.
"""

from typing import Protocol

import structlog


class TestCleanupProbe(Protocol):
    """Observability probe for test cleanup operations."""

    def cleanup_started(
        self,
        default_tenant_name: str,
    ) -> None:
        """Record cleanup started."""
        ...

    def table_cleaned(
        self,
        table_name: str,
        rows_deleted: int | None = None,
    ) -> None:
        """Record table cleanup."""
        ...

    def cleanup_completed(
        self,
        tables_cleaned: int,
    ) -> None:
        """Record cleanup completed successfully."""
        ...

    def cleanup_failed(
        self,
        table_name: str,
        error: str,
    ) -> None:
        """Record cleanup failure."""
        ...


class DefaultTestCleanupProbe:
    """Default test cleanup probe using structlog."""

    def __init__(self) -> None:
        self._logger = structlog.get_logger()

    def cleanup_started(self, default_tenant_name: str) -> None:
        """Record cleanup started."""
        self._logger.info(
            "test_cleanup_started",
            default_tenant_name=default_tenant_name,
        )

    def table_cleaned(self, table_name: str, rows_deleted: int | None = None) -> None:
        """Record table cleanup."""
        self._logger.debug(
            "test_table_cleaned",
            table_name=table_name,
            rows_deleted=rows_deleted,
        )

    def cleanup_completed(self, tables_cleaned: int) -> None:
        """Record cleanup completed successfully."""
        self._logger.info(
            "test_cleanup_completed",
            tables_cleaned=tables_cleaned,
        )

    def cleanup_failed(self, table_name: str, error: str) -> None:
        """Record cleanup failure."""
        self._logger.error(
            "test_cleanup_failed",
            table_name=table_name,
            error=error,
        )
