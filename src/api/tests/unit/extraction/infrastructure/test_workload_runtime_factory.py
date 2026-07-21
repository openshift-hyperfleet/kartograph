"""Unit tests for extraction workload runtime factory."""

from __future__ import annotations

from pathlib import Path

from extraction.infrastructure.container_workload_runtime import (
    ContainerEphemeralExtractionWorkerLauncher,
    ContainerStickySessionRuntimeManager,
)
from extraction.infrastructure.local_runtime.chat_agent import LocalStickyChatAgent
from extraction.infrastructure.local_runtime.sticky_session_runtime_manager import (
    LocalStickySessionRuntimeManager,
)
from extraction.infrastructure.openshell.openshell_sticky_session_runtime_manager import (
    OpenShellStickySessionRuntimeManager,
)
from extraction.infrastructure.workload_runtime import (
    InMemoryEphemeralExtractionWorkerLauncher,
    InMemoryStickySessionRuntimeManager,
)
from extraction.infrastructure.vertex_inference_token_issuer import (
    ImpersonatedVertexInferenceTokenIssuer,
)
from extraction.infrastructure.workload_runtime_factory import (
    create_ephemeral_extraction_worker_launcher,
    create_extraction_chat_agent,
    create_sticky_session_runtime_manager,
    get_vertex_inference_token_issuer,
)
from extraction.infrastructure.workload_runtime_settings import (
    ExtractionWorkloadRuntimeSettings,
    get_extraction_workload_runtime_settings,
)


class TestWorkloadRuntimeFactory:
    def test_memory_backend_returns_in_memory_adapters(self) -> None:
        settings = ExtractionWorkloadRuntimeSettings(backend="memory")

        sticky = create_sticky_session_runtime_manager(settings)
        worker = create_ephemeral_extraction_worker_launcher(settings)

        assert isinstance(sticky, InMemoryStickySessionRuntimeManager)
        assert isinstance(worker, InMemoryEphemeralExtractionWorkerLauncher)

    def test_container_backend_returns_container_adapters(self) -> None:
        settings = ExtractionWorkloadRuntimeSettings(
            backend="container",
            container_engine="docker",
        )

        sticky = create_sticky_session_runtime_manager(settings)
        worker = create_ephemeral_extraction_worker_launcher(settings)

        assert isinstance(sticky, ContainerStickySessionRuntimeManager)
        assert isinstance(worker, ContainerEphemeralExtractionWorkerLauncher)

    def test_openshell_backend_returns_openshell_sticky_manager(self) -> None:
        settings = ExtractionWorkloadRuntimeSettings(backend="openshell")

        sticky = create_sticky_session_runtime_manager(settings)

        assert isinstance(sticky, OpenShellStickySessionRuntimeManager)
        assert settings.job_runner == "openshell"

    def test_local_backend_returns_local_sticky_manager(self) -> None:
        settings = ExtractionWorkloadRuntimeSettings(backend="local")

        sticky = create_sticky_session_runtime_manager(settings)

        assert isinstance(sticky, LocalStickySessionRuntimeManager)
        # Safe placeholder until a real local job runner adapter lands;
        # never silently agentic_ci/openshell for a backend that has none.
        assert settings.job_runner == "stub"

    def test_local_backend_honors_dispatch_settings(self) -> None:
        settings = ExtractionWorkloadRuntimeSettings(
            backend="local",
            sticky_image="kartograph-agent-runtime:custom",
            local_dispatch_timeout_seconds=30.0,
            local_poll_interval_seconds=2.0,
            local_presence_timeout_seconds=10.0,
            vertex_project_id="proj-xyz",
            vertex_region="us-central1",
        )

        sticky = create_sticky_session_runtime_manager(settings)

        assert isinstance(sticky, LocalStickySessionRuntimeManager)
        assert sticky._sticky_image == "kartograph-agent-runtime:custom"
        assert sticky._dispatch_timeout_seconds == 30.0
        assert sticky._poll_interval_seconds == 2.0
        assert sticky._presence_timeout_seconds == 10.0
        assert sticky._vertex_project_id == "proj-xyz"
        assert sticky._vertex_region == "us-central1"

    def test_local_backend_returns_local_chat_agent_honoring_dispatch_settings(
        self,
    ) -> None:
        settings = ExtractionWorkloadRuntimeSettings(
            backend="local",
            local_chat_turn_timeout_seconds=45.0,
            local_poll_interval_seconds=2.0,
            local_presence_timeout_seconds=10.0,
        )

        agent = create_extraction_chat_agent(settings)

        assert isinstance(agent, LocalStickyChatAgent)
        assert agent._dispatch_timeout_seconds == 45.0
        assert agent._poll_interval_seconds == 2.0
        assert agent._presence_timeout_seconds == 10.0

    def test_outbox_extraction_handler_uses_runtime_factory_wiring(self) -> None:
        main_source = Path(__file__).resolve().parents[4] / "main.py"
        content = main_source.read_text(encoding="utf-8")

        assert "create_ephemeral_extraction_worker_launcher" in content
        assert "InMemoryEphemeralExtractionWorkerLauncher" not in content


class TestGetVertexInferenceTokenIssuer:
    def teardown_method(self) -> None:
        get_vertex_inference_token_issuer.cache_clear()
        get_extraction_workload_runtime_settings.cache_clear()

    def test_builds_issuer_from_settings(self, monkeypatch) -> None:
        get_vertex_inference_token_issuer.cache_clear()
        get_extraction_workload_runtime_settings.cache_clear()
        monkeypatch.setenv(
            "KARTOGRAPH_EXTRACTION_RUNTIME_VERTEX_LOCAL_AGENT_SERVICE_ACCOUNT_EMAIL",
            "vertex-inference@proj.iam.gserviceaccount.com",
        )
        monkeypatch.setenv(
            "KARTOGRAPH_EXTRACTION_RUNTIME_VERTEX_LOCAL_AGENT_TOKEN_LIFETIME_SECONDS",
            "900",
        )
        monkeypatch.setenv(
            "KARTOGRAPH_EXTRACTION_RUNTIME_GCLOUD_CONFIG_MOUNT", "/gcloud/config"
        )

        issuer = get_vertex_inference_token_issuer()

        assert isinstance(issuer, ImpersonatedVertexInferenceTokenIssuer)
        assert (
            issuer._service_account_email
            == "vertex-inference@proj.iam.gserviceaccount.com"
        )
        assert issuer._lifetime_seconds == 900
        assert issuer._source_credentials_path == (
            "/gcloud/config/application_default_credentials.json"
        )

    def test_no_source_credentials_path_when_mount_unset(self, monkeypatch) -> None:
        get_vertex_inference_token_issuer.cache_clear()
        get_extraction_workload_runtime_settings.cache_clear()
        monkeypatch.delenv(
            "KARTOGRAPH_EXTRACTION_RUNTIME_GCLOUD_CONFIG_MOUNT", raising=False
        )
        monkeypatch.delenv("KARTOGRAPH_GCLOUD_CONFIG_MOUNT", raising=False)

        issuer = get_vertex_inference_token_issuer()

        assert issuer._source_credentials_path is None
