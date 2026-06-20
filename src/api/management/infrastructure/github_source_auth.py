"""Shared GitHub credential and request header helpers for Management services."""

from __future__ import annotations

import httpx

from management.domain.aggregates import DataSource
from shared_kernel.credential_reader import ICredentialReader

_GITHUB_USER_AGENT = "Kartograph-GitHub/1.0"


async def load_github_credentials(
    *,
    credential_reader: ICredentialReader,
    data_source: DataSource,
) -> dict[str, str]:
    """Load decrypted GitHub credentials scoped to the data source tenant."""
    if not data_source.credentials_path:
        return {}
    try:
        return await credential_reader.retrieve(
            path=data_source.credentials_path,
            tenant_id=data_source.tenant_id,
        )
    except KeyError as exc:
        raise ValueError(
            f"GitHub credentials not found for data source {data_source.name!r}. "
            "Re-save the repository access token on the data source and try again."
        ) from exc


def github_api_headers(credentials: dict[str, str]) -> dict[str, str]:
    """Build standard GitHub REST API headers."""
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": _GITHUB_USER_AGENT,
    }
    token = credentials.get("token") or credentials.get("access_token")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def require_github_token(
    *,
    data_source: DataSource,
    credentials: dict[str, str],
    owner: str,
    repo: str,
) -> None:
    """Fail fast when a private GitHub call would run without credentials."""
    if credentials.get("token") or credentials.get("access_token"):
        return
    if data_source.credentials_path:
        raise ValueError(
            f"GitHub credentials for {data_source.name!r} ({owner}/{repo}) are empty. "
            "Update the data source access token and try again."
        )
    raise ValueError(
        f"GitHub data source {data_source.name!r} ({owner}/{repo}) has no access token "
        "configured. Add credentials before running maintenance."
    )


def raise_for_github_http_error(
    *,
    exc: httpx.HTTPStatusError,
    data_source: DataSource,
    owner: str,
    repo: str,
    operation: str,
) -> None:
    """Translate GitHub HTTP failures into actionable maintenance errors."""
    status = exc.response.status_code
    if status in {401, 403}:
        raise ValueError(
            f"GitHub {operation} failed for {data_source.name!r} ({owner}/{repo}): "
            "access was denied. Update the data source access token and ensure it has "
            "read access to this repository."
        ) from exc
    if status == 404:
        raise ValueError(
            f"GitHub {operation} failed for {data_source.name!r} ({owner}/{repo}): "
            "repository or commit range was not found."
        ) from exc
    raise ValueError(
        f"GitHub {operation} failed for {data_source.name!r} ({owner}/{repo}): {exc}"
    ) from exc
