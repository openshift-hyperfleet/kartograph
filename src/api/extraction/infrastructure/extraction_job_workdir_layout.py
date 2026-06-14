"""Agentic-ci workspace layout for extraction job containers."""

from __future__ import annotations

import shutil
from pathlib import Path

from extraction.infrastructure.extraction_job_helpers import (
    HELPER_BUNDLE_NAMES,
    HELPER_SCRIPT_NAMES,
    HELPERS_CONTAINER_DIR,
    HELPERS_DIR,
)
from extraction.infrastructure.sticky_session_workspace_permissions import (
    ensure_agent_workspace_permissions,
)

MUTATIONS_DIRNAME = "mutations"
MUTATION_RESULT_FILENAME = "result.json"


def prepare_agentic_ci_workspace(
    job_root: Path,
    *,
    container_run_uid: int | None,
    container_run_gid: int | None,
) -> None:
    """Create writable agent artifacts and copy bundled helpers (context_writer pattern)."""
    mutations_dir = job_root / MUTATIONS_DIRNAME
    mutations_dir.mkdir(parents=True, exist_ok=True)

    helpers_dir = job_root / HELPERS_CONTAINER_DIR
    helpers_dir.mkdir(parents=True, exist_ok=True)
    for name in HELPER_BUNDLE_NAMES:
        source = HELPERS_DIR / name
        if source.is_file():
            target = helpers_dir / name
            shutil.copy2(source, target)
            if name in HELPER_SCRIPT_NAMES:
                target.chmod(target.stat().st_mode | 0o111)

    ensure_agent_workspace_permissions(
        job_root,
        container_run_uid=container_run_uid,
        container_run_gid=container_run_gid,
    )


def mutation_result_path(job_root: Path) -> Path:
    return job_root / MUTATIONS_DIRNAME / MUTATION_RESULT_FILENAME
