"""Pydantic models for API key requests and responses."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from iam.domain.aggregates import APIKey


class CreateAPIKeyRequest(BaseModel):
    """Request model for creating an API key.

    The API key secret is generated server-side and returned only once
    in the creation response.
    """

    name: str = Field(
        ...,
        description="Descriptive name for the API key",
        min_length=1,
        max_length=255,
    )
    expires_in_days: int = Field(
        30,
        description="Number of days until the key expires (1-3650, defaults to 30 days)",
        ge=1,
        le=3650,
    )


class APIKeyResponse(BaseModel):
    """Response model for API key (without secret).

    This response is used for listing API keys. The secret is NEVER
    returned after creation.
    """

    id: str = Field(..., description="API Key ID (ULID format)")
    name: str = Field(..., description="API key name")
    prefix: str = Field(
        ..., description="Key prefix for identification (e.g., karto_abc123)"
    )
    created_by_user_id: str = Field(
        ..., description="User ID of the key creator (audit trail)"
    )
    created_at: datetime = Field(..., description="When the key was created")
    expires_at: datetime = Field(description="When the key expires")
    last_used_at: datetime | None = Field(
        None, description="When the key was last used"
    )
    is_revoked: bool = Field(..., description="Whether the key has been revoked")

    @classmethod
    def from_domain(cls, api_key: APIKey) -> APIKeyResponse:
        """Convert domain APIKey aggregate to API response.

        Args:
            api_key: APIKey domain aggregate

        Returns:
            APIKeyResponse (without secret or hash)
        """
        return cls(
            id=api_key.id.value,
            name=api_key.name,
            prefix=api_key.prefix,
            created_by_user_id=api_key.created_by_user_id.value,
            created_at=api_key.created_at,
            expires_at=api_key.expires_at,
            last_used_at=api_key.last_used_at,
            is_revoked=api_key.is_revoked,
        )


class APIKeyCreatedResponse(APIKeyResponse):
    """Response model for newly created API key (includes secret).

    The secret is returned ONLY in this response at creation time.
    Store it securely - it cannot be retrieved again.
    """

    secret: str = Field(
        ...,
        description="The API key secret. SAVE THIS - it cannot be retrieved again.",
    )
