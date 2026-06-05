"""Unit tests for sticky session workspace bind layout."""

from __future__ import annotations

from extraction.infrastructure.sticky_session_workspace_binds import (
    build_sticky_session_workspace_binds,
)


def test_workspace_binds_split_read_only_and_writable_paths() -> None:
    binds = build_sticky_session_workspace_binds(
        host_session_work_dir="/host/session",
        container_work_mount="/workspace",
    )

    assert "/host/session/repository-files:/workspace/repository-files:ro" in binds
    assert "/host/session/ingestion-context:/workspace/ingestion-context:ro" in binds
    assert "/host/session/instance_generators:/workspace/instance_generators" in binds
    assert "/host/session/sources-index.json:/workspace/sources-index.json:ro" in binds
    assert "/host/session/knowledge-graph-id:/workspace/knowledge-graph-id:ro" in binds
    assert not any(bind.endswith("/workspace:ro") for bind in binds)
