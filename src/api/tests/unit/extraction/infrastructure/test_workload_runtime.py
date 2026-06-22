"""Unit tests for extraction workload runtime infrastructure adapters."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from extraction.infrastructure.workload_credential_issuer import DEFAULT_DEV_WORKLOAD_TOKEN_SIGNING_KEY
from extraction.infrastructure.workload_runtime import (
    InMemoryEphemeralExtractionWorkerLauncher,
    InMemoryStickySessionRuntimeManager,
    ScopedWorkloadCredentialIssuer,
)
from extraction.ports.runtime import (
    EphemeralWorkerLaunchRequest,
    ScopedWorkloadCredentials,
)


class TestInMemoryStickySessionRuntimeManager:
    def test_reuses_same_container_while_session_active(self) -> None:
        manager = InMemoryStickySessionRuntimeManager(session_ttl=timedelta(minutes=30))

        first = manager.get_or_start_runtime(
            session_id="session-1",
            user_id="user-1",
            knowledge_graph_id="kg-1",
            mode="extraction_operations",
        )
        second = manager.get_or_start_runtime(
            session_id="session-1",
            user_id="user-1",
            knowledge_graph_id="kg-1",
            mode="extraction_operations",
        )

        assert first.container_id == second.container_id
        assert first.status == "active"
        assert second.status == "active"

    def test_reset_rotates_container_for_same_session(self) -> None:
        manager = InMemoryStickySessionRuntimeManager(session_ttl=timedelta(minutes=30))
        original = manager.get_or_start_runtime(
            session_id="session-1",
            user_id="user-1",
            knowledge_graph_id="kg-1",
            mode="schema_bootstrap",
        )

        rotated = manager.reset_runtime(
            session_id="session-1",
            user_id="user-1",
            knowledge_graph_id="kg-1",
            mode="schema_bootstrap",
        )

        assert rotated.container_id != original.container_id
        assert rotated.status == "active"

    def test_terminate_runtime_removes_active_lease(self) -> None:
        manager = InMemoryStickySessionRuntimeManager(session_ttl=timedelta(minutes=30))
        lease = manager.get_or_start_runtime(
            session_id="session-1",
            user_id="user-1",
            knowledge_graph_id="kg-1",
            mode="schema_bootstrap",
        )

        manager.terminate_runtime(
            session_id="session-1",
            user_id="user-1",
            knowledge_graph_id="kg-1",
            mode="schema_bootstrap",
        )

        assert manager.is_runtime_active(session_id="session-1") is False
        replacement = manager.get_or_start_runtime(
            session_id="session-1",
            user_id="user-1",
            knowledge_graph_id="kg-1",
            mode="schema_bootstrap",
        )
        assert replacement.container_id != lease.container_id

    def test_cleanup_terminates_expired_sessions(self) -> None:
        manager = InMemoryStickySessionRuntimeManager(session_ttl=timedelta(minutes=5))
        lease = manager.get_or_start_runtime(
            session_id="session-1",
            user_id="user-1",
            knowledge_graph_id="kg-1",
            mode="schema_bootstrap",
        )
        cleanup_at = lease.last_activity_at + timedelta(minutes=6)

        terminated = manager.cleanup_expired(now=cleanup_at)

        assert terminated == [lease.container_id]
        replacement = manager.get_or_start_runtime(
            session_id="session-1",
            user_id="user-1",
            knowledge_graph_id="kg-1",
            mode="schema_bootstrap",
        )
        assert replacement.container_id != lease.container_id


class TestEphemeralWorkerLauncher:
    def test_launch_rejects_expired_credentials(self) -> None:
        issuer = ScopedWorkloadCredentialIssuer(signing_key=DEFAULT_DEV_WORKLOAD_TOKEN_SIGNING_KEY, default_ttl=timedelta(minutes=10))
        launcher = InMemoryEphemeralExtractionWorkerLauncher()
        scoped_credentials = issuer.issue(tenant_id="tenant-1", knowledge_graph_id="kg-1")
        expired_credentials = ScopedWorkloadCredentials(
            token=scoped_credentials.token,
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
            scopes=scoped_credentials.scopes,
        )
        request = EphemeralWorkerLaunchRequest(
            tenant_id="tenant-1",
            knowledge_graph_id="kg-1",
            session_id="session-1",
            sync_run_id="sync-1",
            job_package_id="pkg-1",
        )

        with pytest.raises(ValueError, match="expired"):
            launcher.launch(request=request, credentials=expired_credentials)

    def test_launch_requires_credentials_scoped_to_request(self) -> None:
        issuer = ScopedWorkloadCredentialIssuer(signing_key=DEFAULT_DEV_WORKLOAD_TOKEN_SIGNING_KEY, default_ttl=timedelta(minutes=10))
        launcher = InMemoryEphemeralExtractionWorkerLauncher()
        wrong_scope = issuer.issue(
            tenant_id="tenant-2",
            knowledge_graph_id="kg-2",
        )
        request = EphemeralWorkerLaunchRequest(
            tenant_id="tenant-1",
            knowledge_graph_id="kg-1",
            session_id="session-1",
            sync_run_id="sync-1",
            job_package_id="pkg-1",
        )

        with pytest.raises(ValueError, match="scope"):
            launcher.launch(request=request, credentials=wrong_scope)

    def test_launch_uses_ephemeral_worker_and_hides_credential_material(self) -> None:
        issuer = ScopedWorkloadCredentialIssuer(signing_key=DEFAULT_DEV_WORKLOAD_TOKEN_SIGNING_KEY, default_ttl=timedelta(minutes=10))
        launcher = InMemoryEphemeralExtractionWorkerLauncher()
        scoped_credentials = issuer.issue(tenant_id="tenant-1", knowledge_graph_id="kg-1")
        request = EphemeralWorkerLaunchRequest(
            tenant_id="tenant-1",
            knowledge_graph_id="kg-1",
            session_id="session-1",
            sync_run_id="sync-1",
            job_package_id="pkg-1",
        )

        result = launcher.launch(request=request, credentials=scoped_credentials)

        assert result.worker_id
        assert result.status == "running"
        assert result.credentials_expires_at > datetime.now(UTC)
        assert not hasattr(result, "token")
        assert launcher.active_worker_count == 1

    def test_complete_worker_terminates_container(self) -> None:
        issuer = ScopedWorkloadCredentialIssuer(signing_key=DEFAULT_DEV_WORKLOAD_TOKEN_SIGNING_KEY, default_ttl=timedelta(minutes=10))
        launcher = InMemoryEphemeralExtractionWorkerLauncher()
        scoped_credentials = issuer.issue(tenant_id="tenant-1", knowledge_graph_id="kg-1")
        request = EphemeralWorkerLaunchRequest(
            tenant_id="tenant-1",
            knowledge_graph_id="kg-1",
            session_id="session-1",
            sync_run_id="sync-1",
            job_package_id="pkg-1",
        )
        result = launcher.launch(request=request, credentials=scoped_credentials)

        launcher.complete_worker(result.worker_id)

        assert launcher.active_worker_count == 0


class TestScopedWorkloadCredentialIssuer:
    def test_issues_short_lived_credentials_with_least_privilege_scope(self) -> None:
        issuer = ScopedWorkloadCredentialIssuer(signing_key=DEFAULT_DEV_WORKLOAD_TOKEN_SIGNING_KEY, default_ttl=timedelta(minutes=15))

        issued = issuer.issue(tenant_id="tenant-9", knowledge_graph_id="kg-9")

        assert issued.expires_at > datetime.now(UTC)
        assert issued.scopes == (
            "tenant:tenant-9",
            "knowledge_graph:kg-9",
            "workload:extraction",
        )
        assert issued.token
