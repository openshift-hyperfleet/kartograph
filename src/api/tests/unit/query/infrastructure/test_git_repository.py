"""Unit tests for GithubRepository, GitLabRepository and GitRepositoryFactory."""

from unittest.mock import MagicMock, create_autospec, patch

import httpx
import pytest

from query.infrastructure.git_repository import (
    GithubRepository,
    GitLabRepository,
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

        assert parsed.hostname == "github.com"
        assert parsed.owner == "owner"
        assert parsed.repo == "repo"
        assert parsed.ref == "main"
        assert parsed.path == "path/to/file.adoc"

    def test_parses_url_with_commit_sha(self, repository):
        """Should handle commit SHA as ref."""
        url = "https://github.com/owner/repo/blob/abc123def456/file.adoc"
        parsed = repository._parse_url(url)

        assert parsed.hostname == "github.com"
        assert parsed.owner == "owner"
        assert parsed.repo == "repo"
        assert parsed.ref == "abc123def456"
        assert parsed.path == "file.adoc"

    def test_parses_url_with_nested_path(self, repository):
        """Should handle nested directory paths correctly."""
        url = "https://github.com/openshift/openshift-docs/blob/main/modules/amd-testing-the-amd-gpu-operator.adoc"
        parsed = repository._parse_url(url)

        assert parsed.hostname == "github.com"
        assert parsed.owner == "openshift"
        assert parsed.repo == "openshift-docs"
        assert parsed.ref == "main"
        assert parsed.path == "modules/amd-testing-the-amd-gpu-operator.adoc"

    def test_parses_url_with_deeply_nested_path(self, repository):
        """Should handle deeply nested directory paths."""
        url = "https://github.com/owner/repo/blob/main/docs/api/v1/examples/file.adoc"
        parsed = repository._parse_url(url)

        assert parsed.hostname == "github.com"
        assert parsed.owner == "owner"
        assert parsed.repo == "repo"
        assert parsed.ref == "main"
        assert parsed.path == "docs/api/v1/examples/file.adoc"

    def test_parses_ambiguous_url_as_ref_without_slash(self, repository):
        """Should parse ambiguous URLs (branch with slash vs nested path) as ref without slash.

        Note: URLs like blob/feature/branch/file are ambiguous:
        - Could be: ref=feature/branch, path=file (if 'feature/branch' is a branch name)
        - Parsed as: ref=feature, path=branch/file (regex limitation)

        Users with branch names containing slashes should use commit SHAs instead.
        """
        url = "https://github.com/owner/repo/blob/feature/my-branch/file.adoc"
        parsed = repository._parse_url(url)

        # Parsed as ref without slash (may be incorrect if feature/my-branch is a branch name)
        assert parsed.hostname == "github.com"
        assert parsed.owner == "owner"
        assert parsed.repo == "repo"
        assert parsed.ref == "feature"
        assert parsed.path == "my-branch/file.adoc"

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
        parsed = ParsedGitUrl(
            hostname="github.com",
            owner="owner",
            repo="repo",
            ref="main",
            path="file.adoc",
        )
        api_url = repository._build_api_url(parsed)

        assert (
            api_url
            == "https://api.github.com/repos/owner/repo/contents/file.adoc?ref=main"
        )

    def test_builds_url_with_nested_path(self, repository):
        """Should handle nested file paths."""
        parsed = ParsedGitUrl(
            hostname="github.com",
            owner="owner",
            repo="repo",
            ref="main",
            path="docs/api/file.adoc",
        )
        api_url = repository._build_api_url(parsed)

        assert (
            api_url
            == "https://api.github.com/repos/owner/repo/contents/docs/api/file.adoc?ref=main"
        )

    def test_builds_enterprise_api_url(self, repository):
        """Should build GitHub Enterprise API URL with /api/v3/ path."""
        parsed = ParsedGitUrl(
            hostname="github.enterprise.com",
            owner="owner",
            repo="repo",
            ref="main",
            path="file.adoc",
        )
        api_url = repository._build_api_url(parsed)

        assert (
            api_url
            == "https://github.enterprise.com/api/v3/repos/owner/repo/contents/file.adoc?ref=main"
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


class TestGitLabRepository:
    """Tests for GitLabRepository."""

    @pytest.fixture
    def gitlab_repository(self, mock_probe):
        """Create GitLab repository without access token."""
        return GitLabRepository(probe=mock_probe)

    @pytest.fixture
    def authed_gitlab_repository(self, mock_probe):
        """Create GitLab repository with access token."""
        return GitLabRepository(access_token="glpat-test123", probe=mock_probe)

    def test_parses_valid_gitlab_url(self, gitlab_repository):
        """Should parse valid GitLab blob URL."""
        url = "https://gitlab.com/owner/repo/-/blob/main/path/to/file.adoc"
        parsed = gitlab_repository._parse_url(url)

        assert parsed.hostname == "gitlab.com"
        assert parsed.owner == "owner"
        assert parsed.repo == "repo"
        assert parsed.ref == "main"
        assert parsed.path == "path/to/file.adoc"

    def test_parses_self_hosted_gitlab_url(self, gitlab_repository):
        """Should parse self-hosted GitLab URLs."""
        url = "https://gitlab.company.com/team/project/-/blob/develop/README.md"
        parsed = gitlab_repository._parse_url(url)

        assert parsed.hostname == "gitlab.company.com"
        assert parsed.owner == "team"
        assert parsed.repo == "project"
        assert parsed.ref == "develop"
        assert parsed.path == "README.md"

    def test_parses_gitlab_url_with_nested_path(self, gitlab_repository):
        """Should handle nested directory paths."""
        url = "https://gitlab.com/gitlab-org/gitlab/-/blob/master/doc/development/testing.md"
        parsed = gitlab_repository._parse_url(url)

        assert parsed.hostname == "gitlab.com"
        assert parsed.owner == "gitlab-org"
        assert parsed.repo == "gitlab"
        assert parsed.ref == "master"
        assert parsed.path == "doc/development/testing.md"

    def test_raises_on_invalid_gitlab_url(self, gitlab_repository):
        """Should raise ValueError for non-GitLab URL."""
        with pytest.raises(ValueError, match="Invalid GitLab blob URL"):
            gitlab_repository._parse_url("https://github.com/owner/repo/file.adoc")

    def test_raises_on_missing_dash_blob_segment(self, gitlab_repository):
        """Should raise ValueError when /-/blob/ is missing."""
        with pytest.raises(ValueError, match="Invalid GitLab blob URL"):
            gitlab_repository._parse_url(
                "https://gitlab.com/owner/repo/blob/main/file.adoc"
            )

    def test_builds_correct_gitlab_api_url(self, gitlab_repository):
        """Should build correct GitLab API URL with URL encoding."""
        parsed = ParsedGitUrl(
            hostname="gitlab.com",
            owner="owner",
            repo="repo",
            ref="main",
            path="file.adoc",
        )
        api_url = gitlab_repository._build_api_url(parsed)

        assert (
            api_url
            == "https://gitlab.com/api/v4/projects/owner%2Frepo/repository/files/file.adoc/raw?ref=main"
        )

    def test_builds_gitlab_api_url_with_nested_path(self, gitlab_repository):
        """Should URL-encode nested file paths."""
        parsed = ParsedGitUrl(
            hostname="gitlab.com",
            owner="owner",
            repo="repo",
            ref="main",
            path="docs/api/file.adoc",
        )
        api_url = gitlab_repository._build_api_url(parsed)

        assert (
            api_url
            == "https://gitlab.com/api/v4/projects/owner%2Frepo/repository/files/docs%2Fapi%2Ffile.adoc/raw?ref=main"
        )

    def test_builds_api_url_for_self_hosted(self, gitlab_repository):
        """Should use extracted hostname for self-hosted instances."""
        parsed = ParsedGitUrl(
            hostname="gitlab.company.com",
            owner="team",
            repo="project",
            ref="main",
            path="README.md",
        )
        api_url = gitlab_repository._build_api_url(parsed)

        assert (
            api_url
            == "https://gitlab.company.com/api/v4/projects/team%2Fproject/repository/files/README.md/raw?ref=main"
        )

    def test_gitlab_request_headers_with_token(self, authed_gitlab_repository):
        """Should include PRIVATE-TOKEN header when token is set."""
        headers = authed_gitlab_repository._request_headers

        assert "PRIVATE-TOKEN" in headers
        assert headers["PRIVATE-TOKEN"] == "glpat-test123"

    def test_gitlab_request_headers_without_token(self, gitlab_repository):
        """Should return empty dict when no token."""
        headers = gitlab_repository._request_headers

        assert "PRIVATE-TOKEN" not in headers
        assert headers == {}

    @patch("query.infrastructure.git_repository.httpx.get")
    def test_fetches_gitlab_file_successfully(
        self, mock_get, gitlab_repository, mock_probe
    ):
        """Should fetch file content using GitLab API."""
        # Setup
        blob_url = "https://gitlab.com/owner/repo/-/blob/main/file.adoc"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "= Document Title\n\nContent here"
        mock_get.return_value = mock_response

        # Execute
        result = gitlab_repository.get_file(blob_url)

        # Verify
        assert result.success is True
        assert result.content == "= Document Title\n\nContent here"
        assert result.source_url == blob_url

        # Verify API was called correctly
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert "gitlab.com/api/v4/projects" in call_args[0][0]
        assert call_args[1]["timeout"] == 30.0
        assert call_args[1]["follow_redirects"] is False


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

    def test_creates_gitlab_repository_for_gitlab_url(self, mock_probe):
        """Should create GitLabRepository for GitLab URLs."""
        url = "https://gitlab.com/owner/repo/-/blob/main/file.txt"
        repo = GitRepositoryFactory.create_from_url(
            url=url, access_token="glpat-123", probe=mock_probe
        )

        assert isinstance(repo, GitLabRepository)
        assert repo._access_token == "glpat-123"
        assert repo._probe is mock_probe

    def test_creates_gitlab_repository_for_self_hosted(self, mock_probe):
        """Should create GitLabRepository for self-hosted GitLab instances."""
        url = "https://gitlab.company.com/team/project/-/blob/main/file.txt"
        repo = GitRepositoryFactory.create_from_url(url=url, probe=mock_probe)

        assert isinstance(repo, GitLabRepository)
        assert repo._access_token is None

    def test_creates_github_repository_for_github_enterprise(self, mock_probe):
        """Should create GithubRepository for GitHub Enterprise URLs."""
        url = "https://github.enterprise.com/owner/repo/blob/main/file.txt"
        repo = GitRepositoryFactory.create_from_url(url=url, probe=mock_probe)

        assert isinstance(repo, GithubRepository)

    def test_raises_for_unsupported_provider(self):
        """Should raise ValueError for unsupported providers."""
        url = "https://bitbucket.org/owner/repo/src/main/file.txt"

        with pytest.raises(ValueError, match="Unsupported git provider"):
            GitRepositoryFactory.create_from_url(url=url)

    def test_prevents_ssrf_with_github_in_path(self):
        """Should reject URLs with github.com in path (SSRF prevention)."""
        url = "https://evil.com/github.com/malicious"

        with pytest.raises(ValueError, match="Unsupported git provider"):
            GitRepositoryFactory.create_from_url(url=url)

    def test_accepts_any_hostname_with_valid_pattern(self, mock_probe):
        """Should accept any hostname with valid blob pattern (supports self-hosted).

        Note: This is intentional to support self-hosted instances.
        Users explicitly provide URLs, so they control the destination.
        """
        url = "https://custom.git.host.com/owner/repo/blob/main/file.txt"
        repo = GitRepositoryFactory.create_from_url(url=url, probe=mock_probe)

        assert isinstance(repo, GithubRepository)

    def test_prevents_ssrf_with_github_in_query(self):
        """Should reject URLs with github.com in query string (SSRF prevention)."""
        url = "https://evil.com/path?redirect=github.com"

        with pytest.raises(ValueError, match="Unsupported git provider"):
            GitRepositoryFactory.create_from_url(url=url)

    def test_case_insensitive_hostname_matching(self):
        """Should accept GitHub.com with different casing."""
        url = "https://GitHub.COM/owner/repo/blob/main/file.txt"
        repo = GitRepositoryFactory.create_from_url(url=url)

        assert isinstance(repo, GithubRepository)

    def test_rejects_invalid_url_format(self):
        """Should raise ValueError for malformed URLs."""
        url = "not-a-url"

        with pytest.raises(ValueError, match="Missing hostname"):
            GitRepositoryFactory.create_from_url(url=url)

    def test_rejects_url_without_hostname(self):
        """Should raise ValueError for URLs without hostname."""
        url = "file:///local/path/file.txt"

        with pytest.raises(ValueError, match="Missing hostname"):
            GitRepositoryFactory.create_from_url(url=url)
