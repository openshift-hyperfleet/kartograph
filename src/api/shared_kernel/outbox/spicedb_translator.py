"""SpiceDB translator for domain events.

This module provides the translation layer between domain events and
SpiceDB relationship operations. Each event type maps to one or more
operations that need to be executed against SpiceDB.
"""

from __future__ import annotations

from dataclasses import dataclass

from iam.domain.events import (
    DomainEvent,
    GroupCreated,
    GroupDeleted,
    MemberAdded,
    MemberRemoved,
    MemberRoleChanged,
)
from shared_kernel.authorization.types import (
    ResourceType,
    RelationType,
    format_resource,
    format_subject,
)


@dataclass(frozen=True)
class WriteRelationship:
    """Operation to write a relationship to SpiceDB.

    Attributes:
        resource: The resource identifier (e.g., "group:abc123")
        relation: The relation type (e.g., "tenant", "member", "admin")
        subject: The subject identifier (e.g., "user:xyz789")
    """

    resource: str
    relation: str
    subject: str


@dataclass(frozen=True)
class DeleteRelationship:
    """Operation to delete a relationship from SpiceDB.

    Attributes:
        resource: The resource identifier (e.g., "group:abc123")
        relation: The relation type (e.g., "member", "admin")
        subject: The subject identifier (e.g., "user:xyz789")
    """

    resource: str
    relation: str
    subject: str


@dataclass(frozen=True)
class DeleteAllRelationships:
    """Operation to delete all relationships for a resource.

    This is used when a resource is deleted and all its relationships
    need to be removed from SpiceDB.

    Attributes:
        resource: The resource identifier (e.g., "group:abc123")
    """

    resource: str


# Type alias for all SpiceDB operations
SpiceDBOperation = WriteRelationship | DeleteRelationship | DeleteAllRelationships


class SpiceDBTranslator:
    """Translates domain events to SpiceDB operations.

    This class provides the mapping between IAM domain events and the
    corresponding SpiceDB relationship operations. It uses the type-safe
    helpers from shared_kernel.authorization.types to format resources
    and subjects correctly.
    """

    def translate(self, event: DomainEvent) -> list[SpiceDBOperation]:
        """Convert a domain event to SpiceDB operations.

        Args:
            event: The domain event to translate

        Returns:
            A list of SpiceDB operations to execute

        Raises:
            ValueError: If the event type is not recognized
        """
        match event:
            case GroupCreated():
                return [
                    WriteRelationship(
                        resource=format_resource(ResourceType.GROUP, event.group_id),
                        relation=RelationType.TENANT,
                        subject=format_resource(ResourceType.TENANT, event.tenant_id),
                    )
                ]

            case GroupDeleted():
                return [
                    DeleteAllRelationships(
                        resource=format_resource(ResourceType.GROUP, event.group_id)
                    )
                ]

            case MemberAdded():
                return [
                    WriteRelationship(
                        resource=format_resource(ResourceType.GROUP, event.group_id),
                        relation=event.role.value,
                        subject=format_subject(ResourceType.USER, event.user_id),
                    )
                ]

            case MemberRemoved():
                return [
                    DeleteRelationship(
                        resource=format_resource(ResourceType.GROUP, event.group_id),
                        relation=event.role.value,
                        subject=format_subject(ResourceType.USER, event.user_id),
                    )
                ]

            case MemberRoleChanged():
                return [
                    DeleteRelationship(
                        resource=format_resource(ResourceType.GROUP, event.group_id),
                        relation=event.old_role.value,
                        subject=format_subject(ResourceType.USER, event.user_id),
                    ),
                    WriteRelationship(
                        resource=format_resource(ResourceType.GROUP, event.group_id),
                        relation=event.new_role.value,
                        subject=format_subject(ResourceType.USER, event.user_id),
                    ),
                ]

            case _:
                raise ValueError(f"Unknown event type: {type(event).__name__}")
