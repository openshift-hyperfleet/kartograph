"""Unit tests for agent runtime HTTP health endpoints."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from kartograph_agent_runtime import server


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(server.settings, "workspace_dir", str(tmp_path))
    monkeypatch.setattr(server.settings, "session_id", "session-test")
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
