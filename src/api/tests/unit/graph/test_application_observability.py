"""Unit tests for Graph application layer probes."""

from unittest.mock import MagicMock

import structlog

from graph.application.observability import (
    DefaultGraphServiceProbe,
)


class TestDefaultGraphServiceProbe:
    """Tests for DefaultGraphServiceProbe."""

    def test_creates_with_default_logger(self):
        """Should create with default logger when none provided."""
        probe = DefaultGraphServiceProbe()
        assert probe._logger is not None

    def test_accepts_custom_logger(self):
        """Should accept custom logger."""
        mock_logger = MagicMock(spec=structlog.stdlib.BoundLogger)
        probe = DefaultGraphServiceProbe(logger=mock_logger)
        assert probe._logger is mock_logger


class TestSlugSearched:
    """Tests for slug_searched method."""

    def test_logs_with_correct_parameters(self):
        """slug_searched should log with slug, type, and count."""
        mock_logger = MagicMock(spec=structlog.stdlib.BoundLogger)
        probe = DefaultGraphServiceProbe(logger=mock_logger)

        probe.slug_searched(slug="alice", node_type="Person", result_count=2)

        mock_logger.info.assert_called_once_with(
            "graph_slug_searched",
            slug="alice",
            node_type="Person",
            result_count=2,
        )

    def test_logs_with_none_node_type(self):
        """slug_searched should handle None node_type."""
        mock_logger = MagicMock(spec=structlog.stdlib.BoundLogger)
        probe = DefaultGraphServiceProbe(logger=mock_logger)

        probe.slug_searched(slug="test", node_type=None, result_count=0)

        mock_logger.info.assert_called_once_with(
            "graph_slug_searched",
            slug="test",
            node_type=None,
            result_count=0,
        )


class TestRawQueryExecuted:
    """Tests for raw_query_executed method."""

    def test_logs_with_correct_parameters(self):
        """raw_query_executed should log with query and count."""
        mock_logger = MagicMock(spec=structlog.stdlib.BoundLogger)
        probe = DefaultGraphServiceProbe(logger=mock_logger)

        probe.raw_query_executed(query="MATCH (n) RETURN n", result_count=10)

        mock_logger.info.assert_called_once_with(
            "graph_raw_query_executed",
            query="MATCH (n) RETURN n",
            result_count=10,
        )


class TestWithContext:
    """Tests for context binding."""

    def test_with_context_creates_new_probe(self):
        """with_context should create a new probe with context bound."""
        from shared_kernel.observability_context import ObservationContext

        probe = DefaultGraphServiceProbe()
        context = ObservationContext(request_id="req-123", graph_name="test_graph")

        new_probe = probe.with_context(context)

        assert new_probe is not probe
        assert new_probe._context is context

    def test_with_context_preserves_logger(self):
        """with_context should preserve the original logger."""
        from shared_kernel.observability_context import ObservationContext

        mock_logger = MagicMock(spec=structlog.stdlib.BoundLogger)
        probe = DefaultGraphServiceProbe(logger=mock_logger)
        context = ObservationContext()

        new_probe = probe.with_context(context)

        assert new_probe._logger is mock_logger

    def test_context_included_in_log_calls(self):
        """Bound context should be included in log calls."""
        from shared_kernel.observability_context import ObservationContext

        mock_logger = MagicMock(spec=structlog.stdlib.BoundLogger)
        probe = DefaultGraphServiceProbe(logger=mock_logger)
        context = ObservationContext(request_id="req-456", graph_name="my_graph")

        probe_with_context = probe.with_context(context)
        probe_with_context.slug_searched(
            slug="test", node_type="Person", result_count=1
        )

        mock_logger.info.assert_called_once_with(
            "graph_slug_searched",
            slug="test",
            node_type="Person",
            result_count=1,
            request_id="req-456",
            graph_name="my_graph",
        )


class TestMutationServerErrorOccurred:
    """Tests for mutation_server_error_occurred method.

    The probe is used in the presentation layer to emit domain-observable
    events when server-side (infrastructure/database) errors occur during
    mutation processing, instead of calling logger.error() directly.
    """

    def test_logs_at_error_level_with_errors_list(self):
        """mutation_server_error_occurred should log at error level with errors."""
        mock_logger = MagicMock(spec=structlog.stdlib.BoundLogger)
        probe = DefaultGraphServiceProbe(logger=mock_logger)

        probe.mutation_server_error_occurred(errors=["Database connection failed"])

        mock_logger.error.assert_called_once_with(
            "graph_mutation_server_error",
            errors=["Database connection failed"],
        )

    def test_logs_multiple_errors(self):
        """mutation_server_error_occurred should handle multiple error strings."""
        mock_logger = MagicMock(spec=structlog.stdlib.BoundLogger)
        probe = DefaultGraphServiceProbe(logger=mock_logger)

        errors = ["Error 1: timeout", "Error 2: constraint violation"]
        probe.mutation_server_error_occurred(errors=errors)

        mock_logger.error.assert_called_once_with(
            "graph_mutation_server_error",
            errors=errors,
        )

    def test_logs_empty_error_list(self):
        """mutation_server_error_occurred should handle an empty error list."""
        mock_logger = MagicMock(spec=structlog.stdlib.BoundLogger)
        probe = DefaultGraphServiceProbe(logger=mock_logger)

        probe.mutation_server_error_occurred(errors=[])

        mock_logger.error.assert_called_once_with(
            "graph_mutation_server_error",
            errors=[],
        )
