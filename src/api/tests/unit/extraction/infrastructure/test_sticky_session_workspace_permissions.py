"""Unit tests for sticky session workspace permission normalization."""

from __future__ import annotations

import os
import stat
from pathlib import Path

from extraction.infrastructure.sticky_session_workspace_permissions import (
    ensure_agent_workspace_permissions,
)


def test_chown_grants_container_user_write_access_outside_repository_files(tmp_path: Path) -> None:
    session_root = tmp_path / "session"
    generators = session_root / "instance_generators" / "out"
    repo_files = session_root / "repository-files" / "hyperfleet-e2e"
    generators.mkdir(parents=True)
    repo_files.mkdir(parents=True)
    (generators / "test_instances.json").write_text("[]\n", encoding="utf-8")
    (repo_files / "example.go").write_text("package main\n", encoding="utf-8")

    target_uid = os.getuid()
    target_gid = os.getgid()
    ensure_agent_workspace_permissions(
        session_root,
        container_run_uid=target_uid,
        container_run_gid=target_gid,
    )

    assert (generators / "test_instances.json").stat().st_uid == target_uid
    assert (generators / "test_instances.json").stat().st_gid == target_gid
    assert (session_root / "instance_generators").stat().st_mode & stat.S_IWUSR


def test_chmod_fallback_makes_writable_paths_world_writable(tmp_path: Path) -> None:
    session_root = tmp_path / "session"
    out_dir = session_root / "instance_generators" / "out"
    out_dir.mkdir(parents=True)
    out_dir.chmod(0o755)

    ensure_agent_workspace_permissions(
        session_root,
        container_run_uid=None,
        container_run_gid=None,
    )

    mode = out_dir.stat().st_mode
    assert mode & stat.S_IWOTH


def test_materializer_applies_container_user_permissions(tmp_path: Path) -> None:
    from extraction.infrastructure.sticky_session_workdir_materializer import (
        StickySessionWorkdirMaterializer,
    )

    target_uid = os.getuid()
    target_gid = os.getgid()
    materializer = StickySessionWorkdirMaterializer(
        job_package_work_dir=tmp_path,
        container_run_uid=target_uid,
        container_run_gid=target_gid,
    )

    session_root = materializer.prepare(
        session_id="session-perms",
        knowledge_graph_id="kg-1",
        job_packages=(),
    )

    scanner_path = session_root / "instance_generators" / "E2ETest.py"
    scanner_path.write_text("# scanner\n", encoding="utf-8")
    out_path = session_root / "instance_generators" / "out" / "E2ETest_instances.json"
    out_path.write_text("[]\n", encoding="utf-8")

    assert scanner_path.stat().st_uid == target_uid
    assert out_path.stat().st_uid == target_uid
