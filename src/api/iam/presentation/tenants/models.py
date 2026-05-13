"""Pydantic models for tenant API requests and responses."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator

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
    """Request model for adding a member to a tenant.

    Accepts either ``user_id`` (UUID) or ``email`` — exactly one must be provided.
    When ``email`` is given, the route handler resolves it to a user ID.
    """

    user_id: str | None = Field(
        None, description="User ID to add as member", min_length=1
    )
    email: str | None = Field(None, description="Email address of the user to add")
    role: TenantRoleEnum = Field(..., description="Role to assign (admin or member)")

    @field_validator("email", mode="before")
    @classmethod
    def _normalize_email(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip().lower()
        return v if v else None

    @model_validator(mode="after")
    def _exactly_one_identifier(self) -> "AddTenantMemberRequest":
        if self.user_id and self.email:
            raise ValueError("Provide either user_id or email, not both")
        if not self.user_id and not self.email:
            raise ValueError("Either user_id or email is required")
        return self

    def to_domain_role(self) -> TenantRole:
        """Convert API role to domain TenantRole."""
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
