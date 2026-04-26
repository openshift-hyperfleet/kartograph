"""Management-specific event translator for SpiceDB operations.

This module provides the translation layer between Management domain events
and SpiceDB relationship operations. It uses type-safe enums for all resource
types and relations to avoid magic strings.

The translator uses a dictionary-based dispatch approach with automatic
validation to ensure all domain events have corresponding handlers.
"""

from __future__ import annotations

from typing import Any, Callable, get_args

from management.domain.events import (
    DataSourceCreated,
    DataSourceDeleted,
    DataSourceUpdated,
    DomainEvent,
    KnowledgeGraphCreated,
    KnowledgeGraphDeleted,
    KnowledgeGraphUpdated,
    SyncStarted,
)
from shared_kernel.authorization.types import RelationType, ResourceType
from shared_kernel.outbox.operations import (
    DeleteRelationship,
    DeleteRelationshipsByFilter,
    SpiceDBOperation,
    WriteRelationship,
)

# Build registry mapping event type names to classes
_EVENT_REGISTRY: dict[str, type] = {cls.__name__: cls for cls in get_args(DomainEvent)}


class ManagementEventTranslator:
    """Translates Management domain events to SpiceDB operations.

    This translator handles all Management-specific events defined in the
    DomainEvent type alias. Handler methods are mapped via a dictionary
    and validated at initialization to ensure completeness.

    Management events establish authorization relationships for knowledge
    graphs and data sources, linking them to their parent workspaces,
    knowledge graphs, and tenants in the SpiceDB permission system.
    """

    def __init__(self) -> None:
        """Initialize translator and validate all events have handlers."""
        # Map event classes to handler methods
        self._handlers: dict[
            type, Callable[[dict[str, Any]], list[SpiceDBOperation]]
        ] = {
            KnowledgeGraphCreated: self._translate_knowledge_graph_created,
            KnowledgeGraphUpdated: self._translate_knowledge_graph_updated,
            KnowledgeGraphDeleted: self._translate_knowledge_graph_deleted,
            DataSourceCreated: self._translate_data_source_created,
            DataSourceUpdated: self._translate_data_source_updated,
            DataSourceDeleted: self._translate_data_source_deleted,
            SyncStarted: self._translate_sync_started,
        }

        # Validate all domain events have handlers
        self._validate_handlers()

    def _validate_handlers(self) -> None:
        """Ensure all domain events have handler methods.

        This is primarily a developer convenience - Kartograph
        will fail to start if a DomainEvent doesn't have a registered handler.

        Raises:
            ValueError: If any domain events are missing handlers
        """
        event_types = set(get_args(DomainEvent))
        handler_types = set(self._handlers.keys())

        missing = event_types - handler_types
        if missing:
            missing_names = [e.__name__ for e in missing]
            raise ValueError(
                f"Missing translation handlers for events: {missing_names}"
            )

    def supported_event_types(self) -> frozenset[str]:
        """Return the event type names this translator handles."""
        return frozenset(cls.__name__ for cls in self._handlers.keys())

    def translate(
        self,
        event_type: str,
        payload: dict[str, Any],
    ) -> list[SpiceDBOperation]:
        """Convert an event payload to SpiceDB operations.

        Args:
            event_type: The name of the event type
            payload: The serialized event data

        Returns:
            List of SpiceDB operations to execute

        Raises:
            ValueError: If the event type is not supported
        """
        # Get event class from registry
        event_class = _EVENT_REGISTRY.get(event_type)
        if not event_class:
            raise ValueError(f"Unknown event type: {event_type}")

        # Look up handler method
        handler = self._handlers.get(event_class)
        if not handler:
            raise ValueError(f"No handler for event: {event_type}")

        return handler(payload)

    def _translate_knowledge_graph_created(
        self,
        payload: dict[str, Any],
    ) -> list[SpiceDBOperation]:
        """Translate KnowledgeGraphCreated to workspace and tenant relationship writes.

        Creates two relationships:
        - knowledge_graph:<id>#workspace@workspace:<workspace_id>
        - knowledge_graph:<id>#tenant@tenant:<tenant_id>

        These relationships enable permission inheritance: workspace members
        inherit access to knowledge graphs within that workspace.
        """
        return [
            WriteRelationship(
                resource_type=ResourceType.KNOWLEDGE_GRAPH,
                resource_id=payload["knowledge_graph_id"],
                relation=RelationType.WORKSPACE,
                subject_type=ResourceType.WORKSPACE,
                subject_id=payload["workspace_id"],
            ),
            WriteRelationship(
                resource_type=ResourceType.KNOWLEDGE_GRAPH,
                resource_id=payload["knowledge_graph_id"],
                relation=RelationType.TENANT,
                subject_type=ResourceType.TENANT,
                subject_id=payload["tenant_id"],
            ),
        ]

    def _translate_knowledge_graph_updated(
        self,
        payload: dict[str, Any],
    ) -> list[SpiceDBOperation]:
        """Translate KnowledgeGraphUpdated - no SpiceDB changes needed.

        Metadata updates (name, description) do not affect authorization
        relationships. The workspace and tenant associations remain unchanged.
        """
        return []

    def _translate_knowledge_graph_deleted(
        self,
        payload: dict[str, Any],
    ) -> list[SpiceDBOperation]:
        """Translate KnowledgeGraphDeleted to delete all relationships.

        Removes the workspace and tenant relationships created during
        knowledge graph creation, plus any direct user permission grants
        (admin, editor, viewer) using filter-based deletion.

        Order: direct deletes first, then filter deletes.

        Deletes:
        - knowledge_graph:<id>#workspace@workspace:<workspace_id>
        - knowledge_graph:<id>#tenant@tenant:<tenant_id>
        - knowledge_graph:<id>#admin@* (filter)
        - knowledge_graph:<id>#editor@* (filter)
        - knowledge_graph:<id>#viewer@* (filter)
        """
        return [
            # Direct deletes for workspace and tenant
            DeleteRelationship(
                resource_type=ResourceType.KNOWLEDGE_GRAPH,
                resource_id=payload["knowledge_graph_id"],
                relation=RelationType.WORKSPACE,
                subject_type=ResourceType.WORKSPACE,
                subject_id=payload["workspace_id"],
            ),
            DeleteRelationship(
                resource_type=ResourceType.KNOWLEDGE_GRAPH,
                resource_id=payload["knowledge_graph_id"],
                relation=RelationType.TENANT,
                subject_type=ResourceType.TENANT,
                subject_id=payload["tenant_id"],
            ),
            # Filter deletes for any direct admin/editor/viewer grants
            DeleteRelationshipsByFilter(
                resource_type=ResourceType.KNOWLEDGE_GRAPH,
                resource_id=payload["knowledge_graph_id"],
                relation=RelationType.ADMIN,
            ),
            DeleteRelationshipsByFilter(
                resource_type=ResourceType.KNOWLEDGE_GRAPH,
                resource_id=payload["knowledge_graph_id"],
                relation=RelationType.EDITOR,
            ),
            DeleteRelationshipsByFilter(
                resource_type=ResourceType.KNOWLEDGE_GRAPH,
                resource_id=payload["knowledge_graph_id"],
                relation=RelationType.VIEWER,
            ),
        ]

    def _translate_data_source_created(
        self,
        payload: dict[str, Any],
    ) -> list[SpiceDBOperation]:
        """Translate DataSourceCreated to knowledge graph and tenant relationship writes.

        Creates two relationships:
        - data_source:<id>#knowledge_graph@knowledge_graph:<kg_id>
        - data_source:<id>#tenant@tenant:<tenant_id>

        These relationships enable permission inheritance: knowledge graph
        members inherit access to data sources within that knowledge graph.
        """
        return [
            WriteRelationship(
                resource_type=ResourceType.DATA_SOURCE,
                resource_id=payload["data_source_id"],
                relation=RelationType.KNOWLEDGE_GRAPH,
                subject_type=ResourceType.KNOWLEDGE_GRAPH,
                subject_id=payload["knowledge_graph_id"],
            ),
            WriteRelationship(
                resource_type=ResourceType.DATA_SOURCE,
                resource_id=payload["data_source_id"],
                relation=RelationType.TENANT,
                subject_type=ResourceType.TENANT,
                subject_id=payload["tenant_id"],
            ),
        ]

    def _translate_data_source_updated(
        self,
        payload: dict[str, Any],
    ) -> list[SpiceDBOperation]:
        """Translate DataSourceUpdated - no SpiceDB changes needed.

        Connection configuration updates do not affect authorization
        relationships. The knowledge graph and tenant associations remain
        unchanged.
        """
        return []

    def _translate_data_source_deleted(
        self,
        payload: dict[str, Any],
    ) -> list[SpiceDBOperation]:
        """Translate DataSourceDeleted to delete all relationships.

        Removes the knowledge graph and tenant relationships created during
        data source creation.

        Deletes:
        - data_source:<id>#knowledge_graph@knowledge_graph:<kg_id>
        - data_source:<id>#tenant@tenant:<tenant_id>
        """
        return [
            DeleteRelationship(
                resource_type=ResourceType.DATA_SOURCE,
                resource_id=payload["data_source_id"],
                relation=RelationType.KNOWLEDGE_GRAPH,
                subject_type=ResourceType.KNOWLEDGE_GRAPH,
                subject_id=payload["knowledge_graph_id"],
            ),
            DeleteRelationship(
                resource_type=ResourceType.DATA_SOURCE,
                resource_id=payload["data_source_id"],
                relation=RelationType.TENANT,
                subject_type=ResourceType.TENANT,
                subject_id=payload["tenant_id"],
            ),
        ]

    def _translate_sync_started(
        self,
        payload: dict[str, Any],
    ) -> list[SpiceDBOperation]:
        """Translate SyncStarted - no SpiceDB changes needed.

        Sync lifecycle events do not affect authorization relationships.
        This event is consumed by the Ingestion context to trigger the
        data extraction pipeline.
        """
        return []
