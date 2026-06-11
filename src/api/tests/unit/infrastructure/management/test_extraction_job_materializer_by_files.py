"""Unit tests for by_files extraction job materialization."""

from __future__ import annotations

from pathlib import Path

from extraction.domain.prepared_job_package_source import PreparedJobPackageSource
from infrastructure.management.extraction_job_materializer import (
    build_repository_file_catalog,
    materialize_jobs_from_config,
    match_file_patterns,
    projected_job_count,
)
from management.domain.extraction_job_config import (
    ExtractionJobConfigDocument,
    ExtractionJobSetDefinition,
    ExtractionJobSetStrategy,
)
from shared_kernel.job_package.builder import JobPackageBuilder
from shared_kernel.job_package.value_objects import (
    AdapterCheckpoint,
    ChangeOperation,
    ChangesetEntry,
    JobPackageId,
    SyncMode,
)


def _build_package(work_dir: Path, package_id: str, files: dict[str, bytes]) -> None:
    builder = JobPackageBuilder(
        data_source_id="ds-1",
        knowledge_graph_id="kg-1",
        sync_mode=SyncMode.FULL_REFRESH,
        package_id=JobPackageId(value=package_id),
    )
    for index, (path, content) in enumerate(files.items()):
        ref = builder.add_content(content)
        builder.add_changeset_entry(
            ChangesetEntry(
                operation=ChangeOperation.ADD,
                id=f"file-{index}",
                type="io.kartograph.change.file",
                path=path,
                content_ref=ref,
                content_type="text/plain",
                metadata={},
            )
        )
    builder.set_checkpoint(AdapterCheckpoint(schema_version="1.0.0", data={"commit_sha": "abc"}))
    builder.build(work_dir)


def test_match_file_patterns_supports_globs() -> None:
    from extraction.domain.extraction_job import ExtractionTargetFile

    catalog = [
        ExtractionTargetFile(path="src/a.py", repository_folder="repo-a", package_id="pkg-1"),
        ExtractionTargetFile(path="docs/readme.md", repository_folder="repo-a", package_id="pkg-1"),
    ]
    matched = match_file_patterns(catalog, ("**/*.py",))
    assert [item.path for item in matched] == ["src/a.py"]


def test_materialize_by_files_batches_repository_paths(tmp_path: Path) -> None:
    package_id = "01J0000000000000000000001"
    _build_package(
        tmp_path,
        package_id,
        {
            "features/one.feature": b"Feature: one",
            "features/two.feature": b"Feature: two",
            "features/three.feature": b"Feature: three",
        },
    )
    source = PreparedJobPackageSource(
        package_id=package_id,
        data_source_id="ds-1",
        data_source_name="Repo",
        repository_folder="repo-a",
    )
    catalog = build_repository_file_catalog(
        job_package_work_dir=tmp_path,
        job_packages=(source,),
    )
    assert len(catalog) == 3

    config = ExtractionJobConfigDocument(
        version="1.0",
        job_sets=(
            ExtractionJobSetDefinition(
                name="features",
                strategy=ExtractionJobSetStrategy.BY_FILES,
                file_patterns=("features/*.feature",),
                files_per_job=2,
                description="Extract Feature entities from Gherkin files.",
            ),
        ),
    )
    jobs = materialize_jobs_from_config(
        knowledge_graph_id="kg-1",
        config=config,
        graph_data={"nodes": [], "edges": []},
        job_packages=(source,),
        job_package_work_dir=tmp_path,
    )

    assert len(jobs) == 2
    assert [target.path for target in jobs[0].target_files] == [
        "features/one.feature",
        "features/three.feature",
    ]
    assert [target.path for target in jobs[1].target_files] == ["features/two.feature"]
    assert projected_job_count(
        config.job_sets[0],
        entity_instance_counts={},
        matched_file_count=len(match_file_patterns(catalog, ("features/*.feature",))),
    ) == 2
