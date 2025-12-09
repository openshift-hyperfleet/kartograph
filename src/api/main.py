from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status

from graph.application.services import GraphQueryService
from graph.infrastructure.age_client import AgeGraphClient
from graph.infrastructure.graph_repository import GraphReadOnlyRepository
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
) -> GraphQueryService:
    """Get a GraphQueryService instance.

    Note: data_source_id is hardcoded for now - will be derived from
    request context in future iterations.
    """
    if not client.is_connected():
        client.connect()

    repository = GraphReadOnlyRepository(
        client=client,
        data_source_id="default",  # TODO: Derive from request context
    )
    return GraphQueryService(repository=repository)


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


@app.post("/nodes", status_code=status.HTTP_201_CREATED)
def create_nodes(
    client: Annotated[AgeGraphClient, Depends(get_graph_client)],
    count: int = 1,
) -> dict:
    """Create N nodes in the graph.

    Args:
        count: Number of nodes to create (default: 1)

    Returns:
        Dictionary with count of nodes created

    Raises:
        HTTPException: If count is invalid (<= 0)
    """
    if count <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Count must be greater than 0",
        )

    try:
        if not client.is_connected():
            client.connect()

        # Create nodes with a simple label and incrementing id property
        for i in range(count):
            query = f"CREATE (n:Node {{id: {i}}})"
            client.execute_cypher(query)

        return {"count": count}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create nodes: {e}",
        ) from e


@app.get("/nodes")
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


@app.delete("/nodes")
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
