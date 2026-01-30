"""Pydantic models for tenant API requests and responses."""

from __future__ import annotations

from pydantic import BaseModel, Field

from iam.domain.aggregates import Tenant


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
