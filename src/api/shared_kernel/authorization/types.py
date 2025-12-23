"""Authorization type definitions for SpiceDB.

Defines resource types, relations, and permissions that map to the SpiceDB schema.
These enums ensure type safety and prevent hardcoded strings across the codebase.
"""

from enum import StrEnum


class ResourceType(StrEnum):
    """SpiceDB resource types matching schema definitions.

    Each value corresponds to a `definition` in the SpiceDB schema (.zed file).
    """

    USER = "user"
    GROUP = "group"
    WORKSPACE = "workspace"
    TENANT = "tenant"
    # Future: KNOWLEDGE_GRAPH, DATA_SOURCE, etc.


class RelationType(StrEnum):
    """SpiceDB relations matching schema relations.

    Each value corresponds to a `relation` in the SpiceDB schema definitions.
    """

    MEMBER = "member"
    OWNER = "owner"
    ADMIN = "admin"
    PARENT = "parent"
    WORKSPACE = "workspace"
    ROOT_WORKSPACE = "root_workspace"


class Permission(StrEnum):
    """SpiceDB permissions matching schema permissions.

    Each value corresponds to a `permission` in the SpiceDB schema definitions.
    """

    VIEW = "view"
    EDIT = "edit"
    DELETE = "delete"
    MANAGE = "manage"


def format_resource(resource_type: ResourceType, resource_id: str) -> str:
    """Format a resource identifier for SpiceDB.

    Args:
        resource_type: The type of resource
        resource_id: The unique identifier for the resource

    Returns:
        Formatted resource string (e.g., "team:abc123")

    Example:
        >>> format_resource(ResourceType.TEAM, "abc123")
        "team:abc123"
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
