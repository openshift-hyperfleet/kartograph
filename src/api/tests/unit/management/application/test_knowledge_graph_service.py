"""Unit tests for KnowledgeGraphService.

Tests verify authorization checks, repository interactions,
transaction management, and observability probe calls.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from management.application.services.knowledge_graph_service import (
    KnowledgeGraphService,
)
from management.domain.aggregates import KnowledgeGraph
from management.domain.value_objects import KnowledgeGraphId
from management.ports.exceptions import (
    DuplicateKnowledgeGraphNameError,
    UnauthorizedError,
)
from shared_kernel.authorization.types import (
    Permission,
    RelationshipTuple,
)


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
def mock_kg_repo():
    """Create a mock IKnowledgeGraphRepository."""
    return AsyncMock()


@pytest.fixture
def mock_ds_repo():
    """Create a mock IDataSourceRepository."""
    return AsyncMock()


@pytest.fixture
def mock_authz():
    """Create a mock AuthorizationProvider."""
    return AsyncMock()


@pytest.fixture
def mock_probe():
    """Create a mock KnowledgeGraphServiceProbe."""
    return MagicMock()


@pytest.fixture
def tenant_id():
    return "tenant-123"


@pytest.fixture
def user_id():
    return "user-456"


@pytest.fixture
def workspace_id():
    return "workspace-789"


@pytest.fixture
def service(
    mock_session, mock_kg_repo, mock_ds_repo, mock_authz, mock_probe, tenant_id
):
    """Create a KnowledgeGraphService with mocked dependencies."""
    return KnowledgeGraphService(
        session=mock_session,
        knowledge_graph_repository=mock_kg_repo,
        data_source_repository=mock_ds_repo,
        authz=mock_authz,
        scope_to_tenant=tenant_id,
        probe=mock_probe,
    )


def _make_kg(
    kg_id: str = "kg-001",
    tenant_id: str = "tenant-123",
    workspace_id: str = "workspace-789",
    name: str = "Test KG",
    description: str = "A test knowledge graph",
) -> KnowledgeGraph:
    """Create a KnowledgeGraph instance for testing."""
    now = datetime.now(UTC)
    kg = KnowledgeGraph(
        id=KnowledgeGraphId(value=kg_id),
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        name=name,
        description=description,
        created_at=now,
        updated_at=now,
    )
    # Clear events from construction
    kg.collect_events()
    return kg


# ---- create ----


class TestKnowledgeGraphServiceCreate:
    """Tests for KnowledgeGraphService.create."""

    @pytest.mark.asyncio
    async def test_create_checks_edit_permission_on_workspace(
        self, service, mock_authz, user_id, workspace_id
    ):
        """create() must check EDIT permission on the workspace."""
        mock_authz.check_permission.return_value = True

        await service.create(
            user_id=user_id,
            workspace_id=workspace_id,
            name="My KG",
            description="desc",
        )

        mock_authz.check_permission.assert_called_once_with(
            resource=f"workspace:{workspace_id}",
            permission=Permission.EDIT,
            subject=f"user:{user_id}",
        )

    @pytest.mark.asyncio
    async def test_create_raises_unauthorized_when_permission_denied(
        self, service, mock_authz, mock_probe, user_id, workspace_id
    ):
        """create() raises UnauthorizedError when user lacks EDIT on workspace."""
        mock_authz.check_permission.return_value = False

        with pytest.raises(UnauthorizedError):
            await service.create(
                user_id=user_id,
                workspace_id=workspace_id,
                name="My KG",
                description="desc",
            )

        mock_probe.permission_denied.assert_called_once_with(
            user_id=user_id,
            resource_id=workspace_id,
            permission=Permission.EDIT,
        )

    @pytest.mark.asyncio
    async def test_create_saves_aggregate_via_repo(
        self, service, mock_authz, mock_kg_repo, user_id, workspace_id, tenant_id
    ):
        """create() saves the KnowledgeGraph aggregate through the repository."""
        mock_authz.check_permission.return_value = True

        result = await service.create(
            user_id=user_id,
            workspace_id=workspace_id,
            name="My KG",
            description="desc",
        )

        assert result.name == "My KG"
        assert result.description == "desc"
        assert result.tenant_id == tenant_id
        assert result.workspace_id == workspace_id
        mock_kg_repo.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_probes_success(
        self, service, mock_authz, mock_probe, user_id, workspace_id, tenant_id
    ):
        """create() calls probe on success."""
        mock_authz.check_permission.return_value = True

        result = await service.create(
            user_id=user_id,
            workspace_id=workspace_id,
            name="My KG",
            description="desc",
        )

        mock_probe.knowledge_graph_created.assert_called_once_with(
            kg_id=result.id.value,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            name="My KG",
        )

    @pytest.mark.asyncio
    async def test_create_raises_duplicate_on_integrity_error(
        self, service, mock_authz, mock_kg_repo, user_id, workspace_id
    ):
        """create() catches IntegrityError and raises DuplicateKnowledgeGraphNameError."""
        mock_authz.check_permission.return_value = True
        mock_kg_repo.save.side_effect = IntegrityError(
            "INSERT", {}, Exception("uq_knowledge_graphs_tenant_name")
        )

        with pytest.raises(DuplicateKnowledgeGraphNameError):
            await service.create(
                user_id=user_id,
                workspace_id=workspace_id,
                name="Duplicate",
                description="desc",
            )


# ---- get ----


class TestKnowledgeGraphServiceGet:
    """Tests for KnowledgeGraphService.get."""

    @pytest.mark.asyncio
    async def test_get_returns_none_when_not_found(
        self, service, mock_kg_repo, user_id
    ):
        """get() returns None when KG is not found."""
        mock_kg_repo.get_by_id.return_value = None

        result = await service.get(user_id=user_id, kg_id="nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_checks_view_permission(
        self, service, mock_authz, mock_kg_repo, user_id
    ):
        """get() checks VIEW permission on the knowledge graph."""
        kg = _make_kg()
        mock_kg_repo.get_by_id.return_value = kg
        mock_authz.check_permission.return_value = True

        await service.get(user_id=user_id, kg_id=kg.id.value)

        mock_authz.check_permission.assert_called_once_with(
            resource=f"knowledge_graph:{kg.id.value}",
            permission=Permission.VIEW,
            subject=f"user:{user_id}",
        )

    @pytest.mark.asyncio
    async def test_get_raises_unauthorized_when_permission_denied(
        self, service, mock_authz, mock_kg_repo, user_id
    ):
        """get() raises UnauthorizedError when user lacks VIEW."""
        kg = _make_kg()
        mock_kg_repo.get_by_id.return_value = kg
        mock_authz.check_permission.return_value = False

        with pytest.raises(UnauthorizedError):
            await service.get(user_id=user_id, kg_id=kg.id.value)

    @pytest.mark.asyncio
    async def test_get_returns_aggregate_on_success(
        self, service, mock_authz, mock_kg_repo, mock_probe, user_id
    ):
        """get() returns the aggregate when authorized."""
        kg = _make_kg()
        mock_kg_repo.get_by_id.return_value = kg
        mock_authz.check_permission.return_value = True

        result = await service.get(user_id=user_id, kg_id=kg.id.value)

        assert result is kg
        mock_probe.knowledge_graph_retrieved.assert_called_once_with(
            kg_id=kg.id.value,
        )


# ---- list_for_workspace ----


class TestKnowledgeGraphServiceListForWorkspace:
    """Tests for KnowledgeGraphService.list_for_workspace."""

    @pytest.mark.asyncio
    async def test_list_checks_view_permission_on_workspace(
        self, service, mock_authz, user_id, workspace_id
    ):
        """list_for_workspace() checks VIEW on the workspace."""
        mock_authz.check_permission.return_value = True
        mock_authz.read_relationships.return_value = []

        await service.list_for_workspace(user_id=user_id, workspace_id=workspace_id)

        mock_authz.check_permission.assert_called_once_with(
            resource=f"workspace:{workspace_id}",
            permission=Permission.VIEW,
            subject=f"user:{user_id}",
        )

    @pytest.mark.asyncio
    async def test_list_raises_unauthorized_when_permission_denied(
        self, service, mock_authz, user_id, workspace_id
    ):
        """list_for_workspace() raises UnauthorizedError when denied."""
        mock_authz.check_permission.return_value = False

        with pytest.raises(UnauthorizedError):
            await service.list_for_workspace(user_id=user_id, workspace_id=workspace_id)

    @pytest.mark.asyncio
    async def test_list_uses_read_relationships_to_discover_kgs(
        self,
        service,
        mock_authz,
        mock_kg_repo,
        mock_probe,
        user_id,
        workspace_id,
        tenant_id,
    ):
        """list_for_workspace() reads relationships to find KG IDs."""
        mock_authz.check_permission.return_value = True
        kg1 = _make_kg(kg_id="kg-001", tenant_id=tenant_id)
        kg2 = _make_kg(kg_id="kg-002", tenant_id=tenant_id)
        mock_authz.read_relationships.return_value = [
            RelationshipTuple(
                resource="knowledge_graph:kg-001",
                relation="workspace",
                subject=f"workspace:{workspace_id}",
            ),
            RelationshipTuple(
                resource="knowledge_graph:kg-002",
                relation="workspace",
                subject=f"workspace:{workspace_id}",
            ),
        ]
        mock_kg_repo.get_by_id.side_effect = [kg1, kg2]

        result = await service.list_for_workspace(
            user_id=user_id, workspace_id=workspace_id
        )

        assert len(result) == 2
        mock_probe.knowledge_graphs_listed.assert_called_once_with(
            workspace_id=workspace_id,
            count=2,
        )

    @pytest.mark.asyncio
    async def test_list_filters_by_tenant(
        self, service, mock_authz, mock_kg_repo, user_id, workspace_id, tenant_id
    ):
        """list_for_workspace() filters KGs that don't belong to the scoped tenant."""
        mock_authz.check_permission.return_value = True
        kg_own = _make_kg(kg_id="kg-001", tenant_id=tenant_id)
        kg_other = _make_kg(kg_id="kg-002", tenant_id="other-tenant")
        mock_authz.read_relationships.return_value = [
            RelationshipTuple(
                resource="knowledge_graph:kg-001",
                relation="workspace",
                subject=f"workspace:{workspace_id}",
            ),
            RelationshipTuple(
                resource="knowledge_graph:kg-002",
                relation="workspace",
                subject=f"workspace:{workspace_id}",
            ),
        ]
        mock_kg_repo.get_by_id.side_effect = [kg_own, kg_other]

        result = await service.list_for_workspace(
            user_id=user_id, workspace_id=workspace_id
        )

        assert len(result) == 1
        assert result[0].id.value == "kg-001"


# ---- update ----


class TestKnowledgeGraphServiceUpdate:
    """Tests for KnowledgeGraphService.update."""

    @pytest.mark.asyncio
    async def test_update_checks_edit_permission_on_kg(
        self, service, mock_authz, mock_kg_repo, user_id
    ):
        """update() checks EDIT permission on the knowledge graph."""
        kg = _make_kg()
        mock_authz.check_permission.return_value = True
        mock_kg_repo.get_by_id.return_value = kg

        await service.update(
            user_id=user_id,
            kg_id=kg.id.value,
            name="Updated",
            description="Updated desc",
        )

        mock_authz.check_permission.assert_called_once_with(
            resource=f"knowledge_graph:{kg.id.value}",
            permission=Permission.EDIT,
            subject=f"user:{user_id}",
        )

    @pytest.mark.asyncio
    async def test_update_raises_unauthorized_when_permission_denied(
        self, service, mock_authz, user_id
    ):
        """update() raises UnauthorizedError when denied."""
        mock_authz.check_permission.return_value = False

        with pytest.raises(UnauthorizedError):
            await service.update(
                user_id=user_id,
                kg_id="kg-001",
                name="Updated",
                description="Updated desc",
            )

    @pytest.mark.asyncio
    async def test_update_raises_value_error_when_not_found(
        self, service, mock_authz, mock_kg_repo, user_id
    ):
        """update() raises ValueError when KG not found."""
        mock_authz.check_permission.return_value = True
        mock_kg_repo.get_by_id.return_value = None

        with pytest.raises(ValueError):
            await service.update(
                user_id=user_id,
                kg_id="nonexistent",
                name="Updated",
                description="Updated desc",
            )

    @pytest.mark.asyncio
    async def test_update_calls_aggregate_update_and_saves(
        self, service, mock_authz, mock_kg_repo, mock_probe, user_id
    ):
        """update() calls kg.update() and saves via repo."""
        kg = _make_kg()
        mock_authz.check_permission.return_value = True
        mock_kg_repo.get_by_id.return_value = kg

        result = await service.update(
            user_id=user_id,
            kg_id=kg.id.value,
            name="Updated",
            description="New desc",
        )

        assert result.name == "Updated"
        assert result.description == "New desc"
        mock_kg_repo.save.assert_called_once_with(kg)
        mock_probe.knowledge_graph_updated.assert_called_once_with(
            kg_id=kg.id.value,
            name="Updated",
        )

    @pytest.mark.asyncio
    async def test_update_raises_duplicate_on_integrity_error(
        self, service, mock_authz, mock_kg_repo, user_id
    ):
        """update() catches IntegrityError and raises DuplicateKnowledgeGraphNameError."""
        kg = _make_kg()
        mock_authz.check_permission.return_value = True
        mock_kg_repo.get_by_id.return_value = kg
        mock_kg_repo.save.side_effect = IntegrityError(
            "UPDATE", {}, Exception("uq_knowledge_graphs_tenant_name")
        )

        with pytest.raises(DuplicateKnowledgeGraphNameError):
            await service.update(
                user_id=user_id,
                kg_id=kg.id.value,
                name="Duplicate",
                description="desc",
            )


# ---- delete ----


class TestKnowledgeGraphServiceDelete:
    """Tests for KnowledgeGraphService.delete."""

    @pytest.mark.asyncio
    async def test_delete_checks_manage_permission_on_kg(
        self, service, mock_authz, mock_kg_repo, mock_ds_repo, user_id
    ):
        """delete() checks MANAGE permission on the knowledge graph."""
        kg = _make_kg()
        mock_authz.check_permission.return_value = True
        mock_kg_repo.get_by_id.return_value = kg
        mock_ds_repo.find_by_knowledge_graph.return_value = []
        mock_kg_repo.delete.return_value = True

        await service.delete(user_id=user_id, kg_id=kg.id.value)

        mock_authz.check_permission.assert_called_once_with(
            resource=f"knowledge_graph:{kg.id.value}",
            permission=Permission.MANAGE,
            subject=f"user:{user_id}",
        )

    @pytest.mark.asyncio
    async def test_delete_raises_unauthorized_when_permission_denied(
        self, service, mock_authz, user_id
    ):
        """delete() raises UnauthorizedError when denied."""
        mock_authz.check_permission.return_value = False

        with pytest.raises(UnauthorizedError):
            await service.delete(user_id=user_id, kg_id="kg-001")

    @pytest.mark.asyncio
    async def test_delete_returns_false_when_not_found(
        self, service, mock_authz, mock_kg_repo, mock_ds_repo, user_id
    ):
        """delete() returns False when KG not found."""
        mock_authz.check_permission.return_value = True
        mock_kg_repo.get_by_id.return_value = None

        result = await service.delete(user_id=user_id, kg_id="nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_cascades_data_sources(
        self, service, mock_authz, mock_kg_repo, mock_ds_repo, user_id, tenant_id
    ):
        """delete() deletes all data sources before deleting the KG."""
        kg = _make_kg(tenant_id=tenant_id)
        ds1 = MagicMock()
        ds2 = MagicMock()
        mock_authz.check_permission.return_value = True
        mock_kg_repo.get_by_id.return_value = kg
        mock_ds_repo.find_by_knowledge_graph.return_value = [ds1, ds2]
        mock_ds_repo.delete.return_value = True
        mock_kg_repo.delete.return_value = True

        result = await service.delete(user_id=user_id, kg_id=kg.id.value)

        assert result is True
        # Each DS should be marked for deletion and deleted
        ds1.mark_for_deletion.assert_called_once()
        ds2.mark_for_deletion.assert_called_once()
        assert mock_ds_repo.delete.call_count == 2
        mock_kg_repo.delete.assert_called_once_with(kg)

    @pytest.mark.asyncio
    async def test_delete_probes_success(
        self, service, mock_authz, mock_kg_repo, mock_ds_repo, mock_probe, user_id
    ):
        """delete() calls probe on success."""
        kg = _make_kg()
        mock_authz.check_permission.return_value = True
        mock_kg_repo.get_by_id.return_value = kg
        mock_ds_repo.find_by_knowledge_graph.return_value = []
        mock_kg_repo.delete.return_value = True

        await service.delete(user_id=user_id, kg_id=kg.id.value)

        mock_probe.knowledge_graph_deleted.assert_called_once_with(
            kg_id=kg.id.value,
        )
