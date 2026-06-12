"""Unit tests for JobPackage archive hydration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from infrastructure.job_packages.archive_hydrator import JobPackageArchiveHydrator
from shared_kernel.job_package.builder import JobPackageBuilder
from shared_kernel.job_package.value_objects import (
    AdapterCheckpoint,
    ChangeOperation,
    ChangesetEntry,
    JobPackageId,
    SyncMode,
)


def _write_package(work_dir: Path, package_id: str) -> None:
    builder = JobPackageBuilder(
        data_source_id="ds-1",
        knowledge_graph_id="kg-1",
        sync_mode=SyncMode.FULL_REFRESH,
        package_id=JobPackageId(value=package_id),
    )
    ref = builder.add_content(b"print('hello')\n")
    builder.add_changeset_entry(
        ChangesetEntry(
            operation=ChangeOperation.ADD,
            id="file-1",
            type="io.kartograph.change.file",
            path="pkg/example.go",
            content_ref=ref,
            content_type="text/plain",
            metadata={},
        )
    )
    builder.set_checkpoint(AdapterCheckpoint(schema_version="1.0.0", data={"commit_sha": "abc"}))
    builder.build(work_dir)


def _mock_session(*, data_sources: list[dict]) -> AsyncMock:
    ds_result = MagicMock()
    ds_result.fetchall.return_value = [MagicMock(**row) for row in data_sources]
    session = AsyncMock()
    session.execute = AsyncMock(return_value=ds_result)
    session.commit = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_hydrator_skips_when_archive_exists(tmp_path: Path) -> None:
    package_id = "01JFULL0000000000000000000"
    _write_package(tmp_path, package_id)
    session = _mock_session(
        data_sources=[
            {
                "id": "ds-1",
                "name": "hyperfleet-e2e",
                "adapter_type": "github",
                "connection_config": {},
                "credentials_path": None,
                "clone_head_commit": "abc",
                "last_prepared_commit": "abc",
            }
        ]
    )
    hydrator = JobPackageArchiveHydrator(
        session=session,
        job_package_work_dir=tmp_path,
    )
    with patch.object(
        hydrator._archive_reader,
        "latest_job_package_id_for_data_source",
        AsyncMock(return_value=package_id),
    ):
        result = await hydrator.ensure_for_knowledge_graph(
            knowledge_graph_id="kg-1",
            tenant_id="tenant-1",
        )

    assert result.hydrated_count == 0
    assert result.skipped_count == 1
    assert result.errors == ()


@pytest.mark.asyncio
async def test_hydrator_runs_ingestion_when_archive_missing(tmp_path: Path) -> None:
    session = _mock_session(
        data_sources=[
            {
                "id": "ds-1",
                "name": "hyperfleet-e2e",
                "adapter_type": "github",
                "connection_config": {"owner": "org", "repo": "repo"},
                "credentials_path": None,
                "clone_head_commit": "abc",
                "last_prepared_commit": "abc",
            }
        ]
    )
    hydrator = JobPackageArchiveHydrator(
        session=session,
        job_package_work_dir=tmp_path,
    )
    ingestion_result = MagicMock(
        job_package_id=JobPackageId(value="01JHYDRATED000000000000000"),
        entry_count=2,
        branch_file_count=10,
        prepared_commit_sha="def",
    )
    with patch.object(
        hydrator._archive_reader,
        "latest_job_package_id_for_data_source",
        AsyncMock(return_value=None),
    ), patch(
        "ingestion.application.services.ingestion_service.IngestionService"
    ) as ingestion_cls, patch(
        "infrastructure.outbox.repository.OutboxRepository"
    ) as outbox_cls:
        ingestion_service = AsyncMock()
        ingestion_service.run = AsyncMock(return_value=ingestion_result)
        ingestion_cls.return_value = ingestion_service
        outbox = AsyncMock()
        outbox.append = AsyncMock()
        outbox_cls.return_value = outbox

        result = await hydrator.ensure_for_knowledge_graph(
            knowledge_graph_id="kg-1",
            tenant_id="tenant-1",
        )

    assert result.hydrated_count == 1
    assert result.skipped_count == 0
    ingestion_service.run.assert_awaited_once()
    outbox.append.assert_awaited_once()
