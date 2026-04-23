"""Unit tests for application lifecycle behavior.

Tests verifying the startup and shutdown sequence, including:
- Single-tenant mode bootstrap (tenant + workspace provisioning)
- Outbox worker lifecycle (start on startup, stop on shutdown)
- Database connection lifecycle (init on startup, dispose on shutdown)

Spec: specs/nfr/application-lifecycle.spec.md
"""

from __future__ import annotations

from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_async_ctx_manager(return_value=None):
    """Return an async context manager mock that yields *return_value*."""
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=return_value)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


def _make_session_factory(session):
    """Return an async session factory mock."""
    factory = MagicMock()
    factory.return_value = _make_async_ctx_manager(session)
    return factory


def _patched_init_engines(session_factory):
    """Return an init_database_engines side_effect that populates app.state."""

    def _init(app: FastAPI) -> None:
        app.state.write_sessionmaker = session_factory

    return _init


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session():
    """Async SQLAlchemy session mock."""
    session = AsyncMock()
    session.begin.return_value = _make_async_ctx_manager()
    session.begin_nested.return_value = _make_async_ctx_manager()
    return session


@pytest.fixture
def mock_session_factory(mock_session):
    """Async session factory mock that injects mock_session."""
    return _make_session_factory(mock_session)


@pytest.fixture
def mock_iam_settings_single_tenant():
    """IAMSettings mock with single_tenant_mode=True."""
    settings = MagicMock()
    settings.single_tenant_mode = True
    settings.default_tenant_name = "default"
    settings.default_workspace_name = None
    return settings


@pytest.fixture
def mock_iam_settings_multi_tenant():
    """IAMSettings mock with single_tenant_mode=False."""
    settings = MagicMock()
    settings.single_tenant_mode = False
    settings.default_tenant_name = "default"
    settings.default_workspace_name = None
    return settings


@pytest.fixture
def mock_spicedb_settings():
    """SpiceDB settings mock."""
    settings = MagicMock()
    settings.endpoint = "localhost:50051"
    settings.preshared_key.get_secret_value.return_value = "test-key"
    settings.use_tls = False
    settings.cert_path = None
    return settings


@pytest.fixture
def mock_outbox_settings_enabled():
    """Outbox worker settings mock with enabled=True."""
    settings = MagicMock()
    settings.enabled = True
    settings.poll_interval_seconds = 30
    settings.batch_size = 100
    settings.max_retries = 5
    return settings


@pytest.fixture
def mock_outbox_settings_disabled():
    """Outbox worker settings mock with enabled=False."""
    settings = MagicMock()
    settings.enabled = False
    return settings


@pytest.fixture
def mock_db_settings():
    """Database settings mock."""
    settings = MagicMock()
    settings.username = "kartograph"
    settings.password.get_secret_value.return_value = "password"
    settings.host = "localhost"
    settings.port = 5432
    settings.database = "kartograph"
    return settings


@pytest.fixture
def mock_age_pool():
    """AGE connection pool mock."""
    pool = MagicMock()
    pool.close_all = MagicMock()
    return pool


@pytest.fixture
def mock_mcp_inner():
    """Mock for mcp_http_app_inner that provides an async lifespan."""
    app_inner = MagicMock()
    app_inner.lifespan.return_value = _make_async_ctx_manager()
    return app_inner


def _base_patches(
    session_factory,
    iam_settings,
    outbox_settings,
    spicedb_settings,
    age_pool,
    mcp_inner,
    init_engines_side_effect=None,
    close_engines_mock=None,
):
    """Build a dict of base patches needed by all lifecycle tests.

    Returns a dict of {target: mock_or_kwargs} ready to pass to ExitStack.
    Callers may add additional patches before entering the stack.
    """
    mock_age_pool_fn = MagicMock(return_value=age_pool)
    mock_age_pool_fn.cache_clear = MagicMock()

    init_side_effect = init_engines_side_effect or _patched_init_engines(
        session_factory
    )
    close_mock = close_engines_mock if close_engines_mock is not None else AsyncMock()

    return [
        ("main.init_database_engines", dict(side_effect=init_side_effect)),
        ("main.close_database_engines", dict(new=close_mock)),
        ("main.get_spicedb_settings", dict(return_value=spicedb_settings)),
        ("main.SpiceDBClient", dict()),
        ("main.get_iam_settings", dict(return_value=iam_settings)),
        ("main.get_outbox_worker_settings", dict(return_value=outbox_settings)),
        ("main.mcp_http_app_inner", dict(new=mcp_inner)),
        ("main.get_age_connection_pool", dict(new=mock_age_pool_fn)),
    ]


def apply_patches(stack: ExitStack, patch_list: list) -> dict:
    """Apply a list of (target, kwargs) patches via ExitStack, return mocks."""
    mocks = {}
    for target, kwargs in patch_list:
        mocks[target] = stack.enter_context(patch(target, **kwargs))
    return mocks


# ---------------------------------------------------------------------------
# Tests: Single-Tenant Mode Bootstrap
# ---------------------------------------------------------------------------


class TestSingleTenantBootstrap:
    """Tests for single-tenant mode bootstrap during application startup.

    Requirement: Single-Tenant Mode Bootstrap
    Scenario: Default tenant and workspace
    Scenario: Multi-tenant mode
    """

    @pytest.mark.asyncio
    async def test_bootstrap_runs_in_single_tenant_mode(
        self,
        mock_session_factory,
        mock_iam_settings_single_tenant,
        mock_spicedb_settings,
        mock_outbox_settings_disabled,
        mock_age_pool,
        mock_mcp_inner,
    ):
        """GIVEN single-tenant mode is enabled
        WHEN the application starts
        THEN ensure_default_tenant_with_workspace is called with the configured names.
        """
        from main import kartograph_lifespan

        app = FastAPI(lifespan=kartograph_lifespan)

        mock_bootstrap_instance = AsyncMock()
        mock_bootstrap_cls = MagicMock(return_value=mock_bootstrap_instance)

        patches = _base_patches(
            mock_session_factory,
            mock_iam_settings_single_tenant,
            mock_outbox_settings_disabled,
            mock_spicedb_settings,
            mock_age_pool,
            mock_mcp_inner,
        ) + [
            (
                "iam.application.services.TenantBootstrapService",
                dict(new=mock_bootstrap_cls),
            ),
            ("iam.infrastructure.tenant_repository.TenantRepository", dict()),
            ("iam.infrastructure.workspace_repository.WorkspaceRepository", dict()),
            ("infrastructure.outbox.repository.OutboxRepository", dict()),
            ("infrastructure.observability.startup_probe.DefaultStartupProbe", dict()),
        ]

        with ExitStack() as stack:
            apply_patches(stack, patches)
            async with kartograph_lifespan(app):
                pass

        mock_bootstrap_instance.ensure_default_tenant_with_workspace.assert_called_once()

    @pytest.mark.asyncio
    async def test_bootstrap_skipped_in_multi_tenant_mode(
        self,
        mock_session_factory,
        mock_iam_settings_multi_tenant,
        mock_spicedb_settings,
        mock_outbox_settings_disabled,
        mock_age_pool,
        mock_mcp_inner,
    ):
        """GIVEN single-tenant mode is disabled
        WHEN the application starts
        THEN no default tenant or workspace is created.
        """
        from main import kartograph_lifespan

        app = FastAPI(lifespan=kartograph_lifespan)

        mock_bootstrap_instance = AsyncMock()
        mock_bootstrap_cls = MagicMock(return_value=mock_bootstrap_instance)

        patches = _base_patches(
            mock_session_factory,
            mock_iam_settings_multi_tenant,
            mock_outbox_settings_disabled,
            mock_spicedb_settings,
            mock_age_pool,
            mock_mcp_inner,
        ) + [
            (
                "iam.application.services.TenantBootstrapService",
                dict(new=mock_bootstrap_cls),
            ),
        ]

        with ExitStack() as stack:
            apply_patches(stack, patches)
            async with kartograph_lifespan(app):
                pass

        # Bootstrap service should NOT be instantiated in multi-tenant mode
        mock_bootstrap_cls.assert_not_called()
        mock_bootstrap_instance.ensure_default_tenant_with_workspace.assert_not_called()

    @pytest.mark.asyncio
    async def test_workspace_name_defaults_to_tenant_name(
        self,
        mock_session_factory,
        mock_spicedb_settings,
        mock_outbox_settings_disabled,
        mock_age_pool,
        mock_mcp_inner,
    ):
        """GIVEN single-tenant mode is enabled AND workspace name is not configured
        WHEN the application starts
        THEN the workspace name defaults to the tenant name.
        """
        from main import kartograph_lifespan

        app = FastAPI(lifespan=kartograph_lifespan)

        mock_iam_settings = MagicMock()
        mock_iam_settings.single_tenant_mode = True
        mock_iam_settings.default_tenant_name = "acme-corp"
        mock_iam_settings.default_workspace_name = None  # triggers fallback

        mock_bootstrap_instance = AsyncMock()
        mock_bootstrap_cls = MagicMock(return_value=mock_bootstrap_instance)

        patches = _base_patches(
            mock_session_factory,
            mock_iam_settings,
            mock_outbox_settings_disabled,
            mock_spicedb_settings,
            mock_age_pool,
            mock_mcp_inner,
        ) + [
            (
                "iam.application.services.TenantBootstrapService",
                dict(new=mock_bootstrap_cls),
            ),
            ("iam.infrastructure.tenant_repository.TenantRepository", dict()),
            ("iam.infrastructure.workspace_repository.WorkspaceRepository", dict()),
            ("infrastructure.outbox.repository.OutboxRepository", dict()),
            ("infrastructure.observability.startup_probe.DefaultStartupProbe", dict()),
        ]

        with ExitStack() as stack:
            apply_patches(stack, patches)
            async with kartograph_lifespan(app):
                pass

        call_kwargs = (
            mock_bootstrap_instance.ensure_default_tenant_with_workspace.call_args
        )
        assert call_kwargs.kwargs["workspace_name"] == "acme-corp"
        assert call_kwargs.kwargs["tenant_name"] == "acme-corp"


# ---------------------------------------------------------------------------
# Tests: Outbox Worker Lifecycle
# ---------------------------------------------------------------------------


class TestOutboxWorkerLifecycle:
    """Tests for outbox worker startup and shutdown.

    Requirement: Outbox Worker Lifecycle
    Scenario: Outbox enabled
    Scenario: Graceful shutdown
    """

    def _outbox_extra_patches(self, mock_worker_cls, mock_db_settings):
        """Extra patches needed when the outbox is enabled."""
        return [
            ("main.OutboxWorker", dict(new=mock_worker_cls)),
            ("main.get_database_settings", dict(return_value=mock_db_settings)),
            ("main.CompositeEventHandler", dict()),
            ("main.SpiceDBEventHandler", dict()),
            ("main.IAMEventTranslator", dict()),
            ("main.ManagementEventTranslator", dict()),
            ("main.PostgresNotifyEventSource", dict()),
            ("main.DefaultOutboxWorkerProbe", dict()),
            ("main.DefaultEventSourceProbe", dict()),
            ("main.TenantAGEGraphHandler", dict()),
            ("main.AGEGraphProvisioner", dict()),
            ("infrastructure.database.connection.ConnectionFactory", dict()),
        ]

    @pytest.mark.asyncio
    async def test_outbox_worker_started_when_enabled(
        self,
        mock_session_factory,
        mock_iam_settings_single_tenant,
        mock_spicedb_settings,
        mock_outbox_settings_enabled,
        mock_db_settings,
        mock_age_pool,
        mock_mcp_inner,
    ):
        """GIVEN outbox processing is enabled
        WHEN the application starts
        THEN the outbox worker begins processing events from all bounded contexts.
        """
        from main import kartograph_lifespan

        app = FastAPI(lifespan=kartograph_lifespan)

        mock_worker = AsyncMock()
        mock_worker_cls = MagicMock(return_value=mock_worker)

        mock_bootstrap_instance = AsyncMock()
        mock_bootstrap_cls = MagicMock(return_value=mock_bootstrap_instance)

        patches = (
            _base_patches(
                mock_session_factory,
                mock_iam_settings_single_tenant,
                mock_outbox_settings_enabled,
                mock_spicedb_settings,
                mock_age_pool,
                mock_mcp_inner,
            )
            + self._outbox_extra_patches(mock_worker_cls, mock_db_settings)
            + [
                (
                    "iam.application.services.TenantBootstrapService",
                    dict(new=mock_bootstrap_cls),
                ),
                (
                    "iam.infrastructure.tenant_repository.TenantRepository",
                    dict(),
                ),
                (
                    "iam.infrastructure.workspace_repository.WorkspaceRepository",
                    dict(),
                ),
                ("infrastructure.outbox.repository.OutboxRepository", dict()),
                (
                    "infrastructure.observability.startup_probe.DefaultStartupProbe",
                    dict(),
                ),
            ]
        )

        with ExitStack() as stack:
            apply_patches(stack, patches)
            async with kartograph_lifespan(app):
                pass

        mock_worker.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_outbox_worker_not_started_when_disabled(
        self,
        mock_session_factory,
        mock_iam_settings_single_tenant,
        mock_spicedb_settings,
        mock_outbox_settings_disabled,
        mock_age_pool,
        mock_mcp_inner,
    ):
        """GIVEN outbox processing is disabled
        WHEN the application starts
        THEN no outbox worker is created.
        """
        from main import kartograph_lifespan

        app = FastAPI(lifespan=kartograph_lifespan)

        mock_worker_cls = MagicMock()

        mock_bootstrap_instance = AsyncMock()
        mock_bootstrap_cls = MagicMock(return_value=mock_bootstrap_instance)

        patches = _base_patches(
            mock_session_factory,
            mock_iam_settings_single_tenant,
            mock_outbox_settings_disabled,
            mock_spicedb_settings,
            mock_age_pool,
            mock_mcp_inner,
        ) + [
            ("main.OutboxWorker", dict(new=mock_worker_cls)),
            (
                "iam.application.services.TenantBootstrapService",
                dict(new=mock_bootstrap_cls),
            ),
            ("iam.infrastructure.tenant_repository.TenantRepository", dict()),
            ("iam.infrastructure.workspace_repository.WorkspaceRepository", dict()),
            ("infrastructure.outbox.repository.OutboxRepository", dict()),
            ("infrastructure.observability.startup_probe.DefaultStartupProbe", dict()),
        ]

        with ExitStack() as stack:
            apply_patches(stack, patches)
            async with kartograph_lifespan(app):
                pass

        mock_worker_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_outbox_worker_stopped_on_shutdown(
        self,
        mock_session_factory,
        mock_iam_settings_single_tenant,
        mock_spicedb_settings,
        mock_outbox_settings_enabled,
        mock_db_settings,
        mock_age_pool,
        mock_mcp_inner,
    ):
        """GIVEN the outbox worker is running
        WHEN the application shuts down
        THEN the worker stops gracefully.
        """
        from main import kartograph_lifespan

        app = FastAPI(lifespan=kartograph_lifespan)

        mock_worker = AsyncMock()
        mock_worker_cls = MagicMock(return_value=mock_worker)

        mock_bootstrap_instance = AsyncMock()
        mock_bootstrap_cls = MagicMock(return_value=mock_bootstrap_instance)

        patches = (
            _base_patches(
                mock_session_factory,
                mock_iam_settings_single_tenant,
                mock_outbox_settings_enabled,
                mock_spicedb_settings,
                mock_age_pool,
                mock_mcp_inner,
            )
            + self._outbox_extra_patches(mock_worker_cls, mock_db_settings)
            + [
                (
                    "iam.application.services.TenantBootstrapService",
                    dict(new=mock_bootstrap_cls),
                ),
                (
                    "iam.infrastructure.tenant_repository.TenantRepository",
                    dict(),
                ),
                (
                    "iam.infrastructure.workspace_repository.WorkspaceRepository",
                    dict(),
                ),
                ("infrastructure.outbox.repository.OutboxRepository", dict()),
                (
                    "infrastructure.observability.startup_probe.DefaultStartupProbe",
                    dict(),
                ),
            ]
        )

        with ExitStack() as stack:
            apply_patches(stack, patches)
            async with kartograph_lifespan(app):
                pass  # Exit block triggers shutdown

        # Worker should have been stopped during shutdown
        mock_worker.stop.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: Database Connection Lifecycle
# ---------------------------------------------------------------------------


class TestDatabaseConnectionLifecycle:
    """Tests for database engine initialization and disposal.

    Requirement: Database Connection Lifecycle
    Scenario: Startup
    Scenario: Shutdown
    """

    @pytest.mark.asyncio
    async def test_database_engines_initialized_on_startup(
        self,
        mock_session_factory,
        mock_iam_settings_multi_tenant,
        mock_spicedb_settings,
        mock_outbox_settings_disabled,
        mock_age_pool,
        mock_mcp_inner,
    ):
        """GIVEN the application is starting
        WHEN the lifespan begins
        THEN database engines are initialized and connection pools are created.
        """
        from main import kartograph_lifespan

        app = FastAPI(lifespan=kartograph_lifespan)

        mock_init_engines = MagicMock(
            side_effect=_patched_init_engines(mock_session_factory)
        )
        mock_age_pool_fn = MagicMock(return_value=mock_age_pool)
        mock_age_pool_fn.cache_clear = MagicMock()

        patches = [
            ("main.init_database_engines", dict(new=mock_init_engines)),
            ("main.close_database_engines", dict(new_callable=AsyncMock)),
            ("main.get_spicedb_settings", dict(return_value=mock_spicedb_settings)),
            ("main.SpiceDBClient", dict()),
            (
                "main.get_iam_settings",
                dict(return_value=mock_iam_settings_multi_tenant),
            ),
            (
                "main.get_outbox_worker_settings",
                dict(return_value=mock_outbox_settings_disabled),
            ),
            ("main.mcp_http_app_inner", dict(new=mock_mcp_inner)),
            ("main.get_age_connection_pool", dict(new=mock_age_pool_fn)),
        ]

        with ExitStack() as stack:
            apply_patches(stack, patches)
            async with kartograph_lifespan(app):
                pass

        mock_init_engines.assert_called_once_with(app)

    @pytest.mark.asyncio
    async def test_database_engines_disposed_on_shutdown(
        self,
        mock_session_factory,
        mock_iam_settings_multi_tenant,
        mock_spicedb_settings,
        mock_outbox_settings_disabled,
        mock_age_pool,
        mock_mcp_inner,
    ):
        """GIVEN the application is shutting down
        WHEN the lifespan ends
        THEN database engines are disposed and connection pools are released.
        """
        from main import kartograph_lifespan

        app = FastAPI(lifespan=kartograph_lifespan)

        mock_close_engines = AsyncMock()
        mock_age_pool_fn = MagicMock(return_value=mock_age_pool)
        mock_age_pool_fn.cache_clear = MagicMock()

        patches = [
            (
                "main.init_database_engines",
                dict(side_effect=_patched_init_engines(mock_session_factory)),
            ),
            ("main.close_database_engines", dict(new=mock_close_engines)),
            ("main.get_spicedb_settings", dict(return_value=mock_spicedb_settings)),
            ("main.SpiceDBClient", dict()),
            (
                "main.get_iam_settings",
                dict(return_value=mock_iam_settings_multi_tenant),
            ),
            (
                "main.get_outbox_worker_settings",
                dict(return_value=mock_outbox_settings_disabled),
            ),
            ("main.mcp_http_app_inner", dict(new=mock_mcp_inner)),
            ("main.get_age_connection_pool", dict(new=mock_age_pool_fn)),
        ]

        with ExitStack() as stack:
            apply_patches(stack, patches)
            async with kartograph_lifespan(app):
                pass  # Exit triggers shutdown

        mock_close_engines.assert_called_once_with(app)
