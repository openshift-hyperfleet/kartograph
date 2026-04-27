"""Pydantic models for Knowledge Graph requests and responses."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from management.domain.aggregates import KnowledgeGraph


class CreateKnowledgeGraphRequest(BaseModel):
    """Request model for creating a knowledge graph."""

    name: str = Field(
        ...,
        description="Name of the knowledge graph",
        min_length=1,
        max_length=100,
    )
    description: str = Field(
        default="",
        description="Optional description of the knowledge graph",
    )


class UpdateKnowledgeGraphRequest(BaseModel):
    """Request model for updating a knowledge graph.

    All fields are required — this is a full metadata update.
    """

    name: str = Field(
        ...,
        description="New name of the knowledge graph",
        min_length=1,
        max_length=100,
    )
    description: str = Field(
        default="",
        description="New description of the knowledge graph",
    )


class KnowledgeGraphListResponse(BaseModel):
    """Response containing a list of knowledge graphs.

    Attributes:
        knowledge_graphs: List of knowledge graph details
        count: Total number of knowledge graphs returned
    """

    knowledge_graphs: list[KnowledgeGraphResponse] = Field(
        ..., description="List of knowledge graphs"
    )
    count: int = Field(..., description="Number of knowledge graphs returned")


class UpdateKnowledgeGraphRequest(BaseModel):
    """Request body for updating a knowledge graph's metadata.

    Attributes:
        name: New name for the knowledge graph
        description: New description for the knowledge graph
    """

    name: str = Field(
        ...,
        description="New name for the knowledge graph",
        min_length=1,
        max_length=100,
    )
    description: str = Field(
        default="",
        description="New description for the knowledge graph",
    )
    count: int = Field(
        default=0,
        description="Total number of knowledge graphs returned",
    )


class KnowledgeGraphResponse(BaseModel):
    """Response model for a knowledge graph."""

    id: str = Field(..., description="Knowledge Graph ID (ULID format)")
    tenant_id: str = Field(..., description="Tenant ID this KG belongs to")
    workspace_id: str = Field(..., description="Workspace ID this KG belongs to")
    name: str = Field(..., description="Knowledge graph name")
    description: str = Field(..., description="Knowledge graph description")
    created_at: datetime = Field(..., description="When the KG was created")
    updated_at: datetime = Field(..., description="When the KG was last updated")

    @classmethod
    def from_domain(cls, kg: KnowledgeGraph) -> KnowledgeGraphResponse:
        """Convert domain KnowledgeGraph aggregate to API response.

        Args:
            kg: KnowledgeGraph domain aggregate

        Returns:
            KnowledgeGraphResponse with KG details
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
