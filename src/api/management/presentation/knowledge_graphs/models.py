"""Request and response models for Knowledge Graph API endpoints.

Pydantic models for serializing/deserializing knowledge graph data
in the Management bounded context REST API.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from management.domain.aggregates import KnowledgeGraph


class CreateKnowledgeGraphRequest(BaseModel):
    """Request body for creating a knowledge graph.

    Attributes:
        name: Knowledge graph name (1-100 characters)
        description: Description of the knowledge graph
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Knowledge graph name",
        examples=["Platform Graph", "Security Graph"],
    )
    description: str = Field(
        default="",
        description="Description of the knowledge graph",
        examples=["Unified knowledge graph for platform services"],
    )


class UpdateKnowledgeGraphRequest(BaseModel):
    """Request body for updating a knowledge graph's metadata.

    Attributes:
        name: New knowledge graph name (1-100 characters)
        description: New description
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Knowledge graph name",
        examples=["Updated Platform Graph"],
    )
    description: str = Field(
        default="",
        description="Description of the knowledge graph",
        examples=["Updated description"],
    )


class KnowledgeGraphResponse(BaseModel):
    """Response containing knowledge graph details.

    Attributes:
        id: Knowledge graph ID (ULID, 26 characters)
        tenant_id: Tenant this knowledge graph belongs to
        workspace_id: Workspace this knowledge graph is contained in
        name: Knowledge graph name
        description: Description of the knowledge graph
        created_at: Creation timestamp (ISO 8601)
        updated_at: Last update timestamp (ISO 8601)
    """

    id: str = Field(..., description="Knowledge graph ID (ULID format)")
    tenant_id: str = Field(..., description="Tenant ID this knowledge graph belongs to")
    workspace_id: str = Field(
        ..., description="Workspace ID this knowledge graph is contained in"
    )
    name: str = Field(..., description="Knowledge graph name")
    description: str = Field(..., description="Description of the knowledge graph")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_domain(cls, kg: KnowledgeGraph) -> KnowledgeGraphResponse:
        """Convert a KnowledgeGraph domain aggregate to an API response.

        Args:
            kg: KnowledgeGraph domain aggregate

        Returns:
            KnowledgeGraphResponse with serializable fields
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
    """Response containing a list of knowledge graphs.

    Attributes:
        knowledge_graphs: List of knowledge graph details
        count: Total number of knowledge graphs returned
    """

    knowledge_graphs: list[KnowledgeGraphResponse] = Field(
        ..., description="List of knowledge graphs"
    )
    count: int = Field(..., description="Number of knowledge graphs returned")
