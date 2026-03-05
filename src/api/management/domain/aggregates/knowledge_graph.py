"""KnowledgeGraph aggregate for Management context."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from management.domain.events import (
    KnowledgeGraphCreated,
    KnowledgeGraphDeleted,
    KnowledgeGraphUpdated,
)
from management.domain.exceptions import InvalidKnowledgeGraphNameError
from management.domain.observability import (
    DefaultKnowledgeGraphProbe,
    KnowledgeGraphProbe,
)
from management.domain.value_objects import KnowledgeGraphId

if TYPE_CHECKING:
    from management.domain.events import DomainEvent


@dataclass
class KnowledgeGraph:
    """KnowledgeGraph aggregate representing a knowledge graph within a workspace.

    A knowledge graph is a container for interconnected data sourced from
    various data sources. Each knowledge graph belongs to exactly one workspace
    and one tenant.

    Business rules:
    - Name must be 1-100 characters
    - Deletion event must include workspace_id for SpiceDB cleanup

    Event collection:
    - All mutating operations record domain events
    - Events can be collected via collect_events() for the outbox pattern
    """

    id: KnowledgeGraphId
    tenant_id: str
    workspace_id: str
    name: str
    description: str
    created_at: datetime
    updated_at: datetime
    _pending_events: list[DomainEvent] = field(default_factory=list, repr=False)
    _probe: KnowledgeGraphProbe = field(
        default_factory=DefaultKnowledgeGraphProbe,
        repr=False,
    )

    def __post_init__(self) -> None:
        """Validate business rules after initialization."""
        self._validate_name(self.name)

    def _validate_name(self, name: str) -> None:
        """Validate knowledge graph name length.

        Args:
            name: The name to validate

        Raises:
            InvalidKnowledgeGraphNameError: If name is not 1-100 characters
        """
        if not name or len(name) < 1 or len(name) > 100:
            raise InvalidKnowledgeGraphNameError(
                "Knowledge graph name must be between 1 and 100 characters"
            )

    @classmethod
    def create(
        cls,
        tenant_id: str,
        workspace_id: str,
        name: str,
        description: str,
        *,
        created_by: str | None = None,
        probe: KnowledgeGraphProbe | None = None,
    ) -> KnowledgeGraph:
        """Factory method for creating a new knowledge graph.

        Generates a unique ID, initializes the aggregate, and records
        the KnowledgeGraphCreated event.

        Args:
            tenant_id: The tenant this knowledge graph belongs to
            workspace_id: The workspace containing this knowledge graph
            name: The name of the knowledge graph (1-100 characters)
            description: Description of the knowledge graph
            created_by: The user who created the knowledge graph (optional)
            probe: Optional observability probe

        Returns:
            A new KnowledgeGraph aggregate with KnowledgeGraphCreated event recorded

        Raises:
            InvalidKnowledgeGraphNameError: If name is not 1-100 characters
        """
        now = datetime.now(UTC)
        kg = cls(
            id=KnowledgeGraphId.generate(),
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            name=name,
            description=description,
            created_at=now,
            updated_at=now,
            _probe=probe or DefaultKnowledgeGraphProbe(),
        )
        kg._pending_events.append(
            KnowledgeGraphCreated(
                knowledge_graph_id=kg.id.value,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                name=name,
                description=description,
                occurred_at=now,
                created_by=created_by,
            )
        )
        kg._probe.created(
            knowledge_graph_id=kg.id.value,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            name=name,
        )
        return kg

    def update(
        self,
        name: str,
        description: str,
        *,
        updated_by: str | None = None,
    ) -> None:
        """Update the knowledge graph's metadata.

        Args:
            name: The new name (1-100 characters)
            description: The new description
            updated_by: The user performing the update (optional)

        Raises:
            InvalidKnowledgeGraphNameError: If name is not 1-100 characters
        """
        self._validate_name(name)
        self.name = name
        self.description = description
        self.updated_at = datetime.now(UTC)

        self._pending_events.append(
            KnowledgeGraphUpdated(
                knowledge_graph_id=self.id.value,
                tenant_id=self.tenant_id,
                name=name,
                description=description,
                occurred_at=self.updated_at,
                updated_by=updated_by,
            )
        )
        self._probe.updated(
            knowledge_graph_id=self.id.value,
            tenant_id=self.tenant_id,
            name=name,
        )

    def mark_for_deletion(
        self,
        *,
        deleted_by: str | None = None,
    ) -> None:
        """Mark the knowledge graph for deletion.

        Records a KnowledgeGraphDeleted event that includes workspace_id
        for SpiceDB relationship cleanup.

        Args:
            deleted_by: The user performing the deletion (optional)
        """
        self._pending_events.append(
            KnowledgeGraphDeleted(
                knowledge_graph_id=self.id.value,
                tenant_id=self.tenant_id,
                workspace_id=self.workspace_id,
                occurred_at=datetime.now(UTC),
                deleted_by=deleted_by,
            )
        )
        self._probe.deleted(
            knowledge_graph_id=self.id.value,
            tenant_id=self.tenant_id,
            workspace_id=self.workspace_id,
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
