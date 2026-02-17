from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from iam.application.observability import (
    AuthenticationProbe,
    DefaultUserServiceProbe,
    UserServiceProbe,
)
from iam.application.services import UserService
from iam.application.services.api_key_service import APIKeyService
from iam.application.value_objects import AuthenticatedUser, CurrentUser
from iam.dependencies.api_key import get_api_key_service
from iam.dependencies.authentication import (
    JWTValidator,
    get_authentication_probe,
    get_jwt_validator,
    oauth2_scheme,
)
from iam.dependencies.tenant_context import get_tenant_context
from iam.domain.aggregates import User
from iam.domain.value_objects import TenantId, UserId
from iam.infrastructure.tenant_repository import TenantRepository
from iam.infrastructure.user_repository import UserRepository
from infrastructure.authorization_dependencies import get_spicedb_client
from infrastructure.database.dependencies import (
    get_tenant_context_session,
    get_write_session,
)
from infrastructure.outbox.repository import OutboxRepository
from infrastructure.settings import get_iam_settings
from shared_kernel.auth import InvalidTokenError
from shared_kernel.authorization.protocols import AuthorizationProvider
from shared_kernel.middleware.observability import DefaultTenantContextProbe
from shared_kernel.middleware.observability.tenant_context_probe import (
    TenantContextProbe,
)
from shared_kernel.middleware.tenant_context import TenantContext


# ---------------------------------------------------------------------------
# Internal types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _AuthResult:
    """Internal result from the core authentication dependency.

    Carries user identity and auth-method metadata so that downstream
    dependencies can compose without re-validating credentials.
    """

    user_id: UserId
    username: str
    api_key_tenant_id: TenantId | None
    is_api_key: bool


# ---------------------------------------------------------------------------
# Core authentication (single source of truth)
# ---------------------------------------------------------------------------


async def _authenticate(
    validator: Annotated[JWTValidator, Depends(get_jwt_validator)],
    api_key_service: Annotated[APIKeyService, Depends(get_api_key_service)],
    auth_probe: Annotated[AuthenticationProbe, Depends(get_authentication_probe)],
    token: Annotated[str | None, Depends(oauth2_scheme)] = None,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> _AuthResult:
    """Authenticate via JWT Bearer token or X-API-Key header.

    This is the single source of truth for credential validation.
    FastAPI caches the result per-request, so downstream dependencies
    that depend on ``_authenticate`` share the same result without
    re-validating.

    Tries JWT first (if Authorization: Bearer present), then API Key.

    Args:
        validator: JWT validator for token validation
        api_key_service: The API key service for validation
        auth_probe: Authentication probe for observability
        token: Bearer token from Authorization header
        x_api_key: API key from X-API-Key header

    Returns:
        _AuthResult with user identity and auth-method metadata

    Raises:
        HTTPException 401: If neither auth method succeeds
    """
    www_authenticate = "Bearer, API-Key"

    # Try JWT first
    if token is not None:
        try:
            claims = await validator.validate_token(token)
            user_id = UserId(value=claims.sub)
            username = claims.preferred_username or claims.sub

            auth_probe.user_authenticated(user_id=claims.sub, username=username)

            return _AuthResult(
                user_id=user_id,
                username=username,
                api_key_tenant_id=None,
                is_api_key=False,
            )

        except InvalidTokenError as e:
            auth_probe.authentication_failed(reason=str(e))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e),
                headers={"WWW-Authenticate": www_authenticate},
            ) from e

    # Try API Key
    if x_api_key is not None:
        api_key = await api_key_service.validate_and_get_key(x_api_key)
        if api_key is None:
            auth_probe.api_key_authentication_failed(reason="invalid_or_expired")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired API key",
                headers={"WWW-Authenticate": www_authenticate},
            )

        auth_probe.api_key_authentication_succeeded(
            api_key_id=api_key.id.value,
            user_id=api_key.created_by_user_id.value,
        )

        return _AuthResult(
            user_id=api_key.created_by_user_id,
            username=f"api-key:{api_key.id}",
            api_key_tenant_id=api_key.tenant_id,
            is_api_key=True,
        )

    # Neither provided
    auth_probe.authentication_failed(reason="Missing authorization")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": www_authenticate},
    )


# ---------------------------------------------------------------------------
# JIT user provisioning helper
# ---------------------------------------------------------------------------


async def _ensure_user_exists(
    user_id: UserId,
    username: str,
    user_repo: UserRepository,
    session: AsyncSession,
    probe: UserServiceProbe,
) -> None:
    """Ensure user exists in database (find-or-create with SSO username sync).

    This is a lightweight JIT provisioning helper that does not require
    tenant scoping. It mirrors the logic in ``UserService.ensure_user``
    but can be used in contexts where no tenant is available (e.g.
    ``get_authenticated_user``).

    Args:
        user_id: The user's ID (from SSO)
        username: The user's username (from SSO)
        user_repo: Repository for user persistence
        session: Database session for transaction management
        probe: Domain probe for observability
    """
    try:
        async with session.begin():
            existing = await user_repo.get_by_id(user_id)
            if existing:
                if existing.username != username:
                    user = User(id=user_id, username=username)
                    await user_repo.save(user)
                    probe.user_ensured(
                        user_id=user_id.value,
                        username=username,
                        was_created=False,
                        was_updated=True,
                    )
                else:
                    probe.user_ensured(
                        user_id=user_id.value,
                        username=username,
                        was_created=False,
                        was_updated=False,
                    )
                return

            user = User(id=user_id, username=username)
            await user_repo.save(user)
            probe.user_ensured(
                user_id=user_id.value,
                username=username,
                was_created=True,
                was_updated=False,
            )

    except Exception as e:
        probe.user_provision_failed(
            user_id=user_id.value,
            username=username,
            error=str(e),
        )
        raise


# ---------------------------------------------------------------------------
# Dependency providers
# ---------------------------------------------------------------------------


def get_user_service_probe() -> UserServiceProbe:
    """Get UserServiceProbe instance.

    Returns:
        DefaultUserServiceProbe instance for observability
    """
    return DefaultUserServiceProbe()


def get_user_repository(
    session: Annotated[AsyncSession, Depends(get_write_session)],
) -> UserRepository:
    """Get UserRepository instance.

    Args:
        session: Async database session

    Returns:
        UserRepository instance
    """
    return UserRepository(session=session)


def get_tenant_context_probe() -> TenantContextProbe:
    """Get TenantContextProbe instance for tenant context resolution.

    Returns:
        DefaultTenantContextProbe instance for observability
    """
    return DefaultTenantContextProbe()


def _get_outbox_for_context(
    session: Annotated[AsyncSession, Depends(get_tenant_context_session)],
) -> OutboxRepository:
    """Get OutboxRepository for tenant context resolution.

    Uses the dedicated tenant context session (not the main request session)
    to avoid transaction conflicts.

    Args:
        session: Dedicated tenant context database session

    Returns:
        OutboxRepository instance
    """
    return OutboxRepository(session=session)


def _get_tenant_repository_for_context(
    session: Annotated[AsyncSession, Depends(get_tenant_context_session)],
    outbox: Annotated[OutboxRepository, Depends(_get_outbox_for_context)],
) -> TenantRepository:
    """Get TenantRepository for tenant context resolution.

    Uses a dedicated session (get_tenant_context_session) to avoid
    circular imports with iam.dependencies.tenant and to prevent
    transaction conflicts with the main request session.

    Args:
        session: Dedicated tenant context database session
        outbox: Outbox repository using the same dedicated session

    Returns:
        TenantRepository instance
    """
    return TenantRepository(session=session, outbox=outbox)


# ---------------------------------------------------------------------------
# Tenant context resolution
# ---------------------------------------------------------------------------


async def resolve_tenant_context(
    auth_result: Annotated[_AuthResult, Depends(_authenticate)],
    authz: Annotated[AuthorizationProvider, Depends(get_spicedb_client)],
    tenant_context_probe: Annotated[
        TenantContextProbe, Depends(get_tenant_context_probe)
    ],
    tenant_repo: Annotated[
        TenantRepository, Depends(_get_tenant_repository_for_context)
    ],
    tenant_context_session: Annotated[
        AsyncSession, Depends(get_tenant_context_session)
    ],
    x_tenant_id: Annotated[str | None, Header(alias="X-Tenant-ID")] = None,
) -> TenantContext:
    """Resolve tenant context for the current request.

    Uses the cached ``_authenticate`` result to obtain user identity,
    eliminating the redundant JWT validation that previously occurred here.

    For JWT-authenticated requests, resolves tenant via ``get_tenant_context``
    (which handles X-Tenant-ID header validation, SpiceDB authorization
    checks, and single-tenant mode auto-provisioning).

    For API key requests, returns a sentinel TenantContext since the
    actual tenant_id comes from the API key itself (via
    ``_AuthResult.api_key_tenant_id``).

    Args:
        auth_result: Cached authentication result from ``_authenticate``
        authz: Authorization provider for SpiceDB permission checks
        tenant_context_probe: Domain probe for tenant context observability
        tenant_repo: Repository for looking up tenants
        tenant_context_session: Dedicated database session for tenant context
            resolution. Passed to get_tenant_context so that auto-add member
            writes are followed by an explicit ``await session.commit()`` call.
        x_tenant_id: Optional X-Tenant-ID header value

    Returns:
        TenantContext with the resolved tenant ID and source

    Raises:
        HTTPException: If tenant resolution fails (400/403/500)
    """
    # For API key auth, the tenant comes from the key itself.
    # Return a sentinel that get_current_user_no_jit will ignore in favor
    # of auth_result.api_key_tenant_id.
    if auth_result.is_api_key:
        return TenantContext(tenant_id="", source="header")

    iam_settings = get_iam_settings()

    return await get_tenant_context(
        x_tenant_id=x_tenant_id,
        user_id=auth_result.user_id.value,
        username=auth_result.username,
        authz=authz,
        probe=tenant_context_probe,
        single_tenant_mode=iam_settings.single_tenant_mode,
        tenant_repository=tenant_repo,
        default_tenant_name=iam_settings.default_tenant_name,
        bootstrap_admin_usernames=iam_settings.bootstrap_admin_usernames,
        session=tenant_context_session,
    )


# ---------------------------------------------------------------------------
# Public authentication dependencies
# ---------------------------------------------------------------------------


async def get_authenticated_user(
    auth_result: Annotated[_AuthResult, Depends(_authenticate)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    session: Annotated[AsyncSession, Depends(get_write_session)],
    probe: Annotated[UserServiceProbe, Depends(get_user_service_probe)],
) -> AuthenticatedUser:
    """Authenticate via JWT Bearer token or X-API-Key header without tenant context.

    Returns an AuthenticatedUser with user_id and username only.
    Does NOT resolve tenant context — use this for endpoints that need
    authentication but not tenant scoping (e.g., listing or creating tenants).

    JIT provisions the user in the database for JWT-authenticated requests
    so that the user record exists before any tenant operations.

    Args:
        auth_result: Cached authentication result from ``_authenticate``
        user_repo: Repository for JIT user provisioning
        session: Database session for JIT user provisioning
        probe: Domain probe for JIT provisioning observability

    Returns:
        AuthenticatedUser with user_id and username (no tenant_id)
    """
    if not auth_result.is_api_key:
        await _ensure_user_exists(
            auth_result.user_id,
            auth_result.username,
            user_repo,
            session,
            probe,
        )

    return AuthenticatedUser(
        user_id=auth_result.user_id,
        username=auth_result.username,
    )


async def get_current_user_no_jit(
    auth_result: Annotated[_AuthResult, Depends(_authenticate)],
    tenant_context: Annotated[TenantContext, Depends(resolve_tenant_context)],
) -> CurrentUser:
    """Authenticate and resolve tenant context without JIT provisioning.

    Composes ``_authenticate`` with ``resolve_tenant_context`` to produce
    a ``CurrentUser`` with tenant scoping. Does NOT JIT provision the user
    — use ``get_current_user`` if JIT provisioning is desired.

    For API key auth, the tenant_id comes from the API key itself
    (``_AuthResult.api_key_tenant_id``). For JWT auth, it comes from
    the resolved ``TenantContext``.

    Args:
        auth_result: Cached authentication result from ``_authenticate``
        tenant_context: Resolved tenant context from ``resolve_tenant_context``

    Returns:
        CurrentUser with user_id, username, and tenant_id
    """
    tenant_id = auth_result.api_key_tenant_id or TenantId(
        value=tenant_context.tenant_id
    )

    return CurrentUser(
        user_id=auth_result.user_id,
        username=auth_result.username,
        tenant_id=tenant_id,
    )


def get_user_service(
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    session: Annotated[AsyncSession, Depends(get_write_session)],
    probe: Annotated[UserServiceProbe, Depends(get_user_service_probe)],
    current_user: Annotated[CurrentUser, Depends(get_current_user_no_jit)],
) -> UserService:
    """Get UserService instance.

    Args:
        user_repo: User repository (shares session via FastAPI dependency caching)
        session: Database session for transaction management
        probe: User service probe for observability
        current_user: The authenticated user, used to scope the service to their tenant.

    Returns:
        UserService instance
    """
    return UserService(
        user_repository=user_repo,
        probe=probe,
        session=session,
        scope_to_tenant=current_user.tenant_id,
    )


async def get_current_user(
    current_user: Annotated[CurrentUser, Depends(get_current_user_no_jit)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    session: Annotated[AsyncSession, Depends(get_write_session)],
    probe: Annotated[UserServiceProbe, Depends(get_user_service_probe)],
    token: Annotated[str | None, Depends(oauth2_scheme)] = None,
) -> CurrentUser:
    """Authenticate with tenant context and JIT user provisioning.

    Wraps ``get_current_user_no_jit`` and adds JIT provisioning for
    JWT-authenticated users via ``_ensure_user_exists``.

    For API key authentication, JIT provisioning is skipped because
    the user who created the API key already exists.

    Args:
        current_user: Authenticated user with tenant context
        user_repo: Repository for JIT user provisioning
        session: Database session for JIT user provisioning
        probe: Domain probe for JIT provisioning observability
        token: Bearer token (present for JWT auth, None for API key auth)

    Returns:
        CurrentUser with user_id, username, and tenant_id
    """
    if token is not None:
        await _ensure_user_exists(
            current_user.user_id,
            current_user.username,
            user_repo,
            session,
            probe,
        )

    return current_user
