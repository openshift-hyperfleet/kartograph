from abc import abstractmethod
from dataclasses import dataclass
import re
from typing import Optional
from urllib.parse import quote, urlparse

import httpx
from query.infrastructure.observability.remote_file_repository_probe import (
    DefaultRemoteFileRepositoryProbe,
    RemoteFileRepositoryProbe,
)
from query.ports.exceptions import InvalidRemoteFileURL, RemoteFileFetchFailed
from query.ports.file_repository_models import RemoteFileRepositoryResponse
from query.ports.repositories import IRemoteFileRepository


@dataclass(frozen=True, slots=True)
class ParsedGitUrl:
    """Components of a parsed Git repository URL."""

    hostname: str
    owner: str
    repo: str
    ref: str
    path: str


class AbstractGitRemoteFileRepository(IRemoteFileRepository):
    """Template for git provider repositories.

    Uses Template Method pattern: implements common HTTP flow,
    delegates provider-specific details to subclasses.
    """

    def __init__(
        self,
        access_token: Optional[str] = None,
        probe: RemoteFileRepositoryProbe | None = None,
    ):
        self._access_token = access_token
        self._probe = probe or DefaultRemoteFileRepositoryProbe()

    def get_file(self, url: str) -> RemoteFileRepositoryResponse:
        """Fetch file content using provider-specific API.

        Template method that orchestrates the common flow while
        delegating provider-specific details to subclasses.

        Args:
            url: Provider-specific blob URL

        Returns:
            RemoteFileRepositoryResponse with file content

        Raises:
            InvalidRemoteFileURL: If URL format is invalid
            RemoteFileFetchFailed: If fetching fails (network, HTTP error, etc.)
        """
        self._probe.file_fetch_requested(url=url)

        # Parse URL (provider-specific)
        try:
            parsed = self._parse_url(url)
        except ValueError as e:
            self._probe.invalid_url_format(url=url, reason=repr(e))
            raise InvalidRemoteFileURL() from e

        # Build API URL (provider-specific)
        api_url = self._build_api_url(parsed)

        # Common HTTP logic
        try:
            response = httpx.get(
                api_url,
                headers=self._request_headers,
                timeout=30.0,
                follow_redirects=False,
            )
        except Exception as e:
            self._probe.file_fetch_failed(url=url, reason=repr(e))
            raise RemoteFileFetchFailed() from e

        # Check for HTTP errors
        if response.status_code != 200:
            self._probe.file_fetch_failed(
                url=url,
                reason="HTTP error",
                status_code=response.status_code,
            )
            raise RemoteFileFetchFailed(
                f"HTTP {response.status_code}: Failed to fetch from API"
            )

        content = response.text

        self._probe.file_fetched(
            url=url,
            raw_url=api_url,
            content_length=len(content),
        )

        return RemoteFileRepositoryResponse(
            success=True, content=content, raw_url=api_url, source_url=url
        )

    @abstractmethod
    def _parse_url(self, url: str) -> ParsedGitUrl:
        """Parse provider-specific URL format.

        Args:
            url: Provider blob URL

        Returns:
            ParsedGitUrl with extracted components

        Raises:
            ValueError: If URL format is invalid
        """
        ...

    @abstractmethod
    def _build_api_url(self, parsed: ParsedGitUrl) -> str:
        """Build provider-specific API URL.

        Args:
            parsed: Parsed URL components

        Returns:
            API URL for fetching file content
        """
        ...

    @property
    @abstractmethod
    def _request_headers(self) -> dict[str, str]:
        """Build provider-specific request headers including auth.

        Returns:
            Dictionary of HTTP headers
        """
        ...


class GithubRepository(AbstractGitRemoteFileRepository):
    """GitHub file repository using the official GitHub Contents API.

    Fetches file content from GitHub repositories using the REST API.
    Supports both public and private repositories via optional access token.

    Note: Branch/tag names containing forward slashes are not supported.
    Use commit SHAs instead for such cases.
    """

    # Matches: https://github.com/owner/repo/blob/ref/path/to/file
    # Limitation: ref cannot contain slashes (use commit SHA for branches with slashes)
    _GITHUB_URL_PATTERN = re.compile(
        r"^https://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)$"
    )

    @property
    def _request_headers(self) -> dict[str, str]:
        """Build request headers including auth token if available."""
        headers = {
            "Accept": "application/vnd.github.v3.raw",  # Returns raw content directly
        }

        if self._access_token is not None:
            headers["Authorization"] = f"Bearer {self._access_token}"

        return headers

    def _parse_url(self, url: str) -> ParsedGitUrl:
        """Parse a GitHub blob URL into its components.

        Args:
            url: A GitHub blob URL like:
                https://github.com/owner/repo/blob/branch/path/to/file.adoc

        Returns:
            ParsedGitUrl with hostname, owner, repo, ref, and path

        Raises:
            ValueError: If the URL is not a valid GitHub blob URL.

        Note:
            Branch/tag names containing slashes (e.g., feature/my-branch) are not
            supported. The regex pattern ensures refs cannot contain slashes.
            If you have such a branch, use the commit SHA instead.
        """
        # Extract hostname
        parsed = urlparse(url)
        hostname = parsed.hostname

        if not hostname:
            raise ValueError(f"Missing hostname in URL: {url}")

        match = self._GITHUB_URL_PATTERN.match(url)

        if not match:
            raise ValueError(
                f"Invalid GitHub blob URL. Expected format: "
                "'https://github.com/owner/repo/blob/ref/path/file', "
                f"got: {url}"
            )

        owner, repo, ref, path = match.groups()

        return ParsedGitUrl(
            hostname=hostname, owner=owner, repo=repo, ref=ref, path=path
        )

    def _build_api_url(self, parsed: ParsedGitUrl) -> str:
        """Build the GitHub Contents API URL.

        Supports both public GitHub and GitHub Enterprise:
        - Public: https://api.github.com/repos/...
        - Enterprise: https://hostname/api/v3/repos/...

        Args:
            parsed: Parsed URL components

        Returns:
            GitHub API URL for fetching file content
        """
        # Public GitHub uses api.github.com subdomain
        if parsed.hostname == "github.com":
            api_base = "https://api.github.com"
        else:
            # GitHub Enterprise uses /api/v3/ path on the same hostname
            api_base = f"https://{parsed.hostname}/api/v3"

        return (
            f"{api_base}/repos/{parsed.owner}/{parsed.repo}/"
            f"contents/{parsed.path}?ref={parsed.ref}"
        )


class GitLabRepository(AbstractGitRemoteFileRepository):
    """GitLab file repository using the official GitLab Repository Files API.

    Fetches file content from GitLab repositories (gitlab.com or self-hosted).
    Supports both public and private repositories via optional access token.

    Note: Branch/tag names containing forward slashes are not supported.
    Use commit SHAs instead for such cases.
    """

    # Matches: https://{hostname}/owner/repo/-/blob/ref/path/to/file
    # Note the /-/ segment which differentiates GitLab from GitHub
    _GITLAB_URL_PATTERN = re.compile(
        r"^https://([^/]+)/([^/]+)/([^/]+)/-/blob/([^/]+)/(.+)$"
    )

    @property
    def _request_headers(self) -> dict[str, str]:
        """Build request headers including auth token if available."""
        if self._access_token is None:
            return {}

        return {"PRIVATE-TOKEN": self._access_token}

    def _parse_url(self, url: str) -> ParsedGitUrl:
        """Parse a GitLab blob URL into its components.

        Args:
            url: A GitLab blob URL like:
                https://gitlab.com/owner/repo/-/blob/branch/path/to/file.adoc

        Returns:
            ParsedGitUrl with hostname, owner, repo, ref, and path

        Raises:
            ValueError: If the URL is not a valid GitLab blob URL.

        Note:
            Branch/tag names containing slashes (e.g., feature/my-branch) are not
            supported. The regex pattern ensures refs cannot contain slashes.
            If you have such a branch, use the commit SHA instead.
        """
        match = self._GITLAB_URL_PATTERN.match(url)

        if not match:
            raise ValueError(
                f"Invalid GitLab blob URL. Expected format: "
                "'https://hostname/owner/repo/-/blob/ref/path/file', "
                f"got: {url}"
            )

        hostname, owner, repo, ref, path = match.groups()

        return ParsedGitUrl(
            hostname=hostname, owner=owner, repo=repo, ref=ref, path=path
        )

    def _build_api_url(self, parsed: ParsedGitUrl) -> str:
        """Build the GitLab Repository Files API URL.

        Args:
            parsed: Parsed URL components

        Returns:
            GitLab API URL for fetching raw file content

        Note:
            GitLab requires URL encoding for both project path (owner/repo)
            and file path. The API format is:
            https://{host}/api/v4/projects/{project_id}/repository/files/{file_path}/raw?ref={ref}
        """
        # URL-encode project path (owner/repo)
        project_path = f"{parsed.owner}/{parsed.repo}"
        encoded_project = quote(project_path, safe="")

        # URL-encode file path
        encoded_path = quote(parsed.path, safe="")

        return (
            f"https://{parsed.hostname}/api/v4/projects/{encoded_project}/"
            f"repository/files/{encoded_path}/raw?ref={parsed.ref}"
        )


class GitRepositoryFactory:
    """Factory for creating git repository instances based on URL.

    Automatically detects the git provider from the URL and returns
    the appropriate repository implementation.
    """

    @staticmethod
    def create_from_url(
        url: str,
        github_token: Optional[str] = None,
        gitlab_token: Optional[str] = None,
        probe: Optional[RemoteFileRepositoryProbe] = None,
    ) -> IRemoteFileRepository:
        """Create appropriate git repository based on URL pattern.

        Detects provider by URL structure and selects the appropriate token.
        Supports self-hosted instances (e.g., gitlab.company.com, github.enterprise.com).

        Detection:
        - GitLab: Contains /-/blob/ segment → uses gitlab_token
        - GitHub: Contains /blob/ segment (without /-/) → uses github_token

        Security: Validates hostname exists to prevent SSRF attacks.

        Args:
            url: Git blob URL (GitHub, GitLab, self-hosted, etc.)
            github_token: Optional GitHub access token
            gitlab_token: Optional GitLab access token
            probe: Optional observability probe

        Returns:
            Repository instance for the detected provider with appropriate token

        Raises:
            ValueError: If URL is not from a supported git provider

        Example:
            >>> factory = GitRepositoryFactory()
            >>> # Factory auto-selects gitlab_token for GitLab URLs
            >>> repo = factory.create_from_url(
            ...     "https://gitlab.company.com/owner/repo/-/blob/main/file.txt",
            ...     github_token="ghp_...",
            ...     gitlab_token="glpat-..."
            ... )
            >>> response = repo.get_file(url)
        """
        # Validate URL and extract hostname to prevent SSRF
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname
        except Exception:
            raise ValueError(f"Invalid URL format: {url}")

        if not hostname:
            raise ValueError(f"Missing hostname in URL: {url}")

        # Detect provider by URL pattern and select appropriate token
        if "/-/blob/" in url:
            # GitLab pattern: /-/blob/
            return GitLabRepository(access_token=gitlab_token, probe=probe)
        elif "/blob/" in url:
            # GitHub pattern: /blob/ (without /-/)
            return GithubRepository(access_token=github_token, probe=probe)

        raise ValueError(
            f"Unsupported git provider. URL must contain /blob/ (GitHub) "
            f"or /-/blob/ (GitLab). Got: {url}"
        )
