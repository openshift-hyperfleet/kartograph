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


class KnowledgeGraphListResponse(BaseModel):
    """Response model for listing knowledge graphs."""

    knowledge_graphs: list[KnowledgeGraphResponse] = Field(
        ...,
        description="List of knowledge graphs",
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
