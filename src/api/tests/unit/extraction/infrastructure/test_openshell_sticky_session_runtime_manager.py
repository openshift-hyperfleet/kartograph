"""Unit tests for OpenShell sticky session runtime manager."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

from extraction.infrastructure.openshell.openshell_sticky_session_runtime_manager import (
    OpenShellStickySessionRuntimeManager,
)
from extraction.infrastructure.workload_credential_issuer import DEFAULT_DEV_WORKLOAD_TOKEN_SIGNING_KEY
from extraction.infrastructure.workload_credential_issuer import ScopedWorkloadCredentialIssuer
from extraction.ports.runtime import StickySessionRuntimeBootstrap


class TestOpenShellStickySessionRuntimeManager:
    def test_start_runtime_issues_auth_token_and_runtime_url(self) -> None:
        manager = OpenShellStickySessionRuntimeManager(
            sticky_image="kartograph-agent-runtime:dev",
            session_ttl=timedelta(minutes=30),
            runtime_host="host.docker.internal",
            forward_port_base=18787,
        )
        issuer = ScopedWorkloadCredentialIssuer(signing_key=DEFAULT_DEV_WORKLOAD_TOKEN_SIGNING_KEY, default_ttl=timedelta(minutes=10))
        credentials = issuer.issue_for_sticky_session(
            tenant_id="tenant-1",
            knowledge_graph_id="kg-1",
            session_id="session-1",
        )
        bootstrap = StickySessionRuntimeBootstrap(
            tenant_id="tenant-1",
            credentials=credentials,
            host_session_work_dir="/tmp/session-work",
            api_base_url="http://api:8000",
            ui_mode="initial-schema-design",
        )

        with patch(
            "extraction.infrastructure.openshell.openshell_sticky_session_runtime_manager.openshell_gateway.ensure_gateway_registered"
        ), patch(
            "extraction.infrastructure.openshell.openshell_sticky_session_runtime_manager.openshell_sandbox.delete_sandbox"
        ), patch(
            "extraction.infrastructure.openshell.openshell_sticky_session_runtime_manager.openshell_sandbox.create_sandbox"
        ), patch(
            "extraction.infrastructure.openshell.openshell_sticky_session_runtime_manager.openshell_sandbox.upload_directory_contents"
        ), patch(
            "extraction.infrastructure.openshell.openshell_sticky_session_runtime_manager.openshell_sandbox.apply_policy"
        ) as apply_policy, patch(
            "extraction.infrastructure.openshell.openshell_sticky_session_runtime_manager.openshell_sandbox.exec_background"
        ), patch(
            "extraction.infrastructure.openshell.openshell_sticky_session_runtime_manager.openshell_sandbox.start_forward"
        ), patch(
            "extraction.infrastructure.openshell.openshell_sticky_session_runtime_manager.openshell_sandbox.emit_lifecycle"
        ):
            lease = manager.get_or_start_runtime(
                session_id="session-1",
                user_id="user-1",
                knowledge_graph_id="kg-1",
                mode="graph_management",
                bootstrap=bootstrap,
            )

        assert lease.runtime_auth_token
        assert lease.runtime_base_url.startswith("http://host.docker.internal:")
        apply_policy.assert_called_once()
        assert apply_policy.call_args.kwargs["ui_mode"] == "initial-schema-design"

    def test_start_runtime_ensures_vertex_provider(self) -> None:
        manager = OpenShellStickySessionRuntimeManager(
            sticky_image="kartograph-agent-runtime:dev",
            session_ttl=timedelta(minutes=30),
            vertex_enabled=True,
            vertex_project_id="my-project",
            vertex_region="us-east5",
            gcloud_config_mount="/host/.config/gcloud",
        )

        with patch(
            "extraction.infrastructure.openshell.openshell_sticky_session_runtime_manager.openshell_gateway.ensure_gateway_registered"
        ), patch(
            "extraction.infrastructure.openshell.openshell_sticky_session_runtime_manager.ensure_vertex_provider"
        ) as ensure_provider, patch(
            "extraction.infrastructure.openshell.openshell_sticky_session_runtime_manager.openshell_sandbox.delete_sandbox"
        ), patch(
            "extraction.infrastructure.openshell.openshell_sticky_session_runtime_manager.openshell_sandbox.create_sandbox"
        ), patch(
            "extraction.infrastructure.openshell.openshell_sticky_session_runtime_manager.openshell_sandbox.apply_policy"
        ), patch(
            "extraction.infrastructure.openshell.openshell_sticky_session_runtime_manager.openshell_sandbox.exec_background"
        ) as exec_background, patch(
            "extraction.infrastructure.openshell.openshell_sticky_session_runtime_manager.openshell_sandbox.start_forward"
        ), patch(
            "extraction.infrastructure.openshell.openshell_sticky_session_runtime_manager.openshell_sandbox.emit_lifecycle"
        ):
            manager.get_or_start_runtime(
                session_id="session-1",
                user_id="user-1",
                knowledge_graph_id="kg-1",
                mode="graph_management",
                bootstrap=None,
            )

        ensure_provider.assert_called_once_with(
            provider_name="kartograph-gma",
            project_id="my-project",
            region="us-east5",
            gcloud_config_mount="/host/.config/gcloud",
            auth_mode="vertex",
        )
        env = exec_background.call_args.kwargs["env"]
        assert env["ANTHROPIC_BASE_URL"] == "https://inference.local"
        assert env["ANTHROPIC_API_KEY"] == "unused"
        assert env["CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS"] == "1"
        assert "CLAUDE_CODE_USE_VERTEX" not in env
        assert "GOOGLE_APPLICATION_CREDENTIALS" not in env

    def test_terminate_runtime_deletes_sandbox(self) -> None:
        manager = OpenShellStickySessionRuntimeManager(
            sticky_image="kartograph-agent-runtime:dev",
            session_ttl=timedelta(minutes=30),
        )
        probe = MagicMock()
        manager._probe = probe  # noqa: SLF001
        with patch(
            "extraction.infrastructure.openshell.openshell_sticky_session_runtime_manager.openshell_sandbox.sandbox_exists",
            return_value=True,
        ), patch(
            "extraction.infrastructure.openshell.openshell_sticky_session_runtime_manager.openshell_gateway.ensure_gateway_registered"
        ), patch(
            "extraction.infrastructure.openshell.openshell_sticky_session_runtime_manager.openshell_sandbox.delete_sandbox"
        ), patch(
            "extraction.infrastructure.openshell.openshell_sticky_session_runtime_manager.openshell_sandbox.create_sandbox"
        ), patch(
            "extraction.infrastructure.openshell.openshell_sticky_session_runtime_manager.openshell_sandbox.apply_policy"
        ), patch(
            "extraction.infrastructure.openshell.openshell_sticky_session_runtime_manager.openshell_sandbox.exec_background"
        ), patch(
            "extraction.infrastructure.openshell.openshell_sticky_session_runtime_manager.openshell_sandbox.start_forward"
        ), patch(
            "extraction.infrastructure.openshell.openshell_sticky_session_runtime_manager.openshell_sandbox.emit_lifecycle"
        ):
            manager.get_or_start_runtime(
                session_id="session-1",
                user_id="user-1",
                knowledge_graph_id="kg-1",
                mode="graph_management",
                bootstrap=None,
            )

        with patch(
            "extraction.infrastructure.openshell.openshell_sticky_session_runtime_manager.openshell_sandbox.stop_forward"
        ) as stop_forward, patch(
            "extraction.infrastructure.openshell.openshell_sticky_session_runtime_manager.openshell_sandbox.delete_sandbox"
        ) as delete_sandbox, patch(
            "extraction.infrastructure.openshell.openshell_sticky_session_runtime_manager.openshell_sandbox.emit_lifecycle"
        ):
            manager.terminate_runtime(
                session_id="session-1",
                user_id="user-1",
                knowledge_graph_id="kg-1",
                mode="graph_management",
            )

        stop_forward.assert_called_once()
        delete_sandbox.assert_called_once()
