"""Unit tests for Querying application services.

Uses fakes (not mocks) for repository and probe collaborators, per
testing.spec.md: "mocking is NOT acceptable for repositories or probe protocols".
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from query.application.observability import DefaultQueryServiceProbe
from query.application.services import MCPQueryService
from query.domain.value_objects import (
    CypherQueryResult,
    QueryError,
    QueryExecutionError,
    QueryForbiddenError,
    QueryResultRow,
    QueryTimeoutError,
)
from query.ports.repositories import IQueryGraphRepository


# ---------------------------------------------------------------------------
# Fakes — no MagicMock/create_autospec for domain/application collaborators
# ---------------------------------------------------------------------------


class FakeQueryGraphRepository:
    """Fake IQueryGraphRepository that records execute_cypher calls.

    Supports configuring a fixed return value or a side-effect exception
    before each test, providing the same control as MagicMock without
    violating the testing NFR that prohibits mocking repositories.
    """

    def __init__(
        self,
        return_value: list[QueryResultRow] | None = None,
        side_effect: Exception | None = None,
    ) -> None:
        self.return_value: list[QueryResultRow] = (
            return_value if return_value is not None else []
        )
        self.side_effect: Exception | None = side_effect
        # Records of every call: list of {"query": ..., "timeout_seconds": ..., "max_rows": ...}
        self.execute_cypher_calls: list[dict] = []

    def execute_cypher(
        self,
        query: str,
        timeout_seconds: int = 30,
        max_rows: int = 1000,
    ) -> list[QueryResultRow]:
        self.execute_cypher_calls.append(
            {"query": query, "timeout_seconds": timeout_seconds, "max_rows": max_rows}
        )
        if self.side_effect is not None:
            raise self.side_effect
        return self.return_value

    # Convenience helpers for test assertions
    @property
    def call_count(self) -> int:
        return len(self.execute_cypher_calls)

    @property
    def last_call(self) -> dict:
        if not self.execute_cypher_calls:
            raise AssertionError("execute_cypher was never called")
        return self.execute_cypher_calls[-1]

    def assert_called_once(self) -> None:
        assert self.call_count == 1, (
            f"Expected execute_cypher to be called exactly once, "
            f"but it was called {self.call_count} time(s)."
        )


class FakeQueryServiceProbe:
    """Fake QueryServiceProbe that records all domain events.

    Each probe method appends its keyword arguments to a dedicated call list,
    allowing tests to assert on both call count and specific argument values
    without relying on MagicMock.
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


# Verify the repository fake satisfies the runtime-checkable protocol.
# QueryServiceProbe is not @runtime_checkable so we rely on structural
# compatibility (duck typing) verified implicitly by the service tests.
assert isinstance(FakeQueryGraphRepository(), IQueryGraphRepository)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_repository() -> FakeQueryGraphRepository:
    """Fresh FakeQueryGraphRepository for each test."""
    return FakeQueryGraphRepository()


@pytest.fixture
def fake_probe() -> FakeQueryServiceProbe:
    """Fresh FakeQueryServiceProbe for each test."""
    return FakeQueryServiceProbe()


@pytest.fixture
def service(
    fake_repository: FakeQueryGraphRepository, fake_probe: FakeQueryServiceProbe
) -> MCPQueryService:
    """MCPQueryService wired with fake collaborators."""
    return MCPQueryService(
        repository=fake_repository,
        probe=fake_probe,
        default_timeout_seconds=30,
        default_max_rows=1000,
    )


# ---------------------------------------------------------------------------
# TestMCPQueryServiceInit
# ---------------------------------------------------------------------------


class TestMCPQueryServiceInit:
    """Tests for service initialization."""

    def test_stores_repository(self, fake_repository: FakeQueryGraphRepository) -> None:
        """Service should store repository reference."""
        service = MCPQueryService(repository=fake_repository)
        assert service._repository is fake_repository

    def test_uses_default_probe_when_not_provided(
        self, fake_repository: FakeQueryGraphRepository
    ) -> None:
        """Should create default probe when not provided."""
        service = MCPQueryService(repository=fake_repository)
        assert service._probe is not None

    def test_uses_custom_defaults(
        self, fake_repository: FakeQueryGraphRepository
    ) -> None:
        """Should use custom default values."""
        service = MCPQueryService(
            repository=fake_repository,
            default_timeout_seconds=60,
            default_max_rows=500,
        )
        assert service._default_timeout == 60
        assert service._default_max_rows == 500

    def test_stores_defaults(self, service: MCPQueryService) -> None:
        """Should store default timeout and max_rows."""
        assert service._default_timeout == 30
        assert service._default_max_rows == 1000


# ---------------------------------------------------------------------------
# TestExecuteCypherQuery
# ---------------------------------------------------------------------------


class TestExecuteCypherQuery:
    """Tests for execute_cypher_query method."""

    def test_delegates_to_repository(
        self,
        service: MCPQueryService,
        fake_repository: FakeQueryGraphRepository,
    ) -> None:
        """Should delegate query execution to repository."""
        fake_repository.return_value = [{"name": "Alice"}]

        service.execute_cypher_query("MATCH (n) RETURN n")

        fake_repository.assert_called_once()
        assert fake_repository.last_call["query"] == "MATCH (n) RETURN n"

    def test_returns_cypher_query_result_on_success(
        self,
        service: MCPQueryService,
        fake_repository: FakeQueryGraphRepository,
    ) -> None:
        """Should return CypherQueryResult on successful query."""
        fake_repository.return_value = [{"name": "Alice"}]

        result = service.execute_cypher_query("MATCH (n) RETURN n")

        assert isinstance(result, CypherQueryResult)
        assert result.rows == [{"name": "Alice"}]
        assert result.row_count == 1

    def test_returns_query_error_on_failure(
        self,
        service: MCPQueryService,
        fake_repository: FakeQueryGraphRepository,
    ) -> None:
        """Should return QueryError on repository failure."""
        fake_repository.side_effect = Exception("Connection failed")

        result = service.execute_cypher_query("MATCH (n) RETURN n")

        assert isinstance(result, QueryError)
        assert "Connection failed" in result.message

    def test_uses_default_timeout(
        self,
        service: MCPQueryService,
        fake_repository: FakeQueryGraphRepository,
    ) -> None:
        """Should use default timeout when not specified."""
        fake_repository.return_value = []

        service.execute_cypher_query("MATCH (n) RETURN n")

        assert fake_repository.last_call["timeout_seconds"] == 30

    def test_uses_custom_timeout(
        self,
        service: MCPQueryService,
        fake_repository: FakeQueryGraphRepository,
    ) -> None:
        """Should use custom timeout when specified."""
        fake_repository.return_value = []

        service.execute_cypher_query("MATCH (n) RETURN n", timeout_seconds=10)

        assert fake_repository.last_call["timeout_seconds"] == 10

    def test_uses_default_max_rows(
        self,
        service: MCPQueryService,
        fake_repository: FakeQueryGraphRepository,
    ) -> None:
        """Should use default max_rows when not specified."""
        fake_repository.return_value = []

        service.execute_cypher_query("MATCH (n) RETURN n")

        assert fake_repository.last_call["max_rows"] == 1000

    def test_uses_custom_max_rows(
        self,
        service: MCPQueryService,
        fake_repository: FakeQueryGraphRepository,
    ) -> None:
        """Should use custom max_rows when specified."""
        fake_repository.return_value = []

        service.execute_cypher_query("MATCH (n) RETURN n", max_rows=500)

        assert fake_repository.last_call["max_rows"] == 500

    def test_records_query_received_observation(
        self,
        service: MCPQueryService,
        fake_repository: FakeQueryGraphRepository,
        fake_probe: FakeQueryServiceProbe,
    ) -> None:
        """Should record observation when query received."""
        fake_repository.return_value = []

        service.execute_cypher_query("MATCH (n) RETURN n")

        assert len(fake_probe.received_calls) == 1
        received = fake_probe.received_calls[0]
        assert received["query"] == "MATCH (n) RETURN n"
        assert received["query_length"] == len("MATCH (n) RETURN n")

    def test_records_query_executed_observation(
        self,
        service: MCPQueryService,
        fake_repository: FakeQueryGraphRepository,
        fake_probe: FakeQueryServiceProbe,
    ) -> None:
        """Should record observation when query executes."""
        fake_repository.return_value = [{"a": 1}]

        service.execute_cypher_query("MATCH (n) RETURN n")

        assert len(fake_probe.executed_calls) == 1
        assert fake_probe.executed_calls[0]["row_count"] == 1

    def test_tracks_truncation_when_at_limit(
        self,
        service: MCPQueryService,
        fake_repository: FakeQueryGraphRepository,
    ) -> None:
        """Should mark as truncated when row count equals limit."""
        fake_repository.return_value = [{"n": i} for i in range(1000)]

        result = service.execute_cypher_query("MATCH (n) RETURN n")

        assert isinstance(result, CypherQueryResult)
        assert result.truncated is True

    def test_not_truncated_when_below_limit(
        self,
        service: MCPQueryService,
        fake_repository: FakeQueryGraphRepository,
    ) -> None:
        """Should not mark as truncated when below limit."""
        fake_repository.return_value = [{"n": 1}]

        result = service.execute_cypher_query("MATCH (n) RETURN n")

        assert isinstance(result, CypherQueryResult)
        assert result.truncated is False

    def test_tracks_execution_time(
        self,
        service: MCPQueryService,
        fake_repository: FakeQueryGraphRepository,
    ) -> None:
        """Should track execution time in milliseconds."""
        fake_repository.return_value = []

        result = service.execute_cypher_query("MATCH (n) RETURN n")

        assert isinstance(result, CypherQueryResult)
        assert result.execution_time_ms is not None
        assert result.execution_time_ms >= 0

    def test_categorizes_forbidden_error(
        self,
        service: MCPQueryService,
        fake_repository: FakeQueryGraphRepository,
        fake_probe: FakeQueryServiceProbe,
    ) -> None:
        """Should categorize read-only violations as forbidden."""
        fake_repository.side_effect = QueryForbiddenError(
            "Query must be read-only. Found forbidden keyword: CREATE"
        )

        result = service.execute_cypher_query("CREATE (n:Test)")

        assert isinstance(result, QueryError)
        assert result.error_type == "forbidden"
        assert len(fake_probe.rejected_calls) == 1

    def test_categorizes_timeout_error(
        self,
        service: MCPQueryService,
        fake_repository: FakeQueryGraphRepository,
        fake_probe: FakeQueryServiceProbe,
    ) -> None:
        """Should categorize timeout errors appropriately."""
        fake_repository.side_effect = QueryTimeoutError("Query exceeded 5s timeout")

        result = service.execute_cypher_query("MATCH (n) RETURN n")

        assert isinstance(result, QueryError)
        assert result.error_type == "timeout"
        assert len(fake_probe.failed_calls) == 1

    def test_categorizes_execution_error(
        self,
        service: MCPQueryService,
        fake_repository: FakeQueryGraphRepository,
        fake_probe: FakeQueryServiceProbe,
    ) -> None:
        """Should categorize query execution errors appropriately."""
        fake_repository.side_effect = QueryExecutionError("Syntax error")

        result = service.execute_cypher_query("MATCH (n RETURN n")

        assert isinstance(result, QueryError)
        assert result.error_type == "execution_error"
        assert len(fake_probe.failed_calls) == 1

    def test_categorizes_unknown_error(
        self,
        service: MCPQueryService,
        fake_repository: FakeQueryGraphRepository,
        fake_probe: FakeQueryServiceProbe,
    ) -> None:
        """Should categorize unexpected errors as unknown_error."""
        fake_repository.side_effect = ValueError("Unexpected error")

        result = service.execute_cypher_query("MATCH (n) RETURN n")

        assert isinstance(result, QueryError)
        assert result.error_type == "unknown_error"
        assert len(fake_probe.failed_calls) == 1

    def test_includes_query_in_error(
        self,
        service: MCPQueryService,
        fake_repository: FakeQueryGraphRepository,
    ) -> None:
        """Should include query in error for debugging."""
        fake_repository.side_effect = Exception("Failed")

        result = service.execute_cypher_query("MATCH (n) RETURN n")

        assert isinstance(result, QueryError)
        assert result.query == "MATCH (n) RETURN n"

    def test_forbidden_error_includes_correlation_id_in_response(
        self,
        service: MCPQueryService,
        fake_repository: FakeQueryGraphRepository,
    ) -> None:
        """Forbidden QueryError MUST carry a correlation ID (spec: keyword blacklist scenario).

        The error response includes a correlation ID so consumers can look up
        the redacted log entry on the server side.
        """
        exc = QueryForbiddenError(
            "Query must be read-only. Found forbidden keyword: CREATE"
        )
        exc.correlation_id = "test-corr-id-abc123"
        fake_repository.side_effect = exc

        result = service.execute_cypher_query("CREATE (n:Test)")

        assert isinstance(result, QueryError)
        assert result.correlation_id == "test-corr-id-abc123"

    def test_forbidden_error_correlation_id_included_in_probe_call(
        self,
        service: MCPQueryService,
        fake_repository: FakeQueryGraphRepository,
        fake_probe: FakeQueryServiceProbe,
    ) -> None:
        """The probe should receive the correlation ID so it can be logged."""
        exc = QueryForbiddenError(
            "Query must be read-only. Found forbidden keyword: CREATE"
        )
        exc.correlation_id = "probe-corr-id-xyz"
        fake_repository.side_effect = exc

        service.execute_cypher_query("CREATE (n:Test)")

        assert len(fake_probe.rejected_calls) == 1
        assert fake_probe.rejected_calls[0]["correlation_id"] == "probe-corr-id-xyz"

    def test_timeout_error_includes_correlation_id_in_response(
        self,
        service: MCPQueryService,
        fake_repository: FakeQueryGraphRepository,
    ) -> None:
        """Timeout QueryError MUST carry a correlation ID (spec: timeout scenario)."""
        exc = QueryTimeoutError("Query exceeded 5s timeout")
        exc.correlation_id = "timeout-corr-id-456"
        fake_repository.side_effect = exc

        result = service.execute_cypher_query("MATCH (n) RETURN n")

        assert isinstance(result, QueryError)
        assert result.correlation_id == "timeout-corr-id-456"

    def test_timeout_error_correlation_id_included_in_probe_call(
        self,
        service: MCPQueryService,
        fake_repository: FakeQueryGraphRepository,
        fake_probe: FakeQueryServiceProbe,
    ) -> None:
        """The probe should receive the correlation ID for timeout failures."""
        exc = QueryTimeoutError("Query exceeded 5s timeout")
        exc.correlation_id = "timeout-probe-corr-789"
        fake_repository.side_effect = exc

        service.execute_cypher_query("MATCH (n) RETURN n")

        assert len(fake_probe.failed_calls) == 1
        assert fake_probe.failed_calls[0]["correlation_id"] == "timeout-probe-corr-789"


# ---------------------------------------------------------------------------
# TestDefaultQueryServiceProbe
# ---------------------------------------------------------------------------


class TestDefaultQueryServiceProbe:
    """Tests for DefaultQueryServiceProbe log-redaction contract.

    Spec (Req 1B): When a forbidden query is rejected, a 'redacted reference'
    MUST be logged — not the raw query text. This class enforces that contract
    as an automated assertion rather than relying solely on code convention.

    The structlog logger itself is mocked here because it is infrastructure
    (analogous to an HTTP client); we are testing the probe's behaviour
    toward its logger, not the logger itself.
    """

    def test_cypher_query_rejected_does_not_log_raw_query(self) -> None:
        """Raw query text MUST NOT appear in any log argument on rejection.

        The probe receives the raw query so callers don't need to omit it, but
        the DefaultQueryServiceProbe implementation is required to never forward
        that text to the underlying logger. Only the correlation_id and reason
        are emitted, giving operators a redacted audit trail they can link back
        to the client-facing error response via the correlation ID.
        """
        mock_logger = MagicMock()
        probe = DefaultQueryServiceProbe(logger=mock_logger)

        raw_query = "CREATE (n:SensitiveNode {secret: 'password123'})"
        correlation_id = "test-corr-id-redact-check"

        probe.cypher_query_rejected(
            query=raw_query,
            reason="forbidden keyword: CREATE",
            correlation_id=correlation_id,
        )

        # The logger must have been called — the event itself is always emitted.
        mock_logger.warning.assert_called_once()

        # Collect all arguments forwarded to the underlying logger and verify
        # the raw query string is absent from every one of them.
        call_args = mock_logger.warning.call_args

        for arg in call_args.args:
            assert raw_query not in str(arg), (
                f"Raw query must not appear in log positional args, "
                f"but found it in: {arg!r}"
            )

        for key, val in call_args.kwargs.items():
            assert raw_query not in str(val), (
                f"Raw query must not appear in log kwarg {key!r}, "
                f"but found it in: {val!r}"
            )

    def test_cypher_query_rejected_logs_correlation_id(self) -> None:
        """Correlation ID MUST be present in the log call for operator lookup."""
        mock_logger = MagicMock()
        probe = DefaultQueryServiceProbe(logger=mock_logger)

        probe.cypher_query_rejected(
            query="CREATE (n:Test)",
            reason="forbidden keyword: CREATE",
            correlation_id="corr-id-abc-123",
        )

        mock_logger.warning.assert_called_once()
        call_kwargs = mock_logger.warning.call_args.kwargs
        assert call_kwargs.get("correlation_id") == "corr-id-abc-123"

    def test_cypher_query_rejected_logs_reason(self) -> None:
        """Rejection reason MUST be present in the log call."""
        mock_logger = MagicMock()
        probe = DefaultQueryServiceProbe(logger=mock_logger)

        probe.cypher_query_rejected(
            query="DELETE (n)",
            reason="forbidden keyword: DELETE",
            correlation_id="corr-id-xyz",
        )

        mock_logger.warning.assert_called_once()
        call_kwargs = mock_logger.warning.call_args.kwargs
        assert call_kwargs.get("reason") == "forbidden keyword: DELETE"
