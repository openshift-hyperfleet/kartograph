from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, status

from graph.application.services import GraphMutationService, GraphQueryService
from graph.infrastructure.age_client import AgeGraphClient
from graph.infrastructure.graph_repository import GraphExtractionReadOnlyRepository
from graph.infrastructure.mutation_applier import MutationApplier
from graph.infrastructure.type_definition_repository import (
    InMemoryTypeDefinitionRepository,
)
from graph.ports.repositories import ITypeDefinitionRepository
from graph.presentation import routes as graph_routes
from infrastructure.settings import get_database_settings

app = FastAPI()


@lru_cache
def get_graph_client() -> AgeGraphClient:
    """Get a cached AgeGraphClient instance."""
    settings = get_database_settings()
    client = AgeGraphClient(settings)
    return client


def get_graph_query_service(
    client: Annotated[AgeGraphClient, Depends(get_graph_client)],
    data_source_id: str = Query(...),
) -> GraphQueryService:
    """Get a GraphQueryService instance."""
    if not client.is_connected():
        client.connect()

    repository = GraphExtractionReadOnlyRepository(
        client=client,
        data_source_id=data_source_id,
    )
    return GraphQueryService(repository=repository)


@lru_cache
def get_mutation_applier(
    client: Annotated[AgeGraphClient, Depends(get_graph_client)],
) -> MutationApplier:
    """Get a cached MutationApplier instance."""
    if not client.is_connected():
        client.connect()

    return MutationApplier(client=client)


@lru_cache
def get_type_definition_repository() -> ITypeDefinitionRepository:
    """Get a cached TypeDefinitionRepository instance.

    Uses InMemoryTypeDefinitionRepository as MVP implementation.
    This will be replaced with a persistent repository in future iterations.
    """
    return InMemoryTypeDefinitionRepository()


def get_graph_mutation_service(
    applier: Annotated[MutationApplier, Depends(get_mutation_applier)],
    type_def_repo: Annotated[
        ITypeDefinitionRepository, Depends(get_type_definition_repository)
    ],
) -> GraphMutationService:
    """Get a GraphMutationService instance."""
    return GraphMutationService(
        mutation_applier=applier,
        type_definition_repository=type_def_repo,
    )


# Include Graph bounded context routes
app.include_router(graph_routes.router)

# Override Graph route dependency injection
app.dependency_overrides[graph_routes.get_query_service] = get_graph_query_service
app.dependency_overrides[graph_routes.get_mutation_service] = get_graph_mutation_service


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/db")
def health_db(
    client: Annotated[AgeGraphClient, Depends(get_graph_client)],
) -> dict:
    """Check database connection health.

    Returns the connection status and graph name.
    """
    try:
        if not client.is_connected():
            client.connect()

        is_healthy = client.verify_connection()

        return {
            "status": "ok" if is_healthy else "unhealthy",
            "connected": client.is_connected(),
            "graph_name": client.graph_name,
        }
    except Exception as e:
        return {
            "status": "error",
            "connected": False,
            "error": str(e),
        }


@app.get("/util/nodes")
def get_nodes(
    service: Annotated[GraphQueryService, Depends(get_graph_query_service)],
) -> dict:
    """Query all nodes in the graph.

    Returns nodes in domain NodeRecord format via the application service.
    """
    try:
        # Use exploration query through the service
        results = service.execute_exploration_query("MATCH (n) RETURN n")

        # Convert to serializable format
        nodes = [r.get("node", r) for r in results if r]

        return {
            "nodes": nodes,
            "count": len(nodes),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query nodes: {e}",
        ) from e


@app.delete("/util/nodes")
def delete_nodes(
    client: Annotated[AgeGraphClient, Depends(get_graph_client)],
) -> dict:
    """Delete all nodes in the graph.

    Returns:
        Dictionary with count of deleted nodes
    """
    try:
        if not client.is_connected():
            client.connect()

        # First count the nodes
        count_query = "MATCH (n) RETURN count(n)"
        count_result = client.execute_cypher(count_query)
        deleted_count = int(count_result.rows[0][0]) if count_result.rows else 0

        # Delete all nodes
        delete_query = "MATCH (n) DETACH DELETE n"
        client.execute_cypher(delete_query)

        return {"deleted": deleted_count}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete nodes: {e}",
        ) from e


@app.delete("/util/edges")
def delete_edges(
    client: Annotated[AgeGraphClient, Depends(get_graph_client)],
) -> dict:
    """Delete all edges in the graph.

    Returns:
        Dictionary with count of deleted edges
    """
    try:
        if not client.is_connected():
            client.connect()

        # First count the edges
        count_query = "MATCH ()-[r]-() RETURN count(r)"
        count_result = client.execute_cypher(count_query)
        deleted_count = int(count_result.rows[0][0]) if count_result.rows else 0

        # Delete all edges
        delete_query = "MATCH ()-[r]-() DELETE r"
        client.execute_cypher(delete_query)

        return {"deleted": deleted_count}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete edges: {e}",
        ) from e
