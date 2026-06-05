"""Docker bind mounts for sticky session workspaces.

The full workspace is writable so the agent can author scanner scripts and outputs.
``repository-files/`` is overlaid read-only so ingested source snapshots stay immutable.
"""

from __future__ import annotations

WORKSPACE_READONLY_SUBDIRS: tuple[str, ...] = ("repository-files",)


def build_sticky_session_workspace_binds(
    *,
    host_session_work_dir: str,
    container_work_mount: str,
) -> tuple[str, ...]:
    """Return bind specs that expose a writable workspace with read-only repository files."""
    host_root = host_session_work_dir.rstrip("/")
    container_root = container_work_mount.rstrip("/")
    binds = [f"{host_root}:{container_root}"]
    for subdir in WORKSPACE_READONLY_SUBDIRS:
        binds.append(f"{host_root}/{subdir}:{container_root}/{subdir}:ro")
    return tuple(binds)
