"""Pydantic models for Knowledge Graph requests and responses."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from management.domain.aggregates import KnowledgeGraph
from management.domain.value_objects import (
    EdgeTypeDefinition,
    KnowledgeGraphWorkspaceStatus,
    NodeTypeDefinition,
    OntologyConfig,
    WorkspaceReadinessStatus,
    WorkspaceSessionPointers,
    WorkspaceMode,
)


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


class KnowledgeGraphResponse(BaseModel):
    """Response model for a knowledge graph."""

    id: str = Field(..., description="Knowledge Graph ID (ULID format)")
    tenant_id: str = Field(..., description="Tenant ID this KG belongs to")
    workspace_id: str = Field(..., description="Workspace ID this KG belongs to")
    name: str = Field(..., description="Knowledge graph name")
    description: str = Field(..., description="Knowledge graph description")
    workspace_mode: WorkspaceMode = Field(
        ...,
        description="Workspace lifecycle mode for this knowledge graph",
    )
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
            workspace_mode=kg.workspace_mode,
            created_at=kg.created_at,
            updated_at=kg.updated_at,
        )


class WorkspaceReadinessResponse(BaseModel):
    """Workspace readiness flags for bootstrap transition."""

    has_minimum_entity_types: bool
    has_minimum_relationship_types: bool
    prepopulated_types_ready: bool
    prepopulated_types_without_instances: list[str] = Field(default_factory=list)
    blocking_reasons: list[str] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, readiness: WorkspaceReadinessStatus) -> "WorkspaceReadinessResponse":
        return cls(
            has_minimum_entity_types=readiness.has_minimum_entity_types,
            has_minimum_relationship_types=readiness.has_minimum_relationship_types,
            prepopulated_types_ready=readiness.prepopulated_types_ready,
            prepopulated_types_without_instances=list(
                readiness.prepopulated_types_without_instances
            ),
            blocking_reasons=list(readiness.blocking_reasons),
        )


class WorkspaceSessionPointersResponse(BaseModel):
    """Session pointer projection for workspace status UI."""

    active_schema_bootstrap_session_id: str | None = None
    active_extraction_operations_session_id: str | None = None
    most_recent_completed_session_id: str | None = None

    @classmethod
    def from_domain(
        cls, pointers: WorkspaceSessionPointers
    ) -> "WorkspaceSessionPointersResponse":
        return cls(
            active_schema_bootstrap_session_id=pointers.active_schema_bootstrap_session_id,
            active_extraction_operations_session_id=(
                pointers.active_extraction_operations_session_id
            ),
            most_recent_completed_session_id=pointers.most_recent_completed_session_id,
        )


class KnowledgeGraphWorkspaceStatusResponse(BaseModel):
    """Mode/readiness/session status projection for a knowledge graph workspace."""

    knowledge_graph_id: str
    workspace_mode: WorkspaceMode
    readiness: WorkspaceReadinessResponse
    transition_eligible: bool
    session_pointers: WorkspaceSessionPointersResponse

    @classmethod
    def from_domain(
        cls, status: KnowledgeGraphWorkspaceStatus
    ) -> "KnowledgeGraphWorkspaceStatusResponse":
        return cls(
            knowledge_graph_id=status.knowledge_graph_id,
            workspace_mode=status.workspace_mode,
            readiness=WorkspaceReadinessResponse.from_domain(status.readiness),
            transition_eligible=status.transition_eligible,
            session_pointers=WorkspaceSessionPointersResponse.from_domain(
                status.session_pointers
            ),
        )


# ---------------------------------------------------------------------------
# Ontology models
# ---------------------------------------------------------------------------


class NodeTypeDefinitionModel(BaseModel):
    """API model for a node type definition in an ontology."""

    label: str = Field(..., description="Node type label (unique within ontology)")
    description: str = Field(default="", description="Human-readable description")
    required_properties: list[str] = Field(
        default_factory=list,
        description="Properties every node of this type must have",
    )
    optional_properties: list[str] = Field(
        default_factory=list,
        description="Properties nodes of this type may optionally have",
    )
    prepopulated: bool = Field(
        default=False,
        description="Whether this type must have at least one instance before transition",
    )
    prepopulated_instance_count: int = Field(
        default=0,
        ge=0,
        description="Current known instance count used for readiness evaluation",
    )

    def to_domain(self) -> NodeTypeDefinition:
        """Convert to domain NodeTypeDefinition value object."""
        return NodeTypeDefinition(
            label=self.label,
            description=self.description,
            required_properties=tuple(self.required_properties),
            optional_properties=tuple(self.optional_properties),
            prepopulated=self.prepopulated,
            prepopulated_instance_count=self.prepopulated_instance_count,
        )

    @classmethod
    def from_domain(cls, nt: NodeTypeDefinition) -> NodeTypeDefinitionModel:
        """Convert from domain NodeTypeDefinition value object."""
        return cls(
            label=nt.label,
            description=nt.description,
            required_properties=list(nt.required_properties),
            optional_properties=list(nt.optional_properties),
            prepopulated=nt.prepopulated,
            prepopulated_instance_count=nt.prepopulated_instance_count,
        )


class EdgeTypeDefinitionModel(BaseModel):
    """API model for an edge type definition in an ontology."""

    label: str = Field(..., description="Edge type label (unique within ontology)")
    description: str = Field(default="", description="Human-readable description")
    source_labels: list[str] = Field(
        default_factory=list,
        description="Node type labels allowed as sources",
    )
    target_labels: list[str] = Field(
        default_factory=list,
        description="Node type labels allowed as targets",
    )
    properties: list[str] = Field(
        default_factory=list,
        description="Properties this edge type may carry",
    )

    def to_domain(self) -> EdgeTypeDefinition:
        """Convert to domain EdgeTypeDefinition value object."""
        return EdgeTypeDefinition(
            label=self.label,
            description=self.description,
            source_labels=tuple(self.source_labels),
            target_labels=tuple(self.target_labels),
            properties=tuple(self.properties),
        )

    @classmethod
    def from_domain(cls, et: EdgeTypeDefinition) -> EdgeTypeDefinitionModel:
        """Convert from domain EdgeTypeDefinition value object."""
        return cls(
            label=et.label,
            description=et.description,
            source_labels=list(et.source_labels),
            target_labels=list(et.target_labels),
            properties=list(et.properties),
        )


class OntologyConfigRequest(BaseModel):
    """Request body for PUT /knowledge-graphs/{id}/ontology.

    Performs a full replace of the stored ontology — no partial merges.
    """

    node_types: list[NodeTypeDefinitionModel] = Field(
        default_factory=list,
        description="Node type definitions for the ontology",
    )
    edge_types: list[EdgeTypeDefinitionModel] = Field(
        default_factory=list,
        description="Edge type definitions for the ontology",
    )
    approved_at: datetime | None = Field(
        default=None,
        description="ISO-8601 timestamp when the user approved this ontology",
    )

    def to_domain(self) -> OntologyConfig:
        """Convert to domain OntologyConfig value object."""
        return OntologyConfig(
            node_types=tuple(nt.to_domain() for nt in self.node_types),
            edge_types=tuple(et.to_domain() for et in self.edge_types),
            approved_at=self.approved_at,
        )


class OntologyConfigResponse(BaseModel):
    """Response for GET/PUT /knowledge-graphs/{id}/ontology."""

    node_types: list[NodeTypeDefinitionModel] = Field(
        ..., description="Node type definitions"
    )
    edge_types: list[EdgeTypeDefinitionModel] = Field(
        ..., description="Edge type definitions"
    )
    approved_at: datetime | None = Field(
        None, description="When the ontology was approved; null if not yet approved"
    )

    @classmethod
    def from_domain(cls, config: OntologyConfig) -> OntologyConfigResponse:
        """Convert from domain OntologyConfig value object."""
        return cls(
            node_types=[
                NodeTypeDefinitionModel.from_domain(nt) for nt in config.node_types
            ],
            edge_types=[
                EdgeTypeDefinitionModel.from_domain(et) for et in config.edge_types
            ],
            approved_at=config.approved_at,
        )
