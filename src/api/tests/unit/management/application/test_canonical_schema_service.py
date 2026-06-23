"""Unit tests for canonical schema integration in KnowledgeGraphService."""

from __future__ import annotations

import pytest

from management.application.services.knowledge_graph_service import (
    KnowledgeGraphService,
)
from management.domain.value_objects import (
    EdgeTypeDefinition,
    NodeTypeDefinition,
    OntologyConfig,
)
from tests.fakes.authorization import InMemoryAuthorizationProvider
from tests.fakes.canonical_schema import InMemoryCanonicalSchemaRepository
from tests.fakes.management import (
    InMemoryDataSourceRepository,
    InMemoryKnowledgeGraphRepository,
    InMemorySecretStoreRepository,
    RecordingKnowledgeGraphServiceProbe,
)
from tests.unit.management.application.test_knowledge_graph_service import (
    _grant_kg_edit,
    _grant_kg_view,
    _make_kg,
)


@pytest.fixture
def canonical_schema_repo():
    return InMemoryCanonicalSchemaRepository()


@pytest.fixture
def service_with_canonical(
    mock_session, kg_repo, authz, canonical_schema_repo, tenant_id
):
    return KnowledgeGraphService(
        session=mock_session,
        knowledge_graph_repository=kg_repo,
        data_source_repository=InMemoryDataSourceRepository(),
        secret_store=InMemorySecretStoreRepository(),
        authz=authz,
        scope_to_tenant=tenant_id,
        probe=RecordingKnowledgeGraphServiceProbe(),
        canonical_schema_repository=canonical_schema_repo,
    )


@pytest.fixture
def mock_session():
    from unittest.mock import AsyncMock, MagicMock

    session = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.fixture
def kg_repo():
    return InMemoryKnowledgeGraphRepository()


@pytest.fixture
def authz():
    return InMemoryAuthorizationProvider()


@pytest.fixture
def tenant_id():
    return "tenant-123"


@pytest.fixture
def user_id():
    return "user-456"


class TestKnowledgeGraphServiceCanonicalSchema:
    @pytest.mark.asyncio
    async def test_save_ontology_writes_to_canonical_repository(
        self, service_with_canonical, canonical_schema_repo, authz, kg_repo, user_id
    ):
        kg = _make_kg()
        kg_repo.seed(kg)
        await _grant_kg_edit(authz, kg.id.value, user_id)
        config = OntologyConfig(
            node_types=(NodeTypeDefinition(label="Repository"),),
            edge_types=(
                EdgeTypeDefinition(
                    label="CONTAINS",
                    source_labels=("Repository",),
                    target_labels=("Repository",),
                ),
            ),
        )

        await service_with_canonical.save_ontology(
            user_id=user_id,
            kg_id=kg.id.value,
            config=config,
        )

        assert len(canonical_schema_repo.replaced) == 1
        assert canonical_schema_repo.replaced[0][0] == kg.id.value

    @pytest.mark.asyncio
    async def test_workspace_readiness_uses_canonical_schema(
        self, service_with_canonical, canonical_schema_repo, authz, kg_repo, user_id
    ):
        kg = _make_kg()
        kg_repo.seed(kg)
        canonical_schema_repo.seed(
            kg.id.value,
            OntologyConfig(
                node_types=(NodeTypeDefinition(label="Repository"),),
                edge_types=(
                    EdgeTypeDefinition(
                        label="CONTAINS",
                        source_labels=("Repository",),
                        target_labels=("Repository",),
                    ),
                ),
            ),
        )
        await _grant_kg_view(authz, kg.id.value, user_id)

        result = await service_with_canonical.get_workspace_status(
            user_id=user_id,
            kg_id=kg.id.value,
        )

        assert result is not None
        assert result.transition_eligible is True

    @pytest.mark.asyncio
    async def test_save_ontology_requires_canonical_repository_configuration(
        self, mock_session, kg_repo, authz, tenant_id, user_id
    ):
        service_without_canonical = KnowledgeGraphService(
            session=mock_session,
            knowledge_graph_repository=kg_repo,
            data_source_repository=InMemoryDataSourceRepository(),
            secret_store=InMemorySecretStoreRepository(),
            authz=authz,
            scope_to_tenant=tenant_id,
            probe=RecordingKnowledgeGraphServiceProbe(),
            canonical_schema_repository=None,
        )
        kg = _make_kg()
        kg_repo.seed(kg)
        await _grant_kg_edit(authz, kg.id.value, user_id)

        with pytest.raises(
            ValueError, match="Canonical schema repository is not configured"
        ):
            await service_without_canonical.save_ontology(
                user_id=user_id,
                kg_id=kg.id.value,
                config=OntologyConfig(),
            )
