"""Tenant context FastAPI dependency.

Resolves tenant context from the X-Tenant-ID request header.

In single-tenant dev mode (KARTOGRAPH_IAM_SINGLE_TENANT_MODE=true, default),
when the header is missing the dependency auto-selects the default tenant
and auto-adds the user as a member (or admin if in the bootstrap list).
In multi-tenant mode, a missing header returns 400.

Usage in FastAPI routes:
    @router.get("/example")
    async def example(
        tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    ):
        # tenant.tenant_id is the resolved TenantId
        ...
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from iam.domain.value_objects import TenantId, TenantRole, UserId
from iam.ports.repositories import ITenantRepository
from shared_kernel.authorization.protocols import AuthorizationProvider
from shared_kernel.authorization.types import (
    Permission,
    ResourceType,
    format_resource,
    format_subject,
)
from shared_kernel.middleware.observability.tenant_context_probe import (
    TenantContextProbe,
)
from shared_kernel.middleware.tenant_context import TenantContext


def _validate_ulid(raw_value: str) -> TenantId:
    """Validate and parse a raw string as a ULID-based TenantId.

    Accepts case-insensitive input (per Crockford's Base32 spec) and
    returns the canonical uppercase form for consistent SpiceDB keys.

    Args:
        raw_value: The raw X-Tenant-ID header value.

    Returns:
        Validated TenantId with canonical (uppercase) ULID value.

    Raises:
        ValueError: If the value is not a valid ULID.
    """
    parsed_ulid = ULID.from_str(raw_value.upper())
    return TenantId(value=str(parsed_ulid))


async def get_tenant_context(
    x_tenant_id: str | None,
    user_id: str,
    username: str,
    authz: AuthorizationProvider,
    probe: TenantContextProbe,
    single_tenant_mode: bool,
    tenant_repository: ITenantRepository,
    default_tenant_name: str,
    bootstrap_admin_usernames: list[str],
    session: AsyncSession | None = None,
) -> TenantContext:
    """Get the tenant context from the X-Tenant-ID header.

    This is the core logic for the tenant context dependency. It validates
    the header value, checks authorization, and handles single-tenant mode
    auto-selection with automatic user provisioning.

    Args:
        x_tenant_id: The X-Tenant-ID header value, or None if missing.
        user_id: The authenticated user's ID.
        username: The authenticated user's username.
        authz: Authorization provider for SpiceDB permission checks.
        probe: Domain probe for observability.
        single_tenant_mode: Whether single-tenant dev mode is enabled.
        tenant_repository: Repository for looking up the default tenant.
        default_tenant_name: Configured default tenant name from IAMSettings.
        bootstrap_admin_usernames: Usernames that should be auto-added as admins.
        session: Database session for transaction management. Required when
            single_tenant_mode is True and auto-add may occur. After the save,
            ``await session.commit()`` is called to ensure outbox events are
            committed.

    Returns:
        TenantContext with the resolved tenant ID and source.

    Raises:
        HTTPException 400: If header is missing in multi-tenant mode or
            contains an invalid ULID.
        HTTPException 403: If user is not a member of the requested tenant.
        HTTPException 500: If default tenant is not found in single-tenant mode.
    """
    # Validate and normalize user_id and username
    user_id = user_id.strip()
    username = username.strip()

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id must not be empty",
        )

    if not username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="username must not be empty",
        )

    # Case 1: Header is missing
    if x_tenant_id is None:
        if single_tenant_mode:
            return await _resolve_default_tenant(
                user_id=user_id,
                username=username,
                authz=authz,
                probe=probe,
                tenant_repository=tenant_repository,
                default_tenant_name=default_tenant_name,
                bootstrap_admin_usernames=bootstrap_admin_usernames,
                session=session,
            )
        else:
            probe.tenant_header_missing(user_id=user_id)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="X-Tenant-ID header is required",
            )

    # Case 2: Header is present - validate ULID format
    try:
        tenant_id = _validate_ulid(x_tenant_id)
    except (ValueError, TypeError):
        probe.invalid_tenant_id_format(
            raw_value=x_tenant_id,
            user_id=user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"X-Tenant-ID must be a valid ULID format, got: '{x_tenant_id}'",
        )

    # Case 3: Check authorization - user must have 'view' permission on tenant
    try:
        has_permission = await authz.check_permission(
            resource=format_resource(ResourceType.TENANT, tenant_id.value),
            permission=Permission.VIEW,
            subject=format_subject(ResourceType.USER, user_id),
        )
    except Exception as e:
        probe.tenant_authz_check_failed(
            tenant_id=tenant_id.value,
            user_id=user_id,
            error=e,
        )
        raise

    if not has_permission:
        probe.tenant_access_denied(
            tenant_id=tenant_id.value,
            user_id=user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this tenant",
        )

    probe.tenant_resolved_from_header(
        tenant_id=tenant_id.value,
        user_id=user_id,
    )

    return TenantContext(
        tenant_id=tenant_id.value,
        source="header",
    )


async def _resolve_default_tenant(
    user_id: str,
    username: str,
    authz: AuthorizationProvider,
    probe: TenantContextProbe,
    tenant_repository: ITenantRepository,
    default_tenant_name: str,
    bootstrap_admin_usernames: list[str],
    session: AsyncSession | None = None,
) -> TenantContext:
    """Auto-select the default tenant in single-tenant mode.

    Looks up the default tenant by name, checks if the user already has
    access, and auto-adds them if not. Users in the bootstrap_admin_usernames
    list are added as ADMIN; all others are added as MEMBER.

    After saving, ``await session.commit()`` is called to ensure the
    outbox events produced by ``tenant_repository.save()`` are committed.
    Without this, the tenant context session (which has autocommit=False)
    would silently roll back the outbox writes on close.

    Note: We cannot use ``async with session.begin()`` here because the
    session already has an active transaction from the preceding
    ``tenant_repository.get_by_name()`` call.

    Args:
        user_id: The authenticated user's ID.
        username: The authenticated user's username.
        authz: Authorization provider for SpiceDB permission checks.
        probe: Domain probe for observability.
        tenant_repository: Repository for tenant lookup and save.
        default_tenant_name: Configured default tenant name from IAMSettings.
        bootstrap_admin_usernames: Usernames to auto-add as admins.
        session: Database session for committing the save.

    Returns:
        TenantContext with the default tenant and 'default' source.

    Raises:
        HTTPException 500: If the default tenant is not found or auto-add fails.
    """
    tenant = await tenant_repository.get_by_name(default_tenant_name)

    if tenant is None:
        probe.default_tenant_not_found()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Default tenant not found. Ensure application startup "
            "completed successfully.",
        )

    # Check if user already has view permission on the tenant
    try:
        has_permission = await authz.check_permission(
            resource=format_resource(ResourceType.TENANT, tenant.id.value),
            permission=Permission.VIEW,
            subject=format_subject(ResourceType.USER, user_id),
        )
    except Exception as e:
        probe.tenant_authz_check_failed(
            tenant_id=tenant.id.value,
            user_id=user_id,
            error=e,
        )
        raise

    if not has_permission:
        # Ensure we have a session for auto-add persistence
        if session is None:
            probe.user_auto_add_failed(
                tenant_id=tenant.id.value,
                user_id=user_id,
                username=username,
                error=ValueError("No database session available for auto-add"),
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Cannot auto-add user: no database session available",
            )

        # Auto-add user to the default tenant
        role = (
            TenantRole.ADMIN
            if username in bootstrap_admin_usernames
            else TenantRole.MEMBER
        )

        try:
            tenant.add_member(user_id=UserId(value=user_id), role=role)
            await tenant_repository.save(tenant)
            await session.commit()
        except Exception as e:
            probe.user_auto_add_failed(
                tenant_id=tenant.id.value,
                user_id=user_id,
                username=username,
                error=e,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to auto-add user to default tenant.",
            )

        if role == TenantRole.ADMIN:
            probe.user_auto_added_as_admin(
                tenant_id=tenant.id.value,
                user_id=user_id,
                username=username,
            )
        else:
            probe.user_auto_added_as_member(
                tenant_id=tenant.id.value,
                user_id=user_id,
                username=username,
            )

    probe.tenant_resolved_from_default(
        tenant_id=tenant.id.value,
        user_id=user_id,
    )

    return TenantContext(
        tenant_id=tenant.id.value,
        source="default",
    )
