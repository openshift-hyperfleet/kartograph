"""Request and response models for Knowledge Graph API endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from management.domain.aggregates import KnowledgeGraph


class CreateKnowledgeGraphRequest(BaseModel):
    """Request to create a knowledge graph.

    Attributes:
        name: Knowledge graph name (1-100 characters)
        description: Optional description (defaults to empty string)
    """

    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="")


class UpdateKnowledgeGraphRequest(BaseModel):
    """Request to partially update a knowledge graph.

    Attributes:
        name: Optional new name (1-100 characters)
        description: Optional new description
    """

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None)


class KnowledgeGraphResponse(BaseModel):
    """Response containing knowledge graph details.

    Attributes:
        id: Knowledge graph ID (ULID)
        tenant_id: Tenant ID this knowledge graph belongs to
        workspace_id: Workspace ID containing this knowledge graph
        name: Knowledge graph name
        description: Knowledge graph description
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """

    id: str
    tenant_id: str
    workspace_id: str
    name: str
    description: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, kg: KnowledgeGraph) -> KnowledgeGraphResponse:
        """Convert domain KnowledgeGraph aggregate to API response.

        Args:
            kg: KnowledgeGraph domain aggregate

        Returns:
            KnowledgeGraphResponse with knowledge graph details
        """
        return cls(
            id=kg.id.value,
            tenant_id=kg.tenant_id,
            workspace_id=kg.workspace_id,
            name=kg.name,
            description=kg.description,
            created_at=kg.created_at,
            updated_at=kg.updated_at,
        )


class KnowledgeGraphListResponse(BaseModel):
    """Response containing a paginated list of knowledge graphs.

    Attributes:
        items: List of knowledge graph details
        total: Total number of knowledge graphs (before pagination)
        offset: Number of items skipped
        limit: Maximum number of items returned
    """

    items: list[KnowledgeGraphResponse]
    total: int
    offset: int
    limit: int
