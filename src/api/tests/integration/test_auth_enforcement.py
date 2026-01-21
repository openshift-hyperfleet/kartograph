"""Integration tests for authentication enforcement.

Verifies that protected endpoints return 401 when unauthenticated,
and that public endpoints remain accessible.
"""

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from main import app

pytestmark = [pytest.mark.integration, pytest.mark.keycloak]


@pytest_asyncio.fixture
async def async_client():
    """Create async HTTP client for testing with lifespan support."""
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


class TestProtectedEndpointsRequireAuth:
    """Verify protected endpoints return 401 without authentication."""

    @pytest.mark.asyncio
    async def test_iam_groups_post_returns_401_without_auth(self, async_client):
        """POST /iam/groups should return 401 without Authorization header."""
        response = await async_client.post(
            "/iam/groups",
            json={"name": "Test Group"},
        )

        assert response.status_code == 401
        assert response.headers.get("WWW-Authenticate") == "Bearer"

    @pytest.mark.asyncio
    async def test_iam_groups_get_returns_401_without_auth(self, async_client):
        """GET /iam/groups/:id should return 401 without Authorization header."""
        response = await async_client.get("/iam/groups/01JTEST00000000000000000")

        assert response.status_code == 401
        assert response.headers.get("WWW-Authenticate") == "Bearer"

    @pytest.mark.asyncio
    async def test_iam_groups_delete_returns_401_without_auth(self, async_client):
        """DELETE /iam/groups/:id should return 401 without Authorization header."""
        response = await async_client.delete("/iam/groups/01JTEST00000000000000000")

        assert response.status_code == 401
        assert response.headers.get("WWW-Authenticate") == "Bearer"

    @pytest.mark.asyncio
    async def test_iam_tenants_post_returns_401_without_auth(self, async_client):
        """POST /iam/tenants should return 401 without Authorization header."""
        response = await async_client.post(
            "/iam/tenants",
            json={"name": "Test Tenant"},
        )

        assert response.status_code == 401
        assert response.headers.get("WWW-Authenticate") == "Bearer"

    @pytest.mark.asyncio
    async def test_iam_tenants_get_returns_401_without_auth(self, async_client):
        """GET /iam/tenants/:id should return 401 without Authorization header."""
        response = await async_client.get("/iam/tenants/01JTEST00000000000000000")

        assert response.status_code == 401
        assert response.headers.get("WWW-Authenticate") == "Bearer"

    @pytest.mark.asyncio
    async def test_iam_tenants_list_returns_401_without_auth(self, async_client):
        """GET /iam/tenants should return 401 without Authorization header."""
        response = await async_client.get("/iam/tenants")

        assert response.status_code == 401
        assert response.headers.get("WWW-Authenticate") == "Bearer"

    @pytest.mark.asyncio
    async def test_graph_mutations_returns_401_without_auth(self, async_client):
        """POST /graph/mutations should return 401 without Authorization header."""
        response = await async_client.post(
            "/graph/mutations",
            content='{"op": "CREATE", "type": "node"}',
            headers={"Content-Type": "application/jsonlines"},
        )

        assert response.status_code == 401
        assert response.headers.get("WWW-Authenticate") == "Bearer"

    @pytest.mark.asyncio
    async def test_graph_nodes_by_slug_returns_401_without_auth(self, async_client):
        """GET /graph/nodes/by-slug should return 401 without Authorization header."""
        response = await async_client.get("/graph/nodes/by-slug?slug=test")

        assert response.status_code == 401
        assert response.headers.get("WWW-Authenticate") == "Bearer"

    @pytest.mark.asyncio
    async def test_graph_schema_nodes_returns_401_without_auth(self, async_client):
        """GET /graph/schema/nodes should return 401 without Authorization header."""
        response = await async_client.get("/graph/schema/nodes")

        assert response.status_code == 401
        assert response.headers.get("WWW-Authenticate") == "Bearer"


class TestPublicEndpointsAccessible:
    """Verify public endpoints remain accessible without authentication."""

    @pytest.mark.asyncio
    async def test_health_endpoint_accessible(self, async_client):
        """GET /health should be accessible without authentication."""
        response = await async_client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    @pytest.mark.asyncio
    async def test_health_db_endpoint_accessible(self, async_client):
        """GET /health/db should be accessible without authentication."""
        response = await async_client.get("/health/db")

        # May return 200 or 503 depending on DB state, but not 401
        assert response.status_code in [200, 503]

    @pytest.mark.asyncio
    async def test_openapi_json_accessible(self, async_client):
        """GET /openapi.json should be accessible without authentication."""
        response = await async_client.get("/openapi.json")

        assert response.status_code == 200
        assert "openapi" in response.json()

    @pytest.mark.asyncio
    async def test_docs_accessible(self, async_client):
        """GET /docs should be accessible without authentication."""
        response = await async_client.get("/docs")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_util_graph_viewer_accessible(self, async_client):
        """GET /util/graph-viewer should be accessible without authentication (dev utility)."""
        response = await async_client.get("/util/graph-viewer")

        assert response.status_code == 200


class TestInvalidTokenReturns401:
    """Verify invalid tokens return 401 with proper headers."""

    @pytest.mark.asyncio
    async def test_invalid_token_returns_401(self, async_client):
        """Invalid JWT should return 401 with WWW-Authenticate header."""
        response = await async_client.get(
            "/iam/tenants",
            headers={"Authorization": "Bearer invalid.token.here"},
        )

        assert response.status_code == 401
        assert response.headers.get("WWW-Authenticate") == "Bearer"

    @pytest.mark.asyncio
    async def test_malformed_auth_header_returns_401(self, async_client):
        """Malformed Authorization header should return 401."""
        response = await async_client.get(
            "/iam/tenants",
            headers={"Authorization": "NotBearer token"},
        )

        # FastAPI's OAuth2 scheme returns 401 for non-Bearer auth
        assert response.status_code == 401
