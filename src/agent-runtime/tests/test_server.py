"""Unit tests for agent runtime HTTP health endpoints."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from kartograph_agent_runtime import server
from kartograph_agent_runtime.runtime_auth import RUNTIME_AUTH_HEADER


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(server.settings, "workspace_dir", str(tmp_path))
    monkeypatch.setattr(server.settings, "session_id", "session-test")
    monkeypatch.setattr(server.settings, "runtime_auth_token", "runtime-secret")
    return TestClient(server.app)


def test_health_returns_ok_when_workspace_marker_present(
    client: TestClient,
    tmp_path: Path,
) -> None:
    (tmp_path / "knowledge-graph-id").write_text("kg-1", encoding="utf-8")

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_returns_unavailable_when_workspace_marker_missing(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["status"] == "workspace_unavailable"


def test_turn_requires_runtime_auth_when_token_configured(
    client: TestClient,
    tmp_path: Path,
) -> None:
    (tmp_path / "knowledge-graph-id").write_text("kg-1", encoding="utf-8")

    unauthorized = client.post("/v1/turn", json={"message": "hello"})
    assert unauthorized.status_code == 401

    async def fake_stream(**_kwargs):
        yield {"type": "done", "ok": True}

    with patch("kartograph_agent_runtime.server.stream_turn_events", side_effect=fake_stream):
        authorized = client.post(
            "/v1/turn",
            json={"message": "hello"},
            headers={RUNTIME_AUTH_HEADER: "runtime-secret"},
        )

    assert authorized.status_code == 200
