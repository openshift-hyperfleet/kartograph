"""Unit tests for maintenance repository-files materialization."""

from __future__ import annotations

from pathlib import Path

import pytest

from extraction.domain.extraction_job import ExtractionTargetFile
from extraction.domain.prepared_job_package_source import PreparedJobPackageSource
from extraction.infrastructure.maintenance_repository_files import (
    materialize_maintenance_target_files,
    write_maintenance_sources_index,
)
from extraction.infrastructure.extraction_job_repository_files import (
    RepositoryFilesMaterializationResult,
)
from shared_kernel.job_package.builder import JobPackageBuilder
from shared_kernel.job_package.value_objects import (
    AdapterCheckpoint,
    ChangeOperation,
    ChangesetEntry,
    JobPackageId,
    SyncMode,
)


def _source(
    *, package_id: str, folder: str = "hyperfleet-api"
) -> PreparedJobPackageSource:
    return PreparedJobPackageSource(
        package_id=package_id,
        data_source_id="ds-1",
        data_source_name="hyperfleet-api",
        repository_folder=folder,
    )


def _build_package(work_dir: Path, package_id: str, path: str, content: bytes) -> None:
    builder = JobPackageBuilder(
        data_source_id="ds-1",
        knowledge_graph_id="kg-1",
        sync_mode=SyncMode.FULL_REFRESH,
        package_id=JobPackageId(value=package_id),
    )
    ref = builder.add_content(content)
    builder.add_changeset_entry(
        ChangesetEntry(
            operation=ChangeOperation.ADD,
            id="file-1",
            type="io.kartograph.change.file",
            path=path,
            content_ref=ref,
            content_type="text/plain",
            metadata={},
        )
    )
    builder.set_checkpoint(
        AdapterCheckpoint(schema_version="1.0.0", data={"commit_sha": "0b64088c"})
    )
    builder.build(work_dir)


def _target_file(
    *,
    path: str = "src/foo.go",
    status: str = "modified",
    patch: str | None = "@@ -1 +1 @@\n-old\n+new",
) -> ExtractionTargetFile:
    return ExtractionTargetFile(
        path=path,
        repository_folder="hyperfleet-api",
        package_id="01JTESTPACK0000000000000000",
        baseline_commit="defc3afd",
        head_commit="0b64088c",
        change_status=status,
        patch=patch,
        data_source_id="ds-1",
    )


@pytest.mark.asyncio
async def test_materialize_maintenance_target_files_writes_commit_scoped_paths(
    tmp_path: Path,
) -> None:
    package_id = "01JTESTPACK0000000000000000"
    _build_package(tmp_path, package_id, "src/foo.go", b"package foo\n")
    repo_dir = tmp_path / "repository-files"

    async def fetch_baseline(_data_source_id: str, path: str, ref: str) -> bytes | None:
        assert path == "src/foo.go"
        assert ref == "defc3afd"
        return b"package foo_old\n"

    result = await materialize_maintenance_target_files(
        repository_files_dir=repo_dir,
        job_package_work_dir=tmp_path,
        target_files=(_target_file(),),
        packages_by_id={package_id: _source(package_id=package_id)},
        fetch_baseline_content=fetch_baseline,
    )

    head_path = repo_dir / "0b64088c" / "hyperfleet-api" / "src/foo.go"
    baseline_path = repo_dir / "defc3afd" / "hyperfleet-api" / "src/foo.go"
    diff_path = (
        repo_dir
        / "diffs"
        / "defc3afd..0b64088c"
        / "hyperfleet-api"
        / "src/foo.go.patch"
    )

    assert result.files_written == 3
    assert head_path.read_text(encoding="utf-8") == "package foo\n"
    assert baseline_path.read_text(encoding="utf-8") == "package foo_old\n"
    assert "@@ -1 +1 @@" in diff_path.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_materialize_maintenance_target_files_added_skips_baseline_fetch(
    tmp_path: Path,
) -> None:
    package_id = "01JTESTPACK0000000000000000"
    _build_package(tmp_path, package_id, "src/new.go", b"package new\n")
    repo_dir = tmp_path / "repository-files"
    fetch_called = False

    async def fetch_baseline(
        _data_source_id: str, _path: str, _ref: str
    ) -> bytes | None:
        nonlocal fetch_called
        fetch_called = True
        return b"unexpected"

    await materialize_maintenance_target_files(
        repository_files_dir=repo_dir,
        job_package_work_dir=tmp_path,
        target_files=(_target_file(path="src/new.go", status="added", patch=None),),
        packages_by_id={package_id: _source(package_id=package_id)},
        fetch_baseline_content=fetch_baseline,
    )

    assert fetch_called is False
    assert (repo_dir / "0b64088c" / "hyperfleet-api" / "src/new.go").is_file()


@pytest.mark.asyncio
async def test_materialize_maintenance_target_files_removed_writes_baseline_only(
    tmp_path: Path,
) -> None:
    repo_dir = tmp_path / "repository-files"

    async def fetch_baseline(_data_source_id: str, path: str, ref: str) -> bytes | None:
        assert path == "src/removed.go"
        assert ref == "defc3afd"
        return b"package removed\n"

    await materialize_maintenance_target_files(
        repository_files_dir=repo_dir,
        job_package_work_dir=tmp_path,
        target_files=(
            _target_file(path="src/removed.go", status="removed", patch="deleted"),
        ),
        packages_by_id={
            "01JTESTPACK0000000000000000": _source(
                package_id="01JTESTPACK0000000000000000"
            )
        },
        fetch_baseline_content=fetch_baseline,
    )

    assert not (repo_dir / "0b64088c" / "hyperfleet-api" / "src/removed.go").exists()
    assert (repo_dir / "defc3afd" / "hyperfleet-api" / "src/removed.go").read_text(
        encoding="utf-8"
    ) == "package removed\n"


def test_write_maintenance_sources_index_documents_layout(tmp_path: Path) -> None:
    target = _target_file()
    write_maintenance_sources_index(
        job_root=tmp_path,
        knowledge_graph_id="kg-1",
        job_packages=(_source(package_id=target.package_id),),
        target_files=(target,),
        materialization=RepositoryFilesMaterializationResult(files_written=3),
    )

    payload = (tmp_path / "sources-index.json").read_text(encoding="utf-8")
    assert "maintenance_commit_snapshots" in payload
    assert "repository-files/defc3afd/hyperfleet-api/src/foo.go" in payload
    assert "repository-files/0b64088c/hyperfleet-api/src/foo.go" in payload
    assert (
        "repository-files/diffs/defc3afd..0b64088c/hyperfleet-api/src/foo.go.patch"
        in payload
    )
