"""Tests for maintenance job materialization."""

from __future__ import annotations

from infrastructure.management.maintenance_job_materializer import (
    MAINTENANCE_JOB_SET_NAME,
    ChangedMaintenanceFile,
    materialize_maintenance_jobs,
)


def _changed(path: str, *, folder: str = "repo-a", status: str = "modified") -> ChangedMaintenanceFile:
    return ChangedMaintenanceFile(
        data_source_id="ds-a",
        repository_folder=folder,
        path=path,
        status=status,
        package_id="pkg-a",
        patch=f"diff for {path}",
    )


def test_materialize_maintenance_jobs_batches_across_sources() -> None:
    changed = [
        _changed("a.txt", folder="repo-a"),
        *[_changed(f"b{i}.txt", folder="repo-b") for i in range(10)],
        *[_changed(f"c{i}.txt", folder="repo-c") for i in range(4)],
    ]

    jobs = materialize_maintenance_jobs(
        knowledge_graph_id="kg-001",
        changed_files=changed,
        files_per_job=2,
    )

    assert len(jobs) == 8
    assert all(job.job_set_name == MAINTENANCE_JOB_SET_NAME for job in jobs)
    assert all(job.strategy == "by_files" for job in jobs)
    assert sum(len(job.target_files) for job in jobs) == 15
    assert "diff for a.txt" in jobs[0].description


def test_materialize_maintenance_jobs_returns_empty_for_no_changes() -> None:
    assert materialize_maintenance_jobs(
        knowledge_graph_id="kg-001",
        changed_files=[],
        files_per_job=2,
    ) == []
