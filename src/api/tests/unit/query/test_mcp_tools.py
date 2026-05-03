"""Unit tests for MCP tool functions in the Querying presentation layer.

Tests the knowledge_graph_id filter and secure enclave integration
within the query_graph MCP tool, and header-based token extraction
for the fetch_documentation_source tool.

Spec references:
- Scenario: Optional KnowledgeGraph filter
- Scenario: Secure enclave redaction
- Scenario: Internal property filtering
- Scenario: Private repository with token (x-github-pat / x-gitlab-pat headers)
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from query.ports.file_repository_models import RemoteFileRepositoryResponse
from query.presentation.mcp import (
    _filter_by_knowledge_graph,
    _filter_internal_properties,
    fetch_documentation_source,
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


class TestFetchDocumentationSourceHeaders:
    """Tests for fetch_documentation_source PAT header extraction.

    Spec: Scenario: Private repository with token
    - GIVEN a private repository URL and an access token via x-github-pat
      or x-gitlab-pat header
    - WHEN the tool is called
    - THEN the token is used for authentication against the provider API

    These tests verify that the tool correctly extracts the PAT tokens from
    the MCP HTTP request headers and forwards them to get_git_repository().

    FastMCP wraps registered tool functions in a FunctionTool descriptor;
    the underlying callable is accessed via the ``.fn`` attribute.
    """

    _GITHUB_URL = "https://github.com/owner/repo/blob/main/docs/file.adoc"
    _GITLAB_URL = "https://gitlab.com/owner/repo/-/blob/main/docs/file.adoc"

    def _make_response(
        self, content: str = "= Title\nBody text."
    ) -> RemoteFileRepositoryResponse:
        """Build a successful RemoteFileRepositoryResponse for use in mocks."""
        return RemoteFileRepositoryResponse(
            success=True,
            content=content,
            source_url=self._GITHUB_URL,
            raw_url="https://raw.githubusercontent.com/owner/repo/main/docs/file.adoc",
        )

    def test_github_pat_header_is_passed_as_github_token(self) -> None:
        """x-github-pat header value MUST be forwarded as github_token.

        Spec: Private repository with token — the tool reads x-github-pat from
        the MCP HTTP request headers and passes it to the repository factory so
        that private GitHub repositories can be accessed.
        """
        mock_repo = MagicMock()
        mock_repo.get_file.return_value = self._make_response()

        with (
            patch(
                "query.presentation.mcp.get_http_headers",
                return_value={"x-github-pat": "ghp_test_token_abc123"},
            ),
            patch(
                "query.presentation.mcp.get_git_repository",
                return_value=mock_repo,
            ) as mock_factory,
        ):
            fetch_documentation_source.fn(self._GITHUB_URL)

        mock_factory.assert_called_once_with(
            url=self._GITHUB_URL,
            github_token="ghp_test_token_abc123",
            gitlab_token=None,
        )

    def test_gitlab_pat_header_is_passed_as_gitlab_token(self) -> None:
        """x-gitlab-pat header value MUST be forwarded as gitlab_token.

        Spec: Private repository with token — the tool reads x-gitlab-pat from
        the MCP HTTP request headers and passes it to the repository factory so
        that private GitLab repositories can be accessed.
        """
        mock_repo = MagicMock()
        mock_repo.get_file.return_value = RemoteFileRepositoryResponse(
            success=True,
            content="= Doc\nContent.",
            source_url=self._GITLAB_URL,
        )

        with (
            patch(
                "query.presentation.mcp.get_http_headers",
                return_value={"x-gitlab-pat": "glpat_private_token_xyz"},
            ),
            patch(
                "query.presentation.mcp.get_git_repository",
                return_value=mock_repo,
            ) as mock_factory,
        ):
            fetch_documentation_source.fn(self._GITLAB_URL)

        mock_factory.assert_called_once_with(
            url=self._GITLAB_URL,
            github_token=None,
            gitlab_token="glpat_private_token_xyz",
        )

    def test_both_pat_headers_forwarded_simultaneously(self) -> None:
        """Both x-github-pat and x-gitlab-pat can be present at the same time.

        An MCP client may supply both tokens so the caller doesn't need to know
        in advance which provider hosts the requested URL.  Both MUST be
        forwarded independently to the factory.
        """
        mock_repo = MagicMock()
        mock_repo.get_file.return_value = self._make_response()

        with (
            patch(
                "query.presentation.mcp.get_http_headers",
                return_value={
                    "x-github-pat": "ghp_github_token",
                    "x-gitlab-pat": "glpat_gitlab_token",
                },
            ),
            patch(
                "query.presentation.mcp.get_git_repository",
                return_value=mock_repo,
            ) as mock_factory,
        ):
            fetch_documentation_source.fn(self._GITHUB_URL)

        mock_factory.assert_called_once_with(
            url=self._GITHUB_URL,
            github_token="ghp_github_token",
            gitlab_token="glpat_gitlab_token",
        )

    def test_no_tokens_when_headers_absent(self) -> None:
        """When neither PAT header is present, both tokens must be None.

        Public repositories do not require authentication.  When the headers
        are absent, the factory must receive None for both token arguments so
        the repository makes unauthenticated requests.
        """
        mock_repo = MagicMock()
        mock_repo.get_file.return_value = self._make_response()

        with (
            patch(
                "query.presentation.mcp.get_http_headers",
                return_value={},  # no PAT headers
            ),
            patch(
                "query.presentation.mcp.get_git_repository",
                return_value=mock_repo,
            ) as mock_factory,
        ):
            fetch_documentation_source.fn(self._GITHUB_URL)

        mock_factory.assert_called_once_with(
            url=self._GITHUB_URL,
            github_token=None,
            gitlab_token=None,
        )

    def test_get_file_called_with_url(self) -> None:
        """The tool must call repository.get_file() with the original URL."""
        mock_repo = MagicMock()
        mock_repo.get_file.return_value = self._make_response()

        with (
            patch("query.presentation.mcp.get_http_headers", return_value={}),
            patch("query.presentation.mcp.get_git_repository", return_value=mock_repo),
        ):
            fetch_documentation_source.fn(self._GITHUB_URL)

        mock_repo.get_file.assert_called_once_with(url=self._GITHUB_URL)

    def test_returns_repository_response_directly(self) -> None:
        """The tool must return the RemoteFileRepositoryResponse from get_file()."""
        expected_response = RemoteFileRepositoryResponse(
            success=True,
            content="= My Doc\nFull content here.",
            source_url=self._GITHUB_URL,
            raw_url="https://raw.githubusercontent.com/owner/repo/main/docs/file.adoc",
        )
        mock_repo = MagicMock()
        mock_repo.get_file.return_value = expected_response

        with (
            patch("query.presentation.mcp.get_http_headers", return_value={}),
            patch("query.presentation.mcp.get_git_repository", return_value=mock_repo),
        ):
            result = fetch_documentation_source.fn(self._GITHUB_URL)

        assert result is expected_response

    def test_other_headers_are_not_forwarded_as_tokens(self) -> None:
        """Unrelated HTTP headers must not be treated as PAT tokens.

        The tool only reads x-github-pat and x-gitlab-pat.  Other headers
        (authorization, content-type, etc.) must be ignored for token
        extraction — they are never forwarded to the git repository factory.
        """
        mock_repo = MagicMock()
        mock_repo.get_file.return_value = self._make_response()

        with (
            patch(
                "query.presentation.mcp.get_http_headers",
                return_value={
                    "authorization": "Bearer some-mcp-token",
                    "content-type": "application/json",
                    "x-request-id": "req-abc-123",
                },
            ),
            patch(
                "query.presentation.mcp.get_git_repository",
                return_value=mock_repo,
            ) as mock_factory,
        ):
            fetch_documentation_source.fn(self._GITHUB_URL)

        mock_factory.assert_called_once_with(
            url=self._GITHUB_URL,
            github_token=None,
            gitlab_token=None,
        )
