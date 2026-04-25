"""Unit tests for Querying application services."""

from unittest.mock import MagicMock, create_autospec

import pytest

from query.application.observability import DefaultQueryServiceProbe, QueryServiceProbe
from query.application.services import MCPQueryService
from query.domain.value_objects import (
    CypherQueryResult,
    QueryError,
    QueryExecutionError,
    QueryForbiddenError,
    QueryTimeoutError,
)
from query.ports.repositories import IQueryGraphRepository


@pytest.fixture
def mock_repository():
    """Create mock repository."""
    return create_autospec(IQueryGraphRepository, instance=True)


@pytest.fixture
def mock_probe():
    """Create mock probe."""
    return create_autospec(QueryServiceProbe, instance=True)


@pytest.fixture
def service(mock_repository, mock_probe):
    """Create service with mock dependencies."""
    return MCPQueryService(
        repository=mock_repository,
        probe=mock_probe,
        default_timeout_seconds=30,
        default_max_rows=1000,
    )


class TestMCPQueryServiceInit:
    """Tests for service initialization."""

    def test_stores_repository(self, mock_repository):
        """Service should store repository reference."""
        service = MCPQueryService(repository=mock_repository)
        assert service._repository is mock_repository

    def test_uses_default_probe_when_not_provided(self, mock_repository):
        """Should create default probe when not provided."""
        service = MCPQueryService(repository=mock_repository)
        assert service._probe is not None

    def test_uses_custom_defaults(self, mock_repository):
        """Should use custom default values."""
        service = MCPQueryService(
            repository=mock_repository,
            default_timeout_seconds=60,
            default_max_rows=500,
        )
        assert service._default_timeout == 60
        assert service._default_max_rows == 500

    def test_stores_defaults(self, service):
        """Should store default timeout and max_rows."""
        assert service._default_timeout == 30
        assert service._default_max_rows == 1000


class TestExecuteCypherQuery:
    """Tests for execute_cypher_query method."""

    def test_delegates_to_repository(self, service, mock_repository):
        """Should delegate query execution to repository."""
        mock_repository.execute_cypher.return_value = [{"name": "Alice"}]

        service.execute_cypher_query("MATCH (n) RETURN n")

        mock_repository.execute_cypher.assert_called_once()
        call_args = mock_repository.execute_cypher.call_args
        assert call_args.kwargs["query"] == "MATCH (n) RETURN n"

    def test_returns_cypher_query_result_on_success(self, service, mock_repository):
        """Should return CypherQueryResult on successful query."""
        mock_repository.execute_cypher.return_value = [{"name": "Alice"}]

        result = service.execute_cypher_query("MATCH (n) RETURN n")

        assert isinstance(result, CypherQueryResult)
        assert result.rows == [{"name": "Alice"}]
        assert result.row_count == 1

    def test_returns_query_error_on_failure(self, service, mock_repository):
        """Should return QueryError on repository failure."""
        mock_repository.execute_cypher.side_effect = Exception("Connection failed")

        result = service.execute_cypher_query("MATCH (n) RETURN n")

        assert isinstance(result, QueryError)
        assert "Connection failed" in result.message

    def test_uses_default_timeout(self, service, mock_repository):
        """Should use default timeout when not specified."""
        mock_repository.execute_cypher.return_value = []

        service.execute_cypher_query("MATCH (n) RETURN n")

        call_args = mock_repository.execute_cypher.call_args
        assert call_args.kwargs["timeout_seconds"] == 30

    def test_uses_custom_timeout(self, service, mock_repository):
        """Should use custom timeout when specified."""
        mock_repository.execute_cypher.return_value = []

        service.execute_cypher_query("MATCH (n) RETURN n", timeout_seconds=10)

        call_args = mock_repository.execute_cypher.call_args
        assert call_args.kwargs["timeout_seconds"] == 10

    def test_uses_default_max_rows(self, service, mock_repository):
        """Should use default max_rows when not specified."""
        mock_repository.execute_cypher.return_value = []

        service.execute_cypher_query("MATCH (n) RETURN n")

        call_args = mock_repository.execute_cypher.call_args
        assert call_args.kwargs["max_rows"] == 1000

    def test_uses_custom_max_rows(self, service, mock_repository):
        """Should use custom max_rows when specified."""
        mock_repository.execute_cypher.return_value = []

        service.execute_cypher_query("MATCH (n) RETURN n", max_rows=500)

        call_args = mock_repository.execute_cypher.call_args
        assert call_args.kwargs["max_rows"] == 500

    def test_records_query_received_observation(
        self, service, mock_repository, mock_probe
    ):
        """Should record observation when query received."""
        mock_repository.execute_cypher.return_value = []

        service.execute_cypher_query("MATCH (n) RETURN n")

        mock_probe.cypher_query_received.assert_called_once()
        call_args = mock_probe.cypher_query_received.call_args
        assert call_args.kwargs["query"] == "MATCH (n) RETURN n"
        assert call_args.kwargs["query_length"] == len("MATCH (n) RETURN n")

    def test_records_query_executed_observation(
        self, service, mock_repository, mock_probe
    ):
        """Should record observation when query executes."""
        mock_repository.execute_cypher.return_value = [{"a": 1}]

        service.execute_cypher_query("MATCH (n) RETURN n")

        mock_probe.cypher_query_executed.assert_called_once()
        call_args = mock_probe.cypher_query_executed.call_args
        assert call_args.kwargs["row_count"] == 1

    def test_tracks_truncation_when_at_limit(self, service, mock_repository):
        """Should mark as truncated when row count equals limit."""
        # Return exactly max_rows results
        mock_repository.execute_cypher.return_value = [{"n": i} for i in range(1000)]

        result = service.execute_cypher_query("MATCH (n) RETURN n")

        assert result.truncated is True

    def test_not_truncated_when_below_limit(self, service, mock_repository):
        """Should not mark as truncated when below limit."""
        mock_repository.execute_cypher.return_value = [{"n": 1}]

        result = service.execute_cypher_query("MATCH (n) RETURN n")

        assert result.truncated is False

    def test_tracks_execution_time(self, service, mock_repository):
        """Should track execution time in milliseconds."""
        mock_repository.execute_cypher.return_value = []

        result = service.execute_cypher_query("MATCH (n) RETURN n")

        assert result.execution_time_ms is not None
        assert result.execution_time_ms >= 0

    def test_categorizes_forbidden_error(self, service, mock_repository, mock_probe):
        """Should categorize read-only violations as forbidden."""
        mock_repository.execute_cypher.side_effect = QueryForbiddenError(
            "Query must be read-only. Found forbidden keyword: CREATE"
        )

        result = service.execute_cypher_query("CREATE (n:Test)")

        assert isinstance(result, QueryError)
        assert result.error_type == "forbidden"
        mock_probe.cypher_query_rejected.assert_called_once()

    def test_categorizes_timeout_error(self, service, mock_repository, mock_probe):
        """Should categorize timeout errors appropriately."""
        mock_repository.execute_cypher.side_effect = QueryTimeoutError(
            "Query exceeded 5s timeout"
        )

        result = service.execute_cypher_query("MATCH (n) RETURN n")

        assert isinstance(result, QueryError)
        assert result.error_type == "timeout"
        mock_probe.cypher_query_failed.assert_called_once()

    def test_categorizes_execution_error(self, service, mock_repository, mock_probe):
        """Should categorize query execution errors appropriately."""
        mock_repository.execute_cypher.side_effect = QueryExecutionError("Syntax error")

        result = service.execute_cypher_query("MATCH (n RETURN n")

        assert isinstance(result, QueryError)
        assert result.error_type == "execution_error"
        mock_probe.cypher_query_failed.assert_called_once()

    def test_categorizes_unknown_error(self, service, mock_repository, mock_probe):
        """Should categorize unexpected errors as unknown_error."""
        mock_repository.execute_cypher.side_effect = ValueError("Unexpected error")

        result = service.execute_cypher_query("MATCH (n) RETURN n")

        assert isinstance(result, QueryError)
        assert result.error_type == "unknown_error"
        mock_probe.cypher_query_failed.assert_called_once()

    def test_includes_query_in_error(self, service, mock_repository):
        """Should include query in error for debugging."""
        mock_repository.execute_cypher.side_effect = Exception("Failed")

        result = service.execute_cypher_query("MATCH (n) RETURN n")

        assert isinstance(result, QueryError)
        assert result.query == "MATCH (n) RETURN n"

    def test_forbidden_error_includes_correlation_id_in_response(
        self, service, mock_repository
    ):
        """Forbidden QueryError MUST carry a correlation ID (spec: keyword blacklist scenario).

        The error response includes a correlation ID so consumers can look up
        the redacted log entry on the server side.
        """
        exc = QueryForbiddenError(
            "Query must be read-only. Found forbidden keyword: CREATE"
        )
        exc.correlation_id = "test-corr-id-abc123"
        mock_repository.execute_cypher.side_effect = exc

        result = service.execute_cypher_query("CREATE (n:Test)")

        assert isinstance(result, QueryError)
        assert result.correlation_id == "test-corr-id-abc123"

    def test_forbidden_error_correlation_id_included_in_probe_call(
        self, service, mock_repository, mock_probe
    ):
        """The probe should receive the correlation ID so it can be logged."""
        exc = QueryForbiddenError(
            "Query must be read-only. Found forbidden keyword: CREATE"
        )
        exc.correlation_id = "probe-corr-id-xyz"
        mock_repository.execute_cypher.side_effect = exc

        service.execute_cypher_query("CREATE (n:Test)")

        mock_probe.cypher_query_rejected.assert_called_once()
        call_kwargs = mock_probe.cypher_query_rejected.call_args.kwargs
        assert call_kwargs.get("correlation_id") == "probe-corr-id-xyz"

    def test_timeout_error_includes_correlation_id_in_response(
        self, service, mock_repository
    ):
        """Timeout QueryError MUST carry a correlation ID (spec: timeout scenario)."""
        exc = QueryTimeoutError("Query exceeded 5s timeout")
        exc.correlation_id = "timeout-corr-id-456"
        mock_repository.execute_cypher.side_effect = exc

        result = service.execute_cypher_query("MATCH (n) RETURN n")

        assert isinstance(result, QueryError)
        assert result.correlation_id == "timeout-corr-id-456"

    def test_timeout_error_correlation_id_included_in_probe_call(
        self, service, mock_repository, mock_probe
    ):
        """The probe should receive the correlation ID for timeout failures."""
        exc = QueryTimeoutError("Query exceeded 5s timeout")
        exc.correlation_id = "timeout-probe-corr-789"
        mock_repository.execute_cypher.side_effect = exc

        service.execute_cypher_query("MATCH (n) RETURN n")

        mock_probe.cypher_query_failed.assert_called_once()
        call_kwargs = mock_probe.cypher_query_failed.call_args.kwargs
        assert call_kwargs.get("correlation_id") == "timeout-probe-corr-789"


class TestDefaultQueryServiceProbe:
    """Tests for DefaultQueryServiceProbe log-redaction contract.

    Spec (Req 1B): When a forbidden query is rejected, a 'redacted reference'
    MUST be logged — not the raw query text. This class enforces that contract
    as an automated assertion rather than relying solely on code convention.
    """

    def test_cypher_query_rejected_does_not_log_raw_query(self):
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

    def test_cypher_query_rejected_logs_correlation_id(self):
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

    def test_cypher_query_rejected_logs_reason(self):
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
