"""Unit tests for workload auth scope validation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException

from extraction.infrastructure.workload_credential_issuer import (
    DEFAULT_DEV_WORKLOAD_TOKEN_SIGNING_KEY,
    ScopedWorkloadCredentialIssuer,
)
from extraction.presentation.workload_auth import (
    get_workload_auth_context,
    validate_workload_scope_id,
)
from extraction.ports.runtime import ScopedWorkloadCredentials


class _StubIssuer:
    def __init__(self, credentials: ScopedWorkloadCredentials) -> None:
        self._credentials = credentials

    def verify(self, token: str) -> ScopedWorkloadCredentials | None:
        if token == self._credentials.token:
            return self._credentials
        return None


def _credentials_with_scopes(*scopes: str) -> ScopedWorkloadCredentials:
    return ScopedWorkloadCredentials(
        token="test-token",
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
        scopes=scopes,
    )


def test_validate_workload_scope_id_accepts_ulid_like_values() -> None:
    assert validate_workload_scope_id("01JTESTPACK0000000000000000", field="tenant") == (
        "01JTESTPACK0000000000000000"
    )
    assert validate_workload_scope_id("tenant-1", field="tenant") == "tenant-1"


def test_validate_workload_scope_id_rejects_unsafe_characters() -> None:
    with pytest.raises(HTTPException) as exc:
        validate_workload_scope_id("../other-tenant", field="tenant")
    assert exc.value.status_code == 403
    assert "invalid tenant scope" in exc.value.detail


def test_get_workload_auth_context_accepts_valid_scopes() -> None:
    issuer = ScopedWorkloadCredentialIssuer(
        signing_key=DEFAULT_DEV_WORKLOAD_TOKEN_SIGNING_KEY,
        default_ttl=timedelta(minutes=5),
    )
    credentials = issuer.issue_for_sticky_session(
        tenant_id="tenant-1",
        knowledge_graph_id="kg-1",
        session_id="session-test-1",
    )

    auth = get_workload_auth_context(
        workload_token=credentials.token,
        issuer=issuer,
    )

    assert auth.tenant_id == "tenant-1"
    assert auth.knowledge_graph_id == "kg-1"
    assert auth.session_id == "session-test-1"


def test_get_workload_auth_context_rejects_invalid_tenant_scope() -> None:
    credentials = _credentials_with_scopes(
        "tenant:../escape",
        "knowledge_graph:kg-1",
        "workload:chat",
    )
    issuer = _StubIssuer(credentials)

    with pytest.raises(HTTPException) as exc:
        get_workload_auth_context(workload_token="test-token", issuer=issuer)

    assert exc.value.status_code == 403
    assert "invalid tenant scope" in exc.value.detail


def test_get_workload_auth_context_rejects_invalid_knowledge_graph_scope() -> None:
    credentials = _credentials_with_scopes(
        "tenant:tenant-1",
        "knowledge_graph:kg/1",
        "workload:chat",
    )
    issuer = _StubIssuer(credentials)

    with pytest.raises(HTTPException) as exc:
        get_workload_auth_context(workload_token="test-token", issuer=issuer)

    assert exc.value.status_code == 403
    assert "invalid knowledge_graph scope" in exc.value.detail


def test_get_workload_auth_context_rejects_invalid_session_scope() -> None:
    credentials = _credentials_with_scopes(
        "tenant:tenant-1",
        "knowledge_graph:kg-1",
        "workload:chat",
        "session:../../outside",
    )
    issuer = _StubIssuer(credentials)

    with pytest.raises(HTTPException) as exc:
        get_workload_auth_context(workload_token="test-token", issuer=issuer)

    assert exc.value.status_code == 403
    assert "invalid session scope" in exc.value.detail
