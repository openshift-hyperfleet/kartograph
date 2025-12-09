"""Unit tests for domain probes.

Tests that domain probes correctly capture domain events
following the Domain Oriented Observability pattern.
"""

from unittest.mock import MagicMock

import structlog

from graph.infrastructure.observability import (
    DefaultGraphClientProbe,
)
from infrastructure.observability import ObservationContext
from infrastructure.observability.probes import (
    DefaultConnectionProbe,
)


class TestConnectionProbe:
    """Tests for ConnectionProbe protocol and implementation."""

    def test_default_probe_creates_with_default_logger(self):
        """Default probe should work without explicit logger."""
        probe = DefaultConnectionProbe()
        assert probe._logger is not None

    def test_default_probe_accepts_custom_logger(self):
        """Default probe should accept a custom logger."""
        mock_logger = MagicMock(spec=structlog.stdlib.BoundLogger)
        probe = DefaultConnectionProbe(logger=mock_logger)
        assert probe._logger is mock_logger

    def test_connection_established_logs_info(self):
        """connection_established should log with host and database."""
        mock_logger = MagicMock(spec=structlog.stdlib.BoundLogger)
        probe = DefaultConnectionProbe(logger=mock_logger)

        probe.connection_established(host="localhost", database="testdb")

        mock_logger.info.assert_called_once_with(
            "database_connection_established",
            host="localhost",
            database="testdb",
        )

    def test_connection_failed_logs_error(self):
        """connection_failed should log error with host, database, and error."""
        mock_logger = MagicMock(spec=structlog.stdlib.BoundLogger)
        probe = DefaultConnectionProbe(logger=mock_logger)
        error = Exception("Connection refused")

        probe.connection_failed(host="localhost", database="testdb", error=error)

        mock_logger.error.assert_called_once_with(
            "database_connection_failed",
            host="localhost",
            database="testdb",
            error="Connection refused",
        )

    def test_connection_closed_logs_info(self):
        """connection_closed should log info."""
        mock_logger = MagicMock(spec=structlog.stdlib.BoundLogger)
        probe = DefaultConnectionProbe(logger=mock_logger)

        probe.connection_closed()

        mock_logger.info.assert_called_once_with("database_connection_closed")


class TestGraphClientProbe:
    """Tests for GraphClientProbe protocol and implementation."""

    def test_default_probe_creates_with_default_logger(self):
        """Default probe should work without explicit logger."""
        probe = DefaultGraphClientProbe()
        assert probe._logger is not None

    def test_default_probe_accepts_custom_logger(self):
        """Default probe should accept a custom logger."""
        mock_logger = MagicMock(spec=structlog.stdlib.BoundLogger)
        probe = DefaultGraphClientProbe(logger=mock_logger)
        assert probe._logger is mock_logger

    def test_connected_to_graph_logs_info(self):
        """connected_to_graph should log with graph name."""
        mock_logger = MagicMock(spec=structlog.stdlib.BoundLogger)
        probe = DefaultGraphClientProbe(logger=mock_logger)

        probe.connected_to_graph(graph_name="test_graph")

        mock_logger.info.assert_called_once_with(
            "graph_connected",
            graph_name="test_graph",
        )

    def test_graph_created_logs_info(self):
        """graph_created should log with graph name."""
        mock_logger = MagicMock(spec=structlog.stdlib.BoundLogger)
        probe = DefaultGraphClientProbe(logger=mock_logger)

        probe.graph_created(graph_name="new_graph")

        mock_logger.info.assert_called_once_with(
            "graph_created",
            graph_name="new_graph",
        )

    def test_connection_verification_failed_logs_warning(self):
        """connection_verification_failed should log warning with error."""
        mock_logger = MagicMock(spec=structlog.stdlib.BoundLogger)
        probe = DefaultGraphClientProbe(logger=mock_logger)
        error = Exception("Verification timeout")

        probe.connection_verification_failed(error=error)

        mock_logger.warning.assert_called_once_with(
            "graph_connection_verification_failed",
            error="Verification timeout",
        )

    def test_query_failed_logs_error(self):
        """query_failed should log error with query and error."""
        mock_logger = MagicMock(spec=structlog.stdlib.BoundLogger)
        probe = DefaultGraphClientProbe(logger=mock_logger)
        error = Exception("Syntax error")

        probe.query_failed(query="MATCH (n) RETURN n", error=error)

        mock_logger.error.assert_called_once_with(
            "graph_query_failed",
            query="MATCH (n) RETURN n",
            error="Syntax error",
        )

    def test_query_executed_logs_info(self):
        """query_executed should log info with query and row count."""
        mock_logger = MagicMock(spec=structlog.stdlib.BoundLogger)
        probe = DefaultGraphClientProbe(logger=mock_logger)

        probe.query_executed(query="MATCH (n) RETURN n", row_count=5)

        mock_logger.info.assert_called_once_with(
            "graph_query_executed",
            query="MATCH (n) RETURN n",
            row_count=5,
        )

    def test_transaction_started_logs_info(self):
        """transaction_started should log info."""
        mock_logger = MagicMock(spec=structlog.stdlib.BoundLogger)
        probe = DefaultGraphClientProbe(logger=mock_logger)

        probe.transaction_started()

        mock_logger.info.assert_called_once_with("graph_transaction_started")

    def test_transaction_committed_logs_info(self):
        """transaction_committed should log info."""
        mock_logger = MagicMock(spec=structlog.stdlib.BoundLogger)
        probe = DefaultGraphClientProbe(logger=mock_logger)

        probe.transaction_committed()

        mock_logger.info.assert_called_once_with("graph_transaction_committed")

    def test_transaction_rolled_back_logs_warning(self):
        """transaction_rolled_back should log warning."""
        mock_logger = MagicMock(spec=structlog.stdlib.BoundLogger)
        probe = DefaultGraphClientProbe(logger=mock_logger)

        probe.transaction_rolled_back()

        mock_logger.warning.assert_called_once_with("graph_transaction_rolled_back")


class TestProbeProtocolCompliance:
    """Tests to verify implementations match Protocol expectations."""

    def test_default_connection_probe_matches_protocol(self):
        """DefaultConnectionProbe should implement ConnectionProbe protocol."""
        probe = DefaultConnectionProbe()
        # Protocol requires these methods
        assert hasattr(probe, "connection_established")
        assert hasattr(probe, "connection_failed")
        assert hasattr(probe, "connection_closed")
        assert hasattr(probe, "with_context")
        assert callable(probe.connection_established)
        assert callable(probe.connection_failed)
        assert callable(probe.connection_closed)
        assert callable(probe.with_context)

    def test_default_graph_client_probe_matches_protocol(self):
        """DefaultGraphClientProbe should implement GraphClientProbe protocol."""
        probe = DefaultGraphClientProbe()
        # Protocol requires these methods
        assert hasattr(probe, "connected_to_graph")
        assert hasattr(probe, "graph_created")
        assert hasattr(probe, "connection_verification_failed")
        assert hasattr(probe, "query_failed")
        assert hasattr(probe, "query_executed")
        assert hasattr(probe, "transaction_started")
        assert hasattr(probe, "transaction_committed")
        assert hasattr(probe, "transaction_rolled_back")
        assert hasattr(probe, "with_context")
        assert callable(probe.connected_to_graph)
        assert callable(probe.graph_created)
        assert callable(probe.connection_verification_failed)
        assert callable(probe.query_failed)
        assert callable(probe.query_executed)
        assert callable(probe.transaction_started)
        assert callable(probe.transaction_committed)
        assert callable(probe.transaction_rolled_back)
        assert callable(probe.with_context)


class TestObservationContext:
    """Tests for ObservationContext."""

    def test_context_creates_with_defaults(self):
        """Context should work with no arguments."""
        context = ObservationContext()
        assert context.request_id is None
        assert context.user_id is None
        assert context.tenant_id is None
        assert context.graph_name is None
        assert context.extra == {}

    def test_context_creates_with_values(self):
        """Context should accept all fields."""
        context = ObservationContext(
            request_id="req-123",
            user_id="user-456",
            tenant_id="tenant-789",
            graph_name="test_graph",
            extra={"custom": "value"},
        )
        assert context.request_id == "req-123"
        assert context.user_id == "user-456"
        assert context.tenant_id == "tenant-789"
        assert context.graph_name == "test_graph"
        assert context.extra == {"custom": "value"}

    def test_as_dict_excludes_none_values(self):
        """as_dict should only include non-None values."""
        context = ObservationContext(request_id="req-123")
        result = context.as_dict()
        assert result == {"request_id": "req-123"}
        assert "user_id" not in result
        assert "tenant_id" not in result

    def test_as_dict_includes_all_set_values(self):
        """as_dict should include all set values."""
        context = ObservationContext(
            request_id="req-123",
            user_id="user-456",
            extra={"custom": "value"},
        )
        result = context.as_dict()
        assert result == {
            "request_id": "req-123",
            "user_id": "user-456",
            "custom": "value",
        }

    def test_with_graph_creates_new_context(self):
        """with_graph should return new context with graph set."""
        original = ObservationContext(request_id="req-123")
        new_context = original.with_graph("my_graph")

        assert new_context is not original
        assert new_context.request_id == "req-123"
        assert new_context.graph_name == "my_graph"
        assert original.graph_name is None  # Original unchanged

    def test_with_extra_creates_new_context(self):
        """with_extra should return new context with additional metadata."""
        original = ObservationContext(request_id="req-123", extra={"a": 1})
        new_context = original.with_extra(b=2, c=3)

        assert new_context is not original
        assert new_context.request_id == "req-123"
        assert new_context.extra == {"a": 1, "b": 2, "c": 3}
        assert original.extra == {"a": 1}  # Original unchanged

    def test_context_is_immutable(self):
        """Context should be frozen (immutable)."""
        context = ObservationContext(request_id="req-123")
        try:
            context.request_id = "new-id"  # type: ignore
            assert False, "Should have raised FrozenInstanceError"
        except AttributeError:
            pass  # Expected for frozen dataclass


class TestProbesWithContext:
    """Tests for probes with observation context."""

    def test_connection_probe_with_context_includes_metadata(self):
        """ConnectionProbe with context should include context in logs."""
        mock_logger = MagicMock(spec=structlog.stdlib.BoundLogger)
        context = ObservationContext(request_id="req-123", user_id="user-456")
        probe = DefaultConnectionProbe(logger=mock_logger).with_context(context)

        probe.connection_established(host="localhost", database="testdb")

        mock_logger.info.assert_called_once_with(
            "database_connection_established",
            host="localhost",
            database="testdb",
            request_id="req-123",
            user_id="user-456",
        )

    def test_connection_probe_with_context_preserves_logger(self):
        """with_context should preserve the logger."""
        mock_logger = MagicMock(spec=structlog.stdlib.BoundLogger)
        context = ObservationContext(request_id="req-123")
        probe = DefaultConnectionProbe(logger=mock_logger)
        new_probe = probe.with_context(context)

        assert new_probe._logger is mock_logger

    def test_graph_probe_with_context_includes_metadata(self):
        """GraphClientProbe with context should include context in logs."""
        mock_logger = MagicMock(spec=structlog.stdlib.BoundLogger)
        context = ObservationContext(request_id="req-123", user_id="user-456")
        probe = DefaultGraphClientProbe(logger=mock_logger).with_context(context)

        probe.connected_to_graph(graph_name="test_graph")

        mock_logger.info.assert_called_once_with(
            "graph_connected",
            graph_name="test_graph",
            request_id="req-123",
            user_id="user-456",
        )

    def test_graph_probe_query_failed_with_context(self):
        """query_failed should include context metadata."""
        mock_logger = MagicMock(spec=structlog.stdlib.BoundLogger)
        context = ObservationContext(request_id="req-123", user_id="user-456")
        probe = DefaultGraphClientProbe(logger=mock_logger).with_context(context)
        error = Exception("Syntax error")

        probe.query_failed(query="MATCH (n) RETURN n", error=error)

        mock_logger.error.assert_called_once_with(
            "graph_query_failed",
            query="MATCH (n) RETURN n",
            error="Syntax error",
            request_id="req-123",
            user_id="user-456",
        )
