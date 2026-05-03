---
id: task-098
title: Test that DefaultQueryServiceProbe omits raw query text from rejected-query
  logs
spec_ref: specs/query/query-execution.spec.md@dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2
status: complete
phase: null
deps: []
round: 0
branch: hyperloop/task-098
pr: https://github.com/openshift-hyperfleet/kartograph/pull/564
pr_title: 'test(query): verify redacted logging in DefaultQueryServiceProbe.cypher_query_rejected'
pr_description: "## What & Why\n\nThe **Requirement: Read-Only Enforcement — Scenario:\
  \ Keyword blacklist\n(secondary)** in `specs/query/query-execution.spec.md` states:\n\
  \n> AND a redacted reference is logged (not the raw query text)\n> AND the error\
  \ response includes a correlation ID for log lookup\n\n`DefaultQueryServiceProbe.cypher_query_rejected`\
  \ in\n`src/api/query/application/observability.py` correctly implements this:\n\
  it logs `mcp_cypher_query_rejected` with `reason` and `correlation_id`\nbut does\
  \ **not** include the `query` parameter in the `structlog.warning`\ncall. A code\
  \ comment even flags this explicitly:\n\n```python\n# IMPORTANT: Do NOT log `query`\
  \ — log only the correlation_id so that\n# raw query text never appears in log output\
  \ (spec: redacted reference).\n```\n\nHowever, **no test verifies this property**.\
  \ A future refactor (e.g.,\nadding `query` for debugging convenience) could silently\
  \ violate the spec\nwithout any test catching it. This PR closes that gap.\n\n##\
  \ Spec Requirements Satisfied\n\n- Requirement: Read-Only Enforcement / Scenario:\
  \ Keyword blacklist (secondary)\n  — \"AND a redacted reference is logged (not the\
  \ raw query text)\"\n\n## Files Affected\n\n- `src/api/tests/unit/query/test_observability.py`\
  \ *(new file)*\n  — or added to an existing observability test file if one exists\n\
  \n## Test Design\n\nThe tests capture `structlog` output using `structlog.testing.capture_logs()`\n\
  (a context manager that intercepts log events into a list of dicts).\n\n```python\n\
  import structlog\nfrom query.application.observability import DefaultQueryServiceProbe\n\
  \nclass TestDefaultQueryServiceProbeCypherQueryRejected:\n    \\\"\\\"\\\"Verify\
  \ DefaultQueryServiceProbe.cypher_query_rejected redacts the raw query.\\\"\\\"\\\
  \"\n\n    def test_raw_query_not_in_log_event(self):\n        \\\"\\\"\\\"The raw\
  \ query text MUST NOT appear in the structured log event.\\\"\\\"\\\"\n        probe\
  \ = DefaultQueryServiceProbe()\n        secret_query = \"CREATE (n:SuperSecret {password:\
  \ 'hunter2'})\"\n\n        with structlog.testing.capture_logs() as cap:\n     \
  \       probe.cypher_query_rejected(\n                query=secret_query,\n    \
  \            reason=\"Found forbidden keyword: CREATE\",\n                correlation_id=\"\
  test-corr-id-001\",\n            )\n\n        assert len(cap) == 1\n        log_event\
  \ = cap[0]\n        # The raw query MUST NOT appear in any field of the log event\n\
  \        event_str = str(log_event)\n        assert secret_query not in event_str,\
  \ (\n            \"Raw query text MUST NOT be logged — it may contain sensitive\
  \ data. \"\n            f\"Found in log event: {log_event}\"\n        )\n\n    def\
  \ test_correlation_id_present_in_log_event(self):\n        \\\"\\\"\\\"The correlation_id\
  \ MUST be logged for cross-referencing with the error response.\\\"\\\"\\\"\n  \
  \      probe = DefaultQueryServiceProbe()\n\n        with structlog.testing.capture_logs()\
  \ as cap:\n            probe.cypher_query_rejected(\n                query=\"CREATE\
  \ (n:Test)\",\n                reason=\"forbidden keyword\",\n                correlation_id=\"\
  corr-xyz-789\",\n            )\n\n        log_event = cap[0]\n        assert log_event.get(\"\
  correlation_id\") == \"corr-xyz-789\", (\n            \"correlation_id MUST be in\
  \ the log event so the redacted log can be \"\n            \"matched to the error\
  \ response sent to the client\"\n        )\n\n    def test_reason_present_in_log_event(self):\n\
  \        \\\"\\\"\\\"The rejection reason MUST appear in the log (non-sensitive)\\\
  \"\\\"\\\"\n        probe = DefaultQueryServiceProbe()\n\n        with structlog.testing.capture_logs()\
  \ as cap:\n            probe.cypher_query_rejected(\n                query=\"DELETE\
  \ (n)\",\n                reason=\"Found forbidden keyword: DELETE\",\n        \
  \        correlation_id=\"corr-abc-123\",\n            )\n\n        log_event =\
  \ cap[0]\n        assert \"Found forbidden keyword: DELETE\" in log_event.get(\"\
  reason\", \"\")\n\n    def test_log_level_is_warning(self):\n        \\\"\\\"\\\"\
  Rejected queries are security violations — log level MUST be warning or higher.\\\
  \"\\\"\\\"\n        probe = DefaultQueryServiceProbe()\n\n        with structlog.testing.capture_logs()\
  \ as cap:\n            probe.cypher_query_rejected(\n                query=\"MERGE\
  \ (n)\",\n                reason=\"forbidden keyword\",\n                correlation_id=\"\
  corr-warn-001\",\n            )\n\n        log_event = cap[0]\n        level = log_event.get(\"\
  log_level\", \"\")\n        assert level in (\"warning\", \"error\", \"critical\"\
  ), (\n            f\"Expected warning level or higher, got: {level!r}\"\n      \
  \  )\n\n    def test_no_raw_query_even_when_correlation_id_is_none(self):\n    \
  \    \\\"\\\"\\\"Raw query MUST NOT appear even when correlation_id is None.\\\"\
  \\\"\\\"\n        probe = DefaultQueryServiceProbe()\n        secret_query = \"\
  SET n.password = 'exposed'\"\n\n        with structlog.testing.capture_logs() as\
  \ cap:\n            probe.cypher_query_rejected(\n                query=secret_query,\n\
  \                reason=\"Found forbidden keyword: SET\",\n                correlation_id=None,\n\
  \            )\n\n        event_str = str(cap[0])\n        assert secret_query not\
  \ in event_str\n```\n\n## TDD Cycle\n\n1. Create `src/api/tests/unit/query/test_observability.py`\
  \ with the tests\n   above (they will be GREEN immediately because the implementation\
  \ is correct).\n2. Run: `cd src/api && uv run pytest tests/unit/query/test_observability.py\
  \ -v`\n3. All tests must pass.\n4. These tests act as a **regression guard**: if\
  \ anyone modifies\n   `cypher_query_rejected` to accidentally log the query, the\
  \ tests will fail.\n\n## How to Verify\n\n```bash\ncd src/api && uv run pytest tests/unit/query/test_observability.py\
  \ -v\n```\n\n## Design Notes\n\n- `structlog.testing.capture_logs()` is available\
  \ in `structlog >= 20.2.0`\n  and is the canonical way to test structlog-based logging\
  \ without mocking\n  the logger instance.\n- The probe file is `src/api/query/application/observability.py`.\n\
  \  `DefaultQueryServiceProbe` is the concrete class under test; the\n  `QueryServiceProbe`\
  \ protocol is tested implicitly through the service tests.\n- No changes to implementation\
  \ files are expected (tests are GREEN against\n  the current, already-correct implementation)."
---
