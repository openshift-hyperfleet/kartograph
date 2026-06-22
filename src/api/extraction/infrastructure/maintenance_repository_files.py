"""Materialize commit-scoped repository snapshots for maintenance extraction jobs."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from pathlib import Path

from extraction.domain.extraction_job import ExtractionTargetFile
from extraction.domain.prepared_job_package_source import PreparedJobPackageSource
from extraction.infrastructure.extraction_job_repository_files import (
    RepositoryFilesMaterializationResult,
)
from shared_kernel.job_package.path_safety import validate_zip_entry_name
from shared_kernel.job_package.reader import JobPackageReader
from shared_kernel.job_package.value_objects import JobPackageId

BaselineContentFetcher = Callable[[str, str, str], Awaitable[bytes | None]]

_ADDED_STATUSES = frozenset({"added"})
_REMOVED_STATUSES = frozenset({"removed"})
_HEAD_STATUSES = frozenset({"added", "modified", "renamed", "changed", "copied"})
_BASELINE_STATUSES = frozenset({"removed", "modified", "renamed", "changed", "copied"})


def maintenance_head_path(
    *,
    repository_files_dir: Path,
    head_commit: str,
    repository_folder: str,
    path: str,
) -> Path:
    return repository_files_dir / head_commit / repository_folder / path


def maintenance_baseline_path(
    *,
    repository_files_dir: Path,
    baseline_commit: str,
    repository_folder: str,
    path: str,
) -> Path:
    return repository_files_dir / baseline_commit / repository_folder / path


def maintenance_diff_path(
    *,
    repository_files_dir: Path,
    baseline_commit: str,
    head_commit: str,
    repository_folder: str,
    path: str,
) -> Path:
    return (
        repository_files_dir
        / "diffs"
        / f"{baseline_commit}..{head_commit}"
        / repository_folder
        / f"{path}.patch"
    )


def _write_bytes(path: Path, content: bytes) -> None:
    validate_zip_entry_name(path.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _write_text(path: Path, content: str) -> None:
    _write_bytes(path, content.encode("utf-8"))


def _materialize_head_from_job_package(
    *,
    repository_files_dir: Path,
    job_package_work_dir: Path,
    target_file: ExtractionTargetFile,
    source: PreparedJobPackageSource,
) -> bool:
    head_commit = target_file.head_commit
    if not head_commit:
        return False
    archive_path = (
        job_package_work_dir / JobPackageId(value=source.package_id).archive_name()
    )
    if not archive_path.is_file():
        return False
    reader = JobPackageReader(archive_path)
    for change in reader.iter_changeset():
        if change.path != target_file.path or change.content_ref is None:
            continue
        validate_zip_entry_name(change.path)
        output_path = maintenance_head_path(
            repository_files_dir=repository_files_dir,
            head_commit=head_commit,
            repository_folder=source.repository_folder,
            path=target_file.path,
        )
        _write_bytes(output_path, reader.read_content(change.content_ref))
        return True
    return False


async def materialize_maintenance_target_files(
    *,
    repository_files_dir: Path,
    job_package_work_dir: Path,
    target_files: tuple[ExtractionTargetFile, ...],
    packages_by_id: dict[str, PreparedJobPackageSource],
    fetch_baseline_content: BaselineContentFetcher | None = None,
) -> RepositoryFilesMaterializationResult:
    """Write baseline/HEAD snapshots and unified diffs for maintenance jobs."""
    files_written = 0
    packages_missing: list[str] = []
    sample_paths: list[str] = []
    warnings: list[str] = []

    for target_file in target_files:
        source = packages_by_id.get(target_file.package_id)
        if source is None:
            warnings.append(
                f"No prepared JobPackage for target file {target_file.repository_folder}/{target_file.path}"
            )
            continue

        status = (target_file.change_status or "modified").lower()
        baseline_commit = target_file.baseline_commit
        head_commit = target_file.head_commit
        data_source_id = target_file.data_source_id or source.data_source_id

        if status in _HEAD_STATUSES:
            archive_path = (
                job_package_work_dir
                / JobPackageId(value=source.package_id).archive_name()
            )
            if not archive_path.is_file():
                packages_missing.append(target_file.package_id)
            elif head_commit and _materialize_head_from_job_package(
                repository_files_dir=repository_files_dir,
                job_package_work_dir=job_package_work_dir,
                target_file=target_file,
                source=source,
            ):
                files_written += 1
                sample_paths.append(
                    f"{head_commit}/{source.repository_folder}/{target_file.path}"
                )
            elif head_commit:
                warnings.append(
                    f"HEAD content missing in JobPackage for {source.repository_folder}/{target_file.path}"
                )

        if (
            status in _BASELINE_STATUSES
            and baseline_commit
            and fetch_baseline_content is not None
        ):
            baseline_bytes = await fetch_baseline_content(
                data_source_id,
                target_file.path,
                baseline_commit,
            )
            if baseline_bytes is not None:
                baseline_path = maintenance_baseline_path(
                    repository_files_dir=repository_files_dir,
                    baseline_commit=baseline_commit,
                    repository_folder=source.repository_folder,
                    path=target_file.path,
                )
                _write_bytes(baseline_path, baseline_bytes)
                files_written += 1
                sample_paths.append(
                    f"{baseline_commit}/{source.repository_folder}/{target_file.path}"
                )
            elif status in _REMOVED_STATUSES:
                warnings.append(
                    f"Baseline content unavailable for removed file {source.repository_folder}/{target_file.path}"
                )

        if target_file.patch and baseline_commit and head_commit:
            diff_path = maintenance_diff_path(
                repository_files_dir=repository_files_dir,
                baseline_commit=baseline_commit,
                head_commit=head_commit,
                repository_folder=source.repository_folder,
                path=target_file.path,
            )
            _write_text(diff_path, target_file.patch)
            files_written += 1
            sample_paths.append(
                f"diffs/{baseline_commit}..{head_commit}/{source.repository_folder}/{target_file.path}.patch"
            )

    return RepositoryFilesMaterializationResult(
        files_written=files_written,
        packages_requested=len(
            {target_file.package_id for target_file in target_files}
        ),
        packages_found=len({target_file.package_id for target_file in target_files})
        - len(set(packages_missing)),
        packages_missing=tuple(packages_missing),
        sample_paths=tuple(sample_paths[:12]),
        warnings=tuple(warnings),
    )


def write_maintenance_sources_index(
    *,
    job_root: Path,
    knowledge_graph_id: str,
    job_packages: tuple[PreparedJobPackageSource, ...],
    target_files: tuple[ExtractionTargetFile, ...],
    materialization: RepositoryFilesMaterializationResult,
) -> None:
    """Write sources-index.json describing maintenance commit snapshot layout."""
    commits = sorted(
        {
            commit
            for target_file in target_files
            for commit in (target_file.baseline_commit, target_file.head_commit)
            if commit
        }
    )
    diff_ranges = sorted(
        {
            f"{target_file.baseline_commit}..{target_file.head_commit}"
            for target_file in target_files
            if target_file.baseline_commit and target_file.head_commit
        }
    )
    sources = []
    for source in job_packages:
        source_targets = [
            target_file
            for target_file in target_files
            if target_file.data_source_id == source.data_source_id
            or (
                target_file.data_source_id is None
                and target_file.package_id == source.package_id
            )
        ]
        head_commit = next(
            (target.head_commit for target in source_targets if target.head_commit),
            None,
        )
        baseline_commit = next(
            (
                target.baseline_commit
                for target in source_targets
                if target.baseline_commit
            ),
            None,
        )
        sources.append(
            {
                "job_package_id": source.package_id,
                "data_source_id": source.data_source_id,
                "data_source_name": source.data_source_name,
                "repository_folder": source.repository_folder,
                "baseline_snapshot_root": (
                    f"repository-files/{baseline_commit}/{source.repository_folder}"
                    if baseline_commit
                    else None
                ),
                "head_snapshot_root": (
                    f"repository-files/{head_commit}/{source.repository_folder}"
                    if head_commit
                    else None
                ),
            }
        )
    layout = {
        "mode": "maintenance_commit_snapshots",
        "description": (
            "Each changed file appears under repository-files/{commit_sha}/{repository_folder}/{path}. "
            "Baseline copies use last_extraction_baseline_commit; HEAD copies use tracked branch tip. "
            "Unified diffs live under repository-files/diffs/{baseline}..{head}/{repository_folder}/{path}.patch."
        ),
        "baseline_root_pattern": "repository-files/{baseline_commit}/{repository_folder}/",
        "head_root_pattern": "repository-files/{head_commit}/{repository_folder}/",
        "diff_root_pattern": "repository-files/diffs/{baseline_commit}..{head_commit}/{repository_folder}/",
        "commits": commits,
        "diff_ranges": diff_ranges,
        "target_files": [
            {
                **target_file.to_dict(),
                "baseline_path": (
                    f"repository-files/{target_file.baseline_commit}/"
                    f"{target_file.repository_folder}/{target_file.path}"
                    if target_file.baseline_commit
                    else None
                ),
                "head_path": (
                    f"repository-files/{target_file.head_commit}/"
                    f"{target_file.repository_folder}/{target_file.path}"
                    if target_file.head_commit
                    else None
                ),
                "diff_path": (
                    f"repository-files/diffs/{target_file.baseline_commit}..{target_file.head_commit}/"
                    f"{target_file.repository_folder}/{target_file.path}.patch"
                    if target_file.baseline_commit
                    and target_file.head_commit
                    and target_file.patch
                    else None
                ),
            }
            for target_file in target_files
        ],
    }
    (job_root / "sources-index.json").write_text(
        json.dumps(
            {
                "version": 1,
                "knowledge_graph_id": knowledge_graph_id,
                "layout": layout,
                "sources": sources,
                "materialization": materialization.to_dict(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
