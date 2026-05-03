"""Unit tests for DataSourceService.

Tests verify authorization checks, repository interactions,
credential storage, transaction management, and observability probe calls.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Callable
from unittest.mock import MagicMock

import pytest

from management.application.services.data_source_service import DataSourceService
from management.domain.aggregates import DataSource, KnowledgeGraph
from management.domain.entities import DataSourceSyncRun
from management.domain.value_objects import (
    DataSourceId,
    KnowledgeGraphId,
    Ontology,
    OntologyNodeType,
    Schedule,
    ScheduleType,
)
from management.ports.exceptions import UnauthorizedError
from shared_kernel.authorization.types import Permission
from shared_kernel.datasource_types import DataSourceAdapterType

# ---------------------------------------------------------------------------
# In-memory fakes
# ---------------------------------------------------------------------------


class _FakeDataSourceRepository:
    """In-memory fake for IDataSourceRepository."""

    def __init__(self) -> None:
        self._store: dict[str, DataSource] = {}
        self.saved: list[DataSource] = []

    def seed(self, *sources: DataSource) -> None:
        for ds in sources:
            self._store[ds.id.value] = ds

    async def get_by_id(self, data_source_id: DataSourceId | str) -> DataSource | None:
        key = (
            data_source_id if isinstance(data_source_id, str) else data_source_id.value
        )
        return self._store.get(key)

    async def find_by_knowledge_graph(
        self, knowledge_graph_id: str
    ) -> list[DataSource]:
        return [
            ds
            for ds in self._store.values()
            if ds.knowledge_graph_id == knowledge_graph_id
        ]

    async def save(self, data_source: DataSource) -> None:
        self._store[data_source.id.value] = data_source
        self.saved.append(data_source)

    async def delete(self, data_source: DataSource) -> bool:
        return self._store.pop(data_source.id.value, None) is not None

    async def find_all(self) -> list[DataSource]:
        return list(self._store.values())


class _FakeKnowledgeGraphRepository:
    """In-memory fake for IKnowledgeGraphRepository."""

    def __init__(self) -> None:
        self._store: dict[str, KnowledgeGraph] = {}

    def seed(self, *kgs: KnowledgeGraph) -> None:
        for kg in kgs:
            self._store[kg.id.value] = kg

    async def get_by_id(
        self, knowledge_graph_id: KnowledgeGraphId | str
    ) -> KnowledgeGraph | None:
        key = (
            knowledge_graph_id
            if isinstance(knowledge_graph_id, str)
            else knowledge_graph_id.value
        )
        return self._store.get(key)

    async def find_by_tenant(self, tenant_id: str) -> list[KnowledgeGraph]:
        return [kg for kg in self._store.values() if kg.tenant_id == tenant_id]

    async def save(self, knowledge_graph: KnowledgeGraph) -> None:
        self._store[knowledge_graph.id.value] = knowledge_graph

    async def delete(self, knowledge_graph: KnowledgeGraph) -> bool:
        return self._store.pop(knowledge_graph.id.value, None) is not None


class _FakeSecretStore:
    """In-memory fake for ISecretStoreRepository."""

    def __init__(self) -> None:
        self.store_calls: list[dict[str, Any]] = []
        self.delete_calls: list[dict[str, Any]] = []
        self._secrets: dict[tuple[str, str], dict[str, str]] = {}

    async def store(
        self, path: str, tenant_id: str, credentials: dict[str, str]
    ) -> None:
        call = {"path": path, "tenant_id": tenant_id, "credentials": credentials}
        self.store_calls.append(call)
        self._secrets[(path, tenant_id)] = credentials

    async def retrieve(self, path: str, tenant_id: str) -> dict[str, str]:
        return self._secrets.get((path, tenant_id), {})

    async def delete(self, path: str, tenant_id: str) -> bool:
        call = {"path": path, "tenant_id": tenant_id}
        self.delete_calls.append(call)
        return self._secrets.pop((path, tenant_id), None) is not None


class _FakeSyncRunRepository:
    """In-memory fake for IDataSourceSyncRunRepository."""

    def __init__(self) -> None:
        self._runs: dict[str, DataSourceSyncRun] = {}
        self.saved: list[DataSourceSyncRun] = []

    def seed(self, *runs: DataSourceSyncRun) -> None:
        for run in runs:
            self._runs[run.id] = run

    async def save(self, sync_run: DataSourceSyncRun) -> None:
        self._runs[sync_run.id] = sync_run
        self.saved.append(sync_run)

    async def get_by_id(self, sync_run_id: str) -> DataSourceSyncRun | None:
        return self._runs.get(sync_run_id)

    async def find_by_data_source(self, data_source_id: str) -> list[DataSourceSyncRun]:
        return [r for r in self._runs.values() if r.data_source_id == data_source_id]

    async def get_latest_for_data_source(
        self, data_source_id: str
    ) -> DataSourceSyncRun | None:
        runs = [r for r in self._runs.values() if r.data_source_id == data_source_id]
        if not runs:
            return None
        return max(runs, key=lambda r: r.created_at)


class _FakeAuthorizationProvider:
    """Configurable fake for AuthorizationProvider.

    Supports:
    - grant_all() / deny_all() — set default for all check_permission calls
    - grant_resource(resource) — grant a specific resource
    - set_check_fn(fn) — use a custom async function for check_permission
    - check_permission_calls — recorded list of calls for assertions
    """

    def __init__(self, default_grant: bool = False) -> None:
        self._default_grant = default_grant
        self._resource_grants: dict[str, bool] = {}
        self._check_fn: Callable | None = None
        self.check_permission_calls: list[dict[str, Any]] = []

    def grant_all(self) -> None:
        self._default_grant = True

    def deny_all(self) -> None:
        self._default_grant = False

    def grant_resource(self, resource: str) -> None:
        self._resource_grants[resource] = True

    def deny_resource(self, resource: str) -> None:
        self._resource_grants[resource] = False

    def set_check_fn(self, fn: Callable) -> None:
        """Set a custom async function for check_permission(resource, permission, subject)."""
        self._check_fn = fn

    def assert_check_called_once(
        self, resource: str, permission: str, subject: str
    ) -> None:
        assert len(self.check_permission_calls) == 1, (
            f"Expected check_permission called once, got {len(self.check_permission_calls)}"
        )
        call = self.check_permission_calls[0]
        assert call["resource"] == resource, (
            f"resource mismatch: {call['resource']!r} != {resource!r}"
        )
        assert call["permission"] == permission, (
            f"permission mismatch: {call['permission']!r} != {permission!r}"
        )
        assert call["subject"] == subject, (
            f"subject mismatch: {call['subject']!r} != {subject!r}"
        )

    async def check_permission(
        self, resource: str, permission: str, subject: str
    ) -> bool:
        self.check_permission_calls.append(
            {"resource": resource, "permission": permission, "subject": subject}
        )
        if self._check_fn is not None:
            return await self._check_fn(
                resource=resource, permission=permission, subject=subject
            )
        if resource in self._resource_grants:
            return self._resource_grants[resource]
        return self._default_grant

    async def bulk_check_permission(self, requests: list) -> set[str]:
        return set()

    async def write_relationship(
        self, resource: str, relation: str, subject: str
    ) -> None:
        pass

    async def write_relationships(self, relationships: list) -> None:
        pass

    async def delete_relationship(
        self, resource: str, relation: str, subject: str
    ) -> None:
        pass

    async def delete_relationships(self, relationships: list) -> None:
        pass

    async def delete_relationships_by_filter(
        self,
        resource_type: str,
        resource_id: str | None = None,
        relation: str | None = None,
        subject_type: str | None = None,
        subject_id: str | None = None,
    ) -> None:
        pass

    async def lookup_resources(
        self, resource_type: str, permission: str, subject: str
    ) -> list[str]:
        return []

    async def lookup_subjects(
        self,
        resource: str,
        relation: str,
        subject_type: str,
        optional_subject_relation: str | None = None,
    ) -> list:
        return []

    async def read_relationships(
        self,
        resource_type: str,
        resource_id: str | None = None,
        relation: str | None = None,
        subject_type: str | None = None,
        subject_id: str | None = None,
    ) -> list:
        return []


class _RecordingDataSourceServiceProbe:
    """Recording fake for DataSourceServiceProbe.

    Records all probe calls with kwargs for assertion.
    """

    def __init__(self) -> None:
        self.data_source_created_calls: list[dict[str, Any]] = []
        self.data_source_creation_failed_calls: list[dict[str, Any]] = []
        self.data_source_retrieved_calls: list[dict[str, Any]] = []
        self.data_source_updated_calls: list[dict[str, Any]] = []
        self.data_source_deleted_calls: list[dict[str, Any]] = []
        self.data_source_deletion_failed_calls: list[dict[str, Any]] = []
        self.data_sources_listed_calls: list[dict[str, Any]] = []
        self.sync_requested_calls: list[dict[str, Any]] = []
        self.permission_denied_calls: list[dict[str, Any]] = []

    def data_source_created(
        self, ds_id: str, kg_id: str, tenant_id: str, name: str
    ) -> None:
        self.data_source_created_calls.append(
            {"ds_id": ds_id, "kg_id": kg_id, "tenant_id": tenant_id, "name": name}
        )

    def data_source_creation_failed(self, kg_id: str, name: str, error: str) -> None:
        self.data_source_creation_failed_calls.append(
            {"kg_id": kg_id, "name": name, "error": error}
        )

    def data_source_retrieved(self, ds_id: str) -> None:
        self.data_source_retrieved_calls.append({"ds_id": ds_id})

    def data_source_updated(self, ds_id: str, name: str) -> None:
        self.data_source_updated_calls.append({"ds_id": ds_id, "name": name})

    def data_source_deleted(self, ds_id: str) -> None:
        self.data_source_deleted_calls.append({"ds_id": ds_id})

    def data_source_deletion_failed(self, ds_id: str, error: str) -> None:
        self.data_source_deletion_failed_calls.append({"ds_id": ds_id, "error": error})

    def data_sources_listed(self, kg_id: str, count: int) -> None:
        self.data_sources_listed_calls.append({"kg_id": kg_id, "count": count})

    def sync_requested(self, ds_id: str) -> None:
        self.sync_requested_calls.append({"ds_id": ds_id})

    def permission_denied(
        self, user_id: str, resource_id: str, permission: str
    ) -> None:
        self.permission_denied_calls.append(
            {"user_id": user_id, "resource_id": resource_id, "permission": permission}
        )

    def with_context(self, context: Any) -> "_RecordingDataSourceServiceProbe":
        return self


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# In-memory fakes
# ---------------------------------------------------------------------------


class _FakeDataSourceRepository:
    """In-memory fake for IDataSourceRepository."""

    def __init__(self) -> None:
        self._store: dict[str, DataSource] = {}
        self.saved: list[DataSource] = []

    def seed(self, *sources: DataSource) -> None:
        for ds in sources:
            self._store[ds.id.value] = ds

    async def get_by_id(self, data_source_id: DataSourceId | str) -> DataSource | None:
        key = (
            data_source_id if isinstance(data_source_id, str) else data_source_id.value
        )
        return self._store.get(key)

    async def find_by_knowledge_graph(
        self, knowledge_graph_id: str
    ) -> list[DataSource]:
        return [
            ds
            for ds in self._store.values()
            if ds.knowledge_graph_id == knowledge_graph_id
        ]

    async def save(self, data_source: DataSource) -> None:
        self._store[data_source.id.value] = data_source
        self.saved.append(data_source)

    async def delete(self, data_source: DataSource) -> bool:
        return self._store.pop(data_source.id.value, None) is not None

    async def find_all(self) -> list[DataSource]:
        return list(self._store.values())


class _FakeKnowledgeGraphRepository:
    """In-memory fake for IKnowledgeGraphRepository."""

    def __init__(self) -> None:
        self._store: dict[str, KnowledgeGraph] = {}

    def seed(self, *kgs: KnowledgeGraph) -> None:
        for kg in kgs:
            self._store[kg.id.value] = kg

    async def get_by_id(
        self, knowledge_graph_id: KnowledgeGraphId | str
    ) -> KnowledgeGraph | None:
        key = (
            knowledge_graph_id
            if isinstance(knowledge_graph_id, str)
            else knowledge_graph_id.value
        )
        return self._store.get(key)

    async def find_by_tenant(self, tenant_id: str) -> list[KnowledgeGraph]:
        return [kg for kg in self._store.values() if kg.tenant_id == tenant_id]

    async def save(self, knowledge_graph: KnowledgeGraph) -> None:
        self._store[knowledge_graph.id.value] = knowledge_graph

    async def delete(self, knowledge_graph: KnowledgeGraph) -> bool:
        return self._store.pop(knowledge_graph.id.value, None) is not None


class _FakeSecretStore:
    """In-memory fake for ISecretStoreRepository."""

    def __init__(self) -> None:
        self.store_calls: list[dict[str, Any]] = []
        self.delete_calls: list[dict[str, Any]] = []
        self._secrets: dict[tuple[str, str], dict[str, str]] = {}

    async def store(
        self, path: str, tenant_id: str, credentials: dict[str, str]
    ) -> None:
        call = {"path": path, "tenant_id": tenant_id, "credentials": credentials}
        self.store_calls.append(call)
        self._secrets[(path, tenant_id)] = credentials

    async def retrieve(self, path: str, tenant_id: str) -> dict[str, str]:
        return self._secrets.get((path, tenant_id), {})

    async def delete(self, path: str, tenant_id: str) -> bool:
        call = {"path": path, "tenant_id": tenant_id}
        self.delete_calls.append(call)
        return self._secrets.pop((path, tenant_id), None) is not None


class _FakeSyncRunRepository:
    """In-memory fake for IDataSourceSyncRunRepository."""

    def __init__(self) -> None:
        self._runs: dict[str, DataSourceSyncRun] = {}
        self.saved: list[DataSourceSyncRun] = []

    def seed(self, *runs: DataSourceSyncRun) -> None:
        for run in runs:
            self._runs[run.id] = run

    async def save(self, sync_run: DataSourceSyncRun) -> None:
        self._runs[sync_run.id] = sync_run
        self.saved.append(sync_run)

    async def get_by_id(self, sync_run_id: str) -> DataSourceSyncRun | None:
        return self._runs.get(sync_run_id)

    async def find_by_data_source(self, data_source_id: str) -> list[DataSourceSyncRun]:
        return [r for r in self._runs.values() if r.data_source_id == data_source_id]

    async def get_latest_for_data_source(
        self, data_source_id: str
    ) -> DataSourceSyncRun | None:
        runs = [r for r in self._runs.values() if r.data_source_id == data_source_id]
        if not runs:
            return None
        return max(runs, key=lambda r: r.created_at)


class _FakeAuthorizationProvider:
    """Configurable fake for AuthorizationProvider.

    Supports:
    - grant_all() / deny_all() — set default for all check_permission calls
    - grant_resource(resource) — grant a specific resource
    - set_check_fn(fn) — use a custom async function for check_permission
    - check_permission_calls — recorded list of calls for assertions
    """

    def __init__(self, default_grant: bool = False) -> None:
        self._default_grant = default_grant
        self._resource_grants: dict[str, bool] = {}
        self._check_fn: Callable | None = None
        self.check_permission_calls: list[dict[str, Any]] = []

    def grant_all(self) -> None:
        self._default_grant = True

    def deny_all(self) -> None:
        self._default_grant = False

    def grant_resource(self, resource: str) -> None:
        self._resource_grants[resource] = True

    def deny_resource(self, resource: str) -> None:
        self._resource_grants[resource] = False

    def set_check_fn(self, fn: Callable) -> None:
        """Set a custom async function for check_permission(resource, permission, subject)."""
        self._check_fn = fn

    def assert_check_called_once(
        self, resource: str, permission: str, subject: str
    ) -> None:
        assert len(self.check_permission_calls) == 1, (
            f"Expected check_permission called once, got {len(self.check_permission_calls)}"
        )
        call = self.check_permission_calls[0]
        assert call["resource"] == resource, (
            f"resource mismatch: {call['resource']!r} != {resource!r}"
        )
        assert call["permission"] == permission, (
            f"permission mismatch: {call['permission']!r} != {permission!r}"
        )
        assert call["subject"] == subject, (
            f"subject mismatch: {call['subject']!r} != {subject!r}"
        )

    async def check_permission(
        self, resource: str, permission: str, subject: str
    ) -> bool:
        self.check_permission_calls.append(
            {"resource": resource, "permission": permission, "subject": subject}
        )
        if self._check_fn is not None:
            return await self._check_fn(
                resource=resource, permission=permission, subject=subject
            )
        if resource in self._resource_grants:
            return self._resource_grants[resource]
        return self._default_grant

    async def bulk_check_permission(self, requests: list) -> set[str]:
        return set()

    async def write_relationship(
        self, resource: str, relation: str, subject: str
    ) -> None:
        pass

    async def write_relationships(self, relationships: list) -> None:
        pass

    async def delete_relationship(
        self, resource: str, relation: str, subject: str
    ) -> None:
        pass

    async def delete_relationships(self, relationships: list) -> None:
        pass

    async def delete_relationships_by_filter(
        self,
        resource_type: str,
        resource_id: str | None = None,
        relation: str | None = None,
        subject_type: str | None = None,
        subject_id: str | None = None,
    ) -> None:
        pass

    async def lookup_resources(
        self, resource_type: str, permission: str, subject: str
    ) -> list[str]:
        return []

    async def lookup_subjects(
        self,
        resource: str,
        relation: str,
        subject_type: str,
        optional_subject_relation: str | None = None,
    ) -> list:
        return []

    async def read_relationships(
        self,
        resource_type: str,
        resource_id: str | None = None,
        relation: str | None = None,
        subject_type: str | None = None,
        subject_id: str | None = None,
    ) -> list:
        return []


class _RecordingDataSourceServiceProbe:
    """Recording fake for DataSourceServiceProbe.

    Records all probe calls with kwargs for assertion.
    """

    def __init__(self) -> None:
        self.data_source_created_calls: list[dict[str, Any]] = []
        self.data_source_creation_failed_calls: list[dict[str, Any]] = []
        self.data_source_retrieved_calls: list[dict[str, Any]] = []
        self.data_source_updated_calls: list[dict[str, Any]] = []
        self.data_source_deleted_calls: list[dict[str, Any]] = []
        self.data_source_deletion_failed_calls: list[dict[str, Any]] = []
        self.data_sources_listed_calls: list[dict[str, Any]] = []
        self.sync_requested_calls: list[dict[str, Any]] = []
        self.permission_denied_calls: list[dict[str, Any]] = []

    def data_source_created(
        self, ds_id: str, kg_id: str, tenant_id: str, name: str
    ) -> None:
        self.data_source_created_calls.append(
            {"ds_id": ds_id, "kg_id": kg_id, "tenant_id": tenant_id, "name": name}
        )

    def data_source_creation_failed(self, kg_id: str, name: str, error: str) -> None:
        self.data_source_creation_failed_calls.append(
            {"kg_id": kg_id, "name": name, "error": error}
        )

    def data_source_retrieved(self, ds_id: str) -> None:
        self.data_source_retrieved_calls.append({"ds_id": ds_id})

    def data_source_updated(self, ds_id: str, name: str) -> None:
        self.data_source_updated_calls.append({"ds_id": ds_id, "name": name})

    def data_source_deleted(self, ds_id: str) -> None:
        self.data_source_deleted_calls.append({"ds_id": ds_id})

    def data_source_deletion_failed(self, ds_id: str, error: str) -> None:
        self.data_source_deletion_failed_calls.append({"ds_id": ds_id, "error": error})

    def data_sources_listed(self, kg_id: str, count: int) -> None:
        self.data_sources_listed_calls.append({"kg_id": kg_id, "count": count})

    def sync_requested(self, ds_id: str) -> None:
        self.sync_requested_calls.append({"ds_id": ds_id})

    def permission_denied(
        self, user_id: str, resource_id: str, permission: str
    ) -> None:
        self.permission_denied_calls.append(
            {"user_id": user_id, "resource_id": resource_id, "permission": permission}
        )

    def with_context(self, context: Any) -> "_RecordingDataSourceServiceProbe":
        return self


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session():
    """Create a mock AsyncSession with async commit."""
    session = MagicMock()
    session.commit = AsyncMock()
    return session


@pytest.fixture
def ds_repo() -> _FakeDataSourceRepository:
    """In-memory fake data source repository."""
    return _FakeDataSourceRepository()


@pytest.fixture
def kg_repo() -> _FakeKnowledgeGraphRepository:
    """In-memory fake knowledge graph repository."""
    return _FakeKnowledgeGraphRepository()


@pytest.fixture
def secret_store() -> _FakeSecretStore:
    """In-memory fake secret store."""
    return _FakeSecretStore()


@pytest.fixture
def sync_run_repo() -> _FakeSyncRunRepository:
    """In-memory fake sync run repository."""
    return _FakeSyncRunRepository()


@pytest.fixture
def authz() -> _FakeAuthorizationProvider:
    """Configurable fake authorization provider (default: deny all)."""
    return _FakeAuthorizationProvider(default_grant=False)


@pytest.fixture
def ds_probe() -> _RecordingDataSourceServiceProbe:
    """Recording fake for DataSourceServiceProbe."""
    return _RecordingDataSourceServiceProbe()


@pytest.fixture
def tenant_id():
    return "tenant-123"


@pytest.fixture
def user_id():
    return "user-456"


@pytest.fixture
def kg_id():
    return "kg-789"


@pytest.fixture
def service(
    mock_session,
    ds_repo,
    kg_repo,
    secret_store,
    sync_run_repo,
    authz,
    ds_probe,
    tenant_id,
):
    return DataSourceService(
        session=mock_session,
        data_source_repository=ds_repo,
        knowledge_graph_repository=kg_repo,
        secret_store=secret_store,
        sync_run_repository=sync_run_repo,
        authz=authz,
        scope_to_tenant=tenant_id,
        probe=ds_probe,
    )


def _make_kg(
    kg_id: str = "kg-789",
    tenant_id: str = "tenant-123",
    workspace_id: str = "ws-001",
) -> KnowledgeGraph:
    now = datetime.now(UTC)
    kg = KnowledgeGraph(
        id=KnowledgeGraphId(value=kg_id),
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        name="Test KG",
        description="A test KG",
        created_at=now,
        updated_at=now,
    )
    kg.collect_events()
    return kg


def _make_ds(
    ds_id: str = "ds-001",
    kg_id: str = "kg-789",
    tenant_id: str = "tenant-123",
    name: str = "Test DS",
    credentials_path: str | None = None,
) -> DataSource:
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


# ---- create ----


class TestDataSourceServiceCreate:
    """Tests for DataSourceService.create."""

    @pytest.mark.asyncio
    async def test_create_checks_edit_permission_on_kg(
        self, service, authz, user_id, kg_id, kg_repo, tenant_id
    ):
        """create() must check EDIT permission on the knowledge graph."""
        authz.grant_all()
        kg_repo.seed(_make_kg(kg_id=kg_id, tenant_id=tenant_id))

        await service.create(
            user_id=user_id,
            kg_id=kg_id,
            name="My DS",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={"url": "https://github.com"},
        )

        authz.assert_check_called_once(
            resource=f"knowledge_graph:{kg_id}",
            permission=Permission.EDIT,
            subject=f"user:{user_id}",
        )

    @pytest.mark.asyncio
    async def test_create_raises_unauthorized_when_permission_denied(
        self, service, authz, ds_probe, user_id, kg_id
    ):
        """create() raises UnauthorizedError when user lacks EDIT on KG."""
        authz.deny_all()

        with pytest.raises(UnauthorizedError):
            await service.create(
                user_id=user_id,
                kg_id=kg_id,
                name="My DS",
                adapter_type=DataSourceAdapterType.GITHUB,
                connection_config={"url": "https://github.com"},
            )

        assert len(ds_probe.permission_denied_calls) == 1

    @pytest.mark.asyncio
    async def test_create_verifies_kg_exists_and_belongs_to_tenant(
        self, service, authz, kg_repo, user_id, kg_id
    ):
        """create() raises ValueError when KG not found."""
        authz.grant_all()
        # kg_repo is empty — get_by_id returns None

        with pytest.raises(ValueError, match="not found"):
            await service.create(
                user_id=user_id,
                kg_id=kg_id,
                name="My DS",
                adapter_type=DataSourceAdapterType.GITHUB,
                connection_config={},
            )

    @pytest.mark.asyncio
    async def test_create_rejects_kg_from_different_tenant(
        self, service, authz, kg_repo, user_id, kg_id
    ):
        """create() raises ValueError when KG belongs to different tenant."""
        authz.grant_all()
        kg_repo.seed(_make_kg(kg_id=kg_id, tenant_id="other-tenant"))

        with pytest.raises(ValueError, match="different tenant"):
            await service.create(
                user_id=user_id,
                kg_id=kg_id,
                name="My DS",
                adapter_type=DataSourceAdapterType.GITHUB,
                connection_config={},
            )

    @pytest.mark.asyncio
    async def test_create_stores_credentials_when_provided(
        self,
        service,
        authz,
        kg_repo,
        secret_store,
        ds_repo,
        user_id,
        kg_id,
        tenant_id,
    ):
        """create() stores credentials via secret store when raw_credentials provided."""
        authz.grant_all()
        kg_repo.seed(_make_kg(kg_id=kg_id, tenant_id=tenant_id))
        creds = {"token": "abc123"}

        await service.create(
            user_id=user_id,
            kg_id=kg_id,
            name="My DS",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={"url": "https://github.com"},
            raw_credentials=creds,
        )

        assert len(secret_store.store_calls) == 1
        call_kwargs = secret_store.store_calls[0]
        assert "datasource/" in call_kwargs.get("path", "")
        assert call_kwargs.get("tenant_id") == tenant_id
        assert call_kwargs.get("credentials") == creds

    @pytest.mark.asyncio
    async def test_create_probes_success(
        self, service, authz, kg_repo, ds_probe, user_id, kg_id, tenant_id
    ):
        """create() calls probe on success."""
        authz.grant_all()
        kg_repo.seed(_make_kg(kg_id=kg_id, tenant_id=tenant_id))

        result = await service.create(
            user_id=user_id,
            kg_id=kg_id,
            name="My DS",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={},
        )

        assert len(ds_probe.data_source_created_calls) == 1
        call = ds_probe.data_source_created_calls[0]
        assert call["ds_id"] == result.id.value
        assert call["kg_id"] == kg_id
        assert call["tenant_id"] == tenant_id
        assert call["name"] == "My DS"


# ---- get ----


class TestDataSourceServiceGet:
    """Tests for DataSourceService.get."""

    @pytest.mark.asyncio
    async def test_get_returns_none_when_not_found(self, service, ds_repo, user_id):
        """get() returns None when DS not found."""
        # ds_repo is empty — returns None

        result = await service.get(user_id=user_id, ds_id="nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_checks_view_permission(self, service, authz, ds_repo, user_id):
        """get() checks VIEW permission on the data source."""
        ds = _make_ds()
        ds_repo.seed(ds)
        authz.grant_all()

        await service.get(user_id=user_id, ds_id=ds.id.value)

        authz.assert_check_called_once(
            resource=f"data_source:{ds.id.value}",
            permission=Permission.VIEW,
            subject=f"user:{user_id}",
        )

    @pytest.mark.asyncio
    async def test_get_returns_none_for_different_tenant(
        self, service, ds_repo, user_id
    ):
        """get() returns None when DS belongs to a different tenant."""
        ds = _make_ds(tenant_id="other-tenant")
        ds_repo.seed(ds)

        result = await service.get(user_id=user_id, ds_id=ds.id.value)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_returns_none_when_permission_denied(
        self, service, authz, ds_repo, user_id
    ):
        """get() returns None when user lacks VIEW (no existence leakage)."""
        ds = _make_ds()
        ds_repo.seed(ds)
        authz.deny_all()

        result = await service.get(user_id=user_id, ds_id=ds.id.value)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_returns_aggregate_on_success(
        self, service, authz, ds_repo, ds_probe, user_id
    ):
        """get() returns the aggregate when authorized."""
        ds = _make_ds()
        ds_repo.seed(ds)
        authz.grant_all()

        result = await service.get(user_id=user_id, ds_id=ds.id.value)

        assert result is ds
        assert len(ds_probe.data_source_retrieved_calls) == 1
        assert ds_probe.data_source_retrieved_calls[0]["ds_id"] == ds.id.value


# ---- list_for_knowledge_graph ----


class TestDataSourceServiceListForKnowledgeGraph:
    """Tests for DataSourceService.list_for_knowledge_graph."""

    @pytest.mark.asyncio
    async def test_list_checks_view_permission_on_kg(
        self, service, authz, ds_repo, kg_repo, user_id, kg_id, tenant_id
    ):
        """list_for_knowledge_graph() checks VIEW on the KG."""
        authz.grant_all()
        kg_repo.seed(_make_kg(kg_id=kg_id, tenant_id=tenant_id))
        # ds_repo is empty — returns []

        await service.list_for_knowledge_graph(user_id=user_id, kg_id=kg_id)

        authz.assert_check_called_once(
            resource=f"knowledge_graph:{kg_id}",
            permission=Permission.VIEW,
            subject=f"user:{user_id}",
        )

    @pytest.mark.asyncio
    async def test_list_raises_unauthorized_when_denied(
        self, service, authz, user_id, kg_id
    ):
        """list_for_knowledge_graph() raises UnauthorizedError when denied."""
        authz.deny_all()

        with pytest.raises(UnauthorizedError):
            await service.list_for_knowledge_graph(user_id=user_id, kg_id=kg_id)

    @pytest.mark.asyncio
    async def test_list_raises_unauthorized_when_kg_not_found(
        self, service, authz, kg_repo, user_id, kg_id
    ):
        """list_for_knowledge_graph() raises UnauthorizedError when KG not found."""
        authz.grant_all()
        # kg_repo is empty — returns None

        with pytest.raises(UnauthorizedError, match="not accessible"):
            await service.list_for_knowledge_graph(user_id=user_id, kg_id=kg_id)

    @pytest.mark.asyncio
    async def test_list_raises_unauthorized_for_different_tenant_kg(
        self, service, authz, kg_repo, user_id, kg_id
    ):
        """list_for_knowledge_graph() rejects KG belonging to different tenant."""
        authz.grant_all()
        kg_repo.seed(_make_kg(kg_id=kg_id, tenant_id="other-tenant"))

        with pytest.raises(UnauthorizedError, match="not accessible"):
            await service.list_for_knowledge_graph(user_id=user_id, kg_id=kg_id)

    @pytest.mark.asyncio
    async def test_list_returns_data_sources(
        self,
        service,
        authz,
        ds_repo,
        kg_repo,
        ds_probe,
        user_id,
        kg_id,
        tenant_id,
    ):
        """list_for_knowledge_graph() returns data sources from repo."""
        authz.grant_all()
        kg_repo.seed(_make_kg(kg_id=kg_id, tenant_id=tenant_id))
        ds1 = _make_ds(ds_id="ds-001", kg_id=kg_id)
        ds2 = _make_ds(ds_id="ds-002", kg_id=kg_id)
        ds_repo.seed(ds1, ds2)

        result = await service.list_for_knowledge_graph(user_id=user_id, kg_id=kg_id)

        assert len(result) == 2
        assert len(ds_probe.data_sources_listed_calls) == 1
        assert ds_probe.data_sources_listed_calls[0] == {"kg_id": kg_id, "count": 2}


# ---- update ----


class TestDataSourceServiceUpdate:
    """Tests for DataSourceService.update."""

    @pytest.mark.asyncio
    async def test_update_checks_edit_permission_on_ds(
        self, service, authz, ds_repo, user_id
    ):
        """update() checks EDIT permission on the data source."""
        ds = _make_ds()
        authz.grant_all()
        ds_repo.seed(ds)

        await service.update(
            user_id=user_id,
            ds_id=ds.id.value,
            name="Updated",
            connection_config={"url": "https://new.com"},
        )

        authz.assert_check_called_once(
            resource=f"data_source:{ds.id.value}",
            permission=Permission.EDIT,
            subject=f"user:{user_id}",
        )

    @pytest.mark.asyncio
    async def test_update_raises_unauthorized_when_denied(
        self, service, authz, user_id
    ):
        """update() raises UnauthorizedError when denied."""
        authz.deny_all()

        with pytest.raises(UnauthorizedError):
            await service.update(
                user_id=user_id,
                ds_id="ds-001",
                name="Updated",
            )

    @pytest.mark.asyncio
    async def test_update_raises_value_error_when_not_found(
        self, service, authz, ds_repo, user_id
    ):
        """update() raises ValueError when DS not found."""
        authz.grant_all()
        # ds_repo is empty — returns None

        with pytest.raises(ValueError):
            await service.update(
                user_id=user_id,
                ds_id="nonexistent",
                name="Updated",
            )

    @pytest.mark.asyncio
    async def test_update_rejects_different_tenant(
        self, service, authz, ds_repo, user_id
    ):
        """update() raises ValueError when DS belongs to a different tenant."""
        ds = _make_ds(tenant_id="other-tenant")
        authz.grant_all()
        ds_repo.seed(ds)

        with pytest.raises(ValueError):
            await service.update(
                user_id=user_id,
                ds_id=ds.id.value,
                name="Updated",
            )

    @pytest.mark.asyncio
    async def test_update_stores_credentials_when_provided(
        self, service, authz, ds_repo, secret_store, user_id, tenant_id
    ):
        """update() stores credentials via secret store when raw_credentials provided."""
        ds = _make_ds()
        authz.grant_all()
        ds_repo.seed(ds)
        creds = {"token": "new-token"}

        await service.update(
            user_id=user_id,
            ds_id=ds.id.value,
            raw_credentials=creds,
        )

        assert len(secret_store.store_calls) == 1
        call_kwargs = secret_store.store_calls[0]
        assert "datasource/" in call_kwargs.get("path", "")
        assert call_kwargs.get("tenant_id") == tenant_id
        assert call_kwargs.get("credentials") == creds

    @pytest.mark.asyncio
    async def test_update_probes_success(
        self, service, authz, ds_repo, ds_probe, user_id
    ):
        """update() probes success when name is updated."""
        ds = _make_ds()
        authz.grant_all()
        ds_repo.seed(ds)

        await service.update(
            user_id=user_id,
            ds_id=ds.id.value,
            name="Updated",
            connection_config={"url": "https://new.com"},
        )

        assert len(ds_probe.data_source_updated_calls) == 1
        assert ds_probe.data_source_updated_calls[0] == {
            "ds_id": ds.id.value,
            "name": "Updated",
        }


# ---- delete ----


class TestDataSourceServiceDelete:
    """Tests for DataSourceService.delete."""

    @pytest.mark.asyncio
    async def test_delete_checks_manage_permission_on_ds(
        self, service, authz, ds_repo, user_id
    ):
        """delete() checks MANAGE permission on the data source."""
        ds = _make_ds()
        authz.grant_all()
        ds_repo.seed(ds)

        await service.delete(user_id=user_id, ds_id=ds.id.value)

        authz.assert_check_called_once(
            resource=f"data_source:{ds.id.value}",
            permission=Permission.MANAGE,
            subject=f"user:{user_id}",
        )

    @pytest.mark.asyncio
    async def test_delete_raises_unauthorized_when_denied(
        self, service, authz, user_id
    ):
        """delete() raises UnauthorizedError when denied."""
        authz.deny_all()

        with pytest.raises(UnauthorizedError):
            await service.delete(user_id=user_id, ds_id="ds-001")

    @pytest.mark.asyncio
    async def test_delete_returns_false_when_not_found(
        self, service, authz, ds_repo, user_id
    ):
        """delete() returns False when DS not found."""
        authz.grant_all()
        # ds_repo is empty — get_by_id returns None

        result = await service.delete(user_id=user_id, ds_id="nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_returns_false_for_different_tenant(
        self, service, authz, ds_repo, user_id
    ):
        """delete() returns False when DS belongs to a different tenant."""
        ds = _make_ds(tenant_id="other-tenant")
        authz.grant_all()
        ds_repo.seed(ds)

        result = await service.delete(user_id=user_id, ds_id=ds.id.value)

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_removes_credentials_if_path_exists(
        self, service, authz, ds_repo, secret_store, user_id, tenant_id
    ):
        """delete() deletes credentials from secret store if credentials_path is set."""
        ds = _make_ds(credentials_path="datasource/ds-001/credentials")
        authz.grant_all()
        ds_repo.seed(ds)

        await service.delete(user_id=user_id, ds_id=ds.id.value)

        assert len(secret_store.delete_calls) == 1
        assert secret_store.delete_calls[0] == {
            "path": "datasource/ds-001/credentials",
            "tenant_id": tenant_id,
        }

    @pytest.mark.asyncio
    async def test_delete_probes_success(
        self, service, authz, ds_repo, ds_probe, user_id
    ):
        """delete() calls probe on success."""
        ds = _make_ds()
        authz.grant_all()
        ds_repo.seed(ds)

        await service.delete(user_id=user_id, ds_id=ds.id.value)

        assert len(ds_probe.data_source_deleted_calls) == 1
        assert ds_probe.data_source_deleted_calls[0]["ds_id"] == ds.id.value


# ---- trigger_sync ----


class TestDataSourceServiceTriggerSync:
    """Tests for DataSourceService.trigger_sync."""

    @pytest.mark.asyncio
    async def test_trigger_sync_checks_manage_permission(
        self, service, authz, ds_repo, sync_run_repo, user_id
    ):
        """trigger_sync() checks MANAGE permission on the data source."""
        ds = _make_ds()
        authz.grant_all()
        ds_repo.seed(ds)

        await service.trigger_sync(user_id=user_id, ds_id=ds.id.value)

        authz.assert_check_called_once(
            resource=f"data_source:{ds.id.value}",
            permission=Permission.MANAGE,
            subject=f"user:{user_id}",
        )

    @pytest.mark.asyncio
    async def test_trigger_sync_raises_unauthorized_when_denied(
        self, service, authz, user_id
    ):
        """trigger_sync() raises UnauthorizedError when denied."""
        authz.deny_all()

        with pytest.raises(UnauthorizedError):
            await service.trigger_sync(user_id=user_id, ds_id="ds-001")

    @pytest.mark.asyncio
    async def test_trigger_sync_raises_value_error_when_not_found(
        self, service, authz, ds_repo, user_id
    ):
        """trigger_sync() raises ValueError when DS not found."""
        authz.grant_all()
        # ds_repo is empty

        with pytest.raises(ValueError):
            await service.trigger_sync(user_id=user_id, ds_id="nonexistent")

    @pytest.mark.asyncio
    async def test_trigger_sync_rejects_different_tenant(
        self, service, authz, ds_repo, user_id
    ):
        """trigger_sync() raises ValueError when DS belongs to a different tenant."""
        ds = _make_ds(tenant_id="other-tenant")
        authz.grant_all()
        ds_repo.seed(ds)

        with pytest.raises(ValueError):
            await service.trigger_sync(user_id=user_id, ds_id=ds.id.value)

    @pytest.mark.asyncio
    async def test_trigger_sync_creates_sync_run_and_saves_ds(
        self, service, authz, ds_repo, sync_run_repo, ds_probe, user_id
    ):
        """trigger_sync() creates a sync run and saves the data source."""
        ds = _make_ds()
        authz.grant_all()
        ds_repo.seed(ds)

        result = await service.trigger_sync(user_id=user_id, ds_id=ds.id.value)

        assert result.data_source_id == ds.id.value
        assert result.status == "pending"
        assert len(sync_run_repo.saved) == 1
        assert len(ds_repo.saved) == 1
        assert len(ds_probe.sync_requested_calls) == 1
        assert ds_probe.sync_requested_calls[0]["ds_id"] == ds.id.value


class TestDataSourceServiceListAllForUser:
    """Unit tests for DataSourceService.list_all_for_user."""

    @pytest.mark.asyncio
    async def test_returns_all_data_sources_across_kgs(
        self,
        service: DataSourceService,
        kg_repo: _FakeKnowledgeGraphRepository,
        ds_repo: _FakeDataSourceRepository,
        sync_run_repo: _FakeSyncRunRepository,
        authz: _FakeAuthorizationProvider,
        user_id: str,
        tenant_id: str,
    ) -> None:
        """list_all_for_user() aggregates data sources from all accessible KGs."""
        kg1 = _make_kg(kg_id="kg-1", tenant_id=tenant_id)
        kg2 = _make_kg(kg_id="kg-2", tenant_id=tenant_id)
        ds1 = _make_ds(ds_id="ds-1", kg_id="kg-1", tenant_id=tenant_id)
        ds2 = _make_ds(ds_id="ds-2", kg_id="kg-2", tenant_id=tenant_id)
        now = datetime.now(UTC)
        run1 = DataSourceSyncRun(
            id="run-1",
            data_source_id="ds-1",
            status="completed",
            started_at=now,
            completed_at=now,
            error=None,
            created_at=now,
        )

        kg_repo.seed(kg1, kg2)
        authz.grant_all()
        ds_repo.seed(ds1, ds2)
        sync_run_repo.seed(run1)

        result = await service.list_all_for_user(user_id=user_id)

        assert len(result) == 2

        ds1_result = next(r for r in result if r.data_source.id.value == "ds-1")
        assert ds1_result.latest_sync_run is not None
        assert ds1_result.latest_sync_run.status == "completed"

        ds2_result = next(r for r in result if r.data_source.id.value == "ds-2")
        assert ds2_result.latest_sync_run is None

    @pytest.mark.asyncio
    async def test_excludes_kgs_user_cannot_view(
        self,
        service: DataSourceService,
        kg_repo: _FakeKnowledgeGraphRepository,
        ds_repo: _FakeDataSourceRepository,
        sync_run_repo: _FakeSyncRunRepository,
        authz: _FakeAuthorizationProvider,
        user_id: str,
        tenant_id: str,
    ) -> None:
        """list_all_for_user() excludes data sources from KGs the user cannot VIEW."""
        kg_allowed = _make_kg(kg_id="kg-allowed", tenant_id=tenant_id)
        kg_denied = _make_kg(kg_id="kg-denied", tenant_id=tenant_id)
        ds_allowed = _make_ds(
            ds_id="ds-allowed", kg_id="kg-allowed", tenant_id=tenant_id
        )

        kg_repo.seed(kg_allowed, kg_denied)
        authz.grant_resource("knowledge_graph:kg-allowed")
        authz.deny_resource("knowledge_graph:kg-denied")
        ds_repo.seed(ds_allowed)

        result = await service.list_all_for_user(user_id=user_id)

        assert len(result) == 1
        assert result[0].data_source.id.value == "ds-allowed"

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_accessible_kgs(
        self,
        service: DataSourceService,
        kg_repo: _FakeKnowledgeGraphRepository,
        authz: _FakeAuthorizationProvider,
        user_id: str,
    ) -> None:
        """list_all_for_user() returns empty list when user has no accessible KGs."""
        # kg_repo is empty

        result = await service.list_all_for_user(user_id=user_id)

        assert result == []

    @pytest.mark.asyncio
    async def test_data_source_with_no_sync_run_has_none_latest(
        self,
        service: DataSourceService,
        kg_repo: _FakeKnowledgeGraphRepository,
        ds_repo: _FakeDataSourceRepository,
        sync_run_repo: _FakeSyncRunRepository,
        authz: _FakeAuthorizationProvider,
        user_id: str,
        tenant_id: str,
    ) -> None:
        """list_all_for_user() sets latest_sync_run=None for sources with no runs."""
        kg = _make_kg(kg_id="kg-1", tenant_id=tenant_id)
        ds = _make_ds(ds_id="ds-1", kg_id="kg-1", tenant_id=tenant_id)

        kg_repo.seed(kg)
        authz.grant_all()
        ds_repo.seed(ds)
        # sync_run_repo is empty

        result = await service.list_all_for_user(user_id=user_id)

        assert len(result) == 1
        assert result[0].latest_sync_run is None
