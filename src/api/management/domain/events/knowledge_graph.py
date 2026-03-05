"""Domain events for KnowledgeGraph aggregate."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class KnowledgeGraphCreated:
    """Emitted when a new knowledge graph is created.

    Attributes:
        knowledge_graph_id: The ID of the created knowledge graph
        tenant_id: The tenant that owns this knowledge graph
        workspace_id: The workspace containing this knowledge graph
        name: The name given to the knowledge graph
        description: The description of the knowledge graph
        occurred_at: When the event occurred
        created_by: The user who created the knowledge graph (if known)
    """

    knowledge_graph_id: str
    tenant_id: str
    workspace_id: str
    name: str
    description: str
    occurred_at: datetime
    created_by: str | None = None


@dataclass(frozen=True)
class KnowledgeGraphUpdated:
    """Emitted when a knowledge graph's metadata is updated.

    Attributes:
        knowledge_graph_id: The ID of the updated knowledge graph
        tenant_id: The tenant that owns this knowledge graph
        name: The new name of the knowledge graph
        description: The new description of the knowledge graph
        occurred_at: When the event occurred
        updated_by: The user who updated the knowledge graph (if known)
    """

    knowledge_graph_id: str
    tenant_id: str
    name: str
    description: str
    occurred_at: datetime
    updated_by: str | None = None


@dataclass(frozen=True)
class KnowledgeGraphDeleted:
    """Emitted when a knowledge graph is marked for deletion.

    Includes workspace_id to enable SpiceDB relationship cleanup
    for the workspace-knowledge_graph relationship.

    Attributes:
        knowledge_graph_id: The ID of the deleted knowledge graph
        tenant_id: The tenant that owned this knowledge graph
        workspace_id: The workspace that contained this knowledge graph
        occurred_at: When the event occurred
        deleted_by: The user who deleted the knowledge graph (if known)
    """

    knowledge_graph_id: str
    tenant_id: str
    workspace_id: str
    occurred_at: datetime
    deleted_by: str | None = None
