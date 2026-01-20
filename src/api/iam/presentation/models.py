"""Pydantic models for IAM API requests and responses."""

from __future__ import annotations

from pydantic import BaseModel, Field

from iam.domain.aggregates import Group, Tenant
from iam.domain.value_objects import Role


class CreateGroupRequest(BaseModel):
    """Request model for creating a group.

    Tenant ID comes from authenticated user context (JWT claims in production).
    """

    name: str = Field(..., description="Group name", min_length=1, max_length=255)


class GroupMemberResponse(BaseModel):
    """Response model for group member."""

    user_id: str = Field(..., description="User ID (ULID format)")
    role: Role = Field(..., description="Member role (admin or member)")


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


class CreateTenantRequest(BaseModel):
    """Request model for creating a tenant."""

    name: str = Field(..., description="Tenant name", min_length=1, max_length=255)


class TenantResponse(BaseModel):
    """Response model for tenant."""

    id: str = Field(..., description="Tenant ID (ULID format)")
    name: str = Field(..., description="Tenant name")

    @classmethod
    def from_domain(cls, tenant: Tenant) -> TenantResponse:
        """Convert domain Tenant aggregate to API response.

        Args:
            tenant: Tenant domain aggregate

        Returns:
            TenantResponse
        """
        return cls(
            id=tenant.id.value,
            name=tenant.name,
        )
