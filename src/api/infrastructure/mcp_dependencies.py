"""MCP-specific cross-context dependency composition.

This is the integration/composition layer for MCP resources and tools.
It's the ONLY place allowed to wire together Graph, Query, and IAM contexts.

Future service decomposition: When splitting into microservices, this is
where you'd swap GraphSchemaService for an HTTP REST client that calls
the Graph service's API endpoints. The Query context's ISchemaService port
remains unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from iam.domain.aggregates.api_key import APIKey
    from query.ports.schema import ISchemaService


@dataclass(frozen=True)
class MCPBearerResult:
    """Result of validating a Bearer token for MCP authentication.

    Carries the fields needed by MCPApiKeyAuthMiddleware to build
    an MCPAuthContext.
    """

    user_id: str
    tenant_id: str


def get_schema_service_for_mcp() -> "ISchemaService":
    """Get schema service for MCP resources.

    Composes Graph context's GraphSchemaService to satisfy Query context's
    ISchemaService port. This is the integration point between contexts.

    Returns:
        Schema service implementation (GraphSchemaService)
    """
    from graph.application.services import GraphSchemaService
    from graph.dependencies import get_type_definition_repository
    from query.ports.schema import ISchemaService

    type_def_repo = get_type_definition_repository()
    service = GraphSchemaService(type_definition_repository=type_def_repo)

    # GraphSchemaService structurally satisfies ISchemaService protocol
    return cast(ISchemaService, service)


_mcp_auth_engine = None


async def validate_mcp_api_key(secret: str) -> APIKey | None:
    """Validate an API key secret for MCP authentication.

    This is the composition function that wires IAM's APIKeyService
    into the MCP auth middleware. It creates its own database session
    per-request because it operates outside FastAPI's DI system.

    Uses runtime imports to avoid static dependencies from the
    infrastructure module on bounded contexts at the module level.

    Args:
        secret: The plaintext API key secret to validate.

    Returns:
        The APIKey aggregate if valid, None otherwise.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from iam.application.services.api_key_service import APIKeyService
    from iam.infrastructure.api_key_repository import APIKeyRepository
    from infrastructure.outbox.repository import OutboxRepository

    # Lazily cached engine (reused across calls)
    engine = _get_mcp_auth_engine()
    sessionmaker = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )

    async with sessionmaker() as session:
        outbox = OutboxRepository(session=session)
        repo = APIKeyRepository(session=session, outbox=outbox)
        # AuthorizationProvider not needed for validate_and_get_key
        # (it doesn't do authz checks), but APIKeyService requires it.
        # Cast the no-op stub to satisfy mypy's structural check.
        from shared_kernel.authorization.protocols import AuthorizationProvider

        service = APIKeyService(
            session=session,
            api_key_repository=repo,
            authz=cast(AuthorizationProvider, _NoOpAuthz()),
        )
        return await service.validate_and_get_key(secret)


def _get_mcp_auth_engine():
    """Get or create the cached async engine for MCP auth.

    Uses a module-level cache to reuse the engine across requests,
    similar to how get_age_connection_pool() caches the pool.
    """
    global _mcp_auth_engine
    if _mcp_auth_engine is None:
        from infrastructure.database.engines import create_write_engine
        from infrastructure.settings import get_database_settings

        settings = get_database_settings()
        _mcp_auth_engine = create_write_engine(settings)
    return _mcp_auth_engine


class _NoOpAuthz:
    """No-op authorization provider for MCP API key validation.

    The validate_and_get_key() method does not perform authorization
    checks, but APIKeyService requires an AuthorizationProvider in
    its constructor. This stub satisfies that requirement.

    Only used with cast(AuthorizationProvider, ...) -- the methods
    below are never actually called.
    """

    async def check_permission(
        self, resource: str, permission: str, subject: str
    ) -> bool:
        return False

    async def bulk_check_permission(self, requests: list) -> set[str]:
        return set()

    async def write_relationship(
        self, resource: str, relation: str, subject: str
    ) -> None:
        pass

    async def write_relationships(self, relationships: list) -> None:
        pass

    async def delete_relationship(
        self, resource: str, relation: str, subject: str
    ) -> None:
        pass

    async def delete_relationships(self, relationships: list) -> None:
        pass

    async def delete_relationships_by_filter(
        self,
        resource_type: str,
        resource_id: str | None = None,
        relation: str | None = None,
        subject_type: str | None = None,
        subject_id: str | None = None,
    ) -> None:
        pass

    async def lookup_resources(
        self, resource_type: str, permission: str, subject: str
    ) -> list[str]:
        return []

    async def lookup_subjects(
        self,
        resource: str,
        relation: str,
        subject_type: str,
        optional_subject_relation: str | None = None,
    ) -> list:
        return []

    async def read_relationships(
        self,
        resource_type: str,
        resource_id: str | None = None,
        relation: str | None = None,
        subject_type: str | None = None,
        subject_id: str | None = None,
    ) -> list:
        return []


async def validate_mcp_bearer_token(
    token: str, tenant_id: str | None
) -> MCPBearerResult | None:
    """Validate a Bearer JWT token for MCP authentication.

    Uses the same OIDC JWT validation as the REST endpoints.
    The tenant is resolved from the X-Tenant-ID header (or single-tenant
    mode auto-selection), then verified via SpiceDB to ensure the user
    is a member of the resolved tenant.

    Args:
        token: The raw JWT Bearer token string.
        tenant_id: Optional X-Tenant-ID header value.

    Returns:
        MCPBearerResult with user_id and tenant_id on success, None on failure.
    """
    from iam.dependencies.authentication import get_jwt_validator
    from infrastructure.authorization_dependencies import get_spicedb_client
    from infrastructure.settings import get_iam_settings
    from shared_kernel.auth import InvalidTokenError
    from shared_kernel.authorization.types import (
        Permission,
        ResourceType,
        format_resource,
        format_subject,
    )

    validator = get_jwt_validator()

    try:
        claims = await validator.validate_token(token)
    except InvalidTokenError:
        return None

    # Resolve tenant: use header if provided, fall back to single-tenant
    # auto-selection (same logic as resolve_tenant_context for simple cases).
    effective_tenant_id = tenant_id
    if not effective_tenant_id:
        iam_settings = get_iam_settings()
        if iam_settings.single_tenant_mode:
            effective_tenant_id = await _resolve_single_tenant_id()

    if not effective_tenant_id:
        return None

    # Verify the user has view permission on the tenant (membership check).
    # This mirrors the SpiceDB check in get_tenant_context().
    authz = get_spicedb_client()
    has_permission = await authz.check_permission(
        resource=format_resource(ResourceType.TENANT, effective_tenant_id),
        permission=Permission.VIEW,
        subject=format_subject(ResourceType.USER, claims.sub),
    )
    if not has_permission:
        return None

    return MCPBearerResult(
        user_id=claims.sub,
        tenant_id=effective_tenant_id,
    )


async def _resolve_single_tenant_id() -> str | None:
    """Look up the default tenant ID in single-tenant mode."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from infrastructure.settings import get_iam_settings

    iam_settings = get_iam_settings()
    engine = _get_mcp_auth_engine()
    sessionmaker = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )

    async with sessionmaker() as session:
        from sqlalchemy import select

        from iam.infrastructure.models import TenantModel

        stmt = select(TenantModel.id).where(
            TenantModel.name == iam_settings.default_tenant_name
        )
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        return str(row) if row else None
