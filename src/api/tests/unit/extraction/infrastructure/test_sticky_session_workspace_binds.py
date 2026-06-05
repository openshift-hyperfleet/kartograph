"""Unit tests for sticky session workspace bind layout."""

from __future__ import annotations

from extraction.infrastructure.sticky_session_workspace_binds import (
    build_sticky_session_workspace_binds,
)


def test_workspace_binds_mount_full_workspace_with_read_only_repository_files() -> None:
    binds = build_sticky_session_workspace_binds(
        host_session_work_dir="/host/session",
        container_work_mount="/workspace",
    )

    assert "/host/session:/workspace" in binds
    assert "/host/session/repository-files:/workspace/repository-files:ro" in binds
    assert len(binds) == 2
