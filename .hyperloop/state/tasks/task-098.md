---
id: task-098
title: Test that DefaultQueryServiceProbe omits raw query text from rejected-query logs
spec_ref: "specs/query/query-execution.spec.md@dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "test(query): verify redacted logging in DefaultQueryServiceProbe.cypher_query_rejected"
pr_description: |
  ## What & Why

  The **Requirement: Read-Only Enforcement — Scenario: Keyword blacklist
  (secondary)** in `specs/query/query-execution.spec.md` states:

  > AND a redacted reference is logged (not the raw query text)
  > AND the error response includes a correlation ID for log lookup

  `DefaultQueryServiceProbe.cypher_query_rejected` in
  `src/api/query/application/observability.py` correctly implements this:
  it logs `mcp_cypher_query_rejected` with `reason` and `correlation_id`
  but does **not** include the `query` parameter in the `structlog.warning`
  call. A code comment even flags this explicitly:

  ```python
  # IMPORTANT: Do NOT log `query` — log only the correlation_id so that
  # raw query text never appears in log output (spec: redacted reference).
  ```

  However, **no test verifies this property**. A future refactor (e.g.,
  adding `query` for debugging convenience) could silently violate the spec
  without any test catching it. This PR closes that gap.

  ## Spec Requirements Satisfied

  - Requirement: Read-Only Enforcement / Scenario: Keyword blacklist (secondary)
    — "AND a redacted reference is logged (not the raw query text)"

  ## Files Affected

  - `src/api/tests/unit/query/test_observability.py` *(new file)*
    — or added to an existing observability test file if one exists

  ## Test Design

  The tests capture `structlog` output using `structlog.testing.capture_logs()`
  (a context manager that intercepts log events into a list of dicts).

  ```python
  import structlog
  from query.application.observability import DefaultQueryServiceProbe

  class TestDefaultQueryServiceProbeCypherQueryRejected:
      \"\"\"Verify DefaultQueryServiceProbe.cypher_query_rejected redacts the raw query.\"\"\"

      def test_raw_query_not_in_log_event(self):
          \"\"\"The raw query text MUST NOT appear in the structured log event.\"\"\"
          probe = DefaultQueryServiceProbe()
          secret_query = "CREATE (n:SuperSecret {password: 'hunter2'})"

          with structlog.testing.capture_logs() as cap:
              probe.cypher_query_rejected(
                  query=secret_query,
                  reason="Found forbidden keyword: CREATE",
                  correlation_id="test-corr-id-001",
              )

          assert len(cap) == 1
          log_event = cap[0]
          # The raw query MUST NOT appear in any field of the log event
          event_str = str(log_event)
          assert secret_query not in event_str, (
              "Raw query text MUST NOT be logged — it may contain sensitive data. "
              f"Found in log event: {log_event}"
          )

      def test_correlation_id_present_in_log_event(self):
          \"\"\"The correlation_id MUST be logged for cross-referencing with the error response.\"\"\"
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
              "matched to the error response sent to the client"
          )

      def test_reason_present_in_log_event(self):
          \"\"\"The rejection reason MUST appear in the log (non-sensitive)\"\"\"
          probe = DefaultQueryServiceProbe()

          with structlog.testing.capture_logs() as cap:
              probe.cypher_query_rejected(
                  query="DELETE (n)",
                  reason="Found forbidden keyword: DELETE",
                  correlation_id="corr-abc-123",
              )

          log_event = cap[0]
          assert "Found forbidden keyword: DELETE" in log_event.get("reason", "")

      def test_log_level_is_warning(self):
          \"\"\"Rejected queries are security violations — log level MUST be warning or higher.\"\"\"
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
              f"Expected warning level or higher, got: {level!r}"
          )

      def test_no_raw_query_even_when_correlation_id_is_none(self):
          \"\"\"Raw query MUST NOT appear even when correlation_id is None.\"\"\"
          probe = DefaultQueryServiceProbe()
          secret_query = "SET n.password = 'exposed'"

          with structlog.testing.capture_logs() as cap:
              probe.cypher_query_rejected(
                  query=secret_query,
                  reason="Found forbidden keyword: SET",
                  correlation_id=None,
              )

          event_str = str(cap[0])
          assert secret_query not in event_str
  ```

  ## TDD Cycle

  1. Create `src/api/tests/unit/query/test_observability.py` with the tests
     above (they will be GREEN immediately because the implementation is correct).
  2. Run: `cd src/api && uv run pytest tests/unit/query/test_observability.py -v`
  3. All tests must pass.
  4. These tests act as a **regression guard**: if anyone modifies
     `cypher_query_rejected` to accidentally log the query, the tests will fail.

  ## How to Verify

  ```bash
  cd src/api && uv run pytest tests/unit/query/test_observability.py -v
  ```

  ## Design Notes

  - `structlog.testing.capture_logs()` is available in `structlog >= 20.2.0`
    and is the canonical way to test structlog-based logging without mocking
    the logger instance.
  - The probe file is `src/api/query/application/observability.py`.
    `DefaultQueryServiceProbe` is the concrete class under test; the
    `QueryServiceProbe` protocol is tested implicitly through the service tests.
  - No changes to implementation files are expected (tests are GREEN against
    the current, already-correct implementation).
---
