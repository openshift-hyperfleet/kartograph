"""Main FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status

from graph.dependencies import get_age_graph_client
from graph.infrastructure.age_client import AgeGraphClient
from graph.presentation import routes as graph_routes
from iam.presentation import routes as iam_routes
from infrastructure.database.dependencies import (
    close_database_engines,
    init_database_engines,
)
from infrastructure.dependencies import get_age_connection_pool
from infrastructure.logging import configure_logging
from infrastructure.version import __version__
from query.presentation.mcp import query_mcp_app

# Configure structlog before any loggers are created
configure_logging()


@asynccontextmanager
async def kartograph_lifespan(app: FastAPI):
    """Application lifespan context.

    Manages:
    - Database engine lifecycle (created on startup, disposed on shutdown)
    - MCP server lifespan
    - AGE connection pool lifecycle

    Engines are created here (within the running event loop) to ensure
    proper async context for database connections.
    """
    # Startup: initialize database engines
    init_database_engines(app)

    # MCP lifespan - may fail if already run (e.g., in tests with multiple lifespans)
    try:
        async with query_mcp_app.lifespan(app):
            yield
    except RuntimeError as e:
        if "can only be called once" in str(e):
            # MCP already initialized, just yield for database operations
            yield
        else:
            raise

    # Shutdown: close database engines
    await close_database_engines(app)

    # Shutdown: close AGE connection pool
    try:
        pool = get_age_connection_pool()
        pool.close_all()
    except Exception:
        # Pool may not be initialized, ignore
        pass


app = FastAPI(
    title="Kartograph API",
    description="Enterprise-Ready Bi-Temporal Knowledge Graphs as a Service",
    version=__version__,
    lifespan=kartograph_lifespan,
)

app.mount(path="/query", app=query_mcp_app)

# Include Graph bounded context routes
app.include_router(graph_routes.router)

# Include IAM bounded context routes
app.include_router(iam_routes.router)


@app.get("/health")
def health():
    """Basic health check endpoint."""
    return {"status": "ok"}


@app.get("/health/db")
def health_db(
    client: Annotated[AgeGraphClient, Depends(get_age_graph_client)],
) -> dict:
    """Check database connection health.

    Returns the connection status and graph name.
    """
    try:
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
    client: Annotated[AgeGraphClient, Depends(get_age_graph_client)],
) -> dict:
    """Query all nodes in the graph.

    Utility endpoint for development and testing.
    """
    try:
        from age.models import Vertex as AgeVertex

        # Execute simple query
        result = client.execute_cypher("MATCH (n) RETURN n")

        # Convert Vertex objects to serializable dicts
        nodes = []
        for row in result.rows:
            if len(row) > 0 and isinstance(row[0], AgeVertex):
                vertex = row[0]
                nodes.append(
                    {
                        "id": str(vertex.id),
                        "label": vertex.label,
                        "properties": dict(vertex.properties)
                        if vertex.properties
                        else {},
                    }
                )

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
    client: Annotated[AgeGraphClient, Depends(get_age_graph_client)],
) -> dict:
    """Delete all nodes in the graph.

    Returns:
        Dictionary with count of deleted nodes
    """
    try:
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
    client: Annotated[AgeGraphClient, Depends(get_age_graph_client)],
) -> dict:
    """Delete all edges in the graph.

    Returns:
        Dictionary with count of deleted edges
    """
    try:
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
