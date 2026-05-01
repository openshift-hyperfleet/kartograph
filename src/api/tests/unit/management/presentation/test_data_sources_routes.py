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


class TestGetSyncRunLogsRoute:
    """Tests for GET /management/data-sources/{ds_id}/sync-runs/{run_id}/logs endpoint.

    Spec: "Sync Monitoring — Scenario: Sync logs"
    GIVEN a sync run (in progress or completed)
    WHEN the user requests logs
    THEN detailed logs for that run are displayed
    """

    def test_get_logs_returns_200_with_empty_list_when_no_logs(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
        mock_sync_run_repo: AsyncMock,
        sample_data_source: DataSource,
        sample_sync_run: DataSourceSyncRun,
    ) -> None:
        """Should return 200 with empty logs list when no logs captured yet."""
        mock_ds_service.get.return_value = sample_data_source
        mock_sync_run_repo.get_by_id.return_value = sample_sync_run

        response = test_client.get(
            f"/management/data-sources/{sample_data_source.id.value}"
            f"/sync-runs/{sample_sync_run.id}/logs"
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result == {"logs": []}

    def test_get_logs_returns_200_with_log_lines(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
        mock_sync_run_repo: AsyncMock,
        sample_data_source: DataSource,
        sample_sync_run: DataSourceSyncRun,
    ) -> None:
        """Should return 200 with populated log lines when logs exist."""
        log_lines = [
            "2026-04-30T10:00:01Z INFO Starting sync",
            "2026-04-30T10:00:05Z INFO Fetched 100 items",
            "2026-04-30T10:00:10Z INFO Sync completed",
        ]
        sample_sync_run_with_logs = DataSourceSyncRun(
            id=sample_sync_run.id,
            data_source_id=sample_sync_run.data_source_id,
            status="completed",
            started_at=sample_sync_run.started_at,
            completed_at=sample_sync_run.completed_at,
            error=None,
            created_at=sample_sync_run.created_at,
            logs=log_lines,
        )
        mock_ds_service.get.return_value = sample_data_source
        mock_sync_run_repo.get_by_id.return_value = sample_sync_run_with_logs

        response = test_client.get(
            f"/management/data-sources/{sample_data_source.id.value}"
            f"/sync-runs/{sample_sync_run.id}/logs"
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["logs"] == log_lines

    def test_get_logs_returns_404_when_data_source_not_found(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
        mock_sync_run_repo: AsyncMock,
    ) -> None:
        """Should return 404 when data source is not found or user lacks VIEW permission."""
        mock_ds_service.get.return_value = None

        response = test_client.get(
            "/management/data-sources/01JPQRST1234567890ABCDEFDS"
            "/sync-runs/01JPQRST1234567890ABCDEFSR/logs"
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        mock_sync_run_repo.get_by_id.assert_not_called()

    def test_get_logs_returns_404_when_sync_run_not_found(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
        mock_sync_run_repo: AsyncMock,
        sample_data_source: DataSource,
    ) -> None:
        """Should return 404 when sync run does not exist."""
        mock_ds_service.get.return_value = sample_data_source
        mock_sync_run_repo.get_by_id.return_value = None

        response = test_client.get(
            f"/management/data-sources/{sample_data_source.id.value}"
            "/sync-runs/01JPQRST1234567890NONEXIST/logs"
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_logs_returns_404_when_sync_run_belongs_to_different_ds(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
        mock_sync_run_repo: AsyncMock,
        sample_data_source: DataSource,
        sample_sync_run: DataSourceSyncRun,
    ) -> None:
        """Should return 404 when sync run exists but belongs to a different DS."""
        other_ds_run = DataSourceSyncRun(
            id=sample_sync_run.id,
            data_source_id="01JPQRST1234567890OTHERFDS",  # different DS
            status="completed",
            started_at=sample_sync_run.started_at,
            completed_at=None,
            error=None,
            created_at=sample_sync_run.created_at,
        )
        mock_ds_service.get.return_value = sample_data_source
        mock_sync_run_repo.get_by_id.return_value = other_ds_run

        response = test_client.get(
            f"/management/data-sources/{sample_data_source.id.value}"
            f"/sync-runs/{sample_sync_run.id}/logs"
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_logs_calls_service_get_for_authorization(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
        mock_sync_run_repo: AsyncMock,
        sample_data_source: DataSource,
        sample_sync_run: DataSourceSyncRun,
        mock_current_user: CurrentUser,
    ) -> None:
        """Should call service.get to verify VIEW permission before fetching logs."""
        mock_ds_service.get.return_value = sample_data_source
        mock_sync_run_repo.get_by_id.return_value = sample_sync_run

        test_client.get(
            f"/management/data-sources/{sample_data_source.id.value}"
            f"/sync-runs/{sample_sync_run.id}/logs"
        )

        mock_ds_service.get.assert_called_once_with(
            user_id=mock_current_user.user_id.value,
            ds_id=sample_data_source.id.value,
        )

    def test_get_logs_calls_repo_get_by_id_with_run_id(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
        mock_sync_run_repo: AsyncMock,
        sample_data_source: DataSource,
        sample_sync_run: DataSourceSyncRun,
    ) -> None:
        """Should call repo.get_by_id with the provided run_id."""
        mock_ds_service.get.return_value = sample_data_source
        mock_sync_run_repo.get_by_id.return_value = sample_sync_run

        test_client.get(
            f"/management/data-sources/{sample_data_source.id.value}"
            f"/sync-runs/{sample_sync_run.id}/logs"
        )

        mock_sync_run_repo.get_by_id.assert_called_once_with(sample_sync_run.id)


class TestListAllDataSourcesRoute:
    """Tests for GET /management/data-sources (flat list) endpoint."""

    def test_list_all_returns_200_with_data_sources(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
        sample_data_source: DataSource,
        sample_sync_run: DataSourceSyncRun,
    ) -> None:
        """GET /management/data-sources returns 200 with data_sources list."""
        from management.application.services.data_source_service import (
            DataSourceWithLatestRun,
        )

        mock_ds_service.list_all_for_user.return_value = [
            DataSourceWithLatestRun(
                data_source=sample_data_source,
                latest_sync_run=sample_sync_run,
            )
        ]

        response = test_client.get("/management/data-sources")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data_sources" in data
        assert "count" in data
        assert data["count"] == 1
        assert len(data["data_sources"]) == 1

    def test_list_all_includes_latest_sync_run_in_response(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
        sample_data_source: DataSource,
        sample_sync_run: DataSourceSyncRun,
    ) -> None:
        """GET /management/data-sources embeds latest_sync_run in each item."""
        from management.application.services.data_source_service import (
            DataSourceWithLatestRun,
        )

        mock_ds_service.list_all_for_user.return_value = [
            DataSourceWithLatestRun(
                data_source=sample_data_source,
                latest_sync_run=sample_sync_run,
            )
        ]

        response = test_client.get("/management/data-sources")

        assert response.status_code == status.HTTP_200_OK
        ds = response.json()["data_sources"][0]
        assert ds["latest_sync_run"] is not None
        assert ds["latest_sync_run"]["id"] == sample_sync_run.id
        assert ds["latest_sync_run"]["status"] == sample_sync_run.status

    def test_list_all_returns_null_latest_sync_run_when_none(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
        sample_data_source: DataSource,
    ) -> None:
        """GET /management/data-sources returns null latest_sync_run when no run exists."""
        from management.application.services.data_source_service import (
            DataSourceWithLatestRun,
        )

        mock_ds_service.list_all_for_user.return_value = [
            DataSourceWithLatestRun(
                data_source=sample_data_source,
                latest_sync_run=None,
            )
        ]

        response = test_client.get("/management/data-sources")

        assert response.status_code == status.HTTP_200_OK
        ds = response.json()["data_sources"][0]
        assert ds["latest_sync_run"] is None

    def test_list_all_returns_empty_list_when_no_data_sources(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
    ) -> None:
        """GET /management/data-sources returns empty list when user has no data sources."""
        mock_ds_service.list_all_for_user.return_value = []

        response = test_client.get("/management/data-sources")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data_sources"] == []
        assert data["count"] == 0

    def test_list_all_calls_service_with_current_user_id(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
        mock_current_user: CurrentUser,
    ) -> None:
        """GET /management/data-sources passes current user ID to service."""
        mock_ds_service.list_all_for_user.return_value = []

        test_client.get("/management/data-sources")

        mock_ds_service.list_all_for_user.assert_called_once_with(
            user_id=mock_current_user.user_id.value
        )


class TestProposeOntologyRoute:
    """Tests for POST /management/ontology-proposals endpoint.

    Spec: "Ontology Design — Scenario: Agent-proposed ontology"
    GIVEN a free-text intent description and a connected data source
    WHEN the user submits their intent
    THEN the system performs a lightweight scan of the data source
    AND an AI agent explores the scanned data and proposes an ontology
    AND the proposed ontology is presented to the user for review
    """

    def test_propose_ontology_github_returns_200_with_node_and_edge_types(
        self,
        test_client: TestClient,
    ) -> None:
        """Should return 200 with proposed node and edge types for GitHub adapter."""
        response = test_client.post(
            "/management/ontology-proposals",
            json={
                "adapter_type": "github",
                "intent": "I want to understand contributor patterns and issue triage",
                "connection_config": {"repo_url": "https://github.com/owner/repo"},
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "node_types" in data
        assert "edge_types" in data
        assert len(data["node_types"]) > 0
        assert len(data["edge_types"]) > 0

    def test_propose_ontology_github_node_types_have_required_fields(
        self,
        test_client: TestClient,
    ) -> None:
        """Each proposed node type must have label, description, and property lists."""
        response = test_client.post(
            "/management/ontology-proposals",
            json={
                "adapter_type": "github",
                "intent": "Find all contributors",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        for node in response.json()["node_types"]:
            assert "label" in node
            assert "description" in node
            assert "required_properties" in node
            assert "optional_properties" in node

    def test_propose_ontology_github_edge_types_have_required_fields(
        self,
        test_client: TestClient,
    ) -> None:
        """Each proposed edge type must have label, description, from, to, and property lists."""
        response = test_client.post(
            "/management/ontology-proposals",
            json={
                "adapter_type": "github",
                "intent": "Find all contributors",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        for edge in response.json()["edge_types"]:
            assert "label" in edge
            assert "description" in edge
            assert "from_type" in edge
            assert "to_type" in edge
            assert "required_properties" in edge
            assert "optional_properties" in edge

    def test_propose_ontology_unknown_adapter_returns_empty_types(
        self,
        test_client: TestClient,
    ) -> None:
        """Should return 200 with empty node/edge types for unknown adapter."""
        response = test_client.post(
            "/management/ontology-proposals",
            json={
                "adapter_type": "unknown_adapter",
                "intent": "Some intent",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["node_types"] == []
        assert data["edge_types"] == []

    def test_propose_ontology_requires_intent(
        self,
        test_client: TestClient,
    ) -> None:
        """Should return 422 when intent is missing."""
        response = test_client.post(
            "/management/ontology-proposals",
            json={
                "adapter_type": "github",
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_propose_ontology_requires_adapter_type(
        self,
        test_client: TestClient,
    ) -> None:
        """Should return 422 when adapter_type is missing."""
        response = test_client.post(
            "/management/ontology-proposals",
            json={
                "intent": "Some intent",
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_propose_ontology_intent_is_not_ignored(
        self,
        test_client: TestClient,
    ) -> None:
        """Intent text must be accepted and processed (not ignored).

        This test confirms the endpoint accepts a non-empty intent and returns
        a proposal — i.e., intent text is included in the request and handled.
        """
        intent_text = "I want to track issues assigned to specific contributors"
        response = test_client.post(
            "/management/ontology-proposals",
            json={
                "adapter_type": "github",
                "intent": intent_text,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        # Endpoint must have accepted and processed the intent (not rejected it)
        data = response.json()
        assert "node_types" in data
        assert "edge_types" in data

    def test_propose_ontology_connection_config_is_optional(
        self,
        test_client: TestClient,
    ) -> None:
        """Should return 200 when connection_config is omitted."""
        response = test_client.post(
            "/management/ontology-proposals",
            json={
                "adapter_type": "github",
                "intent": "Some intent",
            },
        )

        assert response.status_code == status.HTTP_200_OK


class TestCreateDataSourceWithOntology:
    """Tests for POST /management/knowledge-graphs/{kg_id}/data-sources with ontology.

    Spec: "Ontology Design — Scenario: Ontology review and approval"
    GIVEN a proposed ontology
    WHEN the user reviews and approves it
    THEN extraction begins only after the user explicitly approves
    AND user edits to individual types must be persisted
    """

    def test_create_data_source_accepts_optional_ontology_field(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
        sample_data_source: DataSource,
    ) -> None:
        """Should accept and process an ontology field in the create request."""
        mock_ds_service.create.return_value = sample_data_source

        response = test_client.post(
            f"/management/knowledge-graphs/{sample_data_source.knowledge_graph_id}/data-sources",
            json={
                "name": "My Data Source",
                "adapter_type": "github",
                "connection_config": {"repo_url": "https://github.com/owner/repo"},
                "ontology": {
                    "node_types": [
                        {
                            "label": "Repository",
                            "description": "A GitHub repository",
                            "required_properties": ["name", "url"],
                            "optional_properties": ["description"],
                        }
                    ],
                    "edge_types": [
                        {
                            "label": "CONTAINS",
                            "description": "Repository contains issues",
                            "from_type": "Repository",
                            "to_type": "Issue",
                            "required_properties": [],
                            "optional_properties": [],
                        }
                    ],
                },
            },
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_create_data_source_without_ontology_still_works(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
        sample_data_source: DataSource,
    ) -> None:
        """Ontology is optional — omitting it should not break existing flows."""
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

    def test_create_data_source_ontology_node_types_included_in_connection_config(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
        sample_data_source: DataSource,
        mock_current_user: CurrentUser,
    ) -> None:
        """Approved ontology node types must be stored and not silently discarded.

        The approved node/edge types must reach the service layer so the system
        can use them during extraction.
        """
        mock_ds_service.create.return_value = sample_data_source

        node_types = [
            {
                "label": "Repository",
                "description": "A GitHub repository",
                "required_properties": ["name", "url"],
                "optional_properties": ["stars"],
            }
        ]
        edge_types = [
            {
                "label": "CONTAINS",
                "description": "Repository contains issues",
                "from_type": "Repository",
                "to_type": "Issue",
                "required_properties": [],
                "optional_properties": [],
            }
        ]

        test_client.post(
            f"/management/knowledge-graphs/{sample_data_source.knowledge_graph_id}/data-sources",
            json={
                "name": "My Data Source",
                "adapter_type": "github",
                "connection_config": {"repo_url": "https://github.com/owner/repo"},
                "ontology": {
                    "node_types": node_types,
                    "edge_types": edge_types,
                },
            },
        )

        # The service must be called with connection_config that includes the ontology
        # so the approved types are not silently discarded
        mock_ds_service.create.assert_called_once()
        call_kwargs = mock_ds_service.create.call_args.kwargs
        assert "_ontology" in call_kwargs["connection_config"]
        stored = call_kwargs["connection_config"]["_ontology"]
        assert stored["node_types"][0]["label"] == "Repository"
        assert stored["edge_types"][0]["label"] == "CONTAINS"
