"""Value objects for IAM domain.

Value objects are immutable descriptors that provide type safety and
domain semantics for identifiers and domain concepts.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ulid import ULID


@dataclass(frozen=True)
class GroupId:
    """Identifier for a Group aggregate.

    Uses ULID for sortability and distribution-friendly generation.
    """

    value: str

    def __str__(self) -> str:
        """Return string representation."""
        return self.value

    @classmethod
    def generate(cls) -> GroupId:
        """Generate a new GroupId using ULID."""
        return cls(value=str(ULID()))

    @classmethod
    def from_string(cls, value: str) -> GroupId:
        """Create GroupId from string value.

        Args:
            value: ULID string

        Returns:
            GroupId instance

        Raises:
            ValueError: If value is not a valid ULID
        """
        # Validate ULID format
        try:
            ULID.from_str(value)
        except ValueError as e:
            raise ValueError(f"Invalid GroupId: {value}") from e

        return cls(value=value)


@dataclass(frozen=True)
class UserId:
    """Identifier for a User aggregate.

    Uses ULID for sortability and distribution-friendly generation.
    """

    value: str

    def __str__(self) -> str:
        """Return string representation."""
        return self.value

    @classmethod
    def generate(cls) -> UserId:
        """Generate a new UserId using ULID."""
        return cls(value=str(ULID()))

    @classmethod
    def from_string(cls, value: str) -> UserId:
        """Create UserId from string value.

        Args:
            value: ULID string

        Returns:
            UserId instance

        Raises:
            ValueError: If value is not a valid ULID
        """
        try:
            ULID.from_str(value)
        except ValueError as e:
            raise ValueError(f"Invalid UserId: {value}") from e

        return cls(value=value)


@dataclass(frozen=True)
class WorkspaceId:
    """Identifier for a Workspace.

    Uses ULID for sortability and distribution-friendly generation.
    """

    value: str

    def __str__(self) -> str:
        """Return string representation."""
        return self.value

    @classmethod
    def generate(cls) -> WorkspaceId:
        """Generate a new WorkspaceId using ULID."""
        return cls(value=str(ULID()))

    @classmethod
    def from_string(cls, value: str) -> WorkspaceId:
        """Create WorkspaceId from string value.

        Args:
            value: ULID string

        Returns:
            WorkspaceId instance

        Raises:
            ValueError: If value is not a valid ULID
        """
        try:
            ULID.from_str(value)
        except ValueError as e:
            raise ValueError(f"Invalid WorkspaceId: {value}") from e

        return cls(value=value)


class Role(StrEnum):
    """Roles for group membership.

    Defines the hierarchy of permissions within a group.
    """

    OWNER = "owner"
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

    def is_owner(self) -> bool:
        """Check if this member is an owner."""
        return self.role == Role.OWNER

    def is_admin(self) -> bool:
        """Check if this member is an admin."""
        return self.role == Role.ADMIN

    def is_member(self) -> bool:
        """Check if this member is a regular member."""
        return self.role == Role.MEMBER

    def has_admin_privileges(self) -> bool:
        """Check if this member has admin or owner privileges."""
        return self.role in (Role.OWNER, Role.ADMIN)
