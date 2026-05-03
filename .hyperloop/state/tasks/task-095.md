---
id: task-095
title: Query execution — MCPQueryService error categorization unit tests
spec_ref: "specs/query/query-execution.spec.md@dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "test(query): add MCPQueryService unit tests for all Error Categorization scenarios"
pr_description: |
  ## What & Why

  The **Requirement: Error Categorization** in `specs/query/query-execution.spec.md`
  specifies four distinct error types that the system must produce:

  | Spec scenario | Error type |
  |---|---|
  | Query containing mutation keywords | `"forbidden"` |
  | Query that exceeds the timeout | `"timeout"` |
  | Query with syntax error or runtime failure | `"execution_error"` |
  | Unexpected failure during query execution | `"unknown_error"` |

  The application service layer (`MCPQueryService`) is the component responsible for
  converting repository exceptions into typed `QueryError` value objects. Currently:

  - `QueryGraphRepository` raises `QueryForbiddenError`, `QueryTimeoutError`,
    `QueryExecutionError`, or generic `Exception` for each scenario.
  - `MCPQueryService.execute_cypher_query()` catches each exception type and maps it
    to the corresponding `error_type` string.
  - The MCP presentation layer (`mcp.py`) reads the `error_type` from the `QueryError`
    and includes it in the JSON response.

  **The gap**: `MCPQueryService` has no dedicated unit test file. The service's
  error categorisation contract is only tested indirectly:

  - `test_query_repository.py` — tests the repository raises the right exceptions
  - `test_mcp_query_tool.py` — tests `_build_error_response()` (presentation layer
    helper) converts `QueryError` objects to response dicts

  Neither test file exercises `MCPQueryService` in isolation with a fake repository.
  If the `except` clauses in `execute_cypher_query()` were accidentally reordered or
  one was removed, existing tests would not catch it.

  ## What This PR Does

  ### 1. Create `tests/unit/query/test_mcp_query_service.py`

  TDD: write all tests before any implementation changes. Use a `FakeQueryRepository`
  that raises configurable exceptions.

  ```python
  class FakeQueryRepository(IQueryGraphRepository):
      """Fake repository that raises a pre-configured exception or returns rows."""

      def __init__(
          self,
          rows: list | None = None,
          raises: Exception | None = None,
      ) -> None:
          self._rows = rows or []
          self._raises = raises

      def execute_cypher(self, query: str, timeout_seconds: int = 30, max_rows: int = 1000):
          if self._raises is not None:
              raise self._raises
          return self._rows
  ```

  ### 2. Error Categorization tests (four spec scenarios)

  **Scenario: Forbidden query → error_type "forbidden"**

  ```python
  def test_forbidden_error_type_when_repo_raises_query_forbidden_error():
      repo = FakeQueryRepository(raises=QueryForbiddenError(
          "Forbidden keyword", query="CREATE (n)", correlation_id="corr-1"
      ))
      service = MCPQueryService(repository=repo)
      result = service.execute_cypher_query(query="CREATE (n)")
      assert isinstance(result, QueryError)
      assert result.error_type == "forbidden"
      assert result.correlation_id == "corr-1"
  ```

  **Scenario: Timeout error → error_type "timeout"**

  ```python
  def test_timeout_error_type_when_repo_raises_query_timeout_error():
      repo = FakeQueryRepository(raises=QueryTimeoutError(
          "Query timed out", query="MATCH (n) RETURN n", correlation_id="corr-2"
      ))
      service = MCPQueryService(repository=repo)
      result = service.execute_cypher_query(query="MATCH (n) RETURN n")
      assert isinstance(result, QueryError)
      assert result.error_type == "timeout"
      assert result.correlation_id == "corr-2"
  ```

  **Scenario: Execution error → error_type "execution_error"**

  ```python
  def test_execution_error_type_when_repo_raises_query_execution_error():
      repo = FakeQueryRepository(raises=QueryExecutionError(
          "Syntax error", query="MATCH (n RETURN n"
      ))
      service = MCPQueryService(repository=repo)
      result = service.execute_cypher_query(query="MATCH (n RETURN n")
      assert isinstance(result, QueryError)
      assert result.error_type == "execution_error"
      assert result.correlation_id is None
  ```

  **Scenario: Unexpected error → error_type "unknown_error"**

  ```python
  def test_unknown_error_type_when_repo_raises_unexpected_exception():
      repo = FakeQueryRepository(raises=RuntimeError("Unexpected DB failure"))
      service = MCPQueryService(repository=repo)
      result = service.execute_cypher_query(query="MATCH (n) RETURN n")
      assert isinstance(result, QueryError)
      assert result.error_type == "unknown_error"
      assert result.correlation_id is None
  ```

  ### 3. Successful query test (Requirement: Timeout Enforcement — happy path)

  The spec states "Query within timeout → results returned normally." This tests that
  the service returns a `CypherQueryResult` (not `QueryError`) when the repository
  succeeds:

  ```python
  def test_returns_cypher_query_result_on_success():
      from query.domain.value_objects import NodeDict
      node = NodeDict(id="1", label="Person", properties={"name": "Alice"})
      repo = FakeQueryRepository(rows=[{"node": node}])
      service = MCPQueryService(repository=repo)
      result = service.execute_cypher_query(query="MATCH (n) RETURN n")
      assert isinstance(result, CypherQueryResult)
      assert result.row_count == 1
      assert result.rows == [{"node": node}]
      assert result.truncated is False or result.truncated is True  # depends on limit
  ```

  ### 4. Probe observability tests

  Verify the domain probe is called correctly (Domain-Oriented Observability pattern):

  ```python
  def test_probe_cypher_query_received_called():
      """Probe records the incoming query."""
      probe = MagicMock(spec=QueryServiceProbe)
      repo = FakeQueryRepository(rows=[])
      service = MCPQueryService(repository=repo, probe=probe)
      service.execute_cypher_query(query="MATCH (n) RETURN n")
      probe.cypher_query_received.assert_called_once()

  def test_probe_cypher_query_rejected_called_on_forbidden():
      """Probe records rejection with correlation_id."""
      probe = MagicMock(spec=QueryServiceProbe)
      repo = FakeQueryRepository(raises=QueryForbiddenError(
          "Forbidden", query="CREATE", correlation_id="c-1"
      ))
      service = MCPQueryService(repository=repo, probe=probe)
      service.execute_cypher_query(query="CREATE")
      probe.cypher_query_rejected.assert_called_once()
      call_kwargs = probe.cypher_query_rejected.call_args.kwargs
      assert call_kwargs.get("correlation_id") == "c-1"

  def test_probe_cypher_query_failed_called_on_timeout():
      """Probe records failure with correlation_id on timeout."""
      probe = MagicMock(spec=QueryServiceProbe)
      repo = FakeQueryRepository(raises=QueryTimeoutError(
          "Timeout", query="MATCH (n) RETURN n", correlation_id="t-1"
      ))
      service = MCPQueryService(repository=repo, probe=probe)
      service.execute_cypher_query(query="MATCH (n) RETURN n")
      probe.cypher_query_failed.assert_called_once()
      call_kwargs = probe.cypher_query_failed.call_args.kwargs
      assert call_kwargs.get("correlation_id") == "t-1"
  ```

  ## Files Affected

  - `src/api/tests/unit/query/test_mcp_query_service.py` — **new test file** with
    all tests listed above
  - `src/api/query/application/services.py` — no changes expected; if any test fails,
    fix the service implementation (TDD: tests are authoritative)
  - `src/api/query/domain/value_objects.py` — no changes expected

  ## How to Verify

  1. `cd src/api && uv run pytest tests/unit/query/test_mcp_query_service.py -v`
     All new tests must pass (RED → GREEN cycle).
  2. `cd src/api && uv run pytest tests/unit/query/ -v` — no regressions.
  3. Trace each spec scenario to the test that covers it:
     - Forbidden query → `test_forbidden_error_type_when_repo_raises_query_forbidden_error`
     - Timeout → `test_timeout_error_type_when_repo_raises_query_timeout_error`
     - Execution error → `test_execution_error_type_when_repo_raises_query_execution_error`
     - Unexpected error → `test_unknown_error_type_when_repo_raises_unexpected_exception`

  ## Design Decisions

  - **`FakeQueryRepository` not `MockRepository`**: Per the project's testing philosophy,
    fakes are preferred over mocks for ports (repository interfaces). The fake implements
    `IQueryGraphRepository` and raises a configurable exception, making tests readable
    without `MagicMock.side_effect` boilerplate.
  - **Service layer isolation**: These tests exercise `MCPQueryService` in isolation,
    independent of the actual `QueryGraphRepository`, the AGE database, or the MCP
    presentation layer. This makes them fast and deterministic.
  - **Correlation_id propagation**: `QueryForbiddenError` and `QueryTimeoutError` carry
    a `correlation_id` attribute set by the repository. The service must propagate this
    into the returned `QueryError`. These tests verify the propagation, complementing
    the repository-level tests that verify generation and the presentation-level tests
    that verify inclusion in the JSON response.
  - **No mock for `DefaultQueryServiceProbe`**: Tests that don't verify probe behaviour
    use `MCPQueryService(repository=repo)` without a probe argument, relying on the
    `DefaultQueryServiceProbe` no-op. Tests verifying probe behaviour pass a `MagicMock`
    with `spec=QueryServiceProbe` so typos in probe method names are caught.

  ## Spec Requirement Coverage

  **Requirement: Error Categorization** from `specs/query/query-execution.spec.md`:

  | Scenario | Test |
  |---|---|
  | Forbidden query → `"forbidden"` | `test_forbidden_error_type_when_repo_raises_query_forbidden_error` |
  | Timeout → `"timeout"` | `test_timeout_error_type_when_repo_raises_query_timeout_error` |
  | Execution error → `"execution_error"` | `test_execution_error_type_when_repo_raises_query_execution_error` |
  | Unexpected failure → `"unknown_error"` | `test_unknown_error_type_when_repo_raises_unexpected_exception` |

  **Requirement: Timeout Enforcement — Scenario: Query within timeout** from
  `specs/query/query-execution.spec.md`:

  | Scenario | Test |
  |---|---|
  | Query within timeout → results returned normally | `test_returns_cypher_query_result_on_success` |

  ## Gap Analysis

  `MCPQueryService.execute_cypher_query()` has four `except` clauses corresponding
  to the four spec scenarios. Prior to this task, no unit test exercised the service
  layer directly. If a future refactor accidentally merged two clauses or changed an
  `error_type` string, no existing test would catch it. This task closes that gap with
  direct, isolated unit tests.

  Related tasks:
  - task-088: Adds `correlation_id` to MCP error response dict (presentation layer)
  - task-090: Per-tenant graph routing (infrastructure layer)
  - The repository-level exception raising is tested in `test_query_repository.py`

  ## TDD Cycle

  1. Create `src/api/tests/unit/query/test_mcp_query_service.py` with the tests above.
  2. Run `cd src/api && uv run pytest tests/unit/query/test_mcp_query_service.py -v`
  3. If all tests pass immediately (GREEN without code changes) — the implementation
     is correct; commit.
  4. If any test fails — fix `MCPQueryService` to satisfy the failing test; re-run.
  5. Commit atomically.
---
