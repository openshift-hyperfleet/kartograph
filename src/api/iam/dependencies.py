"""Dependency injection for IAM bounded context.

Composes infrastructure resources (database sessions, authorization) with
IAM-specific components (repositories, services).
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2AuthorizationCodeBearer
from sqlalchemy.ext.asyncio import AsyncSession

from iam.application.observability import (
    AuthenticationProbe,
    DefaultAuthenticationProbe,
    DefaultGroupServiceProbe,
    DefaultTenantServiceProbe,
    DefaultUserServiceProbe,
    GroupServiceProbe,
    TenantServiceProbe,
    UserServiceProbe,
)
from iam.application.services import GroupService, TenantService, UserService
from iam.application.value_objects import CurrentUser
from iam.domain.value_objects import TenantId, UserId
from iam.infrastructure.group_repository import GroupRepository
from iam.infrastructure.tenant_repository import TenantRepository
from iam.infrastructure.user_repository import UserRepository
from infrastructure.authorization_dependencies import get_spicedb_client
from infrastructure.database.dependencies import get_write_session
from infrastructure.outbox.repository import OutboxRepository
from infrastructure.settings import get_oidc_settings
from shared_kernel.auth import InvalidTokenError, JWTValidator
from shared_kernel.auth.observability import DefaultJWTValidatorProbe
from shared_kernel.authorization.protocols import AuthorizationProvider


def _get_oidc_issuer_url() -> str:
    """Get OIDC issuer URL from environment or use default.

    This is used to configure the OAuth2 security scheme at module load time,
    before full OIDC settings validation occurs. The default matches
    OIDCSettings.issuer_url for consistency.
    """
    import os

    return os.getenv(
        "KARTOGRAPH_OIDC_ISSUER_URL",
        "http://localhost:8080/realms/kartograph",
    )


def _create_oauth2_scheme() -> OAuth2AuthorizationCodeBearer:
    """Create OAuth2 security scheme for Swagger UI integration.

    Uses the OIDC issuer URL to configure authorization code flow endpoints.
    This enables Swagger UI's Authorize button to work with Keycloak.
    """
    issuer = _get_oidc_issuer_url()

    return OAuth2AuthorizationCodeBearer(
        authorizationUrl=f"{issuer}/protocol/openid-connect/auth",
        tokenUrl=f"{issuer}/protocol/openid-connect/token",
        refreshUrl=f"{issuer}/protocol/openid-connect/token",
        scopes={
            "openid": "OpenID Connect",
            "profile": "User profile",
            "email": "User email",
        },
        auto_error=False,
    )


# Create OAuth2 security scheme for Swagger UI integration
oauth2_scheme = _create_oauth2_scheme()

# Module-level cache for default tenant ID (populated at startup)
_default_tenant_id: TenantId | None = None


def set_default_tenant_id(tenant_id: TenantId) -> None:
    """Set the default tenant ID (called during app startup).

    Args:
        tenant_id: The default tenant ID to cache
    """
    global _default_tenant_id
    _default_tenant_id = tenant_id


def get_default_tenant_id() -> TenantId:
    """Get the cached default tenant ID.

    Returns:
        The default tenant ID

    Raises:
        RuntimeError: If default tenant hasn't been initialized
    """
    if _default_tenant_id is None:
        raise RuntimeError(
            "Default tenant not initialized. Ensure app startup completed successfully."
        )
    return _default_tenant_id


def get_user_service_probe() -> UserServiceProbe:
    """Get UserServiceProbe instance.

    Returns:
        DefaultUserServiceProbe instance for observability
    """
    return DefaultUserServiceProbe()


def get_group_service_probe() -> GroupServiceProbe:
    """Get GroupServiceProbe instance.

    Returns:
        DefaultGroupServiceProbe instance for observability
    """
    return DefaultGroupServiceProbe()


def get_tenant_service_probe() -> TenantServiceProbe:
    """Get TenantServiceProbe instance.

    Returns:
        DefaultTenantServiceProbe instance for observability
    """
    return DefaultTenantServiceProbe()


def get_outbox_repository(
    session: Annotated[AsyncSession, Depends(get_write_session)],
) -> OutboxRepository:
    """Get OutboxRepository instance.

    The repository accepts pre-serialized payloads, making it context-agnostic.
    Serialization is handled by the bounded context's repository.

    Args:
        session: Async database session (shared with calling repository)

    Returns:
        OutboxRepository instance
    """
    return OutboxRepository(session=session)


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


def get_group_repository(
    session: Annotated[AsyncSession, Depends(get_write_session)],
    authz: Annotated[AuthorizationProvider, Depends(get_spicedb_client)],
    outbox: Annotated[OutboxRepository, Depends(get_outbox_repository)],
) -> GroupRepository:
    """Get GroupRepository instance.

    Args:
        session: Async database session
        authz: Authorization provider (SpiceDB client)
        outbox: Outbox repository for transactional outbox pattern

    Returns:
        GroupRepository instance with outbox pattern enabled
    """
    return GroupRepository(session=session, authz=authz, outbox=outbox)


def get_tenant_repository(
    session: Annotated[AsyncSession, Depends(get_write_session)],
    outbox: Annotated[OutboxRepository, Depends(get_outbox_repository)],
) -> TenantRepository:
    """Get TenantRepository instance.

    Args:
        session: Async database session
        outbox: Outbox repository for transactional outbox pattern

    Returns:
        TenantRepository instance with outbox pattern enabled
    """
    return TenantRepository(session=session, outbox=outbox)


def get_user_service(
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    session: Annotated[AsyncSession, Depends(get_write_session)],
    probe: Annotated[UserServiceProbe, Depends(get_user_service_probe)],
) -> UserService:
    """Get UserService instance.

    Args:
        user_repo: User repository (shares session via FastAPI dependency caching)
        session: Database session for transaction management
        probe: User service probe for observability

    Returns:
        UserService instance
    """
    return UserService(user_repository=user_repo, probe=probe, session=session)


def get_group_service(
    group_repo: Annotated[GroupRepository, Depends(get_group_repository)],
    session: Annotated[AsyncSession, Depends(get_write_session)],
    authz: Annotated[AuthorizationProvider, Depends(get_spicedb_client)],
    group_service_probe: Annotated[GroupServiceProbe, Depends(get_group_service_probe)],
) -> GroupService:
    """Get GroupService instance.

    Args:
        group_repo: Group repository (shares session via FastAPI dependency caching)
        session: Database session for transaction management
        authz: Authorization provider (SpiceDB client)
        group_service_probe: Group service probe for observability

    Returns:
        GroupService instance
    """
    return GroupService(
        session=session,
        group_repository=group_repo,
        authz=authz,
        probe=group_service_probe,
    )


def get_tenant_service(
    tenant_repo: Annotated[TenantRepository, Depends(get_tenant_repository)],
    session: Annotated[AsyncSession, Depends(get_write_session)],
    tenant_service_probe: Annotated[
        TenantServiceProbe, Depends(get_tenant_service_probe)
    ],
) -> TenantService:
    """Get TenantService instance.

    Args:
        tenant_repo: Tenant repository (shares session via FastAPI dependency caching)
        session: Database session for transaction management
        tenant_service_probe: Tenant service probe for observability

    Returns:
        TenantService instance
    """
    return TenantService(
        tenant_repository=tenant_repo,
        session=session,
        probe=tenant_service_probe,
    )


def get_jwt_validator() -> JWTValidator:
    """Get configured JWT validator.

    Returns:
        JWTValidator instance configured from OIDC settings.
    """
    settings = get_oidc_settings()
    probe = DefaultJWTValidatorProbe()
    return JWTValidator(
        issuer_url=settings.issuer_url,
        audience=settings.effective_audience,
        probe=probe,
        user_id_claim=settings.user_id_claim,
        username_claim=settings.username_claim,
    )


def get_authentication_probe() -> AuthenticationProbe:
    """Get AuthenticationProbe instance.

    Returns:
        DefaultAuthenticationProbe instance for observability
    """
    return DefaultAuthenticationProbe()


async def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    validator: Annotated[JWTValidator, Depends(get_jwt_validator)],
    user_service: Annotated[UserService, Depends(get_user_service)],
    auth_probe: Annotated[AuthenticationProbe, Depends(get_authentication_probe)],
) -> CurrentUser:
    """Get current user from JWT Bearer token.

    Validates the JWT and provisions user if needed (JIT).

    Args:
        token: Bearer token from Authorization header (via OAuth2AuthorizationCodeBearer)
        validator: JWT validator for token validation
        user_service: The user service for JIT provisioning
        auth_probe: Authentication probe for observability

    Returns:
        CurrentUser with user_id, username, and tenant_id

    Raises:
        HTTPException 401: If token missing, invalid, or expired
    """
    if token is None:
        auth_probe.authentication_failed(reason="Missing authorization header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        claims = await validator.validate_token(token)
    except InvalidTokenError as e:
        auth_probe.authentication_failed(reason=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    # Map claims to user
    user_id = UserId(value=claims.sub)
    username = claims.preferred_username or claims.sub
    tenant_id = get_default_tenant_id()

    # JIT user provisioning
    await user_service.ensure_user(user_id=user_id, username=username)

    auth_probe.user_authenticated(user_id=claims.sub, username=username)

    return CurrentUser(user_id=user_id, username=username, tenant_id=tenant_id)
