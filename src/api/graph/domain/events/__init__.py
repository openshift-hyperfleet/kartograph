"""Domain events for the Graph bounded context."""

from __future__ import annotations

from graph.domain.events.graph import MutationApplicationFailed, MutationsApplied

DomainEvent = MutationsApplied | MutationApplicationFailed

__all__ = [
    "MutationsApplied",
    "MutationApplicationFailed",
    "DomainEvent",
]
