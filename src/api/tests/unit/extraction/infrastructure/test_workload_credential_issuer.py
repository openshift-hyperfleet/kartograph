"""Unit tests for scoped workload credential issuer."""

from __future__ import annotations

from datetime import timedelta

from extraction.infrastructure.workload_runtime import ScopedWorkloadCredentialIssuer


def test_issue_for_sticky_session_includes_chat_scope() -> None:
    issuer = ScopedWorkloadCredentialIssuer(default_ttl=timedelta(minutes=5))
    credentials = issuer.issue_for_sticky_session(
        tenant_id="tenant-1",
        knowledge_graph_id="kg-1",
    )

    assert "workload:chat" in credentials.scopes
    assert issuer.verify(credentials.token) == credentials


def test_verify_rejects_unknown_token() -> None:
    issuer = ScopedWorkloadCredentialIssuer(default_ttl=timedelta(minutes=5))
    assert issuer.verify("missing-token") is None
