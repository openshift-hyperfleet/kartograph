"""Unit tests for Data Source HTTP routes.

Tests the Management presentation layer for data source endpoints
following the patterns established in tests/unit/iam/presentation/.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from iam.application.value_objects import CurrentUser
from iam.domain.value_objects import TenantId, UserId
from management.application.services.data_source_service import DataSourceService
from management.domain.aggregates import DataSource
from management.domain.entities import DataSourceSyncRun
from management.domain.value_objects import DataSourceId, Schedule, ScheduleType
from management.ports.exceptions import UnauthorizedError
from management.ports.repositories import IDataSourceSyncRunRepository
from shared_kernel.datasource_types import DataSourceAdapterType


@pytest.fixture
def mock_ds_service() -> AsyncMock:
    """Mock DataSourceService for testing."""
    return AsyncMock(spec=DataSourceService)


@pytest.fixture
def mock_sync_run_repo() -> AsyncMock:
    """Mock DataSourceSyncRunRepository for testing."""
    return AsyncMock(spec=IDataSourceSyncRunRepository)


@pytest.fixture
def mock_current_user() -> CurrentUser:
    """Mock CurrentUser for authentication."""
    return CurrentUser(
        user_id=UserId(value="01JPQRST1234567890ABCDEFGH"),
        username="testuser",
        tenant_id=TenantId(value="01JPQRST1234567890ABCDEFAB"),
    )


@pytest.fixture
def sample_data_source(mock_current_user: CurrentUser) -> DataSource:
    """Create a sample DataSource for testing."""
    now = datetime.now(UTC)
    return DataSource(
        id=DataSourceId(value="01JPQRST1234567890ABCDEFDS"),
        knowledge_graph_id="01JPQRST1234567890ABCDEFKG",
        tenant_id=mock_current_user.tenant_id.value,
        name="My Data Source",
        adapter_type=DataSourceAdapterType.GITHUB,
        connection_config={"repo": "org/repo"},
        credentials_path=None,
        schedule=Schedule(schedule_type=ScheduleType.MANUAL),
        last_sync_at=None,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def sample_sync_run(sample_data_source: DataSource) -> DataSourceSyncRun:
    """Create a sample DataSourceSyncRun for testing."""
    now = datetime.now(UTC)
    return DataSourceSyncRun(
        id="01JPQRST1234567890ABCDEFSR",
        data_source_id=sample_data_source.id.value,
        status="pending",
        started_at=now,
        completed_at=None,
        error=None,
        created_at=now,
    )


@pytest.fixture
def test_client(
    mock_ds_service: AsyncMock,
    mock_sync_run_repo: AsyncMock,
    mock_current_user: CurrentUser,
) -> TestClient:
    """Create TestClient with mocked dependencies."""
    from iam.dependencies.user import get_current_user
    from management.dependencies.data_source import (
        get_data_source_service,
        get_sync_run_repository,
    )
    from management.presentation import router

    app = FastAPI()

    app.dependency_overrides[get_data_source_service] = lambda: mock_ds_service
    app.dependency_overrides[get_sync_run_repository] = lambda: mock_sync_run_repo
    app.dependency_overrides[get_current_user] = lambda: mock_current_user

    app.include_router(router)

    return TestClient(app)


class TestListDataSourcesRoute:
    """Tests for GET /management/knowledge-graphs/{kg_id}/data-sources endpoint."""

    def test_list_data_sources_returns_200(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
        sample_data_source: DataSource,
    ) -> None:
        """Should return 200 with list of data sources."""
        mock_ds_service.list_for_knowledge_graph.return_value = [sample_data_source]

        response = test_client.get(
            f"/management/knowledge-graphs/{sample_data_source.knowledge_graph_id}/data-sources"
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert len(result) == 1
        assert result[0]["id"] == sample_data_source.id.value
        assert result[0]["name"] == sample_data_source.name
        assert result[0]["adapter_type"] == sample_data_source.adapter_type.value

    def test_list_data_sources_returns_empty_list(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
    ) -> None:
        """Should return 200 with empty list when no data sources exist."""
        mock_ds_service.list_for_knowledge_graph.return_value = []

        response = test_client.get(
            "/management/knowledge-graphs/01JPQRST1234567890ABCDEFKG/data-sources"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_list_data_sources_calls_service_with_correct_params(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
        mock_current_user: CurrentUser,
    ) -> None:
        """Should call the service with the current user ID and KG ID."""
        mock_ds_service.list_for_knowledge_graph.return_value = []
        kg_id = "01JPQRST1234567890ABCDEFKG"

        test_client.get(f"/management/knowledge-graphs/{kg_id}/data-sources")

        mock_ds_service.list_for_knowledge_graph.assert_called_once_with(
            user_id=mock_current_user.user_id.value,
            kg_id=kg_id,
        )


class TestCreateDataSourceRoute:
    """Tests for POST /management/knowledge-graphs/{kg_id}/data-sources endpoint."""

    def test_create_data_source_returns_201(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
        sample_data_source: DataSource,
    ) -> None:
        """Should create data source and return 201 with DS details."""
        mock_ds_service.create.return_value = sample_data_source

        response = test_client.post(
            f"/management/knowledge-graphs/{sample_data_source.knowledge_graph_id}/data-sources",
            json={
                "name": "My Data Source",
                "adapter_type": "github",
                "connection_config": {"repo": "org/repo"},
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        result = response.json()
        assert result["id"] == sample_data_source.id.value
        assert result["name"] == sample_data_source.name
        assert result["adapter_type"] == sample_data_source.adapter_type.value

    def test_create_data_source_calls_service_correctly(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
        sample_data_source: DataSource,
        mock_current_user: CurrentUser,
    ) -> None:
        """Should call the service with correct parameters."""
        mock_ds_service.create.return_value = sample_data_source
        kg_id = "01JPQRST1234567890ABCDEFKG"

        test_client.post(
            f"/management/knowledge-graphs/{kg_id}/data-sources",
            json={
                "name": "My Data Source",
                "adapter_type": "github",
                "connection_config": {"repo": "org/repo"},
            },
        )

        mock_ds_service.create.assert_called_once_with(
            user_id=mock_current_user.user_id.value,
            kg_id=kg_id,
            name="My Data Source",
            adapter_type=DataSourceAdapterType("github"),
            connection_config={"repo": "org/repo"},
            raw_credentials=None,
        )

    def test_create_data_source_with_credentials(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
        sample_data_source: DataSource,
        mock_current_user: CurrentUser,
    ) -> None:
        """Should pass credentials to service when provided."""
        mock_ds_service.create.return_value = sample_data_source
        kg_id = "01JPQRST1234567890ABCDEFKG"

        test_client.post(
            f"/management/knowledge-graphs/{kg_id}/data-sources",
            json={
                "name": "My Data Source",
                "adapter_type": "github",
                "connection_config": {"repo": "org/repo"},
                "credentials": {"token": "ghp_secret"},  # gitleaks:allow
            },
        )

        mock_ds_service.create.assert_called_once_with(
            user_id=mock_current_user.user_id.value,
            kg_id=kg_id,
            name="My Data Source",
            adapter_type=DataSourceAdapterType("github"),
            connection_config={"repo": "org/repo"},
            raw_credentials={"token": "ghp_secret"},  # gitleaks:allow
        )

    def test_create_data_source_returns_403_when_unauthorized(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
    ) -> None:
        """Should return 403 when service raises UnauthorizedError."""
        mock_ds_service.create.side_effect = UnauthorizedError(
            "User lacks edit permission on knowledge graph"
        )

        response = test_client.post(
            "/management/knowledge-graphs/01JPQRST1234567890ABCDEFKG/data-sources",
            json={
                "name": "My Data Source",
                "adapter_type": "github",
                "connection_config": {},
            },
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "permission" in response.json()["detail"].lower()

    def test_create_data_source_requires_name(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
    ) -> None:
        """Should return 422 when name field is missing."""
        response = test_client.post(
            "/management/knowledge-graphs/01JPQRST1234567890ABCDEFKG/data-sources",
            json={
                "adapter_type": "github",
                "connection_config": {},
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_data_source_requires_adapter_type(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
    ) -> None:
        """Should return 422 when adapter_type field is missing."""
        response = test_client.post(
            "/management/knowledge-graphs/01JPQRST1234567890ABCDEFKG/data-sources",
            json={
                "name": "My Data Source",
                "connection_config": {},
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestTriggerSyncRoute:
    """Tests for POST /management/data-sources/{ds_id}/sync endpoint."""

    def test_trigger_sync_returns_201_with_sync_run(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
        sample_data_source: DataSource,
        sample_sync_run: DataSourceSyncRun,
    ) -> None:
        """Should trigger sync and return 201 with sync run details."""
        mock_ds_service.trigger_sync.return_value = sample_sync_run

        response = test_client.post(
            f"/management/data-sources/{sample_data_source.id.value}/sync"
        )

        assert response.status_code == status.HTTP_201_CREATED
        result = response.json()
        assert result["id"] == sample_sync_run.id
        assert result["data_source_id"] == sample_sync_run.data_source_id
        assert result["status"] == sample_sync_run.status

    def test_trigger_sync_calls_service_with_correct_params(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
        sample_data_source: DataSource,
        sample_sync_run: DataSourceSyncRun,
        mock_current_user: CurrentUser,
    ) -> None:
        """Should call service with the current user ID and DS ID."""
        mock_ds_service.trigger_sync.return_value = sample_sync_run

        test_client.post(f"/management/data-sources/{sample_data_source.id.value}/sync")

        mock_ds_service.trigger_sync.assert_called_once_with(
            user_id=mock_current_user.user_id.value,
            ds_id=sample_data_source.id.value,
        )

    def test_trigger_sync_returns_403_when_unauthorized(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
        sample_data_source: DataSource,
    ) -> None:
        """Should return 403 when service raises UnauthorizedError."""
        mock_ds_service.trigger_sync.side_effect = UnauthorizedError(
            "User lacks manage permission on data source"
        )

        response = test_client.post(
            f"/management/data-sources/{sample_data_source.id.value}/sync"
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "permission" in response.json()["detail"].lower()


class TestListSyncRunsRoute:
    """Tests for GET /management/data-sources/{ds_id}/sync-runs endpoint."""

    def test_list_sync_runs_returns_200(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
        mock_sync_run_repo: AsyncMock,
        sample_data_source: DataSource,
        sample_sync_run: DataSourceSyncRun,
    ) -> None:
        """Should return 200 with sync run history."""
        mock_ds_service.get.return_value = sample_data_source
        mock_sync_run_repo.find_by_data_source.return_value = [sample_sync_run]

        response = test_client.get(
            f"/management/data-sources/{sample_data_source.id.value}/sync-runs"
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert len(result) == 1
        assert result[0]["id"] == sample_sync_run.id
        assert result[0]["status"] == sample_sync_run.status

    def test_list_sync_runs_returns_empty_list(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
        mock_sync_run_repo: AsyncMock,
        sample_data_source: DataSource,
    ) -> None:
        """Should return 200 with empty list when no sync runs exist."""
        mock_ds_service.get.return_value = sample_data_source
        mock_sync_run_repo.find_by_data_source.return_value = []

        response = test_client.get(
            f"/management/data-sources/{sample_data_source.id.value}/sync-runs"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_list_sync_runs_returns_404_when_ds_not_found(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
        mock_sync_run_repo: AsyncMock,
    ) -> None:
        """Should return 404 when data source is not found (service returns None)."""
        mock_ds_service.get.return_value = None

        response = test_client.get(
            "/management/data-sources/01JPQRST1234567890ABCDEFDS/sync-runs"
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        mock_sync_run_repo.find_by_data_source.assert_not_called()
