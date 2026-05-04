"""Unit tests for the query_graph MCP tool helper functions.

Tests two extracted helpers from the `query_graph` MCP tool:

1. `_build_error_response` — constructs the error response dict.
2. `_filter_internal_properties` — strips internal implementation properties
   (e.g. `all_content_lower`) from query results before returning to agents.

Key contracts under test:

_build_error_response:
  - Forbidden errors include correlation_id (spec: keyword blacklist scenario).
  - Timeout errors include correlation_id (spec: query exceeds timeout scenario).
  - Execution errors omit correlation_id key (avoids misleading null).
  - Unknown errors omit correlation_id key.
  - Successful responses don't have correlation_id.

_filter_internal_properties:
  - `all_content_lower` is stripped from all dicts, including nested ones.
  - Non-internal properties are preserved.
  - Filtering is recursive: applies to dicts inside lists and dicts inside dicts.
  - Scalars (int, str, bool, float, None) pass through unchanged.

Note: `query_graph` is wrapped by `@mcp.tool` and cannot be called directly
in unit tests. We test the extracted helpers to verify their contracts in
isolation.

Spec references:
  specs/query/mcp-server.spec.md
  - Req: Graph Query Tool / Scenario: Internal property filtering
    "THEN internal properties are stripped from the response"
  specs/query/query-execution.spec.md
  - Req: Read-Only Enforcement / Scenario: Keyword blacklist (secondary)
    "AND the error response includes a correlation ID for log lookup"
  - Req: Timeout Enforcement / Scenario: Query exceeds timeout
    "THEN a timeout error is returned with a correlation ID for debugging"
"""

from __future__ import annotations

from query.domain.value_objects import QueryError
from query.presentation.mcp import _build_error_response, _filter_internal_properties


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


# ---------------------------------------------------------------------------
# TestFilterInternalProperties
# ---------------------------------------------------------------------------


class TestFilterInternalPropertiesBasicFiltering:
    """Basic filtering: flat dict with/without internal properties.

    Spec: Graph Query Tool — Scenario: Internal property filtering
    GIVEN query results containing internal properties (e.g., `all_content_lower`)
    WHEN the results are returned to the client
    THEN internal properties are stripped from the response
    """

    def test_strips_all_content_lower_from_flat_dict(self) -> None:
        """all_content_lower MUST be stripped from a flat dict.

        This is the primary internal property that the implementation currently
        guards against. It is a concatenated lowercase search-index field that
        must never be exposed to MCP clients.
        """
        data = {"all_content_lower": "foo", "name": "bar"}

        result = _filter_internal_properties(data)

        assert "all_content_lower" not in result
        assert result == {"name": "bar"}

    def test_preserves_non_internal_properties(self) -> None:
        """Non-internal properties must be preserved unchanged."""
        data = {"name": "Alice", "label": "Person", "age": 30}

        result = _filter_internal_properties(data)

        assert result == {"name": "Alice", "label": "Person", "age": 30}

    def test_empty_dict_returns_empty_dict(self) -> None:
        """An empty dict must remain an empty dict after filtering."""
        result = _filter_internal_properties({})

        assert result == {}

    def test_dict_with_only_internal_props_returns_empty(self) -> None:
        """A dict containing only internal properties becomes empty after filtering.

        The empty dict is the correct result — stripping all internal
        properties yields no remaining data.
        """
        data = {"all_content_lower": "alice engineer"}

        result = _filter_internal_properties(data)

        assert result == {}

    def test_strips_all_defined_internal_properties(self) -> None:
        """All properties in INTERNAL_PROPERTIES must be stripped.

        Currently only `all_content_lower` is defined. This test asserts that
        a dict containing this property alongside `name` produces a result
        containing only `name`. When a second internal property is added to
        INTERNAL_PROPERTIES in the future, this test should be updated to
        verify it is also stripped.
        """
        data = {"all_content_lower": "alice", "name": "Alice"}

        result = _filter_internal_properties(data)

        assert "all_content_lower" not in result
        assert result["name"] == "Alice"


class TestFilterInternalPropertiesNodeDict:
    """Node dict filtering — the primary use case.

    Query results arrive as NodeDicts ({"node": {id, label, properties}}).
    The `all_content_lower` field lives inside `properties`.
    """

    def test_strips_internal_props_from_node_dict(self) -> None:
        """all_content_lower MUST be stripped from node properties.

        Spec: Internal property filtering — `all_content_lower` is stripped
        before returning results to the MCP client.
        """
        data = {
            "node": {
                "id": "1",
                "label": "Person",
                "properties": {
                    "name": "Alice",
                    "role": "Engineer",
                    "all_content_lower": "alice engineer",
                },
            }
        }

        result = _filter_internal_properties(data)

        node_props = result["node"]["properties"]
        assert "all_content_lower" not in node_props
        assert node_props["name"] == "Alice"
        assert node_props["role"] == "Engineer"

    def test_preserves_node_dict_structure(self) -> None:
        """id, label, and non-internal properties MUST be preserved unchanged.

        The filter must not alter the shape of the NodeDict — only strip
        internal properties from `properties`.
        """
        data = {
            "node": {
                "id": "42",
                "label": "Service",
                "properties": {
                    "name": "payment-service",
                    "version": "1.0.0",
                },
            }
        }

        result = _filter_internal_properties(data)

        node = result["node"]
        assert node["id"] == "42"
        assert node["label"] == "Service"
        assert node["properties"]["name"] == "payment-service"
        assert node["properties"]["version"] == "1.0.0"


class TestFilterInternalPropertiesEdgeDict:
    """Edge dict filtering.

    EdgeDicts have the same `properties` nesting as NodeDicts.
    `all_content_lower` must be stripped from edge properties while
    preserving `id`, `label`, `start_id`, and `end_id`.
    """

    def test_strips_internal_props_from_edge_dict(self) -> None:
        """all_content_lower MUST be stripped from edge properties.

        Edge structural fields (id, label, start_id, end_id) must survive.
        """
        data = {
            "edge": {
                "id": "10",
                "label": "DEPENDS_ON",
                "start_id": "1",
                "end_id": "2",
                "properties": {
                    "since": 2020,
                    "all_content_lower": "depends on since 2020",
                },
            }
        }

        result = _filter_internal_properties(data)

        edge = result["edge"]
        assert "all_content_lower" not in edge["properties"]
        assert edge["properties"]["since"] == 2020
        assert edge["id"] == "10"
        assert edge["label"] == "DEPENDS_ON"
        assert edge["start_id"] == "1"
        assert edge["end_id"] == "2"


class TestFilterInternalPropertiesRecursion:
    """Recursive filtering — dicts inside dicts, lists inside dicts.

    `_filter_internal_properties` is a recursive function. It must
    propagate filtering through arbitrarily nested data structures.
    """

    def test_filters_recursively_through_nested_dicts(self) -> None:
        """Filtering must propagate into nested dicts.

        A nested dict `{"a": {"all_content_lower": "x", "b": 1}}` must
        produce `{"a": {"b": 1}}` — the inner `all_content_lower` is stripped.
        """
        data = {"a": {"all_content_lower": "x", "b": 1}}

        result = _filter_internal_properties(data)

        assert result == {"a": {"b": 1}}

    def test_filters_recursively_through_lists(self) -> None:
        """Filtering must propagate into items inside a list.

        `[{"all_content_lower": "x"}, {"name": "foo"}]` must produce
        `[{}, {"name": "foo"}]`.
        """
        data = [{"all_content_lower": "x"}, {"name": "foo"}]

        result = _filter_internal_properties(data)

        assert result == [{}, {"name": "foo"}]

    def test_filters_list_inside_dict(self) -> None:
        """A list nested inside a dict must be filtered recursively.

        `{"items": [{"all_content_lower": "x", "n": 1}]}` must produce
        `{"items": [{"n": 1}]}`.
        """
        data = {"items": [{"all_content_lower": "x", "n": 1}]}

        result = _filter_internal_properties(data)

        assert result == {"items": [{"n": 1}]}

    def test_filters_deeply_nested_structure(self) -> None:
        """Filtering must work at arbitrary nesting depth.

        A three-level nesting with `all_content_lower` at the leaf level must
        be stripped, while all other structure is preserved.
        """
        data = {
            "outer": {
                "inner": {
                    "all_content_lower": "deep value",
                    "id": "node-123",
                }
            }
        }

        result = _filter_internal_properties(data)

        inner = result["outer"]["inner"]
        assert "all_content_lower" not in inner
        assert inner["id"] == "node-123"


class TestFilterInternalPropertiesScalarPassThrough:
    """Scalars pass through unchanged.

    Filtering is a no-op for any non-dict, non-list value. This covers
    integers, strings, booleans, floats, and None.
    """

    def test_scalars_pass_through_unchanged(self) -> None:
        """Scalar values MUST be returned as-is without any modification."""
        for value in (42, "hello", True, False, 3.14):
            result = _filter_internal_properties(value)
            assert result == value, (
                f"Expected scalar {value!r} to pass through unchanged, "
                f"but got {result!r}"
            )

    def test_none_passes_through(self) -> None:
        """None MUST pass through unchanged.

        None may appear as a property value or in optional fields.
        The filter must not modify it.
        """
        result = _filter_internal_properties(None)

        assert result is None

    def test_integer_zero_passes_through(self) -> None:
        """Zero (falsy integer) MUST pass through unchanged.

        Ensures the implementation does not special-case falsy values.
        """
        result = _filter_internal_properties(0)

        assert result == 0

    def test_empty_string_passes_through(self) -> None:
        """Empty string MUST pass through unchanged."""
        result = _filter_internal_properties("")

        assert result == ""


class TestFilterInternalPropertiesRowStructure:
    """Filtering applied to the full query result row shape.

    The `query_graph` tool operates on `list[QueryResultRow]`. Each row is
    a dict like `{"node": NodeDict}`, `{"edge": EdgeDict}`, or `{"value": scalar}`.
    This class exercises the complete row-level filtering contract.
    """

    def test_filters_full_node_row(self) -> None:
        """A complete node row with all_content_lower must have it stripped.

        This simulates the actual row format produced by QueryGraphRepository.
        """
        rows = [
            {
                "node": {
                    "id": "1",
                    "label": "DocumentationModule",
                    "properties": {
                        "name": "install-guide",
                        "content_summary": "A brief guide.",
                        "all_content_lower": "install guide a brief guide.",
                    },
                }
            }
        ]

        result = _filter_internal_properties(rows)

        node_props = result[0]["node"]["properties"]
        assert "all_content_lower" not in node_props
        assert node_props["name"] == "install-guide"
        assert node_props["content_summary"] == "A brief guide."

    def test_scalar_row_passes_through_unchanged(self) -> None:
        """A scalar row (e.g., count) must pass through without modification."""
        rows = [{"value": 42}]

        result = _filter_internal_properties(rows)

        assert result == [{"value": 42}]

    def test_multiple_rows_each_filtered(self) -> None:
        """All rows in a multi-row result must be filtered individually."""
        rows = [
            {
                "node": {
                    "id": "1",
                    "label": "Person",
                    "properties": {
                        "name": "Alice",
                        "all_content_lower": "alice",
                    },
                }
            },
            {
                "node": {
                    "id": "2",
                    "label": "Person",
                    "properties": {
                        "name": "Bob",
                        "all_content_lower": "bob",
                    },
                }
            },
        ]

        result = _filter_internal_properties(rows)

        for row in result:
            assert "all_content_lower" not in row["node"]["properties"]

        assert result[0]["node"]["properties"]["name"] == "Alice"
        assert result[1]["node"]["properties"]["name"] == "Bob"
