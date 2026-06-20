"""Pydantic models for Knowledge Graph requests and responses."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from management.domain.aggregates import KnowledgeGraph
from management.domain.value_objects import (
    EdgeTypeDefinition,
    KnowledgeGraphMaintenanceRunRecord,
    KnowledgeGraphMaintenanceSchedule,
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
    prepopulated_relationship_types_without_instances: list[str] = Field(
        default_factory=list
    )
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
            prepopulated_relationship_types_without_instances=list(
                readiness.prepopulated_relationship_types_without_instances
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


class MaintenanceScheduleUpsertRequest(BaseModel):
    """Request body for KG maintenance schedule upsert."""

    enabled: bool = Field(
        default=True,
        description="Whether scheduled maintenance is enabled for this KG",
    )
    cron_expression: str = Field(
        default="0 2 * * *",
        description="Cron expression interpreted in timezone_name",
    )
    timezone_name: str = Field(
        default="UTC",
        description="IANA timezone identifier used for schedule evaluation",
    )
    files_per_job: int = Field(
        default=2,
        ge=1,
        description="Number of changed files batched into each maintenance job",
    )
    worker_count: int = Field(
        default=8,
        ge=1,
        description="Parallel OpenShell workers for maintenance extraction",
    )


class MaintenanceStartReadyRequest(BaseModel):
    """Request body for starting workers on queued maintenance jobs."""

    worker_count: int = Field(
        default=8,
        ge=1,
        description="Parallel OpenShell workers for ready maintenance jobs",
    )


class MaintenanceStartReadyResponse(BaseModel):
    """Response after starting workers for ready maintenance jobs."""

    success: bool
    message: str
    pending_jobs: int
    in_progress_jobs: int
    worker_count: int


class MaintenanceRegenerateJobsRequest(BaseModel):
    """Request body for regenerating pending maintenance jobs."""

    files_per_job: int = Field(
        default=2,
        ge=1,
        description="Number of changed files batched into each maintenance job",
    )


class MaintenanceRegenerateJobsResponse(BaseModel):
    """Response after regenerating pending maintenance jobs."""

    success: bool
    message: str
    generated_jobs: int


class MaintenanceRunTriggerRequest(BaseModel):
    """Request body for manual KG maintenance orchestration."""

    files_per_job: int = Field(
        default=2,
        ge=1,
        description="Number of changed files batched into each maintenance job",
    )
    worker_count: int = Field(
        default=8,
        ge=1,
        description="Parallel OpenShell workers for maintenance extraction",
    )
    start_extraction: bool = Field(
        default=True,
        description=(
            "When true, advance to extraction after ingest completes "
            "(may return ingest-started if ingest is still running)"
        ),
    )


class MaintenanceScheduleResponse(BaseModel):
    """Response model for KG maintenance schedule configuration."""

    enabled: bool
    cron_expression: str
    timezone_name: str
    next_run_at: datetime | None
    files_per_job: int
    worker_count: int

    @classmethod
    def from_domain(
        cls, schedule: KnowledgeGraphMaintenanceSchedule
    ) -> "MaintenanceScheduleResponse":
        return cls(
            enabled=schedule.enabled,
            cron_expression=schedule.cron_expression,
            timezone_name=schedule.timezone_name,
            next_run_at=schedule.next_run_at,
            files_per_job=schedule.files_per_job,
            worker_count=schedule.worker_count,
        )


class MaintenanceRunResponse(BaseModel):
    """Response model for an individual KG maintenance run outcome."""

    run_id: str
    triggered_at: datetime
    outcome: str
    message: str | None
    target_data_source_ids: list[str]
    sync_run_ids: list[str] = Field(default_factory=list)
    changed_file_count: int | None = None
    jobs_materialized: int | None = None
    files_per_job: int | None = None
    worker_count: int | None = None

    @classmethod
    def from_domain(
        cls, run: KnowledgeGraphMaintenanceRunRecord
    ) -> "MaintenanceRunResponse":
        return cls(
            run_id=run.run_id,
            triggered_at=run.triggered_at,
            outcome=run.outcome.value,
            message=run.message,
            target_data_source_ids=list(run.target_data_source_ids),
            sync_run_ids=list(run.sync_run_ids),
            changed_file_count=run.changed_file_count,
            jobs_materialized=run.jobs_materialized,
            files_per_job=run.files_per_job,
            worker_count=run.worker_count,
        )


class MaintenanceRunListResponse(BaseModel):
    """Response model for KG maintenance run history."""

    runs: list[MaintenanceRunResponse]
    count: int


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
    instance_generator: str | None = Field(
        default=None,
        description="Optional workspace-relative script under instance_generators/ for prepopulation",
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
            instance_generator=self.instance_generator,
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
            instance_generator=nt.instance_generator,
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
    prepopulated: bool = Field(
        default=False,
        description=(
            "Whether this relationship type must have instances before transition; "
            "requires all source and target entity types to be prepopulated"
        ),
    )
    prepopulated_instance_count: int = Field(
        default=0,
        ge=0,
        description="Current known instance count used for readiness evaluation",
    )
    instance_generator: str | None = Field(
        default=None,
        description="Optional workspace-relative script under instance_generators/ for prepopulation",
    )
    bidirectional: bool = Field(
        default=True,
        description="When true, platform auto-generates inverse type and twin edge instances",
    )
    inverse_label: str | None = Field(
        default=None,
        description="Optional explicit inverse relationship label (primary types only)",
    )
    inverse_of: str | None = Field(
        default=None,
        description="Primary label this auto-generated inverse type mirrors",
    )
    auto_generated: bool = Field(
        default=False,
        description="True when this edge type was created by bidirectional pairing",
    )

    def to_domain(self) -> EdgeTypeDefinition:
        """Convert to domain EdgeTypeDefinition value object."""
        return EdgeTypeDefinition(
            label=self.label,
            description=self.description,
            source_labels=tuple(self.source_labels),
            target_labels=tuple(self.target_labels),
            properties=tuple(self.properties),
            prepopulated=self.prepopulated,
            prepopulated_instance_count=self.prepopulated_instance_count,
            instance_generator=self.instance_generator,
            bidirectional=self.bidirectional,
            inverse_label=self.inverse_label,
            inverse_of=self.inverse_of,
            auto_generated=self.auto_generated,
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
            prepopulated=et.prepopulated,
            prepopulated_instance_count=et.prepopulated_instance_count,
            instance_generator=et.instance_generator,
            bidirectional=et.bidirectional,
            inverse_label=et.inverse_label,
            inverse_of=et.inverse_of,
            auto_generated=et.auto_generated,
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


class DesignArtifactInstanceModel(BaseModel):
    """One entity or relationship instance surfaced in design artifacts."""

    slug: str | None = None
    source_slug: str | None = None
    target_slug: str | None = None
    properties: dict[str, object] = Field(default_factory=dict)


class DesignArtifactEntityTypeModel(BaseModel):
    """Entity type definition merged with live instance counts."""

    type: str
    description: str = ""
    required_properties: list[str] = Field(default_factory=list)
    optional_properties: list[str] = Field(default_factory=list)
    property_definitions: dict[str, str] = Field(default_factory=dict)
    prepopulated_instances: bool | str = False
    instance_count: int = 0
    instances_returned: int = 0
    instances_truncated: bool = False
    instances: list[DesignArtifactInstanceModel] = Field(default_factory=list)


class DesignArtifactRelationshipTypeModel(BaseModel):
    """Relationship type definition merged with live instance counts."""

    key: str
    source_entity_type: str
    target_entity_type: str
    relationship_type: str
    reverse_relationship_type: str | None = None
    reverse_relationship_description: str | None = None
    prepopulated_instances: bool | str = False
    description: str | None = None
    instance_count: int = 0
    instances_returned: int = 0
    instances_truncated: bool = False
    instances: list[DesignArtifactInstanceModel] = Field(default_factory=list)
    required_parameters: list[str] = Field(default_factory=list)
    optional_parameters: list[str] = Field(default_factory=list)
    parameter_definitions: dict[str, str] = Field(default_factory=dict)


class DesignArtifactsCountsModel(BaseModel):
    """Aggregate counts for design artifact navigation."""

    entity_types: int = 0
    relationship_types: int = 0
    entity_instances: int = 0
    relationship_instances: int = 0


class DesignArtifactsLimitsModel(BaseModel):
    """Truncation metadata for instance payloads."""

    requested: int
    instances_per_type: int = 0
    entity_instances_returned: int
    relationship_instances_returned: int
    entity_instances_truncated: bool
    relationship_instances_truncated: bool


class DesignArtifactInstanceListResponse(BaseModel):
    """Paginated entity instances for one type."""

    entity_type: str
    instances: list[DesignArtifactInstanceModel] = Field(default_factory=list)
    count: int = 0
    total: int = 0
    limit: int = 100
    offset: int = 0
    property_name: str | None = None
    property_value: str | None = None


class DesignArtifactRelationshipInstanceListResponse(BaseModel):
    """Paginated relationship instances for one type triple."""

    relationship_type: str
    source_entity_type: str | None = None
    target_entity_type: str | None = None
    instances: list[DesignArtifactInstanceModel] = Field(default_factory=list)
    count: int = 0
    total: int = 0
    limit: int = 100
    offset: int = 0
    property_name: str | None = None
    property_value: str | None = None


class DesignArtifactsResponse(BaseModel):
    """Canonical schema plus live graph instances for Graph Management UI."""

    found: bool
    knowledge_graph_id: str
    entities: dict[str, DesignArtifactEntityTypeModel]
    relationships: list[DesignArtifactRelationshipTypeModel]
    counts: DesignArtifactsCountsModel
    limits: DesignArtifactsLimitsModel
