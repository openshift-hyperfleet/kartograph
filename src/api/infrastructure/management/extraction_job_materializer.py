"""Materialize extraction jobs from saved job set definitions."""

from __future__ import annotations

import hashlib
import math
from typing import Any

from ulid import ULID

from extraction.domain.extraction_job import ExtractionJobRecord, ExtractionJobStatus, ExtractionTargetInstance
from management.domain.extraction_job_config import (
    ExtractionJobConfigDocument,
    ExtractionJobSetDefinition,
    ExtractionJobSetStrategy,
)


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


def materialize_jobs_from_config(
    *,
    knowledge_graph_id: str,
    config: ExtractionJobConfigDocument,
    graph_data: dict[str, Any],
) -> list[ExtractionJobRecord]:
    """Build pending extraction jobs from job set definitions and live graph instances."""
    instances_by_type = entity_instances_by_type_from_graph(
        knowledge_graph_id=knowledge_graph_id,
        graph_data=graph_data,
    )
    jobs: list[ExtractionJobRecord] = []
    order_index = 0

    for job_set in config.job_sets:
        if job_set.strategy != ExtractionJobSetStrategy.BY_INSTANCES:
            continue
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

    return jobs


def projected_job_count(
    job_set: ExtractionJobSetDefinition,
    *,
    entity_instance_counts: dict[str, int],
) -> int | None:
    if job_set.strategy != ExtractionJobSetStrategy.BY_INSTANCES:
        return None
    total = entity_instance_counts.get(job_set.entity_type or "", 0)
    per_job = job_set.instances_per_job
    if total <= 0 or per_job is None or per_job < 1:
        return 0 if total == 0 else None
    return math.ceil(total / per_job)
