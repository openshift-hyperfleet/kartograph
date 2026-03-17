"""Unit tests for DataSourceService.

Tests verify authorization checks, repository interactions,
credential storage, transaction management, and observability probe calls.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from management.application.services.data_source_service import DataSourceService
from management.domain.aggregates import DataSource, KnowledgeGraph
from management.domain.value_objects import (
    DataSourceId,
    KnowledgeGraphId,
    Schedule,
    ScheduleType,
)
from management.ports.exceptions import UnauthorizedError
from shared_kernel.authorization.types import Permission
from shared_kernel.datasource_types import DataSourceAdapterType


@pytest.fixture
def mock_session():
    """Create a mock AsyncSession with begin() context manager."""
    session = MagicMock()

    @asynccontextmanager
    async def _begin():
        yield

    session.begin = _begin
    return session


@pytest.fixture
def mock_ds_repo():
    return AsyncMock()


@pytest.fixture
def mock_kg_repo():
    return AsyncMock()


@pytest.fixture
def mock_secret_store():
    return AsyncMock()


@pytest.fixture
def mock_sync_run_repo():
    return AsyncMock()


@pytest.fixture
def mock_authz():
    return AsyncMock()


@pytest.fixture
def mock_probe():
    return MagicMock()


@pytest.fixture
def tenant_id():
    return "tenant-123"


@pytest.fixture
def user_id():
    return "user-456"


@pytest.fixture
def kg_id():
    return "kg-789"


@pytest.fixture
def service(
    mock_session,
    mock_ds_repo,
    mock_kg_repo,
    mock_secret_store,
    mock_sync_run_repo,
    mock_authz,
    mock_probe,
    tenant_id,
):
    return DataSourceService(
        session=mock_session,
        data_source_repository=mock_ds_repo,
        knowledge_graph_repository=mock_kg_repo,
        secret_store=mock_secret_store,
        sync_run_repository=mock_sync_run_repo,
        authz=mock_authz,
        scope_to_tenant=tenant_id,
        probe=mock_probe,
    )


def _make_kg(
    kg_id: str = "kg-789",
    tenant_id: str = "tenant-123",
    workspace_id: str = "ws-001",
) -> KnowledgeGraph:
    now = datetime.now(UTC)
    kg = KnowledgeGraph(
        id=KnowledgeGraphId(value=kg_id),
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        name="Test KG",
        description="A test KG",
        created_at=now,
        updated_at=now,
    )
    kg.collect_events()
    return kg


def _make_ds(
    ds_id: str = "ds-001",
    kg_id: str = "kg-789",
    tenant_id: str = "tenant-123",
    name: str = "Test DS",
    credentials_path: str | None = None,
) -> DataSource:
    now = datetime.now(UTC)
    ds = DataSource(
        id=DataSourceId(value=ds_id),
        knowledge_graph_id=kg_id,
        tenant_id=tenant_id,
        name=name,
        adapter_type=DataSourceAdapterType.GITHUB,
        connection_config={"url": "https://github.com"},
        credentials_path=credentials_path,
        schedule=Schedule(schedule_type=ScheduleType.MANUAL),
        last_sync_at=None,
        created_at=now,
        updated_at=now,
    )
    ds.collect_events()
    return ds


# ---- create ----


class TestDataSourceServiceCreate:
    """Tests for DataSourceService.create."""

    @pytest.mark.asyncio
    async def test_create_checks_edit_permission_on_kg(
        self, service, mock_authz, user_id, kg_id, mock_kg_repo, tenant_id
    ):
        """create() must check EDIT permission on the knowledge graph."""
        mock_authz.check_permission.return_value = True
        mock_kg_repo.get_by_id.return_value = _make_kg(kg_id=kg_id, tenant_id=tenant_id)

        await service.create(
            user_id=user_id,
            kg_id=kg_id,
            name="My DS",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={"url": "https://github.com"},
        )

        mock_authz.check_permission.assert_called_once_with(
            resource=f"knowledge_graph:{kg_id}",
            permission=Permission.EDIT,
            subject=f"user:{user_id}",
        )

    @pytest.mark.asyncio
    async def test_create_raises_unauthorized_when_permission_denied(
        self, service, mock_authz, mock_probe, user_id, kg_id
    ):
        """create() raises UnauthorizedError when user lacks EDIT on KG."""
        mock_authz.check_permission.return_value = False

        with pytest.raises(UnauthorizedError):
            await service.create(
                user_id=user_id,
                kg_id=kg_id,
                name="My DS",
                adapter_type=DataSourceAdapterType.GITHUB,
                connection_config={"url": "https://github.com"},
            )

        mock_probe.permission_denied.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_verifies_kg_exists_and_belongs_to_tenant(
        self, service, mock_authz, mock_kg_repo, user_id, kg_id
    ):
        """create() raises ValueError when KG not found."""
        mock_authz.check_permission.return_value = True
        mock_kg_repo.get_by_id.return_value = None

        with pytest.raises(ValueError, match="not found"):
            await service.create(
                user_id=user_id,
                kg_id=kg_id,
                name="My DS",
                adapter_type=DataSourceAdapterType.GITHUB,
                connection_config={},
            )

    @pytest.mark.asyncio
    async def test_create_rejects_kg_from_different_tenant(
        self, service, mock_authz, mock_kg_repo, user_id, kg_id
    ):
        """create() raises ValueError when KG belongs to different tenant."""
        mock_authz.check_permission.return_value = True
        mock_kg_repo.get_by_id.return_value = _make_kg(
            kg_id=kg_id, tenant_id="other-tenant"
        )

        with pytest.raises(ValueError, match="different tenant"):
            await service.create(
                user_id=user_id,
                kg_id=kg_id,
                name="My DS",
                adapter_type=DataSourceAdapterType.GITHUB,
                connection_config={},
            )

    @pytest.mark.asyncio
    async def test_create_stores_credentials_when_provided(
        self,
        service,
        mock_authz,
        mock_kg_repo,
        mock_secret_store,
        mock_ds_repo,
        user_id,
        kg_id,
        tenant_id,
    ):
        """create() stores credentials via secret store when raw_credentials provided."""
        mock_authz.check_permission.return_value = True
        mock_kg_repo.get_by_id.return_value = _make_kg(kg_id=kg_id, tenant_id=tenant_id)
        creds = {"token": "abc123"}

        await service.create(
            user_id=user_id,
            kg_id=kg_id,
            name="My DS",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={"url": "https://github.com"},
            raw_credentials=creds,
        )

        mock_secret_store.store.assert_called_once()
        call_kwargs = mock_secret_store.store.call_args
        assert "datasource/" in call_kwargs.kwargs.get("path", "") or "datasource/" in (
            call_kwargs.args[0] if call_kwargs.args else ""
        )

    @pytest.mark.asyncio
    async def test_create_probes_success(
        self, service, mock_authz, mock_kg_repo, mock_probe, user_id, kg_id, tenant_id
    ):
        """create() calls probe on success."""
        mock_authz.check_permission.return_value = True
        mock_kg_repo.get_by_id.return_value = _make_kg(kg_id=kg_id, tenant_id=tenant_id)

        result = await service.create(
            user_id=user_id,
            kg_id=kg_id,
            name="My DS",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={},
        )

        mock_probe.data_source_created.assert_called_once_with(
            ds_id=result.id.value,
            kg_id=kg_id,
            tenant_id=tenant_id,
            name="My DS",
        )


# ---- get ----


class TestDataSourceServiceGet:
    """Tests for DataSourceService.get."""

    @pytest.mark.asyncio
    async def test_get_returns_none_when_not_found(
        self, service, mock_ds_repo, user_id
    ):
        """get() returns None when DS not found."""
        mock_ds_repo.get_by_id.return_value = None

        result = await service.get(user_id=user_id, ds_id="nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_checks_view_permission(
        self, service, mock_authz, mock_ds_repo, user_id
    ):
        """get() checks VIEW permission on the data source."""
        ds = _make_ds()
        mock_ds_repo.get_by_id.return_value = ds
        mock_authz.check_permission.return_value = True

        await service.get(user_id=user_id, ds_id=ds.id.value)

        mock_authz.check_permission.assert_called_once_with(
            resource=f"data_source:{ds.id.value}",
            permission=Permission.VIEW,
            subject=f"user:{user_id}",
        )

    @pytest.mark.asyncio
    async def test_get_raises_unauthorized_when_denied(
        self, service, mock_authz, mock_ds_repo, user_id
    ):
        """get() raises UnauthorizedError when user lacks VIEW."""
        ds = _make_ds()
        mock_ds_repo.get_by_id.return_value = ds
        mock_authz.check_permission.return_value = False

        with pytest.raises(UnauthorizedError):
            await service.get(user_id=user_id, ds_id=ds.id.value)

    @pytest.mark.asyncio
    async def test_get_returns_aggregate_on_success(
        self, service, mock_authz, mock_ds_repo, mock_probe, user_id
    ):
        """get() returns the aggregate when authorized."""
        ds = _make_ds()
        mock_ds_repo.get_by_id.return_value = ds
        mock_authz.check_permission.return_value = True

        result = await service.get(user_id=user_id, ds_id=ds.id.value)

        assert result is ds
        mock_probe.data_source_retrieved.assert_called_once_with(ds_id=ds.id.value)


# ---- list_for_knowledge_graph ----


class TestDataSourceServiceListForKnowledgeGraph:
    """Tests for DataSourceService.list_for_knowledge_graph."""

    @pytest.mark.asyncio
    async def test_list_checks_view_permission_on_kg(
        self, service, mock_authz, mock_ds_repo, user_id, kg_id
    ):
        """list_for_knowledge_graph() checks VIEW on the KG."""
        mock_authz.check_permission.return_value = True
        mock_ds_repo.find_by_knowledge_graph.return_value = []

        await service.list_for_knowledge_graph(user_id=user_id, kg_id=kg_id)

        mock_authz.check_permission.assert_called_once_with(
            resource=f"knowledge_graph:{kg_id}",
            permission=Permission.VIEW,
            subject=f"user:{user_id}",
        )

    @pytest.mark.asyncio
    async def test_list_raises_unauthorized_when_denied(
        self, service, mock_authz, user_id, kg_id
    ):
        """list_for_knowledge_graph() raises UnauthorizedError when denied."""
        mock_authz.check_permission.return_value = False

        with pytest.raises(UnauthorizedError):
            await service.list_for_knowledge_graph(user_id=user_id, kg_id=kg_id)

    @pytest.mark.asyncio
    async def test_list_returns_data_sources(
        self, service, mock_authz, mock_ds_repo, mock_probe, user_id, kg_id
    ):
        """list_for_knowledge_graph() returns data sources from repo."""
        mock_authz.check_permission.return_value = True
        ds1 = _make_ds(ds_id="ds-001")
        ds2 = _make_ds(ds_id="ds-002")
        mock_ds_repo.find_by_knowledge_graph.return_value = [ds1, ds2]

        result = await service.list_for_knowledge_graph(user_id=user_id, kg_id=kg_id)

        assert len(result) == 2
        mock_probe.data_sources_listed.assert_called_once_with(
            kg_id=kg_id,
            count=2,
        )


# ---- update ----


class TestDataSourceServiceUpdate:
    """Tests for DataSourceService.update."""

    @pytest.mark.asyncio
    async def test_update_checks_edit_permission_on_ds(
        self, service, mock_authz, mock_ds_repo, user_id
    ):
        """update() checks EDIT permission on the data source."""
        ds = _make_ds()
        mock_authz.check_permission.return_value = True
        mock_ds_repo.get_by_id.return_value = ds

        await service.update(
            user_id=user_id,
            ds_id=ds.id.value,
            name="Updated",
            connection_config={"url": "https://new.com"},
        )

        mock_authz.check_permission.assert_called_once_with(
            resource=f"data_source:{ds.id.value}",
            permission=Permission.EDIT,
            subject=f"user:{user_id}",
        )

    @pytest.mark.asyncio
    async def test_update_raises_unauthorized_when_denied(
        self, service, mock_authz, user_id
    ):
        """update() raises UnauthorizedError when denied."""
        mock_authz.check_permission.return_value = False

        with pytest.raises(UnauthorizedError):
            await service.update(
                user_id=user_id,
                ds_id="ds-001",
                name="Updated",
            )

    @pytest.mark.asyncio
    async def test_update_raises_value_error_when_not_found(
        self, service, mock_authz, mock_ds_repo, user_id
    ):
        """update() raises ValueError when DS not found."""
        mock_authz.check_permission.return_value = True
        mock_ds_repo.get_by_id.return_value = None

        with pytest.raises(ValueError):
            await service.update(
                user_id=user_id,
                ds_id="nonexistent",
                name="Updated",
            )

    @pytest.mark.asyncio
    async def test_update_stores_credentials_when_provided(
        self, service, mock_authz, mock_ds_repo, mock_secret_store, user_id, tenant_id
    ):
        """update() stores credentials via secret store when raw_credentials provided."""
        ds = _make_ds()
        mock_authz.check_permission.return_value = True
        mock_ds_repo.get_by_id.return_value = ds
        creds = {"token": "new-token"}

        await service.update(
            user_id=user_id,
            ds_id=ds.id.value,
            raw_credentials=creds,
        )

        mock_secret_store.store.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_probes_success(
        self, service, mock_authz, mock_ds_repo, mock_probe, user_id
    ):
        """update() probes success when name is updated."""
        ds = _make_ds()
        mock_authz.check_permission.return_value = True
        mock_ds_repo.get_by_id.return_value = ds

        await service.update(
            user_id=user_id,
            ds_id=ds.id.value,
            name="Updated",
            connection_config={"url": "https://new.com"},
        )

        mock_probe.data_source_updated.assert_called_once_with(
            ds_id=ds.id.value,
            name="Updated",
        )


# ---- delete ----


class TestDataSourceServiceDelete:
    """Tests for DataSourceService.delete."""

    @pytest.mark.asyncio
    async def test_delete_checks_manage_permission_on_ds(
        self, service, mock_authz, mock_ds_repo, user_id
    ):
        """delete() checks MANAGE permission on the data source."""
        ds = _make_ds()
        mock_authz.check_permission.return_value = True
        mock_ds_repo.get_by_id.return_value = ds
        mock_ds_repo.delete.return_value = True

        await service.delete(user_id=user_id, ds_id=ds.id.value)

        mock_authz.check_permission.assert_called_once_with(
            resource=f"data_source:{ds.id.value}",
            permission=Permission.MANAGE,
            subject=f"user:{user_id}",
        )

    @pytest.mark.asyncio
    async def test_delete_raises_unauthorized_when_denied(
        self, service, mock_authz, user_id
    ):
        """delete() raises UnauthorizedError when denied."""
        mock_authz.check_permission.return_value = False

        with pytest.raises(UnauthorizedError):
            await service.delete(user_id=user_id, ds_id="ds-001")

    @pytest.mark.asyncio
    async def test_delete_returns_false_when_not_found(
        self, service, mock_authz, mock_ds_repo, user_id
    ):
        """delete() returns False when DS not found."""
        mock_authz.check_permission.return_value = True
        mock_ds_repo.get_by_id.return_value = None

        result = await service.delete(user_id=user_id, ds_id="nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_removes_credentials_if_path_exists(
        self, service, mock_authz, mock_ds_repo, mock_secret_store, user_id, tenant_id
    ):
        """delete() deletes credentials from secret store if credentials_path is set."""
        ds = _make_ds(credentials_path="datasource/ds-001/credentials")
        mock_authz.check_permission.return_value = True
        mock_ds_repo.get_by_id.return_value = ds
        mock_ds_repo.delete.return_value = True

        await service.delete(user_id=user_id, ds_id=ds.id.value)

        mock_secret_store.delete.assert_called_once_with(
            path="datasource/ds-001/credentials",
            tenant_id=tenant_id,
        )

    @pytest.mark.asyncio
    async def test_delete_probes_success(
        self, service, mock_authz, mock_ds_repo, mock_probe, user_id
    ):
        """delete() calls probe on success."""
        ds = _make_ds()
        mock_authz.check_permission.return_value = True
        mock_ds_repo.get_by_id.return_value = ds
        mock_ds_repo.delete.return_value = True

        await service.delete(user_id=user_id, ds_id=ds.id.value)

        mock_probe.data_source_deleted.assert_called_once_with(ds_id=ds.id.value)


# ---- trigger_sync ----


class TestDataSourceServiceTriggerSync:
    """Tests for DataSourceService.trigger_sync."""

    @pytest.mark.asyncio
    async def test_trigger_sync_checks_manage_permission(
        self, service, mock_authz, mock_ds_repo, mock_sync_run_repo, user_id
    ):
        """trigger_sync() checks MANAGE permission on the data source."""
        ds = _make_ds()
        mock_authz.check_permission.return_value = True
        mock_ds_repo.get_by_id.return_value = ds

        await service.trigger_sync(user_id=user_id, ds_id=ds.id.value)

        mock_authz.check_permission.assert_called_once_with(
            resource=f"data_source:{ds.id.value}",
            permission=Permission.MANAGE,
            subject=f"user:{user_id}",
        )

    @pytest.mark.asyncio
    async def test_trigger_sync_raises_unauthorized_when_denied(
        self, service, mock_authz, user_id
    ):
        """trigger_sync() raises UnauthorizedError when denied."""
        mock_authz.check_permission.return_value = False

        with pytest.raises(UnauthorizedError):
            await service.trigger_sync(user_id=user_id, ds_id="ds-001")

    @pytest.mark.asyncio
    async def test_trigger_sync_raises_value_error_when_not_found(
        self, service, mock_authz, mock_ds_repo, user_id
    ):
        """trigger_sync() raises ValueError when DS not found."""
        mock_authz.check_permission.return_value = True
        mock_ds_repo.get_by_id.return_value = None

        with pytest.raises(ValueError):
            await service.trigger_sync(user_id=user_id, ds_id="nonexistent")

    @pytest.mark.asyncio
    async def test_trigger_sync_creates_sync_run_and_saves_ds(
        self, service, mock_authz, mock_ds_repo, mock_sync_run_repo, mock_probe, user_id
    ):
        """trigger_sync() creates a sync run and saves the data source."""
        ds = _make_ds()
        mock_authz.check_permission.return_value = True
        mock_ds_repo.get_by_id.return_value = ds

        result = await service.trigger_sync(user_id=user_id, ds_id=ds.id.value)

        assert result.data_source_id == ds.id.value
        assert result.status == "pending"
        mock_sync_run_repo.save.assert_called_once()
        mock_ds_repo.save.assert_called_once()
        mock_probe.sync_requested.assert_called_once_with(ds_id=ds.id.value)
