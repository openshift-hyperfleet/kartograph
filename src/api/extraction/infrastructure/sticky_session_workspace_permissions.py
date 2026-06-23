"""Ensure sticky session workspaces are writable by the agent container user."""

from __future__ import annotations

import os
import stat
from pathlib import Path

_REPOSITORY_FILES_DIRNAME = "repository-files"


def _is_under_repository_files(path: Path, session_root: Path) -> bool:
    try:
        path.relative_to(session_root / _REPOSITORY_FILES_DIRNAME)
    except ValueError:
        return False
    return True


def ensure_agent_workspace_permissions(
    session_root: Path,
    *,
    container_run_uid: int | None,
    container_run_gid: int | None,
) -> None:
    """Grant the sticky container user write access everywhere except repository-files."""
    if container_run_uid is not None and container_run_gid is not None:
        _chown_writable_tree(
            session_root,
            uid=container_run_uid,
            gid=container_run_gid,
        )
        return
    _chmod_writable_tree(session_root)


def _chown_writable_tree(session_root: Path, *, uid: int, gid: int) -> None:
    for path in sorted(
        session_root.rglob("*"), key=lambda item: len(item.parts), reverse=True
    ):
        if _is_under_repository_files(path, session_root):
            continue
        if path.is_symlink():
            continue
        os.chown(path, uid, gid)
        os.chmod(path, 0o775 if path.is_dir() else 0o664)
    if not _is_under_repository_files(session_root, session_root):
        os.chown(session_root, uid, gid)
        os.chmod(session_root, 0o775)


def _chmod_writable_tree(session_root: Path) -> None:
    for path in sorted(
        session_root.rglob("*"), key=lambda item: len(item.parts), reverse=True
    ):
        if _is_under_repository_files(path, session_root):
            continue
        if path.is_symlink():
            continue
        mode = path.stat().st_mode
        desired = mode | stat.S_IWUSR | stat.S_IWGRP
        os.chmod(path, desired)
    session_root.chmod(session_root.stat().st_mode | stat.S_IWUSR | stat.S_IWGRP)
