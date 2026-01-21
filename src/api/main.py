"""Main FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from util import dev_routes

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
from infrastructure.settings import (
    get_cors_settings,
    get_database_settings,
    get_oidc_settings,
    get_outbox_worker_settings,
    get_spicedb_settings,
)
from infrastructure.version import __version__
from iam.infrastructure.outbox import IAMEventTranslator
from infrastructure.outbox.composite import CompositeTranslator
from infrastructure.outbox.event_sources.postgres_notify import (
    PostgresNotifyEventSource,
)
from infrastructure.outbox.worker import OutboxWorker
from shared_kernel.authorization.spicedb.client import SpiceDBClient
from shared_kernel.outbox.observability import (
    DefaultEventSourceProbe,
    DefaultOutboxWorkerProbe,
)
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
    - Outbox worker lifecycle

    Engines are created here (within the running event loop) to ensure
    proper async context for database connections.

    State is tracked per-app instance (app.state._mcp_initialized) to maintain
    test isolation when multiple app instances are created.
    """
    # Initialize MCP state tracking on this app instance
    if not hasattr(app.state, "_mcp_initialized"):
        app.state._mcp_initialized = False

    # Startup: initialize database engines
    init_database_engines(app)

    # Startup: ensure default tenant exists (single-tenant mode)
    if hasattr(app.state, "write_sessionmaker"):
        from iam.dependencies import set_default_tenant_id
        from iam.domain.aggregates import Tenant
        from iam.infrastructure.tenant_repository import TenantRepository
        from infrastructure.observability.startup_probe import DefaultStartupProbe
        from infrastructure.outbox.repository import OutboxRepository
        from infrastructure.settings import get_iam_settings

        iam_settings = get_iam_settings()
        startup_probe = DefaultStartupProbe()

        async with app.state.write_sessionmaker() as session:
            async with session.begin():
                from iam.ports.exceptions import DuplicateTenantNameError

                outbox = OutboxRepository(session=session)
                tenant_repo = TenantRepository(session=session, outbox=outbox)

                # Check if default tenant exists
                tenant = await tenant_repo.get_by_name(iam_settings.default_tenant_name)
                if not tenant:
                    # Handle race condition during concurrent startups
                    try:
                        tenant = Tenant.create(name=iam_settings.default_tenant_name)
                        await tenant_repo.save(tenant)
                        startup_probe.default_tenant_bootstrapped(
                            tenant_id=tenant.id.value,
                            name=tenant.name,
                        )
                    except DuplicateTenantNameError:
                        # Another instance created it concurrently, re-query
                        tenant = await tenant_repo.get_by_name(
                            iam_settings.default_tenant_name
                        )
                        if tenant:
                            startup_probe.default_tenant_already_exists(
                                tenant_id=tenant.id.value,
                                name=tenant.name,
                            )
                        else:
                            # Should never happen, but handle gracefully
                            raise RuntimeError(
                                "Failed to create or retrieve default tenant"
                            )
                else:
                    startup_probe.default_tenant_already_exists(
                        tenant_id=tenant.id.value,
                        name=tenant.name,
                    )

                # Cache default tenant ID for single-tenant mode
                set_default_tenant_id(tenant.id)

    # Startup: start outbox worker if enabled
    outbox_settings = get_outbox_worker_settings()
    if outbox_settings.enabled and hasattr(app.state, "write_sessionmaker"):
        db_settings = get_database_settings()
        spicedb_settings = get_spicedb_settings()

        # Build database URL for LISTEN
        db_url = (
            f"postgresql://{db_settings.username}:"
            f"{db_settings.password.get_secret_value()}@"
            f"{db_settings.host}:{db_settings.port}/{db_settings.database}"
        )

        # Create SpiceDB client
        authz = SpiceDBClient(
            endpoint=spicedb_settings.endpoint,
            preshared_key=spicedb_settings.preshared_key.get_secret_value(),
            use_tls=spicedb_settings.use_tls,
            cert_path=spicedb_settings.cert_path,
        )

        # Create observability probe
        probe = DefaultOutboxWorkerProbe()

        # Build composite translator with registered bounded context translators
        translator = CompositeTranslator(probe=probe)
        translator.register(IAMEventTranslator(), context_name="iam")
        # Future: translator.register(ManagementEventTranslator(), context_name="management")

        # Create event source for real-time NOTIFY processing
        event_source = PostgresNotifyEventSource(
            db_url=db_url,
            channel="outbox_events",
            probe=DefaultEventSourceProbe(),
        )

        worker = OutboxWorker(
            session_factory=app.state.write_sessionmaker,
            authz=authz,
            translator=translator,
            probe=probe,
            event_source=event_source,
            poll_interval_seconds=outbox_settings.poll_interval_seconds,
            batch_size=outbox_settings.batch_size,
            max_retries=outbox_settings.max_retries,
        )
        await worker.start()
        app.state.outbox_worker = worker

    # MCP lifespan - skip if already initialized (e.g., in tests with multiple lifespans)
    if not app.state._mcp_initialized:
        async with query_mcp_app.lifespan(app):
            app.state._mcp_initialized = True
            yield
    else:
        # MCP already initialized in previous lifespan cycle
        yield

    # Shutdown: stop outbox worker
    if hasattr(app.state, "outbox_worker"):
        await app.state.outbox_worker.stop()

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
# Configure CORS if origins are specified
cors_settings = get_cors_settings()

if cors_settings.is_enabled:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_settings.origins,
        allow_credentials=cors_settings.allow_credentials,
        allow_methods=cors_settings.allow_methods,
        allow_headers=cors_settings.allow_headers,
    )

app.mount(path="/query", app=query_mcp_app)

# Include Graph bounded context routes
app.include_router(graph_routes.router)

# Include IAM bounded context routes
app.include_router(iam_routes.router)

# Include dev utility routes (easy to remove for production)
app.include_router(dev_routes.router)


# Conditionally include auth routes when OIDC is enabled
def _register_auth_routes() -> None:
    """Register auth routes if OIDC is configured and enabled."""
    from infrastructure.observability.startup_probe import DefaultStartupProbe

    startup_probe = DefaultStartupProbe()

    try:
        oidc_settings = get_oidc_settings()
        if oidc_settings.auth_routes_enabled:
            from auth.presentation import routes as auth_routes

            app.include_router(auth_routes.router)
            startup_probe.oidc_routes_registered()
        else:
            startup_probe.oidc_routes_disabled()
    except Exception as e:
        # OIDC settings may fail if client_secret is not configured
        startup_probe.oidc_configuration_failed(error=str(e))


_register_auth_routes()


def configure_swagger_oauth2(app: FastAPI) -> None:
    """Configure Swagger UI OAuth2 with PKCE.

    Sets up the Swagger UI to authenticate via OAuth2/OIDC using the
    Authorization Code flow with PKCE. This uses the public swagger client,
    not the confidential API client.

    The security scheme itself is registered automatically by
    OAuth2AuthorizationCodeBearer in iam/dependencies.py. This function
    only configures the Swagger UI initialization parameters.

    If OIDC settings are not configured (e.g., missing client_secret),
    this function silently returns without configuring Swagger OAuth2.
    """
    try:
        oidc_settings = get_oidc_settings()
    except Exception:
        # OIDC not configured, skip Swagger OAuth2
        return

    # Configure Swagger UI init parameters for PKCE flow
    app.swagger_ui_init_oauth = {
        "clientId": oidc_settings.swagger_client_id,
        "usePkceWithAuthorizationCodeGrant": True,
        "scopes": "openid profile email",
    }


# Configure Swagger OAuth2 if OIDC is available
configure_swagger_oauth2(app)


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
