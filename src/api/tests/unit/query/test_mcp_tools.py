"""Unit tests for MCP tool functions in the Querying presentation layer.

Tests internal property filtering and header-based token extraction
for the fetch_documentation_source tool.

Spec references:
- Scenario: Internal property filtering
- Scenario: Private repository with token (x-github-pat / x-gitlab-pat headers)
- Scenario: Invalid URL format
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from query.ports.exceptions import RemoteFileFetchFailed
from query.ports.file_repository_models import RemoteFileRepositoryResponse
from query.presentation.mcp import (
    _filter_internal_properties,
    fetch_documentation_source,
)


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


class TestFetchDocumentationSourceErrorHandling:
    """Tests for fetch_documentation_source error response for invalid URLs.

    Spec: Requirement: Documentation Fetch Tool — Scenario: Invalid URL format
    GIVEN a URL that does not match GitHub or GitLab blob patterns
    WHEN the tool is called
    THEN an error response is returned

    The tool MUST return RemoteFileRepositoryResponse(success=False, error=...)
    rather than propagating exceptions. MCP clients pattern-match on
    response.success and expect a typed response, not a JSON-RPC fault.

    Spec reference: specs/query/mcp-server.spec.md
    """

    _INVALID_URL = "https://example.com/not-a-git-url"
    _GITHUB_NO_BLOB = "https://github.com/owner/repo"

    def test_invalid_url_returns_error_response(self) -> None:
        """Calling fetch_documentation_source.fn with an unsupported URL MUST
        return RemoteFileRepositoryResponse(success=False).

        Spec: Invalid URL format — THEN an error response is returned.

        The tool's return type is RemoteFileRepositoryResponse. A JSON-RPC
        fault (propagated exception) is the wrong shape for MCP clients that
        pattern-match on response.success.
        """
        with patch(
            "query.presentation.mcp.get_http_headers",
            return_value={},
        ):
            result = fetch_documentation_source.fn(self._INVALID_URL)

        assert isinstance(result, RemoteFileRepositoryResponse), (
            "fetch_documentation_source must always return RemoteFileRepositoryResponse, "
            "even for invalid URLs. Propagating exceptions breaks MCP client contracts."
        )
        assert result.success is False, (
            "Invalid URL must result in success=False, not True."
        )

    def test_invalid_url_error_field_is_not_none(self) -> None:
        """The error field in the response MUST contain a non-empty message.

        An error response with success=False but error=None provides no
        actionable information to the MCP client.
        """
        with patch(
            "query.presentation.mcp.get_http_headers",
            return_value={},
        ):
            result = fetch_documentation_source.fn(self._INVALID_URL)

        assert result.error is not None, (
            "error field must be populated when success=False"
        )
        assert len(result.error) > 0, "error field must contain a non-empty message"

    def test_invalid_url_does_not_raise(self) -> None:
        """fetch_documentation_source.fn MUST NOT raise for an invalid URL.

        Spec: Invalid URL format — THEN an error response is returned.

        The tool must return rather than raise so that FastMCP can serialize
        the response. Unhandled exceptions propagate as JSON-RPC errors (a
        different shape from RemoteFileRepositoryResponse).
        """
        with patch(
            "query.presentation.mcp.get_http_headers",
            return_value={},
        ):
            try:
                result = fetch_documentation_source.fn(self._INVALID_URL)
            except Exception as exc:
                raise AssertionError(
                    f"fetch_documentation_source must not raise for invalid URLs. "
                    f"Got {type(exc).__name__}: {exc}"
                ) from exc

        assert result is not None

    def test_github_url_missing_blob_segment_returns_error_response(self) -> None:
        """GitHub URL without /blob/ segment must produce an error response.

        A bare repository URL (e.g., https://github.com/owner/repo) is not
        a valid blob URL. The tool must return success=False rather than raise.

        Spec: Invalid URL format — THEN an error response is returned.
        """
        with patch(
            "query.presentation.mcp.get_http_headers",
            return_value={},
        ):
            result = fetch_documentation_source.fn(self._GITHUB_NO_BLOB)

        assert isinstance(result, RemoteFileRepositoryResponse)
        assert result.success is False

    def test_remote_fetch_failure_returns_error_response(self) -> None:
        """RemoteFileFetchFailed from repository.get_file() MUST be caught and
        returned as RemoteFileRepositoryResponse(success=False).

        Spec: Invalid URL format — THEN an error response is returned.

        This covers HTTP failures (404, 403, network errors) from get_file().
        The tool must not propagate RemoteFileFetchFailed to FastMCP as a
        JSON-RPC fault.
        """
        mock_repo = MagicMock()
        mock_repo.get_file.side_effect = RemoteFileFetchFailed("HTTP 404: Not Found")

        with (
            patch(
                "query.presentation.mcp.get_http_headers",
                return_value={},
            ),
            patch(
                "query.presentation.mcp.get_git_repository",
                return_value=mock_repo,
            ),
        ):
            result = fetch_documentation_source.fn(
                "https://github.com/owner/repo/blob/main/private.adoc"
            )

        assert isinstance(result, RemoteFileRepositoryResponse)
        assert result.success is False
        assert result.error is not None
        assert "404" in result.error, (
            "Error message should reference the HTTP status code for diagnostics."
        )
