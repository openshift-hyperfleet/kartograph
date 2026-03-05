"""SpiceDB event handler adapting EventTranslator to EventHandler.

Wraps the existing translator pattern, translating domain events to
SpiceDB operations and applying them via the authorization provider.
This extracts the _apply_operation pattern match from OutboxWorker into
a standalone, reusable EventHandler implementation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from shared_kernel.outbox.operations import (
    DeleteRelationship,
    DeleteRelationshipsByFilter,
    WriteRelationship,
)

if TYPE_CHECKING:
    from shared_kernel.authorization.protocols import AuthorizationProvider
    from shared_kernel.outbox.ports import EventTranslator


class SpiceDBEventHandler:
    """Adapts EventTranslator + AuthorizationProvider into an EventHandler.

    Wraps the existing translator pattern, translating domain events to
    SpiceDB operations and applying them via the authorization provider.
    This extracts the _apply_operation pattern match from OutboxWorker.
    """

    def __init__(
        self,
        translator: EventTranslator,
        authz: AuthorizationProvider,
    ) -> None:
        self._translator = translator
        self._authz = authz

    def supported_event_types(self) -> frozenset[str]:
        """Return the event types supported by the underlying translator."""
        return self._translator.supported_event_types()

    async def handle(self, event_type: str, payload: dict[str, Any]) -> None:
        """Translate a domain event to SpiceDB operations and apply them.

        Args:
            event_type: The name of the event type
            payload: The serialized event data

        Raises:
            ValueError: If the translator does not support the event type
            Exception: If the authorization provider fails
        """
        operations = self._translator.translate(event_type, payload)

        for operation in operations:
            await self._apply_operation(operation)

    async def _apply_operation(
        self,
        operation: WriteRelationship | DeleteRelationship | DeleteRelationshipsByFilter,
    ) -> None:
        """Apply a single SpiceDB operation via the authorization provider."""
        match operation:
            case WriteRelationship():
                await self._authz.write_relationship(
                    resource=operation.resource,
                    relation=operation.relation_name,
                    subject=operation.subject,
                )

            case DeleteRelationship():
                await self._authz.delete_relationship(
                    resource=operation.resource,
                    relation=operation.relation_name,
                    subject=operation.subject,
                )

            case DeleteRelationshipsByFilter():
                await self._authz.delete_relationships_by_filter(
                    resource_type=operation.resource_type.value,
                    resource_id=operation.resource_id,
                    relation=str(operation.relation) if operation.relation else None,
                    subject_type=operation.subject_type.value
                    if operation.subject_type
                    else None,
                    subject_id=operation.subject_id,
                )

            case _:
                raise TypeError(
                    f"Unsupported operation type: {type(operation).__name__}"
                )
