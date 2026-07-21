"""Unit tests for local agent poll/claim/heartbeat/complete/fail routes."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from extraction.application.local_runtime_agent_service import (
    LocalRuntimeWorkRequestNotClaimableError,
)
from extraction.domain.local_runtime import (
    LocalRuntimeWorkKind,
    LocalRuntimeWorkRequest,
    LocalRuntimeWorkStatus,
)
from extraction.ports.vertex_credentials import (
    VertexInferenceToken,
    VertexInferenceTokenUnavailableError,
)
from iam.application.value_objects import CurrentUser
from iam.domain.value_objects import TenantId, UserId


def _work_request(**overrides) -> LocalRuntimeWorkRequest:
    defaults = dict(
        id="req-1",
        tenant_id="tenant-1",
        user_id="user-123",
        knowledge_graph_id="kg-1",
        kind=LocalRuntimeWorkKind.SANDBOX_START,
        status=LocalRuntimeWorkStatus.CLAIMED,
        session_id="sess-1",
        payload={"mode": "schema_bootstrap"},
        created_at=datetime.now(UTC),
    )
    defaults.update(overrides)
    return LocalRuntimeWorkRequest(**defaults)


class _FakeLocalRuntimeAgentService:
    def __init__(
        self,
        *,
        claim_queue: list[LocalRuntimeWorkRequest] | None = None,
        claimed_by_id: dict[str, LocalRuntimeWorkRequest] | None = None,
    ):
        self._claim_queue = list(claim_queue or [])
        self._claimed_by_id = dict(claimed_by_id or {})
        self.presence_polls: list[tuple[str, str]] = []
        self.rejected: list[tuple[str, str, str]] = []
        self.heartbeats: list[tuple[str, str]] = []
        self.completions: list[tuple[str, str, dict]] = []
        self.failures: list[tuple[str, str, str]] = []
        self.not_claimable_ids: set[str] = set()

    async def poll_and_claim(
        self, *, user_id: str, tenant_id: str
    ) -> LocalRuntimeWorkRequest | None:
        self.presence_polls.append((user_id, tenant_id))
        if self._claim_queue:
            return self._claim_queue.pop(0)
        return None

    async def reject_claim(self, *, request_id: str, user_id: str, reason: str) -> None:
        self.rejected.append((request_id, user_id, reason))

    async def heartbeat(self, *, request_id: str, user_id: str) -> None:
        self.heartbeats.append((request_id, user_id))
        if request_id in self.not_claimable_ids:
            raise LocalRuntimeWorkRequestNotClaimableError("not claimable")

    async def complete(
        self, *, request_id: str, user_id: str, result: dict | None = None
    ) -> None:
        self.completions.append((request_id, user_id, result or {}))
        if request_id in self.not_claimable_ids:
            raise LocalRuntimeWorkRequestNotClaimableError("not claimable")

    async def fail(self, *, request_id: str, user_id: str, failure_reason: str) -> None:
        self.failures.append((request_id, user_id, failure_reason))
        if request_id in self.not_claimable_ids:
            raise LocalRuntimeWorkRequestNotClaimableError("not claimable")

    async def get_claimed_request(
        self, *, request_id: str, user_id: str
    ) -> LocalRuntimeWorkRequest | None:
        return self._claimed_by_id.get(request_id)


class _FakeVertexInferenceTokenIssuer:
    def __init__(
        self,
        *,
        token: VertexInferenceToken | None = None,
        error: Exception | None = None,
    ):
        self.token = token or VertexInferenceToken(
            access_token="minted-token", expires_at=datetime.now(UTC)
        )
        self.error = error
        self.calls: list[tuple[str, str, str]] = []

    def mint_token(
        self, *, tenant_id: str, knowledge_graph_id: str, session_id: str
    ) -> VertexInferenceToken:
        self.calls.append((tenant_id, knowledge_graph_id, session_id))
        if self.error is not None:
            raise self.error
        return self.token


class _StubAuthz:
    def __init__(self, *, allowed: bool = True):
        self.allowed = allowed
        self.checks: list[tuple[str, str, str]] = []

    async def check_permission(
        self, resource: str, permission: str, subject: str
    ) -> bool:
        self.checks.append((resource, permission, subject))
        return self.allowed


@pytest.fixture
def _client_factory():
    from extraction.dependencies import (
        get_local_runtime_agent_service,
        get_vertex_inference_token_issuer,
    )
    from extraction.presentation import router
    from iam.dependencies.user import get_current_user
    from infrastructure.authorization_dependencies import get_spicedb_client

    def _build(
        *,
        service: _FakeLocalRuntimeAgentService,
        authz: _StubAuthz,
        vertex_issuer: _FakeVertexInferenceTokenIssuer | None = None,
    ) -> TestClient:
        app = FastAPI()
        app.dependency_overrides[get_local_runtime_agent_service] = lambda: service
        app.dependency_overrides[get_current_user] = lambda: CurrentUser(
            user_id=UserId(value="user-123"),
            username="alice",
            tenant_id=TenantId(value="tenant-1"),
        )
        app.dependency_overrides[get_spicedb_client] = lambda: authz
        app.dependency_overrides[get_vertex_inference_token_issuer] = (
            lambda: vertex_issuer or _FakeVertexInferenceTokenIssuer()
        )
        app.include_router(router)
        return TestClient(app)

    return _build


class TestPollForWork:
    def test_returns_204_when_no_work_pending(self, _client_factory) -> None:
        service = _FakeLocalRuntimeAgentService(claim_queue=[])
        client = _client_factory(service=service, authz=_StubAuthz(allowed=True))

        response = client.post("/extraction/local-runtime/poll")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert response.content == b""
        assert service.presence_polls == [("user-123", "tenant-1")]

    def test_returns_claimed_work_when_authorized(self, _client_factory) -> None:
        claimed = _work_request()
        service = _FakeLocalRuntimeAgentService(claim_queue=[claimed])
        client = _client_factory(service=service, authz=_StubAuthz(allowed=True))

        response = client.post("/extraction/local-runtime/poll")

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["id"] == "req-1"
        assert body["kind"] == "sandbox_start"
        assert body["session_id"] == "sess-1"
        assert body["payload"] == {"mode": "schema_bootstrap"}
        assert service.rejected == []

    def test_rejects_claim_and_returns_204_when_permission_revoked(
        self, _client_factory
    ) -> None:
        claimed = _work_request(knowledge_graph_id="kg-revoked")
        service = _FakeLocalRuntimeAgentService(claim_queue=[claimed])
        client = _client_factory(service=service, authz=_StubAuthz(allowed=False))

        response = client.post("/extraction/local-runtime/poll")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert response.content == b""
        assert len(service.rejected) == 1
        rejected_id, rejected_user, reason = service.rejected[0]
        assert rejected_id == "req-1"
        assert rejected_user == "user-123"
        assert "kg-revoked" in reason


class TestHeartbeat:
    def test_returns_204_on_success(self, _client_factory) -> None:
        service = _FakeLocalRuntimeAgentService()
        client = _client_factory(service=service, authz=_StubAuthz())

        response = client.post("/extraction/local-runtime/req-1/heartbeat")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert service.heartbeats == [("req-1", "user-123")]

    def test_returns_404_when_not_claimable(self, _client_factory) -> None:
        service = _FakeLocalRuntimeAgentService()
        service.not_claimable_ids.add("req-missing")
        client = _client_factory(service=service, authz=_StubAuthz())

        response = client.post("/extraction/local-runtime/req-missing/heartbeat")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestComplete:
    def test_returns_204_and_forwards_result(self, _client_factory) -> None:
        service = _FakeLocalRuntimeAgentService()
        client = _client_factory(service=service, authz=_StubAuthz())

        response = client.post(
            "/extraction/local-runtime/req-1/complete",
            json={"result": {"container_id": "sandbox-abc"}},
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert service.completions == [
            ("req-1", "user-123", {"container_id": "sandbox-abc"})
        ]

    def test_returns_404_when_not_claimable(self, _client_factory) -> None:
        service = _FakeLocalRuntimeAgentService()
        service.not_claimable_ids.add("req-1")
        client = _client_factory(service=service, authz=_StubAuthz())

        response = client.post(
            "/extraction/local-runtime/req-1/complete", json={"result": {}}
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestFail:
    def test_returns_204_and_forwards_reason(self, _client_factory) -> None:
        service = _FakeLocalRuntimeAgentService()
        client = _client_factory(service=service, authz=_StubAuthz())

        response = client.post(
            "/extraction/local-runtime/req-1/fail",
            json={"failure_reason": "Landlock enforcement unavailable"},
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert service.failures == [
            ("req-1", "user-123", "Landlock enforcement unavailable")
        ]

    def test_returns_404_when_not_claimable(self, _client_factory) -> None:
        service = _FakeLocalRuntimeAgentService()
        service.not_claimable_ids.add("req-1")
        client = _client_factory(service=service, authz=_StubAuthz())

        response = client.post(
            "/extraction/local-runtime/req-1/fail",
            json={"failure_reason": "whatever"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_rejects_empty_failure_reason(self, _client_factory) -> None:
        service = _FakeLocalRuntimeAgentService()
        client = _client_factory(service=service, authz=_StubAuthz())

        response = client.post(
            "/extraction/local-runtime/req-1/fail",
            json={"failure_reason": ""},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestVertexToken:
    def test_returns_minted_token_for_claimed_sandbox_start(
        self, _client_factory
    ) -> None:
        claimed = _work_request(kind=LocalRuntimeWorkKind.SANDBOX_START)
        service = _FakeLocalRuntimeAgentService(claimed_by_id={"req-1": claimed})
        expires_at = datetime(2026, 1, 1, tzinfo=UTC)
        issuer = _FakeVertexInferenceTokenIssuer(
            token=VertexInferenceToken(access_token="minted-abc", expires_at=expires_at)
        )
        client = _client_factory(
            service=service, authz=_StubAuthz(allowed=True), vertex_issuer=issuer
        )

        response = client.post("/extraction/local-runtime/req-1/vertex-token")

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["access_token"] == "minted-abc"
        assert issuer.calls == [("tenant-1", "kg-1", "sess-1")]

    def test_returns_404_when_not_claimed_by_caller(self, _client_factory) -> None:
        service = _FakeLocalRuntimeAgentService(claimed_by_id={})
        client = _client_factory(service=service, authz=_StubAuthz(allowed=True))

        response = client.post("/extraction/local-runtime/req-missing/vertex-token")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_returns_400_for_non_sandbox_start_kind(self, _client_factory) -> None:
        claimed = _work_request(kind=LocalRuntimeWorkKind.CHAT_TURN)
        service = _FakeLocalRuntimeAgentService(claimed_by_id={"req-1": claimed})
        client = _client_factory(service=service, authz=_StubAuthz(allowed=True))

        response = client.post("/extraction/local-runtime/req-1/vertex-token")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_returns_403_when_edit_permission_revoked(self, _client_factory) -> None:
        claimed = _work_request(
            kind=LocalRuntimeWorkKind.SANDBOX_START, knowledge_graph_id="kg-revoked"
        )
        service = _FakeLocalRuntimeAgentService(claimed_by_id={"req-1": claimed})
        client = _client_factory(service=service, authz=_StubAuthz(allowed=False))

        response = client.post("/extraction/local-runtime/req-1/vertex-token")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_returns_503_when_issuer_unavailable(self, _client_factory) -> None:
        claimed = _work_request(kind=LocalRuntimeWorkKind.SANDBOX_START)
        service = _FakeLocalRuntimeAgentService(claimed_by_id={"req-1": claimed})
        issuer = _FakeVertexInferenceTokenIssuer(
            error=VertexInferenceTokenUnavailableError("not configured")
        )
        client = _client_factory(
            service=service, authz=_StubAuthz(allowed=True), vertex_issuer=issuer
        )

        response = client.post("/extraction/local-runtime/req-1/vertex-token")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
