"""Unit tests for filesystem extraction runtime context builder."""

from __future__ import annotations

from pathlib import Path

import pytest

from extraction.infrastructure.runtime_context_builder import (
    FilesystemExtractionRuntimeContextBuilder,
)
from shared_kernel.job_package.builder import JobPackageBuilder
from shared_kernel.job_package.value_objects import (
    AdapterCheckpoint,
    ChangeOperation,
    ChangesetEntry,
    ContentRef,
    SyncMode,
)


def _build_job_package(archive_dir: Path) -> str:
    content_bytes = b"print('hello runtime context')\n"
    content_ref = ContentRef.from_bytes(content_bytes)
    changeset_entry = ChangesetEntry(
        operation=ChangeOperation.ADD,
        id="file-1",
        type="io.kartograph.change.file",
        path="src/main.py",
        content_ref=content_ref,
        content_type="text/x-python",
        metadata={},
    )
    builder = JobPackageBuilder(
        data_source_id="ds-123",
        knowledge_graph_id="kg-123",
        sync_mode=SyncMode.FULL_REFRESH,
    )
    ref = builder.add_content(content_bytes)
    builder.add_changeset_entry(
        ChangesetEntry(
            operation=ChangeOperation.ADD,
            id=changeset_entry.id,
            type=changeset_entry.type,
            path=changeset_entry.path,
            content_ref=ref,
            content_type=changeset_entry.content_type,
            metadata=changeset_entry.metadata,
        )
    )
    builder.set_checkpoint(AdapterCheckpoint(schema_version="1.0.0", data={}))
    archive_path = builder.build(archive_dir)
    return archive_path.stem.removeprefix("job-package-")


@pytest.mark.asyncio
async def test_build_materializes_ingestion_context_and_repository_files(
    tmp_path: Path,
):
    work_dir = tmp_path / "work"
    work_dir.mkdir(parents=True, exist_ok=True)
    package_id = _build_job_package(work_dir)

    builder = FilesystemExtractionRuntimeContextBuilder(work_dir=work_dir)
    runtime = builder.build(sync_run_id="run-123", job_package_id=package_id)

    assert Path(runtime.ingestion_context_dir).exists()
    assert Path(runtime.repository_files_dir, "src/main.py").exists()
    assert Path(runtime.repository_files_dir, "src/main.py").read_text() == (
        "print('hello runtime context')\n"
    )
