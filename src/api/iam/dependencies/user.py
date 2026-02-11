from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from iam.dependencies.api_key import get_api_key_service
from iam.dependencies.authentication import oauth2_scheme
from iam.dependencies.tenant_context import get_tenant_context
from iam.application.observability import (
    AuthenticationProbe,
    DefaultUserServiceProbe,
    UserServiceProbe,
)
from iam.application.services import UserService
from iam.application.services.api_key_service import APIKeyService
from iam.application.value_objects import CurrentUser
from iam.domain.value_objects import TenantId, UserId
from iam.dependencies.authentication import (
    get_authentication_probe,
    get_jwt_validator,
    JWTValidator,
)
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


async def resolve_tenant_context(
    validator: Annotated[JWTValidator, Depends(get_jwt_validator)],
    auth_probe: Annotated[AuthenticationProbe, Depends(get_authentication_probe)],
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
    token: Annotated[str | None, Depends(oauth2_scheme)] = None,
    x_tenant_id: Annotated[str | None, Header(alias="X-Tenant-ID")] = None,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> TenantContext:
    """Resolve tenant context for the current request.

    Extracts user identity from authentication credentials (JWT or API key)
    and resolves the tenant context via get_tenant_context. This bridges the
    gap between authentication (which provides user_id/username) and tenant
    resolution (which needs them for SpiceDB checks and auto-provisioning).

    For JWT-authenticated requests, user identity comes from token claims.
    For API key requests, tenant context is skipped here because the API key
    already carries its own tenant_id (handled in get_current_user_no_jit).

    In the API key case, a sentinel TenantContext is returned since the
    actual tenant_id will come from the API key itself.

    Args:
        validator: JWT validator for token validation
        auth_probe: Authentication probe for observability
        authz: Authorization provider for SpiceDB permission checks
        tenant_context_probe: Domain probe for tenant context observability
        tenant_repo: Repository for looking up tenants
        tenant_context_session: Dedicated database session for tenant context
            resolution. Passed to get_tenant_context so that auto-add member
            writes are wrapped in ``async with session.begin()`` and committed.
        token: Bearer token from Authorization header
        x_tenant_id: Optional X-Tenant-ID header value
        x_api_key: Optional X-API-Key header value

    Returns:
        TenantContext with the resolved tenant ID and source

    Raises:
        HTTPException: If tenant resolution fails (400/403/500)
    """
    iam_settings = get_iam_settings()

    # For JWT-authenticated requests, extract user identity from claims
    if token is not None:
        try:
            claims = await validator.validate_token(token)
            user_id = claims.sub
            username = claims.preferred_username or claims.sub
        except InvalidTokenError:
            # JWT validation failed - let get_current_user_no_jit handle the
            # 401 response. Return a placeholder that won't be used.
            return TenantContext(tenant_id="", source="header")

        return await get_tenant_context(
            x_tenant_id=x_tenant_id,
            user_id=user_id,
            username=username,
            authz=authz,
            probe=tenant_context_probe,
            single_tenant_mode=iam_settings.single_tenant_mode,
            tenant_repository=tenant_repo,
            default_tenant_name=iam_settings.default_tenant_name,
            bootstrap_admin_usernames=iam_settings.bootstrap_admin_usernames,
            session=tenant_context_session,
        )

    # For API key requests, the tenant comes from the API key itself.
    # Return a sentinel that get_current_user_no_jit will ignore in favor
    # of api_key.tenant_id.
    if x_api_key is not None:
        return TenantContext(tenant_id="", source="header")

    # Neither JWT nor API key - authentication will fail in
    # get_current_user_no_jit. Return a placeholder.
    return TenantContext(tenant_id="", source="header")


async def get_current_user_no_jit(
    validator: Annotated[JWTValidator, Depends(get_jwt_validator)],
    api_key_service: Annotated[APIKeyService, Depends(get_api_key_service)],
    auth_probe: Annotated[AuthenticationProbe, Depends(get_authentication_probe)],
    tenant_context: Annotated[TenantContext, Depends(resolve_tenant_context)],
    token: Annotated[str | None, Depends(oauth2_scheme)] = None,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> CurrentUser:
    """Authenticate via JWT Bearer token or X-API-Key header.

    Tries JWT first (if Authorization: Bearer present), then API Key.
    Returns CurrentUser on success, raises HTTPException(401) on failure.

    Does _NOT_ JIT provision the user. Use `get_current_user` if JIT provisioning is desired.

    Tenant context is resolved via the get_tenant_context dependency, which
    handles X-Tenant-ID header validation, SpiceDB authorization checks,
    and single-tenant mode auto-provisioning.

    Args:
        token: Bearer token from Authorization header (via OAuth2AuthorizationCodeBearer)
        x_api_key: API key from X-API-Key header
        tenant_context: Resolved tenant context from get_tenant_context dependency.
            For JWT auth, this contains the validated tenant ID.
            For API key auth, the tenant comes from the API key itself.
        validator: JWT validator for token validation
        api_key_service: The API key service for validation
        auth_probe: Authentication probe for observability

    Returns:
        CurrentUser with user_id, username, and tenant_id

    Raises:
        HTTPException 401: If neither auth method succeeds
    """
    # WWW-Authenticate header for 401 responses showing supported auth methods
    www_authenticate = "Bearer, API-Key"

    # Try JWT first (existing flow)
    if token is not None:
        try:
            claims = await validator.validate_token(token)

            # Map claims to user
            user_id = UserId(value=claims.sub)
            username = claims.preferred_username or claims.sub

            auth_probe.user_authenticated(user_id=claims.sub, username=username)

            return CurrentUser(
                user_id=user_id,
                username=username,
                tenant_id=TenantId(value=tenant_context.tenant_id),
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

        # API key is valid - user already exists (they created the key)
        auth_probe.api_key_authentication_succeeded(
            api_key_id=api_key.id.value,
            user_id=api_key.created_by_user_id.value,
        )

        return CurrentUser(
            user_id=api_key.created_by_user_id,
            username=f"api-key:{api_key.id}",
            tenant_id=api_key.tenant_id,
        )

    # Neither provided
    auth_probe.authentication_failed(reason="Missing authorization")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": www_authenticate},
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
    user_service: Annotated[UserService, Depends(get_user_service)],
    token: Annotated[str | None, Depends(oauth2_scheme)] = None,
) -> CurrentUser:
    """Authenticate via JWT Bearer token or X-API-Key header.

    Tries JWT first (if Authorization: Bearer present), then API Key.
    Returns CurrentUser on success, raises HTTPException(401) on failure.

    Args:
        token: Bearer token from Authorization header (via OAuth2AuthorizationCodeBearer)
        user_service: The user service for JIT provisioning
        current_user: The current authenticated user

    Returns:
        CurrentUser with user_id, username, and tenant_id

    Raises:
        HTTPException 401: If neither auth method succeeds
    """
    # If the user is authenticated via a bearer token (i.e. actual user identity)
    if token is not None:
        # JIT user provisioning
        await user_service.ensure_user(
            user_id=current_user.user_id, username=current_user.username
        )

        return current_user

    # If the user is authenticated via an API key (no need to provision a user)
    return current_user
