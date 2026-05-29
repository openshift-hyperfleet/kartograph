"""Unit tests for sticky session workdir materialization."""

from __future__ import annotations

from pathlib import Path

from shared_kernel.job_package.builder import JobPackageBuilder
from shared_kernel.job_package.value_objects import (
    AdapterCheckpoint,
    ChangeOperation,
    ChangesetEntry,
    ContentRef,
    JobPackageId,
    SyncMode,
)

from extraction.infrastructure.sticky_session_workdir_materializer import (
    StickySessionWorkdirMaterializer,
)


def _build_package(work_dir: Path, package_id: str) -> None:
    content_bytes = b"# hello\n"
    content_ref = ContentRef.from_bytes(content_bytes)
    builder = JobPackageBuilder(
        data_source_id="ds-1",
        knowledge_graph_id="kg-1",
        sync_mode=SyncMode.FULL_REFRESH,
        package_id=JobPackageId(value=package_id),
    )
    ref = builder.add_content(content_bytes)
    builder.add_changeset_entry(
        ChangesetEntry(
            operation=ChangeOperation.ADD,
            id="file-1",
            type="io.kartograph.change.file",
            path="README.md",
            content_ref=ref,
            content_type="text/markdown",
            metadata={},
        )
    )
    builder.set_checkpoint(AdapterCheckpoint(schema_version="1.0.0", data={}))
    builder.build(work_dir)


def test_materializer_extracts_job_package_into_session_workspace(tmp_path: Path) -> None:
    package_id = "01JTESTPACK0000000000000000"
    _build_package(tmp_path, package_id)
    materializer = StickySessionWorkdirMaterializer(job_package_work_dir=tmp_path)

    session_root = materializer.prepare(
        session_id="session-1",
        knowledge_graph_id="kg-1",
        job_package_ids=(package_id,),
    )

    repo_file = session_root / "repository-files" / package_id / "README.md"
    assert repo_file.read_text(encoding="utf-8") == "# hello\n"
