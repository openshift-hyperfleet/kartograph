"""Unit tests for container-backed extraction workload runtime adapters."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock

import pytest

from extraction.infrastructure.container_workload_runtime import (
    ContainerEphemeralExtractionWorkerLauncher,
    ContainerStickySessionRuntimeManager,
)
from extraction.infrastructure.workload_credential_issuer import DEFAULT_DEV_WORKLOAD_TOKEN_SIGNING_KEY
from extraction.infrastructure.workload_runtime import ScopedWorkloadCredentialIssuer
from extraction.ports.runtime import EphemeralWorkerLaunchRequest
from shared_kernel.container_runtime.ports import ContainerRunResult, ContainerRunSpec


class TestContainerStickySessionRuntimeManager:
    def test_reuses_running_container_for_active_session(self) -> None:
        runtime = MagicMock()
        runtime.is_running.return_value = True
        runtime.container_id_for_name.return_value = None
        runtime.run.return_value = ContainerRunResult(
            container_id="container-1",
            name="kartograph-sticky-session-1",
        )
        manager = ContainerStickySessionRuntimeManager(
            container_runtime=runtime,
            sticky_image="busybox:1.36",
            sticky_command=("sleep", "3600"),
            session_ttl=timedelta(minutes=30),
        )

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

        assert first.container_id == second.container_id == "container-1"
        runtime.run.assert_called_once()

    def test_adopts_running_container_after_process_restart(self) -> None:
        runtime = MagicMock()
        runtime.is_running.return_value = True
        runtime.container_id_for_name.return_value = "container-existing"
        manager = ContainerStickySessionRuntimeManager(
            container_runtime=runtime,
            sticky_image="busybox:1.36",
            sticky_command=(),
            session_ttl=timedelta(minutes=30),
            container_network="kartograph_kartograph",
        )

        lease = manager.try_resolve_active_lease(
            session_id="session-1",
            user_id="user-1",
            knowledge_graph_id="kg-1",
            mode="schema_bootstrap",
        )

        assert lease is not None
        assert lease.container_id == "container-existing"
        runtime.run.assert_not_called()
        runtime.remove_by_name.assert_not_called()

    def test_removes_stopped_container_name_before_start(self) -> None:
        runtime = MagicMock()
        runtime.is_running.return_value = False
        runtime.container_id_for_name.return_value = None
        runtime.remove_by_name.return_value = True
        runtime.run.return_value = ContainerRunResult(
            container_id="container-1",
            name="kartograph-sticky-session-1",
        )
        manager = ContainerStickySessionRuntimeManager(
            container_runtime=runtime,
            sticky_image="busybox:1.36",
            sticky_command=("sleep", "3600"),
            session_ttl=timedelta(minutes=30),
        )

        lease = manager.get_or_start_runtime(
            session_id="session-1",
            user_id="user-1",
            knowledge_graph_id="kg-1",
            mode="extraction_operations",
        )

        assert lease.container_id == "container-1"
        runtime.remove_by_name.assert_called_once_with(
            "kartograph-sticky-session-1",
            force=True,
        )
        runtime.run.assert_called_once()

    def test_reset_stops_existing_container_and_starts_new_one(self) -> None:
        runtime = MagicMock()
        runtime.is_running.return_value = True
        runtime.container_id_for_name.return_value = None
        runtime.run.side_effect = [
            ContainerRunResult(container_id="container-1", name="name-1"),
            ContainerRunResult(container_id="container-2", name="name-2"),
        ]
        manager = ContainerStickySessionRuntimeManager(
            container_runtime=runtime,
            sticky_image="busybox:1.36",
            sticky_command=("sleep", "3600"),
            session_ttl=timedelta(minutes=30),
        )
        manager.get_or_start_runtime(
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

        assert rotated.container_id == "container-2"
        runtime.stop.assert_called_once_with("container-1")
        runtime.remove.assert_called_once_with("container-1", force=True)

    def test_cleanup_expired_terminates_and_returns_container_ids(self) -> None:
        runtime = MagicMock()
        runtime.is_running.return_value = True
        runtime.container_id_for_name.return_value = None
        runtime.run.return_value = ContainerRunResult(
            container_id="container-1",
            name="name-1",
        )
        manager = ContainerStickySessionRuntimeManager(
            container_runtime=runtime,
            sticky_image="busybox:1.36",
            sticky_command=("sleep", "3600"),
            session_ttl=timedelta(minutes=5),
        )
        lease = manager.get_or_start_runtime(
            session_id="session-1",
            user_id="user-1",
            knowledge_graph_id="kg-1",
            mode="schema_bootstrap",
        )

        terminated = manager.cleanup_expired(now=lease.expires_at + timedelta(seconds=1))

        assert terminated == ["container-1"]


class TestContainerEphemeralExtractionWorkerLauncher:
    def test_launch_starts_worker_container_without_exposing_credentials(self) -> None:
        runtime = MagicMock()
        runtime.run.return_value = ContainerRunResult(
            container_id="worker-container",
            name="kartograph-worker-abc",
        )
        launcher = ContainerEphemeralExtractionWorkerLauncher(
            container_runtime=runtime,
            worker_image="busybox:1.36",
            worker_command=("sleep", "3600"),
        )
        issuer = ScopedWorkloadCredentialIssuer(signing_key=DEFAULT_DEV_WORKLOAD_TOKEN_SIGNING_KEY, default_ttl=timedelta(minutes=10))
        credentials = issuer.issue(tenant_id="tenant-1", knowledge_graph_id="kg-1")
        request = EphemeralWorkerLaunchRequest(
            tenant_id="tenant-1",
            knowledge_graph_id="kg-1",
            session_id="session-1",
            sync_run_id="sync-1",
            job_package_id="pkg-1",
        )

        result = launcher.launch(request=request, credentials=credentials)

        assert result.worker_id
        assert result.status == "running"
        spec: ContainerRunSpec = runtime.run.call_args.args[0]
        assert spec.env["KARTOGRAPH_WORKLOAD_TOKEN"] == credentials.token

    def test_launch_rejects_invalid_credentials(self) -> None:
        runtime = MagicMock()
        launcher = ContainerEphemeralExtractionWorkerLauncher(
            container_runtime=runtime,
            worker_image="busybox:1.36",
            worker_command=("sleep", "3600"),
        )
        issuer = ScopedWorkloadCredentialIssuer(signing_key=DEFAULT_DEV_WORKLOAD_TOKEN_SIGNING_KEY, default_ttl=timedelta(minutes=10))
        wrong_scope = issuer.issue(tenant_id="tenant-2", knowledge_graph_id="kg-2")
        request = EphemeralWorkerLaunchRequest(
            tenant_id="tenant-1",
            knowledge_graph_id="kg-1",
            session_id="session-1",
            sync_run_id="sync-1",
            job_package_id="pkg-1",
        )

        with pytest.raises(ValueError, match="scope"):
            launcher.launch(request=request, credentials=wrong_scope)

    def test_complete_worker_terminates_running_container(self) -> None:
        runtime = MagicMock()
        runtime.is_running.return_value = True
        runtime.run.return_value = ContainerRunResult(
            container_id="worker-container",
            name="kartograph-worker-abc",
        )
        launcher = ContainerEphemeralExtractionWorkerLauncher(
            container_runtime=runtime,
            worker_image="busybox:1.36",
            worker_command=("sleep", "3600"),
        )
        issuer = ScopedWorkloadCredentialIssuer(signing_key=DEFAULT_DEV_WORKLOAD_TOKEN_SIGNING_KEY, default_ttl=timedelta(minutes=10))
        credentials = issuer.issue(tenant_id="tenant-1", knowledge_graph_id="kg-1")
        request = EphemeralWorkerLaunchRequest(
            tenant_id="tenant-1",
            knowledge_graph_id="kg-1",
            session_id="session-1",
            sync_run_id="sync-1",
            job_package_id="pkg-1",
        )
        result = launcher.launch(request=request, credentials=credentials)

        launcher.complete_worker(result.worker_id)

        runtime.stop.assert_called_once_with("worker-container")
        assert launcher.active_worker_count == 0
