"""Unit tests for GitCommitReferenceService."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from management.domain.aggregates import DataSource
from management.domain.value_objects import DataSourceId, Schedule, ScheduleType
from management.infrastructure.git_commit_reference_service import (
    GitCommitReferenceService,
)
from shared_kernel.datasource_types import DataSourceAdapterType


class _FakeCredentialReader:
    def __init__(self, credentials: dict[str, str] | None = None) -> None:
        self._credentials = credentials or {}

    async def retrieve(self, path: str, tenant_id: str) -> dict[str, str]:
        return dict(self._credentials)


def _make_data_source(
    *,
    adapter_type: DataSourceAdapterType = DataSourceAdapterType.GITHUB,
    connection_config: dict[str, str] | None = None,
    credentials_path: str | None = None,
) -> DataSource:
    now = datetime.now(UTC)
    return DataSource(
        id=DataSourceId(value="01JTESTCOMMITREFSERVICE0000"),
        knowledge_graph_id="01JTESTCOMMITREFKG0000000",
        tenant_id="tenant-001",
        name="GitHub DS",
        adapter_type=adapter_type,
        connection_config=connection_config
        or {"owner": "org", "repo": "repo", "branch": "main"},
        credentials_path=credentials_path,
        schedule=Schedule(schedule_type=ScheduleType.MANUAL),
        last_sync_at=None,
        created_at=now,
        updated_at=now,
    )


def test_parse_github_config_rejects_invalid_repo_url() -> None:
    """Malformed GitHub repo URL should raise a clear error."""
    with pytest.raises(ValueError, match="owner and repo"):
        GitCommitReferenceService._parse_github_connection_config(
            {"repo_url": "https://github.com/owner-only"}
        )


@pytest.mark.asyncio
async def test_resolve_tracked_head_uses_branches_endpoint_with_token() -> None:
    """Service should call GitHub branches API with PAT when available."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://api.github.com/repos/org/repo/branches/main"
        assert request.headers.get("Authorization") == "Bearer secret-token"
        return httpx.Response(
            status_code=200,
            json={"commit": {"sha": "abc123"}},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    service = GitCommitReferenceService(
        credential_reader=_FakeCredentialReader({"access_token": "secret-token"}),
        tenant_id="tenant-001",
        http_client=client,
    )
    ds = _make_data_source(credentials_path="datasource/ds-1/credentials")

    tracked = await service.resolve_tracked_head_commit(ds)
    await client.aclose()

    assert tracked == "abc123"


@pytest.mark.asyncio
async def test_resolve_tracked_head_parses_repo_url_branch() -> None:
    """repo_url tree syntax should map to owner/repo/branch correctly."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert (
            str(request.url)
            == "https://api.github.com/repos/openshift-hyperfleet/kartograph/branches/feature/test"
        )
        return httpx.Response(status_code=200, json={"commit": {"sha": "head987"}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    ds = _make_data_source(
        connection_config={
            "repo_url": "https://github.com/openshift-hyperfleet/kartograph/tree/feature/test"
        },
        credentials_path="datasource/ds-1/credentials",
    )
    service = GitCommitReferenceService(
        credential_reader=_FakeCredentialReader({"access_token": "secret-token"}),
        tenant_id="tenant-001",
        http_client=client,
    )

    tracked = await service.resolve_tracked_head_commit(ds)
    await client.aclose()

    assert tracked == "head987"
