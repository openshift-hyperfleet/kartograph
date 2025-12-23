"""Authorization provider protocol for SpiceDB abstraction.

Defines the interface for authorization providers, allowing for swappable
implementations (SpiceDB, mock, alternative providers).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CheckRequest:
    """A single permission check request for bulk operations.

    Attributes:
        resource: Resource identifier (e.g., "team:abc123")
        permission: Permission to check (e.g., "view", "edit")
        subject: Subject identifier (e.g., "user:alice")
    """

    resource: str
    permission: str
    subject: str


class AuthorizationProvider(Protocol):
    """Protocol for authorization providers.

    Implementations must provide methods for writing relationships,
    checking permissions, and bulk permission checks. The primary
    implementation is SpiceDBClient, but this protocol allows for
    mocking in tests or alternative implementations.
    """

    async def write_relationship(
        self,
        resource: str,
        relation: str,
        subject: str,
    ) -> None:
        """Write a relationship to the authorization system.

        Args:
            resource: Resource identifier (e.g., "team:abc123")
            relation: Relation name (e.g., "member", "owner")
            subject: Subject identifier (e.g., "user:alice")

        Raises:
            AuthorizationError: If the write fails
        """
        ...

    async def check_permission(
        self,
        resource: str,
        permission: str,
        subject: str,
    ) -> bool:
        """Check if a subject has permission on a resource.

        Args:
            resource: Resource identifier (e.g., "team:abc123")
            permission: Permission to check (e.g., "view", "edit")
            subject: Subject identifier (e.g., "user:alice")

        Returns:
            True if permission is granted, False otherwise

        Raises:
            AuthorizationError: If the check fails
        """
        ...

    async def bulk_check_permission(
        self,
        requests: list[CheckRequest],
    ) -> set[str]:
        """Bulk check permissions for multiple resources.

        This is more efficient than individual checks for post-filtering
        query results. Returns the set of resource IDs that passed the check.

        Args:
            requests: List of permission check requests

        Returns:
            Set of resource identifiers that passed permission checks

        Raises:
            AuthorizationError: If the bulk check fails
        """
        ...

    async def delete_relationship(
        self,
        resource: str,
        relation: str,
        subject: str,
    ) -> None:
        """Delete a relationship from the authorization system.

        Args:
            resource: Resource identifier (e.g., "team:abc123")
            relation: Relation name (e.g., "member", "owner")
            subject: Subject identifier (e.g., "user:alice")

        Raises:
            AuthorizationError: If the delete fails
        """
        ...
