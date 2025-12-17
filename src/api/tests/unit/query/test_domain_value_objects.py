"""Unit tests for Querying domain value objects."""

import pytest

from query.domain.value_objects import CypherQueryResult, QueryError


class TestCypherQueryResult:
    """Tests for CypherQueryResult value object."""

    def test_is_immutable(self):
        """Result should be immutable (frozen)."""
        result = CypherQueryResult(rows=[], row_count=0)
        with pytest.raises(Exception):  # ValidationError for frozen model
            result.row_count = 5

    def test_stores_rows(self):
        """Should store query result rows."""
        rows = [{"name": "Alice"}, {"name": "Bob"}]
        result = CypherQueryResult(rows=rows, row_count=2)
        assert result.rows == rows
        assert result.row_count == 2

    def test_default_row_count(self):
        """Should default row_count to 0."""
        result = CypherQueryResult()
        assert result.row_count == 0
        assert result.rows == []

    def test_tracks_truncation(self):
        """Should track if results were truncated."""
        result = CypherQueryResult(rows=[], row_count=0, truncated=True)
        assert result.truncated is True

    def test_truncation_defaults_to_false(self):
        """Truncated should default to False."""
        result = CypherQueryResult(rows=[], row_count=0)
        assert result.truncated is False

    def test_tracks_execution_time(self):
        """Should track execution time."""
        result = CypherQueryResult(rows=[], row_count=0, execution_time_ms=123.45)
        assert result.execution_time_ms == 123.45

    def test_execution_time_optional(self):
        """Execution time should be optional."""
        result = CypherQueryResult(rows=[], row_count=0)
        assert result.execution_time_ms is None


class TestQueryError:
    """Tests for QueryError value object."""

    def test_is_immutable(self):
        """Error should be immutable (frozen)."""
        error = QueryError(error_type="forbidden", message="Not allowed")
        with pytest.raises(Exception):  # ValidationError for frozen model
            error.error_type = "timeout"

    def test_stores_error_details(self):
        """Should store error type and message."""
        error = QueryError(
            error_type="forbidden",
            message="Query contains CREATE",
            query="CREATE (n:Test)",
        )
        assert error.error_type == "forbidden"
        assert error.message == "Query contains CREATE"
        assert error.query == "CREATE (n:Test)"

    def test_query_is_optional(self):
        """Query field should be optional."""
        error = QueryError(error_type="timeout", message="Query timed out")
        assert error.query is None

    def test_requires_error_type(self):
        """Should require error_type field."""
        with pytest.raises(Exception):  # ValidationError
            QueryError(message="Missing type")

    def test_requires_message(self):
        """Should require message field."""
        with pytest.raises(Exception):  # ValidationError
            QueryError(error_type="timeout")
