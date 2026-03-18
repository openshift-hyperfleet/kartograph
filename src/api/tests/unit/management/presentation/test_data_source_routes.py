"""Unit tests for Data Source route handlers.

Tests route-level behavior including status codes, response shapes,
error handling, and pagination. Service dependencies are mocked.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from iam.application.value_objects import CurrentUser
from iam.domain.value_objects import TenantId, UserId
from management.domain.aggregates import DataSource
from management.domain.entities import DataSourceSyncRun
from management.domain.value_objects import DataSourceId, Schedule, ScheduleType
from management.ports.exceptions import (
    DuplicateDataSourceNameError,
    UnauthorizedError,
)
from shared_kernel.datasource_types import DataSourceAdapterType

# Fixed test data
TENANT_ID = "test-tenant-id"
KG_ID = "01JTEST00000000000000KG001"
DS_ID = "01JTEST00000000000000DS001"
USER_ID = "test-user-id"
NOW = datetime(2025, 1, 1, tzinfo=UTC)


def _make_current_user() -> CurrentUser:
    """Create a CurrentUser for dependency override."""
    return CurrentUser(
        user_id=UserId(value=USER_ID),
        username="testuser",
        tenant_id=TenantId(value=TENANT_ID),
    )


def _make_ds(
    ds_id: str = DS_ID,
    name: str = "Test DS",
    credentials_path: str | None = None,
) -> DataSource:
    """Create a DataSource aggregate for testing."""
    return DataSource(
        id=DataSourceId(value=ds_id),
        knowledge_graph_id=KG_ID,
        tenant_id=TENANT_ID,
        name=name,
        adapter_type=DataSourceAdapterType.GITHUB,
        connection_config={"owner": "test", "repo": "test-repo"},
        credentials_path=credentials_path,
        schedule=Schedule(schedule_type=ScheduleType.MANUAL),
        last_sync_at=None,
        created_at=NOW,
        updated_at=NOW,
    )


def _make_sync_run(ds_id: str = DS_ID) -> DataSourceSyncRun:
    """Create a DataSourceSyncRun entity for testing."""
    return DataSourceSyncRun(
        id="01JTEST0000000000000SYNC01",
        data_source_id=ds_id,
        status="pending",
        started_at=NOW,
        completed_at=None,
        error=None,
        created_at=NOW,
    )


@pytest_asyncio.fixture
async def mock_service():
    """Create a mock DataSourceService."""
    return AsyncMock()


@pytest_asyncio.fixture
async def client(mock_service):
    """Create an async HTTP client with mocked dependencies."""
    from main import app

    from iam.dependencies.user import get_current_user
    from management.dependencies.data_source import get_data_source_service

    app.dependency_overrides[get_current_user] = lambda: _make_current_user()
    app.dependency_overrides[get_data_source_service] = lambda: mock_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()


class TestCreateDataSource:
    """Tests for POST /management/knowledge-graphs/{kg_id}/data-sources."""

    @pytest.mark.asyncio
    async def test_creates_successfully(self, client, mock_service):
        """Test successful creation returns 201 with correct response shape."""
        ds = _make_ds()
        mock_service.create.return_value = ds

        resp = await client.post(
            f"/management/knowledge-graphs/{KG_ID}/data-sources",
            json={
                "name": "Test DS",
                "adapter_type": "github",
                "connection_config": {"owner": "test", "repo": "test-repo"},
            },
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == DS_ID
        assert data["knowledge_graph_id"] == KG_ID
        assert data["tenant_id"] == TENANT_ID
        assert data["name"] == "Test DS"
        assert data["adapter_type"] == "github"
        assert data["connection_config"] == {"owner": "test", "repo": "test-repo"}
        assert data["has_credentials"] is False
        assert data["schedule_type"] == "manual"
        assert data["schedule_value"] is None
        assert data["last_sync_at"] is None

    @pytest.mark.asyncio
    async def test_creates_with_credentials(self, client, mock_service):
        """Test creation with credentials sets has_credentials=true."""
        ds = _make_ds(credentials_path="datasource/ds1/credentials")
        mock_service.create.return_value = ds

        resp = await client.post(
            f"/management/knowledge-graphs/{KG_ID}/data-sources",
            json={
                "name": "Test DS",
                "adapter_type": "github",
                "connection_config": {"owner": "test", "repo": "test-repo"},
                "credentials": {"token": "secret"},
            },
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["has_credentials"] is True
        # Credentials should NOT be in response
        assert "credentials" not in data
        assert "credentials_path" not in data

        mock_service.create.assert_awaited_once_with(
            user_id=USER_ID,
            kg_id=KG_ID,
            name="Test DS",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={"owner": "test", "repo": "test-repo"},
            raw_credentials={"token": "secret"},
        )

    @pytest.mark.asyncio
    async def test_invalid_adapter_type_returns_400(self, client, mock_service):
        """Test that invalid adapter type returns 400."""
        resp = await client.post(
            f"/management/knowledge-graphs/{KG_ID}/data-sources",
            json={
                "name": "Test DS",
                "adapter_type": "invalid_type",
                "connection_config": {},
            },
        )

        assert resp.status_code == 400
        assert "adapter type" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_unauthorized_returns_403(self, client, mock_service):
        """Test that UnauthorizedError maps to 403."""
        mock_service.create.side_effect = UnauthorizedError("denied")

        resp = await client.post(
            f"/management/knowledge-graphs/{KG_ID}/data-sources",
            json={
                "name": "Test DS",
                "adapter_type": "github",
                "connection_config": {},
            },
        )

        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_duplicate_name_returns_409(self, client, mock_service):
        """Test that DuplicateDataSourceNameError maps to 409."""
        mock_service.create.side_effect = DuplicateDataSourceNameError("dup")

        resp = await client.post(
            f"/management/knowledge-graphs/{KG_ID}/data-sources",
            json={
                "name": "Test DS",
                "adapter_type": "github",
                "connection_config": {},
            },
        )

        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_empty_name_returns_422(self, client, mock_service):
        """Test that Pydantic validation rejects empty name."""
        resp = await client.post(
            f"/management/knowledge-graphs/{KG_ID}/data-sources",
            json={
                "name": "",
                "adapter_type": "github",
                "connection_config": {},
            },
        )

        assert resp.status_code == 422


class TestListDataSources:
    """Tests for GET /management/knowledge-graphs/{kg_id}/data-sources."""

    @pytest.mark.asyncio
    async def test_lists_successfully(self, client, mock_service):
        """Test successful list returns 200 with correct pagination."""
        data_sources = [
            _make_ds(ds_id=f"01JTEST00000000000000DS00{i}") for i in range(3)
        ]
        mock_service.list_for_knowledge_graph.return_value = data_sources

        resp = await client.get(
            f"/management/knowledge-graphs/{KG_ID}/data-sources",
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3
        assert data["offset"] == 0
        assert data["limit"] == 20

    @pytest.mark.asyncio
    async def test_pagination_offset_limit(self, client, mock_service):
        """Test that offset and limit query params work correctly."""
        data_sources = [
            _make_ds(ds_id=f"01JTEST00000000000000DS00{i}") for i in range(5)
        ]
        mock_service.list_for_knowledge_graph.return_value = data_sources

        resp = await client.get(
            f"/management/knowledge-graphs/{KG_ID}/data-sources?offset=2&limit=2",
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2
        assert data["offset"] == 2
        assert data["limit"] == 2

    @pytest.mark.asyncio
    async def test_unauthorized_returns_403(self, client, mock_service):
        """Test that UnauthorizedError maps to 403."""
        mock_service.list_for_knowledge_graph.side_effect = UnauthorizedError("denied")

        resp = await client.get(
            f"/management/knowledge-graphs/{KG_ID}/data-sources",
        )

        assert resp.status_code == 403


class TestGetDataSource:
    """Tests for GET /management/data-sources/{ds_id}."""

    @pytest.mark.asyncio
    async def test_gets_successfully(self, client, mock_service):
        """Test successful get returns 200 with correct response."""
        ds = _make_ds()
        mock_service.get.return_value = ds

        resp = await client.get(f"/management/data-sources/{DS_ID}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == DS_ID
        assert data["name"] == "Test DS"

    @pytest.mark.asyncio
    async def test_not_found_returns_404(self, client, mock_service):
        """Test that None from service maps to 404."""
        mock_service.get.return_value = None

        resp = await client.get(f"/management/data-sources/{DS_ID}")

        assert resp.status_code == 404


class TestUpdateDataSource:
    """Tests for PATCH /management/data-sources/{ds_id}."""

    @pytest.mark.asyncio
    async def test_updates_successfully(self, client, mock_service):
        """Test successful update returns 200."""
        ds = _make_ds(name="Updated DS")
        mock_service.update.return_value = ds

        resp = await client.patch(
            f"/management/data-sources/{DS_ID}",
            json={"name": "Updated DS"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated DS"

        mock_service.update.assert_awaited_once_with(
            user_id=USER_ID,
            ds_id=DS_ID,
            name="Updated DS",
            connection_config=None,
            raw_credentials=None,
        )

    @pytest.mark.asyncio
    async def test_unauthorized_returns_403(self, client, mock_service):
        """Test that UnauthorizedError maps to 403."""
        mock_service.update.side_effect = UnauthorizedError("denied")

        resp = await client.patch(
            f"/management/data-sources/{DS_ID}",
            json={"name": "New Name"},
        )

        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_duplicate_name_returns_409(self, client, mock_service):
        """Test that DuplicateDataSourceNameError maps to 409."""
        mock_service.update.side_effect = DuplicateDataSourceNameError("dup")

        resp = await client.patch(
            f"/management/data-sources/{DS_ID}",
            json={"name": "Existing Name"},
        )

        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_not_found_returns_404(self, client, mock_service):
        """Test that ValueError with 'not found' from service maps to 404."""
        mock_service.update.side_effect = ValueError("not found")

        resp = await client.patch(
            f"/management/data-sources/{DS_ID}",
            json={"name": "New Name"},
        )

        assert resp.status_code == 404


class TestDeleteDataSource:
    """Tests for DELETE /management/data-sources/{ds_id}."""

    @pytest.mark.asyncio
    async def test_deletes_successfully(self, client, mock_service):
        """Test successful delete returns 204."""
        mock_service.delete.return_value = True

        resp = await client.delete(f"/management/data-sources/{DS_ID}")

        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_not_found_returns_404(self, client, mock_service):
        """Test that False from service maps to 404."""
        mock_service.delete.return_value = False

        resp = await client.delete(f"/management/data-sources/{DS_ID}")

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_unauthorized_returns_403(self, client, mock_service):
        """Test that UnauthorizedError maps to 403."""
        mock_service.delete.side_effect = UnauthorizedError("denied")

        resp = await client.delete(f"/management/data-sources/{DS_ID}")

        assert resp.status_code == 403


class TestTriggerSync:
    """Tests for POST /management/data-sources/{ds_id}/sync."""

    @pytest.mark.asyncio
    async def test_triggers_successfully(self, client, mock_service):
        """Test successful sync trigger returns 202."""
        sync_run = _make_sync_run()
        mock_service.trigger_sync.return_value = sync_run

        resp = await client.post(f"/management/data-sources/{DS_ID}/sync")

        assert resp.status_code == 202
        data = resp.json()
        assert data["id"] == "01JTEST0000000000000SYNC01"
        assert data["data_source_id"] == DS_ID
        assert data["status"] == "pending"
        assert data["completed_at"] is None

    @pytest.mark.asyncio
    async def test_unauthorized_returns_403(self, client, mock_service):
        """Test that UnauthorizedError maps to 403."""
        mock_service.trigger_sync.side_effect = UnauthorizedError("denied")

        resp = await client.post(f"/management/data-sources/{DS_ID}/sync")

        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_not_found_returns_404(self, client, mock_service):
        """Test that ValueError maps to 404."""
        mock_service.trigger_sync.side_effect = ValueError("not found")

        resp = await client.post(f"/management/data-sources/{DS_ID}/sync")

        assert resp.status_code == 404
