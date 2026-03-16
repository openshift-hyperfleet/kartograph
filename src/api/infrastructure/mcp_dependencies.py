"""MCP-specific cross-context dependency composition.

This is the integration/composition layer for MCP resources and tools.
It's the ONLY place allowed to wire together Graph, Query, and IAM contexts.

Future service decomposition: When splitting into microservices, this is
where you'd swap GraphSchemaService for an HTTP REST client that calls
the Graph service's API endpoints. The Query context's ISchemaService port
remains unchanged.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from iam.domain.aggregates.api_key import APIKey
    from query.ports.schema import ISchemaService

# Validated keys are cached for the process lifetime. A key that passes
# validation once is considered permanently valid — no TTL, no re-validation.
# If a key needs to be revoked, restart the process.
_validated_key_cache: set[str] = set()
_validated_key_objects: dict[str, "APIKey"] = {}


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
_mcp_auth_sessionmaker = None


async def validate_mcp_api_key(secret: str) -> "APIKey | None":
    """Validate an API key secret for MCP authentication.

    Valid keys are cached for the process lifetime — a key that passes once
    is never re-checked against the DB. Zero DB access on every subsequent
    request, regardless of how many concurrent agents share the key.

    Args:
        secret: The plaintext API key secret to validate.

    Returns:
        The APIKey aggregate if valid, None otherwise.
    """
    if secret in _validated_key_cache:
        return _validated_key_objects[secret]

    key = await _validate_mcp_api_key_uncached(secret)
    if key is not None:
        _validated_key_cache.add(secret)
        _validated_key_objects[secret] = key
    return key


async def _validate_mcp_api_key_uncached(secret: str) -> "APIKey | None":
    """Full DB validation — only called on cache miss or TTL expiry."""
    from iam.application.services.api_key_service import APIKeyService
    from iam.infrastructure.api_key_repository import APIKeyRepository
    from infrastructure.outbox.repository import OutboxRepository

    # Both engine and sessionmaker are module-level singletons — creating a new
    # sessionmaker on every request was unnecessarily rebuilding the object and
    # obscuring that the underlying connection pool was being shared.
    sessionmaker = _get_mcp_auth_sessionmaker()

    async with sessionmaker() as session:
        outbox = OutboxRepository(session=session)
        repo = APIKeyRepository(session=session, outbox=outbox)
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


def _get_mcp_auth_sessionmaker():
    """Get or create the cached async sessionmaker for MCP auth.

    The sessionmaker is a lightweight factory — it should be a singleton,
    not rebuilt on every request. Rebuilding it per-call was hiding the fact
    that the underlying pool was shared and masking pool exhaustion under load.
    """
    global _mcp_auth_sessionmaker
    if _mcp_auth_sessionmaker is None:
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

        _mcp_auth_sessionmaker = async_sessionmaker(
            _get_mcp_auth_engine(), expire_on_commit=False, class_=AsyncSession
        )
    return _mcp_auth_sessionmaker


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
