"""Git-backed diff summary service for data-source maintenance cues."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from management.domain.aggregates import DataSource
from shared_kernel.credential_reader import ICredentialReader
from shared_kernel.datasource_types import DataSourceAdapterType


@dataclass(frozen=True)
class DiffSummaryResult:
    """Aggregate + file-level diff summary between baseline and tracked head."""

    baseline_commit: str | None
    tracked_head_commit: str | None
    total_changed_files: int
    added_count: int
    modified_count: int
    removed_count: int
    renamed_count: int
    files_truncated: bool
    changed_files: tuple[dict[str, str], ...]


class GitDiffSummaryService:
    """Build a Git commit diff summary for a data source."""

    def __init__(
        self,
        credential_reader: ICredentialReader,
        tenant_id: str,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._credential_reader = credential_reader
        self._tenant_id = tenant_id
        self._http_client = http_client

    @staticmethod
    def _parse_github_connection_config(config: dict[str, str]) -> tuple[str, str]:
        if "repo_url" in config:
            parsed = urlparse(config["repo_url"])
            path_parts = [part for part in parsed.path.split("/") if part]
            if len(path_parts) < 2:
                raise ValueError("repo_url must include owner and repo")
            owner = path_parts[0]
            repo = path_parts[1].removesuffix(".git")
            return owner, repo

        if "owner" in config and "repo" in config:
            return config["owner"], config["repo"]

        raise ValueError(
            "connection_config must include either 'repo_url' or 'owner'+'repo' keys"
        )

    async def build_summary(
        self,
        *,
        data_source: DataSource,
        max_files: int,
    ) -> DiffSummaryResult:
        """Compute changed-file summary from baseline commit to tracked head."""
        baseline = data_source.last_extraction_baseline_commit
        tracked = data_source.tracked_branch_head_commit
        if (
            data_source.adapter_type != DataSourceAdapterType.GITHUB
            or not baseline
            or not tracked
            or baseline == tracked
        ):
            return DiffSummaryResult(
                baseline_commit=baseline,
                tracked_head_commit=tracked,
                total_changed_files=0,
                added_count=0,
                modified_count=0,
                removed_count=0,
                renamed_count=0,
                files_truncated=False,
                changed_files=(),
            )

        owner, repo = self._parse_github_connection_config(data_source.connection_config)
        credentials: dict[str, str] = {}
        if data_source.credentials_path:
            try:
                credentials = await self._credential_reader.retrieve(
                    path=data_source.credentials_path,
                    tenant_id=self._tenant_id,
                )
            except KeyError:
                credentials = {}

        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        token = credentials.get("token") or credentials.get("access_token")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        url = f"https://api.github.com/repos/{owner}/{repo}/compare/{baseline}...{tracked}"
        client = self._http_client or httpx.AsyncClient(timeout=30.0)
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            payload = response.json()
        finally:
            if self._http_client is None:
                await client.aclose()

        files: list[dict[str, str]] = []
        counts = {"added": 0, "modified": 0, "removed": 0, "renamed": 0}
        for file in payload.get("files", []):
            status = str(file.get("status", "modified"))
            if status in counts:
                counts[status] += 1
            files.append(
                {
                    "path": str(file.get("filename", "")),
                    "status": status,
                }
            )

        files_truncated = len(files) > max_files
        visible_files = tuple(files[:max_files])
        return DiffSummaryResult(
            baseline_commit=baseline,
            tracked_head_commit=tracked,
            total_changed_files=len(files),
            added_count=counts["added"],
            modified_count=counts["modified"],
            removed_count=counts["removed"],
            renamed_count=counts["renamed"],
            files_truncated=files_truncated,
            changed_files=visible_files,
        )

