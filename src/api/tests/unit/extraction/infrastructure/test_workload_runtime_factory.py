"""Unit tests for extraction workload runtime factory."""

from __future__ import annotations

from pathlib import Path

from extraction.infrastructure.container_workload_runtime import (
    ContainerEphemeralExtractionWorkerLauncher,
    ContainerStickySessionRuntimeManager,
)
from extraction.infrastructure.workload_runtime import (
    InMemoryEphemeralExtractionWorkerLauncher,
    InMemoryStickySessionRuntimeManager,
)
from extraction.infrastructure.workload_runtime_factory import (
    create_ephemeral_extraction_worker_launcher,
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

    def test_outbox_extraction_handler_uses_runtime_factory_wiring(self) -> None:
        main_source = Path(__file__).resolve().parents[4] / "main.py"
        content = main_source.read_text(encoding="utf-8")

        assert "create_ephemeral_extraction_worker_launcher" in content
        assert "InMemoryEphemeralExtractionWorkerLauncher" not in content
