"""Main FastAPI application entry point."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from util import dev_routes

import health_routes
from graph.presentation import routes as graph_routes
from iam.presentation import router as iam_router
from management.presentation import router as management_router
from infrastructure.database.dependencies import (
    close_database_engines,
    init_database_engines,
)
from infrastructure.dependencies import get_age_connection_pool
from infrastructure.logging import configure_logging
from infrastructure.settings import (
    CORSSettings,
    get_cors_settings,
    get_database_settings,
    get_iam_settings,
    get_oidc_settings,
    get_outbox_worker_settings,
    get_spicedb_settings,
)
from infrastructure.version import __version__
from graph.infrastructure.tenant_graph_handler import (
    AGEGraphProvisioner,
    TenantAGEGraphHandler,
)
from iam.infrastructure.outbox import IAMEventTranslator
from management.infrastructure.outbox import ManagementEventTranslator
from infrastructure.outbox.composite import CompositeEventHandler
from infrastructure.outbox.spicedb_handler import SpiceDBEventHandler
from infrastructure.outbox.event_sources.postgres_notify import (
    PostgresNotifyEventSource,
)
from infrastructure.outbox.worker import OutboxWorker
from shared_kernel.authorization.spicedb.client import SpiceDBClient
from shared_kernel.outbox.observability import (
    DefaultEventSourceProbe,
    DefaultOutboxWorkerProbe,
)
from query.presentation.mcp import mcp_http_app_inner, query_mcp_app

# Default work directory for JobPackage ZIP archives
_JOB_PACKAGE_WORK_DIR = Path("/tmp/kartograph/job_packages")  # noqa: S108

# Scheduler polling interval (seconds)
_SCHEDULER_POLL_INTERVAL_SECONDS = 60


# ---------------------------------------------------------------------------
# Session-aware outbox handler wrappers
#
# These wrappers create a fresh database session per event call, ensuring
# proper transaction isolation for handlers that need database access.
# The bounded-context handlers are imported lazily to avoid circular imports
# and to respect DDD layer boundaries in the module-level namespace.
# ---------------------------------------------------------------------------


class _SessionedSyncLifecycleHandler:
    """Session-aware wrapper for SyncLifecycleHandler.

    Creates a fresh SQLAlchemy session for each event, allowing the
    SyncLifecycleHandler to manage its own transaction lifecycle.
    Registered for all 7 sync lifecycle events.
    """

    _SUPPORTED: frozenset[str] = frozenset(
        {
            "SyncStarted",
            "JobPackageProduced",
            "IngestionFailed",
            "MutationLogProduced",
            "ExtractionFailed",
            "MutationsApplied",
            "MutationApplicationFailed",
        }
    )

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    def supported_event_types(self) -> frozenset[str]:
        return self._SUPPORTED

    async def handle(self, event_type: str, payload: dict[str, Any]) -> None:
        from infrastructure.outbox.repository import OutboxRepository
        from management.infrastructure.repositories.data_source_repository import (
            DataSourceRepository,
        )
        from management.infrastructure.repositories.data_source_sync_run_repository import (
            DataSourceSyncRunRepository,
        )
        from management.infrastructure.sync_lifecycle_handler import (
            SyncLifecycleHandler,
        )

        async with self._session_factory() as session:
            outbox = OutboxRepository(session=session)
            ds_repo = DataSourceRepository(session=session, outbox=outbox)
            sync_run_repo = DataSourceSyncRunRepository(session=session)
            lifecycle_handler = SyncLifecycleHandler(
                session=session,
                sync_run_repository=sync_run_repo,
                data_source_repository=ds_repo,
            )
            await lifecycle_handler.handle(event_type, payload)
            # SyncLifecycleHandler manages its own transactions internally;
            # commit is a no-op if all inner begin() blocks already committed.
            await session.commit()


class _SessionedIngestionEventHandler:
    """Session-aware wrapper for IngestionEventHandler.

    Creates a fresh session per event. The IngestionEventHandler writes
    JobPackageProduced/IngestionFailed to the outbox; the session commit
    here persists those outbox entries atomically.
    """

    _SUPPORTED: frozenset[str] = frozenset({"SyncStarted"})

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    def supported_event_types(self) -> frozenset[str]:
        return self._SUPPORTED

    async def handle(self, event_type: str, payload: dict[str, Any]) -> None:
        from infrastructure.outbox.repository import OutboxRepository
        from ingestion.application.services.ingestion_service import IngestionService
        from ingestion.infrastructure.event_handler import IngestionEventHandler

        async with self._session_factory() as session:
            outbox = OutboxRepository(session=session)
            # Adapter registry is empty; unknown adapter type will raise ValueError,
            # causing IngestionFailed to be emitted by the handler.
            # Real adapters are registered here as the platform evolves.
            ingestion_service = IngestionService(
                adapter_registry={},
                work_dir=_JOB_PACKAGE_WORK_DIR,
            )
            ingestion_handler = IngestionEventHandler(
                ingestion_service=ingestion_service,
                outbox=outbox,
            )
            await ingestion_handler.handle(event_type, payload)
            await session.commit()


class _StubExtractionService:
    """Stub extraction service that raises NotImplementedError.

    Placeholder until the Claude Agent SDK extraction pipeline is implemented.
    Any JobPackageProduced event will result in ExtractionFailed being emitted.
    """

    async def run(
        self,
        sync_run_id: str,
        data_source_id: str,
        knowledge_graph_id: str,
        job_package_id: str,
    ) -> str:
        raise NotImplementedError(
            "AI extraction pipeline is not yet implemented. "
            "Register a real IExtractionService implementation to enable extraction."
        )


class _SessionedExtractionEventHandler:
    """Session-aware wrapper for ExtractionEventHandler.

    Signals the Extraction context to process a JobPackage. Currently
    uses a stub service that emits ExtractionFailed until the Claude
    Agent SDK pipeline is implemented.
    """

    _SUPPORTED: frozenset[str] = frozenset({"JobPackageProduced"})

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory
        self._extraction_service = _StubExtractionService()

    def supported_event_types(self) -> frozenset[str]:
        return self._SUPPORTED

    async def handle(self, event_type: str, payload: dict[str, Any]) -> None:
        from infrastructure.outbox.repository import OutboxRepository
        from extraction.infrastructure.event_handler import ExtractionEventHandler

        async with self._session_factory() as session:
            outbox = OutboxRepository(session=session)
            extraction_handler = ExtractionEventHandler(
                extraction_service=self._extraction_service,
                outbox=outbox,
            )
            await extraction_handler.handle(event_type, payload)
            await session.commit()


class _StubMutationLogApplier:
    """Stub mutation log applier that raises NotImplementedError.

    Placeholder until the AGE-backed mutation application pipeline is
    wired into the outbox handler. Any MutationLogProduced event will
    result in MutationApplicationFailed being emitted.
    """

    async def apply_mutation_log(self, mutation_log_id: str) -> bool:
        raise NotImplementedError(
            "Graph mutation application via outbox is not yet fully implemented. "
            "Register a real IMutationLogApplier to enable graph writes from the outbox."
        )


class _SessionedGraphMutationEventHandler:
    """Session-aware wrapper for GraphMutationEventHandler.

    Applies MutationLogs to the Apache AGE graph database. Currently uses
    a stub applier that emits MutationApplicationFailed until the full
    graph write pipeline is wired to the outbox.
    """

    _SUPPORTED: frozenset[str] = frozenset({"MutationLogProduced"})

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory
        self._mutation_log_applier = _StubMutationLogApplier()

    def supported_event_types(self) -> frozenset[str]:
        return self._SUPPORTED

    async def handle(self, event_type: str, payload: dict[str, Any]) -> None:
        from infrastructure.outbox.repository import OutboxRepository
        from graph.infrastructure.event_handler import GraphMutationEventHandler

        async with self._session_factory() as session:
            outbox = OutboxRepository(session=session)
            graph_handler = GraphMutationEventHandler(
                mutation_log_applier=self._mutation_log_applier,
                outbox=outbox,
            )
            await graph_handler.handle(event_type, payload)
            await session.commit()


async def _run_scheduler_loop(session_factory: Any, poll_interval: int) -> None:
    """Background asyncio task that periodically triggers scheduled syncs.

    Polls data sources with INTERVAL or CRON schedules and initiates syncs
    that are due. Runs until the event loop is stopped (app shutdown).

    Args:
        session_factory: SQLAlchemy async sessionmaker for database access
        poll_interval: Seconds between scheduler runs
    """
    from infrastructure.outbox.repository import OutboxRepository
    from management.application.services.sync_scheduler import SyncSchedulerService
    from management.infrastructure.repositories.data_source_repository import (
        DataSourceRepository,
    )
    from management.infrastructure.repositories.data_source_sync_run_repository import (
        DataSourceSyncRunRepository,
    )

    while True:
        try:
            async with session_factory() as session:
                outbox = OutboxRepository(session=session)
                ds_repo = DataSourceRepository(session=session, outbox=outbox)
                sync_run_repo = DataSourceSyncRunRepository(session=session)
                scheduler = SyncSchedulerService(
                    data_source_repository=ds_repo,
                    sync_run_repository=sync_run_repo,
                )
                await scheduler.check_and_trigger_due_syncs()
                await session.commit()
        except asyncio.CancelledError:
            break
        except Exception:
            # Log but don't crash — scheduler must remain resilient
            pass

        try:
            await asyncio.sleep(poll_interval)
        except asyncio.CancelledError:
            break


# Configure structlog before any loggers are created
configure_logging()


def configure_cors(app: FastAPI, cors_settings: CORSSettings) -> None:
    """Install CORSMiddleware when allowed origins are configured.

    CORS is enabled only when at least one origin is explicitly listed.
    Using a wildcard origin ('*') with credentials is rejected at settings
    validation time (see CORSSettings.validate_no_wildcard_origin_with_credentials).
    """
    if cors_settings.is_enabled:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_settings.origins,
            allow_credentials=cors_settings.allow_credentials,
            allow_methods=cors_settings.allow_methods,
            allow_headers=cors_settings.allow_headers,
            expose_headers=cors_settings.expose_headers,
            max_age=cors_settings.max_age,
        )


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

    # Startup: create shared SpiceDB client for bootstrap and outbox worker
    spicedb_settings = get_spicedb_settings()
    authz = SpiceDBClient(
        endpoint=spicedb_settings.endpoint,
        preshared_key=spicedb_settings.preshared_key.get_secret_value(),
        use_tls=spicedb_settings.use_tls,
        cert_path=spicedb_settings.cert_path,
    )

    # Startup: ensure default tenant and root workspace exist (single-tenant mode)
    iam_settings = get_iam_settings()
    if hasattr(app.state, "write_sessionmaker") and iam_settings.single_tenant_mode:
        from iam.application.services import TenantBootstrapService
        from iam.infrastructure.tenant_repository import TenantRepository
        from iam.infrastructure.workspace_repository import WorkspaceRepository
        from infrastructure.observability.startup_probe import DefaultStartupProbe
        from infrastructure.outbox.repository import OutboxRepository

        startup_probe = DefaultStartupProbe()

        async with app.state.write_sessionmaker() as session:
            outbox = OutboxRepository(session=session)
            tenant_repo = TenantRepository(session=session, outbox=outbox)
            workspace_repo = WorkspaceRepository(
                session=session, authz=authz, outbox=outbox
            )

            bootstrap_service = TenantBootstrapService(
                tenant_repository=tenant_repo,
                workspace_repository=workspace_repo,
                session=session,
                probe=startup_probe,
            )

            # Resolve workspace name (use setting or fall back to tenant name)
            workspace_name = (
                iam_settings.default_workspace_name or iam_settings.default_tenant_name
            )

            await bootstrap_service.ensure_default_tenant_with_workspace(
                tenant_name=iam_settings.default_tenant_name,
                workspace_name=workspace_name,
            )

    # Startup: start outbox worker if enabled
    outbox_settings = get_outbox_worker_settings()
    if outbox_settings.enabled and hasattr(app.state, "write_sessionmaker"):
        db_settings = get_database_settings()

        # Build database URL for LISTEN
        db_url = (
            f"postgresql://{db_settings.username}:"
            f"{db_settings.password.get_secret_value()}@"
            f"{db_settings.host}:{db_settings.port}/{db_settings.database}"
        )

        # Create observability probe
        probe = DefaultOutboxWorkerProbe()

        # Build composite handler with registered bounded context handlers
        handler = CompositeEventHandler(probe=probe)
        # Register SpiceDB handler wrapping the IAM translator
        spicedb_handler = SpiceDBEventHandler(
            translator=IAMEventTranslator(),
            authz=authz,
        )
        handler.register(spicedb_handler, handler_name="iam")
        # Register SpiceDB handler wrapping the Management translator
        management_spicedb_handler = SpiceDBEventHandler(
            translator=ManagementEventTranslator(),
            authz=authz,
        )
        handler.register(management_spicedb_handler, handler_name="management")
        # Register AGE graph provisioning handler for tenant lifecycle events
        age_pool = get_age_connection_pool()
        from infrastructure.database.connection import ConnectionFactory

        age_connection_factory = ConnectionFactory(
            settings=get_database_settings(),
            pool=age_pool,
        )
        tenant_graph_handler = TenantAGEGraphHandler(
            graph_provisioner=AGEGraphProvisioner(age_connection_factory)
        )
        handler.register(tenant_graph_handler, handler_name="tenant_graph")

        # Register sync lifecycle handler: updates DataSourceSyncRun status
        # as events flow through the pipeline (pending → ingesting → ai_extracting
        # → applying → completed / failed).
        sync_lifecycle_handler = _SessionedSyncLifecycleHandler(
            session_factory=app.state.write_sessionmaker
        )
        handler.register(sync_lifecycle_handler, handler_name="sync_lifecycle")

        # Register ingestion handler: processes SyncStarted events by running
        # the adapter extract → package pipeline.
        ingestion_handler = _SessionedIngestionEventHandler(
            session_factory=app.state.write_sessionmaker
        )
        handler.register(ingestion_handler, handler_name="ingestion")

        # Register extraction handler: processes JobPackageProduced events by
        # signaling the Extraction context to run AI entity extraction.
        extraction_handler = _SessionedExtractionEventHandler(
            session_factory=app.state.write_sessionmaker
        )
        handler.register(extraction_handler, handler_name="extraction")

        # Register graph mutation handler: processes MutationLogProduced events
        # by applying the mutation log to the Apache AGE graph database.
        graph_mutation_handler = _SessionedGraphMutationEventHandler(
            session_factory=app.state.write_sessionmaker
        )
        handler.register(graph_mutation_handler, handler_name="graph_mutation")

        # Create event source for real-time NOTIFY processing
        event_source = PostgresNotifyEventSource(
            db_url=db_url,
            channel="outbox_events",
            probe=DefaultEventSourceProbe(),
        )

        worker = OutboxWorker(
            session_factory=app.state.write_sessionmaker,
            handler=handler,
            probe=probe,
            event_source=event_source,
            poll_interval_seconds=outbox_settings.poll_interval_seconds,
            batch_size=outbox_settings.batch_size,
            max_retries=outbox_settings.max_retries,
        )
        await worker.start()
        app.state.outbox_worker = worker

        # Start the sync scheduler background task.
        # Periodically checks data sources with INTERVAL/CRON schedules and
        # triggers syncs that are due (as if manually triggered).
        scheduler_task = asyncio.create_task(
            _run_scheduler_loop(
                session_factory=app.state.write_sessionmaker,
                poll_interval=_SCHEDULER_POLL_INTERVAL_SECONDS,
            )
        )
        app.state.scheduler_task = scheduler_task

    # MCP lifespan - skip if already initialized (e.g., in tests with multiple lifespans)
    if not app.state._mcp_initialized:
        async with mcp_http_app_inner.lifespan(app):
            app.state._mcp_initialized = True
            yield
    else:
        # MCP already initialized in previous lifespan cycle
        yield

    # Shutdown: stop scheduler background task
    if hasattr(app.state, "scheduler_task"):
        app.state.scheduler_task.cancel()
        try:
            await app.state.scheduler_task
        except asyncio.CancelledError:
            pass

    # Shutdown: stop outbox worker
    if hasattr(app.state, "outbox_worker"):
        await app.state.outbox_worker.stop()

    # Shutdown: close database engines
    await close_database_engines(app)

    # Shutdown: close AGE connection pool and clear cache for next startup
    try:
        pool = get_age_connection_pool()
        pool.close_all()
        # Clear lru_cache so next startup creates a fresh pool
        get_age_connection_pool.cache_clear()
    except Exception:
        # Pool may not be initialized, ignore
        pass


app = FastAPI(
    title="Kartograph API",
    description="Enterprise-Ready Bi-Temporal Knowledge Graphs as a Service",
    version=__version__,
    lifespan=kartograph_lifespan,
)
# Configure CORS middleware based on current settings
configure_cors(app, get_cors_settings())

app.mount(path="/query", app=query_mcp_app)

# Include health check routes (liveness and readiness probes)
app.include_router(health_routes.router)

# Include Graph bounded context routes
app.include_router(graph_routes.router)

# Include IAM bounded context routes
app.include_router(iam_router)

# Include Management bounded context routes
app.include_router(management_router)

# Include dev utility routes (easy to remove for production)
app.include_router(dev_routes.router)


# Log OIDC configuration at startup
def _log_oidc_config() -> None:
    """Log OIDC configuration if available."""
    from iam.application.observability import DefaultOIDCConfigProbe

    try:
        oidc_settings = get_oidc_settings()
        DefaultOIDCConfigProbe.log_settings(oidc_settings)
    except Exception:
        # OIDC settings may fail if client_secret is not configured
        pass


_log_oidc_config()


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
