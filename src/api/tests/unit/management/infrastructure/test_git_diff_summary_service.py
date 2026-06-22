"""Unit tests for GitDiffSummaryService."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from management.domain.aggregates import DataSource
from management.domain.value_objects import DataSourceId, Schedule, ScheduleType
from management.infrastructure.git_diff_summary_service import GitDiffSummaryService
from shared_kernel.datasource_types import DataSourceAdapterType


class _FakeCredentialReader:
    def __init__(
        self,
        credentials: dict[str, str] | None = None,
        *,
        missing: bool = False,
    ) -> None:
        self._credentials = credentials or {}
        self._missing = missing

    async def retrieve(self, path: str, tenant_id: str) -> dict[str, str]:
        if self._missing:
            raise KeyError(path)
        return dict(self._credentials)


def _make_data_source(
    *,
    baseline: str | None = "aaaa",
    tracked: str | None = "bbbb",
) -> DataSource:
    now = datetime.now(UTC)
    return DataSource(
        id=DataSourceId(value="01JTESTDIFFSUMMARYSOURCE000"),
        knowledge_graph_id="01JTESTDIFFSUMMARYKG0000000",
        tenant_id="tenant-001",
        name="GitHub DS",
        adapter_type=DataSourceAdapterType.GITHUB,
        connection_config={"owner": "org", "repo": "repo", "branch": "main"},
        credentials_path=None,
        schedule=Schedule(schedule_type=ScheduleType.MANUAL),
        last_sync_at=None,
        created_at=now,
        updated_at=now,
        last_extraction_baseline_commit=baseline,
        tracked_branch_head_commit=tracked,
    )


@pytest.mark.asyncio
async def test_returns_empty_summary_when_commits_missing():
    """Missing baseline/tracked refs should produce an empty summary."""
    service = GitDiffSummaryService(
        credential_reader=_FakeCredentialReader(),
        tenant_id="tenant-001",
    )
    ds = _make_data_source(baseline=None, tracked="bbbb")

    result = await service.build_summary(data_source=ds, max_files=50)

    assert result.total_changed_files == 0
    assert result.changed_files == ()


@pytest.mark.asyncio
async def test_raises_when_github_credentials_missing():
    service = GitDiffSummaryService(
        credential_reader=_FakeCredentialReader(missing=True),
        tenant_id="tenant-001",
    )
    ds = _make_data_source()
    ds = DataSource(
        id=ds.id,
        knowledge_graph_id=ds.knowledge_graph_id,
        tenant_id=ds.tenant_id,
        name=ds.name,
        adapter_type=ds.adapter_type,
        connection_config=ds.connection_config,
        credentials_path="datasource/test/credentials",
        schedule=ds.schedule,
        last_sync_at=ds.last_sync_at,
        created_at=ds.created_at,
        updated_at=ds.updated_at,
        last_extraction_baseline_commit=ds.last_extraction_baseline_commit,
        tracked_branch_head_commit=ds.tracked_branch_head_commit,
    )

    with pytest.raises(ValueError, match="credentials not found"):
        await service.build_summary(data_source=ds, max_files=50)


@pytest.mark.asyncio
async def test_raises_when_github_rejects_credentials():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=401, json={"message": "Bad credentials"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    service = GitDiffSummaryService(
        credential_reader=_FakeCredentialReader({"access_token": "ghp_invalid"}),
        tenant_id="tenant-001",
        http_client=client,
    )
    ds = _make_data_source()
    ds = DataSource(
        id=ds.id,
        knowledge_graph_id=ds.knowledge_graph_id,
        tenant_id=ds.tenant_id,
        name=ds.name,
        adapter_type=ds.adapter_type,
        connection_config=ds.connection_config,
        credentials_path="datasource/test/credentials",
        schedule=ds.schedule,
        last_sync_at=ds.last_sync_at,
        created_at=ds.created_at,
        updated_at=ds.updated_at,
        last_extraction_baseline_commit=ds.last_extraction_baseline_commit,
        tracked_branch_head_commit=ds.tracked_branch_head_commit,
    )

    with pytest.raises(ValueError, match="access was denied"):
        await service.build_summary(data_source=ds, max_files=50)
    await client.aclose()


@pytest.mark.asyncio
async def test_truncates_changed_files_when_max_exceeded():
    """Changed-file list should truncate safely for large diffs."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert "compare" in str(request.url)
        return httpx.Response(
            status_code=200,
            json={
                "files": [
                    {"filename": "a.py", "status": "added"},
                    {"filename": "b.py", "status": "modified"},
                    {"filename": "c.py", "status": "removed"},
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    ds = _make_data_source()
    ds = DataSource(
        id=ds.id,
        knowledge_graph_id=ds.knowledge_graph_id,
        tenant_id=ds.tenant_id,
        name=ds.name,
        adapter_type=ds.adapter_type,
        connection_config=ds.connection_config,
        credentials_path="datasource/test/credentials",
        schedule=ds.schedule,
        last_sync_at=ds.last_sync_at,
        created_at=ds.created_at,
        updated_at=ds.updated_at,
        last_extraction_baseline_commit=ds.last_extraction_baseline_commit,
        tracked_branch_head_commit=ds.tracked_branch_head_commit,
    )
    service = GitDiffSummaryService(
        credential_reader=_FakeCredentialReader({"access_token": "ghp_test"}),
        tenant_id="tenant-001",
        http_client=client,
    )

    result = await service.build_summary(data_source=ds, max_files=2)
    await client.aclose()

    assert result.total_changed_files == 3
    assert result.files_truncated is True
    assert len(result.changed_files) == 2
    assert result.added_count == 1
    assert result.modified_count == 1
    assert result.removed_count == 1
