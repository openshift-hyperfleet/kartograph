"""Integration test fixtures for Extraction bounded context."""

from __future__ import annotations

import shutil
import subprocess

import pytest

from shared_kernel.container_runtime.factory import create_container_runtime

# Re-export Management integration fixtures for extraction integration tests.
from tests.integration.management.conftest import (  # noqa: F401
    async_session,
    clean_management_data,
    data_source_repository,
    data_source_sync_run_repository,
    knowledge_graph_repository,
    management_db_settings,
    session_factory,
    test_tenant,
    test_workspace,
)


def _engine_available(engine: str) -> bool:
    if shutil.which(engine) is None:
        return False
    result = subprocess.run(
        [engine, "info"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


@pytest.fixture(scope="session")
def container_runtime_engine() -> str:
    """Return the container engine binary used for integration tests."""
    for engine in ("docker", "podman"):
        if _engine_available(engine):
            return engine
    pytest.skip("No docker/podman engine available for container runtime tests")


@pytest.fixture
def container_runtime(container_runtime_engine: str):
    """Provide a CLI container runtime for integration tests."""
    return create_container_runtime(container_runtime_engine)
