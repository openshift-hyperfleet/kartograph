"""Unit tests for DataSourceService.

Tests verify authorization checks, repository interactions,
credential storage, transaction management, and observability probe calls.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime

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
from tests.fakes.authorization import InMemoryAuthorizationProvider
from tests.fakes.management import (
    InMemoryDataSourceRepository,
    InMemoryDataSourceSyncRunRepository,
    InMemoryKnowledgeGraphRepository,
    InMemorySecretStoreRepository,
    RecordingDataSourceServiceProbe,
)


@pytest.fixture
def mock_session():
    """Create a fake AsyncSession with begin() context manager."""
    from unittest.mock import MagicMock

    session = MagicMock()

    @asynccontextmanager
    async def _begin():
        yield

    session.begin = _begin
    return session


@pytest.fixture
def ds_repo():
    return InMemoryDataSourceRepository()


@pytest.fixture
def kg_repo():
    return InMemoryKnowledgeGraphRepository()


@pytest.fixture
def secret_store():
    return InMemorySecretStoreRepository()


@pytest.fixture
def sync_run_repo():
    return InMemoryDataSourceSyncRunRepository()


@pytest.fixture
def authz():
    return InMemoryAuthorizationProvider()


@pytest.fixture
def probe():
    return RecordingDataSourceServiceProbe()


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
    ds_repo,
    kg_repo,
    secret_store,
    sync_run_repo,
    authz,
    probe,
    tenant_id,
):
    return DataSourceService(
        session=mock_session,
        data_source_repository=ds_repo,
        knowledge_graph_repository=kg_repo,
        secret_store=secret_store,
        sync_run_repository=sync_run_repo,
        authz=authz,
        scope_to_tenant=tenant_id,
        probe=probe,
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
        self, service, authz, user_id, kg_id, kg_repo, tenant_id
    ):
        """create() must check EDIT permission on the knowledge graph."""
        await authz.write_relationship(
            f"knowledge_graph:{kg_id}", "editor", f"user:{user_id}"
        )
        kg_repo.seed(_make_kg(kg_id=kg_id, tenant_id=tenant_id))

        await service.create(
            user_id=user_id,
            kg_id=kg_id,
            name="My DS",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={"url": "https://github.com"},
        )

        assert len(authz.check_permission_calls) == 1
        assert authz.check_permission_calls[0] == {
            "resource": f"knowledge_graph:{kg_id}",
            "permission": Permission.EDIT,
            "subject": f"user:{user_id}",
        }

    @pytest.mark.asyncio
    async def test_create_raises_unauthorized_when_permission_denied(
        self, service, probe, user_id, kg_id
    ):
        """create() raises UnauthorizedError when user lacks EDIT on KG."""
        # No relationship written — permission denied

        with pytest.raises(UnauthorizedError):
            await service.create(
                user_id=user_id,
                kg_id=kg_id,
                name="My DS",
                adapter_type=DataSourceAdapterType.GITHUB,
                connection_config={"url": "https://github.com"},
            )

        assert len(probe.permission_denied_calls) == 1

    @pytest.mark.asyncio
    async def test_create_verifies_kg_exists_and_belongs_to_tenant(
        self, service, authz, user_id, kg_id
    ):
        """create() raises ValueError when KG not found."""
        await authz.write_relationship(
            f"knowledge_graph:{kg_id}", "editor", f"user:{user_id}"
        )
        # KG not seeded — get_by_id returns None

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
        self, service, authz, kg_repo, user_id, kg_id
    ):
        """create() raises ValueError when KG belongs to different tenant."""
        await authz.write_relationship(
            f"knowledge_graph:{kg_id}", "editor", f"user:{user_id}"
        )
        kg_repo.seed(_make_kg(kg_id=kg_id, tenant_id="other-tenant"))

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
        authz,
        kg_repo,
        secret_store,
        ds_repo,
        user_id,
        kg_id,
        tenant_id,
    ):
        """create() stores credentials via secret store when raw_credentials provided."""
        await authz.write_relationship(
            f"knowledge_graph:{kg_id}", "editor", f"user:{user_id}"
        )
        kg_repo.seed(_make_kg(kg_id=kg_id, tenant_id=tenant_id))
        creds = {"token": "abc123"}

        await service.create(
            user_id=user_id,
            kg_id=kg_id,
            name="My DS",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={"url": "https://github.com"},
            raw_credentials=creds,
        )

        assert len(secret_store.store_calls) == 1
        call_info = secret_store.store_calls[0]
        assert "datasource/" in call_info.get("path", "")
        assert call_info.get("tenant_id") == tenant_id
        assert call_info.get("credentials") == creds

    @pytest.mark.asyncio
    async def test_create_probes_success(
        self, service, authz, kg_repo, probe, user_id, kg_id, tenant_id
    ):
        """create() calls probe on success."""
        await authz.write_relationship(
            f"knowledge_graph:{kg_id}", "editor", f"user:{user_id}"
        )
        kg_repo.seed(_make_kg(kg_id=kg_id, tenant_id=tenant_id))

        result = await service.create(
            user_id=user_id,
            kg_id=kg_id,
            name="My DS",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={},
        )

        assert len(probe.data_source_created_calls) == 1
        assert probe.data_source_created_calls[0] == {
            "ds_id": result.id.value,
            "kg_id": kg_id,
            "tenant_id": tenant_id,
            "name": "My DS",
        }


# ---- get ----


class TestDataSourceServiceGet:
    """Tests for DataSourceService.get."""

    @pytest.mark.asyncio
    async def test_get_returns_none_when_not_found(self, service, ds_repo, user_id):
        """get() returns None when DS not found."""
        # DS not seeded

        result = await service.get(user_id=user_id, ds_id="nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_checks_view_permission(self, service, authz, ds_repo, user_id):
        """get() checks VIEW permission on the data source."""
        ds = _make_ds()
        ds_repo.seed(ds)
        await authz.write_relationship(
            f"data_source:{ds.id.value}", "view", f"user:{user_id}"
        )

        await service.get(user_id=user_id, ds_id=ds.id.value)

        assert len(authz.check_permission_calls) == 1
        assert authz.check_permission_calls[0] == {
            "resource": f"data_source:{ds.id.value}",
            "permission": Permission.VIEW,
            "subject": f"user:{user_id}",
        }

    @pytest.mark.asyncio
    async def test_get_returns_none_for_different_tenant(
        self, service, ds_repo, user_id
    ):
        """get() returns None when DS belongs to a different tenant."""
        ds = _make_ds(tenant_id="other-tenant")
        ds_repo.seed(ds)

        result = await service.get(user_id=user_id, ds_id=ds.id.value)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_returns_none_when_permission_denied(
        self, service, authz, ds_repo, user_id
    ):
        """get() returns None when user lacks VIEW (no existence leakage)."""
        ds = _make_ds()
        ds_repo.seed(ds)
        # No relationship written — permission denied

        result = await service.get(user_id=user_id, ds_id=ds.id.value)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_returns_aggregate_on_success(
        self, service, authz, ds_repo, probe, user_id
    ):
        """get() returns the aggregate when authorized."""
        ds = _make_ds()
        ds_repo.seed(ds)
        await authz.write_relationship(
            f"data_source:{ds.id.value}", "view", f"user:{user_id}"
        )

        result = await service.get(user_id=user_id, ds_id=ds.id.value)

        assert result is ds
        assert len(probe.data_source_retrieved_calls) == 1
        assert probe.data_source_retrieved_calls[0] == {"ds_id": ds.id.value}


# ---- list_for_knowledge_graph ----


class TestDataSourceServiceListForKnowledgeGraph:
    """Tests for DataSourceService.list_for_knowledge_graph."""

    @pytest.mark.asyncio
    async def test_list_checks_view_permission_on_kg(
        self, service, authz, ds_repo, kg_repo, user_id, kg_id, tenant_id
    ):
        """list_for_knowledge_graph() checks VIEW on the KG."""
        await authz.write_relationship(
            f"knowledge_graph:{kg_id}", "viewer", f"user:{user_id}"
        )
        kg_repo.seed(_make_kg(kg_id=kg_id, tenant_id=tenant_id))

        await service.list_for_knowledge_graph(user_id=user_id, kg_id=kg_id)

        assert len(authz.check_permission_calls) == 1
        assert authz.check_permission_calls[0] == {
            "resource": f"knowledge_graph:{kg_id}",
            "permission": Permission.VIEW,
            "subject": f"user:{user_id}",
        }

    @pytest.mark.asyncio
    async def test_list_raises_unauthorized_when_denied(
        self, service, authz, user_id, kg_id
    ):
        """list_for_knowledge_graph() raises UnauthorizedError when denied."""
        # No relationship written — permission denied

        with pytest.raises(UnauthorizedError):
            await service.list_for_knowledge_graph(user_id=user_id, kg_id=kg_id)

    @pytest.mark.asyncio
    async def test_list_raises_unauthorized_when_kg_not_found(
        self, service, authz, kg_repo, user_id, kg_id
    ):
        """list_for_knowledge_graph() raises UnauthorizedError when KG not found."""
        await authz.write_relationship(
            f"knowledge_graph:{kg_id}", "viewer", f"user:{user_id}"
        )
        # KG not seeded

        with pytest.raises(UnauthorizedError, match="not accessible"):
            await service.list_for_knowledge_graph(user_id=user_id, kg_id=kg_id)

    @pytest.mark.asyncio
    async def test_list_raises_unauthorized_for_different_tenant_kg(
        self, service, authz, kg_repo, user_id, kg_id
    ):
        """list_for_knowledge_graph() rejects KG belonging to different tenant."""
        await authz.write_relationship(
            f"knowledge_graph:{kg_id}", "viewer", f"user:{user_id}"
        )
        kg_repo.seed(_make_kg(kg_id=kg_id, tenant_id="other-tenant"))

        with pytest.raises(UnauthorizedError, match="not accessible"):
            await service.list_for_knowledge_graph(user_id=user_id, kg_id=kg_id)

    @pytest.mark.asyncio
    async def test_list_returns_data_sources(
        self,
        service,
        authz,
        ds_repo,
        kg_repo,
        probe,
        user_id,
        kg_id,
        tenant_id,
    ):
        """list_for_knowledge_graph() returns data sources from repo."""
        await authz.write_relationship(
            f"knowledge_graph:{kg_id}", "viewer", f"user:{user_id}"
        )
        kg_repo.seed(_make_kg(kg_id=kg_id, tenant_id=tenant_id))
        ds1 = _make_ds(ds_id="ds-001")
        ds2 = _make_ds(ds_id="ds-002")
        ds_repo.seed(ds1, ds2)

        result = await service.list_for_knowledge_graph(user_id=user_id, kg_id=kg_id)

        assert len(result) == 2
        assert len(probe.data_sources_listed_calls) == 1
        assert probe.data_sources_listed_calls[0] == {"kg_id": kg_id, "count": 2}


# ---- update ----


class TestDataSourceServiceUpdate:
    """Tests for DataSourceService.update."""

    @pytest.mark.asyncio
    async def test_update_checks_edit_permission_on_ds(
        self, service, authz, ds_repo, user_id
    ):
        """update() checks EDIT permission on the data source."""
        ds = _make_ds()
        ds_repo.seed(ds)
        await authz.write_relationship(
            f"data_source:{ds.id.value}", "edit", f"user:{user_id}"
        )

        await service.update(
            user_id=user_id,
            ds_id=ds.id.value,
            name="Updated",
            connection_config={"url": "https://new.com"},
        )

        assert len(authz.check_permission_calls) == 1
        assert authz.check_permission_calls[0] == {
            "resource": f"data_source:{ds.id.value}",
            "permission": Permission.EDIT,
            "subject": f"user:{user_id}",
        }

    @pytest.mark.asyncio
    async def test_update_raises_unauthorized_when_denied(
        self, service, authz, user_id
    ):
        """update() raises UnauthorizedError when denied."""
        # No relationship written — permission denied

        with pytest.raises(UnauthorizedError):
            await service.update(
                user_id=user_id,
                ds_id="ds-001",
                name="Updated",
            )

    @pytest.mark.asyncio
    async def test_update_raises_value_error_when_not_found(
        self, service, authz, ds_repo, user_id
    ):
        """update() raises ValueError when DS not found."""
        await authz.write_relationship(
            "data_source:nonexistent", "edit", f"user:{user_id}"
        )
        # DS not seeded

        with pytest.raises(ValueError):
            await service.update(
                user_id=user_id,
                ds_id="nonexistent",
                name="Updated",
            )

    @pytest.mark.asyncio
    async def test_update_rejects_different_tenant(
        self, service, authz, ds_repo, user_id
    ):
        """update() raises ValueError when DS belongs to a different tenant."""
        ds = _make_ds(tenant_id="other-tenant")
        ds_repo.seed(ds)
        await authz.write_relationship(
            f"data_source:{ds.id.value}", "edit", f"user:{user_id}"
        )

        with pytest.raises(ValueError):
            await service.update(
                user_id=user_id,
                ds_id=ds.id.value,
                name="Updated",
            )

    @pytest.mark.asyncio
    async def test_update_stores_credentials_when_provided(
        self, service, authz, ds_repo, secret_store, user_id, tenant_id
    ):
        """update() stores credentials via secret store when raw_credentials provided."""
        ds = _make_ds()
        ds_repo.seed(ds)
        await authz.write_relationship(
            f"data_source:{ds.id.value}", "edit", f"user:{user_id}"
        )
        creds = {"token": "new-token"}

        await service.update(
            user_id=user_id,
            ds_id=ds.id.value,
            raw_credentials=creds,
        )

        assert len(secret_store.store_calls) == 1
        call_info = secret_store.store_calls[0]
        assert "datasource/" in call_info.get("path", "")
        assert call_info.get("tenant_id") == tenant_id
        assert call_info.get("credentials") == creds

    @pytest.mark.asyncio
    async def test_update_probes_success(self, service, authz, ds_repo, probe, user_id):
        """update() probes success when name is updated."""
        ds = _make_ds()
        ds_repo.seed(ds)
        await authz.write_relationship(
            f"data_source:{ds.id.value}", "edit", f"user:{user_id}"
        )

        await service.update(
            user_id=user_id,
            ds_id=ds.id.value,
            name="Updated",
            connection_config={"url": "https://new.com"},
        )

        assert len(probe.data_source_updated_calls) == 1
        assert probe.data_source_updated_calls[0] == {
            "ds_id": ds.id.value,
            "name": "Updated",
        }


# ---- delete ----


class TestDataSourceServiceDelete:
    """Tests for DataSourceService.delete."""

    @pytest.mark.asyncio
    async def test_delete_checks_manage_permission_on_ds(
        self, service, authz, ds_repo, user_id
    ):
        """delete() checks MANAGE permission on the data source."""
        ds = _make_ds()
        ds_repo.seed(ds)
        await authz.write_relationship(
            f"data_source:{ds.id.value}", "manage", f"user:{user_id}"
        )

        await service.delete(user_id=user_id, ds_id=ds.id.value)

        assert len(authz.check_permission_calls) == 1
        assert authz.check_permission_calls[0] == {
            "resource": f"data_source:{ds.id.value}",
            "permission": Permission.MANAGE,
            "subject": f"user:{user_id}",
        }

    @pytest.mark.asyncio
    async def test_delete_raises_unauthorized_when_denied(
        self, service, authz, user_id
    ):
        """delete() raises UnauthorizedError when denied."""
        # No relationship written — permission denied

        with pytest.raises(UnauthorizedError):
            await service.delete(user_id=user_id, ds_id="ds-001")

    @pytest.mark.asyncio
    async def test_delete_returns_false_when_not_found(
        self, service, authz, ds_repo, user_id
    ):
        """delete() returns False when DS not found."""
        await authz.write_relationship(
            "data_source:nonexistent", "manage", f"user:{user_id}"
        )
        # DS not seeded

        result = await service.delete(user_id=user_id, ds_id="nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_returns_false_for_different_tenant(
        self, service, authz, ds_repo, user_id
    ):
        """delete() returns False when DS belongs to a different tenant."""
        ds = _make_ds(tenant_id="other-tenant")
        ds_repo.seed(ds)
        await authz.write_relationship(
            f"data_source:{ds.id.value}", "manage", f"user:{user_id}"
        )

        result = await service.delete(user_id=user_id, ds_id=ds.id.value)

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_removes_credentials_if_path_exists(
        self, service, authz, ds_repo, secret_store, user_id, tenant_id
    ):
        """delete() deletes credentials from secret store if credentials_path is set."""
        ds = _make_ds(credentials_path="datasource/ds-001/credentials")
        ds_repo.seed(ds)
        await authz.write_relationship(
            f"data_source:{ds.id.value}", "manage", f"user:{user_id}"
        )

        await service.delete(user_id=user_id, ds_id=ds.id.value)

        assert len(secret_store.delete_calls) == 1
        assert secret_store.delete_calls[0] == {
            "path": "datasource/ds-001/credentials",
            "tenant_id": tenant_id,
        }

    @pytest.mark.asyncio
    async def test_delete_probes_success(self, service, authz, ds_repo, probe, user_id):
        """delete() calls probe on success."""
        ds = _make_ds()
        ds_repo.seed(ds)
        await authz.write_relationship(
            f"data_source:{ds.id.value}", "manage", f"user:{user_id}"
        )

        await service.delete(user_id=user_id, ds_id=ds.id.value)

        assert len(probe.data_source_deleted_calls) == 1
        assert probe.data_source_deleted_calls[0] == {"ds_id": ds.id.value}


# ---- trigger_sync ----


class TestDataSourceServiceTriggerSync:
    """Tests for DataSourceService.trigger_sync."""

    @pytest.mark.asyncio
    async def test_trigger_sync_checks_manage_permission(
        self, service, authz, ds_repo, sync_run_repo, user_id
    ):
        """trigger_sync() checks MANAGE permission on the data source."""
        ds = _make_ds()
        ds_repo.seed(ds)
        await authz.write_relationship(
            f"data_source:{ds.id.value}", "manage", f"user:{user_id}"
        )

        await service.trigger_sync(user_id=user_id, ds_id=ds.id.value)

        assert len(authz.check_permission_calls) == 1
        assert authz.check_permission_calls[0] == {
            "resource": f"data_source:{ds.id.value}",
            "permission": Permission.MANAGE,
            "subject": f"user:{user_id}",
        }

    @pytest.mark.asyncio
    async def test_trigger_sync_raises_unauthorized_when_denied(
        self, service, authz, user_id
    ):
        """trigger_sync() raises UnauthorizedError when denied."""
        # No relationship written — permission denied

        with pytest.raises(UnauthorizedError):
            await service.trigger_sync(user_id=user_id, ds_id="ds-001")

    @pytest.mark.asyncio
    async def test_trigger_sync_raises_value_error_when_not_found(
        self, service, authz, ds_repo, user_id
    ):
        """trigger_sync() raises ValueError when DS not found."""
        await authz.write_relationship(
            "data_source:nonexistent", "manage", f"user:{user_id}"
        )
        # DS not seeded

        with pytest.raises(ValueError):
            await service.trigger_sync(user_id=user_id, ds_id="nonexistent")

    @pytest.mark.asyncio
    async def test_trigger_sync_rejects_different_tenant(
        self, service, authz, ds_repo, user_id
    ):
        """trigger_sync() raises ValueError when DS belongs to a different tenant."""
        ds = _make_ds(tenant_id="other-tenant")
        ds_repo.seed(ds)
        await authz.write_relationship(
            f"data_source:{ds.id.value}", "manage", f"user:{user_id}"
        )

        with pytest.raises(ValueError):
            await service.trigger_sync(user_id=user_id, ds_id=ds.id.value)

    @pytest.mark.asyncio
    async def test_trigger_sync_creates_sync_run_and_saves_ds(
        self, service, authz, ds_repo, sync_run_repo, probe, user_id
    ):
        """trigger_sync() creates a sync run and saves the data source."""
        ds = _make_ds()
        ds_repo.seed(ds)
        await authz.write_relationship(
            f"data_source:{ds.id.value}", "manage", f"user:{user_id}"
        )

        result = await service.trigger_sync(user_id=user_id, ds_id=ds.id.value)

        assert result.data_source_id == ds.id.value
        assert result.status == "pending"
        assert len(sync_run_repo.saved) == 1
        assert len(ds_repo.saved) == 1
        assert len(probe.sync_requested_calls) == 1
        assert probe.sync_requested_calls[0] == {"ds_id": ds.id.value}


class TestDataSourceServiceListAllForUser:
    """Unit tests for DataSourceService.list_all_for_user."""

    @pytest.mark.asyncio
    async def test_returns_all_data_sources_across_kgs(
        self,
        service,
        authz,
        kg_repo,
        ds_repo,
        sync_run_repo,
        user_id,
        tenant_id,
    ):
        """list_all_for_user() aggregates data sources from all accessible KGs."""
        from management.domain.entities import DataSourceSyncRun

        kg1 = _make_kg(kg_id="kg-1", tenant_id=tenant_id)
        kg2 = _make_kg(kg_id="kg-2", tenant_id=tenant_id)
        ds1 = _make_ds(ds_id="ds-1", kg_id="kg-1")
        ds2 = _make_ds(ds_id="ds-2", kg_id="kg-2")
        now = datetime.now(UTC)
        run1 = DataSourceSyncRun(
            id="run-1",
            data_source_id="ds-1",
            status="completed",
            started_at=now,
            completed_at=now,
            error=None,
            created_at=now,
        )

        kg_repo.seed(kg1, kg2)
        ds_repo.seed(ds1, ds2)
        await sync_run_repo.save(run1)
        await authz.write_relationship(
            "knowledge_graph:kg-1", "viewer", f"user:{user_id}"
        )
        await authz.write_relationship(
            "knowledge_graph:kg-2", "viewer", f"user:{user_id}"
        )

        result = await service.list_all_for_user(user_id=user_id)

        assert len(result) == 2

        ds1_result = next(r for r in result if r.data_source.id.value == "ds-1")
        assert ds1_result.latest_sync_run is not None
        assert ds1_result.latest_sync_run.status == "completed"

        ds2_result = next(r for r in result if r.data_source.id.value == "ds-2")
        assert ds2_result.latest_sync_run is None

    @pytest.mark.asyncio
    async def test_excludes_kgs_user_cannot_view(
        self,
        service,
        authz,
        kg_repo,
        ds_repo,
        user_id,
        tenant_id,
    ):
        """list_all_for_user() excludes data sources from KGs the user cannot VIEW."""
        kg_allowed = _make_kg(kg_id="kg-allowed", tenant_id=tenant_id)
        kg_denied = _make_kg(kg_id="kg-denied", tenant_id=tenant_id)
        ds_allowed = _make_ds(ds_id="ds-allowed", kg_id="kg-allowed")

        kg_repo.seed(kg_allowed, kg_denied)
        ds_repo.seed(ds_allowed)
        # Only grant VIEW on kg-allowed (not kg-denied)
        await authz.write_relationship(
            "knowledge_graph:kg-allowed", "viewer", f"user:{user_id}"
        )

        result = await service.list_all_for_user(user_id=user_id)

        assert len(result) == 1
        assert result[0].data_source.id.value == "ds-allowed"

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_accessible_kgs(
        self,
        service,
        user_id,
    ):
        """list_all_for_user() returns empty list when user has no accessible KGs."""
        result = await service.list_all_for_user(user_id=user_id)

        assert result == []

    @pytest.mark.asyncio
    async def test_data_source_with_no_sync_run_has_none_latest(
        self,
        service,
        authz,
        kg_repo,
        ds_repo,
        user_id,
        tenant_id,
    ):
        """list_all_for_user() sets latest_sync_run=None for sources with no runs."""
        kg = _make_kg(kg_id="kg-1", tenant_id=tenant_id)
        ds = _make_ds(ds_id="ds-1", kg_id="kg-1")

        kg_repo.seed(kg)
        ds_repo.seed(ds)
        await authz.write_relationship(
            "knowledge_graph:kg-1", "viewer", f"user:{user_id}"
        )

        result = await service.list_all_for_user(user_id=user_id)

        assert len(result) == 1
        assert result[0].latest_sync_run is None
