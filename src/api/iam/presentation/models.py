"""Pydantic models for IAM API requests and responses."""

from __future__ import annotations

from pydantic import BaseModel, Field

from iam.domain.aggregates import Group


class CreateGroupRequest(BaseModel):
    """Request model for creating a group."""

    name: str = Field(..., description="Group name", min_length=1, max_length=255)
    tenant_id: str = Field(..., description="Tenant ID (ULID format)")


class GroupMemberResponse(BaseModel):
    """Response model for group member."""

    user_id: str = Field(..., description="User ID (ULID format)")
    role: str = Field(..., description="Member role (admin or member)")


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
                    role=member.role.value,
                )
                for member in group.members
            ],
        )
