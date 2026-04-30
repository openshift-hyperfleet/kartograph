"""Unit tests for KnowledgeGraphService.

Tests verify authorization checks, repository interactions,
transaction management, and observability probe calls.

Collaborators use in-memory fakes (no MagicMock/AsyncMock for domain or
application-layer ports) per specs/nfr/testing.spec.md.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from management.application.services.knowledge_graph_service import (
    KnowledgeGraphService,
)
from management.domain.aggregates import DataSource, KnowledgeGraph
from management.domain.value_objects import (
    DataSourceId,
    KnowledgeGraphId,
    Schedule,
    ScheduleType,
)
from shared_kernel.datasource_types import DataSourceAdapterType
from management.ports.exceptions import (
    DuplicateKnowledgeGraphNameError,
    KnowledgeGraphNotFoundError,
    UnauthorizedError,
)
from shared_kernel.authorization.types import Permission
from tests.fakes.authorization import InMemoryAuthorizationProvider
from tests.fakes.management import (
    InMemoryDataSourceRepository,
    InMemoryKnowledgeGraphRepository,
    InMemorySecretStoreRepository,
    RecordingKnowledgeGraphServiceProbe,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session():
    """Create a mock AsyncSession with begin() context manager.

    The session is mocked at the infrastructure boundary — unit tests of
    the application service do not exercise real SQLAlchemy transaction
    semantics.  Rollback behaviour is covered by integration tests.
    """
    session = MagicMock()

    @asynccontextmanager
    async def _begin():
        yield

    session.begin = _begin
    return session


@pytest.fixture
def kg_repo():
    """In-memory KnowledgeGraph repository."""
    return InMemoryKnowledgeGraphRepository()


@pytest.fixture
def ds_repo():
    """In-memory DataSource repository."""
    return InMemoryDataSourceRepository()


@pytest.fixture
def secret_store():
    """In-memory secret store."""
    return InMemorySecretStoreRepository()


@pytest.fixture
def authz():
    """In-memory authorization provider (full fake, no mocks)."""
    return InMemoryAuthorizationProvider()


@pytest.fixture
def probe():
    """Concrete recording probe (no MagicMock)."""
    return RecordingKnowledgeGraphServiceProbe()


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
def service(mock_session, kg_repo, ds_repo, secret_store, authz, probe, tenant_id):
    """KnowledgeGraphService wired with in-memory fakes."""
    return KnowledgeGraphService(
        session=mock_session,
        knowledge_graph_repository=kg_repo,
        data_source_repository=ds_repo,
        secret_store=secret_store,
        authz=authz,
        scope_to_tenant=tenant_id,
        probe=probe,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _make_ds(
    ds_id: str = "ds-001",
    kg_id: str = "kg-001",
    tenant_id: str = "tenant-123",
    name: str = "Test DS",
    credentials_path: str | None = None,
) -> DataSource:
    """Create a DataSource instance for testing."""
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


async def _grant_workspace_edit(
    authz: InMemoryAuthorizationProvider, workspace_id: str, user_id: str
) -> None:
    """Grant EDIT permission on a workspace to a user."""
    await authz.write_relationship(
        f"workspace:{workspace_id}", "editor", f"user:{user_id}"
    )


async def _grant_workspace_view(
    authz: InMemoryAuthorizationProvider, workspace_id: str, user_id: str
) -> None:
    """Grant VIEW-only permission on a workspace to a user (member role)."""
    await authz.write_relationship(
        f"workspace:{workspace_id}", "member", f"user:{user_id}"
    )


async def _grant_kg_edit(
    authz: InMemoryAuthorizationProvider, kg_id: str, user_id: str
) -> None:
    """Grant EDIT permission on a knowledge graph to a user."""
    await authz.write_relationship(
        f"knowledge_graph:{kg_id}", "editor", f"user:{user_id}"
    )


async def _grant_kg_view(
    authz: InMemoryAuthorizationProvider, kg_id: str, user_id: str
) -> None:
    """Grant VIEW permission on a knowledge graph to a user."""
    await authz.write_relationship(
        f"knowledge_graph:{kg_id}", "viewer", f"user:{user_id}"
    )


async def _grant_kg_manage(
    authz: InMemoryAuthorizationProvider, kg_id: str, user_id: str
) -> None:
    """Grant MANAGE permission on a knowledge graph to a user (admin role)."""
    await authz.write_relationship(
        f"knowledge_graph:{kg_id}", "admin", f"user:{user_id}"
    )


# ---- create ----


class TestKnowledgeGraphServiceCreate:
    """Tests for KnowledgeGraphService.create."""

    @pytest.mark.asyncio
    async def test_create_checks_edit_permission_on_workspace(
        self, service, authz, user_id, workspace_id
    ):
        """create() requires EDIT on the workspace — VIEW alone is not enough."""
        # member grants VIEW but not EDIT — create must fail
        await _grant_workspace_view(authz, workspace_id, user_id)
        with pytest.raises(UnauthorizedError):
            await service.create(
                user_id=user_id,
                workspace_id=workspace_id,
                name="My KG",
                description="desc",
            )

        # editor grants EDIT — create must succeed
        await _grant_workspace_edit(authz, workspace_id, user_id)
        result = await service.create(
            user_id=user_id,
            workspace_id=workspace_id,
            name="My KG",
            description="desc",
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_create_raises_unauthorized_when_permission_denied(
        self, service, authz, probe, user_id, workspace_id
    ):
        """create() raises UnauthorizedError when user lacks EDIT on workspace."""
        # No relationships written — all checks return False

        with pytest.raises(UnauthorizedError):
            await service.create(
                user_id=user_id,
                workspace_id=workspace_id,
                name="My KG",
                description="desc",
            )

        assert len(probe.permission_denied_calls) == 1
        call = probe.permission_denied_calls[0]
        assert call["user_id"] == user_id
        assert call["resource_id"] == workspace_id
        assert call["permission"] == Permission.EDIT

    @pytest.mark.asyncio
    async def test_create_saves_aggregate_via_repo(
        self, service, authz, kg_repo, user_id, workspace_id, tenant_id
    ):
        """create() saves the KnowledgeGraph aggregate through the repository."""
        await _grant_workspace_edit(authz, workspace_id, user_id)

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
        assert len(kg_repo.saved) == 1

    @pytest.mark.asyncio
    async def test_create_probes_success(
        self, service, authz, probe, user_id, workspace_id, tenant_id
    ):
        """create() calls probe on success."""
        await _grant_workspace_edit(authz, workspace_id, user_id)

        result = await service.create(
            user_id=user_id,
            workspace_id=workspace_id,
            name="My KG",
            description="desc",
        )

        assert len(probe.knowledge_graph_created_calls) == 1
        call = probe.knowledge_graph_created_calls[0]
        assert call["kg_id"] == result.id.value
        assert call["tenant_id"] == tenant_id
        assert call["workspace_id"] == workspace_id
        assert call["name"] == "My KG"

    @pytest.mark.asyncio
    async def test_create_raises_duplicate_on_integrity_error(
        self, service, authz, kg_repo, user_id, workspace_id
    ):
        """create() catches IntegrityError and raises DuplicateKnowledgeGraphNameError."""
        await _grant_workspace_edit(authz, workspace_id, user_id)

        # Simulate a duplicate by making save raise IntegrityError
        original_save = kg_repo.save

        async def raise_integrity_error(kg: KnowledgeGraph) -> None:
            raise IntegrityError(
                "INSERT", {}, Exception("uq_knowledge_graphs_tenant_name")
            )

        kg_repo.save = raise_integrity_error

        with pytest.raises(DuplicateKnowledgeGraphNameError):
            await service.create(
                user_id=user_id,
                workspace_id=workspace_id,
                name="Duplicate",
                description="desc",
            )

        kg_repo.save = original_save


# ---- get ----


class TestKnowledgeGraphServiceGet:
    """Tests for KnowledgeGraphService.get."""

    @pytest.mark.asyncio
    async def test_get_returns_none_when_not_found(self, service, authz, user_id):
        """get() returns None when KG is not found."""
        # Grant VIEW so the permission check doesn't prevent us from seeing
        # the absence in the repo.  The KG simply doesn't exist.
        result = await service.get(user_id=user_id, kg_id="nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_checks_view_permission(self, service, authz, kg_repo, user_id):
        """get() requires VIEW on the knowledge graph — missing permission returns None."""
        kg = _make_kg()
        kg_repo.seed(kg)

        # Without VIEW permission → None (no existence leakage)
        result = await service.get(user_id=user_id, kg_id=kg.id.value)
        assert result is None

        # Grant VIEW → KG returned
        await _grant_kg_view(authz, kg.id.value, user_id)
        result = await service.get(user_id=user_id, kg_id=kg.id.value)
        assert result is kg

    @pytest.mark.asyncio
    async def test_get_returns_none_for_different_tenant(
        self, service, kg_repo, user_id
    ):
        """get() returns None when KG belongs to a different tenant."""
        kg = _make_kg(tenant_id="other-tenant")
        kg_repo.seed(kg)

        result = await service.get(user_id=user_id, kg_id=kg.id.value)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_returns_none_when_permission_denied(
        self, service, kg_repo, user_id
    ):
        """get() returns None when user lacks VIEW (no existence leakage)."""
        kg = _make_kg()
        kg_repo.seed(kg)
        # No relationships written → VIEW denied

        result = await service.get(user_id=user_id, kg_id=kg.id.value)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_returns_aggregate_on_success(
        self, service, authz, kg_repo, probe, user_id
    ):
        """get() returns the aggregate when authorized."""
        kg = _make_kg()
        kg_repo.seed(kg)
        await _grant_kg_view(authz, kg.id.value, user_id)

        result = await service.get(user_id=user_id, kg_id=kg.id.value)

        assert result is kg
        assert len(probe.knowledge_graph_retrieved_calls) == 1
        assert probe.knowledge_graph_retrieved_calls[0]["kg_id"] == kg.id.value


# ---- list_for_workspace ----


class TestKnowledgeGraphServiceListForWorkspace:
    """Tests for KnowledgeGraphService.list_for_workspace."""

    @pytest.mark.asyncio
    async def test_list_checks_view_permission_on_workspace(
        self, service, authz, user_id, workspace_id
    ):
        """list_for_workspace() requires VIEW on the workspace — missing permission raises."""
        # No relationships written → VIEW denied → should raise
        with pytest.raises(UnauthorizedError):
            await service.list_for_workspace(user_id=user_id, workspace_id=workspace_id)

        # Grant VIEW → should succeed
        await _grant_workspace_view(authz, workspace_id, user_id)
        result = await service.list_for_workspace(
            user_id=user_id, workspace_id=workspace_id
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_list_raises_unauthorized_when_permission_denied(
        self, service, user_id, workspace_id
    ):
        """list_for_workspace() raises UnauthorizedError when denied."""
        # No relationships written
        with pytest.raises(UnauthorizedError):
            await service.list_for_workspace(user_id=user_id, workspace_id=workspace_id)

    @pytest.mark.asyncio
    async def test_list_uses_read_relationships_to_discover_kgs(
        self,
        service,
        authz,
        kg_repo,
        probe,
        user_id,
        workspace_id,
        tenant_id,
    ):
        """list_for_workspace() reads relationships to find KG IDs."""
        await _grant_workspace_view(authz, workspace_id, user_id)

        kg1 = _make_kg(kg_id="kg-001", tenant_id=tenant_id, workspace_id=workspace_id)
        kg2 = _make_kg(kg_id="kg-002", tenant_id=tenant_id, workspace_id=workspace_id)
        kg_repo.seed(kg1, kg2)

        # Write workspace→KG relationships so the service can discover them
        await authz.write_relationship(
            "knowledge_graph:kg-001", "workspace", f"workspace:{workspace_id}"
        )
        await authz.write_relationship(
            "knowledge_graph:kg-002", "workspace", f"workspace:{workspace_id}"
        )

        result = await service.list_for_workspace(
            user_id=user_id, workspace_id=workspace_id
        )

        assert len(result) == 2
        assert len(probe.knowledge_graphs_listed_calls) == 1
        listed_call = probe.knowledge_graphs_listed_calls[0]
        assert listed_call["workspace_id"] == workspace_id
        assert listed_call["count"] == 2

    @pytest.mark.asyncio
    async def test_list_filters_by_tenant(
        self, service, authz, kg_repo, user_id, workspace_id, tenant_id
    ):
        """list_for_workspace() filters KGs that don't belong to the scoped tenant."""
        await _grant_workspace_view(authz, workspace_id, user_id)

        kg_own = _make_kg(kg_id="kg-001", tenant_id=tenant_id)
        kg_other = _make_kg(kg_id="kg-002", tenant_id="other-tenant")
        kg_repo.seed(kg_own, kg_other)

        await authz.write_relationship(
            "knowledge_graph:kg-001", "workspace", f"workspace:{workspace_id}"
        )
        await authz.write_relationship(
            "knowledge_graph:kg-002", "workspace", f"workspace:{workspace_id}"
        )

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
        self, service, authz, kg_repo, user_id
    ):
        """update() requires EDIT on the knowledge graph — VIEW alone is not enough."""
        kg = _make_kg()
        kg_repo.seed(kg)

        # viewer role grants VIEW but not EDIT
        await _grant_kg_view(authz, kg.id.value, user_id)
        with pytest.raises(UnauthorizedError):
            await service.update(
                user_id=user_id,
                kg_id=kg.id.value,
                name="Updated",
                description="Updated desc",
            )

        # editor role grants EDIT — update must succeed
        await _grant_kg_edit(authz, kg.id.value, user_id)
        result = await service.update(
            user_id=user_id,
            kg_id=kg.id.value,
            name="Updated",
            description="Updated desc",
        )
        assert result.name == "Updated"

    @pytest.mark.asyncio
    async def test_update_raises_unauthorized_when_permission_denied(
        self, service, user_id
    ):
        """update() raises UnauthorizedError when denied."""
        # No relationships written
        with pytest.raises(UnauthorizedError):
            await service.update(
                user_id=user_id,
                kg_id="kg-001",
                name="Updated",
                description="Updated desc",
            )

    @pytest.mark.asyncio
    async def test_update_raises_not_found_error_when_not_found(
        self, service, authz, user_id
    ):
        """update() raises KnowledgeGraphNotFoundError when KG not found."""
        await _grant_kg_edit(authz, "nonexistent", user_id)

        with pytest.raises(KnowledgeGraphNotFoundError):
            await service.update(
                user_id=user_id,
                kg_id="nonexistent",
                name="Updated",
                description="Updated desc",
            )

    @pytest.mark.asyncio
    async def test_update_rejects_different_tenant(
        self, service, authz, kg_repo, user_id
    ):
        """update() raises KnowledgeGraphNotFoundError when KG belongs to a different tenant."""
        kg = _make_kg(tenant_id="other-tenant")
        kg_repo.seed(kg)
        await _grant_kg_edit(authz, kg.id.value, user_id)

        with pytest.raises(KnowledgeGraphNotFoundError):
            await service.update(
                user_id=user_id,
                kg_id=kg.id.value,
                name="Updated",
                description="Updated desc",
            )

    @pytest.mark.asyncio
    async def test_update_calls_aggregate_update_and_saves(
        self, service, authz, kg_repo, probe, user_id
    ):
        """update() calls kg.update() and saves via repo."""
        kg = _make_kg()
        kg_repo.seed(kg)
        await _grant_kg_edit(authz, kg.id.value, user_id)

        result = await service.update(
            user_id=user_id,
            kg_id=kg.id.value,
            name="Updated",
            description="New desc",
        )

        assert result.name == "Updated"
        assert result.description == "New desc"
        assert len(kg_repo.saved) == 1
        assert kg_repo.saved[0] is kg

        assert len(probe.knowledge_graph_updated_calls) == 1
        call = probe.knowledge_graph_updated_calls[0]
        assert call["kg_id"] == kg.id.value
        assert call["name"] == "Updated"

    @pytest.mark.asyncio
    async def test_update_raises_duplicate_on_integrity_error(
        self, service, authz, kg_repo, user_id
    ):
        """update() catches IntegrityError and raises DuplicateKnowledgeGraphNameError."""
        kg = _make_kg()
        kg_repo.seed(kg)
        await _grant_kg_edit(authz, kg.id.value, user_id)

        original_save = kg_repo.save

        async def raise_integrity_error(knowledge_graph: KnowledgeGraph) -> None:
            raise IntegrityError(
                "UPDATE", {}, Exception("uq_knowledge_graphs_tenant_name")
            )

        kg_repo.save = raise_integrity_error

        with pytest.raises(DuplicateKnowledgeGraphNameError):
            await service.update(
                user_id=user_id,
                kg_id=kg.id.value,
                name="Duplicate",
                description="desc",
            )

        kg_repo.save = original_save


# ---- delete ----


class TestKnowledgeGraphServiceDelete:
    """Tests for KnowledgeGraphService.delete."""

    @pytest.mark.asyncio
    async def test_delete_checks_manage_permission_on_kg(
        self, service, authz, kg_repo, ds_repo, user_id, tenant_id
    ):
        """delete() requires MANAGE on the knowledge graph — EDIT alone is not enough."""
        kg = _make_kg(tenant_id=tenant_id)
        kg_repo.seed(kg)

        # editor grants EDIT but not MANAGE
        await _grant_kg_edit(authz, kg.id.value, user_id)
        with pytest.raises(UnauthorizedError):
            await service.delete(user_id=user_id, kg_id=kg.id.value)

        # admin grants MANAGE — delete must succeed
        await _grant_kg_manage(authz, kg.id.value, user_id)
        result = await service.delete(user_id=user_id, kg_id=kg.id.value)
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_raises_unauthorized_when_permission_denied(
        self, service, user_id
    ):
        """delete() raises UnauthorizedError when denied."""
        # No relationships written
        with pytest.raises(UnauthorizedError):
            await service.delete(user_id=user_id, kg_id="kg-001")

    @pytest.mark.asyncio
    async def test_delete_returns_false_when_not_found(self, service, authz, user_id):
        """delete() returns False when KG not found."""
        await _grant_kg_manage(authz, "nonexistent", user_id)

        result = await service.delete(user_id=user_id, kg_id="nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_returns_false_for_different_tenant(
        self, service, authz, kg_repo, user_id
    ):
        """delete() returns False when KG belongs to a different tenant."""
        kg = _make_kg(tenant_id="other-tenant")
        kg_repo.seed(kg)
        await _grant_kg_manage(authz, kg.id.value, user_id)

        result = await service.delete(user_id=user_id, kg_id=kg.id.value)

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_cascades_data_sources(
        self, service, authz, kg_repo, ds_repo, user_id, tenant_id
    ):
        """delete() deletes all data sources before deleting the KG."""
        kg = _make_kg(tenant_id=tenant_id)
        ds1 = _make_ds(ds_id="ds-001", kg_id=kg.id.value, tenant_id=tenant_id)
        ds2 = _make_ds(ds_id="ds-002", kg_id=kg.id.value, tenant_id=tenant_id)

        kg_repo.seed(kg)
        ds_repo.seed(ds1, ds2)
        await _grant_kg_manage(authz, kg.id.value, user_id)

        result = await service.delete(user_id=user_id, kg_id=kg.id.value)

        assert result is True
        assert len(ds_repo.deleted) == 2
        assert len(kg_repo.deleted) == 1

    @pytest.mark.asyncio
    async def test_delete_calls_secret_store_delete_for_credential_bearing_ds(
        self,
        service,
        authz,
        kg_repo,
        ds_repo,
        secret_store,
        user_id,
        tenant_id,
    ):
        """delete() calls secret_store.delete for each DS that has credentials_path."""
        kg = _make_kg(tenant_id=tenant_id)
        ds1 = _make_ds(
            ds_id="ds-001",
            kg_id=kg.id.value,
            tenant_id=tenant_id,
            credentials_path="datasource/ds-001/credentials",
        )
        ds2 = _make_ds(
            ds_id="ds-002",
            kg_id=kg.id.value,
            tenant_id=tenant_id,
            credentials_path="datasource/ds-002/credentials",
        )

        kg_repo.seed(kg)
        ds_repo.seed(ds1, ds2)
        await _grant_kg_manage(authz, kg.id.value, user_id)

        await service.delete(user_id=user_id, kg_id=kg.id.value)

        assert len(secret_store.delete_calls) == 2
        paths_deleted = {c["path"] for c in secret_store.delete_calls}
        assert paths_deleted == {
            "datasource/ds-001/credentials",
            "datasource/ds-002/credentials",
        }
        for call in secret_store.delete_calls:
            assert call["tenant_id"] == tenant_id

    @pytest.mark.asyncio
    async def test_delete_skips_secret_store_for_ds_without_credentials(
        self,
        service,
        authz,
        kg_repo,
        ds_repo,
        secret_store,
        user_id,
        tenant_id,
    ):
        """delete() skips secret_store.delete for DS with no credentials_path."""
        kg = _make_kg(tenant_id=tenant_id)
        ds = _make_ds(
            ds_id="ds-001",
            kg_id=kg.id.value,
            tenant_id=tenant_id,
            credentials_path=None,
        )

        kg_repo.seed(kg)
        ds_repo.seed(ds)
        await _grant_kg_manage(authz, kg.id.value, user_id)

        await service.delete(user_id=user_id, kg_id=kg.id.value)

        assert len(secret_store.delete_calls) == 0

    @pytest.mark.asyncio
    async def test_delete_secret_cleanup_happens_before_repo_delete(
        self,
        authz,
        kg_repo,
        mock_session,
        user_id,
        tenant_id,
        probe,
    ):
        """delete() cleans up credentials BEFORE deleting the DS row."""
        call_order: list[str] = []

        # Fakes with shared call_log track cross-object ordering
        ordered_secret_store = InMemorySecretStoreRepository(call_log=call_order)
        ordered_ds_repo = InMemoryDataSourceRepository(call_log=call_order)

        kg = _make_kg(tenant_id=tenant_id)
        ds = _make_ds(
            ds_id="ds-001",
            kg_id=kg.id.value,
            tenant_id=tenant_id,
            credentials_path="datasource/ds-001/credentials",
        )

        kg_repo.seed(kg)
        ordered_ds_repo.seed(ds)
        await _grant_kg_manage(authz, kg.id.value, user_id)

        svc = KnowledgeGraphService(
            session=mock_session,
            knowledge_graph_repository=kg_repo,
            data_source_repository=ordered_ds_repo,
            secret_store=ordered_secret_store,
            authz=authz,
            scope_to_tenant=tenant_id,
            probe=probe,
        )

        await svc.delete(user_id=user_id, kg_id=kg.id.value)

        assert call_order == ["secret_store.delete", "ds_repo.delete"], (
            "Credentials must be deleted before the DataSource row is removed"
        )

    @pytest.mark.asyncio
    async def test_delete_probes_success(
        self, service, authz, kg_repo, ds_repo, probe, user_id, tenant_id
    ):
        """delete() calls probe on success."""
        kg = _make_kg(tenant_id=tenant_id)
        kg_repo.seed(kg)
        await _grant_kg_manage(authz, kg.id.value, user_id)

        await service.delete(user_id=user_id, kg_id=kg.id.value)

        assert len(probe.knowledge_graph_deleted_calls) == 1
        assert probe.knowledge_graph_deleted_calls[0]["kg_id"] == kg.id.value

    @pytest.mark.asyncio
    async def test_delete_removes_credentials_for_data_sources_with_credentials_path(
        self,
        mock_session,
        kg_repo,
        ds_repo,
        authz,
        probe,
        user_id,
        tenant_id,
    ):
        """delete() calls secret_store.delete for each DS with a credentials_path.

        Given a knowledge graph with data sources — one with credentials and one
        without — when the knowledge graph is deleted, then the secret store's
        delete() is called only for the data source that has credentials, and
        the KG and both data sources are still removed from the database.
        """
        local_secret_store = InMemorySecretStoreRepository()

        service_with_secret_store = KnowledgeGraphService(
            session=mock_session,
            knowledge_graph_repository=kg_repo,
            data_source_repository=ds_repo,
            authz=authz,
            scope_to_tenant=tenant_id,
            probe=probe,
            secret_store=local_secret_store,
        )

        kg = _make_kg(tenant_id=tenant_id)
        ds_with_creds = _make_ds(
            ds_id="ds-001",
            kg_id=kg.id.value,
            tenant_id=tenant_id,
            credentials_path="datasource/ds-001/credentials",
        )
        ds_no_creds = _make_ds(
            ds_id="ds-002",
            kg_id=kg.id.value,
            tenant_id=tenant_id,
            credentials_path=None,
        )

        kg_repo.seed(kg)
        ds_repo.seed(ds_with_creds, ds_no_creds)
        await _grant_kg_manage(authz, kg.id.value, user_id)

        result = await service_with_secret_store.delete(
            user_id=user_id, kg_id=kg.id.value
        )

        assert result is True
        # Credentials deleted only for the DS that has a credentials_path
        assert len(local_secret_store.delete_calls) == 1
        assert (
            local_secret_store.delete_calls[0]["path"]
            == "datasource/ds-001/credentials"
        )
        assert local_secret_store.delete_calls[0]["tenant_id"] == tenant_id
        # Both data sources are deleted from the DB regardless
        assert len(ds_repo.deleted) == 2
        assert len(kg_repo.deleted) == 1

    @pytest.mark.asyncio
    async def test_delete_skips_credential_cleanup_when_no_secret_store(
        self,
        mock_session,
        kg_repo,
        ds_repo,
        authz,
        probe,
        user_id,
        tenant_id,
    ):
        """delete() gracefully skips credential cleanup when secret_store is None.

        If the service is constructed without a secret_store, data sources are
        still removed from the DB but credential blobs are left intact (acceptable
        for contexts where the secret store is not available).
        """
        service_no_secret_store = KnowledgeGraphService(
            session=mock_session,
            knowledge_graph_repository=kg_repo,
            data_source_repository=ds_repo,
            authz=authz,
            scope_to_tenant=tenant_id,
            probe=probe,
            secret_store=None,
        )

        kg = _make_kg(tenant_id=tenant_id)
        ds_with_creds = _make_ds(
            ds_id="ds-001",
            kg_id=kg.id.value,
            tenant_id=tenant_id,
            credentials_path="datasource/ds-001/credentials",
        )

        kg_repo.seed(kg)
        ds_repo.seed(ds_with_creds)
        await _grant_kg_manage(authz, kg.id.value, user_id)

        # Should not raise even though there's a credentials_path but no secret_store
        result = await service_no_secret_store.delete(
            user_id=user_id, kg_id=kg.id.value
        )

        assert result is True
        assert len(ds_repo.deleted) == 1
        assert len(kg_repo.deleted) == 1
