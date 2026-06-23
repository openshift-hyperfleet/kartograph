"""Unit tests for extraction job repository-files materialization."""

from __future__ import annotations

from pathlib import Path

from extraction.domain.extraction_job import ExtractionTargetInstance
from extraction.domain.prepared_job_package_source import PreparedJobPackageSource
from extraction.infrastructure.extraction_job_repository_files import (
    collect_instance_repository_paths,
    materialize_all_repository_files,
    materialize_instance_repository_paths,
)
from shared_kernel.job_package.builder import JobPackageBuilder
from shared_kernel.job_package.value_objects import (
    AdapterCheckpoint,
    ChangeOperation,
    ChangesetEntry,
    JobPackageId,
    SyncMode,
)


def _source(*, package_id: str) -> PreparedJobPackageSource:
    return PreparedJobPackageSource(
        package_id=package_id,
        data_source_id="ds-1",
        data_source_name="hyperfleet-e2e",
        repository_folder="hyperfleet-e2e",
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
        AdapterCheckpoint(schema_version="1.0.0", data={"commit_sha": "abc"})
    )
    builder.build(work_dir)


def test_collect_instance_repository_paths_reads_config_and_source_paths() -> None:
    paths = collect_instance_repository_paths(
        (
            ExtractionTargetInstance(
                slug="adapter-a",
                entity_type="Adapter",
                properties={
                    "config_file_path": "testdata/adapter-configs/cl-stuck/adapter-config.yaml",
                    "source_path": "pkg/internal/foo.go",
                },
            ),
        )
    )

    assert "testdata/adapter-configs/cl-stuck/adapter-config.yaml" in paths
    assert "pkg/internal/foo.go" in paths


def test_collect_instance_repository_paths_reads_config_path_directories() -> None:
    paths = collect_instance_repository_paths(
        (
            ExtractionTargetInstance(
                slug="cl_m_wrong_nest",
                entity_type="Adapter",
                properties={"config_path": "testdata/adapter-configs/cl-m-wrong-nest"},
            ),
        )
    )

    assert paths == ("testdata/adapter-configs/cl-m-wrong-nest",)


def test_materialize_all_repository_files_writes_changeset(tmp_path: Path) -> None:
    package_id = "01JTESTPACK0000000000000000"
    _build_package(
        tmp_path,
        package_id,
        "testdata/adapter-configs/cl-stuck/adapter-config.yaml",
        b"adapter: stuck\n",
    )
    repo_dir = tmp_path / "repository-files"

    result = materialize_all_repository_files(
        repository_files_dir=repo_dir,
        job_package_work_dir=tmp_path,
        job_packages=(_source(package_id=package_id),),
    )

    output = (
        repo_dir
        / "hyperfleet-e2e"
        / "testdata/adapter-configs/cl-stuck/adapter-config.yaml"
    )
    assert result.files_written == 1
    assert output.read_text(encoding="utf-8") == "adapter: stuck\n"


def test_materialize_all_repository_files_warns_when_archives_missing(
    tmp_path: Path,
) -> None:
    result = materialize_all_repository_files(
        repository_files_dir=tmp_path / "repository-files",
        job_package_work_dir=tmp_path,
        job_packages=(_source(package_id="01JMISSING0000000000000000"),),
    )

    assert result.files_written == 0
    assert result.packages_missing == ("01JMISSING0000000000000000",)
    assert any("No JobPackage archives found" in warning for warning in result.warnings)


def test_materialize_instance_repository_paths_targets_referenced_files(
    tmp_path: Path,
) -> None:
    package_id = "01JTESTPACK0000000000000001"
    _build_package(
        tmp_path,
        package_id,
        "testdata/adapter-configs/cl-stuck/adapter-config.yaml",
        b"adapter: stuck\n",
    )
    repo_dir = tmp_path / "repository-files"

    result = materialize_instance_repository_paths(
        repository_files_dir=repo_dir,
        job_package_work_dir=tmp_path,
        job_packages=(_source(package_id=package_id),),
        paths=("testdata/adapter-configs/cl-stuck/adapter-config.yaml",),
    )

    assert result.files_written == 1
    assert result.paths_not_found == ()
    assert (
        repo_dir
        / "hyperfleet-e2e"
        / "testdata/adapter-configs/cl-stuck/adapter-config.yaml"
    ).is_file()


def test_materialize_instance_repository_paths_matches_directory_config_path_prefix(
    tmp_path: Path,
) -> None:
    package_id = "01JTESTPACK0000000000000003"
    _build_package(
        tmp_path,
        package_id,
        "testdata/adapter-configs/cl-m-wrong-nest/adapter-config.yaml",
        b"transport: maestro\n",
    )
    repo_dir = tmp_path / "repository-files"

    result = materialize_instance_repository_paths(
        repository_files_dir=repo_dir,
        job_package_work_dir=tmp_path,
        job_packages=(_source(package_id=package_id),),
        paths=("testdata/adapter-configs/cl-m-wrong-nest",),
    )

    output = (
        repo_dir
        / "hyperfleet-e2e"
        / "testdata/adapter-configs/cl-m-wrong-nest/adapter-config.yaml"
    )
    assert result.files_written == 1
    assert result.paths_not_found == ()
    assert output.read_text(encoding="utf-8") == "transport: maestro\n"
