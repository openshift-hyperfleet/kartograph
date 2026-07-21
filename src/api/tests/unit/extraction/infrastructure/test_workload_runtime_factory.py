"""Unit tests for extraction workload runtime factory."""

from __future__ import annotations

from pathlib import Path

import pytest

from extraction.infrastructure.container_workload_runtime import (
    ContainerEphemeralExtractionWorkerLauncher,
    ContainerStickySessionRuntimeManager,
)
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
from extraction.infrastructure.workload_runtime_factory import (
    create_ephemeral_extraction_worker_launcher,
    create_extraction_chat_agent,
    create_sticky_session_runtime_manager,
)
from extraction.infrastructure.workload_runtime_settings import (
    ExtractionWorkloadRuntimeSettings,
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
            local_dispatch_timeout_seconds=30.0,
            local_poll_interval_seconds=2.0,
            local_presence_timeout_seconds=10.0,
        )

        sticky = create_sticky_session_runtime_manager(settings)

        assert isinstance(sticky, LocalStickySessionRuntimeManager)
        assert sticky._dispatch_timeout_seconds == 30.0
        assert sticky._poll_interval_seconds == 2.0
        assert sticky._presence_timeout_seconds == 10.0

    def test_local_backend_chat_agent_not_yet_implemented(self) -> None:
        settings = ExtractionWorkloadRuntimeSettings(backend="local")

        with pytest.raises(NotImplementedError):
            create_extraction_chat_agent(settings)

    def test_outbox_extraction_handler_uses_runtime_factory_wiring(self) -> None:
        main_source = Path(__file__).resolve().parents[4] / "main.py"
        content = main_source.read_text(encoding="utf-8")

        assert "create_ephemeral_extraction_worker_launcher" in content
        assert "InMemoryEphemeralExtractionWorkerLauncher" not in content
