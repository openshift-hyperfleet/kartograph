from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI

from graph.infrastructure.age_client import AgeGraphClient
from infrastructure.settings import get_database_settings

app = FastAPI()


@lru_cache
def get_graph_client() -> AgeGraphClient:
    """Get a cached AgeGraphClient instance."""
    settings = get_database_settings()
    client = AgeGraphClient(settings)
    return client


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
