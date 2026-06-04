"""Safe path resolution under the sticky session workspace mount."""

from __future__ import annotations

from pathlib import Path


def resolve_workspace_file(workspace_dir: str, relative_path: str) -> Path:
    """Resolve a user-supplied path that must stay inside the workspace root."""
    root = Path(workspace_dir).resolve()
    candidate = (root / relative_path.strip()).resolve()
    if root != candidate and root not in candidate.parents:
        raise ValueError(f"Path must stay within workspace: {relative_path}")
    if not candidate.is_file():
        raise ValueError(f"Workspace file not found: {relative_path}")
    return candidate


def read_workspace_text_file(workspace_dir: str, relative_path: str) -> str:
    """Read a text file from the workspace using a relative path."""
    return resolve_workspace_file(workspace_dir, relative_path).read_text(encoding="utf-8")
