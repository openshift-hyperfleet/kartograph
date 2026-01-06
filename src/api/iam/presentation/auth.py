"""Authentication helpers for IAM presentation layer.

Provides stub authentication for tracer bullet implementation.
In production, this will validate x-rh-identity header from Red Hat SSO.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Header, HTTPException, status

from iam.domain.value_objects import TenantId, UserId


@dataclass(frozen=True)
class CurrentUser:
    """Represents the currently authenticated user.

    This is extracted from authentication headers and used throughout
    the request lifecycle. In production, this comes from JWT claims.
    """

    user_id: UserId
    username: str
    tenant_id: TenantId


async def get_current_user(
    x_user_id: str = Header(..., description="User ID from SSO (stub)"),
    x_username: str = Header(..., description="Username from SSO (stub)"),
    x_tenant_id: str = Header(..., description="Tenant ID from SSO (stub)"),
) -> CurrentUser:
    """Extract current user from headers (stub for SSO integration).

    This is a simplified authentication mechanism for the walking skeleton.
    In production, this will:
    - Decode and validate JWT from Authorization header
    - Extract user_id, username, tenant_id from JWT claims
    - Validate JWT signature with Red Hat SSO public key
    - Handle authentication errors properly

    For now, we accept user info from custom headers to enable testing
    without a full SSO/JWT integration.

    Args:
        x_user_id: User ID header (ULID format)
        x_username: Username header
        x_tenant_id: Tenant ID header (ULID format)

    Returns:
        CurrentUser with validated user ID, username, and tenant ID

    Raises:
        HTTPException: 400 if user ID or tenant ID are invalid ULID format
    """
    try:
        user_id = UserId.from_string(x_user_id)
        tenant_id = TenantId.from_string(x_tenant_id)
        return CurrentUser(user_id=user_id, username=x_username, tenant_id=tenant_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid ID format: {e}",
        ) from e
