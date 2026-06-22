"""Fetch GitHub file content at a historical commit for maintenance jobs."""

from __future__ import annotations

import base64
import json
from urllib.parse import quote, urlparse

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.settings import get_management_settings


class MaintenanceBaselineContentFetcher:
    """Load baseline repository file bytes from GitHub at a specific ref."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        tenant_id: str,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._session = session
        self._tenant_id = tenant_id
        self._http_client = http_client
        self._github_context_cache: dict[str, tuple[str, str, dict[str, str]]] = {}

    async def fetch_file(
        self,
        *,
        data_source_id: str,
        path: str,
        ref: str,
    ) -> bytes | None:
        owner, repo, headers = await self._github_context_for_source(data_source_id)
        encoded_path = quote(path, safe="")
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{encoded_path}?ref={quote(ref, safe='')}"
        client = self._http_client or httpx.AsyncClient(timeout=30.0)
        try:
            response = await client.get(url, headers=headers)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            payload = response.json()
        finally:
            if self._http_client is None:
                await client.aclose()

        if isinstance(payload, list):
            return None
        content = payload.get("content")
        encoding = payload.get("encoding")
        if not isinstance(content, str) or encoding != "base64":
            return None
        normalized = content.replace("\n", "")
        try:
            return base64.b64decode(normalized, validate=False)
        except (ValueError, TypeError):
            return None

    async def _github_context_for_source(
        self,
        data_source_id: str,
    ) -> tuple[str, str, dict[str, str]]:
        cached = self._github_context_cache.get(data_source_id)
        if cached is not None:
            return cached

        result = await self._session.execute(
            text(
                """
                SELECT adapter_type, connection_config, credentials_path, tenant_id
                FROM data_sources
                WHERE id = :data_source_id AND tenant_id = :tenant_id
                """
            ),
            {"data_source_id": data_source_id, "tenant_id": self._tenant_id},
        )
        row = result.mappings().first()
        if row is None:
            raise ValueError(f"Data source not found: {data_source_id}")
        if str(row["adapter_type"]) != "github":
            raise ValueError(f"Baseline fetch supports GitHub sources only: {data_source_id}")

        connection_config = row["connection_config"]
        if isinstance(connection_config, str):
            connection_config = json.loads(connection_config)
        owner, repo = _parse_github_connection_config(dict(connection_config or {}))
        headers = await self._build_github_headers(
            credentials_path=row.get("credentials_path"),
            tenant_id=str(row["tenant_id"] or self._tenant_id),
        )
        context = (owner, repo, headers)
        self._github_context_cache[data_source_id] = context
        return context

    async def _build_github_headers(
        self,
        *,
        credentials_path: str | None,
        tenant_id: str,
    ) -> dict[str, str]:
        from management.infrastructure.github_source_auth import github_api_headers

        if not credentials_path or not tenant_id.strip():
            return github_api_headers({})

        from management.infrastructure.repositories.fernet_secret_store import FernetSecretStore

        mgmt_settings = get_management_settings()
        encryption_keys = [
            key.strip()
            for key in mgmt_settings.encryption_key.get_secret_value().split(",")
            if key.strip()
        ]
        if not encryption_keys:
            return github_api_headers({})

        credential_reader = FernetSecretStore(
            session=self._session,
            encryption_keys=encryption_keys,
        )
        try:
            credentials = await credential_reader.retrieve(
                path=str(credentials_path),
                tenant_id=tenant_id,
            )
        except KeyError:
            credentials = {}
        return github_api_headers(credentials)


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
