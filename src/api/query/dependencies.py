"""Dependency injection for Query bounded context.

Provides dependencies local to the Query context only.
Cross-context composition is handled in infrastructure.mcp_dependencies.
"""

from collections.abc import Generator
from typing import TYPE_CHECKING, Annotated

from fastmcp.dependencies import Depends

from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.connection_pool import ConnectionPool
from infrastructure.dependencies import get_age_connection_pool
from infrastructure.settings import get_database_settings
from query.application.observability import (
    DefaultQueryServiceProbe,
    DefaultSchemaResourceProbe,
    QueryServiceProbe,
    SchemaResourceProbe,
)
from query.application.services import MCPQueryService
from query.infrastructure.query_repository import QueryGraphRepository

if TYPE_CHECKING:
    from graph.infrastructure.age_client import AgeGraphClient


def get_query_service_probe() -> QueryServiceProbe:
    """Get QueryServiceProbe instance.

    Returns:
        DefaultQueryServiceProbe instance for observability
    """
    return DefaultQueryServiceProbe()


def get_mcp_graph_client(
    pool: Annotated[ConnectionPool, Depends(get_age_connection_pool)],
) -> Generator["AgeGraphClient", None, None]:
    """Get request-scoped AGE graph client for MCP operations.

    Each MCP request gets its own client with a connection from the pool.
    Connection is automatically returned to pool on cleanup.

    Args:
        pool: Application-scoped connection pool

    Yields:
        Connected AgeGraphClient instance
    """
    # Runtime import to avoid static dependency on Graph infrastructure
    from graph.infrastructure.age_client import AgeGraphClient

    settings = get_database_settings()
    factory = ConnectionFactory(settings, pool=pool)
    client = AgeGraphClient(settings, connection_factory=factory)
    client.connect()
    try:
        yield client
    finally:
        client.disconnect()


def get_mcp_query_service(
    client: Annotated["AgeGraphClient", Depends(get_mcp_graph_client)],
    probe: Annotated[QueryServiceProbe, Depends(get_query_service_probe)],
) -> MCPQueryService:
    """Get MCPQueryService for MCP operations.

    Args:
        client: Request-scoped graph client
        probe: Query service probe for observability

    Returns:
        MCPQueryService instance
    """
    repository = QueryGraphRepository(client=client)
    return MCPQueryService(repository=repository, probe=probe)


def get_schema_resource_probe() -> SchemaResourceProbe:
    """Get schema resource probe for observability.

    Returns:
        SchemaResourceProbe instance for domain event emission
    """
    return DefaultSchemaResourceProbe()
