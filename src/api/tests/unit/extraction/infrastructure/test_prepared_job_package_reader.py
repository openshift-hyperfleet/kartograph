"""Unit tests for SqlPreparedJobPackageReader."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from extraction.infrastructure.prepared_job_package_reader import SqlPreparedJobPackageReader
from shared_kernel.job_package.builder import JobPackageBuilder
from shared_kernel.job_package.value_objects import (
    AdapterCheckpoint,
    ChangeOperation,
    ChangesetEntry,
    JobPackageId,
    SyncMode,
)


def _build_package(work_dir: Path, package_id: str, *, with_file: bool) -> None:
    builder = JobPackageBuilder(
        data_source_id="ds-1",
        knowledge_graph_id="kg-1",
        sync_mode=SyncMode.FULL_REFRESH,
        package_id=JobPackageId(value=package_id),
    )
    if with_file:
        content = b"print('hello')\n"
        ref = builder.add_content(content)
        builder.add_changeset_entry(
            ChangesetEntry(
                operation=ChangeOperation.ADD,
                id="file-1",
                type="io.kartograph.change.file",
                path="pkg/api/example.go",
                content_ref=ref,
                content_type="text/plain",
                metadata={},
            )
        )
    builder.set_checkpoint(AdapterCheckpoint(schema_version="1.0.0", data={"commit_sha": "abc"}))
    builder.build(work_dir)


def _mock_session(rows: list) -> AsyncMock:
    result = MagicMock()
    result.fetchall.return_value = rows
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)
    return session


@pytest.mark.asyncio
class TestSqlPreparedJobPackageReader:
    async def test_prefers_latest_non_empty_job_package_per_data_source(
        self, tmp_path: Path
    ) -> None:
        empty_id = "01JEMPTY000000000000000000"
        full_id = "01JFULL0000000000000000000"
        _build_package(tmp_path, empty_id, with_file=False)
        _build_package(tmp_path, full_id, with_file=True)

        rows = [
            MagicMock(
                data_source_id="ds-1",
                data_source_name="Hyperfleet API",
                job_package_id=empty_id,
                occurred_at="2026-05-31T12:00:00Z",
            ),
            MagicMock(
                data_source_id="ds-1",
                data_source_name="Hyperfleet API",
                job_package_id=full_id,
                occurred_at="2026-05-31T11:00:00Z",
            ),
        ]
        reader = SqlPreparedJobPackageReader(
            session=_mock_session(rows),
            job_package_work_dir=tmp_path,
        )

        sources = await reader.list_latest_for_knowledge_graph(
            knowledge_graph_id="kg-1",
        )

        assert len(sources) == 1
        assert sources[0].package_id == full_id
        assert sources[0].data_source_name == "Hyperfleet API"
        assert sources[0].repository_folder == "hyperfleet-api"

    async def test_skips_data_source_when_all_packages_are_empty(self, tmp_path: Path) -> None:
        empty_id = "01JEMPTY000000000000000000"
        _build_package(tmp_path, empty_id, with_file=False)
        rows = [
            MagicMock(
                data_source_id="ds-1",
                data_source_name="Hyperfleet API",
                job_package_id=empty_id,
                occurred_at="2026-05-31T12:00:00Z",
            ),
        ]
        reader = SqlPreparedJobPackageReader(
            session=_mock_session(rows),
            job_package_work_dir=tmp_path,
        )

        sources = await reader.list_latest_for_knowledge_graph(
            knowledge_graph_id="kg-1",
        )

        assert sources == ()
