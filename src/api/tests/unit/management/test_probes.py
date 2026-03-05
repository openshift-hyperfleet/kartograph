"""Unit tests for Management domain observability probes."""

from __future__ import annotations

from unittest.mock import MagicMock

import structlog

from management.domain.observability import (
    DataSourceProbe,
    DefaultDataSourceProbe,
    DefaultKnowledgeGraphProbe,
    KnowledgeGraphProbe,
)


class TestKnowledgeGraphProbe:
    """Tests for KnowledgeGraphProbe protocol compliance."""

    def test_default_probe_satisfies_protocol(self):
        """DefaultKnowledgeGraphProbe should satisfy the KnowledgeGraphProbe protocol."""
        probe: KnowledgeGraphProbe = DefaultKnowledgeGraphProbe()
        assert isinstance(probe, KnowledgeGraphProbe)


class TestDefaultKnowledgeGraphProbe:
    """Tests for DefaultKnowledgeGraphProbe structlog implementation."""

    def test_created_logs_with_correct_event_and_context(self):
        logger = MagicMock(spec=structlog.stdlib.BoundLogger)
        probe = DefaultKnowledgeGraphProbe(logger=logger)

        probe.created(
            knowledge_graph_id="kg-123",
            tenant_id="tenant-456",
            workspace_id="ws-789",
            name="My Graph",
        )

        logger.info.assert_called_once_with(
            "knowledge_graph_created",
            knowledge_graph_id="kg-123",
            tenant_id="tenant-456",
            workspace_id="ws-789",
            name="My Graph",
        )

    def test_updated_logs_with_correct_event_and_context(self):
        logger = MagicMock(spec=structlog.stdlib.BoundLogger)
        probe = DefaultKnowledgeGraphProbe(logger=logger)

        probe.updated(
            knowledge_graph_id="kg-123",
            tenant_id="tenant-456",
            name="Updated Graph",
        )

        logger.info.assert_called_once_with(
            "knowledge_graph_updated",
            knowledge_graph_id="kg-123",
            tenant_id="tenant-456",
            name="Updated Graph",
        )

    def test_deleted_logs_with_correct_event_and_context(self):
        logger = MagicMock(spec=structlog.stdlib.BoundLogger)
        probe = DefaultKnowledgeGraphProbe(logger=logger)

        probe.deleted(
            knowledge_graph_id="kg-123",
            tenant_id="tenant-456",
            workspace_id="ws-789",
        )

        logger.info.assert_called_once_with(
            "knowledge_graph_deleted",
            knowledge_graph_id="kg-123",
            tenant_id="tenant-456",
            workspace_id="ws-789",
        )

    def test_uses_default_logger_when_none_provided(self):
        """Should create its own logger when none is injected."""
        probe = DefaultKnowledgeGraphProbe()
        assert probe._logger is not None


class TestDataSourceProbe:
    """Tests for DataSourceProbe protocol compliance."""

    def test_default_probe_satisfies_protocol(self):
        """DefaultDataSourceProbe should satisfy the DataSourceProbe protocol."""
        probe: DataSourceProbe = DefaultDataSourceProbe()
        assert isinstance(probe, DataSourceProbe)


class TestDefaultDataSourceProbe:
    """Tests for DefaultDataSourceProbe structlog implementation."""

    def test_created_logs_with_correct_event_and_context(self):
        logger = MagicMock(spec=structlog.stdlib.BoundLogger)
        probe = DefaultDataSourceProbe(logger=logger)

        probe.created(
            data_source_id="ds-123",
            knowledge_graph_id="kg-456",
            tenant_id="tenant-789",
            name="GitHub Source",
            adapter_type="github",
        )

        logger.info.assert_called_once_with(
            "data_source_created",
            data_source_id="ds-123",
            knowledge_graph_id="kg-456",
            tenant_id="tenant-789",
            name="GitHub Source",
            adapter_type="github",
        )

    def test_updated_logs_with_correct_event_and_context(self):
        logger = MagicMock(spec=structlog.stdlib.BoundLogger)
        probe = DefaultDataSourceProbe(logger=logger)

        probe.updated(
            data_source_id="ds-123",
            knowledge_graph_id="kg-456",
            tenant_id="tenant-789",
            name="Updated Source",
        )

        logger.info.assert_called_once_with(
            "data_source_updated",
            data_source_id="ds-123",
            knowledge_graph_id="kg-456",
            tenant_id="tenant-789",
            name="Updated Source",
        )

    def test_deleted_logs_with_correct_event_and_context(self):
        logger = MagicMock(spec=structlog.stdlib.BoundLogger)
        probe = DefaultDataSourceProbe(logger=logger)

        probe.deleted(
            data_source_id="ds-123",
            knowledge_graph_id="kg-456",
            tenant_id="tenant-789",
        )

        logger.info.assert_called_once_with(
            "data_source_deleted",
            data_source_id="ds-123",
            knowledge_graph_id="kg-456",
            tenant_id="tenant-789",
        )

    def test_sync_completed_logs_with_correct_event_and_context(self):
        logger = MagicMock(spec=structlog.stdlib.BoundLogger)
        probe = DefaultDataSourceProbe(logger=logger)

        probe.sync_completed(
            data_source_id="ds-123",
            knowledge_graph_id="kg-456",
            tenant_id="tenant-789",
        )

        logger.info.assert_called_once_with(
            "data_source_sync_completed",
            data_source_id="ds-123",
            knowledge_graph_id="kg-456",
            tenant_id="tenant-789",
        )

    def test_uses_default_logger_when_none_provided(self):
        """Should create its own logger when none is injected."""
        probe = DefaultDataSourceProbe()
        assert probe._logger is not None
