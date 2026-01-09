"""SpiceDB operation value objects.

These immutable value objects represent the operations that need to be
executed against SpiceDB. They are produced by EventTranslators and
consumed by the OutboxWorker.
"""

from __future__ import annotations

from dataclasses import dataclass

from shared_kernel.authorization.types import RelationType, ResourceType


@dataclass(frozen=True)
class WriteRelationship:
    """Operation to write a relationship to SpiceDB.

    Attributes:
        resource_type: The type of the resource (e.g., ResourceType.GROUP)
        resource_id: The ULID of the resource
        relation: The relation type (e.g., RelationType.TENANT)
        subject_type: The type of the subject (e.g., ResourceType.USER)
        subject_id: The ULID of the subject
    """

    resource_type: ResourceType
    resource_id: str
    relation: RelationType | str  # str for Role values
    subject_type: ResourceType
    subject_id: str

    @property
    def resource(self) -> str:
        """Format resource as 'type:id' string."""
        return f"{self.resource_type}:{self.resource_id}"

    @property
    def subject(self) -> str:
        """Format subject as 'type:id' string."""
        return f"{self.subject_type}:{self.subject_id}"

    @property
    def relation_name(self) -> str:
        """Get the relation name as a string."""
        return str(self.relation)


@dataclass(frozen=True)
class DeleteRelationship:
    """Operation to delete a relationship from SpiceDB.

    Attributes:
        resource_type: The type of the resource (e.g., ResourceType.GROUP)
        resource_id: The ULID of the resource
        relation: The relation type (e.g., RelationType.MEMBER)
        subject_type: The type of the subject (e.g., ResourceType.USER)
        subject_id: The ULID of the subject
    """

    resource_type: ResourceType
    resource_id: str
    relation: RelationType | str  # str for Role values
    subject_type: ResourceType
    subject_id: str

    @property
    def resource(self) -> str:
        """Format resource as 'type:id' string."""
        return f"{self.resource_type}:{self.resource_id}"

    @property
    def subject(self) -> str:
        """Format subject as 'type:id' string."""
        return f"{self.subject_type}:{self.subject_id}"

    @property
    def relation_name(self) -> str:
        """Get the relation name as a string."""
        return str(self.relation)


# Type alias for all SpiceDB operations
SpiceDBOperation = WriteRelationship | DeleteRelationship
