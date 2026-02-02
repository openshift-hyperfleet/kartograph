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


class GithubRepository(IRemoteFileRepository):
    _GITHUB_BLOB_PATTERN = re.compile(
        r"^https://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)$"
    )

    def __init__(
        self,
        access_token: Optional[str] = None,
        probe: RemoteFileRepositoryProbe | None = None,
    ):
        self._access_token = access_token
        self._probe = probe or DefaultRemoteFileRepositoryProbe()

    @property
    def _request_headers(self) -> dict[str, str]:
        if self._access_token is None:
            return {}

        return {"Authorization": f"Bearer {self._access_token}"}

    def _transform_github_blob_to_raw_url(self, blob_url: str) -> str:
        """Transform a GitHub blob URL to a raw.githubusercontent.com URL.

        Args:
            blob_url: A GitHub blob URL like:
                https://github.com/owner/repo/blob/branch/path/to/file.adoc

        Returns:
            The corresponding raw URL like:
                https://raw.githubusercontent.com/owner/repo/branch/path/to/file.adoc

        Raises:
            ValueError: If the URL is not a valid GitHub blob URL.
        """
        match = self._GITHUB_BLOB_PATTERN.match(blob_url)

        if not match:
            raise ValueError(
                f"Invalid URL format. Expected a GitHub blob URL like "
                f"'https://github.com/owner/repo/blob/branch/path/file.adoc', "
                f"got: {blob_url}"
            )

        owner, repo, branch, path = match.groups()

        return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"

    def _extract_asciidoc_content(self, raw_content: str) -> str:
        """Extract the main content from an AsciiDoc file.

        Strips metadata, comments, and attributes that appear before the first
        level-1 heading (= Title). Returns content from the title onwards.

        Args:
            raw_content: The raw AsciiDoc file content.

        Returns:
            The content starting from the first level-1 heading title,
            or the original content if no heading is found.
        """
        if not raw_content:
            return raw_content

        # Find the first occurrence of "\n= " (level-1 heading after newline)
        # or "= " at the very start of the file
        newline_heading_pos = raw_content.find("\n= ")
        start_heading_match = raw_content.startswith("= ")

        if start_heading_match:
            # Heading is at the very start, skip the "= " marker
            return raw_content[2:]
        elif newline_heading_pos != -1:
            # Found heading after newline, skip "\n= " to start at title text
            return raw_content[newline_heading_pos + 3 :]
        else:
            # No level-1 heading found, return as-is
            return raw_content

    def _fetch_blob(
        self,
        blob_url: str,
    ) -> RemoteFileRepositoryResponse:
        """Core implementation for fetching documentation source content.

        Args:
            blob_url: A blob_url

        Returns:
            A RemoteFileRepositoryResponse
        """
        self._probe.file_fetch_requested(url=blob_url)

        # Transform the GitHub blob URL to raw content URL
        try:
            raw_url = self._transform_github_blob_to_raw_url(blob_url=blob_url)
        except ValueError as e:
            self._probe.invalid_url_format(url=blob_url, reason=repr(e))
            raise InvalidRemoteFileURL() from e

        # Fetch the raw content
        try:
            response = httpx.get(raw_url, timeout=30.0, follow_redirects=True)
        except Exception as e:
            self._probe.file_fetch_failed(url=blob_url, reason=repr(e))
            raise RemoteFileFetchFailed() from e

        # Check for HTTP errors
        if response.status_code != 200:
            self._probe.file_fetch_failed(
                url=blob_url,
                reason="HTTP error",
                status_code=response.status_code,
            )
            raise RemoteFileFetchFailed(
                f"HTTP {response.status_code}: Failed to fetch content from {raw_url}"
            )

        # Extract the main content (strip metadata/comments before title)
        raw_content = response.text
        content = self._extract_asciidoc_content(raw_content=raw_content)

        self._probe.file_fetched(
            url=blob_url,
            raw_url=raw_url,
            content_length=len(content),
        )

        return RemoteFileRepositoryResponse(
            success=True, content=content, raw_url=raw_url, source_url=blob_url
        )

    def get_file(self, url: str) -> RemoteFileRepositoryResponse:
        return self._fetch_blob(blob_url=url)
