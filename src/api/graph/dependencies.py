"""Dependency injection for Graph bounded context.

Composes infrastructure resources (pool) with graph-specific components
(client, repositories, services).
"""

from collections.abc import Generator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Query

from graph.application.services import (
    GraphMutationService,
    GraphQueryService,
    GraphSchemaService,
)
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
    data_source_id: str = Query(...),
) -> GraphQueryService:
    """Get GraphQueryService for scoped read operations.

    Args:
        client: Request-scoped graph client
        data_source_id: Data source ID for query scoping

    Returns:
        GraphQueryService instance
    """
    repository = GraphExtractionReadOnlyRepository(
        client=client,
        data_source_id=data_source_id,
    )
    return GraphQueryService(repository=repository)


def get_mutation_applier(
    client: Annotated[AgeGraphClient, Depends(get_age_graph_client)],
) -> MutationApplier:
    """Get MutationApplier instance.

    Args:
        client: Request-scoped graph client

    Returns:
        MutationApplier instance
    """
    return MutationApplier(client=client)


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
) -> GraphSchemaService:
    """Get GraphSchemaService instance.

    Args:
        type_def_repo: Type definition repository

    Returns:
        GraphSchemaService instance
    """
    return GraphSchemaService(type_definition_repository=type_def_repo)
