"""Integration tests for the Ingestion API sync job endpoints.

Coverage:
1. POST /ingestion/sync-jobs — create a SyncJob, verify 202 + PENDING status
2. GET /ingestion/sync-jobs — list jobs (empty when none exist)
3. GET /ingestion/sync-jobs?status=pending — filter by status
4. GET /ingestion/sync-jobs?data_source_id=... — filter by data source
5. GET /ingestion/sync-jobs/{job_id} — retrieve a specific job
6. GET /ingestion/sync-jobs/{job_id} — 404 for non-existent job
7. POST /ingestion/sync-jobs — 422 for missing required fields
"""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


class TestTriggerSync:
    """Tests for POST /ingestion/sync-jobs."""

    @pytest.mark.asyncio
    async def test_creates_sync_job_returns_202(
        self,
        async_client: AsyncClient,
        clean_sync_jobs,
    ) -> None:
        """POST creates a SyncJob in PENDING state and returns 202."""
        response = await async_client.post(
            "/ingestion/sync-jobs",
            json={
                "data_source_id": "ds-abc123",
                "tenant_id": "tenant-xyz",
            },
        )

        assert response.status_code == 202
        body = response.json()
        assert body["data_source_id"] == "ds-abc123"
        assert body["tenant_id"] == "tenant-xyz"
        assert body["status"] == "pending"
        assert body["id"] is not None
        assert body["created_at"] is not None
        assert body["started_at"] is None
        assert body["completed_at"] is None
        assert body["error"] is None

    @pytest.mark.asyncio
    async def test_creates_sync_job_with_knowledge_graph(
        self,
        async_client: AsyncClient,
        clean_sync_jobs,
    ) -> None:
        """POST creates a SyncJob with optional knowledge_graph_id."""
        response = await async_client.post(
            "/ingestion/sync-jobs",
            json={
                "data_source_id": "ds-abc123",
                "tenant_id": "tenant-xyz",
                "knowledge_graph_id": "kg-789",
            },
        )

        assert response.status_code == 202
        body = response.json()
        assert body["knowledge_graph_id"] == "kg-789"
        assert body["status"] == "pending"

    @pytest.mark.asyncio
    async def test_missing_data_source_id_returns_422(
        self,
        async_client: AsyncClient,
    ) -> None:
        """POST without data_source_id returns 422 Unprocessable Entity."""
        response = await async_client.post(
            "/ingestion/sync-jobs",
            json={"tenant_id": "tenant-xyz"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_tenant_id_returns_422(
        self,
        async_client: AsyncClient,
    ) -> None:
        """POST without tenant_id returns 422 Unprocessable Entity."""
        response = await async_client.post(
            "/ingestion/sync-jobs",
            json={"data_source_id": "ds-abc123"},
        )
        assert response.status_code == 422


class TestListSyncJobs:
    """Tests for GET /ingestion/sync-jobs."""

    @pytest.mark.asyncio
    async def test_empty_list_when_no_jobs(
        self,
        async_client: AsyncClient,
        clean_sync_jobs,
    ) -> None:
        """GET returns empty list when no sync jobs exist."""
        response = await async_client.get("/ingestion/sync-jobs")

        assert response.status_code == 200
        body = response.json()
        assert body["sync_jobs"] == []
        assert body["total"] == 0

    @pytest.mark.asyncio
    async def test_lists_all_sync_jobs(
        self,
        async_client: AsyncClient,
        clean_sync_jobs,
    ) -> None:
        """GET returns all sync jobs."""
        # Create two jobs
        await async_client.post(
            "/ingestion/sync-jobs",
            json={"data_source_id": "ds-1", "tenant_id": "tenant-a"},
        )
        await async_client.post(
            "/ingestion/sync-jobs",
            json={"data_source_id": "ds-2", "tenant_id": "tenant-a"},
        )

        response = await async_client.get("/ingestion/sync-jobs")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 2
        assert len(body["sync_jobs"]) == 2

    @pytest.mark.asyncio
    async def test_filter_by_status(
        self,
        async_client: AsyncClient,
        clean_sync_jobs,
    ) -> None:
        """GET ?status=pending returns only PENDING jobs."""
        await async_client.post(
            "/ingestion/sync-jobs",
            json={"data_source_id": "ds-1", "tenant_id": "tenant-a"},
        )

        response = await async_client.get("/ingestion/sync-jobs?status=pending")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["sync_jobs"][0]["status"] == "pending"

    @pytest.mark.asyncio
    async def test_filter_by_data_source_id(
        self,
        async_client: AsyncClient,
        clean_sync_jobs,
    ) -> None:
        """GET ?data_source_id=... returns jobs for that data source only."""
        await async_client.post(
            "/ingestion/sync-jobs",
            json={"data_source_id": "ds-target", "tenant_id": "tenant-a"},
        )
        await async_client.post(
            "/ingestion/sync-jobs",
            json={"data_source_id": "ds-other", "tenant_id": "tenant-a"},
        )

        response = await async_client.get(
            "/ingestion/sync-jobs?data_source_id=ds-target"
        )

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["sync_jobs"][0]["data_source_id"] == "ds-target"

    @pytest.mark.asyncio
    async def test_filter_by_tenant_id(
        self,
        async_client: AsyncClient,
        clean_sync_jobs,
    ) -> None:
        """GET ?tenant_id=... returns jobs for that tenant only."""
        await async_client.post(
            "/ingestion/sync-jobs",
            json={"data_source_id": "ds-1", "tenant_id": "tenant-a"},
        )
        await async_client.post(
            "/ingestion/sync-jobs",
            json={"data_source_id": "ds-2", "tenant_id": "tenant-b"},
        )

        response = await async_client.get("/ingestion/sync-jobs?tenant_id=tenant-a")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["sync_jobs"][0]["tenant_id"] == "tenant-a"


class TestGetSyncJobById:
    """Tests for GET /ingestion/sync-jobs/{job_id}."""

    @pytest.mark.asyncio
    async def test_returns_job_by_id(
        self,
        async_client: AsyncClient,
        clean_sync_jobs,
    ) -> None:
        """GET /{job_id} returns the correct sync job."""
        create_resp = await async_client.post(
            "/ingestion/sync-jobs",
            json={"data_source_id": "ds-abc", "tenant_id": "tenant-xyz"},
        )
        assert create_resp.status_code == 202
        job_id = create_resp.json()["id"]

        get_resp = await async_client.get(f"/ingestion/sync-jobs/{job_id}")

        assert get_resp.status_code == 200
        body = get_resp.json()
        assert body["id"] == job_id
        assert body["data_source_id"] == "ds-abc"
        assert body["tenant_id"] == "tenant-xyz"
        assert body["status"] == "pending"

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_job(
        self,
        async_client: AsyncClient,
    ) -> None:
        """GET /{job_id} returns 404 when job does not exist."""
        response = await async_client.get("/ingestion/sync-jobs/nonexistent-id-12345")

        assert response.status_code == 404
        body = response.json()
        assert "not found" in body["detail"].lower()
