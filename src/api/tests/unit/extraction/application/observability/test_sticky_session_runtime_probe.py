"""Unit tests for StickySessionRuntimeProbe.

Following Domain-Oriented Observability patterns, these probes must capture
the real failure detail (e.g. the raw OpenShell CLI stderr) whenever a
sticky runtime fails to start, so that production failures are visible in
structured logs without needing to reproduce them by hand.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import structlog

from extraction.application.observability.sticky_session_runtime_probe import (
    DefaultStickySessionRuntimeProbe,
)


class TestStickySessionRuntimeProbe:
    def test_default_probe_creates_with_default_logger(self):
        probe = DefaultStickySessionRuntimeProbe()
        assert probe._logger is not None

    def test_runtime_start_failed_logs_error_with_detail(self):
        mock_logger = MagicMock(spec=structlog.stdlib.BoundLogger)
        probe = DefaultStickySessionRuntimeProbe(logger=mock_logger)

        probe.runtime_start_failed(
            session_id="session-1",
            knowledge_graph_id="kg-1",
            mode="schema_bootstrap",
            error="openshell provider create --name kartograph-gma failed: no credentials resolved",
        )

        mock_logger.error.assert_called_once_with(
            "sticky_runtime_start_failed",
            session_id="session-1",
            knowledge_graph_id="kg-1",
            mode="schema_bootstrap",
            error="openshell provider create --name kartograph-gma failed: no credentials resolved",
        )

    def test_runtime_unhealthy_logs_error_with_detail(self):
        mock_logger = MagicMock(spec=structlog.stdlib.BoundLogger)
        probe = DefaultStickySessionRuntimeProbe(logger=mock_logger)

        probe.runtime_unhealthy(
            session_id="session-1",
            knowledge_graph_id="kg-1",
            mode="schema_bootstrap",
            error="timed out waiting for sticky runtime health",
        )

        mock_logger.error.assert_called_once_with(
            "sticky_runtime_unhealthy",
            session_id="session-1",
            knowledge_graph_id="kg-1",
            mode="schema_bootstrap",
            error="timed out waiting for sticky runtime health",
        )
