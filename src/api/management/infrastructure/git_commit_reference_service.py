"""Resolve remote commit references for Git-backed data sources."""

from __future__ import annotations

from urllib.parse import urlparse

import httpx

from management.domain.aggregates import DataSource
from management.infrastructure.github_source_auth import (
    github_api_headers,
    load_github_credentials,
    raise_for_github_http_error,
    require_github_token,
)
from shared_kernel.credential_reader import ICredentialReader
from shared_kernel.datasource_types import DataSourceAdapterType


class GitCommitReferenceService:
    """Fetch tracked branch HEAD commit metadata from remote Git providers."""

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
    def _parse_github_connection_config(
        config: dict[str, str],
    ) -> tuple[str, str, str]:
        """Parse GitHub connection settings into owner/repo/branch."""
        if "repo_url" in config:
            parsed = urlparse(config["repo_url"])
            path_parts = [part for part in parsed.path.split("/") if part]
            if len(path_parts) < 2:
                raise ValueError("repo_url must include owner and repo")
            owner = path_parts[0]
            repo = path_parts[1].removesuffix(".git")
            branch = config.get("branch", "main")
            if len(path_parts) >= 4 and path_parts[2] == "tree":
                branch = "/".join(path_parts[3:])
            return owner, repo, branch

        if "owner" in config and "repo" in config:
            return config["owner"], config["repo"], config.get("branch", "main")

        raise ValueError(
            "connection_config must include either 'repo_url' or 'owner'+'repo' keys"
        )

    async def resolve_tracked_head_commit(self, data_source: DataSource) -> str | None:
        """Resolve tracked branch HEAD commit for GitHub data sources."""
        if data_source.adapter_type != DataSourceAdapterType.GITHUB:
            return None

        owner, repo, branch = self._parse_github_connection_config(
            data_source.connection_config
        )

        credentials = await load_github_credentials(
            credential_reader=self._credential_reader,
            data_source=data_source,
        )
        require_github_token(
            data_source=data_source,
            credentials=credentials,
            owner=owner,
            repo=repo,
        )
        headers = github_api_headers(credentials)

        url = f"https://api.github.com/repos/{owner}/{repo}/branches/{branch}"
        client = self._http_client or httpx.AsyncClient(timeout=20.0)
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise_for_github_http_error(
                exc=exc,
                data_source=data_source,
                owner=owner,
                repo=repo,
                operation="branch lookup",
            )
        finally:
            if self._http_client is None:
                await client.aclose()

        sha = payload.get("commit", {}).get("sha")
        return str(sha) if sha else None
