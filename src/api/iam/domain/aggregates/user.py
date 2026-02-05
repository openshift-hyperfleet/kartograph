"""User aggregate for IAM context."""

from __future__ import annotations

from dataclasses import dataclass

from iam.domain.value_objects import UserId


@dataclass(frozen=True)
class User:
    """User aggregate representing a person in the system.

    Users are provisioned from SSO (Red Hat SSO) and represent individuals
    who can be members of groups and access resources.

    For the walking skeleton, User is minimal (just id and username).
    Future enhancements will add email, clearance_level, etc.
    """

    id: UserId
    username: str

    def __str__(self) -> str:
        """Return string representation."""
        return f"User({self.username})"

    def __eq__(self, other: object) -> bool:
        """Users are equal if they have the same ID (identity-based equality)."""
        if not isinstance(other, User):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        """Hash based on ID for use in sets and dicts."""
        return hash(self.id)
