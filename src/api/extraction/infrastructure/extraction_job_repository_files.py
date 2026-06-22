"""Materialize repository-files from prepared JobPackages for extraction jobs."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from extraction.domain.extraction_job import (
    ExtractionTargetFile,
    ExtractionTargetInstance,
)
from extraction.domain.prepared_job_package_source import PreparedJobPackageSource
from shared_kernel.job_package.path_safety import validate_zip_entry_name
from shared_kernel.job_package.reader import JobPackageReader
from shared_kernel.job_package.value_objects import JobPackageId

_INSTANCE_PATH_PROPERTY_KEYS = (
    "config_file_path",
    "config_path",
    "source_path",
    "file_path",
    "repository_path",
)


@dataclass(frozen=True)
class RepositoryFilesMaterializationResult:
    """Outcome of unpacking JobPackage archives into repository-files/."""

    files_written: int = 0
    packages_requested: int = 0
    packages_found: int = 0
    packages_missing: tuple[str, ...] = field(default_factory=tuple)
    paths_requested: tuple[str, ...] = field(default_factory=tuple)
    paths_not_found: tuple[str, ...] = field(default_factory=tuple)
    sample_paths: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def merge(
        self, other: RepositoryFilesMaterializationResult
    ) -> RepositoryFilesMaterializationResult:
        combined_samples = self.sample_paths + other.sample_paths
        return RepositoryFilesMaterializationResult(
            files_written=self.files_written + other.files_written,
            packages_requested=max(self.packages_requested, other.packages_requested),
            packages_found=self.packages_found + other.packages_found,
            packages_missing=tuple(
                dict.fromkeys(self.packages_missing + other.packages_missing)
            ),
            paths_requested=tuple(
                dict.fromkeys(self.paths_requested + other.paths_requested)
            ),
            paths_not_found=tuple(
                dict.fromkeys(self.paths_not_found + other.paths_not_found)
            ),
            sample_paths=tuple(dict.fromkeys(combined_samples))[:12],
            warnings=tuple(dict.fromkeys(self.warnings + other.warnings)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "files_written": self.files_written,
            "packages_requested": self.packages_requested,
            "packages_found": self.packages_found,
            "packages_missing": list(self.packages_missing),
            "paths_requested": list(self.paths_requested),
            "paths_not_found": list(self.paths_not_found),
            "sample_paths": list(self.sample_paths),
            "warnings": list(self.warnings),
        }


def collect_instance_repository_paths(
    instances: tuple[ExtractionTargetInstance, ...],
) -> tuple[str, ...]:
    """Return repository-relative paths referenced by assigned instance properties."""
    paths: list[str] = []
    seen: set[str] = set()
    for instance in instances:
        for key, raw_value in instance.properties.items():
            if raw_value in (None, ""):
                continue
            candidates: list[str] = []
            if key in _INSTANCE_PATH_PROPERTY_KEYS or key.endswith("_path"):
                candidates.append(str(raw_value).strip())
            for candidate in candidates:
                normalized = _normalize_repository_path(candidate)
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                paths.append(normalized)
    return tuple(sorted(paths))


def _normalize_repository_path(path: str) -> str:
    cleaned = path.strip().replace("\\", "/")
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    return cleaned.lstrip("/")


def _path_matches(requested: str, candidate: str) -> bool:
    normalized_requested = _normalize_repository_path(requested).rstrip("/")
    normalized_candidate = _normalize_repository_path(candidate)
    if normalized_candidate == normalized_requested:
        return True
    if normalized_candidate.startswith(f"{normalized_requested}/"):
        return True
    if normalized_candidate.endswith(f"/{normalized_requested}"):
        return True
    if normalized_requested.endswith(normalized_candidate):
        return True
    return False


def materialize_all_repository_files(
    *,
    repository_files_dir: Path,
    job_package_work_dir: Path,
    job_packages: tuple[PreparedJobPackageSource, ...],
) -> RepositoryFilesMaterializationResult:
    """Unpack every JobPackage changeset entry into repository-files/."""
    files_written = 0
    packages_found = 0
    packages_missing: list[str] = []
    sample_paths: list[str] = []

    for source in job_packages:
        archive_path = (
            job_package_work_dir / JobPackageId(value=source.package_id).archive_name()
        )
        if not archive_path.is_file():
            packages_missing.append(source.package_id)
            continue
        reader = JobPackageReader(archive_path)
        manifest = reader.read_manifest()
        if manifest.entry_count <= 0:
            continue
        packages_found += 1
        for change in reader.iter_changeset():
            if change.content_ref is None or not change.path:
                continue
            validate_zip_entry_name(change.path)
            output_path = repository_files_dir / source.repository_folder / change.path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(reader.read_content(change.content_ref))
            files_written += 1
            if len(sample_paths) < 12:
                sample_paths.append(f"{source.repository_folder}/{change.path}")

    warnings: list[str] = []
    if job_packages and files_written == 0:
        if packages_missing:
            warnings.append(
                "No JobPackage archives found on disk for: "
                + ", ".join(packages_missing[:5])
                + ("..." if len(packages_missing) > 5 else "")
            )
        else:
            warnings.append(
                "JobPackages exist but no repository file content was materialized."
            )

    return RepositoryFilesMaterializationResult(
        files_written=files_written,
        packages_requested=len(job_packages),
        packages_found=packages_found,
        packages_missing=tuple(packages_missing),
        sample_paths=tuple(sample_paths),
        warnings=tuple(warnings),
    )


def materialize_instance_repository_paths(
    *,
    repository_files_dir: Path,
    job_package_work_dir: Path,
    job_packages: tuple[PreparedJobPackageSource, ...],
    paths: tuple[str, ...],
) -> RepositoryFilesMaterializationResult:
    """Materialize only repository paths referenced by assigned entity instances."""
    if not paths:
        return RepositoryFilesMaterializationResult()

    files_written = 0
    packages_found = 0
    packages_missing: list[str] = []
    paths_not_found = set(paths)
    sample_paths: list[str] = []

    for source in job_packages:
        archive_path = (
            job_package_work_dir / JobPackageId(value=source.package_id).archive_name()
        )
        if not archive_path.is_file():
            packages_missing.append(source.package_id)
            continue
        reader = JobPackageReader(archive_path)
        packages_found += 1
        for change in reader.iter_changeset():
            if change.content_ref is None or not change.path:
                continue
            matched = next(
                (
                    requested
                    for requested in paths
                    if _path_matches(requested, str(change.path))
                ),
                None,
            )
            if matched is None:
                continue
            validate_zip_entry_name(change.path)
            output_path = repository_files_dir / source.repository_folder / change.path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(reader.read_content(change.content_ref))
            files_written += 1
            paths_not_found.discard(matched)
            if len(sample_paths) < 12:
                sample_paths.append(f"{source.repository_folder}/{change.path}")

    warnings: list[str] = []
    if paths_not_found:
        warnings.append(
            "Instance-referenced paths not found in JobPackages: "
            + ", ".join(sorted(paths_not_found)[:8])
            + ("..." if len(paths_not_found) > 8 else "")
        )

    return RepositoryFilesMaterializationResult(
        files_written=files_written,
        packages_requested=len(job_packages),
        packages_found=packages_found,
        packages_missing=tuple(packages_missing),
        paths_requested=paths,
        paths_not_found=tuple(sorted(paths_not_found)),
        sample_paths=tuple(sample_paths),
        warnings=tuple(warnings),
    )


def materialize_target_files(
    *,
    repository_files_dir: Path,
    job_package_work_dir: Path,
    target_files: tuple[ExtractionTargetFile, ...],
    packages_by_id: dict[str, PreparedJobPackageSource],
) -> RepositoryFilesMaterializationResult:
    files_written = 0
    packages_missing: list[str] = []
    sample_paths: list[str] = []

    for target_file in target_files:
        source = packages_by_id.get(target_file.package_id)
        if source is None:
            continue
        archive_path = (
            job_package_work_dir / JobPackageId(value=source.package_id).archive_name()
        )
        if not archive_path.is_file():
            packages_missing.append(target_file.package_id)
            continue
        reader = JobPackageReader(archive_path)
        for change in reader.iter_changeset():
            if change.path != target_file.path or change.content_ref is None:
                continue
            validate_zip_entry_name(change.path)
            output_path = repository_files_dir / source.repository_folder / change.path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(reader.read_content(change.content_ref))
            files_written += 1
            sample_paths.append(f"{source.repository_folder}/{change.path}")
            break

    return RepositoryFilesMaterializationResult(
        files_written=files_written,
        packages_requested=len(
            {target_file.package_id for target_file in target_files}
        ),
        packages_found=len({target_file.package_id for target_file in target_files})
        - len(packages_missing),
        packages_missing=tuple(packages_missing),
        sample_paths=tuple(sample_paths),
    )


def write_sources_index(
    *,
    job_root: Path,
    knowledge_graph_id: str,
    job_packages: tuple[PreparedJobPackageSource, ...],
    materialization: RepositoryFilesMaterializationResult,
) -> None:
    """Write sources-index.json (agentic-ci context file) for the job workspace."""
    sources = [
        {
            "job_package_id": source.package_id,
            "data_source_id": source.data_source_id,
            "data_source_name": source.data_source_name,
            "repository_folder": source.repository_folder,
            "repository_root": f"repository-files/{source.repository_folder}",
        }
        for source in job_packages
    ]
    (job_root / "sources-index.json").write_text(
        json.dumps(
            {
                "version": 1,
                "knowledge_graph_id": knowledge_graph_id,
                "sources": sources,
                "materialization": materialization.to_dict(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
