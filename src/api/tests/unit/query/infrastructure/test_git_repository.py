"""Unit tests for GithubRepository and GitRepositoryFactory."""

from unittest.mock import MagicMock, create_autospec, patch

import httpx
import pytest

from query.infrastructure.git_repository import (
    GithubRepository,
    GitRepositoryFactory,
    ParsedGitUrl,
)
from query.infrastructure.observability.remote_file_repository_probe import (
    RemoteFileRepositoryProbe,
)
from query.ports.exceptions import InvalidRemoteFileURL, RemoteFileFetchFailed


@pytest.fixture
def mock_probe():
    """Create mock probe."""
    return create_autospec(RemoteFileRepositoryProbe, instance=True)


@pytest.fixture
def repository(mock_probe):
    """Create repository without access token."""
    return GithubRepository(probe=mock_probe)


@pytest.fixture
def authed_repository(mock_probe):
    """Create repository with access token."""
    return GithubRepository(access_token="ghp_test123", probe=mock_probe)


class TestInit:
    """Tests for repository initialization."""

    def test_stores_access_token(self):
        """Should store access token when provided."""
        repo = GithubRepository(access_token="ghp_test123")
        assert repo._access_token == "ghp_test123"

    def test_no_access_token(self):
        """Should handle None access token."""
        repo = GithubRepository()
        assert repo._access_token is None

    def test_uses_default_probe_when_none_provided(self):
        """Should create default probe if none provided."""
        repo = GithubRepository()
        assert repo._probe is not None


class TestParseGithubUrl:
    """Tests for GitHub URL parsing."""

    def test_parses_valid_blob_url(self, repository):
        """Should parse valid GitHub blob URL."""
        url = "https://github.com/owner/repo/blob/main/path/to/file.adoc"
        parsed = repository._parse_url(url)

        assert parsed.owner == "owner"
        assert parsed.repo == "repo"
        assert parsed.ref == "main"
        assert parsed.path == "path/to/file.adoc"

    def test_parses_url_with_commit_sha(self, repository):
        """Should handle commit SHA as ref."""
        url = "https://github.com/owner/repo/blob/abc123def456/file.adoc"
        parsed = repository._parse_url(url)

        assert parsed.owner == "owner"
        assert parsed.repo == "repo"
        assert parsed.ref == "abc123def456"
        assert parsed.path == "file.adoc"

    def test_raises_on_branch_with_slashes(self, repository):
        """Should raise ValueError for branch names containing slashes with helpful message."""
        url = "https://github.com/owner/repo/blob/feature/my-branch/file.adoc"
        with pytest.raises(
            ValueError, match="Branch/tag names with slashes are not supported"
        ):
            repository._parse_url(url)

    def test_raises_on_invalid_url(self, repository):
        """Should raise ValueError for non-GitHub URL."""
        with pytest.raises(ValueError, match="Invalid GitHub blob URL"):
            repository._parse_url("https://gitlab.com/owner/repo/file.adoc")

    def test_raises_on_missing_blob_segment(self, repository):
        """Should raise ValueError when /blob/ is missing."""
        with pytest.raises(ValueError, match="Invalid GitHub blob URL"):
            repository._parse_url("https://github.com/owner/repo/main/file.adoc")

    def test_raises_on_empty_path(self, repository):
        """Should raise ValueError when path is empty."""
        with pytest.raises(ValueError, match="Invalid GitHub blob URL"):
            repository._parse_url("https://github.com/owner/repo/blob/main/")


class TestBuildApiUrl:
    """Tests for GitHub API URL construction."""

    def test_builds_correct_api_url(self, repository):
        """Should build correct GitHub API URL."""
        parsed = ParsedGitUrl(owner="owner", repo="repo", ref="main", path="file.adoc")
        api_url = repository._build_api_url(parsed)

        assert (
            api_url
            == "https://api.github.com/repos/owner/repo/contents/file.adoc?ref=main"
        )

    def test_builds_url_with_nested_path(self, repository):
        """Should handle nested file paths."""
        parsed = ParsedGitUrl(
            owner="owner", repo="repo", ref="main", path="docs/api/file.adoc"
        )
        api_url = repository._build_api_url(parsed)

        assert (
            api_url
            == "https://api.github.com/repos/owner/repo/contents/docs/api/file.adoc?ref=main"
        )


class TestRequestHeaders:
    """Tests for request headers."""

    def test_includes_auth_header_when_token_provided(self, authed_repository):
        """Should include Authorization header when token is set."""
        headers = authed_repository._request_headers

        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer ghp_test123"
        assert headers["Accept"] == "application/vnd.github.v3.raw"

    def test_no_auth_header_when_no_token(self, repository):
        """Should include Accept header but no Authorization when no token."""
        headers = repository._request_headers

        assert "Authorization" not in headers
        assert headers["Accept"] == "application/vnd.github.v3.raw"


class TestGetFile:
    """Tests for fetching files."""

    @patch("query.infrastructure.git_repository.httpx.get")
    def test_fetches_file_successfully(self, mock_get, repository, mock_probe):
        """Should fetch file content using GitHub API."""
        # Setup
        blob_url = "https://github.com/owner/repo/blob/main/file.adoc"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "= Document Title\n\nContent here"
        mock_get.return_value = mock_response

        # Execute
        result = repository.get_file(blob_url)

        # Verify
        assert result.success is True
        assert result.content == "= Document Title\n\nContent here"
        assert result.source_url == blob_url
        assert (
            result.raw_url
            == "https://api.github.com/repos/owner/repo/contents/file.adoc?ref=main"
        )

        # Verify API was called correctly
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert (
            call_args[0][0]
            == "https://api.github.com/repos/owner/repo/contents/file.adoc?ref=main"
        )
        assert call_args[1]["headers"]["Accept"] == "application/vnd.github.v3.raw"
        assert call_args[1]["timeout"] == 30.0

        # Verify probe was called
        mock_probe.file_fetch_requested.assert_called_once_with(url=blob_url)
        mock_probe.file_fetched.assert_called_once()

    @patch("query.infrastructure.git_repository.httpx.get")
    def test_includes_auth_token_in_request(self, mock_get, authed_repository):
        """Should include authorization header when token is set."""
        # Setup
        blob_url = "https://github.com/owner/repo/blob/main/file.adoc"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "content"
        mock_get.return_value = mock_response

        # Execute
        authed_repository.get_file(blob_url)

        # Verify auth header was included
        call_args = mock_get.call_args
        assert "Authorization" in call_args[1]["headers"]
        assert call_args[1]["headers"]["Authorization"] == "Bearer ghp_test123"

    def test_raises_on_invalid_url(self, repository, mock_probe):
        """Should raise InvalidRemoteFileURL for invalid URLs."""
        with pytest.raises(InvalidRemoteFileURL):
            repository.get_file("https://not-github.com/file.adoc")

        # Verify probe was notified
        mock_probe.file_fetch_requested.assert_called_once()
        mock_probe.invalid_url_format.assert_called_once()

    @patch("query.infrastructure.git_repository.httpx.get")
    def test_raises_on_http_error(self, mock_get, repository, mock_probe):
        """Should raise RemoteFileFetchFailed on HTTP errors."""
        # Setup
        blob_url = "https://github.com/owner/repo/blob/main/file.adoc"
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        # Execute & Verify
        with pytest.raises(RemoteFileFetchFailed):
            repository.get_file(blob_url)

        # Verify probe was notified
        mock_probe.file_fetch_requested.assert_called_once()
        mock_probe.file_fetch_failed.assert_called_once()
        call_args = mock_probe.file_fetch_failed.call_args
        assert call_args[1]["status_code"] == 404

    @patch("query.infrastructure.git_repository.httpx.get")
    def test_raises_on_network_error(self, mock_get, repository, mock_probe):
        """Should raise RemoteFileFetchFailed on network errors."""
        # Setup
        blob_url = "https://github.com/owner/repo/blob/main/file.adoc"
        mock_get.side_effect = httpx.ConnectError("Connection failed")

        # Execute & Verify
        with pytest.raises(RemoteFileFetchFailed):
            repository.get_file(blob_url)

        # Verify probe was notified
        mock_probe.file_fetch_requested.assert_called_once()
        mock_probe.file_fetch_failed.assert_called_once()

    @patch("query.infrastructure.git_repository.httpx.get")
    def test_handles_403_forbidden(self, mock_get, repository, mock_probe):
        """Should handle 403 Forbidden (rate limit or private repo)."""
        # Setup
        blob_url = "https://github.com/owner/repo/blob/main/file.adoc"
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_get.return_value = mock_response

        # Execute & Verify
        with pytest.raises(RemoteFileFetchFailed):
            repository.get_file(blob_url)

        mock_probe.file_fetch_failed.assert_called_once()
        call_args = mock_probe.file_fetch_failed.call_args
        assert call_args[1]["status_code"] == 403


class TestGitRepositoryFactory:
    """Tests for GitRepositoryFactory."""

    def test_creates_github_repository_for_github_url(self, mock_probe):
        """Should create GithubRepository for GitHub URLs."""
        url = "https://github.com/owner/repo/blob/main/file.txt"
        repo = GitRepositoryFactory.create_from_url(
            url=url, access_token="token123", probe=mock_probe
        )

        assert isinstance(repo, GithubRepository)
        assert repo._access_token == "token123"
        assert repo._probe is mock_probe

    def test_creates_github_repository_without_token(self, mock_probe):
        """Should create GithubRepository without access token."""
        url = "https://github.com/owner/repo/blob/main/file.txt"
        repo = GitRepositoryFactory.create_from_url(url=url, probe=mock_probe)

        assert isinstance(repo, GithubRepository)
        assert repo._access_token is None

    def test_creates_github_repository_without_probe(self):
        """Should create GithubRepository with default probe."""
        url = "https://github.com/owner/repo/blob/main/file.txt"
        repo = GitRepositoryFactory.create_from_url(url=url)

        assert isinstance(repo, GithubRepository)
        assert repo._probe is not None

    def test_raises_for_gitlab_url(self):
        """Should raise ValueError for GitLab URLs (not yet implemented)."""
        url = "https://gitlab.com/owner/repo/-/blob/main/file.txt"

        with pytest.raises(ValueError, match="GitLab support coming soon"):
            GitRepositoryFactory.create_from_url(url=url)

    def test_raises_for_unsupported_provider(self):
        """Should raise ValueError for unsupported providers."""
        url = "https://bitbucket.org/owner/repo/src/main/file.txt"

        with pytest.raises(ValueError, match="Unsupported git provider"):
            GitRepositoryFactory.create_from_url(url=url)
