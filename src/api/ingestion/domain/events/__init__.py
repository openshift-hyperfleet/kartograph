"""Domain events for the Ingestion bounded context."""

from __future__ import annotations

from ingestion.domain.events.sync import IngestionFailed, JobPackageProduced

DomainEvent = JobPackageProduced | IngestionFailed

__all__ = [
    "JobPackageProduced",
    "IngestionFailed",
    "DomainEvent",
]
