"""Pydantic models for group API requests and responses."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from iam.domain.aggregates import Group
from iam.domain.value_objects import GroupRole


class GroupRoleEnum(StrEnum):
    """API-level enum for group roles."""

    ADMIN = "admin"
    MEMBER = "member"


class CreateGroupRequest(BaseModel):
    """Request model for creating a group.

    Tenant ID comes from authenticated user context (JWT claims in production).
    """

    name: str = Field(..., description="Group name", min_length=1, max_length=255)


class UpdateGroupRequest(BaseModel):
    """Request model for updating group metadata."""

    name: str = Field(..., min_length=1, max_length=255, description="Group name")


class AddGroupMemberRequest(BaseModel):
    """Request model for adding a member to a group."""

    user_id: str = Field(..., description="User ID to add", min_length=1)
    role: GroupRoleEnum = Field(..., description="Role to assign")

    def to_domain_role(self) -> GroupRole:
        """Convert API role to domain GroupRole.

        Returns:
            GroupRole domain value object
        """
        return GroupRole(self.role.value)


class UpdateGroupMemberRoleRequest(BaseModel):
    """Request model for updating a group member's role."""

    role: GroupRoleEnum = Field(..., description="New role to assign")

    def to_domain_role(self) -> GroupRole:
        """Convert API role to domain GroupRole.

        Returns:
            GroupRole domain value object
        """
        return GroupRole(self.role.value)


class GroupMemberResponse(BaseModel):
    """Response model for group member."""

    user_id: str = Field(..., description="User ID (ULID format)")
    role: GroupRole = Field(..., description="Member role (admin or member)")


class GroupResponse(BaseModel):
    """Response model for group."""

    id: str = Field(..., description="Group ID (ULID format)")
    name: str = Field(..., description="Group name")
    members: list[GroupMemberResponse] = Field(
        default_factory=list, description="Group members with roles"
    )

    @classmethod
    def from_domain(cls, group: Group) -> GroupResponse:
        """Convert domain Group aggregate to API response.

        Args:
            group: Group domain aggregate

        Returns:
            GroupResponse with members
        """
        return cls(
            id=group.id.value,
            name=group.name,
            members=[
                GroupMemberResponse(
                    user_id=member.user_id.value,
                    role=member.role,
                )
                for member in group.members
            ],
        )
