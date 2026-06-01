"""Unit tests for sticky session workdir materialization."""

from __future__ import annotations

import json
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


def test_materializer_does_not_discover_archives_when_package_ids_empty(tmp_path: Path) -> None:
    package_id = "01JTESTPACK0000000000000001"
    _build_package(tmp_path, package_id)
    materializer = StickySessionWorkdirMaterializer(job_package_work_dir=tmp_path)

    session_root = materializer.prepare(
        session_id="session-2",
        knowledge_graph_id="kg-1",
        job_package_ids=(),
    )

    assert not any((session_root / "repository-files").iterdir())


def _build_empty_package(work_dir: Path, package_id: str) -> None:
    builder = JobPackageBuilder(
        data_source_id="ds-empty",
        knowledge_graph_id="kg-1",
        sync_mode=SyncMode.INCREMENTAL,
        package_id=JobPackageId(value=package_id),
    )
    builder.set_checkpoint(AdapterCheckpoint(schema_version="1.0.0", data={"commit_sha": "abc"}))
    builder.build(work_dir)


def test_materializer_skips_empty_job_packages(tmp_path: Path) -> None:
    empty_id = "01JEMPTY000000000000000000"
    full_id = "01JTESTPACK0000000000000003"
    _build_empty_package(tmp_path, empty_id)
    _build_package(tmp_path, full_id)
    materializer = StickySessionWorkdirMaterializer(job_package_work_dir=tmp_path)

    session_root = materializer.prepare(
        session_id="session-empty",
        knowledge_graph_id="kg-1",
        job_package_ids=(empty_id, full_id),
    )

    assert not (session_root / "repository-files" / empty_id).exists()
    assert (session_root / "repository-files" / full_id / "README.md").exists()


def test_materializer_writes_sources_index(tmp_path: Path) -> None:
    package_id = "01JTESTPACK0000000000000004"
    _build_package(tmp_path, package_id)
    materializer = StickySessionWorkdirMaterializer(job_package_work_dir=tmp_path)

    session_root = materializer.prepare(
        session_id="session-index",
        knowledge_graph_id="kg-1",
        job_package_ids=(package_id,),
    )

    index_path = session_root / "sources-index.json"
    assert index_path.is_file()
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    assert payload["knowledge_graph_id"] == "kg-1"
    assert len(payload["sources"]) == 1
    source = payload["sources"][0]
    assert source["job_package_id"] == package_id
    assert source["entry_count"] == 1
    assert source["sample_paths"] == ["README.md"]


def test_materializer_refresh_preserves_session_root_directory(tmp_path: Path) -> None:
    package_id = "01JTESTPACK0000000000000002"
    _build_package(tmp_path, package_id)
    materializer = StickySessionWorkdirMaterializer(job_package_work_dir=tmp_path)

    first_root = materializer.prepare(
        session_id="session-3",
        knowledge_graph_id="kg-1",
        job_package_ids=(package_id,),
    )
    second_root = materializer.prepare(
        session_id="session-3",
        knowledge_graph_id="kg-1",
        job_package_ids=(package_id,),
    )

    assert first_root == second_root
    assert (second_root / "repository-files" / package_id / "README.md").exists()
