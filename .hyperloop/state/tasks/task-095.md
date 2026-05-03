---
id: task-095
title: Query execution — MCPQueryService error categorization unit tests
spec_ref: specs/query/query-execution.spec.md@dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2
status: not_started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: 'test(query): add MCPQueryService unit tests for all Error Categorization
  scenarios'
pr_description: "## What & Why\n\nThe **Requirement: Error Categorization** in `specs/query/query-execution.spec.md`\n\
  specifies four distinct error types that the system must produce:\n\n| Spec scenario\
  \ | Error type |\n|---|---|\n| Query containing mutation keywords | `\"forbidden\"\
  ` |\n| Query that exceeds the timeout | `\"timeout\"` |\n| Query with syntax error\
  \ or runtime failure | `\"execution_error\"` |\n| Unexpected failure during query\
  \ execution | `\"unknown_error\"` |\n\nThe application service layer (`MCPQueryService`)\
  \ is the component responsible for\nconverting repository exceptions into typed\
  \ `QueryError` value objects. Currently:\n\n- `QueryGraphRepository` raises `QueryForbiddenError`,\
  \ `QueryTimeoutError`,\n  `QueryExecutionError`, or generic `Exception` for each\
  \ scenario.\n- `MCPQueryService.execute_cypher_query()` catches each exception type\
  \ and maps it\n  to the corresponding `error_type` string.\n- The MCP presentation\
  \ layer (`mcp.py`) reads the `error_type` from the `QueryError`\n  and includes\
  \ it in the JSON response.\n\n**The gap**: `MCPQueryService` has no dedicated unit\
  \ test file. The service's\nerror categorisation contract is only tested indirectly:\n\
  \n- `test_query_repository.py` — tests the repository raises the right exceptions\n\
  - `test_mcp_query_tool.py` — tests `_build_error_response()` (presentation layer\n\
  \  helper) converts `QueryError` objects to response dicts\n\nNeither test file\
  \ exercises `MCPQueryService` in isolation with a fake repository.\nIf the `except`\
  \ clauses in `execute_cypher_query()` were accidentally reordered or\none was removed,\
  \ existing tests would not catch it.\n\n## What This PR Does\n\n### 1. Create `tests/unit/query/test_mcp_query_service.py`\n\
  \nTDD: write all tests before any implementation changes. Use a `FakeQueryRepository`\n\
  that raises configurable exceptions.\n\n```python\nclass FakeQueryRepository(IQueryGraphRepository):\n\
  \    \"\"\"Fake repository that raises a pre-configured exception or returns rows.\"\
  \"\"\n\n    def __init__(\n        self,\n        rows: list | None = None,\n  \
  \      raises: Exception | None = None,\n    ) -> None:\n        self._rows = rows\
  \ or []\n        self._raises = raises\n\n    def execute_cypher(self, query: str,\
  \ timeout_seconds: int = 30, max_rows: int = 1000):\n        if self._raises is\
  \ not None:\n            raise self._raises\n        return self._rows\n```\n\n\
  ### 2. Error Categorization tests (four spec scenarios)\n\n**Scenario: Forbidden\
  \ query → error_type \"forbidden\"**\n\n```python\ndef test_forbidden_error_type_when_repo_raises_query_forbidden_error():\n\
  \    repo = FakeQueryRepository(raises=QueryForbiddenError(\n        \"Forbidden\
  \ keyword\", query=\"CREATE (n)\", correlation_id=\"corr-1\"\n    ))\n    service\
  \ = MCPQueryService(repository=repo)\n    result = service.execute_cypher_query(query=\"\
  CREATE (n)\")\n    assert isinstance(result, QueryError)\n    assert result.error_type\
  \ == \"forbidden\"\n    assert result.correlation_id == \"corr-1\"\n```\n\n**Scenario:\
  \ Timeout error → error_type \"timeout\"**\n\n```python\ndef test_timeout_error_type_when_repo_raises_query_timeout_error():\n\
  \    repo = FakeQueryRepository(raises=QueryTimeoutError(\n        \"Query timed\
  \ out\", query=\"MATCH (n) RETURN n\", correlation_id=\"corr-2\"\n    ))\n    service\
  \ = MCPQueryService(repository=repo)\n    result = service.execute_cypher_query(query=\"\
  MATCH (n) RETURN n\")\n    assert isinstance(result, QueryError)\n    assert result.error_type\
  \ == \"timeout\"\n    assert result.correlation_id == \"corr-2\"\n```\n\n**Scenario:\
  \ Execution error → error_type \"execution_error\"**\n\n```python\ndef test_execution_error_type_when_repo_raises_query_execution_error():\n\
  \    repo = FakeQueryRepository(raises=QueryExecutionError(\n        \"Syntax error\"\
  , query=\"MATCH (n RETURN n\"\n    ))\n    service = MCPQueryService(repository=repo)\n\
  \    result = service.execute_cypher_query(query=\"MATCH (n RETURN n\")\n    assert\
  \ isinstance(result, QueryError)\n    assert result.error_type == \"execution_error\"\
  \n    assert result.correlation_id is None\n```\n\n**Scenario: Unexpected error\
  \ → error_type \"unknown_error\"**\n\n```python\ndef test_unknown_error_type_when_repo_raises_unexpected_exception():\n\
  \    repo = FakeQueryRepository(raises=RuntimeError(\"Unexpected DB failure\"))\n\
  \    service = MCPQueryService(repository=repo)\n    result = service.execute_cypher_query(query=\"\
  MATCH (n) RETURN n\")\n    assert isinstance(result, QueryError)\n    assert result.error_type\
  \ == \"unknown_error\"\n    assert result.correlation_id is None\n```\n\n### 3.\
  \ Successful query test (Requirement: Timeout Enforcement — happy path)\n\nThe spec\
  \ states \"Query within timeout → results returned normally.\" This tests that\n\
  the service returns a `CypherQueryResult` (not `QueryError`) when the repository\n\
  succeeds:\n\n```python\ndef test_returns_cypher_query_result_on_success():\n   \
  \ from query.domain.value_objects import NodeDict\n    node = NodeDict(id=\"1\"\
  , label=\"Person\", properties={\"name\": \"Alice\"})\n    repo = FakeQueryRepository(rows=[{\"\
  node\": node}])\n    service = MCPQueryService(repository=repo)\n    result = service.execute_cypher_query(query=\"\
  MATCH (n) RETURN n\")\n    assert isinstance(result, CypherQueryResult)\n    assert\
  \ result.row_count == 1\n    assert result.rows == [{\"node\": node}]\n    assert\
  \ result.truncated is False or result.truncated is True  # depends on limit\n```\n\
  \n### 4. Probe observability tests\n\nVerify the domain probe is called correctly\
  \ (Domain-Oriented Observability pattern):\n\n```python\ndef test_probe_cypher_query_received_called():\n\
  \    \"\"\"Probe records the incoming query.\"\"\"\n    probe = MagicMock(spec=QueryServiceProbe)\n\
  \    repo = FakeQueryRepository(rows=[])\n    service = MCPQueryService(repository=repo,\
  \ probe=probe)\n    service.execute_cypher_query(query=\"MATCH (n) RETURN n\")\n\
  \    probe.cypher_query_received.assert_called_once()\n\ndef test_probe_cypher_query_rejected_called_on_forbidden():\n\
  \    \"\"\"Probe records rejection with correlation_id.\"\"\"\n    probe = MagicMock(spec=QueryServiceProbe)\n\
  \    repo = FakeQueryRepository(raises=QueryForbiddenError(\n        \"Forbidden\"\
  , query=\"CREATE\", correlation_id=\"c-1\"\n    ))\n    service = MCPQueryService(repository=repo,\
  \ probe=probe)\n    service.execute_cypher_query(query=\"CREATE\")\n    probe.cypher_query_rejected.assert_called_once()\n\
  \    call_kwargs = probe.cypher_query_rejected.call_args.kwargs\n    assert call_kwargs.get(\"\
  correlation_id\") == \"c-1\"\n\ndef test_probe_cypher_query_failed_called_on_timeout():\n\
  \    \"\"\"Probe records failure with correlation_id on timeout.\"\"\"\n    probe\
  \ = MagicMock(spec=QueryServiceProbe)\n    repo = FakeQueryRepository(raises=QueryTimeoutError(\n\
  \        \"Timeout\", query=\"MATCH (n) RETURN n\", correlation_id=\"t-1\"\n   \
  \ ))\n    service = MCPQueryService(repository=repo, probe=probe)\n    service.execute_cypher_query(query=\"\
  MATCH (n) RETURN n\")\n    probe.cypher_query_failed.assert_called_once()\n    call_kwargs\
  \ = probe.cypher_query_failed.call_args.kwargs\n    assert call_kwargs.get(\"correlation_id\"\
  ) == \"t-1\"\n```\n\n## Files Affected\n\n- `src/api/tests/unit/query/test_mcp_query_service.py`\
  \ — **new test file** with\n  all tests listed above\n- `src/api/query/application/services.py`\
  \ — no changes expected; if any test fails,\n  fix the service implementation (TDD:\
  \ tests are authoritative)\n- `src/api/query/domain/value_objects.py` — no changes\
  \ expected\n\n## How to Verify\n\n1. `cd src/api && uv run pytest tests/unit/query/test_mcp_query_service.py\
  \ -v`\n   All new tests must pass (RED → GREEN cycle).\n2. `cd src/api && uv run\
  \ pytest tests/unit/query/ -v` — no regressions.\n3. Trace each spec scenario to\
  \ the test that covers it:\n   - Forbidden query → `test_forbidden_error_type_when_repo_raises_query_forbidden_error`\n\
  \   - Timeout → `test_timeout_error_type_when_repo_raises_query_timeout_error`\n\
  \   - Execution error → `test_execution_error_type_when_repo_raises_query_execution_error`\n\
  \   - Unexpected error → `test_unknown_error_type_when_repo_raises_unexpected_exception`\n\
  \n## Design Decisions\n\n- **`FakeQueryRepository` not `MockRepository`**: Per the\
  \ project's testing philosophy,\n  fakes are preferred over mocks for ports (repository\
  \ interfaces). The fake implements\n  `IQueryGraphRepository` and raises a configurable\
  \ exception, making tests readable\n  without `MagicMock.side_effect` boilerplate.\n\
  - **Service layer isolation**: These tests exercise `MCPQueryService` in isolation,\n\
  \  independent of the actual `QueryGraphRepository`, the AGE database, or the MCP\n\
  \  presentation layer. This makes them fast and deterministic.\n- **Correlation_id\
  \ propagation**: `QueryForbiddenError` and `QueryTimeoutError` carry\n  a `correlation_id`\
  \ attribute set by the repository. The service must propagate this\n  into the returned\
  \ `QueryError`. These tests verify the propagation, complementing\n  the repository-level\
  \ tests that verify generation and the presentation-level tests\n  that verify inclusion\
  \ in the JSON response.\n- **No mock for `DefaultQueryServiceProbe`**: Tests that\
  \ don't verify probe behaviour\n  use `MCPQueryService(repository=repo)` without\
  \ a probe argument, relying on the\n  `DefaultQueryServiceProbe` no-op. Tests verifying\
  \ probe behaviour pass a `MagicMock`\n  with `spec=QueryServiceProbe` so typos in\
  \ probe method names are caught.\n\n## Spec Requirement Coverage\n\n**Requirement:\
  \ Error Categorization** from `specs/query/query-execution.spec.md`:\n\n| Scenario\
  \ | Test |\n|---|---|\n| Forbidden query → `\"forbidden\"` | `test_forbidden_error_type_when_repo_raises_query_forbidden_error`\
  \ |\n| Timeout → `\"timeout\"` | `test_timeout_error_type_when_repo_raises_query_timeout_error`\
  \ |\n| Execution error → `\"execution_error\"` | `test_execution_error_type_when_repo_raises_query_execution_error`\
  \ |\n| Unexpected failure → `\"unknown_error\"` | `test_unknown_error_type_when_repo_raises_unexpected_exception`\
  \ |\n\n**Requirement: Timeout Enforcement — Scenario: Query within timeout** from\n\
  `specs/query/query-execution.spec.md`:\n\n| Scenario | Test |\n|---|---|\n| Query\
  \ within timeout → results returned normally | `test_returns_cypher_query_result_on_success`\
  \ |\n\n## Gap Analysis\n\n`MCPQueryService.execute_cypher_query()` has four `except`\
  \ clauses corresponding\nto the four spec scenarios. Prior to this task, no unit\
  \ test exercised the service\nlayer directly. If a future refactor accidentally\
  \ merged two clauses or changed an\n`error_type` string, no existing test would\
  \ catch it. This task closes that gap with\ndirect, isolated unit tests.\n\nRelated\
  \ tasks:\n- task-088: Adds `correlation_id` to MCP error response dict (presentation\
  \ layer)\n- task-090: Per-tenant graph routing (infrastructure layer)\n- The repository-level\
  \ exception raising is tested in `test_query_repository.py`\n\n## TDD Cycle\n\n\
  1. Create `src/api/tests/unit/query/test_mcp_query_service.py` with the tests above.\n\
  2. Run `cd src/api && uv run pytest tests/unit/query/test_mcp_query_service.py -v`\n\
  3. If all tests pass immediately (GREEN without code changes) — the implementation\n\
  \   is correct; commit.\n4. If any test fails — fix `MCPQueryService` to satisfy\
  \ the failing test; re-run.\n5. Commit atomically."
---
