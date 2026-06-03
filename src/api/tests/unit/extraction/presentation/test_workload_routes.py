"""Unit tests for extraction workload schema routes."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from extraction.infrastructure.workload_runtime import ScopedWorkloadCredentialIssuer
from extraction.presentation import workload_routes
from extraction.presentation.workload_auth import WorkloadAuthContext, get_workload_auth_context
from infrastructure.extraction_workload.dependencies import get_workload_schema_service
from management.domain.value_objects import OntologyConfig


class _FakeSchemaService:
    def __init__(self) -> None:
        self.saved: OntologyConfig | None = None
        self.applied_jsonl: str | None = None

    async def get_ontology(self, *, knowledge_graph_id: str) -> OntologyConfig | None:
        return self.saved

    async def replace_ontology(
        self,
        *,
        knowledge_graph_id: str,
        config: OntologyConfig,
    ) -> OntologyConfig:
        self.saved = config
        return config

    async def apply_mutation_jsonl(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
        jsonl: str,
    ) -> dict[str, object]:
        self.applied_jsonl = jsonl
        return {"applied": True, "errors": []}


@pytest.fixture
def workload_client() -> tuple[TestClient, _FakeSchemaService, str]:
    fake = _FakeSchemaService()
    issuer = ScopedWorkloadCredentialIssuer(default_ttl=__import__("datetime").timedelta(minutes=10))
    credentials = issuer.issue_for_sticky_session(
        tenant_id="tenant-1",
        knowledge_graph_id="kg-1",
    )

    app = FastAPI()
    app.include_router(workload_routes.router, prefix="/extraction")
    app.dependency_overrides[get_workload_schema_service] = lambda: fake
    app.dependency_overrides[get_workload_auth_context] = lambda: WorkloadAuthContext(
        credentials=credentials,
        tenant_id="tenant-1",
        knowledge_graph_id="kg-1",
    )

    client = TestClient(app)
    return client, fake, credentials.token


def test_workload_get_schema_authoring_guide(workload_client: tuple[TestClient, _FakeSchemaService, str]) -> None:
    client, _fake, token = workload_client
    response = client.get(
        "/extraction/workloads/schema/authoring-guide",
        headers={"X-Workload-Token": token},
    )
    assert response.status_code == 200
    assert "kartograph_get_schema_ontology" in response.json()["guide"]


def test_workload_save_schema_ontology(workload_client: tuple[TestClient, _FakeSchemaService, str]) -> None:
    client, fake, token = workload_client
    response = client.put(
        "/extraction/workloads/schema/ontology",
        headers={"X-Workload-Token": token},
        json={
            "node_types": [
                {
                    "label": "service",
                    "description": "Service entity",
                    "required_properties": ["name"],
                    "optional_properties": [],
                    "prepopulated": False,
                    "prepopulated_instance_count": 0,
                }
            ],
            "edge_types": [
                {
                    "label": "depends_on",
                    "description": "Dependency",
                    "source_labels": ["service"],
                    "target_labels": ["service"],
                    "properties": [],
                }
            ],
        },
    )
    assert response.status_code == 200
    assert fake.saved is not None
    assert fake.saved.node_types[0].label == "service"
    assert fake.saved.edge_types[0].label == "depends_on"


def test_workload_apply_graph_mutations(workload_client: tuple[TestClient, _FakeSchemaService, str]) -> None:
    client, fake, token = workload_client
    response = client.post(
        "/extraction/workloads/mutations/apply",
        headers={"X-Workload-Token": token},
        json={"jsonl": '{"op":"CREATE","type":"node","id":"service:0123456789abcdef","label":"service","set_properties":{"name":"api","slug":"api","data_source_id":"bootstrap","source_path":"assistant"}}'},
    )
    assert response.status_code == 200
    assert response.json()["applied"] is True
    assert fake.applied_jsonl is not None
