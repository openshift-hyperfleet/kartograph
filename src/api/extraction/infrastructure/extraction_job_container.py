"""Container lifecycle helpers for agentic-ci extraction jobs."""

from __future__ import annotations

import re

from shared_kernel.container_runtime.factory import create_container_runtime

_CONTAINER_NAME_SAFE = re.compile(r"[^a-zA-Z0-9_.-]+")


def extraction_job_container_name(job_id: str) -> str:
    cleaned = _CONTAINER_NAME_SAFE.sub("-", job_id).strip("-")
    return f"kartograph-extract-{cleaned}"[:63].rstrip("-_.")


def stop_extraction_job_container(*, job_id: str, container_engine: str = "auto") -> bool:
    """Stop and remove the extraction container for one job, if it exists."""
    runtime = create_container_runtime(container_engine)
    name = extraction_job_container_name(job_id)
    return runtime.remove_by_name(name, force=True)
