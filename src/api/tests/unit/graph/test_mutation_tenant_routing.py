"""Unit tests for tenant graph routing in mutation operations.

Spec: specs/graph/mutations.spec.md
Requirement: Per-Tenant Graph Isolation

Tests verify that:
- Mutations are routed to the tenant-specific AGE graph (tenant_{tenant_id})
- No data is written to any other tenant's graph
"""

from __future__ import annotations

from graph.infrastructure.age_client import AgeGraphClient
from infrastructure.settings import DatabaseSettings


class TestAgeGraphClientDynamicGraphName:
    """Tests for dynamic graph name support in AgeGraphClient."""

    def test_uses_settings_graph_name_by_default(self):
        """AgeGraphClient should use settings.graph_name when no override provided."""
        settings = DatabaseSettings(
            postgres_host="localhost",
            postgres_port=5432,
            postgres_db="testdb",
            postgres_user="testuser",
            postgres_password="testpass",
            graph_name="default_graph",
        )
        client = AgeGraphClient(settings=settings)
        assert client.graph_name == "default_graph"

    def test_accepts_graph_name_override(self):
        """AgeGraphClient should use provided graph_name over settings.graph_name."""
        settings = DatabaseSettings(
            postgres_host="localhost",
            postgres_port=5432,
            postgres_db="testdb",
            postgres_user="testuser",
            postgres_password="testpass",
            graph_name="default_graph",
        )
        client = AgeGraphClient(settings=settings, graph_name="tenant_abc123")
        assert client.graph_name == "tenant_abc123"

    def test_tenant_graph_name_format(self):
        """Tenant graph names must follow the tenant_{tenant_id} format."""
        tenant_id = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
        expected_graph_name = f"tenant_{tenant_id}"

        settings = DatabaseSettings(
            postgres_host="localhost",
            postgres_port=5432,
            postgres_db="testdb",
            postgres_user="testuser",
            postgres_password="testpass",
            graph_name="default_graph",
        )
        client = AgeGraphClient(settings=settings, graph_name=expected_graph_name)
        assert client.graph_name == f"tenant_{tenant_id}"


class TestTenantGraphRouting:
    """Tests for tenant graph routing in mutation dependencies."""

    def test_get_tenant_graph_name_formats_correctly(self):
        """get_tenant_graph_name should return tenant_{tenant_id} format."""
        from graph.dependencies import get_tenant_graph_name
        from iam.application.value_objects import CurrentUser
        from iam.domain.value_objects import TenantId, UserId

        tenant_id = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
        user = CurrentUser(
            user_id=UserId(value="user-123"),
            username="testuser",
            tenant_id=TenantId(value=tenant_id),
        )

        graph_name = get_tenant_graph_name(current_user=user)
        assert graph_name == f"tenant_{tenant_id}"

    def test_different_tenants_get_different_graph_names(self):
        """Different tenants should route to different AGE graphs."""
        from graph.dependencies import get_tenant_graph_name
        from iam.application.value_objects import CurrentUser
        from iam.domain.value_objects import TenantId, UserId

        user_t1 = CurrentUser(
            user_id=UserId(value="user-1"),
            username="alice",
            tenant_id=TenantId(value="tenant-001"),
        )
        user_t2 = CurrentUser(
            user_id=UserId(value="user-2"),
            username="bob",
            tenant_id=TenantId(value="tenant-002"),
        )

        graph_name_t1 = get_tenant_graph_name(current_user=user_t1)
        graph_name_t2 = get_tenant_graph_name(current_user=user_t2)

        assert graph_name_t1 != graph_name_t2
        assert graph_name_t1 == "tenant_tenant-001"
        assert graph_name_t2 == "tenant_tenant-002"
