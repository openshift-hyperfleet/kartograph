"""Unit tests for DefaultQueryServiceProbe log-redaction contract.

Spec: specs/query/query-execution.spec.md
Requirement: Read-Only Enforcement — Scenario: Keyword blacklist (secondary)

The spec states:
  "AND a redacted reference is logged (not the raw query text)"
  "AND the error response includes a correlation ID for log lookup"

These tests verify that DefaultQueryServiceProbe.cypher_query_rejected
never forwards the raw query text to the underlying logger, using
structlog.testing.capture_logs() to inspect actual log events produced
by the probe rather than relying on mock assertions alone.

This file is deliberately kept separate from test_application_services.py
(which also exercises the probe via MagicMock) to provide a complementary
end-to-end test of the structlog output — the canonical regression guard
for the redacted-logging contract.
"""

from __future__ import annotations

import structlog

from query.application.observability import DefaultQueryServiceProbe


class TestDefaultQueryServiceProbeCypherQueryRejected:
    """Verify DefaultQueryServiceProbe.cypher_query_rejected redacts the raw query.

    These tests use structlog.testing.capture_logs() — the canonical structlog
    test helper (available since structlog ≥ 20.2.0) — to capture actual log
    events without mocking the logger instance.  Each test inspects the
    captured event dictionary to assert on the presence/absence of specific
    fields.
    """

    def test_raw_query_not_in_log_event(self) -> None:
        """The raw query text MUST NOT appear in the structured log event.

        The probe receives the raw query so that callers do not have to
        sanitise it before calling cypher_query_rejected, but the
        DefaultQueryServiceProbe implementation is required to never forward
        that text to the underlying logger.  Raw queries can contain sensitive
        data (e.g. property values, node labels reflecting internal taxonomy).
        """
        probe = DefaultQueryServiceProbe()
        secret_query = "CREATE (n:SuperSecret {password: 'hunter2'})"

        with structlog.testing.capture_logs() as cap:
            probe.cypher_query_rejected(
                query=secret_query,
                reason="Found forbidden keyword: CREATE",
                correlation_id="test-corr-id-001",
            )

        assert len(cap) == 1, f"Expected exactly one log event, got {len(cap)}: {cap}"
        log_event = cap[0]
        # The raw query MUST NOT appear in any field of the log event.
        event_str = str(log_event)
        assert secret_query not in event_str, (
            "Raw query text MUST NOT be logged — it may contain sensitive data. "
            f"Found in log event: {log_event}"
        )

    def test_correlation_id_present_in_log_event(self) -> None:
        """The correlation_id MUST be logged for cross-referencing with the error response.

        Operators must be able to match the redacted log entry to the
        correlation ID returned in the HTTP/MCP error response so they can
        reconstruct what happened without re-exposing the raw query.
        """
        probe = DefaultQueryServiceProbe()

        with structlog.testing.capture_logs() as cap:
            probe.cypher_query_rejected(
                query="CREATE (n:Test)",
                reason="forbidden keyword",
                correlation_id="corr-xyz-789",
            )

        log_event = cap[0]
        assert log_event.get("correlation_id") == "corr-xyz-789", (
            "correlation_id MUST be in the log event so the redacted log can be "
            "matched to the error response sent to the client.  "
            f"Got log_event: {log_event}"
        )

    def test_reason_present_in_log_event(self) -> None:
        """The rejection reason MUST appear in the log (non-sensitive).

        The reason names the forbidden keyword category, which is safe to log
        (it does not reproduce user-supplied data) and is necessary for
        security audit trails.
        """
        probe = DefaultQueryServiceProbe()

        with structlog.testing.capture_logs() as cap:
            probe.cypher_query_rejected(
                query="DELETE (n)",
                reason="Found forbidden keyword: DELETE",
                correlation_id="corr-abc-123",
            )

        log_event = cap[0]
        assert "Found forbidden keyword: DELETE" in log_event.get("reason", ""), (
            f"Expected rejection reason in 'reason' field; got: {log_event}"
        )

    def test_log_level_is_warning(self) -> None:
        """Rejected queries are security violations — log level MUST be warning or higher.

        Rejected-query events are security-relevant (someone sent a mutation
        query) so they must be emitted at warning level or above to surface in
        default log configurations that suppress INFO.
        """
        probe = DefaultQueryServiceProbe()

        with structlog.testing.capture_logs() as cap:
            probe.cypher_query_rejected(
                query="MERGE (n)",
                reason="forbidden keyword",
                correlation_id="corr-warn-001",
            )

        log_event = cap[0]
        level = log_event.get("log_level", "")
        assert level in ("warning", "error", "critical"), (
            f"Expected warning level or higher for a security rejection, "
            f"got: {level!r}.  Full event: {log_event}"
        )

    def test_no_raw_query_even_when_correlation_id_is_none(self) -> None:
        """Raw query MUST NOT appear even when correlation_id is None.

        When a forbidden query is caught before a correlation ID is assigned
        (e.g. during a defensive pre-check), the probe must still redact the
        query text from the log output.
        """
        probe = DefaultQueryServiceProbe()
        secret_query = "SET n.password = 'exposed'"

        with structlog.testing.capture_logs() as cap:
            probe.cypher_query_rejected(
                query=secret_query,
                reason="Found forbidden keyword: SET",
                correlation_id=None,
            )

        event_str = str(cap[0])
        assert secret_query not in event_str, (
            "Raw query text MUST NOT be logged even when correlation_id is None. "
            f"Found in log event: {cap[0]}"
        )

    def test_log_event_name_is_mcp_cypher_query_rejected(self) -> None:
        """The structlog event name MUST be 'mcp_cypher_query_rejected'.

        A stable event name allows log aggregators (e.g. Loki, Splunk) to
        build dashboards and alerts specifically for rejected query events
        without parsing free-form message strings.
        """
        probe = DefaultQueryServiceProbe()

        with structlog.testing.capture_logs() as cap:
            probe.cypher_query_rejected(
                query="LOAD CSV FROM 'file.csv'",
                reason="Found forbidden keyword: LOAD",
                correlation_id="corr-event-name-check",
            )

        log_event = cap[0]
        assert log_event.get("event") == "mcp_cypher_query_rejected", (
            f"Expected event name 'mcp_cypher_query_rejected', "
            f"got: {log_event.get('event')!r}"
        )
