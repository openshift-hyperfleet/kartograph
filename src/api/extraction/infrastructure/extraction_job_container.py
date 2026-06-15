"""Container and OpenShell sandbox lifecycle helpers for extraction jobs."""

from __future__ import annotations

import re

from shared_kernel.container_runtime.factory import create_container_runtime

_CONTAINER_NAME_SAFE = re.compile(r"[^a-zA-Z0-9_.-]+")
_EXTRACTION_SANDBOX_PREFIX = "kartograph-extract-"


def extraction_job_container_name(job_id: str) -> str:
    cleaned = _CONTAINER_NAME_SAFE.sub("-", job_id).strip("-")
    return f"{_EXTRACTION_SANDBOX_PREFIX}{cleaned}"[:63].rstrip("-_.")


def stop_extraction_job_container(*, job_id: str, container_engine: str = "auto") -> bool:
    """Stop and remove the extraction container for one job, if it exists."""
    runtime = create_container_runtime(container_engine)
    name = extraction_job_container_name(job_id)
    return runtime.remove_by_name(name, force=True)


def stop_extraction_job_containers(
    *,
    job_ids: tuple[str, ...] | list[str],
    container_engine: str = "auto",
) -> int:
    """Stop and remove extraction containers for many jobs. Returns count removed."""
    stopped = 0
    for job_id in job_ids:
        if stop_extraction_job_container(job_id=job_id, container_engine=container_engine):
            stopped += 1
    return stopped


def stop_extraction_job_sandboxes(
    *,
    job_ids: tuple[str, ...] | list[str],
    sweep_orphans: bool = False,
) -> int:
    """Delete OpenShell sandboxes for extraction jobs. Returns count deleted."""
    from extraction.infrastructure.openshell import sandbox as openshell_sandbox

    stopped = openshell_sandbox.stop_extraction_job_sandboxes(job_ids=job_ids)
    if sweep_orphans:
        stopped += openshell_sandbox.delete_sandboxes_by_prefix(_EXTRACTION_SANDBOX_PREFIX)
    return stopped


def stop_extraction_job_runtimes(
    *,
    job_ids: tuple[str, ...] | list[str],
    container_engine: str = "auto",
    openshell_backend: bool = False,
) -> tuple[int, int]:
    """Stop Docker containers and/or OpenShell sandboxes for extraction jobs."""
    containers_stopped = stop_extraction_job_containers(
        job_ids=job_ids,
        container_engine=container_engine,
    )
    sandboxes_stopped = 0
    if openshell_backend:
        sandboxes_stopped = stop_extraction_job_sandboxes(
            job_ids=job_ids,
            sweep_orphans=True,
        )
    return containers_stopped, sandboxes_stopped
