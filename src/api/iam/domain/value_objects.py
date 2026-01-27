"""Value objects for IAM domain.

Value objects are immutable descriptors that provide type safety and
domain semantics for identifiers and domain concepts.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TypeVar

from ulid import ULID

# Generic type variable for ID classes
T = TypeVar("T", bound="BaseId")


@dataclass(frozen=True)
class BaseId:
    """Base class for ULID-based identifier value objects.

    Provides common functionality for ID generation and validation.
    Subclasses only need to define their docstrings for specific semantics.
    """

    value: str

    def __str__(self) -> str:
        """Return string representation."""
        return self.value

    @classmethod
    def generate(cls: type[T]) -> T:
        """Generate a new ID using ULID.

        Returns:
            New ID instance with generated ULID
        """
        return cls(value=str(ULID()))

    @classmethod
    def from_string(cls: type[T], value: str) -> T:
        """Create ID from string value.

        Args:
            value: ULID string

        Returns:
            ID instance

        Raises:
            ValueError: If value is not a valid ULID
        """
        try:
            ULID.from_str(value)
        except ValueError as e:
            raise ValueError(f"Invalid {cls.__name__}: {value}") from e

        return cls(value=value)


@dataclass(frozen=True)
class GroupId(BaseId):
    """Identifier for a Group aggregate.

    Uses ULID for sortability and distribution-friendly generation.
    """

    pass


@dataclass(frozen=True)
class UserId(BaseId):
    """Identifier for a User aggregate.

    Doesn't require ULID because user ids are managed externally
    by an identity provider.
    """

    @classmethod
    def from_string(cls: type[T], value: str) -> T:
        """Create ID from string value.

        Args:
            value: string

        Returns:
            ID instance

        Raises:
            ValueError: If value is empty or whitespace-only
        """
        trimmed_value = value.strip()
        if not trimmed_value:
            raise ValueError(
                f"Invalid {cls.__name__}: value cannot be empty or whitespace-only"
            )

        return cls(value=trimmed_value)


@dataclass(frozen=True)
class WorkspaceId(BaseId):
    """Identifier for a Workspace.

    Uses ULID for sortability and distribution-friendly generation.
    """

    pass


@dataclass(frozen=True)
class TenantId(BaseId):
    """Identifier for a Tenant.

    Uses ULID for sortability and distribution-friendly generation.
    """

    pass


@dataclass(frozen=True)
class APIKeyId(BaseId):
    """Identifier for an API Key.

    Uses ULID for sortability and distribution-friendly generation.
    """

    pass


class Role(StrEnum):
    """Roles for group membership.

    Defines the hierarchy of permissions within a group.
    """

    ADMIN = "admin"
    MEMBER = "member"


@dataclass(frozen=True)
class GroupMember:
    """Represents a user's membership in a group with a specific role.

    This is an immutable value object describing the relationship between
    a user and a group.
    """

    user_id: UserId
    role: Role

    def is_admin(self) -> bool:
        """Check if this member is an admin."""
        return self.role == Role.ADMIN

    def is_member(self) -> bool:
        """Check if this member is a regular member."""
        return self.role == Role.MEMBER

    def has_admin_privileges(self) -> bool:
        """Check if this member has admin privileges."""
        return self.role == Role.ADMIN
