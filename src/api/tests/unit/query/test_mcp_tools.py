"""Unit tests for MCP tool functions in the Querying presentation layer.

Tests the knowledge_graph_id filter and secure enclave integration
within the query_graph MCP tool.

Spec references:
- Scenario: Optional KnowledgeGraph filter
- Scenario: Secure enclave redaction
- Scenario: Internal property filtering
"""

from __future__ import annotations

from typing import Any

from query.presentation.mcp import (
    _filter_by_knowledge_graph,
    _filter_internal_properties,
)


# ---------------------------------------------------------------------------
# Type-erasing test helpers
# ---------------------------------------------------------------------------


def _filter_kg(rows: list, knowledge_graph_id: str | None) -> list[Any]:
    """Type-erasing wrapper for _filter_by_knowledge_graph.

    Plain dict literals in tests are inferred as ``list[dict[str, dict[str, str]]]``
    by mypy, which is incompatible with the strict ``list[QueryResultRow]`` param.
    A single ignore here is cleaner than annotating every call site.
    """
    return _filter_by_knowledge_graph(rows, knowledge_graph_id)  # type: ignore[arg-type]


class TestFilterByKnowledgeGraph:
    """Tests for the knowledge_graph_id post-filter helper.

    Spec: Optional KnowledgeGraph filter — results are filtered to only that KG.
    """

    def test_no_filter_returns_all_rows(self) -> None:
        """When knowledge_graph_id is None, all rows are returned unchanged."""
        rows = [
            {
                "node": {
                    "id": "1",
                    "label": "Person",
                    "properties": {"name": "Alice", "knowledge_graph_id": "kg-1"},
                }
            },
            {
                "node": {
                    "id": "2",
                    "label": "Person",
                    "properties": {"name": "Bob", "knowledge_graph_id": "kg-2"},
                }
            },
        ]
        result = _filter_kg(rows, knowledge_graph_id=None)

        assert len(result) == 2

    def test_filter_includes_matching_node(self) -> None:
        """Nodes with matching knowledge_graph_id should be included."""
        rows = [
            {
                "node": {
                    "id": "1",
                    "label": "Person",
                    "properties": {"name": "Alice", "knowledge_graph_id": "kg-1"},
                }
            }
        ]
        result = _filter_kg(rows, knowledge_graph_id="kg-1")

        assert len(result) == 1

    def test_filter_excludes_non_matching_node(self) -> None:
        """Nodes with a different knowledge_graph_id should be excluded."""
        rows = [
            {
                "node": {
                    "id": "1",
                    "label": "Person",
                    "properties": {"name": "Alice", "knowledge_graph_id": "kg-2"},
                }
            }
        ]
        result = _filter_kg(rows, knowledge_graph_id="kg-1")

        assert len(result) == 0

    def test_filter_includes_matching_edge(self) -> None:
        """Edges with matching knowledge_graph_id should be included."""
        rows = [
            {
                "edge": {
                    "id": "10",
                    "label": "KNOWS",
                    "start_id": "1",
                    "end_id": "2",
                    "properties": {"since": 2020, "knowledge_graph_id": "kg-1"},
                }
            }
        ]
        result = _filter_kg(rows, knowledge_graph_id="kg-1")

        assert len(result) == 1

    def test_filter_excludes_non_matching_edge(self) -> None:
        """Edges from a different KnowledgeGraph should be excluded."""
        rows = [
            {
                "edge": {
                    "id": "10",
                    "label": "KNOWS",
                    "start_id": "1",
                    "end_id": "2",
                    "properties": {"knowledge_graph_id": "kg-2"},
                }
            }
        ]
        result = _filter_kg(rows, knowledge_graph_id="kg-1")

        assert len(result) == 0

    def test_filter_excludes_node_with_no_knowledge_graph_id(self) -> None:
        """Nodes without knowledge_graph_id property are excluded when filter is set."""
        rows = [
            {
                "node": {
                    "id": "1",
                    "label": "Person",
                    "properties": {"name": "Alice"},  # no knowledge_graph_id
                }
            }
        ]
        result = _filter_kg(rows, knowledge_graph_id="kg-1")

        assert len(result) == 0

    def test_filter_mixed_rows(self) -> None:
        """Only rows matching the knowledge_graph_id should remain."""
        rows = [
            {
                "node": {
                    "id": "1",
                    "label": "Person",
                    "properties": {"name": "Alice", "knowledge_graph_id": "kg-1"},
                }
            },
            {
                "node": {
                    "id": "2",
                    "label": "Person",
                    "properties": {"name": "Bob", "knowledge_graph_id": "kg-2"},
                }
            },
            {
                "node": {
                    "id": "3",
                    "label": "Person",
                    "properties": {"name": "Carol", "knowledge_graph_id": "kg-1"},
                }
            },
        ]
        result = _filter_kg(rows, knowledge_graph_id="kg-1")

        assert len(result) == 2
        ids = [r["node"]["id"] for r in result]
        assert "1" in ids
        assert "3" in ids
        assert "2" not in ids

    def test_filter_includes_scalar_rows(self) -> None:
        """Scalar rows (count, etc.) have no knowledge_graph_id, should pass through."""
        rows = [{"value": 42}]
        result = _filter_kg(rows, knowledge_graph_id="kg-1")

        # Scalars always pass through (can't filter without entity)
        assert len(result) == 1
        assert result[0] == {"value": 42}

    def test_filter_map_result_with_matching_entity(self) -> None:
        """Map results with at least one matching entity should be included."""
        rows = [
            {
                "person": {
                    "id": "1",
                    "label": "Person",
                    "properties": {"name": "Alice", "knowledge_graph_id": "kg-1"},
                },
                "count": 5,
            }
        ]
        result = _filter_kg(rows, knowledge_graph_id="kg-1")

        assert len(result) == 1

    def test_filter_map_result_with_no_matching_entity(self) -> None:
        """Map results where no entity matches should be excluded."""
        rows = [
            {
                "person": {
                    "id": "1",
                    "label": "Person",
                    "properties": {"name": "Alice", "knowledge_graph_id": "kg-2"},
                }
            }
        ]
        result = _filter_kg(rows, knowledge_graph_id="kg-1")

        assert len(result) == 0

    def test_empty_rows_returns_empty(self) -> None:
        """Empty input returns empty output."""
        result = _filter_kg([], knowledge_graph_id="kg-1")
        assert result == []


class TestFilterInternalProperties:
    """Tests for internal property filtering (already-implemented, regression guard).

    Spec: Internal property filtering — `all_content_lower` and similar
    must be stripped before returning to the MCP client.
    """

    def test_strips_all_content_lower_from_node_properties(self) -> None:
        """all_content_lower must be removed from node properties."""
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
            }
        ]
        result = _filter_internal_properties(rows)

        assert "all_content_lower" not in result[0]["node"]["properties"]
        assert result[0]["node"]["properties"]["name"] == "Alice"

    def test_preserves_non_internal_properties(self) -> None:
        """Non-internal properties should be preserved."""
        data = {"name": "Alice", "role": "Engineer"}
        result = _filter_internal_properties(data)
        assert result == {"name": "Alice", "role": "Engineer"}
