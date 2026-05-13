"""User aggregate for IAM context."""

from __future__ import annotations

from dataclasses import dataclass

from iam.domain.value_objects import UserId


@dataclass(frozen=True)
class User:
    """User aggregate representing a person in the system.

    Users are provisioned from SSO (Red Hat SSO) and represent individuals
    who can be members of groups and access resources. Profile fields
    (name, email) are synced from the identity provider on each login.
    """

    id: UserId
    username: str
    name: str | None = None
    email: str | None = None

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
