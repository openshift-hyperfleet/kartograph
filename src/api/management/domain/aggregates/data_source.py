"""DataSource aggregate for Management context."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from management.domain.events import (
    DataSourceCreated,
    DataSourceDeleted,
    DataSourceUpdated,
)
from management.domain.exceptions import (
    AggregateDeletedError,
    InvalidDataSourceNameError,
)
from management.domain.observability import (
    DataSourceProbe,
    DefaultDataSourceProbe,
)
from management.domain.value_objects import DataSourceId, Schedule, ScheduleType
from shared_kernel.datasource_types import DataSourceAdapterType

if TYPE_CHECKING:
    from management.domain.events import DomainEvent


@dataclass
class DataSource:
    """DataSource aggregate representing a data source connected to a knowledge graph.

    A data source defines how data is ingested into a knowledge graph from
    an external system (e.g., GitHub). Each data source belongs to exactly
    one knowledge graph and one tenant.

    Business rules:
    - Name must be 1-100 characters
    - Schedule defaults to MANUAL when created
    - last_sync_at starts as None and is updated via record_sync_completed()
    - Deletion event must include knowledge_graph_id for relationship cleanup

    Event collection:
    - Mutating operations record domain events (except record_sync_completed)
    - Events can be collected via collect_events() for the outbox pattern
    """

    id: DataSourceId
    knowledge_graph_id: str
    tenant_id: str
    name: str
    adapter_type: DataSourceAdapterType
    connection_config: dict[str, str]
    credentials_path: str | None
    schedule: Schedule
    last_sync_at: datetime | None
    created_at: datetime
    updated_at: datetime
    _pending_events: list[DomainEvent] = field(default_factory=list, repr=False)
    _probe: DataSourceProbe = field(
        default_factory=DefaultDataSourceProbe,
        repr=False,
    )
    _deleted: bool = field(default=False, repr=False)

    def __post_init__(self) -> None:
        """Validate business rules after initialization."""
        self._validate_name(self.name)

    def _validate_name(self, name: str) -> None:
        """Validate data source name length.

        Args:
            name: The name to validate

        Raises:
            InvalidDataSourceNameError: If name is not 1-100 characters
        """
        if not (1 <= len(name) <= 100):
            raise InvalidDataSourceNameError(
                "Data source name must be between 1 and 100 characters"
            )

    @classmethod
    def create(
        cls,
        knowledge_graph_id: str,
        tenant_id: str,
        name: str,
        adapter_type: DataSourceAdapterType,
        connection_config: dict[str, str],
        credentials_path: str | None = None,
        *,
        created_by: str | None = None,
        probe: DataSourceProbe | None = None,
    ) -> DataSource:
        """Factory method for creating a new data source.

        Generates a unique ID, initializes the aggregate with a MANUAL schedule,
        and records the DataSourceCreated event.

        Args:
            knowledge_graph_id: The knowledge graph this data source belongs to
            tenant_id: The tenant that owns this data source
            name: The name of the data source
            adapter_type: The type of adapter (e.g., GITHUB)
            connection_config: Key-value pairs for adapter configuration
            credentials_path: Optional path to credentials in vault
            created_by: The user who created the data source (optional)
            probe: Optional observability probe

        Returns:
            A new DataSource aggregate with DataSourceCreated event recorded
        """
        now = datetime.now(UTC)
        ds = cls(
            id=DataSourceId.generate(),
            knowledge_graph_id=knowledge_graph_id,
            tenant_id=tenant_id,
            name=name,
            adapter_type=adapter_type,
            connection_config=dict(connection_config),
            credentials_path=credentials_path,
            schedule=Schedule(schedule_type=ScheduleType.MANUAL),
            last_sync_at=None,
            created_at=now,
            updated_at=now,
            _probe=probe or DefaultDataSourceProbe(),
        )
        ds._pending_events.append(
            DataSourceCreated(
                data_source_id=ds.id.value,
                knowledge_graph_id=knowledge_graph_id,
                tenant_id=tenant_id,
                name=name,
                adapter_type=adapter_type.value,
                occurred_at=now,
                created_by=created_by,
            )
        )
        ds._probe.created(
            data_source_id=ds.id.value,
            knowledge_graph_id=knowledge_graph_id,
            tenant_id=tenant_id,
            name=name,
            adapter_type=adapter_type.value,
        )
        return ds

    def update_connection(
        self,
        name: str,
        connection_config: dict[str, str],
        credentials_path: str | None,
        *,
        updated_by: str | None = None,
    ) -> None:
        """Update the data source's connection configuration.

        Args:
            name: The new name (1-100 characters)
            connection_config: The new connection configuration
            credentials_path: The new credentials path (or None)
            updated_by: The user performing the update (optional)

        Raises:
            InvalidDataSourceNameError: If name is not 1-100 characters
            AggregateDeletedError: If the data source has been marked for deletion
        """
        if self._deleted:
            raise AggregateDeletedError("Cannot update a deleted data source")
        self._validate_name(name)
        self.name = name
        self.connection_config = dict(connection_config)
        self.credentials_path = credentials_path
        self.updated_at = datetime.now(UTC)

        self._pending_events.append(
            DataSourceUpdated(
                data_source_id=self.id.value,
                knowledge_graph_id=self.knowledge_graph_id,
                tenant_id=self.tenant_id,
                name=name,
                occurred_at=self.updated_at,
                updated_by=updated_by,
            )
        )
        self._probe.updated(
            data_source_id=self.id.value,
            knowledge_graph_id=self.knowledge_graph_id,
            tenant_id=self.tenant_id,
            name=name,
        )

    def record_sync_completed(self) -> None:
        """Record that a sync has completed.

        Updates last_sync_at to the current time and calls the probe.
        Does NOT emit a domain event — this is just a timestamp update.
        """
        self.last_sync_at = datetime.now(UTC)
        self._probe.sync_completed(
            data_source_id=self.id.value,
            knowledge_graph_id=self.knowledge_graph_id,
            tenant_id=self.tenant_id,
        )

    def mark_for_deletion(
        self,
        *,
        deleted_by: str | None = None,
    ) -> None:
        """Mark the data source for deletion.

        Records a DataSourceDeleted event that includes knowledge_graph_id
        for relationship cleanup.

        Args:
            deleted_by: The user performing the deletion (optional)
        """
        if self._deleted:
            return
        self._deleted = True
        self._pending_events.append(
            DataSourceDeleted(
                data_source_id=self.id.value,
                knowledge_graph_id=self.knowledge_graph_id,
                tenant_id=self.tenant_id,
                occurred_at=datetime.now(UTC),
                deleted_by=deleted_by,
            )
        )
        self._probe.deleted(
            data_source_id=self.id.value,
            knowledge_graph_id=self.knowledge_graph_id,
            tenant_id=self.tenant_id,
        )

    def collect_events(self) -> list[DomainEvent]:
        """Return and clear pending domain events.

        Returns all domain events that have been recorded since
        the last call to collect_events(). Clears the internal list.

        Returns:
            List of pending domain events
        """
        events = self._pending_events.copy()
        self._pending_events.clear()
        return events
