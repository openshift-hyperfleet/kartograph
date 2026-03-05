"""Domain events for Management bounded context.

Domain events capture facts about things that have happened in the domain.
They are immutable value objects that carry all the information needed
to describe the occurrence of an event.
"""

from __future__ import annotations

from management.domain.events.data_source import (
    DataSourceCreated,
    DataSourceDeleted,
    DataSourceUpdated,
    SyncRequested,
)
from management.domain.events.knowledge_graph import (
    KnowledgeGraphCreated,
    KnowledgeGraphDeleted,
    KnowledgeGraphUpdated,
)

# Type alias for all domain events in the Management context
DomainEvent = (
    KnowledgeGraphCreated
    | KnowledgeGraphUpdated
    | KnowledgeGraphDeleted
    | DataSourceCreated
    | DataSourceUpdated
    | DataSourceDeleted
    | SyncRequested
)

__all__ = [
    # KnowledgeGraph events
    "KnowledgeGraphCreated",
    "KnowledgeGraphUpdated",
    "KnowledgeGraphDeleted",
    # DataSource events
    "DataSourceCreated",
    "DataSourceUpdated",
    "DataSourceDeleted",
    "SyncRequested",
    # Type alias
    "DomainEvent",
]
