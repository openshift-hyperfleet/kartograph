"""Dependency injection for Graph bounded context.

Composes infrastructure resources (pool) with graph-specific components
(client, repositories, services).
"""

from collections.abc import Generator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from iam.application.value_objects import CurrentUser
from iam.dependencies.user import get_current_user
from infrastructure.authorization_dependencies import get_spicedb_client
from shared_kernel.authorization.protocols import AuthorizationProvider

from graph.application.observability import (
    DefaultGraphServiceProbe,
    DefaultSchemaServiceProbe,
    GraphServiceProbe,
    SchemaServiceProbe,
)
from graph.application.services import (
    GraphMutationService,
    GraphQueryService,
    GraphSchemaService,
    GraphSecureEnclaveService,
)
from graph.infrastructure.age_bulk_loading import AgeBulkLoadingStrategy
from graph.infrastructure.age_client import AgeGraphClient
from graph.infrastructure.graph_repository import GraphExtractionReadOnlyRepository
from graph.infrastructure.mutation_applier import MutationApplier
from graph.infrastructure.type_definition_repository import (
    InMemoryTypeDefinitionRepository,
)
from graph.ports.repositories import ITypeDefinitionRepository
from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.connection_pool import ConnectionPool
from infrastructure.dependencies import get_age_connection_pool
from infrastructure.settings import get_database_settings


def get_graph_service_probe() -> GraphServiceProbe:
    """Get GraphServiceProbe instance.

    Returns:
        DefaultGraphServiceProbe instance for observability
    """
    return DefaultGraphServiceProbe()


def get_schema_service_probe() -> SchemaServiceProbe:
    """Get SchemaServiceProbe instance.

    Returns:
        DefaultSchemaServiceProbe instance for observability
    """
    return DefaultSchemaServiceProbe()


def get_age_graph_client(
    pool: Annotated[ConnectionPool, Depends(get_age_connection_pool)],
) -> Generator[AgeGraphClient, None, None]:
    """Get request-scoped AGE graph client.

    Each request gets its own client with a connection from the pool.
    Connection is automatically returned to pool on cleanup.

    Args:
        pool: Application-scoped connection pool

    Yields:
        Connected AgeGraphClient instance
    """
    settings = get_database_settings()
    factory = ConnectionFactory(settings, pool=pool)
    client = AgeGraphClient(settings, connection_factory=factory)
    client.connect()
    try:
        yield client
    finally:
        client.disconnect()


def get_graph_query_service(
    client: Annotated[AgeGraphClient, Depends(get_age_graph_client)],
    probe: Annotated[GraphServiceProbe, Depends(get_graph_service_probe)],
    graph_id: str = get_database_settings().graph_name,
) -> GraphQueryService:
    """Get GraphQueryService for scoped read operations.

    Args:
        client: Request-scoped graph client
        probe: Graph service probe for observability
        graph_id: Data source ID for query scoping

    Returns:
        GraphQueryService instance
    """
    repository = GraphExtractionReadOnlyRepository(
        client=client,
        graph_id=graph_id,
    )
    return GraphQueryService(repository=repository, probe=probe)


def get_graph_secure_enclave_service(
    query_service: Annotated[GraphQueryService, Depends(get_graph_query_service)],
    authz: Annotated[AuthorizationProvider, Depends(get_spicedb_client)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> GraphSecureEnclaveService:
    """Get GraphSecureEnclaveService for authorized read operations.

    The secure enclave wraps the GraphQueryService and applies per-entity
    authorization based on each entity's knowledge_graph_id property.
    Unauthorized entities are redacted rather than removed, preserving
    graph topology while protecting sensitive content.

    Args:
        query_service: Underlying graph query service.
        authz: Authorization provider (SpiceDB client).
        current_user: The authenticated user making the request.

    Returns:
        GraphSecureEnclaveService instance scoped to the requesting user.
    """
    return GraphSecureEnclaveService(
        query_service=query_service,
        authz=authz,
        user_id=current_user.user_id.value,
    )


def get_mutation_applier(
    client: Annotated[AgeGraphClient, Depends(get_age_graph_client)],
) -> MutationApplier:
    """Get MutationApplier instance.

    Args:
        client: Request-scoped graph client

    Returns:
        MutationApplier instance with AGE bulk loading strategy
    """
    # AgeBulkLoadingStrategy creates its own AgeIndexingStrategy by default
    strategy = AgeBulkLoadingStrategy()
    return MutationApplier(client=client, bulk_loading_strategy=strategy)


@lru_cache
def get_type_definition_repository() -> ITypeDefinitionRepository:
    """Get type definition repository (in-memory for MVP).

    Returns:
        In-memory type definition repository
    """
    return InMemoryTypeDefinitionRepository()


def get_graph_mutation_service(
    applier: Annotated[MutationApplier, Depends(get_mutation_applier)],
    type_def_repo: Annotated[
        ITypeDefinitionRepository, Depends(get_type_definition_repository)
    ],
) -> GraphMutationService:
    """Get GraphMutationService instance.

    Args:
        applier: Mutation applier
        type_def_repo: Type definition repository

    Returns:
        GraphMutationService instance
    """
    return GraphMutationService(
        mutation_applier=applier,
        type_definition_repository=type_def_repo,
    )


def get_schema_service(
    type_def_repo: Annotated[
        ITypeDefinitionRepository, Depends(get_type_definition_repository)
    ],
    probe: Annotated[SchemaServiceProbe, Depends(get_schema_service_probe)],
) -> GraphSchemaService:
    """Get GraphSchemaService instance.

    Args:
        type_def_repo: Type definition repository
        probe: Schema service probe for observability

    Returns:
        GraphSchemaService instance
    """
    return GraphSchemaService(type_definition_repository=type_def_repo, probe=probe)
