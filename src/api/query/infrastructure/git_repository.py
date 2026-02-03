from abc import abstractmethod
from dataclasses import dataclass
import re
from typing import Optional

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

    owner: str
    repo: str
    ref: str
    path: str


class AbstractGitRemoteFileRepository(IRemoteFileRepository):
    """Repository interface for fetching remote files from a remote git server.

    The repository provides optional access token initialization.

    This interface is designed to enable fetching
    files from remote git servers, such as Github, Gitlab, or others.
    """

    def __init__(
        self,
        access_token: Optional[str] = None,
        probe: RemoteFileRepositoryProbe | None = None,
    ):
        self._access_token = access_token
        self._probe = probe or DefaultRemoteFileRepositoryProbe()

    @abstractmethod
    def get_file(self, url: str) -> RemoteFileRepositoryResponse: ...


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

    def _parse_github_url(self, blob_url: str) -> ParsedGitUrl:
        """Parse a GitHub blob URL into its components.

        Args:
            blob_url: A GitHub blob URL like:
                https://github.com/owner/repo/blob/branch/path/to/file.adoc

        Returns:
            ParsedGitUrl with owner, repo, ref, and path

        Raises:
            ValueError: If the URL is not a valid GitHub blob URL.

        Note:
            Branch/tag names containing slashes (e.g., feature/my-branch) are not
            supported due to URL ambiguity. Use the commit SHA instead:
            - Not supported: github.com/owner/repo/blob/feature/my-branch/file.txt
            - Use instead:   github.com/owner/repo/blob/abc123def456/file.txt
        """
        # Check for potential branch/tag with slashes before regex matching
        # Format: https://github.com/owner/repo/blob/ref/file
        # Expected: 7 slashes (https:/ / github.com/ owner/ repo/ blob/ ref/ file)
        # If exactly 8 slashes, it's ambiguous: could be blob/ref-with-slash/file
        # or blob/ref/dir/file. We reject to avoid silent misparsing.
        slash_count = blob_url.count("/")
        if "/blob/" in blob_url and slash_count == 8:
            # Ambiguous: could be blob/feature/branch/file or blob/main/dir/file
            # We err on the side of caution and require commit SHA for this case
            raise ValueError(
                "Invalid GitHub blob URL. Branch/tag names with slashes are not "
                f"supported. Use a commit SHA instead. Got: {blob_url}"
            )

        match = self._GITHUB_URL_PATTERN.match(blob_url)

        if not match:
            raise ValueError(
                f"Invalid GitHub blob URL. Expected format: "
                "'https://github.com/owner/repo/blob/ref/path/file', "
                f"got: {blob_url}"
            )

        owner, repo, ref, path = match.groups()

        return ParsedGitUrl(owner=owner, repo=repo, ref=ref, path=path)

    def _build_api_url(self, owner: str, repo: str, ref: str, path: str) -> str:
        """Build the GitHub Contents API URL.

        Args:
            owner: Repository owner
            repo: Repository name
            ref: Git reference (branch, tag, or commit SHA)
            path: File path within repository

        Returns:
            GitHub API URL for fetching file content
        """
        return f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={ref}"

    def get_file(self, url: str) -> RemoteFileRepositoryResponse:
        """Fetch file content from GitHub using the official API.

        Args:
            url: GitHub blob URL

        Returns:
            RemoteFileRepositoryResponse with file content

        Raises:
            InvalidRemoteFileURL: If URL format is invalid
            RemoteFileFetchFailed: If fetching fails (network, HTTP error, etc.)
        """
        self._probe.file_fetch_requested(url=url)

        # Parse the GitHub blob URL
        try:
            parsed = self._parse_github_url(url)
        except ValueError as e:
            self._probe.invalid_url_format(url=url, reason=repr(e))
            raise InvalidRemoteFileURL() from e

        # Build API URL
        api_url = self._build_api_url(
            owner=parsed.owner, repo=parsed.repo, ref=parsed.ref, path=parsed.path
        )

        # Fetch content from GitHub API
        try:
            response = httpx.get(api_url, headers=self._request_headers, timeout=30.0)
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
                f"HTTP {response.status_code}: Failed to fetch from GitHub API"
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
