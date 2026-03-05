"""Domain events for DataSource aggregate."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DataSourceCreated:
    """Emitted when a new data source is created.

    Attributes:
        data_source_id: The ID of the created data source
        knowledge_graph_id: The knowledge graph this data source belongs to
        tenant_id: The tenant that owns this data source
        name: The name given to the data source
        adapter_type: The type of adapter (e.g., "github")
        occurred_at: When the event occurred
        created_by: The user who created the data source (if known)
    """

    data_source_id: str
    knowledge_graph_id: str
    tenant_id: str
    name: str
    adapter_type: str
    occurred_at: datetime
    created_by: str | None = None


@dataclass(frozen=True)
class DataSourceUpdated:
    """Emitted when a data source's connection configuration is updated.

    Attributes:
        data_source_id: The ID of the updated data source
        knowledge_graph_id: The knowledge graph this data source belongs to
        tenant_id: The tenant that owns this data source
        name: The current name of the data source
        occurred_at: When the event occurred
        updated_by: The user who updated the data source (if known)
    """

    data_source_id: str
    knowledge_graph_id: str
    tenant_id: str
    name: str
    occurred_at: datetime
    updated_by: str | None = None


@dataclass(frozen=True)
class DataSourceDeleted:
    """Emitted when a data source is marked for deletion.

    Attributes:
        data_source_id: The ID of the deleted data source
        knowledge_graph_id: The knowledge graph this data source belonged to
        tenant_id: The tenant that owned this data source
        occurred_at: When the event occurred
        deleted_by: The user who deleted the data source (if known)
    """

    data_source_id: str
    knowledge_graph_id: str
    tenant_id: str
    occurred_at: datetime
    deleted_by: str | None = None


@dataclass(frozen=True)
class SyncRequested:
    """Emitted when a sync is requested for a data source.

    Attributes:
        data_source_id: The ID of the data source to sync
        knowledge_graph_id: The knowledge graph this data source belongs to
        tenant_id: The tenant that owns this data source
        occurred_at: When the event occurred
        requested_by: The user who requested the sync (if known)
    """

    data_source_id: str
    knowledge_graph_id: str
    tenant_id: str
    occurred_at: datetime
    requested_by: str | None = None
