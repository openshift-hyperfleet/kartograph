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
from management.infrastructure.git_diff_summary_service import DiffSummaryResult
from management.domain.value_objects import (
    DataSourceId,
    Ontology,
    OntologyEdgeType,
    OntologyNodeType,
    Schedule,
    ScheduleType,
)
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
def mock_diff_summary_service() -> AsyncMock:
    """Mock GitDiffSummaryService for diff-summary route testing."""
    return AsyncMock()


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
        clone_head_commit="1111111111111111111111111111111111111111",
        last_extraction_baseline_commit="2222222222222222222222222222222222222222",
        tracked_branch_head_commit="3333333333333333333333333333333333333333",
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
    mock_diff_summary_service: AsyncMock,
    mock_current_user: CurrentUser,
) -> TestClient:
    """Create TestClient with mocked dependencies."""
    from iam.dependencies.user import get_current_user
    from management.dependencies.data_source import (
        get_data_source_service,
        get_git_diff_summary_service,
        get_sync_run_repository,
    )
    from management.presentation import router

    app = FastAPI()

    app.dependency_overrides[get_data_source_service] = lambda: mock_ds_service
    app.dependency_overrides[get_sync_run_repository] = lambda: mock_sync_run_repo
    app.dependency_overrides[get_git_diff_summary_service] = (
        lambda: mock_diff_summary_service
    )
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
        assert result[0]["clone_head_commit"] == sample_data_source.clone_head_commit
        assert (
            result[0]["last_extraction_baseline_commit"]
            == sample_data_source.last_extraction_baseline_commit
        )
        assert (
            result[0]["tracked_branch_head_commit"]
            == sample_data_source.tracked_branch_head_commit
        )

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
            ontology=None,
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
            ontology=None,
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


class TestDataSourceDiffSummaryRoute:
    """Tests for GET /management/data-sources/{ds_id}/diff-summary endpoint."""

    def test_diff_summary_returns_counts_and_changed_files(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
        mock_diff_summary_service: AsyncMock,
        sample_data_source: DataSource,
    ) -> None:
        """Diff summary should include aggregate counts + changed file list."""
        mock_ds_service.get.return_value = sample_data_source
        mock_diff_summary_service.build_summary.return_value = DiffSummaryResult(
            baseline_commit="abc",
            tracked_head_commit="def",
            total_changed_files=2,
            added_count=1,
            modified_count=1,
            removed_count=0,
            renamed_count=0,
            files_truncated=False,
            changed_files=(
                {"path": "src/a.py", "status": "added"},
                {"path": "src/b.py", "status": "modified"},
            ),
        )

        response = test_client.get(
            f"/management/data-sources/{sample_data_source.id.value}/diff-summary"
        )

        assert response.status_code == status.HTTP_200_OK
        payload = response.json()
        assert payload["total_changed_files"] == 2
        assert payload["added_count"] == 1
        assert payload["modified_count"] == 1
        assert payload["files_truncated"] is False
        assert payload["changed_files"][0]["path"] == "src/a.py"

    def test_diff_summary_returns_404_when_data_source_inaccessible(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
        mock_diff_summary_service: AsyncMock,
    ) -> None:
        """Diff summary route should return 404 when DS is not found/authorized."""
        mock_ds_service.get.return_value = None

        response = test_client.get(
            "/management/data-sources/01JPQRST1234567890ABCDEFDS/diff-summary"
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        mock_diff_summary_service.build_summary.assert_not_called()


class TestUpdateDataSourceRoute:
    """Tests for PATCH /management/data-sources/{ds_id} endpoint.

    This endpoint exposes DataSourceService.update() to allow name and
    credential changes without requiring a parent knowledge-graph ID in
    the path (per the API convention: flat retrieval/mutation at DS level).
    """

    def test_update_data_source_returns_200(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
        sample_data_source: DataSource,
    ) -> None:
        """PATCH /management/data-sources/{ds_id} returns 200 with updated DS."""
        updated = DataSource(
            id=sample_data_source.id,
            knowledge_graph_id=sample_data_source.knowledge_graph_id,
            tenant_id=sample_data_source.tenant_id,
            name="Updated Name",
            adapter_type=sample_data_source.adapter_type,
            connection_config=sample_data_source.connection_config,
            credentials_path=sample_data_source.credentials_path,
            schedule=sample_data_source.schedule,
            last_sync_at=sample_data_source.last_sync_at,
            created_at=sample_data_source.created_at,
            updated_at=sample_data_source.updated_at,
        )
        mock_ds_service.update.return_value = updated

        response = test_client.patch(
            f"/management/data-sources/{sample_data_source.id.value}",
            json={"name": "Updated Name"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == sample_data_source.id.value
        assert data["name"] == "Updated Name"

    def test_update_calls_service_with_correct_params(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
        mock_current_user: CurrentUser,
        sample_data_source: DataSource,
    ) -> None:
        """PATCH passes ds_id, user_id, name, and credentials to service."""
        mock_ds_service.update.return_value = sample_data_source
        ds_id = sample_data_source.id.value

        test_client.patch(
            f"/management/data-sources/{ds_id}",
            json={"name": "New Name", "credentials": {"access_token": "tok-abc"}},
        )

        mock_ds_service.update.assert_called_once_with(
            user_id=mock_current_user.user_id.value,
            ds_id=ds_id,
            name="New Name",
            connection_config=None,
            raw_credentials={"access_token": "tok-abc"},
        )

    def test_update_returns_403_when_unauthorized(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
        sample_data_source: DataSource,
    ) -> None:
        """PATCH returns 403 when user lacks EDIT permission on the data source."""
        mock_ds_service.update.side_effect = UnauthorizedError("no permission")

        response = test_client.patch(
            f"/management/data-sources/{sample_data_source.id.value}",
            json={"name": "Updated"},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_returns_404_when_not_found(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
        sample_data_source: DataSource,
    ) -> None:
        """PATCH returns 404 when data source does not exist."""
        mock_ds_service.update.side_effect = ValueError("Data source not found")

        response = test_client.patch(
            f"/management/data-sources/{sample_data_source.id.value}",
            json={"name": "Updated"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_name_only_does_not_require_credentials(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
        mock_current_user: CurrentUser,
        sample_data_source: DataSource,
    ) -> None:
        """PATCH with name only sends None for credentials to the service."""
        mock_ds_service.update.return_value = sample_data_source

        test_client.patch(
            f"/management/data-sources/{sample_data_source.id.value}",
            json={"name": "Renamed"},
        )

        mock_ds_service.update.assert_called_once_with(
            user_id=mock_current_user.user_id.value,
            ds_id=sample_data_source.id.value,
            name="Renamed",
            connection_config=None,
            raw_credentials=None,
        )


class TestDeleteDataSourceRoute:
    """Tests for DELETE /management/data-sources/{ds_id} endpoint.

    This endpoint exposes DataSourceService.delete() at a flat path
    (per API convention: flat mutation at DS level — no KG ID required).
    """

    def test_delete_returns_204_when_deleted(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
        sample_data_source: DataSource,
    ) -> None:
        """DELETE /management/data-sources/{ds_id} returns 204 on success."""
        mock_ds_service.delete.return_value = True

        response = test_client.delete(
            f"/management/data-sources/{sample_data_source.id.value}"
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_delete_calls_service_with_correct_params(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
        mock_current_user: CurrentUser,
        sample_data_source: DataSource,
    ) -> None:
        """DELETE passes ds_id and user_id to the service."""
        mock_ds_service.delete.return_value = True
        ds_id = sample_data_source.id.value

        test_client.delete(f"/management/data-sources/{ds_id}")

        mock_ds_service.delete.assert_called_once_with(
            user_id=mock_current_user.user_id.value,
            ds_id=ds_id,
        )

    def test_delete_returns_403_when_unauthorized(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
        sample_data_source: DataSource,
    ) -> None:
        """DELETE returns 403 when user lacks MANAGE permission."""
        mock_ds_service.delete.side_effect = UnauthorizedError("no permission")

        response = test_client.delete(
            f"/management/data-sources/{sample_data_source.id.value}"
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_returns_404_when_not_found(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
        sample_data_source: DataSource,
    ) -> None:
        """DELETE returns 404 when data source not found."""
        mock_ds_service.delete.return_value = False

        response = test_client.delete(
            f"/management/data-sources/{sample_data_source.id.value}"
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestOntologyInDataSourceRoutes:
    """Tests for ontology field in data source create/update/response."""

    def _make_ds_with_ontology(
        self,
        mock_current_user: "CurrentUser",
        ontology: "Ontology | None",
    ) -> DataSource:
        """Create a sample DataSource with an optional ontology."""
        from datetime import UTC, datetime

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
            ontology=ontology,
            created_at=now,
            updated_at=now,
        )

    def test_response_includes_ontology_when_present(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
        mock_current_user: "CurrentUser",
    ) -> None:
        """DataSourceResponse should include the ontology when set."""
        ontology = Ontology(
            node_types=[
                OntologyNodeType(
                    label="Repository",
                    description="A code repo",
                    required_properties=["url"],
                    optional_properties=["description"],
                )
            ],
            edge_types=[
                OntologyEdgeType(
                    label="HAS_PR",
                    from_type="Repository",
                    to_type="PullRequest",
                )
            ],
        )
        ds = self._make_ds_with_ontology(mock_current_user, ontology=ontology)
        kg_id = ds.knowledge_graph_id
        mock_ds_service.list_for_knowledge_graph.return_value = [ds]

        response = test_client.get(f"/management/knowledge-graphs/{kg_id}/data-sources")

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert len(result) == 1
        assert result[0]["ontology"] is not None
        assert result[0]["ontology"]["node_types"][0]["label"] == "Repository"
        assert result[0]["ontology"]["edge_types"][0]["label"] == "HAS_PR"

    def test_response_includes_null_ontology_when_not_set(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
        mock_current_user: "CurrentUser",
    ) -> None:
        """DataSourceResponse should include ontology=null when not set."""
        ds = self._make_ds_with_ontology(mock_current_user, ontology=None)
        kg_id = ds.knowledge_graph_id
        mock_ds_service.list_for_knowledge_graph.return_value = [ds]

        response = test_client.get(f"/management/knowledge-graphs/{kg_id}/data-sources")

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result[0]["ontology"] is None

    def test_create_with_ontology_passes_ontology_to_service(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
        mock_current_user: "CurrentUser",
    ) -> None:
        """POST /data-sources with ontology should call service.create() with ontology."""
        ds = self._make_ds_with_ontology(mock_current_user, ontology=None)
        mock_ds_service.create.return_value = ds

        kg_id = "01JPQRST1234567890ABCDEFKG"
        response = test_client.post(
            f"/management/knowledge-graphs/{kg_id}/data-sources",
            json={
                "name": "My Data Source",
                "adapter_type": "github",
                "connection_config": {"repo": "org/repo"},
                "ontology": {
                    "node_types": [
                        {
                            "label": "Repository",
                            "description": None,
                            "required_properties": [],
                            "optional_properties": [],
                        }
                    ],
                    "edge_types": [],
                },
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        # Verify the service was called with an ontology kwarg
        call_kwargs = mock_ds_service.create.call_args.kwargs
        assert "ontology" in call_kwargs
        assert call_kwargs["ontology"] is not None

    def test_update_with_ontology_calls_update_ontology_on_service(
        self,
        test_client: TestClient,
        mock_ds_service: AsyncMock,
        mock_current_user: "CurrentUser",
    ) -> None:
        """PATCH /data-sources/{id} with ontology calls service.update_ontology()."""
        ds = self._make_ds_with_ontology(mock_current_user, ontology=None)
        mock_ds_service.update.return_value = ds
        mock_ds_service.update_ontology.return_value = ds

        ds_id = ds.id.value
        response = test_client.patch(
            f"/management/data-sources/{ds_id}",
            json={
                "ontology": {
                    "node_types": [
                        {
                            "label": "Issue",
                            "description": "A GitHub issue",
                            "required_properties": ["title"],
                            "optional_properties": [],
                        }
                    ],
                    "edge_types": [],
                }
            },
        )

        assert response.status_code == status.HTTP_200_OK
        mock_ds_service.update_ontology.assert_called_once()
        call_kwargs = mock_ds_service.update_ontology.call_args.kwargs
        assert call_kwargs["ds_id"] == ds_id
        assert call_kwargs["user_id"] == mock_current_user.user_id.value
