"""Integration tests for container-backed extraction workload runtime adapters."""

from __future__ import annotations

import time
from datetime import timedelta

import pytest
from ulid import ULID

from extraction.infrastructure.container_workload_runtime import (
    ContainerEphemeralExtractionWorkerLauncher,
    ContainerStickySessionRuntimeManager,
)
from extraction.infrastructure.workload_runtime import ScopedWorkloadCredentialIssuer
from extraction.ports.runtime import EphemeralWorkerLaunchRequest
from shared_kernel.container_runtime.ports import IContainerRuntime

pytestmark = [pytest.mark.integration, pytest.mark.container_runtime]

BUSYBOX_IMAGE = "docker.io/library/busybox:1.36"


@pytest.fixture(scope="module", autouse=True)
def ensure_busybox_image(container_runtime_engine: str) -> None:
    """Pull the lightweight image used by runtime integration tests."""
    import subprocess

    result = subprocess.run(
        [container_runtime_engine, "image", "inspect", BUSYBOX_IMAGE],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pull = subprocess.run(
            [container_runtime_engine, "pull", BUSYBOX_IMAGE],
            capture_output=True,
            text=True,
            check=False,
        )
        if pull.returncode != 0:
            pytest.skip(f"Unable to pull test image {BUSYBOX_IMAGE}: {pull.stderr}")


@pytest.fixture
def sticky_manager(container_runtime: IContainerRuntime) -> ContainerStickySessionRuntimeManager:
    return ContainerStickySessionRuntimeManager(
        container_runtime=container_runtime,
        sticky_image=BUSYBOX_IMAGE,
        sticky_command=("sleep", "3600"),
        session_ttl=timedelta(seconds=30),
    )


@pytest.fixture
def worker_launcher(
    container_runtime: IContainerRuntime,
) -> ContainerEphemeralExtractionWorkerLauncher:
    return ContainerEphemeralExtractionWorkerLauncher(
        container_runtime=container_runtime,
        worker_image=BUSYBOX_IMAGE,
        worker_command=("sleep", "3600"),
    )


class TestContainerStickySessionRuntimeIntegration:
    def test_happy_path_reuses_sticky_container_until_reset(
        self,
        sticky_manager: ContainerStickySessionRuntimeManager,
        container_runtime: IContainerRuntime,
    ) -> None:
        first = sticky_manager.get_or_start_runtime(
            session_id=f"integration-session-1-{ULID()}",
            user_id="user-1",
            knowledge_graph_id="kg-1",
            mode="extraction_operations",
        )
        second = sticky_manager.get_or_start_runtime(
            session_id=first.session_id,
            user_id="user-1",
            knowledge_graph_id="kg-1",
            mode="extraction_operations",
        )

        assert first.container_id == second.container_id
        assert container_runtime.is_running(first.container_id)

        rotated = sticky_manager.reset_runtime(
            session_id=first.session_id,
            user_id="user-1",
            knowledge_graph_id="kg-1",
            mode="extraction_operations",
        )

        assert rotated.container_id != first.container_id
        assert not container_runtime.is_running(first.container_id)
        assert container_runtime.is_running(rotated.container_id)

        sticky_manager.cleanup_expired(now=rotated.expires_at + timedelta(seconds=1))
        assert not container_runtime.is_running(rotated.container_id)

    def test_timeout_cleanup_terminates_expired_sticky_container(
        self,
        container_runtime: IContainerRuntime,
    ) -> None:
        manager = ContainerStickySessionRuntimeManager(
            container_runtime=container_runtime,
            sticky_image=BUSYBOX_IMAGE,
            sticky_command=("sleep", "3600"),
            session_ttl=timedelta(seconds=2),
        )
        lease = manager.get_or_start_runtime(
            session_id=f"integration-session-timeout-{ULID()}",
            user_id="user-1",
            knowledge_graph_id="kg-1",
            mode="schema_bootstrap",
        )
        assert container_runtime.is_running(lease.container_id)

        time.sleep(3)
        terminated = manager.cleanup_expired(
            now=lease.last_activity_at + timedelta(seconds=3)
        )

        assert terminated == [lease.container_id]
        assert not container_runtime.is_running(lease.container_id)


class TestContainerEphemeralWorkerIntegration:
    def test_happy_path_launches_and_completes_worker(
        self,
        worker_launcher: ContainerEphemeralExtractionWorkerLauncher,
        container_runtime: IContainerRuntime,
    ) -> None:
        issuer = ScopedWorkloadCredentialIssuer(default_ttl=timedelta(minutes=5))
        credentials = issuer.issue(tenant_id="tenant-1", knowledge_graph_id="kg-1")
        request = EphemeralWorkerLaunchRequest(
            tenant_id="tenant-1",
            knowledge_graph_id="kg-1",
            session_id=f"integration-session-worker-{ULID()}",
            sync_run_id="sync-1",
            job_package_id="pkg-1",
        )

        result = worker_launcher.launch(request=request, credentials=credentials)
        container_id = worker_launcher.worker_container_id(result.worker_id)

        assert container_id is not None
        assert container_runtime.is_running(container_id)

        worker_launcher.complete_worker(result.worker_id)

        assert worker_launcher.active_worker_count == 0
        assert not container_runtime.is_running(container_id)

    def test_failure_path_rejects_bad_credentials_without_launching_container(
        self,
        worker_launcher: ContainerEphemeralExtractionWorkerLauncher,
    ) -> None:
        issuer = ScopedWorkloadCredentialIssuer(default_ttl=timedelta(minutes=5))
        wrong_scope = issuer.issue(tenant_id="tenant-2", knowledge_graph_id="kg-2")
        request = EphemeralWorkerLaunchRequest(
            tenant_id="tenant-1",
            knowledge_graph_id="kg-1",
            session_id=f"integration-session-worker-{ULID()}",
            sync_run_id="sync-1",
            job_package_id="pkg-1",
        )

        with pytest.raises(ValueError, match="scope"):
            worker_launcher.launch(request=request, credentials=wrong_scope)

        assert worker_launcher.active_worker_count == 0
