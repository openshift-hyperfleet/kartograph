"""Pydantic models for Data Source requests and responses."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from management.application.services.data_source_service import DataSourceWithLatestRun
from management.domain.aggregates import DataSource
from management.domain.entities import DataSourceSyncRun
from management.domain.value_objects import Ontology, OntologyEdgeType, OntologyNodeType


class OntologyNodeTypeModel(BaseModel):
    """Pydantic model for an ontology node type."""

    label: str = Field(..., description="Node type label (e.g. 'Repository')")
    description: str | None = Field(None, description="Optional description")
    required_properties: list[str] = Field(
        default_factory=list,
        description="Property names that must be present on nodes of this type",
    )
    optional_properties: list[str] = Field(
        default_factory=list,
        description="Property names that may be present on nodes of this type",
    )

    @classmethod
    def from_domain(cls, node_type: OntologyNodeType) -> OntologyNodeTypeModel:
        """Convert domain OntologyNodeType to API model."""
        return cls(
            label=node_type.label,
            description=node_type.description,
            required_properties=list(node_type.required_properties),
            optional_properties=list(node_type.optional_properties),
        )

    def to_domain(self) -> OntologyNodeType:
        """Convert API model to domain OntologyNodeType."""
        return OntologyNodeType(
            label=self.label,
            description=self.description,
            required_properties=list(self.required_properties),
            optional_properties=list(self.optional_properties),
        )


class OntologyEdgeTypeModel(BaseModel):
    """Pydantic model for an ontology edge type."""

    label: str = Field(..., description="Edge type label (e.g. 'HAS_PR')")
    from_type: str = Field(..., description="Source node type label")
    to_type: str = Field(..., description="Target node type label")
    description: str | None = Field(None, description="Optional description")
    required_properties: list[str] = Field(
        default_factory=list,
        description="Property names that must be present on edges of this type",
    )
    optional_properties: list[str] = Field(
        default_factory=list,
        description="Property names that may be present on edges of this type",
    )

    @classmethod
    def from_domain(cls, edge_type: OntologyEdgeType) -> OntologyEdgeTypeModel:
        """Convert domain OntologyEdgeType to API model."""
        return cls(
            label=edge_type.label,
            from_type=edge_type.from_type,
            to_type=edge_type.to_type,
            description=edge_type.description,
            required_properties=list(edge_type.required_properties),
            optional_properties=list(edge_type.optional_properties),
        )

    def to_domain(self) -> OntologyEdgeType:
        """Convert API model to domain OntologyEdgeType."""
        return OntologyEdgeType(
            label=self.label,
            from_type=self.from_type,
            to_type=self.to_type,
            description=self.description,
            required_properties=list(self.required_properties),
            optional_properties=list(self.optional_properties),
        )


class OntologyModel(BaseModel):
    """Pydantic model for an ontology."""

    node_types: list[OntologyNodeTypeModel] = Field(
        default_factory=list,
        description="Node type definitions",
    )
    edge_types: list[OntologyEdgeTypeModel] = Field(
        default_factory=list,
        description="Edge type definitions",
    )

    @classmethod
    def from_domain(cls, ontology: Ontology) -> OntologyModel:
        """Convert domain Ontology to API model."""
        return cls(
            node_types=[
                OntologyNodeTypeModel.from_domain(nt) for nt in ontology.node_types
            ],
            edge_types=[
                OntologyEdgeTypeModel.from_domain(et) for et in ontology.edge_types
            ],
        )

    def to_domain(self) -> Ontology:
        """Convert API model to domain Ontology."""
        return Ontology(
            node_types=[nt.to_domain() for nt in self.node_types],
            edge_types=[et.to_domain() for et in self.edge_types],
        )


class CreateDataSourceRequest(BaseModel):
    """Request model for creating a data source."""

    name: str = Field(
        ...,
        description="Name of the data source",
        min_length=1,
        max_length=100,
    )
    adapter_type: str = Field(
        ...,
        description="Adapter type (e.g., 'github')",
    )
    connection_config: dict = Field(
        ...,
        description="Connection configuration key-value pairs for the adapter",
    )
    credentials: dict | None = Field(
        default=None,
        description="Optional credentials to encrypt and store securely",
    )
    ontology: OntologyModel | None = Field(
        default=None,
        description="Optional initial approved ontology for this data source",
    )


class UpdateDataSourceRequest(BaseModel):
    """Request model for updating a data source.

    All fields are optional — only the fields provided are updated.
    At least one field should be provided, though the server will accept
    an empty body (resulting in a no-op).
    """

    name: str | None = Field(
        default=None,
        description="New name for the data source",
        min_length=1,
        max_length=100,
    )
    connection_config: dict | None = Field(
        default=None,
        description="Updated connection configuration key-value pairs",
    )
    credentials: dict | None = Field(
        default=None,
        description="New credentials to encrypt and store (replaces existing)",
    )
    ontology: OntologyModel | None = Field(
        default=None,
        description="Updated approved ontology (replaces existing)",
    )


class DataSourceResponse(BaseModel):
    """Response model for a data source."""

    id: str = Field(..., description="Data Source ID (ULID format)")
    knowledge_graph_id: str = Field(
        ..., description="Knowledge Graph ID this DS belongs to"
    )
    tenant_id: str = Field(..., description="Tenant ID this DS belongs to")
    name: str = Field(..., description="Data source name")
    adapter_type: str = Field(..., description="Adapter type (e.g., 'github')")
    schedule_type: str = Field(
        ..., description="Schedule type (e.g., 'manual', 'cron')"
    )
    last_sync_at: datetime | None = Field(
        None, description="When the last sync completed"
    )
    clone_head_commit: str | None = Field(
        None, description="Latest known commit in the local/ingested clone"
    )
    last_extraction_baseline_commit: str | None = Field(
        None, description="Commit used as baseline during the last extraction run"
    )
    tracked_branch_head_commit: str | None = Field(
        None, description="Latest known commit at the tracked source branch head"
    )
    created_at: datetime = Field(..., description="When the DS was created")
    updated_at: datetime = Field(..., description="When the DS was last updated")
    ontology: OntologyModel | None = Field(
        None,
        description="Approved ontology for this data source, or null if not yet set",
    )

    @classmethod
    def from_domain(cls, ds: DataSource) -> DataSourceResponse:
        """Convert domain DataSource aggregate to API response.

        Args:
            ds: DataSource domain aggregate

        Returns:
            DataSourceResponse with DS details
        """
        return cls(
            id=ds.id.value,
            knowledge_graph_id=ds.knowledge_graph_id,
            tenant_id=ds.tenant_id,
            name=ds.name,
            adapter_type=ds.adapter_type.value,
            schedule_type=ds.schedule.schedule_type.value,
            last_sync_at=ds.last_sync_at,
            clone_head_commit=ds.clone_head_commit,
            last_extraction_baseline_commit=ds.last_extraction_baseline_commit,
            tracked_branch_head_commit=ds.tracked_branch_head_commit,
            created_at=ds.created_at,
            updated_at=ds.updated_at,
            ontology=(
                OntologyModel.from_domain(ds.ontology)
                if ds.ontology is not None
                else None
            ),
        )


class SyncRunLogsResponse(BaseModel):
    """Response model for sync run log lines."""

    logs: list[str] = Field(
        default_factory=list,
        description="Ordered log lines captured during this sync run",
    )


class SyncRunResponse(BaseModel):
    """Response model for a data source sync run."""

    id: str = Field(..., description="Sync Run ID (ULID format)")
    data_source_id: str = Field(..., description="Data Source ID this run belongs to")
    status: str = Field(
        ...,
        description="Sync run status (pending, ingesting, ai_extracting, applying, completed, failed)",
    )
    started_at: datetime = Field(..., description="When the sync run started")
    completed_at: datetime | None = Field(
        None, description="When the sync run completed"
    )
    error: str | None = Field(None, description="Error message if the sync run failed")
    created_at: datetime = Field(
        ..., description="When the sync run record was created"
    )

    @classmethod
    def from_domain(cls, run: DataSourceSyncRun) -> SyncRunResponse:
        """Convert domain DataSourceSyncRun entity to API response.

        Args:
            run: DataSourceSyncRun domain entity

        Returns:
            SyncRunResponse with sync run details
        """
        return cls(
            id=run.id,
            data_source_id=run.data_source_id,
            status=run.status,
            started_at=run.started_at,
            completed_at=run.completed_at,
            error=run.error,
            created_at=run.created_at,
        )


class DataSourceWithSyncResponse(BaseModel):
    """Data source response with embedded latest sync run.

    Used by GET /management/data-sources (flat list) to return all data
    sources in the tenant with their most recent sync status in a single
    API call — enabling the sidebar navigation badge.
    """

    id: str = Field(..., description="Data Source ID (ULID format)")
    knowledge_graph_id: str = Field(
        ..., description="Knowledge Graph ID this DS belongs to"
    )
    tenant_id: str = Field(..., description="Tenant ID this DS belongs to")
    name: str = Field(..., description="Data source name")
    adapter_type: str = Field(..., description="Adapter type (e.g., 'github')")
    schedule_type: str = Field(
        ..., description="Schedule type (e.g., 'manual', 'cron')"
    )
    last_sync_at: datetime | None = Field(
        None, description="When the last sync completed"
    )
    clone_head_commit: str | None = Field(
        None, description="Latest known commit in the local/ingested clone"
    )
    last_extraction_baseline_commit: str | None = Field(
        None, description="Commit used as baseline during the last extraction run"
    )
    tracked_branch_head_commit: str | None = Field(
        None, description="Latest known commit at the tracked source branch head"
    )
    created_at: datetime = Field(..., description="When the DS was created")
    updated_at: datetime = Field(..., description="When the DS was last updated")
    ontology: OntologyModel | None = Field(
        None,
        description="Approved ontology for this data source, or null if not yet set",
    )
    latest_sync_run: SyncRunResponse | None = Field(
        None,
        description="Most recent sync run, or null if the data source has never synced",
    )

    @classmethod
    def from_domain_pair(
        cls, pair: DataSourceWithLatestRun
    ) -> DataSourceWithSyncResponse:
        """Convert a DataSourceWithLatestRun pair to API response.

        Args:
            pair: DataSourceWithLatestRun from the application service

        Returns:
            DataSourceWithSyncResponse with DS details and embedded sync run
        """
        ds = pair.data_source
        return cls(
            id=ds.id.value,
            knowledge_graph_id=ds.knowledge_graph_id,
            tenant_id=ds.tenant_id,
            name=ds.name,
            adapter_type=ds.adapter_type.value,
            schedule_type=ds.schedule.schedule_type.value,
            last_sync_at=ds.last_sync_at,
            clone_head_commit=ds.clone_head_commit,
            last_extraction_baseline_commit=ds.last_extraction_baseline_commit,
            tracked_branch_head_commit=ds.tracked_branch_head_commit,
            created_at=ds.created_at,
            updated_at=ds.updated_at,
            ontology=(
                OntologyModel.from_domain(ds.ontology)
                if ds.ontology is not None
                else None
            ),
            latest_sync_run=(
                SyncRunResponse.from_domain(pair.latest_sync_run)
                if pair.latest_sync_run is not None
                else None
            ),
        )


class DataSourceListResponse(BaseModel):
    """Response model for the flat data source list endpoint."""

    data_sources: list[DataSourceWithSyncResponse] = Field(
        ..., description="List of data sources with their latest sync run"
    )
    count: int = Field(..., description="Total number of data sources returned")
