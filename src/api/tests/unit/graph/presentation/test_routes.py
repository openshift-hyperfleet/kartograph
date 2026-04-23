"""Unit tests for Graph HTTP routes."""

from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from graph.domain.value_objects import (
    EdgeRecord,
    MutationResult,
    NodeRecord,
)
from iam.application.value_objects import CurrentUser
from iam.domain.value_objects import TenantId, UserId


@pytest.fixture
def mock_enclave_service():
    """Mock GraphSecureEnclaveService for testing (async methods)."""
    return AsyncMock()


@pytest.fixture
def mock_mutation_service():
    """Mock GraphMutationService for testing."""
    return Mock()


@pytest.fixture
def mock_current_user():
    """Mock CurrentUser for authentication."""
    return CurrentUser(
        user_id=UserId(value="test-user-123"),
        username="testuser",
        tenant_id=TenantId(value="t1"),
    )


@pytest.fixture
def mock_authz_allowed():
    """Mock AuthorizationProvider that allows all permission checks."""
    authz = AsyncMock()
    authz.check_permission.return_value = True
    return authz


@pytest.fixture
def mock_authz_denied():
    """Mock AuthorizationProvider that denies all permission checks."""
    authz = AsyncMock()
    authz.check_permission.return_value = False
    return authz


@pytest.fixture
def test_client(
    mock_enclave_service, mock_mutation_service, mock_current_user, mock_authz_allowed
):
    """Create TestClient with mocked dependencies."""
    from fastapi import FastAPI

    from graph import dependencies
    from graph.presentation import routes
    from iam.dependencies.user import get_current_user
    from infrastructure.authorization_dependencies import get_spicedb_client

    app = FastAPI()

    # Override query/secure-enclave endpoints with async mock
    app.dependency_overrides[dependencies.get_graph_secure_enclave_service] = (
        lambda: mock_enclave_service
    )
    app.dependency_overrides[dependencies.get_graph_mutation_service] = (
        lambda: mock_mutation_service
    )
    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[get_spicedb_client] = lambda: mock_authz_allowed

    app.include_router(routes.router)

    return TestClient(app)


def _make_kg_test_client(
    mock_query_service, mock_mutation_service, mock_current_user, mock_authz
):
    """Helper to build a TestClient with a specific authz mock."""
    from fastapi import FastAPI

    from graph import dependencies
    from graph.presentation import routes
    from iam.dependencies.user import get_current_user
    from infrastructure.authorization_dependencies import get_spicedb_client

    app = FastAPI()
    app.dependency_overrides[dependencies.get_graph_query_service] = (
        lambda: mock_query_service
    )
    app.dependency_overrides[dependencies.get_graph_mutation_service] = (
        lambda: mock_mutation_service
    )
    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[get_spicedb_client] = lambda: mock_authz

    app.include_router(routes.router)
    return TestClient(app)


class TestApplyMutationsRoute:
    """Tests for POST /graph/mutations endpoint."""

    def test_apply_mutations_success(self, test_client, mock_mutation_service):
        """Should apply mutations from JSONL and return success result."""
        mock_mutation_service.apply_mutations_from_jsonl.return_value = MutationResult(
            success=True,
            operations_applied=2,
        )

        jsonl_data = '{"op": "CREATE", "type": "node", "id": "person:abc123def456789a", "label": "person", "set_properties": {"slug": "alice", "name": "Alice", "data_source_id": "ds-123", "source_path": "people/alice.md"}}\n{"op": "UPDATE", "type": "node", "id": "person:abc123def456789a", "set_properties": {"email": "alice@example.com"}}'

        response = test_client.post(
            "/graph/mutations",
            content=jsonl_data,
            headers={"Content-Type": "application/jsonlines"},
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["success"] is True
        assert result["operations_applied"] == 2

        # Verify service was called with JSONL string
        mock_mutation_service.apply_mutations_from_jsonl.assert_called_once_with(
            jsonl_content=jsonl_data
        )

    def test_apply_mutations_failure_returns_500(
        self, test_client, mock_mutation_service
    ):
        """Should return 500 when mutation application fails."""
        mock_mutation_service.apply_mutations_from_jsonl.return_value = MutationResult(
            success=False,
            operations_applied=0,
            errors=["Database connection failed"],
        )

        jsonl_data = '{"op": "DELETE", "type": "node", "id": "person:abc123def456789a"}'

        response = test_client.post(
            "/graph/mutations",
            content=jsonl_data,
            headers={"Content-Type": "application/jsonlines"},
        )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "errors" in response.json()["detail"]

    def test_apply_whitespace_only_jsonl(self, test_client, mock_mutation_service):
        """Should handle JSONL with only whitespace/newlines."""
        mock_mutation_service.apply_mutations_from_jsonl.return_value = MutationResult(
            success=True,
            operations_applied=0,
        )

        response = test_client.post(
            "/graph/mutations",
            content="\n\n  \n",  # Whitespace only
            headers={"Content-Type": "application/jsonlines"},
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["success"] is True
        assert result["operations_applied"] == 0

    def test_apply_mutations_validation_error_returns_422(
        self, test_client, mock_mutation_service
    ):
        """Should return 422 for validation errors."""
        mock_mutation_service.apply_mutations_from_jsonl.return_value = MutationResult(
            success=False,
            operations_applied=0,
            errors=["JSON parse error: Invalid syntax"],
        )

        invalid_jsonl = "not valid json"

        response = test_client.post(
            "/graph/mutations",
            content=invalid_jsonl,
            headers={"Content-Type": "application/jsonlines"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "errors" in response.json()["detail"]


class TestFindBySlugRoute:
    """Tests for GET /graph/nodes/by-slug endpoint."""

    def test_find_by_slug_success(self, test_client, mock_enclave_service):
        """Should find nodes by slug."""
        mock_nodes = [
            NodeRecord(
                id="person:abc123def456789a",
                label="person",
                properties={
                    "slug": "alice",
                    "name": "Alice",
                    "data_source_id": "ds-123",
                    "source_path": "people/alice.md",
                },
            )
        ]

        mock_enclave_service.search_by_slug.return_value = mock_nodes

        response = test_client.get("/graph/nodes/by-slug?slug=alice")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "nodes" in data
        assert len(data["nodes"]) == 1
        assert data["nodes"][0]["properties"]["slug"] == "alice"

    def test_find_by_slug_with_type_filter(self, test_client, mock_enclave_service):
        """Should filter by node type when provided."""
        mock_nodes = [
            NodeRecord(
                id="person:abc123def456789a",
                label="person",
                properties={
                    "slug": "alice",
                    "name": "Alice",
                    "data_source_id": "ds-123",
                    "source_path": "people/alice.md",
                },
            )
        ]

        mock_enclave_service.search_by_slug.return_value = mock_nodes

        response = test_client.get("/graph/nodes/by-slug?slug=alice&node_type=Person")

        assert response.status_code == status.HTTP_200_OK
        mock_enclave_service.search_by_slug.assert_called_once_with(
            "alice", node_type="Person"
        )


class TestGetNeighborsRoute:
    """Tests for GET /graph/nodes/{node_id}/neighbors endpoint."""

    def test_get_neighbors_success(self, test_client, mock_enclave_service):
        """Should get neighbors and edges."""
        from graph.application.services import SecureEnclaveNeighborsResult

        mock_central_node = NodeRecord(
            id="person:abc123def456789a",
            label="person",
            properties={
                "slug": "alice",
                "name": "Alice",
                "data_source_id": "ds-123",
                "source_path": "people/alice.md",
            },
        )
        mock_neighbor_nodes = [
            NodeRecord(
                id="person:def456abc123789a",
                label="person",
                properties={
                    "slug": "bob",
                    "name": "Bob",
                    "data_source_id": "ds-123",
                    "source_path": "people/bob.md",
                },
            )
        ]
        mock_connecting_edges = [
            EdgeRecord(
                id="knows:aaa111bbb222ccc3",
                label="knows",
                start_id="person:abc123def456789a",
                end_id="person:def456abc123789a",
                properties={
                    "since": 2020,
                    "data_source_id": "ds-123",
                    "source_path": "people/alice.md",
                },
            )
        ]

        mock_enclave_service.get_neighbors.return_value = SecureEnclaveNeighborsResult(
            central_node=mock_central_node,
            nodes=mock_neighbor_nodes,
            edges=mock_connecting_edges,
        )

        response = test_client.get("/graph/nodes/person:abc123def456789a/neighbors")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "central_node" in data
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) == 1
        assert len(data["edges"]) == 1
        assert data["nodes"][0]["properties"]["slug"] == "bob"
        assert data["central_node"]["id"] == "person:abc123def456789a"

    def test_get_neighbors_no_results(self, test_client, mock_enclave_service):
        """Should return empty arrays for isolated node."""
        from graph.application.services import SecureEnclaveNeighborsResult

        mock_central_node = NodeRecord(
            id="person:isolated111111",
            label="person",
            properties={
                "slug": "isolated",
                "data_source_id": "ds-123",
            },
        )

        mock_enclave_service.get_neighbors.return_value = SecureEnclaveNeighborsResult(
            central_node=mock_central_node,
            nodes=[],
            edges=[],
        )

        response = test_client.get("/graph/nodes/person:isolated111111/neighbors")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["central_node"]["id"] == "person:isolated111111"
        assert data["nodes"] == []
        assert data["edges"] == []


class TestKnowledgeGraphScopedMutationsRoute:
    """Tests for POST /graph/knowledge-graphs/{knowledge_graph_id}/mutations endpoint.

    This route enforces:
    - SpiceDB edit permission on the target KnowledgeGraph
    - knowledge_graph_id stamping on all mutations
    - 403 Forbidden when the user lacks edit permission
    """

    def test_kg_mutations_route_accessible_with_edit_permission(
        self,
        mock_query_service,
        mock_mutation_service,
        mock_current_user,
        mock_authz_allowed,
    ):
        """Route should return 200 when user has edit permission."""
        client = _make_kg_test_client(
            mock_query_service,
            mock_mutation_service,
            mock_current_user,
            mock_authz_allowed,
        )
        mock_mutation_service.apply_mutations_from_jsonl.return_value = MutationResult(
            success=True, operations_applied=1
        )

        response = client.post(
            "/graph/knowledge-graphs/kg-123/mutations",
            content='{"op":"DELETE","type":"node","id":"person:abc123def456789a"}',
            headers={"Content-Type": "application/jsonlines"},
        )

        assert response.status_code == status.HTTP_200_OK

    def test_kg_mutations_route_forbidden_without_edit_permission(
        self,
        mock_query_service,
        mock_mutation_service,
        mock_current_user,
        mock_authz_denied,
    ):
        """Route should return 403 when user lacks edit permission on KnowledgeGraph."""
        client = _make_kg_test_client(
            mock_query_service,
            mock_mutation_service,
            mock_current_user,
            mock_authz_denied,
        )

        response = client.post(
            "/graph/knowledge-graphs/kg-123/mutations",
            content='{"op":"DELETE","type":"node","id":"person:abc123def456789a"}',
            headers={"Content-Type": "application/jsonlines"},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        # Service should NOT be called when unauthorized
        mock_mutation_service.apply_mutations_from_jsonl.assert_not_called()

    def test_kg_mutations_route_checks_correct_resource(
        self,
        mock_query_service,
        mock_mutation_service,
        mock_current_user,
        mock_authz_allowed,
    ):
        """Route should check edit permission on the specific knowledge_graph_id."""
        client = _make_kg_test_client(
            mock_query_service,
            mock_mutation_service,
            mock_current_user,
            mock_authz_allowed,
        )
        mock_mutation_service.apply_mutations_from_jsonl.return_value = MutationResult(
            success=True, operations_applied=0
        )

        client.post(
            "/graph/knowledge-graphs/my-graph-456/mutations",
            content=" ",  # Non-empty (whitespace-only) so FastAPI accepts the body
            headers={"Content-Type": "application/jsonlines"},
        )

        # Check that authz was called with the correct resource
        mock_authz_allowed.check_permission.assert_called_once()
        call_args = mock_authz_allowed.check_permission.call_args
        # First positional arg is the resource: "knowledge_graph:my-graph-456"
        resource_arg = call_args[0][0]
        assert "my-graph-456" in resource_arg
        assert "knowledge_graph" in resource_arg

    def test_kg_mutations_route_passes_knowledge_graph_id_to_service(
        self,
        mock_query_service,
        mock_mutation_service,
        mock_current_user,
        mock_authz_allowed,
    ):
        """Route should pass knowledge_graph_id to the service for stamping."""
        client = _make_kg_test_client(
            mock_query_service,
            mock_mutation_service,
            mock_current_user,
            mock_authz_allowed,
        )
        mock_mutation_service.apply_mutations_from_jsonl.return_value = MutationResult(
            success=True, operations_applied=1
        )

        response = client.post(
            "/graph/knowledge-graphs/kg-999/mutations",
            content='{"op":"DELETE","type":"node","id":"person:abc123def456789a"}',
            headers={"Content-Type": "application/jsonlines"},
        )

        assert response.status_code == status.HTTP_200_OK
        # Service should be called with the knowledge_graph_id from the path
        mock_mutation_service.apply_mutations_from_jsonl.assert_called_once()
        call_kwargs = mock_mutation_service.apply_mutations_from_jsonl.call_args[1]
        assert call_kwargs.get("knowledge_graph_id") == "kg-999"

    def test_kg_mutations_route_forbidden_returns_correct_status(
        self,
        mock_query_service,
        mock_mutation_service,
        mock_current_user,
        mock_authz_denied,
    ):
        """Route should return 403 Forbidden with appropriate detail."""
        client = _make_kg_test_client(
            mock_query_service,
            mock_mutation_service,
            mock_current_user,
            mock_authz_denied,
        )

        response = client.post(
            "/graph/knowledge-graphs/kg-123/mutations",
            content=" ",  # Non-empty so FastAPI accepts the body before auth check
            headers={"Content-Type": "application/jsonlines"},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        data = response.json()
        assert "detail" in data


class TestTenantGraphRouting:
    """Tests for per-tenant graph routing.

    The system uses tenant-specific graph names (tenant_{tenant_id})
    to isolate graph data between tenants.
    """

    def test_graph_client_uses_tenant_specific_graph_name(self):
        """get_age_graph_client dependency should use tenant_{tenant_id} as graph name."""
        from graph.dependencies import get_tenant_graph_name
        from iam.domain.value_objects import TenantId, UserId
        from iam.application.value_objects import CurrentUser

        user = CurrentUser(
            user_id=UserId(value="user-abc"),
            username="testuser",
            tenant_id=TenantId(value="t1"),
        )

        graph_name = get_tenant_graph_name(user)
        assert graph_name == "tenant_t1"

    def test_graph_name_uses_full_tenant_id(self):
        """Graph name should use the complete tenant_id value."""
        from graph.dependencies import get_tenant_graph_name
        from iam.domain.value_objects import TenantId, UserId
        from iam.application.value_objects import CurrentUser

        user = CurrentUser(
            user_id=UserId(value="user-xyz"),
            username="testuser",
            tenant_id=TenantId(value="my-org-tenant-123"),
        )

        graph_name = get_tenant_graph_name(user)
        assert graph_name == "tenant_my-org-tenant-123"
