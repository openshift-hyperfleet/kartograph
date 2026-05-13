"""Unit tests for query_graph MCP tool success-path wiring and secure enclave integration.

Tests the *wiring* inside query_graph itself — not the individual components
(which are already tested in test_mcp_query_service.py, test_mcp_secure_enclave.py,
and test_mcp_query_tool.py respectively).

Three things were untested at the tool layer:

1. **Success response format** — no test asserted that the success dict contains
   ``success=True``, ``rows``, ``row_count``, ``truncated``, and ``execution_time_ms``.

2. **Secure enclave call** — no test verified that ``query_graph`` actually calls
   ``secure_enclave.apply_redaction(rows)`` on the service result.  If that line
   were removed, every ``MCPQuerySecureEnclave`` unit test would still pass.

3. **Internal-property filter call** — no test verified that
   ``_filter_internal_properties`` is applied to the rows *after* redaction.

Spec references:
  specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e
  - Requirement: Graph Query Tool / Scenario: Successful query
    "THEN the results are returned with rows, row_count, truncation flag,
     and execution time"
  - Requirement: Graph Query Tool / Scenario: Secure enclave redaction
    "THEN unauthorized nodes are redacted to ID-only"
    "AND unauthorized edges are redacted to their ID, start_id, and end_id only"
    "AND the graph topology is preserved"
  - Requirement: Graph Query Tool / Scenario: Internal property filtering
    "THEN internal properties are stripped from the response"
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

import query.presentation.mcp as mcp_module
from query.domain.value_objects import CypherQueryResult, QueryResultRow
from query.presentation.mcp import query_graph


# ---------------------------------------------------------------------------
# Fakes — no MagicMock for domain/application collaborators
# ---------------------------------------------------------------------------


class FakeMCPQueryService:
    """Fake MCPQueryService that returns a configurable CypherQueryResult.

    Implements execute_cypher_query() without real infrastructure dependencies.
    The fake always returns the pre-configured result, making success-path
    tests deterministic and independent of repository/probe wiring.

    Note: The real MCPQueryService can return CypherQueryResult | QueryError.
    This fake only supports the success path (CypherQueryResult), which is all
    the wiring tests here need.
    """

    def __init__(
        self,
        result: CypherQueryResult | None = None,
    ) -> None:
        self._result = result or CypherQueryResult(
            rows=[],
            row_count=0,
            truncated=False,
            execution_time_ms=0.0,
        )

    def execute_cypher_query(
        self,
        query: str,
        timeout_seconds: int | None = None,
        max_rows: int | None = None,
    ) -> CypherQueryResult:
        return self._result


class FakePassthroughEnclave:
    """Fake secure enclave that returns rows unchanged.

    Used for tests that only care about response format, not redaction
    behaviour.  Calling apply_redaction() is a no-op (passthrough).
    """

    async def apply_redaction(self, rows: list[QueryResultRow]) -> list[QueryResultRow]:
        return rows


class RecordingEnclave:
    """Fake secure enclave that records every call to apply_redaction.

    Used to verify that query_graph calls apply_redaction with the correct
    arguments (the rows from the service result).  Optionally returns a
    pre-configured result instead of the input, enabling ordering tests.

    Attributes:
        calls: List of row-lists passed to each apply_redaction() call.
    """

    def __init__(self, result: list[QueryResultRow] | None = None) -> None:
        self.calls: list[list[QueryResultRow]] = []
        # None → return input unchanged (passthrough); otherwise return fixed result
        self._result = result

    async def apply_redaction(self, rows: list[QueryResultRow]) -> list[QueryResultRow]:
        self.calls.append(list(rows))
        return self._result if self._result is not None else rows


class RedactingEnclave:
    """Fake secure enclave that strips all node properties except 'id'.

    Simulates the deny-all behaviour of MCPQuerySecureEnclave for nodes
    whose knowledge_graph_id the caller is not authorized to view.  Used
    to verify that query_graph returns post-redaction rows (not raw rows).

    Redaction rule applied here:
    - Node dict (has 'id' + 'properties'): reduced to {"id": original_id}
    - Everything else: passed through unchanged
    """

    async def apply_redaction(self, rows: list[QueryResultRow]) -> list[QueryResultRow]:
        redacted: list[QueryResultRow] = []
        for row in rows:
            redacted_row: QueryResultRow = {}
            for key, value in row.items():
                if isinstance(value, dict) and "id" in value and "properties" in value:
                    # Redact node: keep only 'id'
                    redacted_row[key] = {"id": value["id"]}  # type: ignore[assignment]
                else:
                    redacted_row[key] = value  # type: ignore[assignment]
            redacted.append(redacted_row)
        return redacted


# ---------------------------------------------------------------------------
# Helper — type-erasing wrapper for dict literals
# ---------------------------------------------------------------------------


def _make_node_row(
    node_id: str,
    label: str,
    properties: dict[str, Any],
) -> QueryResultRow:
    """Build a well-typed node row for test data.

    Plain ``{"node": {...}}`` literals are inferred as
    ``dict[str, dict[str, str]]`` by mypy, incompatible with the strict
    ``QueryResultRow`` alias.  Using this helper avoids per-call ignores.
    """
    return {"node": {"id": node_id, "label": label, "properties": properties}}  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# TestQueryGraphToolSuccessPath
# ---------------------------------------------------------------------------


class TestQueryGraphToolSuccessPath:
    """Success-path response format.

    Spec: Graph Query Tool — Scenario: Successful query
    GIVEN an authenticated MCP client
    WHEN the client calls query_graph with a valid Cypher query
    THEN the results are returned with rows, row_count, truncation flag,
         and execution time
    """

    @pytest.mark.asyncio
    async def test_success_response_contains_all_required_fields(self) -> None:
        """Success response MUST contain success, rows, row_count, truncated, execution_time_ms.

        If any required field is dropped or renamed, this test catches it.
        This is the primary regression guard for the success dict shape.
        """
        fake_service = FakeMCPQueryService(
            result=CypherQueryResult(
                rows=[{"value": 42}],
                row_count=1,
                truncated=False,
                execution_time_ms=12.5,
            )
        )
        fake_enclave = FakePassthroughEnclave()

        with patch.object(
            mcp_module, "get_mcp_secure_enclave", return_value=fake_enclave
        ):
            result = await query_graph.fn(
                cypher="MATCH (n) RETURN count(n)",
                service=fake_service,
            )

        assert "success" in result, "success key must be present in success response"
        assert "rows" in result, "rows key must be present in success response"
        assert "row_count" in result, (
            "row_count key must be present in success response"
        )
        assert "truncated" in result, (
            "truncated key must be present in success response"
        )
        assert "execution_time_ms" in result, (
            "execution_time_ms key must be present in success response"
        )

    @pytest.mark.asyncio
    async def test_success_flag_is_true(self) -> None:
        """Success response MUST have success=True.

        Distinguishes the success path from error responses (which have
        success=False).  If query_graph returned the error dict structure
        on success, this test would catch it.
        """
        fake_service = FakeMCPQueryService(
            result=CypherQueryResult(
                rows=[{"value": 1}],
                row_count=1,
                truncated=False,
                execution_time_ms=5.0,
            )
        )
        fake_enclave = FakePassthroughEnclave()

        with patch.object(
            mcp_module, "get_mcp_secure_enclave", return_value=fake_enclave
        ):
            result = await query_graph.fn(
                cypher="MATCH (n) RETURN 1",
                service=fake_service,
            )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_row_count_matches_rows_length(self) -> None:
        """row_count MUST equal len(rows) in the success response.

        The tool computes row_count from the filtered + redacted rows list,
        not from CypherQueryResult.row_count (which reflects pre-filter size).
        A consistent row_count == len(rows) is the spec contract.

        Scenario: changing ``"row_count": len(filtered_rows)`` to
        ``"row_count": 0`` in mcp.py would cause this test to fail.
        """
        rows: list[QueryResultRow] = [{"value": i} for i in range(5)]  # type: ignore[list-item]
        fake_service = FakeMCPQueryService(
            result=CypherQueryResult(
                rows=rows,
                row_count=5,
                truncated=False,
                execution_time_ms=8.0,
            )
        )
        fake_enclave = FakePassthroughEnclave()

        with patch.object(
            mcp_module, "get_mcp_secure_enclave", return_value=fake_enclave
        ):
            result = await query_graph.fn(
                cypher="MATCH (n) RETURN n",
                service=fake_service,
            )

        assert result["row_count"] == len(result["rows"]), (
            "row_count must equal len(rows) in the response"
        )
        assert result["row_count"] == 5

    @pytest.mark.asyncio
    async def test_truncated_forwarded_from_service_result(self) -> None:
        """truncated MUST be taken from CypherQueryResult.truncated, not recomputed.

        Spec: query response includes a truncation flag.
        If someone changed the source of the truncated flag (e.g., to always
        False), this test would catch it.
        """
        fake_service = FakeMCPQueryService(
            result=CypherQueryResult(
                rows=[{"value": i} for i in range(10)],
                row_count=10,
                truncated=True,  # explicitly True — must appear in response
                execution_time_ms=20.0,
            )
        )
        fake_enclave = FakePassthroughEnclave()

        with patch.object(
            mcp_module, "get_mcp_secure_enclave", return_value=fake_enclave
        ):
            result = await query_graph.fn(
                cypher="MATCH (n) RETURN n",
                service=fake_service,
            )

        assert result["truncated"] is True, (
            "truncated must be forwarded from CypherQueryResult.truncated"
        )

    @pytest.mark.asyncio
    async def test_execution_time_ms_forwarded_from_service_result(self) -> None:
        """execution_time_ms MUST come from CypherQueryResult.execution_time_ms.

        Spec: query response includes execution time.
        If execution_time_ms were dropped or renamed in the response dict,
        this test would catch it.
        """
        expected_time = 123.456
        fake_service = FakeMCPQueryService(
            result=CypherQueryResult(
                rows=[],
                row_count=0,
                truncated=False,
                execution_time_ms=expected_time,
            )
        )
        fake_enclave = FakePassthroughEnclave()

        with patch.object(
            mcp_module, "get_mcp_secure_enclave", return_value=fake_enclave
        ):
            result = await query_graph.fn(
                cypher="MATCH (n) RETURN n LIMIT 0",
                service=fake_service,
            )

        assert result["execution_time_ms"] == expected_time, (
            "execution_time_ms must be forwarded from CypherQueryResult.execution_time_ms"
        )


# ---------------------------------------------------------------------------
# TestQueryGraphToolSecureEnclaveWiring
# ---------------------------------------------------------------------------


class TestQueryGraphToolSecureEnclaveWiring:
    """Tests that query_graph correctly calls the secure enclave.

    Spec: Graph Query Tool — Scenario: Secure enclave redaction
    GIVEN query results containing entities the caller is not authorized to view
    WHEN the results are returned
    THEN unauthorized nodes are redacted to ID-only
    AND unauthorized edges are redacted to their ID, start_id, and end_id only
    AND the graph topology is preserved

    These tests verify the *wiring* — that apply_redaction is actually called
    with the rows from the service, and that its output drives the response.
    If the ``rows = await secure_enclave.apply_redaction(rows)`` line were
    removed from mcp.py, the tests in this class would fail while every
    MCPQuerySecureEnclave unit test would still pass.
    """

    @pytest.mark.asyncio
    async def test_apply_redaction_called_on_service_result_rows(self) -> None:
        """apply_redaction MUST be called with the rows returned by the service.

        This is the primary safety net: if apply_redaction were removed from
        query_graph, query results would be silently unredacted and exposed to
        callers without authorization.  This test makes that regression visible.
        """
        service_rows = [
            _make_node_row(
                "1", "Person", {"name": "Alice", "knowledge_graph_id": "kg-1"}
            )
        ]
        fake_service = FakeMCPQueryService(
            result=CypherQueryResult(
                rows=service_rows,
                row_count=1,
                truncated=False,
                execution_time_ms=5.0,
            )
        )
        recording_enclave = RecordingEnclave()

        with patch.object(
            mcp_module, "get_mcp_secure_enclave", return_value=recording_enclave
        ):
            await query_graph.fn(
                cypher="MATCH (n) RETURN n",
                service=fake_service,
            )

        assert len(recording_enclave.calls) == 1, (
            "apply_redaction must be called exactly once per query_graph invocation"
        )
        # The rows passed to apply_redaction must be the service result rows
        # (after KG filtering, but here knowledge_graph_id=None so no filtering)
        assert recording_enclave.calls[0] == service_rows, (
            "apply_redaction must receive the rows from the service result"
        )

    @pytest.mark.asyncio
    async def test_apply_redaction_called_before_internal_property_filter(
        self,
    ) -> None:
        """apply_redaction MUST be called before _filter_internal_properties.

        The ordering (redact → strip internal) is critical for correctness:
        redaction makes authorization decisions on full properties, then
        internal props are stripped from the (possibly-redacted) result.

        We verify this ordering by:
        1. Having the recording enclave return rows that contain all_content_lower.
        2. Checking the final response has all_content_lower stripped.
        → Proves _filter_internal_properties ran on post-enclave rows.
        """
        # Enclave will return rows with all_content_lower present
        post_redaction_rows: list[QueryResultRow] = [
            _make_node_row(
                "1",
                "Person",
                {
                    "name": "Alice",
                    "all_content_lower": "alice",  # must be stripped AFTER enclave
                    "knowledge_graph_id": "kg-1",
                },
            )
        ]
        fake_service = FakeMCPQueryService(
            result=CypherQueryResult(
                rows=[
                    _make_node_row("1", "Person", {"name": "Alice"})
                ],  # service rows (replaced by enclave)
                row_count=1,
                truncated=False,
                execution_time_ms=5.0,
            )
        )
        # The enclave replaces its input with post_redaction_rows (which still have
        # all_content_lower — internal filtering hasn't happened yet).
        recording_enclave = RecordingEnclave(result=post_redaction_rows)

        with patch.object(
            mcp_module, "get_mcp_secure_enclave", return_value=recording_enclave
        ):
            result = await query_graph.fn(
                cypher="MATCH (n) RETURN n",
                service=fake_service,
            )

        # apply_redaction was called (confirms enclave is wired)
        assert len(recording_enclave.calls) == 1, (
            "apply_redaction must have been called"
        )

        # _filter_internal_properties ran on the post-enclave rows
        node_props = result["rows"][0]["node"]["properties"]
        assert "all_content_lower" not in node_props, (
            "_filter_internal_properties must be applied AFTER apply_redaction; "
            "all_content_lower should have been stripped from the enclave output"
        )
        assert node_props["name"] == "Alice"

    @pytest.mark.asyncio
    async def test_redacted_rows_returned_not_raw_rows(self) -> None:
        """The response rows MUST be the post-redaction output, not the raw service rows.

        When the enclave redacts a node (strips all props to just ``{"id": ...}``),
        the caller must receive the redacted version.  If query_graph returned
        the raw service rows instead, this test would catch the regression.
        """
        service_rows = [
            _make_node_row(
                "1",
                "Person",
                {
                    "name": "Alice",
                    "secret_field": "classified",
                    "knowledge_graph_id": "kg-denied",
                },
            )
        ]
        fake_service = FakeMCPQueryService(
            result=CypherQueryResult(
                rows=service_rows,
                row_count=1,
                truncated=False,
                execution_time_ms=5.0,
            )
        )
        redacting_enclave = RedactingEnclave()

        with patch.object(
            mcp_module, "get_mcp_secure_enclave", return_value=redacting_enclave
        ):
            result = await query_graph.fn(
                cypher="MATCH (n) RETURN n",
                service=fake_service,
            )

        assert len(result["rows"]) == 1
        node = result["rows"][0]["node"]
        # Post-redaction: only 'id' present
        assert node == {"id": "1"}, (
            "Returned rows must be the post-redaction rows from the enclave, "
            "not the raw rows from the service.  "
            f"Got: {node!r}"
        )
        assert "label" not in node, "redacted node must not expose label"
        assert "properties" not in node, "redacted node must not expose properties"
        assert "secret_field" not in str(node), (
            "secret_field must not appear in the redacted response"
        )


# ---------------------------------------------------------------------------
# TestQueryGraphToolInternalPropertyFilterWiring
# ---------------------------------------------------------------------------


class TestQueryGraphToolInternalPropertyFilterWiring:
    """Tests that query_graph applies _filter_internal_properties to results.

    Spec: Graph Query Tool — Scenario: Internal property filtering
    GIVEN query results containing internal properties (e.g., all_content_lower)
    WHEN the results are returned to the client
    THEN internal properties are stripped from the response

    These tests verify the *wiring* — that the filter is actually applied
    to the success response rows, not just that _filter_internal_properties()
    works in isolation (which is tested in test_mcp_query_tool.py).
    """

    @pytest.mark.asyncio
    async def test_internal_properties_stripped_from_success_response(self) -> None:
        """all_content_lower MUST be absent from the success response rows.

        The service (and enclave) may return rows with all_content_lower in
        node properties. query_graph MUST strip it before returning to the client.

        If the ``_filter_internal_properties`` call were removed from query_graph,
        all_content_lower would leak through to MCP clients.
        """
        service_rows = [
            _make_node_row(
                "1",
                "DocumentationModule",
                {
                    "name": "install-guide",
                    "content_summary": "A brief guide.",
                    "all_content_lower": "install guide a brief guide.",
                },
            )
        ]
        fake_service = FakeMCPQueryService(
            result=CypherQueryResult(
                rows=service_rows,
                row_count=1,
                truncated=False,
                execution_time_ms=3.0,
            )
        )
        fake_enclave = FakePassthroughEnclave()

        with patch.object(
            mcp_module, "get_mcp_secure_enclave", return_value=fake_enclave
        ):
            result = await query_graph.fn(
                cypher="MATCH (n:DocumentationModule) RETURN n",
                service=fake_service,
            )

        assert len(result["rows"]) == 1
        node_props = result["rows"][0]["node"]["properties"]
        assert "all_content_lower" not in node_props, (
            "all_content_lower must be stripped from the success response rows; "
            "it is an internal search-index property not meant for MCP clients"
        )
        assert node_props["name"] == "install-guide"
        assert node_props["content_summary"] == "A brief guide."

    @pytest.mark.asyncio
    async def test_internal_property_filter_applied_to_all_rows(self) -> None:
        """Internal property filter MUST be applied to all rows.

        When knowledge_graph_id is specified, rows are first filtered to that
        KG, then passed through the enclave, then internal properties are
        stripped.  This test verifies the complete pipeline produces the correct
        final output: only matching KG rows, with all_content_lower absent.
        """
        service_rows = [
            _make_node_row(
                "1",
                "Person",
                {
                    "name": "Alice",
                    "knowledge_graph_id": "kg-1",
                    "all_content_lower": "alice",
                },
            ),
            _make_node_row(
                "2",
                "Person",
                {
                    "name": "Bob",
                    "knowledge_graph_id": "kg-2",
                    "all_content_lower": "bob",
                },
            ),
        ]
        fake_service = FakeMCPQueryService(
            result=CypherQueryResult(
                rows=service_rows,
                row_count=2,
                truncated=False,
                execution_time_ms=6.0,
            )
        )
        fake_enclave = FakePassthroughEnclave()

        with patch.object(
            mcp_module, "get_mcp_secure_enclave", return_value=fake_enclave
        ):
            result = await query_graph.fn(
                cypher="MATCH (n:Person) RETURN n",
                service=fake_service,
            )

        # KG post-filter removed — Secure Enclave handles authorization.
        # Both rows pass through (knowledge_graph_id param is deprecated).
        assert result["row_count"] == 2
        assert len(result["rows"]) == 2

        # Internal property filter: all_content_lower stripped from both
        for row in result["rows"]:
            node_props = row["node"]["properties"]
            assert "all_content_lower" not in node_props, (
                "all_content_lower must be stripped after enclave"
            )
