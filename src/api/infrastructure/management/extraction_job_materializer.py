"""Materialize extraction jobs from saved job set definitions."""

from __future__ import annotations

import fnmatch
import hashlib
import math
from pathlib import Path
from typing import Any

from ulid import ULID

from extraction.domain.extraction_job import (
    ExtractionJobRecord,
    ExtractionJobStatus,
    ExtractionTargetFile,
    ExtractionTargetInstance,
)
from extraction.domain.prepared_job_package_source import PreparedJobPackageSource
from management.domain.extraction_job_config import (
    ExtractionJobConfigDocument,
    ExtractionJobSetDefinition,
    ExtractionJobSetStrategy,
)
from shared_kernel.job_package.path_safety import validate_zip_entry_name
from shared_kernel.job_package.reader import JobPackageReader
from shared_kernel.job_package.value_objects import JobPackageId


def _batch_items(items: list[Any], batch_size: int) -> list[list[Any]]:
    return [items[i : i + batch_size] for i in range(0, len(items), batch_size)]


def _generate_job_id(job_set_name: str, batch_idx: int, content_hash: str) -> str:
    hash_suffix = hashlib.sha256(content_hash.encode()).hexdigest()[:8]
    return f"{job_set_name}_batch_{batch_idx:04d}_{hash_suffix}"


def entity_instance_counts_from_graph(
    *,
    knowledge_graph_id: str,
    graph_data: dict[str, Any],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for node in graph_data.get("nodes", []):
        if node.get("knowledge_graph_id") != knowledge_graph_id or node.get("_redacted"):
            continue
        entity_type = str(node.get("type") or "unknown")
        counts[entity_type] = counts.get(entity_type, 0) + 1
    return counts


def entity_instances_by_type_from_graph(
    *,
    knowledge_graph_id: str,
    graph_data: dict[str, Any],
) -> dict[str, list[ExtractionTargetInstance]]:
    grouped: dict[str, list[ExtractionTargetInstance]] = {}
    for node in sorted(
        graph_data.get("nodes", []),
        key=lambda item: str(item.get("slug") or item.get("domainId") or item.get("id") or ""),
    ):
        if node.get("knowledge_graph_id") != knowledge_graph_id or node.get("_redacted"):
            continue
        entity_type = str(node.get("type") or "unknown")
        slug = str(node.get("slug") or node.get("domainId") or node.get("id") or "")
        properties = {
            key: value
            for key, value in node.items()
            if key
            not in {
                "id",
                "slug",
                "data_source_id",
                "source_path",
                "knowledge_graph_id",
                "graph_id",
                "name",
                "type",
                "domainId",
            }
            and not str(key).startswith("_")
        }
        grouped.setdefault(entity_type, []).append(
            ExtractionTargetInstance(slug=slug, entity_type=entity_type, properties=properties)
        )
    return grouped


def build_repository_file_catalog(
    *,
    job_package_work_dir: Path,
    job_packages: tuple[PreparedJobPackageSource, ...],
) -> list[ExtractionTargetFile]:
    """Collect repository file paths from the latest prepared JobPackages."""
    catalog: list[ExtractionTargetFile] = []
    for source in job_packages:
        archive_path = job_package_work_dir / JobPackageId(value=source.package_id).archive_name()
        if not archive_path.is_file():
            continue
        try:
            reader = JobPackageReader(archive_path)
        except (OSError, ValueError):
            continue
        for change in reader.iter_changeset():
            if change.content_ref is None or not change.path:
                continue
            validate_zip_entry_name(change.path)
            catalog.append(
                ExtractionTargetFile(
                    path=str(change.path),
                    repository_folder=source.repository_folder,
                    package_id=source.package_id,
                )
            )
    return sorted(catalog, key=lambda item: (item.repository_folder, item.path))


def match_file_patterns(
    catalog: list[ExtractionTargetFile],
    patterns: tuple[str, ...],
) -> list[ExtractionTargetFile]:
    """Return catalog entries matching any glob pattern."""
    if not patterns:
        return []
    matched: list[ExtractionTargetFile] = []
    seen: set[tuple[str, str, str]] = set()
    for target_file in catalog:
        candidates = (
            target_file.path,
            f"{target_file.repository_folder}/{target_file.path}",
        )
        for pattern in patterns:
            if any(fnmatch.fnmatch(candidate, pattern) for candidate in candidates):
                key = (
                    target_file.path,
                    target_file.repository_folder,
                    target_file.package_id,
                )
                if key not in seen:
                    seen.add(key)
                    matched.append(target_file)
                break
    return matched


def materialize_jobs_from_config(
    *,
    knowledge_graph_id: str,
    config: ExtractionJobConfigDocument,
    graph_data: dict[str, Any],
    job_packages: tuple[PreparedJobPackageSource, ...] = (),
    job_package_work_dir: Path | None = None,
) -> list[ExtractionJobRecord]:
    """Build pending extraction jobs from job set definitions and live graph instances."""
    instances_by_type = entity_instances_by_type_from_graph(
        knowledge_graph_id=knowledge_graph_id,
        graph_data=graph_data,
    )
    file_catalog: list[ExtractionTargetFile] = []
    if job_package_work_dir is not None and job_packages:
        file_catalog = build_repository_file_catalog(
            job_package_work_dir=job_package_work_dir,
            job_packages=job_packages,
        )
    jobs: list[ExtractionJobRecord] = []
    order_index = 0

    for job_set in config.job_sets:
        if job_set.strategy == ExtractionJobSetStrategy.BY_INSTANCES:
            entity_type = job_set.entity_type or ""
            instances = instances_by_type.get(entity_type, [])
            per_job = int(job_set.instances_per_job or 1)
            if per_job < 1 or not instances:
                continue
            description = (job_set.description or "").strip()
            for batch_idx, batch in enumerate(_batch_items(instances, per_job), start=1):
                content_hash = "|".join(instance.slug for instance in batch)
                job_id = _generate_job_id(job_set.name, batch_idx, content_hash)
                jobs.append(
                    ExtractionJobRecord(
                        id=str(ULID()),
                        knowledge_graph_id=knowledge_graph_id,
                        job_id=job_id,
                        job_set_name=job_set.name,
                        strategy=job_set.strategy.value,
                        status=ExtractionJobStatus.PENDING,
                        order_index=order_index,
                        description=description,
                        target_instances=tuple(batch),
                    )
                )
                order_index += 1
            continue

        if job_set.strategy != ExtractionJobSetStrategy.BY_FILES:
            continue
        matched_files = match_file_patterns(file_catalog, job_set.file_patterns)
        per_job = int(job_set.files_per_job or 1)
        if per_job < 1 or not matched_files:
            continue
        description = (job_set.description or "").strip() or f"Extract entities from files in {job_set.name}."
        for batch_idx, batch in enumerate(_batch_items(matched_files, per_job), start=1):
            content_hash = "|".join(
                f"{target_file.repository_folder}:{target_file.path}" for target_file in batch
            )
            job_id = _generate_job_id(job_set.name, batch_idx, content_hash)
            jobs.append(
                ExtractionJobRecord(
                    id=str(ULID()),
                    knowledge_graph_id=knowledge_graph_id,
                    job_id=job_id,
                    job_set_name=job_set.name,
                    strategy=job_set.strategy.value,
                    status=ExtractionJobStatus.PENDING,
                    order_index=order_index,
                    description=description,
                    target_files=tuple(batch),
                )
            )
            order_index += 1

    return jobs


def projected_job_count(
    job_set: ExtractionJobSetDefinition,
    *,
    entity_instance_counts: dict[str, int],
    matched_file_count: int | None = None,
) -> int | None:
    if job_set.strategy == ExtractionJobSetStrategy.BY_INSTANCES:
        total = entity_instance_counts.get(job_set.entity_type or "", 0)
        per_job = job_set.instances_per_job
        if total <= 0 or per_job is None or per_job < 1:
            return 0 if total == 0 else None
        return math.ceil(total / per_job)
    if job_set.strategy != ExtractionJobSetStrategy.BY_FILES:
        return None
    total = matched_file_count
    if total is None:
        return None
    per_job = job_set.files_per_job
    if total <= 0 or per_job is None or per_job < 1:
        return 0 if total == 0 else None
    return math.ceil(total / per_job)
