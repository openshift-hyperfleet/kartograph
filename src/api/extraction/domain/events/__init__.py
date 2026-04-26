"""Domain events for the Extraction bounded context."""

from __future__ import annotations

from extraction.domain.events.extraction import ExtractionFailed, MutationLogProduced

DomainEvent = MutationLogProduced | ExtractionFailed

__all__ = [
    "MutationLogProduced",
    "ExtractionFailed",
    "DomainEvent",
]
