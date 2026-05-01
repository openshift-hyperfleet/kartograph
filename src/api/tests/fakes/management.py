"""In-memory fakes for Management bounded context ports.

Provides fast, self-contained test doubles for:
- IKnowledgeGraphRepository
- IDataSourceRepository
- ISecretStoreRepository
- KnowledgeGraphServiceProbe

These fakes implement the full port protocols using in-memory storage and
record all mutation calls so tests can assert on behavior without resorting
to MagicMock or AsyncMock.  They follow the "Fakes over Mocks" principle
from specs/nfr/testing.spec.md.
"""

from __future__ import annotations

from management.domain.aggregates import DataSource, KnowledgeGraph
from management.domain.value_objects import DataSourceId, KnowledgeGraphId


# ---------------------------------------------------------------------------
# Repository fakes
# ---------------------------------------------------------------------------


class InMemoryKnowledgeGraphRepository:
    """In-memory fake implementing IKnowledgeGraphRepository.

    Stores KnowledgeGraph aggregates in a dict keyed by ULID string.
    Records all save and delete calls so tests can assert on interactions
    without using MagicMock.
    """

    def __init__(self) -> None:
        self._store: dict[str, KnowledgeGraph] = {}
        self.saved: list[KnowledgeGraph] = []
        self.deleted: list[KnowledgeGraph] = []

    def seed(self, *kgs: KnowledgeGraph) -> None:
        """Pre-populate the store (used in test setup)."""
        for kg in kgs:
            self._store[kg.id.value] = kg

    async def save(self, knowledge_graph: KnowledgeGraph) -> None:
        self.saved.append(knowledge_graph)
        self._store[knowledge_graph.id.value] = knowledge_graph

    async def get_by_id(
        self, knowledge_graph_id: KnowledgeGraphId
    ) -> KnowledgeGraph | None:
        return self._store.get(knowledge_graph_id.value)

    async def find_by_tenant(self, tenant_id: str) -> list[KnowledgeGraph]:
        return [kg for kg in self._store.values() if kg.tenant_id == tenant_id]

    async def delete(self, knowledge_graph: KnowledgeGraph) -> bool:
        self.deleted.append(knowledge_graph)
        if knowledge_graph.id.value in self._store:
            del self._store[knowledge_graph.id.value]
            return True
        return False


class InMemoryDataSourceRepository:
    """In-memory fake implementing IDataSourceRepository.

    Stores DataSource aggregates in a dict keyed by ULID string.
    Optionally appends to a shared ``call_log`` list on every ``delete``
    call so that cross-object call ordering can be asserted in tests.
    """

    def __init__(self, call_log: list[str] | None = None) -> None:
        self._store: dict[str, DataSource] = {}
        self._call_log = call_log
        self.saved: list[DataSource] = []
        self.deleted: list[DataSource] = []

    def seed(self, *data_sources: DataSource) -> None:
        """Pre-populate the store (used in test setup)."""
        for ds in data_sources:
            self._store[ds.id.value] = ds

    async def save(self, data_source: DataSource) -> None:
        self.saved.append(data_source)
        self._store[data_source.id.value] = data_source

    async def get_by_id(self, data_source_id: DataSourceId) -> DataSource | None:
        return self._store.get(data_source_id.value)

    async def find_by_knowledge_graph(
        self, knowledge_graph_id: str
    ) -> list[DataSource]:
        return [
            ds
            for ds in self._store.values()
            if ds.knowledge_graph_id == knowledge_graph_id
        ]

    async def delete(self, data_source: DataSource) -> bool:
        self.deleted.append(data_source)
        if self._call_log is not None:
            self._call_log.append("ds_repo.delete")
        if data_source.id.value in self._store:
            del self._store[data_source.id.value]
            return True
        return False

    async def find_all(self) -> list[DataSource]:
        return list(self._store.values())


class InMemorySecretStoreRepository:
    """In-memory fake implementing ISecretStoreRepository.

    Stores encrypted credentials in a dict keyed by (path, tenant_id).
    Records all delete calls so tests can assert on call count and arguments.
    Optionally appends to a shared ``call_log`` list on every ``delete``
    call so that cross-object call ordering can be asserted in tests.
    """

    def __init__(self, call_log: list[str] | None = None) -> None:
        self._store: dict[tuple[str, str], dict[str, str]] = {}
        self._call_log = call_log
        self.store_calls: list[dict[str, object]] = []
        self.retrieve_calls: list[dict[str, object]] = []
        self.delete_calls: list[dict[str, str]] = []

    async def store(
        self, path: str, tenant_id: str, credentials: dict[str, str]
    ) -> None:
        self.store_calls.append(
            {"path": path, "tenant_id": tenant_id, "credentials": credentials}
        )
        self._store[(path, tenant_id)] = credentials

    async def retrieve(self, path: str, tenant_id: str) -> dict[str, str]:
        self.retrieve_calls.append({"path": path, "tenant_id": tenant_id})
        key = (path, tenant_id)
        if key not in self._store:
            raise KeyError(f"No credentials at {path} for tenant {tenant_id}")
        return self._store[key]

    async def delete(self, path: str, tenant_id: str) -> bool:
        self.delete_calls.append({"path": path, "tenant_id": tenant_id})
        if self._call_log is not None:
            self._call_log.append("secret_store.delete")
        key = (path, tenant_id)
        existed = key in self._store
        self._store.pop(key, None)
        return existed


# ---------------------------------------------------------------------------
# Probe fake
# ---------------------------------------------------------------------------


class RecordingKnowledgeGraphServiceProbe:
    """Concrete recording probe implementing KnowledgeGraphServiceProbe protocol.

    Records every method call in per-method lists so tests can assert on
    which events were raised and what arguments were passed.  This is a
    concrete class — NOT a MagicMock(spec=...) — as required by the testing
    NFR (specs/nfr/testing.spec.md).
    """

    def __init__(self) -> None:
        self.knowledge_graph_created_calls: list[dict[str, str]] = []
        self.knowledge_graph_creation_failed_calls: list[dict[str, str]] = []
        self.knowledge_graph_retrieved_calls: list[dict[str, str]] = []
        self.knowledge_graph_updated_calls: list[dict[str, str]] = []
        self.knowledge_graph_deleted_calls: list[dict[str, str]] = []
        self.knowledge_graph_deletion_failed_calls: list[dict[str, str]] = []
        self.knowledge_graphs_listed_calls: list[dict[str, object]] = []
        self.permission_denied_calls: list[dict[str, str]] = []

    def knowledge_graph_created(
        self,
        kg_id: str,
        tenant_id: str,
        workspace_id: str,
        name: str,
    ) -> None:
        self.knowledge_graph_created_calls.append(
            {
                "kg_id": kg_id,
                "tenant_id": tenant_id,
                "workspace_id": workspace_id,
                "name": name,
            }
        )

    def knowledge_graph_creation_failed(
        self,
        tenant_id: str,
        name: str,
        error: str,
    ) -> None:
        self.knowledge_graph_creation_failed_calls.append(
            {"tenant_id": tenant_id, "name": name, "error": error}
        )

    def knowledge_graph_retrieved(self, kg_id: str) -> None:
        self.knowledge_graph_retrieved_calls.append({"kg_id": kg_id})

    def knowledge_graph_updated(self, kg_id: str, name: str) -> None:
        self.knowledge_graph_updated_calls.append({"kg_id": kg_id, "name": name})

    def knowledge_graph_deleted(self, kg_id: str) -> None:
        self.knowledge_graph_deleted_calls.append({"kg_id": kg_id})

    def knowledge_graph_deletion_failed(self, kg_id: str, error: str) -> None:
        self.knowledge_graph_deletion_failed_calls.append(
            {"kg_id": kg_id, "error": error}
        )

    def knowledge_graphs_listed(self, workspace_id: str, count: int) -> None:
        self.knowledge_graphs_listed_calls.append(
            {"workspace_id": workspace_id, "count": count}
        )

    def permission_denied(
        self,
        user_id: str,
        resource_id: str,
        permission: str,
    ) -> None:
        self.permission_denied_calls.append(
            {
                "user_id": user_id,
                "resource_id": resource_id,
                "permission": permission,
            }
        )

    def with_context(self, context: object) -> "RecordingKnowledgeGraphServiceProbe":
        """Return self — context is not used in tests."""
        return self
