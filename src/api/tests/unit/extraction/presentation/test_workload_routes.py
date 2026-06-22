"""Unit tests for extraction workload schema routes."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from extraction.infrastructure.workload_credential_issuer import DEFAULT_DEV_WORKLOAD_TOKEN_SIGNING_KEY
from extraction.infrastructure.workload_credential_issuer import ScopedWorkloadCredentialIssuer
from extraction.presentation import workload_routes
from extraction.presentation.workload_auth import WorkloadAuthContext, get_workload_auth_context
from extraction.ports.workload_graph import WorkloadGraphNode, WorkloadGraphRelationship
from infrastructure.extraction_workload.dependencies import (
    get_graph_management_session_journal_service,
    get_workload_extraction_jobs_service,
    get_workload_graph_reader,
    get_workload_schema_service,
)
from infrastructure.database.exceptions import GraphQueryError
from management.domain.value_objects import EdgeTypeDefinition, NodeTypeDefinition, OntologyConfig


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

    async def validate_mutation_jsonl(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
        jsonl: str,
    ) -> dict[str, object]:
        return {"valid": True, "errors": [], "operation_count": 1}

    async def apply_mutation_jsonl(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
        jsonl: str,
    ) -> dict[str, object]:
        self.applied_jsonl = jsonl
        return {"applied": True, "errors": [], "operations_applied": 1, "applied_jsonl": jsonl}


class _FakeGraphReader:
    async def search_by_slug(self, **kwargs):
        return []

    async def list_instances_by_type(self, **kwargs):
        return (
            [
                WorkloadGraphNode(
                    id="service:abc",
                    entity_type="service",
                    slug="api-gateway",
                    properties={"name": "api-gateway"},
                )
            ],
            1,
        )

    async def count_entity_instances_by_type(self, **kwargs):
        entity_type = kwargs.get("entity_type")
        if entity_type == "service":
            return 1
        return 0

    async def list_relationship_instances(self, **kwargs):
        return (
            [
                WorkloadGraphRelationship(
                    id="contains:abc",
                    relationship_type="contains",
                    start_id="folder:aaa",
                    end_id="file:bbb",
                    source_slug="root-hyperfleet",
                    target_slug="pkg-api-example-go",
                    source_entity_type="folder",
                    target_entity_type="source_file",
                    properties={},
                )
            ],
            1,
        )

    async def count_relationship_instances(self, **kwargs):
        relationship_type = kwargs.get("relationship_type")
        if relationship_type == "contains":
            return 1
        return 0

    async def find_existing_node_ids(self, **kwargs):
        return frozenset()

    async def find_existing_edge_ids(self, **kwargs):
        return frozenset()

    async def find_existing_slugs_for_entity_type(self, **kwargs):
        return frozenset({"api-gateway"})

    async def partition_slugs_by_existence(self, **kwargs):
        slugs = tuple(kwargs.get("slugs") or ())
        existing = sorted(slug for slug in slugs if slug == "api-gateway")
        missing = sorted(slug for slug in slugs if slug != "api-gateway")
        return existing, missing


class _BrokenGraphReader(_FakeGraphReader):
    async def count_entity_instances_by_type(self, **kwargs):
        raise GraphQueryError("graph with oid 17491 does not exist", query="MATCH (n) RETURN n")


class _FakeSessionJournal:
    def __init__(self) -> None:
        self.appended: list[tuple[str, str]] = []

    async def append_applied_jsonl(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
        session_id: str,
        applied_jsonl: str,
    ) -> None:
        self.appended.append((session_id, applied_jsonl))


class _FakeExtractionJobsService:
    def __init__(self) -> None:
        self.saved_payload: dict[str, object] | None = None

    async def get_document(self, *, tenant_id: str, knowledge_graph_id: str) -> dict[str, object]:
        if self.saved_payload is None:
            return {"version": "1.0", "job_sets": [], "entity_types": [{"name": "Adapter", "instance_count": 19}]}
        return dict(self.saved_payload)

    async def save_document(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        self.saved_payload = {
            **payload,
            "entity_types": [{"name": "Adapter", "instance_count": 19}],
            "generated_jobs": 7,
        }
        return dict(self.saved_payload)

    async def get_plan_summary(self, *, tenant_id: str, knowledge_graph_id: str) -> dict[str, object]:
        job_sets = list((self.saved_payload or {}).get("job_sets") or [])
        return {
            "job_sets": [{**row, "projected_jobs": 7} for row in job_sets],
            "entity_types": [{"name": "Adapter", "instance_count": 19}],
        }

    async def get_database_status(self, *, tenant_id: str, knowledge_graph_id: str) -> dict[str, object]:
        return {
            "exists": True,
            "jobsByStatus": {"pending": 7, "in_progress": 0, "completed": 0, "failed": 0},
            "jobsBySet": {},
            "recentJobs": [],
            "activeWorkers": [],
            "avgCompletedJobSeconds": None,
            "entitiesByType": {"Adapter": 19},
            "entitiesTotal": 19,
            "hasInProgressJobs": False,
        }


@pytest.fixture
def workload_client() -> tuple[TestClient, _FakeSchemaService, str]:
    fake = _FakeSchemaService()
    extraction_jobs_fake = _FakeExtractionJobsService()
    session_journal_fake = _FakeSessionJournal()
    fake.saved = OntologyConfig(
        node_types=(
            NodeTypeDefinition(label="service", prepopulated=True, prepopulated_instance_count=0),
        ),
        edge_types=(
            EdgeTypeDefinition(
                label="contains",
                source_labels=("folder",),
                target_labels=("source_file",),
                prepopulated=True,
            ),
            EdgeTypeDefinition(
                label="depends_on",
                source_labels=("service",),
                target_labels=("service",),
            ),
        ),
    )
    issuer = ScopedWorkloadCredentialIssuer(signing_key=DEFAULT_DEV_WORKLOAD_TOKEN_SIGNING_KEY, default_ttl=__import__("datetime").timedelta(minutes=10))
    credentials = issuer.issue_for_sticky_session(
        tenant_id="tenant-1",
        knowledge_graph_id="kg-1",
        session_id="session-test-1",
    )

    app = FastAPI()
    app.include_router(workload_routes.router, prefix="/extraction")
    app.dependency_overrides[get_workload_schema_service] = lambda: fake
    app.dependency_overrides[get_workload_extraction_jobs_service] = lambda: extraction_jobs_fake
    app.dependency_overrides[get_workload_graph_reader] = lambda: _FakeGraphReader()
    app.dependency_overrides[get_graph_management_session_journal_service] = lambda: session_journal_fake
    app.dependency_overrides[get_workload_auth_context] = lambda: WorkloadAuthContext(
        credentials=credentials,
        tenant_id="tenant-1",
        knowledge_graph_id="kg-1",
        session_id="session-test-1",
    )

    client = TestClient(app)
    return client, fake, credentials.token, session_journal_fake


def test_workload_get_schema_authoring_guide(workload_client: tuple[TestClient, _FakeSchemaService, str]) -> None:
    client, _fake, token, _journal = workload_client
    response = client.get(
        "/extraction/workloads/schema/authoring-guide",
        headers={"X-Workload-Token": token},
    )
    assert response.status_code == 200
    assert "kartograph_get_schema_ontology" in response.json()["guide"]
    assert "PREPOPULATION_WORKFLOW.md" in response.json()["guide"]
    assert "case-sensitive" in response.json()["guide"]
    assert "Failure modes" in response.json()["guide"]


def test_workload_get_workspace_readiness(workload_client: tuple[TestClient, _FakeSchemaService, str]) -> None:
    client, _fake, token, _journal = workload_client
    response = client.get(
        "/extraction/workloads/schema/readiness",
        headers={"X-Workload-Token": token},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["knowledge_graph_id"] == "kg-1"
    assert payload["prepopulated_entity_types_without_instances_live"] == []
    assert payload["prepopulated_entity_types"][0]["live_instance_count"] == 1
    assert payload["prepopulated_entity_types"][0]["label"] == "service"


def test_workload_get_workspace_readiness_returns_503_for_graph_storage_errors() -> None:
    fake = _FakeSchemaService()
    fake.saved = OntologyConfig(
        node_types=(
            NodeTypeDefinition(label="service", prepopulated=True, prepopulated_instance_count=0),
        ),
        edge_types=(),
    )
    issuer = ScopedWorkloadCredentialIssuer(signing_key=DEFAULT_DEV_WORKLOAD_TOKEN_SIGNING_KEY, default_ttl=__import__("datetime").timedelta(minutes=10))
    credentials = issuer.issue_for_sticky_session(
        tenant_id="tenant-1",
        knowledge_graph_id="kg-1",
        session_id="session-broken",
    )
    app = FastAPI()
    app.include_router(workload_routes.router, prefix="/extraction")
    app.dependency_overrides[get_workload_schema_service] = lambda: fake
    app.dependency_overrides[get_workload_graph_reader] = lambda: _BrokenGraphReader()
    app.dependency_overrides[get_workload_extraction_jobs_service] = lambda: _FakeExtractionJobsService()
    app.dependency_overrides[get_graph_management_session_journal_service] = lambda: _FakeSessionJournal()
    app.dependency_overrides[get_workload_auth_context] = lambda: WorkloadAuthContext(
        credentials=credentials,
        tenant_id="tenant-1",
        knowledge_graph_id="kg-1",
        session_id="session-broken",
    )
    client = TestClient(app)
    response = client.get(
        "/extraction/workloads/schema/readiness",
        headers={"X-Workload-Token": credentials.token},
    )
    assert response.status_code == 503
    assert "dev-repair-age-graphs" in response.json()["detail"]


def test_workload_list_instances_by_type(workload_client: tuple[TestClient, _FakeSchemaService, str]) -> None:
    client, _fake, token, _journal = workload_client
    response = client.get(
        "/extraction/workloads/graph/instances",
        headers={"X-Workload-Token": token},
        params={"entity_type": "service"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["entity_type"] == "service"
    assert payload["count"] == 1
    assert payload["nodes"][0]["slug"] == "api-gateway"


def test_workload_list_relationship_instances(workload_client: tuple[TestClient, _FakeSchemaService, str]) -> None:
    client, _fake, token, _journal = workload_client
    response = client.get(
        "/extraction/workloads/graph/relationships",
        headers={"X-Workload-Token": token},
        params={
            "relationship_type": "contains",
            "source_entity_type": "folder",
            "target_entity_type": "source_file",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["relationship_type"] == "contains"
    assert payload["count"] == 1
    assert payload["relationships"][0]["source_slug"] == "root-hyperfleet"


def test_workload_save_schema_ontology(workload_client: tuple[TestClient, _FakeSchemaService, str]) -> None:
    client, fake, token, _journal = workload_client
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


def test_workload_check_graph_slugs(workload_client: tuple[TestClient, _FakeSchemaService, str]) -> None:
    client, _fake, token, _journal = workload_client
    response = client.post(
        "/extraction/workloads/graph/check-slugs",
        headers={"X-Workload-Token": token},
        json={"entity_type": "service", "slugs": ["api-gateway", "new-service"]},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["existing_slugs"] == ["api-gateway"]
    assert payload["missing_slugs"] == ["new-service"]


def test_workload_validate_graph_mutations(workload_client: tuple[TestClient, _FakeSchemaService, str]) -> None:
    client, _fake, token, _journal = workload_client
    response = client.post(
        "/extraction/workloads/mutations/validate",
        headers={"X-Workload-Token": token},
        json={"jsonl": '{"op":"CREATE","type":"node","id":"service:0123456789abcdef","label":"service","set_properties":{"name":"api","slug":"api","data_source_id":"bootstrap","source_path":"assistant"}}'},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is True
    assert payload["operation_count"] == 1


def test_workload_apply_graph_mutations_appends_session_journal(
    workload_client: tuple[TestClient, _FakeSchemaService, str, _FakeSessionJournal],
) -> None:
    client, _fake, token, journal = workload_client
    response = client.post(
        "/extraction/workloads/mutations/apply",
        headers={"X-Workload-Token": token},
        json={"jsonl": '{"op":"CREATE","type":"node","id":"service:0123456789abcdef","label":"service","set_properties":{"name":"api","slug":"api","data_source_id":"bootstrap","source_path":"assistant"}}'},
    )
    assert response.status_code == 200
    assert len(journal.appended) == 1
    assert journal.appended[0][0] == "session-test-1"
    assert "CREATE" in journal.appended[0][1]


def test_workload_apply_graph_mutations(workload_client: tuple[TestClient, _FakeSchemaService, str, _FakeSessionJournal]) -> None:
    client, fake, token, _journal = workload_client
    fake.saved = OntologyConfig(
        node_types=(
            NodeTypeDefinition(label="service", prepopulated=True, prepopulated_instance_count=0),
            NodeTypeDefinition(label="folder", prepopulated=True),
        ),
        edge_types=(),
    )
    response = client.post(
        "/extraction/workloads/mutations/apply",
        headers={"X-Workload-Token": token},
        json={"jsonl": '{"op":"CREATE","type":"node","id":"service:0123456789abcdef","label":"service","set_properties":{"name":"api","slug":"api","data_source_id":"bootstrap","source_path":"assistant"}}'},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["applied"] is True
    assert fake.applied_jsonl is not None
    assert payload["next_action"]
    assert "folder" in payload["remaining_entity_gaps"]


def test_workload_get_extraction_jobs_config(workload_client: tuple[TestClient, _FakeSchemaService, str]) -> None:
    client, _fake, token, _journal = workload_client
    response = client.get(
        "/extraction/workloads/extraction-jobs",
        headers={"X-Workload-Token": token},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["version"] == "1.0"
    assert payload["entity_types"][0]["name"] == "Adapter"
    assert payload["entity_types"][0]["instance_count"] == 19


def test_workload_save_extraction_jobs_config(workload_client: tuple[TestClient, _FakeSchemaService, str]) -> None:
    client, _fake, token, _journal = workload_client
    job_set = {
        "name": "Adapter Deep Extraction",
        "strategy": "by_instances",
        "entity_type": "Adapter",
        "instances_per_job": 3,
        "description": "Enrich each Adapter with implementation and config details.",
    }
    response = client.put(
        "/extraction/workloads/extraction-jobs",
        headers={"X-Workload-Token": token},
        json={"version": "1.0", "job_sets": [job_set]},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["generated_jobs"] == 7
    assert payload["job_sets"][0]["name"] == "Adapter Deep Extraction"


def test_workload_get_extraction_jobs_plan_summary(
    workload_client: tuple[TestClient, _FakeSchemaService, str],
) -> None:
    client, _fake, token, _journal = workload_client
    client.put(
        "/extraction/workloads/extraction-jobs",
        headers={"X-Workload-Token": token},
        json={
            "version": "1.0",
            "job_sets": [
                {
                    "name": "Adapter Deep Extraction",
                    "strategy": "by_instances",
                    "entity_type": "Adapter",
                    "instances_per_job": 3,
                    "description": "Enrich adapters.",
                }
            ],
        },
    )
    response = client.get(
        "/extraction/workloads/extraction-jobs/plan-summary",
        headers={"X-Workload-Token": token},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["job_sets"][0]["projected_jobs"] == 7


def test_workload_get_extraction_jobs_status(workload_client: tuple[TestClient, _FakeSchemaService, str]) -> None:
    client, _fake, token, _journal = workload_client
    response = client.get(
        "/extraction/workloads/extraction-jobs/status",
        headers={"X-Workload-Token": token},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["jobsByStatus"]["pending"] == 7
    assert payload["entitiesByType"]["Adapter"] == 19


def _read_only_workload_client() -> TestClient:
    fake = _FakeSchemaService()
    issuer = ScopedWorkloadCredentialIssuer(
        signing_key=DEFAULT_DEV_WORKLOAD_TOKEN_SIGNING_KEY,
        default_ttl=__import__("datetime").timedelta(minutes=10),
    )
    credentials = issuer.issue(
        tenant_id="tenant-1",
        knowledge_graph_id="kg-1",
        extra_scopes=("workload:read", "session:session-read-only"),
    )
    app = FastAPI()
    app.include_router(workload_routes.router, prefix="/extraction")
    app.dependency_overrides[get_workload_schema_service] = lambda: fake
    app.dependency_overrides[get_workload_extraction_jobs_service] = lambda: _FakeExtractionJobsService()
    app.dependency_overrides[get_workload_graph_reader] = lambda: _FakeGraphReader()
    app.dependency_overrides[get_graph_management_session_journal_service] = lambda: _FakeSessionJournal()
    app.dependency_overrides[get_workload_auth_context] = lambda: WorkloadAuthContext(
        credentials=credentials,
        tenant_id="tenant-1",
        knowledge_graph_id="kg-1",
        session_id="session-read-only",
    )
    return TestClient(app)


def test_read_only_workload_token_can_read_schema_ontology() -> None:
    client = _read_only_workload_client()
    response = client.get(
        "/extraction/workloads/schema/ontology",
        headers={"X-Workload-Token": "unused"},
    )
    assert response.status_code == 200


def test_read_only_workload_token_cannot_apply_mutations() -> None:
    client = _read_only_workload_client()
    response = client.post(
        "/extraction/workloads/mutations/apply",
        headers={"X-Workload-Token": "unused"},
        json={"jsonl": '{"op":"CREATE","type":"node","id":"service:0123456789abcdef","label":"service","set_properties":{"name":"api","slug":"api","data_source_id":"bootstrap","source_path":"assistant"}}'},
    )
    assert response.status_code == 403


def test_read_only_workload_token_cannot_save_extraction_jobs() -> None:
    client = _read_only_workload_client()
    response = client.put(
        "/extraction/workloads/extraction-jobs",
        headers={"X-Workload-Token": "unused"},
        json={"version": "1.0", "job_sets": []},
    )
    assert response.status_code == 403
