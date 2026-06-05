"""Docker bind mounts for sticky session workspaces.

Repository snapshots stay read-only; ``instance_generators/`` must be writable so the
agent can author scanner scripts and JSON/JSONL outputs for bulk prepopulation.
"""

from __future__ import annotations

WORKSPACE_READONLY_SUBDIRS: tuple[str, ...] = (
    "repository-files",
    "ingestion-context",
)
WORKSPACE_WRITABLE_SUBDIRS: tuple[str, ...] = ("instance_generators",)
WORKSPACE_READONLY_ROOT_FILES: tuple[str, ...] = (
    "sources-index.json",
    "knowledge-graph-id",
)


def build_sticky_session_workspace_binds(
    *,
    host_session_work_dir: str,
    container_work_mount: str,
) -> tuple[str, ...]:
    """Return bind specs that expose a split read/write workspace layout."""
    host_root = host_session_work_dir.rstrip("/")
    container_root = container_work_mount.rstrip("/")
    binds: list[str] = []
    for subdir in WORKSPACE_READONLY_SUBDIRS:
        binds.append(f"{host_root}/{subdir}:{container_root}/{subdir}:ro")
    for subdir in WORKSPACE_WRITABLE_SUBDIRS:
        binds.append(f"{host_root}/{subdir}:{container_root}/{subdir}")
    for filename in WORKSPACE_READONLY_ROOT_FILES:
        binds.append(f"{host_root}/{filename}:{container_root}/{filename}:ro")
    return tuple(binds)
