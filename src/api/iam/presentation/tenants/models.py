"""Pydantic models for tenant API requests and responses."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from iam.domain.aggregates import Tenant
from iam.domain.value_objects import TenantRole


class TenantRoleEnum(StrEnum):
    """API-level enum for tenant roles.

    Maps to domain TenantRole values for validation.
    """

    ADMIN = "admin"
    MEMBER = "member"


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


class AddTenantMemberRequest(BaseModel):
    """Request model for adding a member to a tenant."""

    user_id: str = Field(..., description="User ID to add as member", min_length=1)
    role: TenantRoleEnum = Field(..., description="Role to assign (admin or member)")

    def to_domain_role(self) -> TenantRole:
        """Convert API role to domain TenantRole.

        Returns:
            TenantRole domain value object
        """
        return TenantRole(self.role.value)


class TenantMemberResponse(BaseModel):
    """Response model for a tenant member."""

    user_id: str = Field(..., description="User ID")
    role: str = Field(..., description="Member's role in the tenant")

    @classmethod
    def from_tuple(cls, member: tuple[str, str]) -> TenantMemberResponse:
        """Create from (user_id, role) tuple.

        Args:
            member: Tuple of (user_id, role)

        Returns:
            TenantMemberResponse
        """
        return cls(user_id=member[0], role=member[1])
