"""Unit tests for scoped workload credential issuer."""

from __future__ import annotations

from datetime import timedelta

from extraction.infrastructure.workload_credential_issuer import (
    DEFAULT_DEV_WORKLOAD_TOKEN_SIGNING_KEY,
    ScopedWorkloadCredentialIssuer,
)


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
    assert issuer.verify("not-a-valid-jwt") is None


def test_verify_survives_new_issuer_instance_with_same_signing_key() -> None:
    signing_key = "shared-test-signing-key"
    issuer_a = ScopedWorkloadCredentialIssuer(
        signing_key=signing_key,
        default_ttl=timedelta(minutes=5),
    )
    credentials = issuer_a.issue_for_sticky_session(
        tenant_id="tenant-1",
        knowledge_graph_id="kg-1",
    )

    issuer_b = ScopedWorkloadCredentialIssuer(
        signing_key=signing_key,
        default_ttl=timedelta(minutes=5),
    )
    verified = issuer_b.verify(credentials.token)

    assert verified is not None
    assert verified.scopes == credentials.scopes
    assert verified.expires_at == credentials.expires_at


def test_verify_rejects_token_signed_with_different_key() -> None:
    issuer = ScopedWorkloadCredentialIssuer(
        signing_key="issuer-a-key",
        default_ttl=timedelta(minutes=5),
    )
    credentials = issuer.issue(tenant_id="tenant-1", knowledge_graph_id="kg-1")

    other_issuer = ScopedWorkloadCredentialIssuer(
        signing_key="issuer-b-key",
        default_ttl=timedelta(minutes=5),
    )

    assert other_issuer.verify(credentials.token) is None


def test_verify_rejects_expired_token() -> None:
    issuer = ScopedWorkloadCredentialIssuer(default_ttl=timedelta(seconds=-60))
    credentials = issuer.issue(tenant_id="tenant-1", knowledge_graph_id="kg-1")

    assert issuer.verify(credentials.token) is None


def test_rejects_empty_signing_key() -> None:
    try:
        ScopedWorkloadCredentialIssuer(signing_key="   ")
    except ValueError as exc:
        assert "signing key" in str(exc).lower()
    else:
        raise AssertionError("expected ValueError for empty signing key")


def test_default_dev_signing_key_is_stable() -> None:
    assert DEFAULT_DEV_WORKLOAD_TOKEN_SIGNING_KEY
