"""Domain types for materialized extraction jobs and runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class ExtractionJobStatus(StrEnum):
    """Lifecycle status for one materialized extraction job."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ExtractionRunStatus(StrEnum):
    """Orchestrator state for one knowledge graph extraction run."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSING = "pausing"
    PAUSED = "paused"
    HALTED = "halted"


@dataclass(frozen=True)
class ExtractionTargetFile:
    """One repository file assigned to an extraction job."""

    path: str
    repository_folder: str
    package_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "repository_folder": self.repository_folder,
            "package_id": self.package_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExtractionTargetFile:
        return cls(
            path=str(data.get("path") or ""),
            repository_folder=str(data.get("repository_folder") or ""),
            package_id=str(data.get("package_id") or ""),
        )


@dataclass(frozen=True)
class ExtractionTargetInstance:
    """One entity instance assigned to an extraction job."""

    slug: str
    entity_type: str
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "entity_type": self.entity_type,
            "properties": dict(self.properties),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExtractionTargetInstance:
        return cls(
            slug=str(data.get("slug") or ""),
            entity_type=str(data.get("entity_type") or ""),
            properties=dict(data.get("properties") or {}),
        )


@dataclass(frozen=True)
class ExtractionJobRecord:
    """One persisted extraction job row."""

    id: str
    knowledge_graph_id: str
    job_id: str
    job_set_name: str
    strategy: str
    status: ExtractionJobStatus
    order_index: int
    description: str
    target_instances: tuple[ExtractionTargetInstance, ...] = field(default_factory=tuple)
    target_files: tuple[ExtractionTargetFile, ...] = field(default_factory=tuple)
    worker_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    attempt: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    cost_usd: float = 0.0
    entities_created: int = 0
    entities_modified: int = 0
    relationships_created: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "knowledge_graph_id": self.knowledge_graph_id,
            "job_id": self.job_id,
            "job_set": self.job_set_name,
            "job_set_name": self.job_set_name,
            "strategy": self.strategy,
            "status": self.status.value,
            "order_index": self.order_index,
            "description": self.description,
            "target_instances": [instance.to_dict() for instance in self.target_instances],
            "target_files": [target_file.to_dict() for target_file in self.target_files],
            "worker_id": self.worker_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "attempt": self.attempt,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_creation_tokens": self.cache_creation_tokens,
            "cost_usd": self.cost_usd,
            "entities_created": self.entities_created,
            "entities_modified": self.entities_modified,
            "relationships_created": self.relationships_created,
            "instance_count": len(self.target_instances),
            "file_count": len(self.target_files),
        }


@dataclass(frozen=True)
class ExtractionRunRecord:
    """Orchestrator run metadata for one knowledge graph."""

    id: str
    knowledge_graph_id: str
    status: ExtractionRunStatus
    worker_count: int
    started_at: datetime | None = None
    completed_at: datetime | None = None
    pause_requested: bool = False
    orchestrator_pid: int | None = None
