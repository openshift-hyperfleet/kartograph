"""Unit tests for the query_graph MCP tool's error response format.

Tests the `_build_error_response` helper function which constructs the error
response dict returned by the `query_graph` tool.

The key contract under test:
  - Forbidden errors include correlation_id (spec: keyword blacklist scenario).
  - Timeout errors include correlation_id (spec: query exceeds timeout scenario).
  - Execution errors omit correlation_id key (avoids misleading null).
  - Unknown errors omit correlation_id key.
  - Successful responses don't have correlation_id.

Note: `query_graph` is wrapped by `@mcp.tool` and cannot be called directly
in unit tests. We test the extracted helper `_build_error_response` to verify
the error-dict construction contract in isolation.

Spec references:
  specs/query/query-execution.spec.md
  - Req: Read-Only Enforcement / Scenario: Keyword blacklist (secondary)
    "AND the error response includes a correlation ID for log lookup"
  - Req: Timeout Enforcement / Scenario: Query exceeds timeout
    "THEN a timeout error is returned with a correlation ID for debugging"
"""

from __future__ import annotations

from query.domain.value_objects import QueryError
from query.presentation.mcp import _build_error_response


class TestBuildErrorResponseForbiddenErrors:
    """Forbidden errors MUST include correlation_id in the response dict.

    Spec: Keyword blacklist (secondary) — the error response includes a
    correlation ID for log lookup.
    """

    def test_forbidden_error_includes_correlation_id(self):
        """Forbidden QueryError response MUST contain correlation_id."""
        error = QueryError(
            error_type="forbidden",
            message="Query must be read-only. Found forbidden keyword: CREATE",
            query="CREATE (n:Test)",
            correlation_id="corr-id-forbidden-001",
        )

        result = _build_error_response(error)

        assert result["success"] is False
        assert result["error_type"] == "forbidden"
        assert "correlation_id" in result, (
            "correlation_id MUST be present in forbidden error response"
        )
        assert result["correlation_id"] == "corr-id-forbidden-001"

    def test_forbidden_error_preserves_error_type_and_message(self):
        """Forbidden error response still carries error_type and message."""
        error = QueryError(
            error_type="forbidden",
            message="Forbidden keyword detected",
            correlation_id="corr-id-forbidden-002",
        )

        result = _build_error_response(error)

        assert result["error_type"] == "forbidden"
        assert result["message"] == "Forbidden keyword detected"
        assert result["success"] is False

    def test_forbidden_error_correlation_id_is_exact_value(self):
        """The correlation_id in the response MUST be the exact ID from QueryError."""
        expected_id = "unique-forbidden-correlation-id-xyz"
        error = QueryError(
            error_type="forbidden",
            message="Forbidden",
            correlation_id=expected_id,
        )

        result = _build_error_response(error)

        assert result["correlation_id"] == expected_id


class TestBuildErrorResponseTimeoutErrors:
    """Timeout errors MUST include correlation_id in the response dict.

    Spec: Query exceeds timeout — a timeout error is returned with a
    correlation ID for debugging.
    """

    def test_timeout_error_includes_correlation_id(self):
        """Timeout QueryError response MUST contain correlation_id."""
        error = QueryError(
            error_type="timeout",
            message="Query exceeded 30s timeout",
            correlation_id="corr-id-timeout-001",
        )

        result = _build_error_response(error)

        assert result["success"] is False
        assert result["error_type"] == "timeout"
        assert "correlation_id" in result, (
            "correlation_id MUST be present in timeout error response"
        )
        assert result["correlation_id"] == "corr-id-timeout-001"

    def test_timeout_error_preserves_error_type_and_message(self):
        """Timeout error response still carries error_type and message."""
        error = QueryError(
            error_type="timeout",
            message="Query timed out",
            correlation_id="corr-id-timeout-002",
        )

        result = _build_error_response(error)

        assert result["error_type"] == "timeout"
        assert result["message"] == "Query timed out"
        assert result["success"] is False

    def test_timeout_error_correlation_id_is_exact_value(self):
        """The correlation_id in the response MUST be the exact ID from QueryError."""
        expected_id = "unique-timeout-correlation-id-abc"
        error = QueryError(
            error_type="timeout",
            message="Timed out",
            correlation_id=expected_id,
        )

        result = _build_error_response(error)

        assert result["correlation_id"] == expected_id


class TestBuildErrorResponseExecutionErrors:
    """Execution errors MUST NOT include correlation_id key in response.

    Execution errors (syntax errors, runtime failures) don't generate
    correlation IDs. Including a null key would be misleading.
    """

    def test_execution_error_omits_correlation_id_key(self):
        """Execution error response MUST NOT have correlation_id key when None."""
        error = QueryError(
            error_type="execution_error",
            message="Syntax error in query",
            correlation_id=None,
        )

        result = _build_error_response(error)

        assert result["success"] is False
        assert result["error_type"] == "execution_error"
        assert "correlation_id" not in result, (
            "correlation_id key MUST NOT be present in execution_error response "
            "(avoids misleading null)"
        )

    def test_execution_error_preserves_error_type_and_message(self):
        """Execution error response still carries error_type and message."""
        error = QueryError(
            error_type="execution_error",
            message="Query failed: invalid syntax",
            correlation_id=None,
        )

        result = _build_error_response(error)

        assert result["error_type"] == "execution_error"
        assert result["message"] == "Query failed: invalid syntax"


class TestBuildErrorResponseUnknownErrors:
    """Unknown errors MUST NOT include correlation_id key.

    Like execution errors, unexpected failures don't produce correlation IDs.
    No null key should appear in the response.
    """

    def test_unknown_error_omits_correlation_id_key(self):
        """Unknown error response MUST NOT have correlation_id key when None."""
        error = QueryError(
            error_type="unknown_error",
            message="Unexpected failure",
            correlation_id=None,
        )

        result = _build_error_response(error)

        assert result["success"] is False
        assert result["error_type"] == "unknown_error"
        assert "correlation_id" not in result, (
            "correlation_id key MUST NOT be present in unknown_error response"
        )

    def test_unknown_error_preserves_error_type_and_message(self):
        """Unknown error response still carries error_type and message."""
        error = QueryError(
            error_type="unknown_error",
            message="Something went wrong",
            correlation_id=None,
        )

        result = _build_error_response(error)

        assert result["error_type"] == "unknown_error"
        assert result["message"] == "Something went wrong"


class TestBuildErrorResponseBaseContract:
    """Base contract: all error responses MUST carry success=False."""

    def test_all_errors_have_success_false(self):
        """Every error response dict MUST have success=False."""
        for error_type in ("forbidden", "timeout", "execution_error", "unknown_error"):
            error = QueryError(
                error_type=error_type,
                message="Error",
                correlation_id=None,
            )
            result = _build_error_response(error)
            assert result["success"] is False, (
                f"Expected success=False for error_type={error_type!r}"
            )

    def test_correlation_id_only_included_when_not_none(self):
        """correlation_id key is present iff the QueryError has a non-None correlation_id."""
        error_with_id = QueryError(
            error_type="forbidden",
            message="Forbidden",
            correlation_id="some-id",
        )
        error_without_id = QueryError(
            error_type="execution_error",
            message="Error",
            correlation_id=None,
        )

        result_with = _build_error_response(error_with_id)
        result_without = _build_error_response(error_without_id)

        assert "correlation_id" in result_with
        assert "correlation_id" not in result_without
