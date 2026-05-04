"""Unit tests for MCPQueryService error categorization.

Spec: specs/query/query-execution.spec.md
Requirement: Error Categorization

The system SHALL categorize query errors into distinct types for consumer
handling. MCPQueryService.execute_cypher_query() is the application-layer
component responsible for mapping repository exceptions to typed QueryError
value objects.

These tests exercise MCPQueryService in isolation using a FakeQueryRepository
(not the real QueryGraphRepository or a MagicMock) per the project's
testing philosophy of "fakes over mocks" for port collaborators.

If the except clauses in execute_cypher_query() were accidentally reordered,
merged, or their error_type strings changed, these tests would catch it.
"""

from __future__ import annotations

import pytest

from query.application.services import MCPQueryService
from query.domain.value_objects import (
    CypherQueryResult,
    NodeDict,
    QueryError,
    QueryExecutionError,
    QueryForbiddenError,
    QueryResultRow,
    QueryTimeoutError,
)
from query.ports.repositories import IQueryGraphRepository


# ---------------------------------------------------------------------------
# Fakes — no MagicMock for domain/application collaborators
# ---------------------------------------------------------------------------


class FakeQueryRepository:
    """Fake IQueryGraphRepository that raises a configurable exception or returns rows.

    Using a fake rather than MagicMock per testing.spec.md: "mocking is NOT
    acceptable for repositories or probe protocols."
    """

    def __init__(
        self,
        rows: list[QueryResultRow] | None = None,
        raises: Exception | None = None,
    ) -> None:
        self._rows: list[QueryResultRow] = rows or []
        self._raises = raises

    def execute_cypher(
        self,
        query: str,
        timeout_seconds: int = 30,
        max_rows: int = 1000,
    ) -> list[QueryResultRow]:
        if self._raises is not None:
            raise self._raises
        return self._rows


# Verify the fake satisfies the runtime-checkable protocol.
assert isinstance(FakeQueryRepository(), IQueryGraphRepository)


class FakeQueryServiceProbe:
    """Fake QueryServiceProbe that records calls without side effects.

    Structured fakes are preferred over MagicMock for probe collaborators.
    """

    def __init__(self) -> None:
        self.received_calls: list[dict] = []
        self.executed_calls: list[dict] = []
        self.rejected_calls: list[dict] = []
        self.failed_calls: list[dict] = []

    def cypher_query_received(self, query: str, query_length: int) -> None:
        self.received_calls.append({"query": query, "query_length": query_length})

    def cypher_query_executed(
        self,
        query: str,
        row_count: int,
        execution_time_ms: float,
        truncated: bool,
    ) -> None:
        self.executed_calls.append(
            {
                "query": query,
                "row_count": row_count,
                "execution_time_ms": execution_time_ms,
                "truncated": truncated,
            }
        )

    def cypher_query_rejected(
        self,
        query: str,
        reason: str,
        correlation_id: str | None = None,
    ) -> None:
        self.rejected_calls.append(
            {"query": query, "reason": reason, "correlation_id": correlation_id}
        )

    def cypher_query_failed(
        self,
        query: str,
        error: str,
        correlation_id: str | None = None,
    ) -> None:
        self.failed_calls.append(
            {"query": query, "error": error, "correlation_id": correlation_id}
        )

    def with_context(self, context) -> FakeQueryServiceProbe:  # type: ignore[override]
        return self


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def probe() -> FakeQueryServiceProbe:
    """Fresh FakeQueryServiceProbe for each test."""
    return FakeQueryServiceProbe()


def make_service(
    rows: list[QueryResultRow] | None = None,
    raises: Exception | None = None,
    probe: FakeQueryServiceProbe | None = None,
) -> MCPQueryService:
    """Convenience factory: wire MCPQueryService with a fake repository."""
    repo = FakeQueryRepository(rows=rows, raises=raises)
    return MCPQueryService(
        repository=repo,
        probe=probe,
        default_timeout_seconds=30,
        default_max_rows=1000,
    )


# ---------------------------------------------------------------------------
# Requirement: Error Categorization — four spec scenarios
# ---------------------------------------------------------------------------


class TestErrorCategorization:
    """Error categorization scenarios from specs/query/query-execution.spec.md.

    Each test maps to one spec scenario in Requirement: Error Categorization.
    """

    # Scenario: Forbidden query
    def test_forbidden_error_type_when_repo_raises_query_forbidden_error(self):
        """GIVEN a query containing mutation keywords
        THEN the error type is "forbidden".

        Spec: Error Categorization — Forbidden query scenario.
        """
        exc = QueryForbiddenError(
            "Query must be read-only. Found forbidden keyword: CREATE",
            query="CREATE (n:Test)",
            correlation_id="corr-forbidden-1",
        )
        service = make_service(raises=exc)

        result = service.execute_cypher_query("CREATE (n:Test)")

        assert isinstance(result, QueryError)
        assert result.error_type == "forbidden"

    def test_forbidden_error_preserves_correlation_id(self):
        """Correlation ID from QueryForbiddenError MUST be propagated to QueryError.

        Spec: Keyword blacklist scenario — error response includes a correlation ID.
        """
        exc = QueryForbiddenError(
            "Forbidden keyword: CREATE",
            query="CREATE (n:Test)",
            correlation_id="corr-forbidden-preserved",
        )
        service = make_service(raises=exc)

        result = service.execute_cypher_query("CREATE (n:Test)")

        assert isinstance(result, QueryError)
        assert result.correlation_id == "corr-forbidden-preserved"

    def test_forbidden_error_message_is_propagated(self):
        """Error message should be present in QueryError."""
        exc = QueryForbiddenError(
            "Query must be read-only. Found forbidden keyword: DELETE",
        )
        service = make_service(raises=exc)

        result = service.execute_cypher_query("MATCH (n) DELETE n")

        assert isinstance(result, QueryError)
        assert "DELETE" in result.message
        assert "read-only" in result.message.lower()

    # Scenario: Timeout error
    def test_timeout_error_type_when_repo_raises_query_timeout_error(self):
        """GIVEN a query that exceeds the timeout
        THEN the error type is "timeout".

        Spec: Error Categorization — Timeout error scenario.
        """
        exc = QueryTimeoutError(
            "Query exceeded 30s timeout",
            query="MATCH (n) RETURN n",
            correlation_id="corr-timeout-1",
        )
        service = make_service(raises=exc)

        result = service.execute_cypher_query("MATCH (n) RETURN n")

        assert isinstance(result, QueryError)
        assert result.error_type == "timeout"

    def test_timeout_error_preserves_correlation_id(self):
        """Correlation ID from QueryTimeoutError MUST be propagated to QueryError.

        Spec: Query exceeds timeout — error returned with a correlation ID for debugging.
        """
        exc = QueryTimeoutError(
            "Query exceeded timeout",
            query="MATCH (n) RETURN n",
            correlation_id="corr-timeout-preserved",
        )
        service = make_service(raises=exc)

        result = service.execute_cypher_query("MATCH (n) RETURN n")

        assert isinstance(result, QueryError)
        assert result.correlation_id == "corr-timeout-preserved"

    def test_timeout_error_without_correlation_id(self):
        """Timeout errors without a correlation_id should still return error_type timeout."""
        exc = QueryTimeoutError("Query exceeded timeout")
        service = make_service(raises=exc)

        result = service.execute_cypher_query("MATCH (n) RETURN n")

        assert isinstance(result, QueryError)
        assert result.error_type == "timeout"

    # Scenario: Execution error
    def test_execution_error_type_when_repo_raises_query_execution_error(self):
        """GIVEN a query with a syntax error or runtime failure
        THEN the error type is "execution_error".

        Spec: Error Categorization — Execution error scenario.
        """
        exc = QueryExecutionError(
            "Syntax error in query",
            query="MATCH (n RETURN n",
        )
        service = make_service(raises=exc)

        result = service.execute_cypher_query("MATCH (n RETURN n")

        assert isinstance(result, QueryError)
        assert result.error_type == "execution_error"

    def test_execution_error_has_no_correlation_id_by_default(self):
        """QueryExecutionError does not carry a correlation_id (unlike forbidden/timeout).

        The correlation_id is used for redacted-log cross-reference and is
        only relevant for forbidden and timeout errors.
        """
        exc = QueryExecutionError("Syntax error", query="MATCH (n RETURN n")
        service = make_service(raises=exc)

        result = service.execute_cypher_query("MATCH (n RETURN n")

        assert isinstance(result, QueryError)
        assert result.error_type == "execution_error"
        assert result.correlation_id is None

    def test_execution_error_message_includes_original_error(self):
        """Execution error message should reference the original failure."""
        exc = QueryExecutionError("Tenant graph 'tenant_xyz' does not exist.")
        service = make_service(raises=exc)

        result = service.execute_cypher_query("MATCH (n) RETURN n")

        assert isinstance(result, QueryError)
        assert "does not exist" in result.message
        assert "tenant" in result.message.lower()

    # Scenario: Unexpected error
    def test_unknown_error_type_when_repo_raises_unexpected_exception(self):
        """GIVEN an unexpected failure during query execution
        THEN the error type is "unknown_error".

        Spec: Error Categorization — Unexpected error scenario.
        """
        exc = RuntimeError("Unexpected DB connection failure")
        service = make_service(raises=exc)

        result = service.execute_cypher_query("MATCH (n) RETURN n")

        assert isinstance(result, QueryError)
        assert result.error_type == "unknown_error"

    def test_unknown_error_for_value_error(self):
        """ValueError (unexpected) should be categorised as unknown_error."""
        service = make_service(raises=ValueError("Unexpected value error"))

        result = service.execute_cypher_query("MATCH (n) RETURN n")

        assert isinstance(result, QueryError)
        assert result.error_type == "unknown_error"

    def test_unknown_error_for_type_error(self):
        """TypeError (unexpected) should be categorised as unknown_error."""
        service = make_service(raises=TypeError("Unexpected type error"))

        result = service.execute_cypher_query("MATCH (n) RETURN n")

        assert isinstance(result, QueryError)
        assert result.error_type == "unknown_error"

    def test_unknown_error_has_no_correlation_id(self):
        """Unexpected errors carry no correlation_id."""
        service = make_service(raises=RuntimeError("Something broke"))

        result = service.execute_cypher_query("MATCH (n) RETURN n")

        assert isinstance(result, QueryError)
        assert result.correlation_id is None

    def test_error_categorization_ordering_matters(self):
        """QueryForbiddenError and QueryTimeoutError are QueryExecutionError subclasses.

        The service MUST catch them in the correct order: subclasses before the
        base class. If QueryExecutionError is caught first, forbidden/timeout errors
        would be swallowed and returned with error_type="execution_error".

        This test verifies ordering by checking that a QueryForbiddenError (which IS-A
        QueryExecutionError) produces error_type="forbidden" not "execution_error".
        """
        exc = QueryForbiddenError("Mutation keyword detected")
        service = make_service(raises=exc)

        result = service.execute_cypher_query("CREATE (n)")

        assert isinstance(result, QueryError)
        assert result.error_type == "forbidden", (
            "QueryForbiddenError must be caught before the base QueryExecutionError. "
            f"Got error_type={result.error_type!r} instead of 'forbidden'. "
            "Check except clause ordering in execute_cypher_query()."
        )

    def test_timeout_categorization_before_base_exception(self):
        """QueryTimeoutError IS-A QueryExecutionError — must be caught separately."""
        exc = QueryTimeoutError("DB cancelled statement due to timeout")
        service = make_service(raises=exc)

        result = service.execute_cypher_query("MATCH (n) RETURN n")

        assert isinstance(result, QueryError)
        assert result.error_type == "timeout", (
            "QueryTimeoutError must be caught before the base QueryExecutionError. "
            f"Got error_type={result.error_type!r} instead of 'timeout'."
        )


# ---------------------------------------------------------------------------
# Requirement: Timeout Enforcement — happy path (Query within timeout)
# ---------------------------------------------------------------------------


class TestSuccessfulExecution:
    """Tests for successful query execution (Timeout Enforcement — happy path)."""

    def test_returns_cypher_query_result_on_success(self):
        """GIVEN a query that completes within the timeout
        WHEN the query executes
        THEN results are returned normally (CypherQueryResult, not QueryError).

        Spec: Timeout Enforcement — Query within timeout scenario.
        """
        node: NodeDict = {  # type: ignore[assignment]
            "id": "1",
            "label": "Person",
            "properties": {"name": "Alice"},
        }
        rows: list[QueryResultRow] = [{"node": node}]
        service = make_service(rows=rows)

        result = service.execute_cypher_query("MATCH (n) RETURN n")

        assert isinstance(result, CypherQueryResult)
        assert result.row_count == 1
        assert result.rows == rows

    def test_success_result_is_not_truncated_for_small_result_set(self):
        """Results below the limit should not be marked as truncated."""
        rows: list[QueryResultRow] = [{"value": i} for i in range(5)]
        service = make_service(rows=rows)

        result = service.execute_cypher_query("MATCH (n) RETURN n")

        assert isinstance(result, CypherQueryResult)
        assert result.truncated is False

    def test_success_result_tracks_execution_time(self):
        """Successful result should include execution_time_ms."""
        service = make_service(rows=[])

        result = service.execute_cypher_query("MATCH (n) RETURN n")

        assert isinstance(result, CypherQueryResult)
        assert result.execution_time_ms is not None
        assert result.execution_time_ms >= 0

    def test_empty_result_set_is_valid(self):
        """Empty result set is a normal successful execution."""
        service = make_service(rows=[])

        result = service.execute_cypher_query("MATCH (n:NonExistent) RETURN n")

        assert isinstance(result, CypherQueryResult)
        assert result.row_count == 0
        assert result.rows == []


# ---------------------------------------------------------------------------
# Observability: probe is called correctly
# ---------------------------------------------------------------------------


class TestProbeObservability:
    """Tests verifying Domain-Oriented Observability probe behaviour.

    Each error path should call the appropriate probe method with correct args.
    """

    def test_probe_cypher_query_received_called_on_every_invocation(
        self, probe: FakeQueryServiceProbe
    ) -> None:
        """Probe must record every incoming query."""
        service = make_service(rows=[], probe=probe)

        service.execute_cypher_query("MATCH (n) RETURN n")

        assert len(probe.received_calls) == 1
        assert probe.received_calls[0]["query"] == "MATCH (n) RETURN n"

    def test_probe_cypher_query_executed_called_on_success(
        self, probe: FakeQueryServiceProbe
    ) -> None:
        """Probe records execution on successful path."""
        service = make_service(rows=[{"value": 1}], probe=probe)

        service.execute_cypher_query("MATCH (n) RETURN n")

        assert len(probe.executed_calls) == 1
        assert probe.executed_calls[0]["row_count"] == 1

    def test_probe_cypher_query_rejected_called_on_forbidden(
        self, probe: FakeQueryServiceProbe
    ) -> None:
        """Probe records rejection for forbidden queries.

        Spec: Keyword blacklist — a redacted reference is logged.
        """
        exc = QueryForbiddenError(
            "Forbidden keyword: CREATE",
            query="CREATE (n)",
            correlation_id="c-1",
        )
        service = make_service(raises=exc, probe=probe)

        service.execute_cypher_query("CREATE (n)")

        assert len(probe.rejected_calls) == 1
        assert probe.rejected_calls[0]["correlation_id"] == "c-1"

    def test_probe_cypher_query_rejected_not_called_on_other_errors(
        self, probe: FakeQueryServiceProbe
    ) -> None:
        """cypher_query_rejected must NOT be called for non-forbidden errors."""
        service = make_service(raises=QueryTimeoutError("Timeout"), probe=probe)

        service.execute_cypher_query("MATCH (n) RETURN n")

        assert len(probe.rejected_calls) == 0

    def test_probe_cypher_query_failed_called_on_timeout(
        self, probe: FakeQueryServiceProbe
    ) -> None:
        """Probe records failure with correlation_id on timeout."""
        exc = QueryTimeoutError(
            "Query timed out",
            query="MATCH (n) RETURN n",
            correlation_id="t-1",
        )
        service = make_service(raises=exc, probe=probe)

        service.execute_cypher_query("MATCH (n) RETURN n")

        assert len(probe.failed_calls) == 1
        assert probe.failed_calls[0]["correlation_id"] == "t-1"

    def test_probe_cypher_query_failed_called_on_execution_error(
        self, probe: FakeQueryServiceProbe
    ) -> None:
        """Probe records failure for execution errors."""
        exc = QueryExecutionError("Syntax error")
        service = make_service(raises=exc, probe=probe)

        service.execute_cypher_query("MATCH (n RETURN n")

        assert len(probe.failed_calls) == 1

    def test_probe_cypher_query_failed_called_on_unknown_error(
        self, probe: FakeQueryServiceProbe
    ) -> None:
        """Probe records failure for unexpected errors."""
        service = make_service(raises=RuntimeError("Unexpected"), probe=probe)

        service.execute_cypher_query("MATCH (n) RETURN n")

        assert len(probe.failed_calls) == 1

    def test_probe_not_called_with_raw_query_on_rejection(
        self, probe: FakeQueryServiceProbe
    ) -> None:
        """The probe's rejected_calls record query, but DefaultQueryServiceProbe
        MUST NOT forward the raw query to the logger (separate contract tested
        in TestDefaultQueryServiceProbe in test_application_services.py).

        This test verifies the probe receives the query argument (so the impl
        can use it for correlation without logging it).
        """
        raw_query = "CREATE (n:Secret {password: 's3cr3t'})"
        exc = QueryForbiddenError("Forbidden keyword: CREATE")
        service = make_service(raises=exc, probe=probe)

        service.execute_cypher_query(raw_query)

        # Probe is called with the query for correlation purposes
        assert len(probe.rejected_calls) == 1
        assert probe.rejected_calls[0]["query"] == raw_query
