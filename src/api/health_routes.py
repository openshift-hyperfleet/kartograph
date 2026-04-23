"""Health check routes for liveness and readiness probing.

Exposes:
  GET /health     — basic liveness probe (no dependencies)
  GET /health/db  — database readiness probe (checks AGE/PostgreSQL connectivity)

These endpoints are consumed by Kubernetes liveness and readiness probes.
Startup ordering (waiting for migrations and SpiceDB schema) is enforced by
Kubernetes init containers declared in the API Deployment manifest; the
application itself does not need to poll for those conditions.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from graph.infrastructure.age_client import AgeGraphClient
from infrastructure.database.connection import ConnectionFactory
from infrastructure.dependencies import get_age_connection_pool
from infrastructure.settings import get_database_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """Basic health check — confirms the application process is alive."""
    return {"status": "ok"}


@router.get("/health/db")
def health_db() -> dict:
    """Database connectivity check — confirms the graph database is reachable.

    Returns:
        200 {"status": "ok", "connected": True, "graph_name": ...}
            when the database is reachable.
        503 {"detail": "<error message>"}
            when the database is unreachable or the connection is unhealthy.

    The endpoint deliberately avoids FastAPI dependency injection so that
    every part of the connection attempt (including pool acquisition) is
    wrapped in the same try/except, guaranteeing a 503 on any failure rather
    than the default 500 that FastAPI would return for unhandled dependency
    exceptions.
    """
    try:
        pool = get_age_connection_pool()
        settings = get_database_settings()
        factory = ConnectionFactory(settings, pool=pool)
        client = AgeGraphClient(settings, connection_factory=factory)
        client.connect()
        try:
            is_healthy = client.verify_connection()
        finally:
            client.disconnect()

        if not is_healthy:
            raise HTTPException(
                status_code=503,
                detail="Database connection is not healthy",
            )

        return {
            "status": "ok",
            "connected": True,
            "graph_name": client.graph_name,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Database connectivity failure: {exc}",
        ) from exc
