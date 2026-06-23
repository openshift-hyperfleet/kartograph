"""Resolve changed maintenance files to prepared JobPackage targets."""

from __future__ import annotations

from pathlib import Path

from infrastructure.management.extraction_job_materializer import (
    build_repository_file_catalog,
    match_file_patterns,
)
from infrastructure.management.maintenance_job_materializer import (
    ChangedMaintenanceFile,
)
from management.domain.aggregates import DataSource
from management.infrastructure.git_diff_summary_service import GitDiffSummaryService


async def collect_changed_maintenance_files(
    *,
    diff_summary_service: GitDiffSummaryService,
    data_sources: list[DataSource],
    job_package_work_dir: Path,
    job_packages: tuple,
    max_files_per_source: int = 10_000,
) -> list[ChangedMaintenanceFile]:
    """Collect changed files across sources and map them to prepared package paths."""
    catalog = build_repository_file_catalog(
        job_package_work_dir=job_package_work_dir,
        job_packages=job_packages,
    )
    packages_by_source = {source.data_source_id: source for source in job_packages}

    changed: list[ChangedMaintenanceFile] = []
    for data_source in sorted(data_sources, key=lambda ds: ds.name):
        summary = await diff_summary_service.build_summary(
            data_source=data_source,
            max_files=max_files_per_source,
        )
        if summary.total_changed_files <= 0:
            continue
        package = packages_by_source.get(data_source.id.value)
        if package is None:
            continue
        patterns = tuple(
            f"**/{entry['path']}"
            for entry in summary.changed_files
            if entry.get("path")
        )
        matched = match_file_patterns(catalog, patterns) if patterns else []
        matched_by_path = {
            target.path: target
            for target in matched
            if target.repository_folder == package.repository_folder
        }
        for entry in summary.changed_files:
            path = str(entry.get("path", "")).strip()
            if not path:
                continue
            target = matched_by_path.get(path)
            if target is None:
                continue
            baseline_commit = summary.baseline_commit
            head_commit = summary.tracked_head_commit
            if not baseline_commit or not head_commit:
                continue
            changed.append(
                ChangedMaintenanceFile(
                    data_source_id=data_source.id.value,
                    repository_folder=target.repository_folder,
                    path=target.path,
                    status=str(entry.get("status", "modified")),
                    package_id=target.package_id,
                    baseline_commit=baseline_commit,
                    head_commit=head_commit,
                    patch=(
                        str(entry["patch"]) if entry.get("patch") is not None else None
                    ),
                )
            )
    return changed


__all__ = [
    "collect_changed_maintenance_files",
]
