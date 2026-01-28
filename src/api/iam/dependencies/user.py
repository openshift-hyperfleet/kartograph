from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from iam.dependencies.api_key import get_api_key_service
from iam.dependencies.authentication import oauth2_scheme
from iam.dependencies.tenant import get_default_tenant_id
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
from iam.infrastructure.user_repository import UserRepository
from infrastructure.database.dependencies import get_write_session
from shared_kernel.auth import InvalidTokenError


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


async def get_current_user_no_jit(
    validator: Annotated[JWTValidator, Depends(get_jwt_validator)],
    api_key_service: Annotated[APIKeyService, Depends(get_api_key_service)],
    auth_probe: Annotated[AuthenticationProbe, Depends(get_authentication_probe)],
    x_tenant_id: Annotated[str, Depends(get_default_tenant_id)],
    token: Annotated[str | None, Depends(oauth2_scheme)] = None,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> CurrentUser:
    """Authenticate via JWT Bearer token or X-API-Key header.

    Tries JWT first (if Authorization: Bearer present), then API Key.
    Returns CurrentUser on success, raises HTTPException(401) on failure.

    Does _NOT_ JIT provision the user. Use `get_current_user` if JIT provisioning is desired.

    Args:
        token: Bearer token from Authorization header (via OAuth2AuthorizationCodeBearer)
        x_api_key: API key from X-API-Key header
        x_tenant_id: Tenant ID. For now, it's hard-coded, but in the future would come from X-Tenant-ID header.
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
                tenant_id=TenantId(value=x_tenant_id),
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
            username=f"api-key:{api_key.name}",
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
        tenant_id: The tenant ID to which the user service will be scoped.
            For now, it's hard-coded to the default tenant. In the future,
            this would/could come from an X-Tenant-ID header.

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
        x_api_key: API key from X-API-Key header
        validator: JWT validator for token validation
        user_service: The user service for JIT provisioning
        api_key_service: The API key service for validation
        auth_probe: Authentication probe for observability

    Returns:
        CurrentUser with user_id, username, and tenant_id

    Raises:
        HTTPException 401: If neither auth method succeeds
    """
    # If the user is authenticated via a bearer token (i.e. actual user identity)
    if token is None:
        # JIT user provisioning
        await user_service.ensure_user(
            user_id=current_user.user_id, username=current_user.username
        )

        return current_user

    # If the user is authenticated via an API key (no need to provision a user)
    return current_user
