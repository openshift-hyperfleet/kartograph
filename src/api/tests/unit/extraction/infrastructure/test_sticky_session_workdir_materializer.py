"""Unit tests for sticky session workdir materialization."""

from __future__ import annotations

import json
from pathlib import Path

from extraction.domain.prepared_job_package_source import PreparedJobPackageSource
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


def _source(
    *,
    package_id: str,
    data_source_id: str = "ds-1",
    data_source_name: str = "hyperfleet-api",
) -> PreparedJobPackageSource:
    return PreparedJobPackageSource(
        package_id=package_id,
        data_source_id=data_source_id,
        data_source_name=data_source_name,
        repository_folder=data_source_name.lower().replace(" ", "-"),
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


def test_materializer_extracts_job_package_into_session_workspace(tmp_path: Path) -> None:
    package_id = "01JTESTPACK0000000000000000"
    _build_package(tmp_path, package_id, with_file=True)
    materializer = StickySessionWorkdirMaterializer(job_package_work_dir=tmp_path)

    session_root = materializer.prepare(
        session_id="session-1",
        knowledge_graph_id="kg-1",
        job_packages=(_source(package_id=package_id),),
    )

    repo_file = session_root / "repository-files" / "hyperfleet-api" / "pkg/api/example.go"
    assert repo_file.read_text(encoding="utf-8") == "print('hello')\n"


def test_materializer_does_not_materialize_when_job_packages_empty(tmp_path: Path) -> None:
    package_id = "01JTESTPACK0000000000000001"
    _build_package(tmp_path, package_id, with_file=True)
    materializer = StickySessionWorkdirMaterializer(job_package_work_dir=tmp_path)

    session_root = materializer.prepare(
        session_id="session-2",
        knowledge_graph_id="kg-1",
        job_packages=(),
    )

    assert not any((session_root / "repository-files").iterdir())


def test_materializer_skips_empty_job_packages(tmp_path: Path) -> None:
    empty_id = "01JEMPTY000000000000000000"
    full_id = "01JTESTPACK0000000000000003"
    _build_package(tmp_path, empty_id, with_file=False)
    _build_package(tmp_path, full_id, with_file=True)
    materializer = StickySessionWorkdirMaterializer(job_package_work_dir=tmp_path)

    session_root = materializer.prepare(
        session_id="session-empty",
        knowledge_graph_id="kg-1",
        job_packages=(
            _source(package_id=empty_id, data_source_name="empty-source"),
            _source(package_id=full_id, data_source_name="hyperfleet-api"),
        ),
    )

    assert not (session_root / "repository-files" / "empty-source").exists()
    assert (session_root / "repository-files" / "hyperfleet-api" / "pkg/api/example.go").exists()


def test_materializer_writes_sources_index(tmp_path: Path) -> None:
    package_id = "01JTESTPACK0000000000000004"
    _build_package(tmp_path, package_id, with_file=True)
    materializer = StickySessionWorkdirMaterializer(job_package_work_dir=tmp_path)

    session_root = materializer.prepare(
        session_id="session-index",
        knowledge_graph_id="kg-1",
        job_packages=(_source(package_id=package_id, data_source_name="Hyperfleet E2E"),),
    )

    index_path = session_root / "sources-index.json"
    assert index_path.is_file()
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    assert payload["knowledge_graph_id"] == "kg-1"
    assert len(payload["sources"]) == 1
    source = payload["sources"][0]
    assert source["job_package_id"] == package_id
    assert source["data_source_name"] == "Hyperfleet E2E"
    assert source["repository_folder"] == "hyperfleet-e2e"
    assert source["entry_count"] == 1
    assert source["sample_paths"] == ["pkg/api/example.go"]
    assert source["repository_root"] == "repository-files/hyperfleet-e2e"


def test_materializer_refresh_preserves_session_root_directory(tmp_path: Path) -> None:
    package_id = "01JTESTPACK0000000000000002"
    _build_package(tmp_path, package_id, with_file=True)
    materializer = StickySessionWorkdirMaterializer(job_package_work_dir=tmp_path)
    packages = (_source(package_id=package_id),)

    first_root = materializer.prepare(
        session_id="session-3",
        knowledge_graph_id="kg-1",
        job_packages=packages,
    )
    second_root = materializer.prepare(
        session_id="session-3",
        knowledge_graph_id="kg-1",
        job_packages=packages,
    )

    assert first_root == second_root
    assert (second_root / "repository-files" / "hyperfleet-api" / "pkg/api/example.go").exists()
