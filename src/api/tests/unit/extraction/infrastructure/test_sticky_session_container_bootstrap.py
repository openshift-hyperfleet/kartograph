"""Unit tests for container sticky runtime bootstrap wiring."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from extraction.infrastructure.container_workload_runtime import (
    ContainerStickySessionRuntimeManager,
)
from extraction.infrastructure.workload_credential_issuer import DEFAULT_DEV_WORKLOAD_TOKEN_SIGNING_KEY
from extraction.infrastructure.workload_runtime import ScopedWorkloadCredentialIssuer
from extraction.ports.runtime import StickySessionRuntimeBootstrap
from shared_kernel.container_runtime.ports import ContainerRunResult, ContainerRunSpec


def test_start_runtime_mounts_skills_workspace_and_injects_token() -> None:
    runtime = MagicMock()
    runtime.is_running.return_value = False
    runtime.container_id_for_name.return_value = None
    runtime.run.return_value = ContainerRunResult(container_id="container-1", name="name-1")
    manager = ContainerStickySessionRuntimeManager(
        container_runtime=runtime,
        sticky_image="kartograph-agent-runtime:dev",
        sticky_command=(),
        session_ttl=timedelta(minutes=30),
        container_network="kartograph_kartograph",
        gcloud_config_mount="/host/.config/gcloud",
        gcloud_config_container_path="/gcloud/config",
        container_run_uid=1000,
        container_run_gid=1000,
        agent_max_turns=500,
    )
    issuer = ScopedWorkloadCredentialIssuer(signing_key=DEFAULT_DEV_WORKLOAD_TOKEN_SIGNING_KEY, default_ttl=timedelta(minutes=10))
    credentials = issuer.issue_for_sticky_session(
        tenant_id="tenant-1",
        knowledge_graph_id="kg-1",
        session_id="session-bootstrap",
    )
    bootstrap = StickySessionRuntimeBootstrap(
        tenant_id="tenant-1",
        credentials=credentials,
        host_session_work_dir="/tmp/session-work",
        api_base_url="http://api:8000",
    )

    lease = manager.get_or_start_runtime(
        session_id="session-1",
        user_id="user-1",
        knowledge_graph_id="kg-1",
        mode="schema_bootstrap",
        bootstrap=bootstrap,
    )

    spec: ContainerRunSpec = runtime.run.call_args.args[0]
    assert spec.command == ()
    assert spec.network == "kartograph_kartograph"
    assert "KARTOGRAPH_WORKLOAD_TOKEN" not in spec.env
    assert spec.env["KARTOGRAPH_RUNTIME_AUTH_TOKEN"]
    assert spec.cap_drop_all is True
    assert spec.read_only_rootfs is True
    assert spec.no_new_privileges is True
    assert spec.pids_limit == 256
    assert spec.memory_limit == "2g"
    assert "/tmp:rw,noexec,nosuid,size=512m" in spec.tmpfs_mounts
    assert "/tmp/session-work:/workspace" in spec.binds
    assert "/tmp/session-work/repository-files:/workspace/repository-files:ro" in spec.binds
    assert "/host/.config/gcloud:/gcloud/config:ro" in spec.binds
    assert spec.env["CLOUDSDK_CONFIG"] == "/gcloud/config"
    assert spec.env["GOOGLE_APPLICATION_CREDENTIALS"] == (
        "/gcloud/config/application_default_credentials.json"
    )
    assert spec.env["HOME"] == "/tmp"
    assert spec.env["KARTOGRAPH_AGENT_MAX_TURNS"] == "500"
    assert spec.user == "1000:1000"
    assert lease.runtime_base_url.startswith("http://kartograph-sticky-")
    assert lease.runtime_auth_token == spec.env["KARTOGRAPH_RUNTIME_AUTH_TOKEN"]
