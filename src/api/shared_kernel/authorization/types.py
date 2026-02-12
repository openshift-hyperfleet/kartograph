"""Authorization type definitions for SpiceDB.

Defines resource types, relations, and permissions that map to the SpiceDB schema.
These enums ensure type safety and prevent hardcoded strings across the codebase.
"""

from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True)
class RelationshipSpec:
    """Specification for a relationship between a resource and subject.

    Used for bulk write/delete operations to clearly specify the
    resource, relation, and subject components.

    Attributes:
        resource: Resource identifier (e.g., "group:abc123")
        relation: Relation name (e.g., "member", "admin")
        subject: Subject identifier (e.g., "user:alice")

    Example:
        >>> RelationshipSpec(
        ...     resource="group:abc123",
        ...     relation="admin",
        ...     subject="user:alice"
        ... )
    """

    resource: str
    relation: str
    subject: str


@dataclass(frozen=True)
class SubjectRelation:
    """A subject and its relationship to a resource.

    Returned by lookup_subjects() to represent subjects that have
    a specific relationship to a resource in SpiceDB.

    Attributes:
        subject_id: The ID of the subject (e.g., user ID without type prefix)
        relation: The relation type (e.g., "member", "owner", "admin")

    Example:
        >>> SubjectRelation(subject_id="01ARZ3...", relation="owner")
    """

    subject_id: str
    relation: str


class ResourceType(StrEnum):
    """SpiceDB resource types matching schema definitions.

    Each value corresponds to a `definition` in the SpiceDB schema (.zed file).
    """

    USER = "user"
    GROUP = "group"
    WORKSPACE = "workspace"
    TENANT = "tenant"
    API_KEY = "api_key"
    # Future: KNOWLEDGE_GRAPH, DATA_SOURCE, etc.


class RelationType(StrEnum):
    """SpiceDB relations matching schema relations.

    Each value corresponds to a `relation` in the SpiceDB schema definitions.
    """

    ADMIN = "admin"
    EDITOR = "editor"
    MEMBER = "member"
    OWNER = "owner"
    PARENT = "parent"
    ROOT_WORKSPACE = "root_workspace"
    TENANT = "tenant"


class Permission(StrEnum):
    """SpiceDB permissions matching schema permissions.

    Each value corresponds to a `permission` in the SpiceDB schema definitions.
    """

    VIEW = "view"
    EDIT = "edit"
    MANAGE = "manage"
    ADMINISTRATE = "administrate"


def format_resource(resource_type: ResourceType, resource_id: str) -> str:
    """Format a resource identifier for SpiceDB.

    Args:
        resource_type: The type of resource
        resource_id: The unique identifier for the resource

    Returns:
        Formatted resource string (e.g., "workspace:abc123")

    Example:
        >>> format_resource(ResourceType.WORKSPACE, "abc123")
        "workspace:abc123"
    """
    return f"{resource_type}:{resource_id}"


def format_subject(subject_type: ResourceType, subject_id: str) -> str:
    """Format a subject identifier for SpiceDB.

    Args:
        subject_type: The type of subject (usually USER or GROUP)
        subject_id: The unique identifier for the subject

    Returns:
        Formatted subject string (e.g., "user:alice")

    Example:
        >>> format_subject(ResourceType.USER, "alice")
        "user:alice"
    """
    return f"{subject_type}:{subject_id}"
