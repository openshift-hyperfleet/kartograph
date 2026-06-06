"""Extraction job set configuration value objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ExtractionJobSetStrategy(StrEnum):
    """Batching strategy for an extraction job set."""

    BY_INSTANCES = "by_instances"
    BY_FILES = "by_files"


@dataclass(frozen=True)
class ExtractionJobSetDefinition:
    """One job set describing how to batch extraction work."""

    name: str
    strategy: ExtractionJobSetStrategy
    description: str | None = None
    entity_type: str | None = None
    instances_per_job: int | None = None
    file_patterns: tuple[str, ...] = field(default_factory=tuple)
    files_per_job: int | None = None

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("Job set name must not be empty")

    def validation_errors(self, *, entity_instance_counts: dict[str, int]) -> tuple[str, ...]:
        """Return human-readable validation errors for this job set."""
        errors: list[str] = []
        if self.strategy == ExtractionJobSetStrategy.BY_INSTANCES:
            if not self.entity_type or not self.entity_type.strip():
                errors.append(f"{self.name}: entity type is required for by_instances.")
            else:
                count = entity_instance_counts.get(self.entity_type, 0)
                if count <= 0:
                    errors.append(
                        f"{self.name}: selected entity type '{self.entity_type}' has 0 instances."
                    )
            per_job = self.instances_per_job
            if per_job is None or not isinstance(per_job, int) or per_job < 1:
                errors.append(f"{self.name}: instances_per_job must be an integer >= 1.")
            if not self.description or not self.description.strip():
                errors.append(
                    f"{self.name}: per-instance extraction description is required."
                )
        elif self.strategy == ExtractionJobSetStrategy.BY_FILES:
            if not self.file_patterns:
                errors.append(f"{self.name}: at least one file pattern is required for by_files.")
            per_job = self.files_per_job
            if per_job is None or not isinstance(per_job, int) or per_job < 1:
                errors.append(f"{self.name}: files_per_job must be an integer >= 1.")
        return tuple(errors)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "strategy": self.strategy.value,
        }
        if self.description:
            payload["description"] = self.description
        if self.strategy == ExtractionJobSetStrategy.BY_INSTANCES:
            if self.entity_type:
                payload["entity_type"] = self.entity_type
            if self.instances_per_job is not None:
                payload["instances_per_job"] = self.instances_per_job
        else:
            payload["file_patterns"] = list(self.file_patterns)
            if self.files_per_job is not None:
                payload["files_per_job"] = self.files_per_job
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExtractionJobSetDefinition:
        strategy = ExtractionJobSetStrategy(str(data["strategy"]))
        raw_patterns = data.get("file_patterns") or []
        return cls(
            name=str(data["name"]),
            strategy=strategy,
            description=str(data["description"]).strip() if data.get("description") else None,
            entity_type=str(data["entity_type"]).strip() if data.get("entity_type") else None,
            instances_per_job=int(data["instances_per_job"])
            if data.get("instances_per_job") is not None
            else None,
            file_patterns=tuple(str(pattern) for pattern in raw_patterns),
            files_per_job=int(data["files_per_job"]) if data.get("files_per_job") is not None else None,
        )


@dataclass(frozen=True)
class ExtractionJobConfigDocument:
    """Persisted extraction job configuration for one knowledge graph."""

    version: str
    job_sets: tuple[ExtractionJobSetDefinition, ...] = field(default_factory=tuple)

    def validation_errors(self, *, entity_instance_counts: dict[str, int]) -> tuple[str, ...]:
        errors: list[str] = []
        seen_names: set[str] = set()
        for job_set in self.job_sets:
            if job_set.name in seen_names:
                errors.append(f"Duplicate job set name '{job_set.name}'.")
            seen_names.add(job_set.name)
            errors.extend(job_set.validation_errors(entity_instance_counts=entity_instance_counts))
        return tuple(errors)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "job_sets": [job_set.to_dict() for job_set in self.job_sets],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ExtractionJobConfigDocument | None:
        if not data:
            return None
        raw_sets = data.get("job_sets") or []
        return cls(
            version=str(data.get("version") or "1.0"),
            job_sets=tuple(ExtractionJobSetDefinition.from_dict(row) for row in raw_sets),
        )

    @classmethod
    def empty(cls) -> ExtractionJobConfigDocument:
        return cls(version="1.0", job_sets=())
