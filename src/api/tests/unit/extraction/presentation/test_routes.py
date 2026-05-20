"""Unit tests for extraction session routes."""

from __future__ import annotations

from dataclasses import replace
import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from extraction.application.agent_session_service import ExtractionAgentSessionService
from extraction.domain.entities.agent_session import ExtractionAgentSession
from iam.application.value_objects import CurrentUser
from iam.domain.value_objects import TenantId, UserId


class _InMemoryAgentSessionRepository:
    def __init__(self) -> None:
        self._sessions: dict[str, ExtractionAgentSession] = {}

    async def save(self, session: ExtractionAgentSession) -> None:
        self._sessions[session.id] = replace(session)

    async def get_by_id(self, session_id: str) -> ExtractionAgentSession | None:
        session = self._sessions.get(session_id)
        return replace(session) if session else None

    async def find_active_by_scope(
        self,
        user_id: str,
        knowledge_graph_id: str,
        mode: ExtractionSessionMode,
    ) -> ExtractionAgentSession | None:
        for session in self._sessions.values():
            if (
                session.user_id == user_id
                and session.knowledge_graph_id == knowledge_graph_id
                and session.mode == mode
                and session.archived_at is None
            ):
                return replace(session)
        return None

    async def list_by_scope(
        self,
        user_id: str,
        knowledge_graph_id: str,
        mode: ExtractionSessionMode | None = None,
    ) -> list[ExtractionAgentSession]:
        rows = [
            replace(session)
            for session in self._sessions.values()
            if session.user_id == user_id
            and session.knowledge_graph_id == knowledge_graph_id
            and (mode is None or session.mode == mode)
        ]
        return sorted(rows, key=lambda s: s.updated_at, reverse=True)


class _AllowAllAuthz:
    async def check_permission(self, resource: str, permission: str, subject: str) -> bool:
        return True

    async def write_relationship(self, resource: str, relation: str, subject: str) -> None:
        return None

    async def write_relationships(self, relationships: list) -> None:
        return None

    async def delete_relationship(self, resource: str, relation: str, subject: str) -> None:
        return None

    async def delete_relationships(self, relationships: list) -> None:
        return None

    async def delete_relationships_by_filter(
        self,
        resource_type: str,
        resource_id: str | None = None,
        relation: str | None = None,
        subject_type: str | None = None,
        subject_id: str | None = None,
    ) -> None:
        return None

    async def bulk_check_permission(self, requests: list) -> set[str]:
        return set()

    async def lookup_subjects(
        self,
        resource: str,
        relation: str,
        subject_type: str,
        optional_subject_relation: str | None = None,
    ) -> list:
        return []

    async def lookup_resources(
        self,
        resource_type: str,
        permission: str,
        subject: str,
    ) -> list[str]:
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


@pytest.fixture
def extraction_client():
    from extraction.dependencies import get_extraction_agent_session_service
    from extraction.presentation import router
    from iam.dependencies.user import get_current_user
    from infrastructure.authorization_dependencies import get_spicedb_client

    app = FastAPI()
    repo = _InMemoryAgentSessionRepository()
    service = ExtractionAgentSessionService(repository=repo)
    app.dependency_overrides[get_extraction_agent_session_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        user_id=UserId(value="user-123"),
        username="alice",
        tenant_id=TenantId(value="t1"),
    )
    app.dependency_overrides[get_spicedb_client] = lambda: _AllowAllAuthz()
    app.include_router(router)
    return TestClient(app), service


class TestExtractionSessionRoutes:
    def test_clear_chat_archives_old_session_and_returns_fresh_session(
        self, extraction_client
    ):
        client, _ = extraction_client
        active = client.get(
            "/extraction/knowledge-graphs/kg-123/sessions/extraction_operations/active"
        )
        assert active.status_code == status.HTTP_200_OK
        old_id = active.json()["id"]

        response = client.post(
            "/extraction/knowledge-graphs/kg-123/sessions/extraction_operations/clear-chat"
        )
        assert response.status_code == status.HTTP_200_OK
        payload = response.json()
        assert payload["id"] != old_id
        assert payload["message_history"] == []
        assert payload["runtime_context"] == {}

        history_resp = client.get(
            "/extraction/knowledge-graphs/kg-123/sessions/extraction_operations"
        )
        assert history_resp.status_code == status.HTTP_200_OK
        history = history_resp.json()["sessions"]
        assert len(history) == 2
        assert any(row["id"] == old_id and row["archived_at"] is not None for row in history)

    def test_active_session_endpoint_returns_existing_active_session(
        self, extraction_client
    ):
        client, _ = extraction_client
        first = client.get(
            "/extraction/knowledge-graphs/kg-999/sessions/schema_bootstrap/active"
        )
        second = client.get(
            "/extraction/knowledge-graphs/kg-999/sessions/schema_bootstrap/active"
        )
        assert first.status_code == status.HTTP_200_OK
        assert second.status_code == status.HTTP_200_OK
        assert first.json()["id"] == second.json()["id"]

